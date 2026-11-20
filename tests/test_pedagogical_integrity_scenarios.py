"""
Unit and Integration Tests for Pedagogical Integrity & Teaching-Before-Testing Guarantees.

Scenarios tested:
1. SAGE teaches a concept and asks a question about it -> Normal assessment.
2. SAGE only mentions a concept but doesn't explain it -> Teach before assessing.
3. SAGE plans to teach a concept later -> Must not ask assessment questions about it yet.
4. Student says "You haven't taught me this" and is correct -> Acknowledge and teach, without penalizing.
5. Student says "You haven't taught me this" but the concept was already explained -> Give a recap and another opportunity.
6. SAGE asks a comparison question where one concept is missing -> Teach the missing concept first.
"""

import unittest
from unittest.mock import MagicMock, patch
from multi_agent_tutor.app.graph.state import TutorState
from multi_agent_tutor.app.schemas.bkt import BKTState
from multi_agent_tutor.app.schemas.socratic import SocraticResponse
from multi_agent_tutor.app.schemas.teaching_assessment import TeachingAssessment
from multi_agent_tutor.app.schemas.critic import CriticOutput
from multi_agent_tutor.app.Agents.intent_classifier import pre_filter_intent, intent_classifier_node
from multi_agent_tutor.app.Agents.doubt_agent import doubt_agent_node, TeachingGapAudit
from multi_agent_tutor.app.Agents.teaching_assessor import assess_teaching_response
from multi_agent_tutor.app.Agents.mastery_updater import update_mastery
from multi_agent_tutor.app.Agents.critic import critic_agent
from multi_agent_tutor.app.rag.vector_store import has_indexed_documents, search_knowledge


class TestPedagogicalIntegrityScenarios(unittest.TestCase):

    def test_scenario_1_normal_teaching_and_assessment(self):
        """
        Scenario 1: SAGE teaches a concept and asks a question about it -> Normal assessment.
        - Answer attempt is classified as ANSWER_ATTEMPT.
        - Teaching assessment grades it with strong credit.
        - Mastery updates upward via BKT.
        """
        pq = {
            "question_id": "bs_q1",
            "concept_id": "binary_search",
            "question": "Why does Binary Search require the array to be sorted?",
            "expected_answer": "Sorted order allows us to compare against mid and eliminate half the search space.",
            "evaluator_type": "llm",
            "evaluation_criteria": ["Elimination of half", "Sorted order requirement"],
        }
        student_msg = "Because sorted order allows us to discard half of the remaining elements at each step."

        # 1. Intent classifier: should be ANSWER_ATTEMPT
        intent_res = pre_filter_intent(
            message=student_msg,
            has_pending_question=True,
            pending_question=pq,
            awaiting="answer",
        )
        self.assertIsNotNone(intent_res)
        self.assertEqual(intent_res.intent, "ANSWER_ATTEMPT")

        # 2. Teaching Assessment & Mastery Update
        state: TutorState = {
            "student_id": "test_student",
            "target_topic": "Binary Search",
            "current_concept": "binary_search",
            "pending_question": pq,
            "student_input": student_msg,
            "messages": [],
            "mastery": {"binary_search": 0.35},
            "bkt_states": {
                "binary_search": BKTState(p_know=0.35, p_learn=0.15, p_guess=0.20, p_slip=0.10)
            },
            "teaching": {"misconception_history": [], "attempt_count": 0},
            "teaching_assessment": None,
            "socratic_response": None,
        }

        with patch("multi_agent_tutor.app.Agents.teaching_assessor.assessment_chain") as mock_chain:
            mock_chain.invoke.return_value = TeachingAssessment(
                understanding="mastered",
                score=0.95,
                confidence=0.95,
                reasoning_quality="strong",
                misconceptions=[],
            )
            ass_res = assess_teaching_response(state)
            self.assertEqual(ass_res["teaching_assessment"].understanding, "mastered")
            self.assertGreaterEqual(ass_res["teaching_assessment"].score, 0.85)

            state["teaching_assessment"] = ass_res["teaching_assessment"]
            mastery_res = update_mastery(state)
            updated_p = mastery_res["bkt_states"]["binary_search"].p_know
            self.assertGreater(updated_p, 0.35, "Mastery should increase upon correct answer")

    def test_scenario_2_critic_catches_unexplained_concept(self):
        """
        Scenario 2: SAGE only mentions a concept but doesn't explain it -> Critic rejects it to enforce teaching first.
        """
        state: TutorState = {
            "student_id": "test_student",
            "target_topic": "Algorithms",
            "current_concept": "binary_search",
            "mastery": {"binary_search": 0.40},
            "messages": [
                {"role": "assistant", "content": "Welcome! We will soon cover Hash Tables and Trees, but today we start with Binary Search."}
            ],
            "socratic_response": SocraticResponse(
                message="How does a Hash Table handle collisions when inserting duplicate keys?",
                question="How does a Hash Table handle collisions when inserting duplicate keys?",
                action="probe",
                expected_answer="Chaining or open addressing",
                evaluator_type="llm",
                evaluation_criteria=["Mentions chaining"],
                question_type="conceptual",
            ),
            "teaching_mode": "mode_1_qa",
            "teaching_step": "check",
            "retry_count": 0,
        }

        with patch("multi_agent_tutor.app.Agents.critic.critic_chain") as mock_critic_chain:
            mock_critic_chain.invoke.return_value = CriticOutput(
                passed=False,
                score=4.0,
                feedback="Rejected: The proposed question asks about 'Hash Table collision resolution', which has not been explained to the student yet. Teach this concept briefly with an example first before asking an assessment question."
            )
            crit_res = critic_agent(state)
            self.assertFalse(crit_res["critic_result"].passed)
            self.assertIn("not been explained", crit_res["critic_result"].feedback)
            self.assertEqual(crit_res["retry_count"], 1)

    def test_scenario_3_critic_blocks_upcoming_planned_curriculum_question(self):
        """
        Scenario 3: SAGE plans to teach a concept later -> It must not ask assessment questions about it yet.
        """
        state: TutorState = {
            "student_id": "test_student",
            "target_topic": "Binary Search",
            "current_concept": "bs_array_invariants",
            "mastery": {"bs_array_invariants": 0.25},
            "messages": [
                {"role": "assistant", "content": "Lesson 1: In a sorted array, the elements are monotonic, allowing us to discard half of the array at each step."}
            ],
            "socratic_response": SocraticResponse(
                message="In Lesson 5, we will explore Answer Space Optimization. How do you establish the feasibility predicate for maximizing minimum distance?",
                question="How do you establish the feasibility predicate for maximizing minimum distance in answer space optimization?",
                action="probe",
                expected_answer="Feasibility predicate monotonicity",
                evaluator_type="llm",
                evaluation_criteria=["Monotonic predicate"],
                question_type="conceptual",
            ),
            "teaching_mode": "mode_2_teach_first",
            "teaching_step": "check",
            "retry_count": 0,
        }

        with patch("multi_agent_tutor.app.Agents.critic.critic_chain") as mock_critic_chain:
            mock_critic_chain.invoke.return_value = CriticOutput(
                passed=False,
                score=3.0,
                feedback="Rejected: The proposed question tests 'Answer Space Optimization' from an upcoming lesson. SAGE must only ask questions about concepts already taught in the conversation."
            )
            crit_res = critic_agent(state)
            self.assertFalse(crit_res["critic_result"].passed)
            self.assertIn("upcoming lesson", crit_res["critic_result"].feedback)

    def test_scenario_4_student_reports_untaught_concept_and_is_correct(self):
        """
        Scenario 4: Student says "You haven't taught me this" and is correct.
        - Intent classifier detects DOUBT / teaching_gap (never ANSWER_ATTEMPT).
        - SAGE checks conversation history and confirms it was untaught.
        - SAGE acknowledges mistake, explains the missing concept with a simple example, and re-asks question.
        - BKT mastery is 100% UNCHANGED (zero penalty).
        """
        student_msg = "You haven't taught me this."
        pq = {
            "question_id": "bs_f_q3",
            "concept_id": "binary_search",
            "question": "Can Binary Search be used to find an element in a rotated sorted array?",
            "expected_answer": "Yes, because one half always remains sorted.",
        }

        # 1. Intent classifier check
        intent_res = pre_filter_intent(
            message=student_msg,
            has_pending_question=True,
            pending_question=pq,
            awaiting="answer",
        )
        self.assertIsNotNone(intent_res)
        self.assertEqual(intent_res.intent, "DOUBT")
        self.assertEqual(intent_res.meta_subintent, "teaching_gap")

        # 2. Doubt agent execution
        state: TutorState = {
            "student_id": "test_student",
            "target_topic": "Binary Search",
            "current_concept": "binary_search",
            "student_input": student_msg,
            "pending_question": pq,
            "awaiting": "answer",
            "messages": [
                {"role": "assistant", "content": "Welcome to Binary Search! In standard binary search, the array must be sorted."}
            ],
            "detected_intent": {"intent": "DOUBT", "meta_subintent": "teaching_gap"},
            "doubt_state": {"doubt_stack": [], "doubt_log": []},
            "mastery": {"binary_search": 0.35},
            "bkt_states": {
                "binary_search": BKTState(p_know=0.35)
            },
            "teaching": {"attempt_count": 0},
        }

        with patch("multi_agent_tutor.app.Agents.doubt_agent._teaching_gap_chain") as mock_gap_chain:
            mock_gap_chain.invoke.return_value = TeachingGapAudit(
                was_taught=False,
                concept_identified="rotated sorted array",
                pedagogical_message=(
                    "You're completely right! My apologies—I asked you about rotated arrays before we properly covered them. "
                    "In a rotated sorted array (like [4, 5, 6, 7, 0, 1, 2]), a sorted list is shifted around a pivot point, "
                    "meaning at least one half is always normally sorted. "
                    "\n\nNow with that explained, let's take another look:\n\n**Question:** Can Binary Search be used to find an element in a rotated sorted array?"
                )
            )

            res = doubt_agent_node(state)

            # Verification of response
            self.assertIn("My apologies", res["tutor_response"])
            self.assertIn("rotated sorted array", res["tutor_response"])
            self.assertIn("Can Binary Search be used", res["tutor_response"])

            # Verification of state invariants
            self.assertEqual(res["awaiting"], "answer")
            self.assertEqual(res["pending_question"], pq)
            self.assertIsNone(res["student_input"])

            # Verify BKT was never touched:
            self.assertEqual(state["mastery"]["binary_search"], 0.35)
            self.assertEqual(state["bkt_states"]["binary_search"].p_know, 0.35)

    def test_scenario_5_student_reports_untaught_concept_but_was_already_explained(self):
        """
        Scenario 5: Student says "You didn't explain this concept" but it actually was explained.
        - Intent classifier routes to DOUBT / teaching_gap.
        - SAGE checks conversation history and sees the explanation was provided.
        - SAGE responds politely, gives a short recap, and offers another opportunity.
        - Zero penalty to mastery score.
        """
        student_msg = "You didn't explain this concept."
        pq = {
            "question_id": "bs_q_overflow",
            "concept_id": "binary_search",
            "question": "Why do we calculate mid using low + (high - low) // 2 instead of (low + high) // 2?",
            "expected_answer": "To prevent integer overflow in languages with fixed integer widths.",
        }

        intent_res = pre_filter_intent(
            message=student_msg,
            has_pending_question=True,
            pending_question=pq,
            awaiting="answer",
        )
        self.assertEqual(intent_res.intent, "DOUBT")

        state: TutorState = {
            "student_id": "test_student",
            "target_topic": "Binary Search",
            "current_concept": "binary_search",
            "student_input": student_msg,
            "pending_question": pq,
            "awaiting": "answer",
            "messages": [
                {
                    "role": "assistant",
                    "content": "Notice how we calculate the middle index: using mid = low + (high - low) // 2 prevents integer overflow in bounded arithmetic."
                }
            ],
            "detected_intent": {"intent": "DOUBT", "meta_subintent": "teaching_gap"},
            "doubt_state": {"doubt_stack": [], "doubt_log": []},
            "mastery": {"binary_search": 0.40},
            "bkt_states": {
                "binary_search": BKTState(p_know=0.40)
            },
            "teaching": {"attempt_count": 0},
        }

        with patch("multi_agent_tutor.app.Agents.doubt_agent._teaching_gap_chain") as mock_gap_chain:
            mock_gap_chain.invoke.return_value = TeachingGapAudit(
                was_taught=True,
                concept_identified="integer overflow in midpoint calculation",
                pedagogical_message=(
                    "No problem at all! We actually touched on this a moment ago when we looked at calculating the midpoint—here is a quick refresher:\n\n"
                    "Adding (low + high) directly can exceed the maximum integer limit if both numbers are large. Writing low + (high - low) // 2 achieves the exact same math safely without integer overflow.\n\n"
                    "With that refresher in mind, let's give it another shot:\n\n**Question:** Why do we calculate mid using low + (high - low) // 2 instead of (low + high) // 2?"
                )
            )

            res = doubt_agent_node(state)

            self.assertIn("quick refresher", res["tutor_response"])
            self.assertIn("integer overflow", res["tutor_response"])
            self.assertEqual(res["awaiting"], "answer")
            self.assertEqual(res["pending_question"], pq)
            self.assertEqual(state["mastery"]["binary_search"], 0.40)

    def test_scenario_6_comparison_question_missing_concept_caught_by_critic(self):
        """
        Scenario 6: SAGE asks a comparison question where one concept is missing -> Critic catches it.
        """
        state: TutorState = {
            "student_id": "test_student",
            "target_topic": "Searching Algorithms",
            "current_concept": "binary_search",
            "mastery": {"binary_search": 0.30},
            "messages": [
                {"role": "assistant", "content": "Binary search eliminates half the remaining items at each step on sorted data."}
            ],
            "socratic_response": SocraticResponse(
                message="Compare the lookup mechanics of Binary Search against a Bloom Filter.",
                question="How does the false positive probability of a Bloom Filter compare to Binary Search guarantees?",
                action="probe",
                expected_answer="Bloom filter is probabilistic while binary search is deterministic",
                evaluator_type="llm",
                evaluation_criteria=["Probabilistic vs deterministic"],
                question_type="conceptual",
            ),
            "teaching_mode": "mode_1_qa",
            "teaching_step": "check",
            "retry_count": 0,
        }

        with patch("multi_agent_tutor.app.Agents.critic.critic_chain") as mock_critic_chain:
            mock_critic_chain.invoke.return_value = CriticOutput(
                passed=False,
                score=3.5,
                feedback="Rejected: The comparison question requires knowledge of a 'Bloom Filter', which has not been taught in this conversation. Teach the missing concept first before asking a comparison question."
            )
            crit_res = critic_agent(state)
            self.assertFalse(crit_res["critic_result"].passed)
            self.assertIn("Teach the missing concept first", crit_res["critic_result"].feedback)

    def test_rag_token_saving_when_no_documents_indexed(self):
        """
        Verify RAG token saving: When no user documents exist for a topic,
        has_indexed_documents returns False and search_knowledge returns [] immediately
        without calling any LLM synthesizer or embedding calls.
        """
        with patch("multi_agent_tutor.app.rag.vector_store.get_vector_store") as mock_store_getter:
            mock_store = MagicMock()
            mock_store.get.return_value = {"ids": []}  # No documents in ChromaDB
            mock_store_getter.return_value = mock_store

            self.assertFalse(has_indexed_documents("brand_new_unseen_topic"))
            res = search_knowledge("What is the definition?", topic="brand_new_unseen_topic")
            self.assertEqual(res, [], "search_knowledge must return empty list when no documents are uploaded")
            # Verify no similarity search was executed
            mock_store.similarity_search_with_score.assert_not_called()


if __name__ == "__main__":
    unittest.main()
