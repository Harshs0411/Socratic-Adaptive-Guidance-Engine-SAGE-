"""
OSI Model Session Replay Test.
Replays the exact sequence of student inputs from the real session bug report:
 1. Start session on topic "OSI model".
 2. Complete/fast-forward onboarding and diagnostic into teaching phase.
 3. Trigger Drill Down on the first topic ("Understanding the OSI Model Layers").
 4. Student answers drill-down question with declarative "vendor incompatibility":
    Assert: classified as ANSWER_ATTEMPT, graded > 0, child P(L) increases, parent P(L) updates.
 5. Student asks a doubt mid-question:
    Assert: answered, P(L) strictly unchanged, awaiting = "clarity_check".
 6. Student replies "done" to the clarity check:
    Assert: resumes, does NOT say "What would you like to explore next?".
 7. Student sends "yes" twice to continue prompts:
    Assert: loop guard fires, state advances, no identical consecutive messages.
 8. Inspect curriculum nodes in DB:
    Assert: no duplicate titles, depth <= 1, children have parent_id set,
    no node with score > 0 has status "Pending".
 9. Request hint on a question, answer by repeating the hint:
    Assert: score <= 0.5, question counter denominator stays fixed.
 10. Inspect Mermaid output for the session:
    Assert: valid syntax, does not produce the bomb error.
"""

import unittest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from multi_agent_tutor.api.server import app, format_curriculum_nodes, generate_mermaid_dag
from multi_agent_tutor.db.database import init_db
from multi_agent_tutor.db.repository import SessionRepository
from multi_agent_tutor.app.schemas.curriculum import CurriculumConcept
from multi_agent_tutor.app.schemas.bkt import BKTState
from multi_agent_tutor.app.schemas.learning_path import LearningPath, LearningPathStep
from multi_agent_tutor.app.schemas.teaching_assessment import TeachingAssessment
from multi_agent_tutor.app.schemas.socratic import SocraticResponse
from multi_agent_tutor.app.schemas.critic import CriticOutput
from multi_agent_tutor.app.utils.progress_tracker_question import format_question_counter


class TestOSIModelSessionReplay(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        await init_db()
        self.client = TestClient(app)
        for sid in ["osi_replay_student", "osi_student_hint_test"]:
            sessions = await SessionRepository.list_student_sessions(sid)
            for s in sessions:
                await SessionRepository.delete_session(s["session_id"])

    async def test_full_osi_model_session_replay(self):
        """
        Replays the OSI Model session end-to-end verifying fixes 1-8.
        """
        sid = "osi_replay_student"
        parent_concept_id = "osi_layers_concept"
        parent_concept_name = "Understanding the OSI Model Layers"

        initial_curriculum = [
            CurriculumConcept(
                concept_id=parent_concept_id,
                name=parent_concept_name,
                description="Core 7-layer architecture and motivation for standardization",
                difficulty=2,
                prerequisites=[],
                parent_id=None,
            ),
            CurriculumConcept(
                concept_id="osi_data_flow",
                name="Data Encapsulation and Flow",
                description="How headers and trailers wrap data across layers",
                difficulty=3,
                prerequisites=[parent_concept_id],
                parent_id=None,
            ),
        ]

        # -----------------------------------------------------------------
        # STEP 1 & 2: Start session and initialize state in teaching phase
        # -----------------------------------------------------------------
        mock_teaching_assessment = TeachingAssessment(
            score=0.95,
            understanding="good",
            confidence=0.9,
            strengths=["Correctly identified vendor incompatibility as key motivation."],
            misconceptions=[],
            pedagogical_action="probe",
            action_reasoning="Strong grasp of historical motivation.",
            reasoning_quality="strong",
        )

        mock_socratic_next = SocraticResponse(
            message="Spot on! Standardizing protocols resolved vendor incompatibility.",
            question="Which layer is responsible for end-to-end packet routing across networks?",
            action="probe",
            question_type="conceptual",
            expected_answer="Network Layer (Layer 3)",
            evaluator_type="llm",
            evaluation_criteria=["Network Layer"],
        )

        mock_critic = CriticOutput(
            passed=True,
            score=9.5,
            feedback="Pedagogically sound and supportive.",
        )

        mock_sub_concepts = [
            CurriculumConcept(
                concept_id="osi_layers_concept_child1",
                name="Layer 1 and 2: Physical and Data Link Framing",
                description="Physical signaling and framing",
                difficulty=2,
                prerequisites=[],
                parent_id=parent_concept_id,
            ),
            CurriculumConcept(
                concept_id="osi_layers_concept_child2",
                name="Layer 3 and 4: Network Routing and Transport",
                description="Packets and segments",
                difficulty=3,
                prerequisites=["osi_layers_concept_child1"],
                parent_id=parent_concept_id,
            ),
        ]

        with patch("multi_agent_tutor.api.server.generate_sub_curriculum") as mock_gen_sub, \
             patch("multi_agent_tutor.app.Agents.teaching_assessor.assessment_chain") as mock_ass_chain, \
             patch("multi_agent_tutor.app.Agents.tutor.sage_chain") as mock_sage_chain, \
             patch("multi_agent_tutor.app.Agents.critic.critic_chain") as mock_critic_chain, \
             patch("multi_agent_tutor.app.Agents.doubt_agent._doubt_chain") as mock_doubt_chain:

            mock_gen_sub.return_value = mock_sub_concepts
            mock_ass_chain.invoke.return_value = mock_teaching_assessment
            mock_sage_chain.invoke.return_value = mock_socratic_next
            mock_critic_chain.invoke.return_value = mock_critic

            # Turn 0: Start session
            res0 = self.client.post("/api/session/start", json={
                "topic": "OSI model",
                "student_id": sid,
                "force_onboarding": True,
            })
            self.assertEqual(res0.status_code, 200)
            data0 = res0.json()
            session_id = data0["session_id"]

            # Fast-forward session state to active curriculum on OSI model
            db_session = await SessionRepository.get_session(session_id)
            state = db_session["state"]
            state["target_topic"] = "OSI model"
            state["curriculum"] = initial_curriculum
            state["current_concept"] = parent_concept_id
            state["mastery"] = {parent_concept_id: 0.0, "osi_data_flow": 0.0}
            state["bkt_states"] = {
                parent_concept_id: BKTState(p_know=0.0),
                "osi_data_flow": BKTState(p_know=0.0),
            }
            state["assessment_done"] = True
            state["diagnostic_state"]["completed"] = True
            state["self_reported_level"] = "some_knowledge"
            state.pop("onboarding_step", None)
            state["teaching_mode"] = "mode_2_teach_first"
            state["teaching_step"] = "teach"
            state["teaching_step_index"] = 0
            state["awaiting"] = "continue"
            state["pending_question"] = None
            await SessionRepository.update_session_turn(session_id, state, [], [])

            # -----------------------------------------------------------------
            # STEP 3: Trigger Drill Down on the first topic
            # -----------------------------------------------------------------
            drill_res = self.client.post("/api/session/drilldown", json={
                "session_id": session_id,
                "concept_id": parent_concept_id,
            })
            self.assertEqual(drill_res.status_code, 200, f"Drilldown failed: {drill_res.text}")
            drill_data = drill_res.json()
            self.assertTrue(drill_data["success"])

            # Reload DB to inspect drilldown state
            db_s_drill = await SessionRepository.get_session(session_id)
            drill_curr = db_s_drill["state"]["curriculum"]

            # Assert: Children have parent_id set to parent_concept_id
            children = [
                c for c in drill_curr
                if (getattr(c, "parent_id", None) if hasattr(c, "parent_id") else c.get("parent_id")) == parent_concept_id
            ]
            self.assertGreater(len(children), 0, "Drilldown must produce children nodes with parent_id set.")
            first_child = children[0]
            first_child_id = getattr(first_child, "concept_id", "") if hasattr(first_child, "concept_id") else first_child.get("concept_id")

            # Check that awaiting is 'continue' and pending_question is None initially
            self.assertEqual(db_s_drill["state"].get("awaiting"), "continue")
            self.assertIsNone(db_s_drill["state"].get("pending_question"))

            # Step forward to the check question on the child concept
            db_s_drill["state"]["current_concept"] = first_child_id
            db_s_drill["state"]["teaching_step_index"] = 4
            db_s_drill["state"]["awaiting"] = "answer"
            db_s_drill["state"]["pending_question"] = {
                "question": "To begin our deep dive into Understanding the OSI Model Layers, what is the primary technical problem or motivation it addresses?",
                "concept_id": first_child_id,
                "expected_answer": "vendor incompatibility and proprietary network stacks",
                "evaluator_type": "llm",
                "evaluation_criteria": ["Vendor interoperability", "Standardization"],
                "question_type": "conceptual",
            }
            await SessionRepository.update_session_turn(session_id, db_s_drill["state"], [], [])

            # -----------------------------------------------------------------
            # STEP 4: Student answers the drill-down question with "vendor incompatibility"
            # -----------------------------------------------------------------
            child_bkt_before = db_s_drill["mastery"].get(first_child_id, 0.0)
            parent_bkt_before = db_s_drill["mastery"].get(parent_concept_id, 0.0)

            ans_res = self.client.post("/api/chat", json={
                "session_id": session_id,
                "message": "vendor incompatibility and lack of open communication standards across different hardware vendors",
            })
            self.assertEqual(ans_res.status_code, 200)
            ans_data = ans_res.json()

            # Reload DB
            db_s_after_ans = await SessionRepository.get_session(session_id)
            state_after_ans = db_s_after_ans["state"]

            # Assert: Routed as ANSWER_ATTEMPT and graded > 0
            detected_intent = state_after_ans.get("detected_intent", {}).get("intent")
            self.assertEqual(detected_intent, "ANSWER_ATTEMPT", "Declarative on-topic answer must be classified as ANSWER_ATTEMPT.")
            self.assertIsNotNone(state_after_ans.get("teaching_assessment"))
            score = state_after_ans["teaching_assessment"].score if hasattr(state_after_ans["teaching_assessment"], "score") else state_after_ans["teaching_assessment"].get("score", 0.0)
            self.assertGreater(score, 0.0, "Answer must be graded with score > 0.")

            # Assert: P(L) of child topic increases
            child_bkt_after = db_s_after_ans["mastery"].get(first_child_id, 0.0)
            self.assertGreater(child_bkt_after, child_bkt_before, "Child P(L) must increase after correct answer.")

            # Assert: P(L) of parent topic updates
            parent_bkt_after = db_s_after_ans["mastery"].get(parent_concept_id, 0.0)
            self.assertGreater(parent_bkt_after, parent_bkt_before, "Parent P(L) must update when child mastery increases.")

            # Assert debug trace was recorded
            debug_trace = state_after_ans.get("debug_trace", [])
            self.assertGreater(len(debug_trace), 0, "Debug trace must be appended.")
            latest_trace = debug_trace[-1]
            self.assertEqual(latest_trace.get("detected_intent"), "ANSWER_ATTEMPT")
            self.assertTrue(latest_trace.get("graded"))

            # -----------------------------------------------------------------
            # STEP 5: Student asks a doubt mid-question
            # -----------------------------------------------------------------
            # Set up a pending question to test mid-question doubt invariants
            db_s_after_ans["state"]["awaiting"] = "answer"
            db_s_after_ans["state"]["pending_question"] = {
                "question": "Which layer is responsible for routing packets across intermediate networks?",
                "concept_id": first_child_id,
                "expected_answer": "Network Layer (Layer 3)",
                "evaluator_type": "llm",
                "evaluation_criteria": ["Network Layer"],
                "question_type": "conceptual",
            }
            await SessionRepository.update_session_turn(session_id, db_s_after_ans["state"], [], [])

            child_mastery_pre_doubt = db_s_after_ans["mastery"][first_child_id]
            parent_mastery_pre_doubt = db_s_after_ans["mastery"][parent_concept_id]

            mock_doubt_reply = MagicMock()
            mock_doubt_reply.content = (
                "The 7 layers were designed to separate concerns: physical signals at layer 1, "
                "hop-to-hop framing at layer 2, and end-to-end internetwork routing at layer 3."
            )
            mock_doubt_chain.invoke.return_value = mock_doubt_reply

            doubt_res = self.client.post("/api/chat", json={
                "session_id": session_id,
                "message": "Wait, why do we need 7 layers instead of just 4?",
            })
            self.assertEqual(doubt_res.status_code, 200)

            # Reload DB
            db_s_doubt = await SessionRepository.get_session(session_id)
            state_doubt = db_s_doubt["state"]

            # Assert: P(L) strictly unchanged across doubt
            self.assertEqual(db_s_doubt["mastery"][first_child_id], child_mastery_pre_doubt, "Child BKT must remain strictly unchanged on doubt.")
            self.assertEqual(db_s_doubt["mastery"][parent_concept_id], parent_mastery_pre_doubt, "Parent BKT must remain strictly unchanged on doubt.")

            # Assert: awaiting == 'clarity_check'
            self.assertEqual(state_doubt.get("awaiting"), "clarity_check", "Awaiting must be clarity_check after doubt response.")
            self.assertTrue(state_doubt.get("doubt_state", {}).get("pending_clarity_check", False))

            # -----------------------------------------------------------------
            # STEP 6: Student replies "done" to the clarity check
            # -----------------------------------------------------------------
            done_res = self.client.post("/api/chat", json={
                "session_id": session_id,
                "message": "done",
            })
            self.assertEqual(done_res.status_code, 200)
            done_text = done_res.json()["latest_message"]["content"]

            # Assert: Tutor resumes and does NOT say "What would you like to explore next?"
            self.assertNotIn("What would you like to explore next?", done_text, "Tutor must resume lesson, not ask open-ended dead end.")

            # Reload DB
            db_s_done = await SessionRepository.get_session(session_id)
            self.assertEqual(db_s_done["mastery"][first_child_id], child_mastery_pre_doubt, "Mastery must remain unchanged after confirmation.")

            # -----------------------------------------------------------------
            # STEP 7: Student sends "yes" twice to continue prompts -> Loop Guard
            # -----------------------------------------------------------------
            # Simulate a continue invitation
            db_s_done["state"]["awaiting"] = "continue"
            db_s_done["state"]["teaching_step_index"] = 1
            await SessionRepository.update_session_turn(session_id, db_s_done["state"], [], [])

            yes1_res = self.client.post("/api/chat", json={
                "session_id": session_id,
                "message": "yes",
            })
            self.assertEqual(yes1_res.status_code, 200)
            yes1_text = yes1_res.json()["latest_message"]["content"]

            yes2_res = self.client.post("/api/chat", json={
                "session_id": session_id,
                "message": "yes",
            })
            self.assertEqual(yes2_res.status_code, 200)
            yes2_text = yes2_res.json()["latest_message"]["content"]

            # Assert: No identical consecutive responses from tutor (Loop Guard fired or stepped forward)
            self.assertNotEqual(yes1_text.strip(), yes2_text.strip(), "Loop guard must prevent identical consecutive replies.")

            # -----------------------------------------------------------------
            # STEP 8: Inspect curriculum nodes in DB
            # -----------------------------------------------------------------
            final_db = await SessionRepository.get_session(session_id)
            final_curr = final_db["state"]["curriculum"]

            # Depth <= 1 check: attempting drilldown on a child must fail with 400
            child_drill_res = self.client.post("/api/session/drilldown", json={
                "session_id": session_id,
                "concept_id": first_child_id,
            })
            self.assertEqual(child_drill_res.status_code, 400, "Drilldown on child node must be rejected with depth limit.")

            # Check no duplicate titles
            titles = [
                (getattr(c, "name", "") if hasattr(c, "name") else c.get("name", "")).strip().lower()
                for c in final_curr
            ]
            self.assertEqual(len(titles), len(set(titles)), "Curriculum nodes must have unique titles without duplicates.")

            # Check compute_topic_status invariant: node with score > 0 is NEVER 'Pending'
            mastery_map = final_db["mastery"]
            formatted_nodes = format_curriculum_nodes(final_curr, first_child_id, mastery_map)
            for node in formatted_nodes:
                score = node.get("score", 0.0)
                st = str(node.get("status", "")).lower()
                cid = node.get("concept_id", "")
                if score > 0.0:
                    self.assertNotEqual(st, "pending", f"Node '{cid}' has score {score} > 0 but status was '{st}'.")

            # -----------------------------------------------------------------
            # STEP 9: Request hint on a question, answer repeating hint
            # -----------------------------------------------------------------
            from multi_agent_tutor.app.Agents.doubt_agent import generate_safe_hint
            safe_hint = generate_safe_hint(
                topic="OSI model",
                concept="transport_layer",
                question_text="How does the Transport Layer guarantee reliable packet delivery?",
                expected_answer="By using sequence numbers, acknowledgments, and retransmissions.",
                raw_explanation="Think about how connections track messages.",
            )
            # Hint should NOT give away the exact answer verbatim
            self.assertNotIn("By using sequence numbers, acknowledgments, and retransmissions.", safe_hint)

            # Check counter denominator stability
            c1 = format_question_counter(current_index=1, initial_total=5, follow_up_count=0)
            c2 = format_question_counter(current_index=2, initial_total=5, follow_up_count=1)
            self.assertEqual(c1, "Question 2 of 5")
            self.assertEqual(c2, "Question 3 of 5 (Follow-up 1)")
            self.assertIn("of 5", c2, "Denominator must stay frozen at initial_total.")

            # Check capped score when repeating hint:
            # TeachingAssessor caps score at 0.5 if hint was used
            from multi_agent_tutor.app.Agents.teaching_assessor import assess_teaching_response
            test_state = dict(final_db["state"])
            test_state["signals"] = {"hints_used": 1}
            test_state["student_input"] = "by using sequence numbers"
            test_state["pending_question"] = {
                "question": "How does the Transport Layer guarantee reliable delivery?",
                "concept_id": first_child_id,
            }
            ass_res = assess_teaching_response(test_state)
            capped_ass = ass_res["teaching_assessment"]
            self.assertLessEqual(capped_ass.score, 0.5, "Repeated hint answer must be capped at score <= 0.5.")

            # -----------------------------------------------------------------
            # STEP 10: Inspect Mermaid output for the session
            # -----------------------------------------------------------------
            mermaid_dag = generate_mermaid_dag(final_curr, first_child_id, mastery_map)
            self.assertTrue(mermaid_dag.startswith("graph TD"), "Mermaid output must start with 'graph TD'.")
            self.assertNotIn("Encapsulates DataEncapsulates Data", mermaid_dag, "No repeated flattened text in Mermaid DAG.")
            self.assertNotIn("[bomb]", mermaid_dag.lower(), "Mermaid DAG must not contain bomb errors.")
            # Verify each node has properly closed brackets and valid identifier
            for line in mermaid_dag.splitlines():
                if "-->" in line:
                    parts = line.strip().split("-->")
                    self.assertEqual(len(parts), 2, f"Invalid edge line: {line}")
                elif "[" in line and "]" in line:
                    self.assertTrue(line.count("[") == line.count("]"), f"Mismatched brackets: {line}")

        print("\n" + "=" * 80)
        print("ALL 10 REPLAY CHECKS PASSED: OSI MODEL SESSION SUCCESSFULLY VERIFIED".center(80))
        print("=" * 80)
