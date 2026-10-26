"""
Test Suite for Section D: Mastery Safety & Subtopic Completion Rule.
Covers:
- D.1: Configurable subtopic completion rule:
       Topic/subtopic completes only when P(L) >= 0.85 AND correct_checks >= 3
       AND at least 1 transfer question answered correctly.
- D.2: Beginner simulation measuring turns needed to reach mastery from:
       P(L) = 0.0, P(L) = 0.35, and P(L) = 0.60.
"""

import unittest
from multi_agent_tutor.app.config import (
    MASTERY_ADVANCE_THRESHOLD,
    SUBTOPIC_MIN_CORRECT_CHECKS,
    SUBTOPIC_REQUIRE_TRANSFER,
)
from multi_agent_tutor.app.Agents.teaching_controller import teaching_controller
from multi_agent_tutor.app.utils.bkt import update_bkt, BKTState
from multi_agent_tutor.app.schemas.teaching_assessment import TeachingAssessment


class TestSectionDMasterySafety(unittest.TestCase):

    def test_d1_subtopic_completion_rule(self):
        """
        D.1: Verify subtopic completion rule:
        - Case A: High P(L) >= 0.85 but correct_checks < 3 -> DOES NOT ADVANCE (probes for more checks).
        - Case B: High P(L) >= 0.85 and correct_checks >= 3 but NO transfer question -> DOES NOT ADVANCE (probes for transfer).
        - Case C: High P(L) >= 0.85 and correct_checks >= 3 AND transfer question passed -> ADVANCES!
        """
        concept = "bs_halving_principle"
        self.assertEqual(SUBTOPIC_MIN_CORRECT_CHECKS, 3)
        self.assertTrue(SUBTOPIC_REQUIRE_TRANSFER)

        strong_assessment = TeachingAssessment(
            score=0.95,
            understanding="mastered",
            reasoning_quality="strong",
            misconceptions=[],
            evidence_observed="Perfect answer",
            confidence=0.95,
        )

        # ----------------------------------------------------
        # Case A: P(L) = 0.90, but only 1 correct check
        # ----------------------------------------------------
        state_case_a = {
            "current_concept": concept,
            "target_topic": "Binary Search",
            "signals": {},
            "bkt_states": {concept: BKTState(p_know=0.90)},
            "teaching": {
                "attempt_count": 1,
                "correct_checks": 0,  # will become 1 with this assessment
                "has_transfer_correct": False,
                "misconception_history": [],
                "current_objective": "Initial check",
            },
            "pending_question": {"question": "What is log n?", "is_transfer": False, "question_type": "conceptual"},
            "teaching_assessment": strong_assessment,
        }
        res_a = teaching_controller(state_case_a)
        self.assertEqual(res_a["teaching_decision"].action, "probe", "Should not advance with only 1 correct check.")
        self.assertFalse(res_a["teaching"]["concept_completed"])

        # ----------------------------------------------------
        # Case B: P(L) = 0.92, 3 correct checks, but NO transfer question
        # ----------------------------------------------------
        state_case_b = {
            "current_concept": concept,
            "target_topic": "Binary Search",
            "signals": {},
            "bkt_states": {concept: BKTState(p_know=0.92)},
            "teaching": {
                "attempt_count": 3,
                "correct_checks": 2,  # will become 3 with this assessment
                "has_transfer_correct": False,
                "misconception_history": [],
                "current_objective": "Check 3",
            },
            "pending_question": {"question": "What is worst case?", "is_transfer": False, "question_type": "conceptual"},
            "teaching_assessment": strong_assessment,
        }
        res_b = teaching_controller(state_case_b)
        self.assertEqual(res_b["teaching_decision"].action, "probe", "Should not advance without transfer question.")
        self.assertFalse(res_b["teaching"]["concept_completed"])
        self.assertIn("transfer", res_b["teaching"]["current_objective"].lower())

        # ----------------------------------------------------
        # Case C: P(L) = 0.95, 3 correct checks, AND transfer question passed
        # ----------------------------------------------------
        state_case_c = {
            "current_concept": concept,
            "target_topic": "Binary Search",
            "signals": {},
            "bkt_states": {concept: BKTState(p_know=0.95)},
            "teaching": {
                "attempt_count": 3,
                "correct_checks": 2,  # will become 3
                "has_transfer_correct": False,
                "misconception_history": [],
                "current_objective": "Transfer check",
            },
            "pending_question": {"question": "Transfer problem in 2D array", "is_transfer": True, "question_type": "application"},
            "teaching_assessment": strong_assessment,
        }
        res_c = teaching_controller(state_case_c)
        self.assertEqual(res_c["teaching_decision"].action, "advance", "Should advance when P(L)>=0.85, checks>=3, and transfer passed.")
        self.assertTrue(res_c["teaching"]["concept_completed"])
        print("\n✅ D.1: Subtopic completion rule verified (gated by checks >= 3 and transfer question).")

    def test_d2_beginner_simulation_mastery_trajectories(self):
        """
        D.2: Beginner simulation measuring turns needed to reach mastery threshold (0.85).
        Evaluates from:
        1. P(L) = 0.0 (Absolute beginner)
        2. P(L) = 0.35 (Some knowledge)
        3. P(L) = 0.60 (Comfortable)
        """
        p_initials = [0.0, 0.35, 0.60]
        results = {}

        print("\n" + "=" * 80)
        print("SECTION D.2: BKT BEGINNER MASTERY SIMULATION".center(80))
        print("=" * 80)
        print(f"{'Initial P(L)':<15} | {'Turns to >= 0.85':<20} | {'P(L) Trajectory'}")
        print("-" * 80)

        for p_start in p_initials:
            bkt = BKTState(p_know=p_start)
            turns = 0
            traj = [round(p_start, 4)]

            while bkt.p_know < MASTERY_ADVANCE_THRESHOLD and turns < 15:
                # Evidence 1.0 = correct demonstration on check question
                bkt = update_bkt(bkt, evidence=1.0)
                turns += 1
                traj.append(round(bkt.p_know, 4))

            results[p_start] = (turns, traj)
            traj_str = " -> ".join(map(str, traj))
            print(f"{p_start:<15} | {turns:<20} | {traj_str}")

        # Assertions
        # Beginner (0.0): takes 4 correct check turns to exceed 0.85 (target 4-6)
        self.assertEqual(results[0.0][0], 4)
        self.assertGreaterEqual(results[0.0][1][-1], MASTERY_ADVANCE_THRESHOLD)

        # Some knowledge (0.35): takes 2 correct check turns
        self.assertEqual(results[0.35][0], 2)

        # Comfortable (0.60): takes 1 correct check turn
        self.assertEqual(results[0.60][0], 1)

        print("\nSimulation Result:")
        print(f"- Absolute Beginner (P(L)=0.0): reaches P(L)=0.8542 in exactly 4 correct checks.")
        print(f"- Combined with SUBTOPIC_MIN_CORRECT_CHECKS=3 and transfer check, total checks to complete = 4-5.")
        print(f"- Target of 4-6 checks per topic is achieved cleanly with standard BKT.")
        print("=" * 80)


if __name__ == "__main__":
    unittest.main()
