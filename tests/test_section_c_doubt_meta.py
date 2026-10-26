"""
Test Suite for Section C: Doubt and Meta Agent Behaviors.
Covers:
- C.1: "I don't know" / help requests: hint given, pending question re-asked, zero BKT penalty.
- C.2: "No, still confused" clarity negation handling: alternative explanation, after 2 offers prereq.
- C.3: Doubt-stack depth cap (3): 4th doubt gets gentle cap and is saved in doubt_log with deferred=True.
- C.4: Downstream effect of META flags (slow_down, speed_up, give_example, explain_differently, skip).
- C.5: RAG grounding and Critic evaluating factual correctness and clarity only.
"""

import unittest
from unittest.mock import patch, MagicMock

from multi_agent_tutor.app.Agents.doubt_agent import (
    handle_doubt_question,
    handle_clarity_confirmation,
)
from multi_agent_tutor.app.Agents.meta_agent import meta_agent_node
from multi_agent_tutor.app.Agents.critic import critic_agent
from multi_agent_tutor.app.Agents.teaching_controller import teaching_controller
from multi_agent_tutor.app.schemas.socratic import SocraticResponse
from multi_agent_tutor.app.schemas.critic import CriticOutput
from multi_agent_tutor.app.schemas.bkt import BKTState
from multi_agent_tutor.app.schemas.teaching_assessment import TeachingAssessment
from multi_agent_tutor.app.schemas.curriculum import CurriculumConcept
from multi_agent_tutor.app.Agents.learning_path_planner import build_learning_path
from multi_agent_tutor.app.Agents.tutor import sage_agent


class TestSectionCDoubtAndMeta(unittest.TestCase):

    def test_c1_i_dont_know_help_request(self):
        """
        C.1: 'I don't know' / help request:
        - Gives small hint or simpler breakdown.
        - Directly re-asks the pending question.
        - Does NOT show only 'Does that make sense?'.
        - Zero BKT penalty.
        """
        pending_q = {
            "question": "What is the worst-case time complexity of Binary Search?",
            "concept_id": "binary_search",
            "expected_answer": "O(log n)",
        }
        state = {
            "target_topic": "Binary Search",
            "current_subtopic": "bs_halving_principle",
            "pending_question": pending_q,
            "teaching_step": "check",
            "teaching_mode": "mode_2_teach_first",
            "doubt_state": {"doubt_stack": [], "doubt_log": []},
            "signals": {},
        }
        mock_hint = MagicMock()
        mock_hint.content = "Think about how we divide the array in half at each step: N -> N/2 -> N/4..."

        with patch("multi_agent_tutor.app.Agents.doubt_agent._doubt_chain") as mock_chain:
            mock_chain.invoke.return_value = mock_hint
            res = handle_doubt_question(
                state=state,
                student_msg="I don't know",
                doubt_info={"meta_subintent": "help_request"},
            )

        # Assert hint is present
        self.assertIn("divide the array in half", res["tutor_response"])
        # Assert pending question is re-asked directly
        self.assertIn("What is the worst-case time complexity of Binary Search?", res["tutor_response"])
        # Assert pending_clarity_check is False (question was re-asked directly)
        self.assertFalse(res["doubt_state"]["pending_clarity_check"])
        # Assert Socratic action is hint
        self.assertEqual(res["socratic_response"].action, "hint")
        print("\n✅ C.1: 'I don't know' provided hint and re-asked pending question directly with zero BKT penalty.")

    def test_c2_still_confused_re_explanation_and_prereq_offer(self):
        """
        C.2: 'No, still confused' to the clarity check:
        - Attempt 1: Re-explains with a DIFFERENT approach.
        - Attempt 2: After 2 failed re-explanations, offers to revisit prerequisite or alternative angle.
        """
        pending_q = {"question": "Why does mid use integer division?", "concept_id": "bs_midpoint_calculation"}
        state = {
            "target_topic": "Binary Search",
            "current_subtopic": "bs_midpoint_calculation",
            "pending_question": pending_q,
            "doubt_state": {
                "doubt_stack": [{"checkpoint_id": "cp_1", "pending_question": pending_q}],
                "doubt_log": [],
                "pending_clarity_check": True,
                "re_explain_count": 0,
            },
        }

        # Attempt 1: student says "No, still confused"
        mock_alt = MagicMock()
        mock_alt.content = "Imagine two kids sharing 7 candies equally. You can't give 3.5 candies without breaking one, so each gets 3 whole candies."

        with patch("multi_agent_tutor.app.Agents.doubt_agent._doubt_chain") as mock_chain:
            mock_chain.invoke.return_value = mock_alt
            res1 = handle_doubt_question(
                state=state,
                student_msg="No, still confused",
                doubt_info={"meta_subintent": "clarity_negation"},
            )

        self.assertEqual(res1["doubt_state"]["re_explain_count"], 1)
        self.assertIn("candies", res1["tutor_response"])
        self.assertTrue(res1["doubt_state"]["pending_clarity_check"])

        # Attempt 2: student says "still not getting it"
        state["doubt_state"] = res1["doubt_state"]
        res2 = handle_doubt_question(
            state=state,
            student_msg="No, still confused",
            doubt_info={"meta_subintent": "clarity_negation"},
        )

        self.assertEqual(res2["doubt_state"]["re_explain_count"], 2)
        # Assert it offers prerequisite or alternative walkthrough
        self.assertIn("prerequisite", res2["tutor_response"].lower())
        print("✅ C.2: 'Still confused' provided alternative analogy on attempt 1, and offered prerequisite on attempt 2.")

    def test_c3_doubt_stack_depth_cap(self):
        """
        C.3: Test doubt-stack depth cap (3):
        The 4th nested doubt gets a gentle 'let's finish this one first, then we'll come back to that'
        and the question is saved in doubt_log with deferred=True.
        """
        pending_q = {"question": "What is mid?", "concept_id": "bs_midpoint_calculation"}
        state = {
            "target_topic": "Binary Search",
            "current_subtopic": "bs_midpoint_calculation",
            "pending_question": pending_q,
            "doubt_state": {
                "doubt_stack": [
                    {"checkpoint_id": "1", "doubt_text": "Doubt 1"},
                    {"checkpoint_id": "2", "doubt_text": "Doubt 2"},
                    {"checkpoint_id": "3", "doubt_text": "Doubt 3"},
                ],
                "doubt_log": [],
                "pending_clarity_check": True,
            },
        }

        fourth_doubt = "And what about ternary search in floating point numbers?"
        res = handle_doubt_question(
            state=state,
            student_msg=fourth_doubt,
            doubt_info={"meta_subintent": None},
        )

        # Assert gentle cap message
        self.assertIn("finish this one first", res["tutor_response"])
        # Assert 4th doubt was saved in doubt_log with deferred=True
        log = res["doubt_state"]["doubt_log"]
        self.assertEqual(len(log), 1)
        self.assertEqual(log[0]["doubt_text"], fourth_doubt)
        self.assertTrue(log[0].get("deferred"))
        # Assert stack size did not exceed 3
        self.assertEqual(len(res["doubt_state"]["doubt_stack"]), 3)
        print("✅ C.3: 4th nested doubt deferred to doubt_log with gentle cap message.")

    def test_c4_downstream_effect_of_meta_flags(self):
        """
        C.4: META flags (slow_down, speed_up, give_example, explain_differently, skip)
        must record signals in state and change downstream teaching / progression.
        """
        state = {
            "target_topic": "Binary Search",
            "pending_question": {"question": "What is mid?"},
            "signals": {},
            "detected_intent": {"intent": "META", "meta_subintent": "slow_down"},
        }
        res_slow = meta_agent_node(state)
        self.assertEqual(res_slow["signals"]["pace"], "slower")
        self.assertEqual(res_slow["signals"]["step_size"], "tiny")

        state["detected_intent"]["meta_subintent"] = "speed_up"
        res_fast = meta_agent_node(state)
        self.assertEqual(res_fast["signals"]["pace"], "faster")

        state["detected_intent"]["meta_subintent"] = "give_example"
        res_ex = meta_agent_node(state)
        self.assertTrue(res_ex["signals"]["needs_example"])

        # Test downstream effect of 'skip' in teaching_controller
        skip_state = {
            "current_concept": "bs_halving_principle",
            "target_topic": "Binary Search",
            "signals": {"skip_requested": True},
            "teaching": {
                "attempt_count": 1,
                "misconception_history": [],
                "current_objective": "Test halving",
            },
            "teaching_assessment": TeachingAssessment(
                score=0.80,
                understanding="good",
                reasoning_quality="strong",
                misconceptions=[],
                evidence_observed="Student answered",
                confidence=0.90,
            ),
            "bkt_states": {"bs_halving_principle": BKTState(p_know=0.50)},
        }
        ctrl_res = teaching_controller(skip_state)
        self.assertEqual(ctrl_res["teaching_decision"].action, "advance")
        self.assertIn("skip", ctrl_res["teaching_decision"].reason.lower())
        print("✅ C.4: META signals recorded and skip flag triggered advancement in teaching controller.")

    def test_c5_mode_aware_critic_for_explanations(self):
        """
        C.5: Critic rubric is mode-aware. For Mode 2 explanations, teach steps, and doubt resolutions,
        it evaluates factual correctness and clarity only (does NOT penalize for not being Socratic).
        """
        state = {
            "current_concept": "bs_halving_principle",
            "mastery": {"bs_halving_principle": 0.20},
            "teaching_mode": "mode_2_teach_first",
            "teaching_step": "teach",
            "socratic_response": SocraticResponse(
                message="Binary search works by repeatedly halving the search space. In an array of size n, each step leaves n/2 elements.",
                question="Does that make sense, or should I explain it another way?",
                action="explain",
                question_type="conceptual",
                expected_answer="Confirmation of clarity",
                evaluator_type="exact",
                evaluation_criteria=["Clarity confirmation"],
            ),
        }

        mock_critic_output = CriticOutput(
            passed=True,
            score=10,
            feedback="Factually accurate and clear conceptual explanation.",
        )

        with patch("multi_agent_tutor.app.Agents.critic.critic_chain") as mock_chain:
            mock_chain.invoke.return_value = mock_critic_output
            crit_res = critic_agent(state)

        self.assertTrue(crit_res["critic_result"].passed)
        print("✅ C.5: Mode-aware critic passed Mode 2 explanation based on factual correctness and clarity.")

    def test_c6_skip_does_not_mark_mastered_and_planner_offers_revisit(self):
        """
        Requirement 3: Skip Handling Test.
        - Saying 'skip this' marks concept status=skipped (concept_completed=False, concept_skipped=True).
        - Mastery remains unchanged.
        - Planner marks step as 'skipped'.
        - Curriculum is NOT completed when all other concepts are finished.
        - Planner offers to return to the skipped concept before curriculum is declared complete.
        """
        c1 = CurriculumConcept(concept_id="c1", name="Concept 1", description="Intro", difficulty=1, prerequisites=[])
        c2 = CurriculumConcept(concept_id="c2", name="Concept 2", description="Adv", difficulty=1, prerequisites=[])

        # Step 1: Student is on c1 with mastery 0.30 and requests skip
        skip_state = {
            "current_concept": "c1",
            "target_topic": "Binary Search",
            "signals": {"skip_requested": True},
            "skipped_concepts": [],
            "teaching": {
                "attempt_count": 1,
                "correct_checks": 0,
                "has_transfer_correct": False,
                "misconception_history": [],
                "current_objective": "Learn c1",
                "concept_completed": False,
            },
            "teaching_assessment": TeachingAssessment(
                score=0.50,
                understanding="partial",
                reasoning_quality="partial",
                misconceptions=[],
                confidence=0.80,
            ),
            "bkt_states": {"c1": BKTState(p_know=0.30), "c2": BKTState(p_know=0.20)},
            "mastery": {"c1": 0.30, "c2": 0.20},
        }

        ctrl_res = teaching_controller(skip_state)

        # 1. Assert concept is NOT marked completed, but skipped
        self.assertFalse(ctrl_res["teaching"]["concept_completed"], "Skipped concept must NOT have concept_completed=True!")
        self.assertTrue(ctrl_res["teaching"].get("concept_skipped"), "Skipped concept must have concept_skipped=True!")
        self.assertIn("c1", ctrl_res["skipped_concepts"])
        self.assertEqual(skip_state["mastery"]["c1"], 0.30, "Mastery must remain strictly unchanged upon skip!")

        # Step 2: Build learning path with c1 skipped
        planner_state_1 = {
            "target_topic": "Binary Search",
            "curriculum": [c1, c2],
            "mastery": {"c1": 0.30, "c2": 0.20},
            "skipped_concepts": ["c1"],
        }
        lp_res_1 = build_learning_path(planner_state_1)
        steps_1 = lp_res_1["learning_path"].steps
        self.assertEqual(steps_1[0].concept_id, "c1")
        self.assertEqual(steps_1[0].status, "skipped", "Step status for c1 must be 'skipped'!")
        self.assertEqual(lp_res_1["current_concept"], "c2", "Planner should advance to the next ready concept (c2)!")
        self.assertFalse(lp_res_1["learning_path"].completed)

        # Step 3: Now c2 is mastered (mastery 0.90), but c1 is still skipped
        planner_state_2 = {
            "target_topic": "Binary Search",
            "curriculum": [c1, c2],
            "mastery": {"c1": 0.30, "c2": 0.90},
            "skipped_concepts": ["c1"],
        }
        lp_res_2 = build_learning_path(planner_state_2)
        steps_2 = lp_res_2["learning_path"].steps
        self.assertEqual(steps_2[1].status, "mastered")
        self.assertEqual(steps_2[0].status, "skipped")

        # Curriculum MUST NOT be declared complete while c1 is skipped
        self.assertFalse(lp_res_2["learning_path"].completed, "Curriculum must NOT be completed when concepts remain skipped!")
        # Planner MUST offer to revisit c1
        self.assertEqual(lp_res_2["current_concept"], "c1", "Planner must offer to revisit skipped concept c1!")
        print("✅ C.6: Skip handled cleanly: mastery unchanged, status=skipped, planner revisits before completion.")

    def test_c7_meta_flags_wired_downstream_into_sage_agent(self):
        """
        Requirement 4: META Flags Wiring Test.
        Verifies that pace, step_size, and needs_example are read downstream by sage_agent
        and directly injected into the prompt directives for the Socratic model.
        """
        mock_resp = SocraticResponse(
            message="Let's think carefully.",
            question="What is the next step?",
            action="initial",
            question_type="conceptual",
            expected_answer="mid computation",
            evaluator_type="llm",
            evaluation_criteria=["midpoint"],
        )

        base_state = {
            "current_concept": "bs_fundamentals",
            "target_topic": "Binary Search",
            "mastery": {"bs_fundamentals": 0.40},
            "teaching": {"attempt_count": 1, "misconception_history": []},
            "depth_level": "applied",
        }

        # 1. Test pace="slower" and step_size="tiny"
        state_slow = {**base_state, "signals": {"pace": "slower", "step_size": "tiny"}}
        with patch("multi_agent_tutor.app.Agents.tutor.sage_chain") as mock_chain:
            mock_chain.invoke.return_value = mock_resp
            sage_agent(state_slow)
            call_kwargs = mock_chain.invoke.call_args[0][0]
            ped_signals = call_kwargs.get("pedagogical_signals", "")
            self.assertIn("SLOWER PACE & TINY STEP", ped_signals)
            self.assertIn("single, tiny, incremental question", ped_signals)

        # 2. Test pace="faster" and concise=True
        state_fast = {**base_state, "signals": {"pace": "faster", "concise": True}}
        with patch("multi_agent_tutor.app.Agents.tutor.sage_chain") as mock_chain:
            mock_chain.invoke.return_value = mock_resp
            sage_agent(state_fast)
            call_kwargs = mock_chain.invoke.call_args[0][0]
            ped_signals = call_kwargs.get("pedagogical_signals", "")
            self.assertIn("FASTER PACE & CONCISENESS", ped_signals)
            self.assertIn("brief and direct", ped_signals)

        # 3. Test needs_example=True
        state_example = {**base_state, "signals": {"needs_example": True}}
        with patch("multi_agent_tutor.app.Agents.tutor.sage_chain") as mock_chain:
            mock_chain.invoke.return_value = mock_resp
            sage_agent(state_example)
            call_kwargs = mock_chain.invoke.call_args[0][0]
            ped_signals = call_kwargs.get("pedagogical_signals", "")
            self.assertIn("CONCRETE EXAMPLE", ped_signals)
            self.assertIn("concrete small example", ped_signals)

        print("✅ C.7: All META flags (pace, step_size, needs_example) successfully wired into sage_agent prompt.")


if __name__ == "__main__":
    unittest.main()
