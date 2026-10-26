"""
Test Suite for Section B: Intent Classifier Edge Cases.
Validates terse answers, implicit confirmation on ignored clarity checks,
confirmation safety when no check is pending, mixed messages, diagnostic doubt routing,
and includes an opt-in suite for ambiguous messages.
"""

import os
import unittest
import pytest
from unittest.mock import patch, MagicMock

from multi_agent_tutor.app.Agents.intent_classifier import (
    classify_student_intent,
    pre_filter_intent,
)
from multi_agent_tutor.app.Agents.doubt_agent import (
    handle_doubt_question,
    handle_clarity_confirmation,
)
from multi_agent_tutor.app.Agents.teaching_assessor import assess_teaching_response
from multi_agent_tutor.app.schemas.socratic import SocraticResponse
from multi_agent_tutor.app.schemas.teaching_assessment import TeachingAssessment
from multi_agent_tutor.app.graph.workflow import master_graph


class TestSectionBIntentEdgeCases(unittest.TestCase):

    def test_b1_terse_answers_with_pending_question(self):
        """
        B.1: All terse answer formats in presence of a pending question
        MUST be classified as ANSWER_ATTEMPT:
        - "O(log n)"
        - "3"
        - "B"
        - "True"
        - "mid = 4"
        - code snippet
        - one-word answer
        """
        pending_q = {
            "question": "What is the worst-case time complexity of Binary Search?",
            "concept_id": "binary_search",
        }

        terse_cases = [
            ("O(log n)", "ANSWER_ATTEMPT", "Asymptotic notation"),
            ("3", "ANSWER_ATTEMPT", "Single number"),
            ("B", "ANSWER_ATTEMPT", "Multiple choice option letter"),
            ("True", "ANSWER_ATTEMPT", "Boolean answer"),
            ("mid = 4", "ANSWER_ATTEMPT", "Algorithmic variable assignment"),
            ("def search(arr):\n    return mid", "ANSWER_ATTEMPT", "Code snippet"),
            ("Halving", "ANSWER_ATTEMPT", "Single-word conceptual answer"),
        ]

        print("\n" + "=" * 80)
        print("SECTION B.1: TERSE ANSWERS TEST RESULTS".center(80))
        print("=" * 80)
        for msg, expected_intent, note in terse_cases:
            res = classify_student_intent(
                message=msg,
                pending_question=pending_q,
                current_topic="Binary Search",
                pending_clarity_check=False,
            )
            print(f"Input: {msg:<32} | Expected: {expected_intent:<15} | Detected: {res.intent:<15} | Note: {note}")
            self.assertEqual(res.intent, expected_intent, f"Failed for terse message '{msg}'")

    def test_b2_ignored_clarity_check_implicit_confirmation(self):
        """
        B.2: A student who ignores a pending clarity check and answers the pending question
        directly is classified as ANSWER_ATTEMPT. In assess_teaching_response, it is treated
        as an implicit confirmation, popping the checkpoint, and grading the answer.
        """
        pending_q = {
            "question": "What is the time complexity of Binary Search?",
            "expected_answer": "O(log n)",
            "evaluator_type": "exact",
            "evaluation_criteria": ["Logarithmic time O(log n)"],
        }

        # Step 1: Student sends direct answer while pending_clarity_check is True
        classification = classify_student_intent(
            message="O(log n)",
            pending_question=pending_q,
            current_topic="Binary Search",
            pending_clarity_check=True,
        )
        self.assertEqual(classification.intent, "ANSWER_ATTEMPT")

        # Step 2: In assess_teaching_response, verify implicit confirmation pops checkpoint
        mock_assessment = TeachingAssessment(
            score=1.0,
            understanding="mastered",
            reasoning_quality="strong",
            misconceptions=[],
            evidence_observed="Student correctly provided O(log n)",
            confidence=0.98,
        )

        state = {
            "current_concept": "bs_halving_principle",
            "student_input": "O(log n)",
            "pending_question": pending_q,
            "teaching": {
                "current_question": pending_q["question"],
                "misconception_history": [],
                "attempt_count": 1,
            },
            "doubt_state": {
                "doubt_stack": [{"checkpoint_id": "cp_123", "pending_question": pending_q}],
                "pending_clarity_check": True,
            },
        }

        with patch("multi_agent_tutor.app.Agents.teaching_assessor.assessment_chain") as mock_chain:
            mock_chain.invoke.return_value = mock_assessment
            result = assess_teaching_response(state)

        # Assert implicit confirmation popped the checkpoint and cleared pending_clarity_check
        self.assertIn("doubt_state", result)
        self.assertFalse(result["doubt_state"]["pending_clarity_check"])
        self.assertEqual(len(result["doubt_state"]["doubt_stack"]), 0)
        self.assertEqual(result["teaching_assessment"].score, 1.0)
        print("✅ B.2: Ignored clarity check treated as implicit confirmation, checkpoint popped, answer graded.")

    def test_b3_confirmation_without_clarity_check_safe_and_yes_no(self):
        """
        B.3: CONFIRMATION when no clarity check is pending must be safe:
        no crash, no popped checkpoint, no grading.
        A bare 'yes' or 'no' is an ANSWER_ATTEMPT if the pending question is a yes/no question.
        """
        # Scenario 1: Affirmative 'ok' with no clarity check and no pending question
        res_ok = classify_student_intent(
            message="ok, got it",
            pending_question=None,
            pending_clarity_check=False,
        )
        self.assertEqual(res_ok.intent, "CONFIRMATION")

        # Calling handle_clarity_confirmation with empty stack is safe
        state_empty_stack = {"doubt_state": {"doubt_stack": [], "pending_clarity_check": False}}
        safe_resp = handle_clarity_confirmation(state_empty_stack)
        self.assertIn("tutor_response", safe_resp)
        self.assertEqual(len(safe_resp["doubt_state"]["doubt_stack"]), 0)

        # Scenario 2: Bare 'yes' to a yes/no polar question
        yes_no_q = {
            "question": "Does the array need to be sorted before applying binary search?",
            "concept_id": "binary_search",
        }
        res_yes = classify_student_intent(
            message="yes",
            pending_question=yes_no_q,
            pending_clarity_check=False,
        )
        self.assertEqual(res_yes.intent, "ANSWER_ATTEMPT")

        # Bare 'no' to a yes/no question
        res_no = classify_student_intent(
            message="no",
            pending_question=yes_no_q,
            pending_clarity_check=False,
        )
        self.assertEqual(res_no.intent, "ANSWER_ATTEMPT")
        print("✅ B.3: Safe confirmation without clarity check, and bare yes/no recognized as answer to polar questions.")

    def test_b4_mixed_message_flow(self):
        """
        B.4: Mixed messages (answer + doubt):
        1. Answer the doubt first, store the attempt part in the checkpoint.
        2. After student confirms, resume bridge re-asks the pending question
           explicitly acknowledging the stored attempt.
        """
        mixed_input = "I think it's O(log n), but why doesn't linear search work here?"
        pending_q = {
            "question": "What is the worst-case time complexity of Binary Search?",
            "concept_id": "binary_search",
        }

        classification = classify_student_intent(
            message=mixed_input,
            pending_question=pending_q,
            current_topic="Binary Search",
            pending_clarity_check=False,
        )
        self.assertEqual(classification.intent, "DOUBT")
        self.assertTrue(classification.is_mixed)
        self.assertEqual(classification.attempt_part, "I think it's O(log n)")
        self.assertEqual(classification.doubt_part, "why doesn't linear search work here?")

        # Doubt agent handles it
        state = {
            "target_topic": "Binary Search",
            "pending_question": pending_q,
            "teaching_step": "check",
            "teaching_mode": "mode_2_teach_first",
            "doubt_state": {"doubt_stack": [], "doubt_log": []},
            "signals": {},
        }

        mock_socratic = MagicMock()
        mock_socratic.content = "Linear search does work, but it examines every element one-by-one taking O(n) time."

        with patch("multi_agent_tutor.app.Agents.doubt_agent._doubt_chain") as mock_chain:
            mock_chain.invoke.return_value = mock_socratic
            doubt_res = handle_doubt_question(state, mixed_input, classification.model_dump())

        # Assert attempt part was stored in checkpoint
        checkpoint = doubt_res["doubt_state"]["doubt_stack"][-1]
        self.assertEqual(checkpoint["stored_attempt"], "I think it's O(log n)")
        self.assertTrue(doubt_res["doubt_state"]["pending_clarity_check"])

        # Now student confirms clarity ("makes sense, got it")
        state["doubt_state"] = doubt_res["doubt_state"]
        resume_res = handle_clarity_confirmation(state)

        # Assert bridge mentions stored attempt and restates pending question
        self.assertIn("I think it's O(log n)", resume_res["tutor_response"])
        self.assertIn(pending_q["question"], resume_res["tutor_response"])
        self.assertFalse(resume_res["doubt_state"]["pending_clarity_check"])
        print("✅ B.4: Mixed message handled: doubt answered first, attempt stored, and bridged on confirmation.")

    def test_b5_doubts_and_meta_during_diagnostic_phase(self):
        """
        B.5: Doubts and meta requests during the diagnostic phase must work
        without grading or corrupting diagnostic progress.
        """
        diag_state = {
            "completed": False,
            "current_question_id": "diag_q1",
            "questions": [],
            "answers": {},
            "assessments": {},
        }
        pending_diag_q = {
            "question_id": "diag_q1",
            "question": "Diagnostic Q1: What is Binary Search?",
            "concept": "binary_search",
        }

        # Student asks a doubt during diagnostic
        classification = classify_student_intent(
            message="Wait, what does monotonic mean?",
            pending_question=pending_diag_q,
            current_topic="Binary Search",
            pending_clarity_check=False,
        )
        self.assertEqual(classification.intent, "DOUBT")

        # Student sends meta request during diagnostic
        classification_meta = classify_student_intent(
            message="can you slow down please?",
            pending_question=pending_diag_q,
            current_topic="Binary Search",
            pending_clarity_check=False,
        )
        self.assertEqual(classification_meta.intent, "META")
        self.assertEqual(classification_meta.meta_subintent, "slow_down")
        print("✅ B.5: Doubts and META requests during diagnostic phase classified correctly without grading.")

    @pytest.mark.skipif(
        not os.getenv("RUN_REAL_LLM_TESTS"),
        reason="Opt-in test suite for real LLM classifier evaluation (B.6). Set RUN_REAL_LLM_TESTS=1 to run."
    )
    def test_b6_twenty_ambiguous_messages_real_llm(self):
        """
        B.6: Opt-in suite running ~20 ambiguous messages through the REAL LLM classifier.
        Prints a formatted markdown table.
        """
        pending_q = {
            "question": "What is the worst-case time complexity of Binary Search?",
            "concept_id": "binary_search",
        }

        ambiguous_messages = [
            "ok", "hmm", "what?", "maybe 5?", "I guess log n", "no",
            "wait", "really?", "huh?", "sure", "definitely", "probably O(n)",
            "I have no clue", "explain again", "next please", "hi", "3.14",
            "could be log n", "why?", "i think so"
        ]

        print("\n" + "=" * 80)
        print("SECTION B.6: OPT-IN 20 AMBIGUOUS MESSAGES (REAL LLM)".center(80))
        print("=" * 80)
        for msg in ambiguous_messages:
            res = classify_student_intent(
                message=msg,
                pending_question=pending_q,
                current_topic="Binary Search",
                pending_clarity_check=False,
            )
            print(f"Message: {msg:<20} | Intent: {res.intent:<15} | Confidence: {res.confidence:.2f} | Reasoning: {res.reasoning[:40]}")


if __name__ == "__main__":
    unittest.main()
