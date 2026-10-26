"""
End-to-End API Persistence Test (Section A.2).
Tests the real FastAPI endpoints (/api/session/start and /api/chat)
with database reloaded between every single message:
  question -> doubt -> clarity check -> confirmation -> resume -> graded answer

Asserts:
1. BKT mastery is strictly unchanged across doubt and confirmation turns.
2. The exact same pending question is re-asked after the reload upon confirmation.
3. Checkpoint stack is pushed on doubt and popped on confirmation.
4. Database state rehydrates cleanly without losing extended state fields.
"""

import unittest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from multi_agent_tutor.api.server import app
from multi_agent_tutor.db.database import init_db
from multi_agent_tutor.db.repository import SessionRepository
import uuid
from multi_agent_tutor.app.schemas.diagnostic import (
    DiagnosticQuestion,
    DiagnosticQuestionSet,
)
from multi_agent_tutor.app.schemas.assessment import AssessmentResult
from multi_agent_tutor.app.schemas.socratic import SocraticResponse
from multi_agent_tutor.app.schemas.critic import CriticOutput
from multi_agent_tutor.app.schemas.bkt import BKTState
from multi_agent_tutor.app.schemas.teaching_assessment import TeachingAssessment
from multi_agent_tutor.app.schemas.curriculum import CurriculumConcept
from multi_agent_tutor.app.schemas.learning_path import LearningPath, LearningPathStep


class TestE2EApiPersistence(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        """Initialize database before each test run."""
        await init_db()
        self.client = TestClient(app)
        for sid in ["persistence_student_01", "student_bkt_test_01"]:
            prev = await SessionRepository.list_student_sessions(sid)
            for s in prev:
                await SessionRepository.delete_session(s["session_id"])

    async def test_e2e_question_doubt_reload_confirm_answer_flow(self):
        """
        Executes end-to-end conversation flow through HTTP endpoints:
        Turn 0: /api/session/start -> returns initial diagnostic question
        Turn 1: /api/chat (Doubt) -> returns doubt resolution + clarity check; BKT unchanged
        Turn 2: /api/chat (Confirmation) -> returns resume bridge restating question; BKT unchanged
        Turn 3: /api/chat (Graded Answer) -> grades answer; BKT advances
        """
        mock_diag_q = DiagnosticQuestion(
            question_id="diag_q1",
            concept="bs_array_invariants",
            question="Why must an array be sorted before applying Binary Search?",
            difficulty="beginner",
            question_type="conceptual",
            reason="Check prerequisite understanding",
            evaluation_criteria=["Eliminate half of search space at each step"],
        )
        mock_diag_set = DiagnosticQuestionSet(
            topic="Binary Search",
            questions=[mock_diag_q],
        )

        mock_doubt_content = MagicMock()
        mock_doubt_content.content = (
            "Great question! Binary search relies on sorted order because comparing your target "
            "against the middle element tells you definitively whether to discard the left or right half."
        )

        mock_assessment = AssessmentResult(
            correctness="correct",
            score=1.0,
            confidence=0.98,
            evidence_of_understanding=["Eliminates half of the search space at each step"],
            misconceptions=[],
            feedback="Strong, clear explanation of the binary elimination principle.",
        )

        mock_socratic = SocraticResponse(
            message="Welcome to the teaching phase for Binary Search!",
            question="What is the first step when searching in a sorted array?",
            action="initial",
            question_type="conceptual",
            expected_answer="Compute midpoint",
            evaluator_type="llm",
            evaluation_criteria=["Midpoint computation"],
        )
        mock_critic = CriticOutput(
            passed=True,
            score=10,
            feedback="Accurate and pedagogical.",
        )

        print("\n" + "=" * 90)
        print("END-TO-END API PERSISTENCE & LIFECYCLE AUDIT (Section A.2)".center(90))
        print("=" * 90)

        with patch("multi_agent_tutor.app.Agents.diagnostic.generate_diagnostic_questions") as mock_generate_diag, \
             patch("multi_agent_tutor.app.Agents.doubt_agent._doubt_chain") as mock_doubt_chain, \
             patch("multi_agent_tutor.app.Agents.assessment.assessment_chain") as mock_ass_chain, \
             patch("multi_agent_tutor.app.Agents.tutor.sage_chain") as mock_sage_chain, \
             patch("multi_agent_tutor.app.Agents.critic.critic_chain") as mock_critic_chain:

            mock_generate_diag.return_value = mock_diag_set
            mock_doubt_chain.invoke.return_value = mock_doubt_content
            mock_ass_chain.invoke.return_value = mock_assessment
            mock_sage_chain.invoke.return_value = mock_socratic
            mock_critic_chain.invoke.return_value = mock_critic

            # -------------------------------------------------------------
            # STEP 0: Start Session via /api/session/start
            # -------------------------------------------------------------
            start_payload = {
                "topic": "Binary Search",
                "student_id": "persistence_student_01",
                "depth_level": "deep",
            }
            res0 = self.client.post("/api/session/start", json=start_payload)
            self.assertEqual(res0.status_code, 200, f"Failed to start session: {res0.text}")
            data0 = res0.json()
            session_id = data0["session_id"]
            self.assertTrue(bool(session_id))

            # RELOAD FROM DB: verify session is saved with pending_question
            db_s0 = await SessionRepository.get_session(session_id)
            self.assertIsNotNone(db_s0)
            initial_bkt_mastery = dict(db_s0["mastery"])
            pending_q0 = db_s0["state"].get("pending_question")
            self.assertIsNotNone(pending_q0, "pending_question must be present in DB after start.")
            pq_text = pending_q0.get("question")
            self.assertTrue("sorted" in pq_text.lower() and "array" in pq_text.lower())

            print(f"[Turn 0: Start Session] ID: {session_id[:8]}... | Initial Question: '{pq_text}'")
            print(f"       Initial BKT Mastery Snapshot: {initial_bkt_mastery}")

            # -------------------------------------------------------------
            # STEP 1: Student asks a DOUBT via /api/chat
            # -------------------------------------------------------------
            doubt_msg = "Why does the array need to be sorted first? What happens if it isn't?"
            res1 = self.client.post("/api/chat", json={"session_id": session_id, "message": doubt_msg})
            self.assertEqual(res1.status_code, 200)
            data1 = res1.json()
            tutor_doubt_resp = data1["latest_message"]["content"]
            self.assertIn("Does that make sense, or should I explain it another way?", tutor_doubt_resp)

            # RELOAD FROM DB: verify doubt state persisted and BKT UNCHANGED
            db_s1 = await SessionRepository.get_session(session_id)
            doubt_state_1 = db_s1["state"].get("doubt_state", {})
            self.assertTrue(doubt_state_1.get("pending_clarity_check"), "pending_clarity_check must be True in DB.")
            self.assertEqual(len(doubt_state_1.get("doubt_stack", [])), 1, "doubt_stack must have 1 checkpoint.")
            self.assertEqual(db_s1["mastery"], initial_bkt_mastery, "BKT mastery MUST NOT change during a doubt!")
            self.assertEqual(db_s1["state"].get("pending_question"), pending_q0, "pending_question must be preserved.")

            print(f"\n[Turn 1: Student Doubt] Input: '{doubt_msg}'")
            print(f"       Tutor Response: '{tutor_doubt_resp[:85]}...'")
            print(f"       [DB RELOAD]: pending_clarity_check={doubt_state_1.get('pending_clarity_check')} | Stack Depth={len(doubt_state_1.get('doubt_stack'))}")
            print(f"       [BKT ASSERTION]: Mastery unchanged -> {db_s1['mastery']}")

            # -------------------------------------------------------------
            # STEP 2: Student CONFIRMS clarity via /api/chat
            # -------------------------------------------------------------
            confirm_msg = "makes sense, got it"
            res2 = self.client.post("/api/chat", json={"session_id": session_id, "message": confirm_msg})
            self.assertEqual(res2.status_code, 200)
            data2 = res2.json()
            resume_bridge_text = data2["latest_message"]["content"]

            # Assert the resume bridge restates the pending question
            self.assertIn("Awesome, glad that's clear! Let's get right back to where we were", resume_bridge_text)
            self.assertIn(pq_text, resume_bridge_text)

            # RELOAD FROM DB: verify checkpoint popped and BKT STILL UNCHANGED
            db_s2 = await SessionRepository.get_session(session_id)
            doubt_state_2 = db_s2["state"].get("doubt_state", {})
            self.assertFalse(doubt_state_2.get("pending_clarity_check"), "pending_clarity_check must be False after confirmation.")
            self.assertEqual(len(doubt_state_2.get("doubt_stack", [])), 0, "doubt_stack must be empty after popping checkpoint.")
            self.assertEqual(db_s2["mastery"], initial_bkt_mastery, "BKT mastery MUST NOT change during confirmation!")
            self.assertEqual(db_s2["state"].get("pending_question"), pending_q0, "pending_question must still be intact.")

            print(f"\n[Turn 2: Confirmation] Input: '{confirm_msg}'")
            print(f"       Tutor Bridge: '{resume_bridge_text[:85]}...'")
            print(f"       [DB RELOAD]: pending_clarity_check={doubt_state_2.get('pending_clarity_check')} | Stack Depth={len(doubt_state_2.get('doubt_stack'))}")
            print(f"       [BKT ASSERTION]: Mastery unchanged -> {db_s2['mastery']}")
            print(f"       [RESUME ASSERTION]: Original pending question re-asked cleanly.")

            # -------------------------------------------------------------
            # STEP 3: Student answers the pending question via /api/chat
            # -------------------------------------------------------------
            answer_msg = "Because sorted order allows binary search to eliminate half of the remaining elements at each step."
            res3 = self.client.post("/api/chat", json={"session_id": session_id, "message": answer_msg})
            self.assertEqual(res3.status_code, 200)
            data3 = res3.json()

            # RELOAD FROM DB: verify answer was evaluated and diagnostic assessment stored
            db_s3 = await SessionRepository.get_session(session_id)
            diag_state_3 = db_s3["state"].get("diagnostic_state", {})
            expected_qid = pending_q0.get("question_id")
            self.assertIn(expected_qid, diag_state_3.get("assessments", {}))
            ass_stored = diag_state_3["assessments"][expected_qid]
            score = getattr(ass_stored, "score", None) or (ass_stored.get("score") if isinstance(ass_stored, dict) else 0.0)
            self.assertEqual(score, 1.0)

            print(f"\n[Turn 3: Graded Answer] Input: '{answer_msg}'")
            print(f"       [DB RELOAD]: Diagnostic Question diag_q1 graded with score {score}.")
            print(f"       Turn successfully persisted across all DB reloads.")
            print("=" * 90)

    async def test_e2e_teaching_phase_bkt_invariant_with_real_mastery(self):
        """
        API-Level End-to-End Test in TEACHING PHASE (Requirement 1).
        Verifies with a REAL, non-empty initial mastery value P(L) = 0.35:
          tutor question -> doubt -> clarity check -> 'makes sense' -> same question re-asked -> graded answer
        
        Asserts:
        1. P(L) is strictly identical before and after doubt (Turn 1).
        2. P(L) is strictly identical before and after confirmation (Turn 2).
        3. Pending question is intact and re-asked cleanly after confirmation.
        4. P(L) changes ONLY after the graded answer (Turn 3).
        5. Database reloaded between every single message.
        """
        concept = "bs_array_invariants"
        initial_p = 0.35
        session_id = f"sess_teach_{uuid.uuid4().hex[:8]}"

        mock_doubt_content = MagicMock()
        mock_doubt_content.content = (
            "Great question! Binary search relies on sorted order because comparing your target "
            "against the middle element tells you definitively whether to discard the left or right half."
        )

        mock_teaching_assessment = TeachingAssessment(
            understanding="mastered",
            score=1.0,
            confidence=1.0,
            misconceptions=[],
            reasoning_quality="strong",
        )

        mock_socratic = SocraticResponse(
            message="Great work on understanding array invariants!",
            question="What is the next invariant in binary search?",
            action="probe",
            question_type="conceptual",
            expected_answer="Boundary invariants",
            evaluator_type="llm",
            evaluation_criteria=["Boundary conditions"],
        )

        mock_critic = CriticOutput(
            passed=True,
            score=10.0,
            feedback="Accurate and pedagogical.",
        )

        initial_state = {
            "student_id": "student_bkt_test_01",
            "target_topic": "Binary Search",
            "messages": [
                {
                    "role": "assistant",
                    "content": "Why must an array be sorted before applying Binary Search?",
                    "action": "probe",
                }
            ],
            "student_input": None,
            "diagnostic_state": {
                "completed": True,
                "questions": [],
                "current_question_id": None,
                "answers": {},
                "assessments": {},
            },
            "learner_profile": None,
            "mastery": {concept: initial_p},
            "bkt_states": {concept: BKTState(p_know=initial_p)},
            "curriculum": [
                CurriculumConcept(
                    concept_id=concept,
                    name="Array Invariants in Binary Search",
                    description="Understanding why sorting is required for binary search",
                    difficulty=1,
                    prerequisites=[],
                )
            ],
            "learning_path": LearningPath(
                target_topic="Binary Search",
                steps=[
                    LearningPathStep(
                        concept_id=concept,
                        status="ready",
                        mastery=initial_p,
                        reason="Current learning focus",
                    )
                ],
                current_concept_id=concept,
                completed=False,
            ),
            "current_concept": concept,
            "teaching": {
                "current_action": "probe",
                "current_question": "Why must an array be sorted before applying Binary Search?",
                "attempt_count": 0,
                "correct_checks": 0,
                "has_transfer_correct": False,
                "misconception_history": [],
                "current_objective": "Understand array sorting invariant",
                "concept_completed": False,
            },
            "teaching_assessment": None,
            "teaching_decision": None,
            "socratic_response": None,
            "rag_context": None,
            "tutor_response": "Why must an array be sorted before applying Binary Search?",
            "critic_result": None,
            "retry_count": 0,
            "misconceptions": [],
            "hint_level": 0,
            "depth_level": "deep",
            "assessment_done": True,
            "self_reported_level": "some_knowledge",
            "teaching_mode": "mode_1_qa",
            "teaching_step": "check",
            "pending_question": {
                "question": "Why must an array be sorted before applying Binary Search?",
                "concept_id": concept,
                "expected_answer": "Eliminate half of the elements",
                "evaluator_type": "llm",
                "evaluation_criteria": ["Elimination principle"],
                "question_type": "conceptual",
            },
            "current_subtopic": "bs_fundamentals",
            "subtopic_mastery": {"bs_fundamentals": {concept: initial_p}},
            "detected_intent": None,
            "doubt_state": {
                "doubt_stack": [],
                "doubt_log": [],
                "pending_clarity_check": False,
                "clarity_doubt_id": None,
                "active_doubt_response": None,
            },
            "misconceptions_log": [],
            "signals": {
                "hints_used": 0,
                "attempts": 0,
                "response_time": 0.0,
                "stated_confidence": None,
            },
            "last_practice_time": None,
            "study_plan": None,
            "skipped_concepts": [],
        }

        initial_msg = {
            "id": f"msg_{session_id}_0",
            "role": "assistant",
            "content": "Why must an array be sorted before applying Binary Search?",
            "question": "Why must an array be sorted before applying Binary Search?",
            "action": "probe",
            "metadata": {},
            "rag_context": None,
        }

        await SessionRepository.create_session(
            session_id=session_id,
            student_id="student_bkt_test_01",
            topic="Binary Search",
            state=initial_state,
            initial_message=initial_msg,
            bkt_history=[{"concept": concept, "p_know": initial_p}],
        )

        print("\n" + "=" * 90)
        print("TEACHING PHASE BKT INVARIANT AUDIT WITH REAL MASTERY P(L)=0.35".center(90))
        print("=" * 90)
        print(f"[Baseline Session Setup] Concept: '{concept}' | Initial P(L): {initial_p:.4f}")

        with patch("multi_agent_tutor.app.Agents.doubt_agent._doubt_chain") as mock_doubt_chain, \
             patch("multi_agent_tutor.app.Agents.teaching_assessor.assessment_chain") as mock_teaching_ass_chain, \
             patch("multi_agent_tutor.app.Agents.tutor.sage_chain") as mock_sage_chain, \
             patch("multi_agent_tutor.app.Agents.critic.critic_chain") as mock_critic_chain:

            mock_doubt_chain.invoke.return_value = mock_doubt_content
            mock_teaching_ass_chain.invoke.return_value = mock_teaching_assessment
            mock_sage_chain.invoke.return_value = mock_socratic
            mock_critic_chain.invoke.return_value = mock_critic

            # -------------------------------------------------------------
            # TURN 1: Student asks a DOUBT via /api/chat
            # -------------------------------------------------------------
            doubt_msg = "Why does the array need to be sorted first? What happens if it is unsorted?"
            res1 = self.client.post("/api/chat", json={"session_id": session_id, "message": doubt_msg})
            self.assertEqual(res1.status_code, 200)

            # RELOAD DB: verify P(L) is strictly identical
            db_s1 = await SessionRepository.get_session(session_id)
            p_after_doubt = db_s1["mastery"][concept]
            print(f"[Turn 1: Doubt] Input: '{doubt_msg}'")
            print(f"       -> Before: P(L)={initial_p:.4f} | After Doubt: P(L)={p_after_doubt:.4f} (STRICTLY EQUAL)")
            self.assertEqual(
                p_after_doubt,
                initial_p,
                f"BKT mastery changed during doubt! Expected {initial_p}, got {p_after_doubt}",
            )
            self.assertTrue(db_s1["state"]["doubt_state"]["pending_clarity_check"])

            # -------------------------------------------------------------
            # TURN 2: Student CONFIRMS clarity via /api/chat
            # -------------------------------------------------------------
            confirm_msg = "makes sense, got it"
            res2 = self.client.post("/api/chat", json={"session_id": session_id, "message": confirm_msg})
            self.assertEqual(res2.status_code, 200)
            data2 = res2.json()

            # RELOAD DB: verify P(L) is STILL strictly identical
            db_s2 = await SessionRepository.get_session(session_id)
            p_after_confirm = db_s2["mastery"][concept]
            print(f"[Turn 2: Confirmation] Input: '{confirm_msg}'")
            print(f"       -> Before: P(L)={initial_p:.4f} | After Confirm: P(L)={p_after_confirm:.4f} (STRICTLY EQUAL)")
            self.assertEqual(
                p_after_confirm,
                initial_p,
                f"BKT mastery changed during confirmation! Expected {initial_p}, got {p_after_confirm}",
            )
            self.assertFalse(db_s2["state"]["doubt_state"]["pending_clarity_check"])
            self.assertIn("Why must an array be sorted before applying Binary Search?", data2["latest_message"]["content"])

            # -------------------------------------------------------------
            # TURN 3: Student answers the pending question via /api/chat
            # -------------------------------------------------------------
            answer_msg = "Because sorted order allows binary search to eliminate half of the remaining elements at each step."
            res3 = self.client.post("/api/chat", json={"session_id": session_id, "message": answer_msg})
            self.assertEqual(res3.status_code, 200)

            # RELOAD DB: verify P(L) has updated after the graded answer
            db_s3 = await SessionRepository.get_session(session_id)
            p_after_answer = db_s3["mastery"][concept]
            print(f"[Turn 3: Graded Answer] Input: '{answer_msg}'")
            print(f"       -> Before: P(L)={initial_p:.4f} | After Graded Answer: P(L)={p_after_answer:.4f} (UPDATED)")
            self.assertNotEqual(
                p_after_answer,
                initial_p,
                "BKT mastery should update after a graded answer!",
            )
            self.assertGreater(p_after_answer, initial_p)
            self.assertAlmostEqual(p_after_answer, 0.6835, places=3)
            print(f"       Verified: P(L) updated strictly from {initial_p:.4f} to {p_after_answer:.4f}!")
            print("=" * 90)


if __name__ == "__main__":
    unittest.main()
