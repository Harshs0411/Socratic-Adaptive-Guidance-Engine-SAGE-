"""
Phase 2 Deterministic Verification Test Suite:
1. Intent Classifier Evaluation across 10 diverse representative student messages.
2. End-to-End State Verification:
   - A doubt mid-question leaves BKT mastery 100% UNCHANGED.
   - Checkpoint is pushed to the doubt stack and clarity check is verified.
   - Confirmation pops checkpoint and resumes with bridge restating the pending question.
   - Subsequent answer attempt updates BKT mastery.
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Add project root to sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from multi_agent_tutor.app.schemas.bkt import BKTState
from multi_agent_tutor.app.schemas.intent import IntentClassification
from multi_agent_tutor.app.schemas.socratic import SocraticResponse
from multi_agent_tutor.app.schemas.teaching_assessment import TeachingAssessment
from multi_agent_tutor.app.Agents.intent_classifier import classify_student_intent
from multi_agent_tutor.app.graph.workflow import master_graph


class TestPhase2IntentAndDoubt(unittest.TestCase):

    def test_01_ten_example_intent_messages(self):
        """
        Evaluates the Intent Classifier on 10 diverse student messages.
        Outputs a clean formatted table for review.
        """
        pending_q = {
            "question": "What is the worst-case time complexity of Binary Search on a sorted array of size n?",
            "concept_id": "binary_search",
        }

        test_cases = [
            ("Why does the array need to be sorted first?", "DOUBT", "Inquires about prerequisite concept"),
            ("O(log n) because we halve the array each step", "ANSWER_ATTEMPT", "Direct answer to the pending question"),
            ("I don't know", "DOUBT", "Help request / don't know: never penalized"),
            ("can you explain it differently?", "META", "Requests pedagogical explanation style switch"),
            ("makes sense, got it", "CONFIRMATION", "Affirmative acknowledgment of clarity"),
            ("hello SAGE, how are you today?", "CHITCHAT", "Social greeting / pleasantry"),
            ("I think it's O(log n), but why doesn't linear search work here?", "DOUBT", "Mixed message: attempt + embedded doubt"),
            ("slow down, you're going too fast", "META", "Metacognitive pacing adjustment"),
            ("what does the 'low <= high' condition mean?", "DOUBT", "Conceptual inquiry about algorithm invariants"),
            ("give me an example of this with real numbers", "META", "Requests worked concrete example"),
        ]

        print("\n" + "=" * 95)
        print("TABLE OF 10 INTENT CLASSIFICATION TEST EXAMPLES".center(95))
        print("=" * 95)
        print(f"{'#':<3} | {'Student Message':<45} | {'Expected':<15} | {'Detected':<15} | {'Match'}")
        print("-" * 95)

        for idx, (msg, expected_intent, notes) in enumerate(test_cases, 1):
            # Mock LLM fallback if needed, but rule pre-filter handles common cases
            classification = classify_student_intent(
                message=msg,
                pending_question=pending_q,
                current_topic="Binary Search",
                pending_clarity_check=(msg == "makes sense, got it"),
            )
            detected = classification.intent
            match = "✅ PASS" if detected == expected_intent else f"❌ FAIL ({detected})"
            print(f"{idx:<3} | {msg[:45]:<45} | {expected_intent:<15} | {detected:<15} | {match}")
            self.assertEqual(detected, expected_intent, f"Failed for message: '{msg}'")

        print("=" * 95)

    def test_02_no_pending_question_cannot_be_answer_attempt(self):
        """
        Strict Invariant: If there is no pending question, a message can NEVER be classified as ANSWER_ATTEMPT.
        """
        classification = classify_student_intent(
            message="O(log n)",
            pending_question=None,  # No pending question!
            current_topic="Binary Search",
        )
        self.assertNotEqual(classification.intent, "ANSWER_ATTEMPT")
        self.assertIn(classification.intent, ["DOUBT", "CHITCHAT", "META"])

    @patch("multi_agent_tutor.app.Agents.tutor.retrieve_pedagogical_context")
    @patch("multi_agent_tutor.app.Agents.critic.critic_chain")
    @patch("multi_agent_tutor.app.Agents.tutor.sage_chain")
    @patch("multi_agent_tutor.app.Agents.teaching_assessor.assessment_chain")
    @patch("multi_agent_tutor.app.Agents.doubt_agent._doubt_chain")
    def test_03_doubt_mid_question_preserves_bkt_and_resumes(self, mock_doubt_chain, mock_teach_chain, mock_sage_chain, mock_critic_chain, mock_rag):
        """
        Comprehensive End-to-End Simulation:
        1. Student is asked: 'What is the time complexity of Binary Search?'
        2. Current BKT mastery is exactly 0.35.
        3. Student asks a doubt: 'Why do we divide the search space in half?'
           -> Verify BKT mastery is 100% UNCHANGED (still 0.35).
           -> Verify doubt stack has 1 checkpoint.
           -> Verify clarity check is asked.
        4. Student confirms: 'yes, that makes sense!'
           -> Verify BKT mastery is STILL 100% UNCHANGED (still 0.35).
           -> Verify checkpoint is popped.
           -> Verify pending question is restated with bridge.
        5. Student answers: 'O(log n)'
           -> Verify BKT updates from 0.35 to > 0.35.
        """
        mock_doubt_chain.invoke.return_value = MagicMock(content="Dividing in half eliminates 50% of remaining items in 1 comparison.")
        mock_teach_chain.invoke.return_value = TeachingAssessment(
            understanding="mastered",
            score=0.95,
            confidence=0.95,
            reasoning_quality="strong",
            misconceptions=[],
        )
        mock_sage_chain.invoke.return_value = SocraticResponse(
            message="Great job! Now let's explore how binary search handles edge cases.",
            question="What happens if the array has only 1 element?",
            action="probe",
            question_type="conceptual",
            expected_answer="Checks if that 1 element equals target.",
            evaluator_type="llm",
            evaluation_criteria=["Single element boundary check."],
        )
        mock_critic_chain.invoke.return_value = MagicMock(passed=True, score=10, feedback="Passed")
        mock_rag.return_value = {"context_text": "Binary search reference text", "citations": []}

        initial_state = {
            "student_id": "test_student",
            "target_topic": "Binary Search",
            "messages": [],
            "student_input": None,
            "curriculum": [
                MagicMock(concept_id="binary_search", name="Binary Search", prerequisites=[], difficulty=2)
            ],
            "diagnostic_state": {
                "completed": True,
                "questions": [],
                "current_question_id": None,
                "answers": {},
                "assessments": {},
            },
            "learner_profile": None,
            "mastery": {"binary_search": 0.35},
            "bkt_states": {
                "binary_search": BKTState(p_know=0.35, p_learn=0.15, p_guess=0.20, p_slip=0.10)
            },
            "learning_path": MagicMock(completed=False),
            "current_concept": "binary_search",
            "teaching": {
                "current_action": "probe",
                "current_question": "What is the time complexity of Binary Search?",
                "attempt_count": 0,
                "misconception_history": [],
                "current_objective": "Time complexity",
                "concept_completed": False,
            },
            "teaching_assessment": None,
            "teaching_decision": None,
            "socratic_response": SocraticResponse(
                message="What is the time complexity of Binary Search?",
                question="What is the time complexity of Binary Search?",
                action="probe",
                question_type="conceptual",
                expected_answer="O(log n)",
                evaluator_type="llm",
                evaluation_criteria=["Mentions O(log n)"],
            ),
            "tutor_response": "What is the time complexity of Binary Search?",
            "critic_result": None,
            "retry_count": 0,
            "misconceptions": [],
            "hint_level": 0,
            "rag_context": None,
            "depth_level": "deep",
            "assessment_done": True,
            "self_reported_level": "some_knowledge",
            "teaching_mode": "mode_1_qa",
            "teaching_step": "check",
            "pending_question": {
                "question": "What is the time complexity of Binary Search?",
                "concept_id": "binary_search",
                "expected_answer": "O(log n)",
                "evaluator_type": "llm",
                "evaluation_criteria": ["Mentions O(log n)"],
                "question_type": "conceptual",
            },
            "current_subtopic": None,
            "subtopic_mastery": {},
            "detected_intent": None,
            "doubt_state": {
                "doubt_stack": [],
                "doubt_log": [],
                "pending_clarity_check": False,
                "clarity_doubt_id": None,
                "active_doubt_response": None,
            },
            "misconceptions_log": [],
            "signals": {"hints_used": 0, "attempts": 0, "response_time": 0.0, "stated_confidence": None},
            "last_practice_time": None,
            "study_plan": None,
        }

        # -------------------------------------------------------------
        # TURN 1: Student interrupts with a DOUBT
        # -------------------------------------------------------------
        state = dict(initial_state)
        state["student_input"] = "Why do we divide the search space in half?"
        state_after_doubt = master_graph.invoke(state)

        # 1. BKT Mastery must be STRICTLY UNCHANGED
        bkt_val_turn1 = state_after_doubt["mastery"]["binary_search"]
        self.assertEqual(
            bkt_val_turn1, 0.35,
            f"VIOLATION: BKT mastery changed on a doubt! Expected 0.35, got {bkt_val_turn1}"
        )
        self.assertEqual(state_after_doubt["bkt_states"]["binary_search"].p_know, 0.35)

        # 2. Doubt checkpoint must be saved on stack
        doubt_stack = state_after_doubt["doubt_state"]["doubt_stack"]
        self.assertEqual(len(doubt_stack), 1)
        self.assertEqual(doubt_stack[0]["topic"], "Binary Search")
        self.assertEqual(doubt_stack[0]["doubt_text"], "Why do we divide the search space in half?")
        self.assertTrue(state_after_doubt["doubt_state"]["pending_clarity_check"])

        # 3. Tutor response must include clarity check
        tutor_resp = state_after_doubt["tutor_response"]
        self.assertIn("Does that make sense, or should I explain it another way?", tutor_resp)
        print("\n✅ TURN 1 PASSED: Doubt answered. BKT unchanged at 0.35. Checkpoint saved.")

        # -------------------------------------------------------------
        # TURN 2: Student confirms clarity
        # -------------------------------------------------------------
        state_after_doubt["student_input"] = "yes, that makes sense!"
        state_after_confirm = master_graph.invoke(state_after_doubt)

        # 1. BKT Mastery must STILL be STRICTLY UNCHANGED
        bkt_val_turn2 = state_after_confirm["mastery"]["binary_search"]
        self.assertEqual(
            bkt_val_turn2, 0.35,
            f"VIOLATION: BKT mastery changed on confirmation! Expected 0.35, got {bkt_val_turn2}"
        )
        self.assertEqual(state_after_confirm["bkt_states"]["binary_search"].p_know, 0.35)

        # 2. Checkpoint must be popped
        self.assertEqual(len(state_after_confirm["doubt_state"]["doubt_stack"]), 0)
        self.assertFalse(state_after_confirm["doubt_state"]["pending_clarity_check"])

        # 3. Tutor response must bridge and restate pending question
        confirm_resp = state_after_confirm["tutor_response"]
        self.assertIn("Awesome, glad that's clear! Let's get right back to where we were:", confirm_resp)
        self.assertIn("What is the time complexity of Binary Search?", confirm_resp)
        print("✅ TURN 2 PASSED: Confirmation acknowledged. BKT unchanged at 0.35. Checkpoint popped. Question resumed.")

        # -------------------------------------------------------------
        # TURN 3: Student answers the resumed question
        # -------------------------------------------------------------
        state_after_confirm["student_input"] = "O(log n) because the search space cuts in half every time"
        state_after_answer = master_graph.invoke(state_after_confirm)

        # 1. Intent should be ANSWER_ATTEMPT
        self.assertEqual(state_after_answer["detected_intent"]["intent"], "ANSWER_ATTEMPT")

        # 2. NOW BKT Mastery must update and grow!
        bkt_val_turn3 = state_after_answer["mastery"]["binary_search"]
        self.assertGreater(
            bkt_val_turn3, 0.35,
            f"VIOLATION: BKT did not grow after correct answer! Got {bkt_val_turn3}"
        )
        print(f"✅ TURN 3 PASSED: Graded answer attempt updated BKT mastery from 0.35 -> {bkt_val_turn3:.4f}.")


if __name__ == "__main__":
    unittest.main()
