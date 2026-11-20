import unittest
from multi_agent_tutor.app.graph.state import TutorState
from multi_agent_tutor.app.schemas.teaching_assessment import TeachingAssessment
from multi_agent_tutor.app.schemas.socratic import SocraticResponse
from multi_agent_tutor.app.Agents.tutor import sage_agent
from multi_agent_tutor.app.Agents.concept_advancer import advance_concept
from multi_agent_tutor.app.schemas.curriculum import CurriculumConcept
from multi_agent_tutor.app.schemas.learning_path import LearningPath


class TestContinuityAndAcknowledgment(unittest.TestCase):

    def test_correct_answer_acknowledged_with_explanation(self):
        """
        Verify that a student's correct answer is explicitly acknowledged with an explanation
        and connected to the next check question.
        """
        state: TutorState = {
            "current_concept": "assembly_line",
            "target_topic": "Industrial Manufacturing",
            "mastery": {"assembly_line": 0.4},
            "teaching_mode": "mode_2_teach_first",
            "teaching_step": "check",
            "pending_question": {
                "question_id": "assembly_line_q1",
                "question": "How did assembly-line production affect car prices?",
                "expected_answer": "Mass production reduced labor time and per-unit production costs, making cars affordable.",
                "concept_id": "assembly_line",
            },
            "student_input": "Mass production made cars more affordable.",
            "teaching_assessment": TeachingAssessment(
                understanding="mastered",
                score=1.0,
                confidence=1.0,
                misconceptions=[],
                reasoning_quality="strong",
                feedback="Spot-on! Mass production on the moving line drastically reduced per-unit labor costs, enabling Ford to cut prices for everyday consumers."
            ),
            "teaching": {
                "current_action": "probe",
                "current_question": "How did assembly-line production affect car prices?",
                "attempt_count": 1,
                "correct_checks": 1,
                "has_transfer_correct": False,
                "misconception_history": [],
            },
            "asked_question_ids": ["assembly_line_q1"],
            "asked_question_texts": ["How did assembly-line production affect car prices?"],
            "retry_count": 0,
        }

        output = sage_agent(state)
        response_text = output["tutor_response"]

        # 1. Must acknowledge the answer
        self.assertIn("Verdict:** Correct!", response_text)
        # 2. Must explain why it's correct
        self.assertIn("per-unit labor costs", response_text)
        # 3. Must maintain continuity
        self.assertTrue(
            "Building on" in response_text or "Assembly Line" in response_text,
            f"Expected continuity lead-in, got: {response_text}"
        )
        # 4. Must provide the next question with context
        self.assertIn("**Question:**", response_text)

    def test_concept_advancement_preserves_acknowledgment_and_bridges(self):
        """
        When student masters concept A and advances to concept B,
        SAGE must acknowledge the answer on concept A, celebrate mastery,
        and introduce concept B with an explanation before asking questions.
        """
        curriculum = [
            CurriculumConcept(
                concept_id="assembly_line",
                name="Assembly Line Production",
                description="Sequential manufacturing method.",
                prerequisites=[],
                difficulty=1
            ),
            CurriculumConcept(
                concept_id="interchangeable_parts",
                name="Interchangeable Parts",
                description="Components manufactured to specifications that fit into any assembly of the same type.",
                prerequisites=["assembly_line"],
                difficulty=2
            ),
        ]

        state: TutorState = {
            "current_concept": "assembly_line",
            "target_topic": "Industrial Manufacturing",
            "curriculum": curriculum,
            "mastery": {"assembly_line": 0.9, "interchangeable_parts": 0.1},
            "teaching_mode": "mode_2_teach_first",
            "teaching_step": "check",
            "teaching": {
                "current_action": "advance",
                "current_question": "How did assembly-line production affect car prices?",
                "attempt_count": 2,
                "correct_checks": 2,
                "has_transfer_correct": True,
                "misconception_history": [],
                "concept_completed": True,
            },
            "teaching_assessment": TeachingAssessment(
                understanding="mastered",
                score=1.0,
                confidence=1.0,
                misconceptions=[],
                reasoning_quality="strong",
                feedback="Exactly right: standardized repetitive operations lowered assembly time from 12 hours to 93 minutes, driving costs down."
            ),
            "pending_question": {
                "question_id": "assembly_line_q1",
                "question": "How did assembly-line production affect car prices?",
                "expected_answer": "Lowered costs per vehicle.",
                "concept_id": "assembly_line",
            },
            "retry_count": 0,
        }

        # Step 1: Advance concept
        advanced_state = advance_concept(state)
        self.assertEqual(advanced_state["current_concept"], "interchangeable_parts")
        self.assertIsNotNone(advanced_state["teaching_assessment"], "Assessment should not be wiped upon advancement")

        # Step 2: SAGE presents the new milestone
        merged_state = {**state, **advanced_state}
        output = sage_agent(merged_state)
        tutor_msg = output["tutor_response"]

        # Must acknowledge the previous correct answer
        self.assertIn("Verdict:** Correct!", tutor_msg)
        self.assertIn("driving costs down", tutor_msg)
        # Must celebrate previous concept mastery
        self.assertIn("Assembly Line", tutor_msg)
        # Must introduce the new concept with an explanation
        self.assertIn("Interchangeable Parts", tutor_msg)
        # Must provide explanation before testing
        self.assertTrue(output["awaiting"] in ("continue", "answer"))


if __name__ == "__main__":
    unittest.main()
