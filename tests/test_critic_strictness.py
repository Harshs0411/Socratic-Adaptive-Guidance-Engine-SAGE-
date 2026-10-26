"""
Test Critic Strictness on SAGE Language and Analogies.
Verifies:
1. Critic strictly evaluates and rejects out-of-context 'Russian nesting doll' analogies for recursion.
2. Critic provides actionable, pedagogically grounded feedback explaining why Russian dolls misrepresent computation.
3. Critic passes technically authentic recursion explanations (call stack frames, return value propagation).
4. Analogy sanitizer replaces clichéd Russian doll analogies with authentic computational models.
"""

import unittest
from multi_agent_tutor.app.Agents.critic import critic_agent
from multi_agent_tutor.app.Agents.teaching_agent import sanitize_analogy, _DYNAMIC_PEDAGOGICAL_CACHE
from multi_agent_tutor.app.schemas.socratic import SocraticResponse


class TestCriticStrictness(unittest.TestCase):

    def test_critic_rejects_russian_doll_analogy(self):
        """
        Critic MUST fail any SAGE response that uses Russian nesting dolls to explain recursion.
        """
        mock_state = {
            "current_concept": "base_case",
            "target_topic": "recursion",
            "mastery": {"base_case": 0.1},
            "teaching_mode": "mode_2_teach_first",
            "teaching_step": "teach",
            "retry_count": 0,
            "socratic_response": SocraticResponse(
                message=(
                    "## 📚 Base Case (Part 1/4: Intuition)\n\n"
                    "Think of recursion like Russian nesting dolls! You open one doll, and inside is another smaller doll, "
                    "until you reach the smallest doll which cannot be opened further. That smallest doll is your base case."
                ),
                question="",
                action="explain",
                expected_answer="Continue",
                evaluator_type="exact",
                evaluation_criteria=[],
                question_type="conceptual",
            )
        }

        output = critic_agent(mock_state)
        crit_result = output["critic_result"]

        self.assertFalse(crit_result.passed, "Critic must reject Russian nesting doll analogy!")
        self.assertLessEqual(crit_result.score, 5.0)
        self.assertIn("russian doll", crit_result.feedback.lower())
        self.assertIn("call stack", crit_result.feedback.lower())
        self.assertEqual(output["retry_count"], 1)

    def test_critic_passes_authentic_computational_analogy(self):
        """
        Critic should pass authentic computational analogies (call stack frames, task delegation with return propagation).
        """
        mock_state = {
            "current_concept": "base_case",
            "target_topic": "recursion",
            "mastery": {"base_case": 0.1},
            "teaching_mode": "mode_2_teach_first",
            "teaching_step": "teach",
            "retry_count": 0,
            "socratic_response": SocraticResponse(
                message=(
                    "## 📚 Base Case (Part 1/4: Intuition)\n\n"
                    "Think of recursion as Task Delegation with Return Handoff: A lead engineer delegates a smaller identical subproblem "
                    "to an assistant, who in turn delegates further, creating a stack of pending execution frames. Once the simplest base-case "
                    "task is reached (e.g. factorial(1) = 1), it returns an immediate value. That value is passed back up the call stack frame "
                    "by frame, allowing each caller to complete their multiplication until the final answer is computed."
                ),
                question="",
                action="explain",
                expected_answer="Continue",
                evaluator_type="exact",
                evaluation_criteria=[],
                question_type="conceptual",
            )
        }

        output = critic_agent(mock_state)
        crit_result = output["critic_result"]

        self.assertTrue(crit_result.passed, f"Critic should pass technically sound call-stack analogy! Feedback: {crit_result.feedback}")
        self.assertGreaterEqual(crit_result.score, 6.0)

    def test_sanitize_analogy_replaces_russian_dolls(self):
        """
        sanitize_analogy must replace Russian doll / Matryoshka tropes with computational models.
        """
        bad_analogy_1 = "Recursion is like Russian nesting dolls where each doll holds a smaller doll."
        bad_analogy_2 = "Think of Matryoshka dolls nested inside one another."

        clean_1 = sanitize_analogy(bad_analogy_1, "recursion", "base_case")
        clean_2 = sanitize_analogy(bad_analogy_2, "recursion", "recursive_step")

        self.assertNotIn("russian", clean_1.lower())
        self.assertNotIn("doll", clean_1.lower())
        self.assertIn("call stack", clean_1.lower())

        self.assertNotIn("matryoshka", clean_2.lower())
        self.assertIn("call stack", clean_2.lower())


if __name__ == "__main__":
    unittest.main()
