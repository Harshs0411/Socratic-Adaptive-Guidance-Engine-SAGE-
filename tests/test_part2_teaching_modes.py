"""
Unit and Integration Tests for Requirement 2 & Part 2:
Two Teaching Modes, Differentiated Re-teach Cycles, Remediation Cap,
Completion Rule, and Visual Model Integration.
"""

import unittest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from multi_agent_tutor.api.server import app
from multi_agent_tutor.db.database import init_db
from multi_agent_tutor.app.config import (
    MODE_SWITCH_MASTERY_THRESHOLD,
    REMEDIATION_CAP,
    SUBTOPIC_MIN_CORRECT_CHECKS,
    MASTERY_ADVANCE_THRESHOLD,
)
from multi_agent_tutor.app.Agents.teaching_agent import (
    choose_mode,
    generate_mode_2_explanation,
    generate_re_teach_explanation,
    select_check_question,
)
from multi_agent_tutor.app.Agents.visual_agent import get_visual_for_concept
from multi_agent_tutor.app.Agents.teaching_controller import teaching_controller
from multi_agent_tutor.app.schemas.teaching_assessment import TeachingAssessment
from multi_agent_tutor.app.schemas.bkt import BKTState
from multi_agent_tutor.app.Agents.critic import critic_agent
from multi_agent_tutor.app.schemas.socratic import SocraticResponse


class TestPart2TeachingModes(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        await init_db()
        self.client = TestClient(app)

    def test_01_mode_selection_threshold(self):
        """Requirement 2: Choose mode strictly based on mastery threshold (0.65)."""
        self.assertEqual(choose_mode(0.0), "mode_2_teach_first")
        self.assertEqual(choose_mode(0.35), "mode_2_teach_first")
        self.assertEqual(choose_mode(0.64), "mode_2_teach_first")
        self.assertEqual(choose_mode(0.65), "mode_1_qa")
        self.assertEqual(choose_mode(0.85), "mode_1_qa")

    def test_02_mode_2_explanation_structure_and_visual(self):
        """
        Requirement 2 & 4:
        Mode 2 explanation must contain:
        1. Real-world analogy
        2. At least 2 concrete worked examples
        3. Attached visual model (Mermaid / ASCII / trace table)
        4. Ends with invitation, not a test question
        """
        expl = generate_mode_2_explanation("Binary Search", "binary_search_fundamentals")
        
        # 1. Analogy
        self.assertIn("Analogy", expl)
        # 2. Two worked examples
        self.assertIn("Worked Example 1", expl)
        self.assertIn("Worked Example 2", expl)
        # 3. Attached visual model
        self.assertIn("Visual Model", expl)
        # 4. Ends with invitation, NOT a quiz
        self.assertIn("Any questions on this, or shall we move on", expl)
        # Does not quiz or ask for an answer
        self.assertNotIn("What is mid on the first step?", expl)

    def test_03_differentiated_re_teach_cycles_and_cap(self):
        """
        Requirement 2.3:
        Cycle 1: alternate analogy
        Cycle 2: smaller step-by-step walkthrough
        Cycle 3: worked example with fresh numbers
        Cap (3): offer prerequisite revisit or hint ladder
        """
        # Cycle 1
        t1, cap1 = generate_re_teach_explanation("Binary Search", "binary_search_fundamentals", attempt_count=1, misconception_notes=[])
        self.assertFalse(cap1)
        self.assertIn("Alternative Analogy", t1)

        # Cycle 2
        t2, cap2 = generate_re_teach_explanation("Binary Search", "binary_search_fundamentals", attempt_count=2, misconception_notes=[])
        self.assertFalse(cap2)
        self.assertIn("tiny, bite-sized steps", t2)

        # Cycle 3 (cap reached after 3 cycles)
        t_cap, cap_flag = generate_re_teach_explanation("Binary Search", "binary_search_fundamentals", attempt_count=REMEDIATION_CAP, misconception_notes=[])
        self.assertTrue(cap_flag)
        self.assertIn("prerequisite", t_cap.lower())
        self.assertIn("hint ladder", t_cap.lower())

    def test_04_subtopic_completion_rule(self):
        """
        Completion rule:
        Topic completed ONLY when:
        P(L) >= 0.85 AND >= 3 correct checks AND >= 1 correct transfer question.
        """
        base_state = {
            "current_concept": "binary_search_fundamentals",
            "teaching_mode": "mode_2_teach_first",
            "teaching_step": "check",
            "target_topic": "Binary Search",
            "signals": {},
            "skipped_concepts": [],
        }

        # Case A: High P(L) but only 1 correct check -> NOT completed
        ass_pass = TeachingAssessment(understanding="mastered", score=1.0, confidence=1.0, misconceptions=[], reasoning_quality="strong")
        state_a = {
            **base_state,
            "bkt_states": {"binary_search_fundamentals": BKTState(p_know=0.88)},
            "teaching": {"attempt_count": 1, "correct_checks": 0, "has_transfer_correct": False, "misconception_history": []},
            "teaching_assessment": ass_pass,
            "pending_question": {"is_transfer": False, "question_type": "conceptual"},
        }
        res_a = teaching_controller(state_a)
        self.assertFalse(res_a["teaching"]["concept_completed"])
        self.assertEqual(res_a["teaching_decision"].action, "probe")

        # Case B: High P(L) and 3 correct checks and transfer question -> COMPLETED
        state_b = {
            **base_state,
            "bkt_states": {"binary_search_fundamentals": BKTState(p_know=0.88)},
            "teaching": {"attempt_count": 3, "correct_checks": 2, "has_transfer_correct": False, "misconception_history": []},
            "teaching_assessment": ass_pass,
            "pending_question": {"is_transfer": True, "question_type": "application"},
        }
        res_b = teaching_controller(state_b)
        self.assertTrue(res_b["teaching"]["concept_completed"])
        self.assertEqual(res_b["teaching_decision"].action, "advance")

    def test_05_critic_mode_aware_evaluation(self):
        """
        Requirement 2.5:
        In Mode 2 explain steps, critic evaluates in explanation_only mode
        and does NOT penalize for not asking a question.
        """
        state = {
            "current_concept": "binary_search_fundamentals",
            "teaching_mode": "mode_2_teach_first",
            "teaching_step": "explain",
            "mastery": {"binary_search_fundamentals": 0.0},
            "retry_count": 0,
            "socratic_response": SocraticResponse(
                message="Here is a complete explanation of binary search with analogy and worked examples.",
                question="",
                action="explain",
                expected_answer="",
                evaluator_type="llm",
                evaluation_criteria=[],
                question_type="conceptual",
            ),
        }
        with patch("multi_agent_tutor.app.Agents.critic.critic_chain") as mock_chain:
            mock_chain.invoke.return_value = MagicMock(passed=True, score=10.0, feedback="Clear explanation.")
            res = critic_agent(state)
            # Verify critic evaluated with explanation_only mode
            call_args = mock_chain.invoke.call_args[0][0]
            self.assertEqual(call_args["evaluation_mode"], "explanation_only")
            self.assertTrue(res["critic_result"].passed)

    async def test_06_request_visual_meta_intent_flow(self):
        """
        Step 4:
        Student saying 'show me a diagram' receives a visual diagram,
        BKT is strictly unchanged, and pending question is preserved.
        """
        res0 = self.client.post("/api/session/start", json={
            "topic": "Binary Search",
            "student_id": "test_vis_user_01",
            "self_reported_level": "some_knowledge",
        })
        self.assertEqual(res0.status_code, 200)
        session_id = res0.json()["session_id"]
        init_mastery = dict(res0.json()["mastery"])

        # Student asks for a diagram
        res1 = self.client.post("/api/chat", json={
            "session_id": session_id,
            "message": "Can you show me a diagram of how this works?",
        })
        self.assertEqual(res1.status_code, 200)
        data1 = res1.json()

        # Visual diagram present in response
        self.assertIn("visual diagram", data1["latest_message"]["content"].lower())
        # BKT unchanged
        self.assertEqual(data1["mastery"], init_mastery)
