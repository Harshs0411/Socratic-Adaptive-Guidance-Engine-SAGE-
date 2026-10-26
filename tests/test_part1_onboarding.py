"""
Unit and Integration Tests for Requirement 1 & Part 1:
Onboarding, First-Time Assessment, Returning Students, and Mid-Lesson Switch.
"""

import unittest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from multi_agent_tutor.api.server import app
from multi_agent_tutor.db.database import init_db
from multi_agent_tutor.db.repository import SessionRepository
from multi_agent_tutor.app.curriculum_loader import load_rich_curriculum, load_curriculum_concepts
from multi_agent_tutor.app.Agents.onboarding_agent import (
    detect_student_level,
    get_onboarding_greeting,
    get_clarifying_question,
    handle_beginner_onboarding,
    is_level_change_to_beginner,
    build_bank_diagnostic_questions,
)
from multi_agent_tutor.app.utils.bkt import update_bkt, apply_forgetting
from multi_agent_tutor.app.schemas.bkt import BKTState


class TestPart1Onboarding(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        await init_db()
        self.client = TestClient(app)

    def test_01_level_detection_and_vague_handling(self):
        """Verify level detector correctly parses beginner, some, comfortable, and vague."""
        lvl, is_vague = detect_student_level("I am a beginner")
        self.assertEqual(lvl, "beginner")
        self.assertFalse(is_vague)

        lvl, is_vague = detect_student_level("1")
        self.assertEqual(lvl, "beginner")

        lvl, is_vague = detect_student_level("I know some basics")
        self.assertEqual(lvl, "some_knowledge")
        self.assertFalse(is_vague)

        lvl, is_vague = detect_student_level("I'm comfortable with algorithms")
        self.assertEqual(lvl, "comfortable")
        self.assertFalse(is_vague)

        lvl, is_vague = detect_student_level("a little bit, not sure")
        self.assertIsNone(lvl)
        self.assertTrue(is_vague)

    def test_02_beginner_onboarding_state_invariants(self):
        """
        Requirement 1.A:
        - Ask ZERO test questions.
        - P(L) = 0.0 for EVERY topic in curriculum.
        - P(T) > 0 so mastery can grow from 0.
        - Pre-score for Hake's gain = 0.0.
        - Mode 2 (teach first), Topic 1 selected.
        - Planner does NOT mark everything locked or needs_review.
        """
        topic = "Binary Search"
        raw_state = {
            "student_id": "test_beginner_001",
            "target_topic": topic,
            "curriculum": load_curriculum_concepts(topic),
        }
        res = handle_beginner_onboarding(raw_state)

        # 1. Zero test questions
        self.assertEqual(len(res["diagnostic_state"]["questions"]), 0)
        self.assertTrue(res["diagnostic_state"]["completed"])
        self.assertIsNone(res["pending_question"])

        # 2. Every concept has P(L) = 0.0
        for cid, val in res["mastery"].items():
            self.assertEqual(val, 0.0, f"Concept {cid} must have P(L) = 0.0")

        # 3. P(T) > 0 in BKT states
        for cid, bkt in res["bkt_states"].items():
            self.assertEqual(bkt.p_know, 0.0)
            self.assertGreater(bkt.p_learn, 0.0, "P(T) must be > 0 for learning to occur")

        # 4. Mode 2 & Topic 1 selected
        self.assertEqual(res["teaching_mode"], "mode_2_teach_first")
        self.assertEqual(res["teaching_step"], "explain")
        self.assertEqual(res["current_concept"], "binary_search_fundamentals")

        # 5. Planner does NOT mark everything locked/needs_review
        lp = res["learning_path"]
        self.assertIsNotNone(lp)
        step0 = lp.steps[0]
        self.assertIn(step0.status, ["ready", "in_progress", "active"])

        # 6. Real BKT growth from 0.0: verify 4 checks to reach >= 0.85
        bkt_curr = BKTState(p_know=0.0, p_learn=0.07, p_guess=0.25, p_slip=0.10)
        # Check 1
        bkt_curr = update_bkt(bkt_curr, evidence=1.0)
        self.assertAlmostEqual(bkt_curr.p_know, 0.07, places=2)
        # Check 2
        bkt_curr = update_bkt(bkt_curr, evidence=1.0)
        self.assertGreater(bkt_curr.p_know, 0.20)
        # Check 3
        bkt_curr = update_bkt(bkt_curr, evidence=1.0)
        self.assertGreater(bkt_curr.p_know, 0.55)
        # Check 4
        bkt_curr = update_bkt(bkt_curr, evidence=1.0)
        self.assertGreaterEqual(bkt_curr.p_know, 0.85)

    async def test_03_beginner_via_api_starts_in_mode_2_with_explanation(self):
        """API test: Beginner student gets warm welcome explanation, no quiz question."""
        sid = "test_beg_api_01"
        res = self.client.post("/api/session/start", json={
            "topic": "Binary Search",
            "student_id": sid,
            "self_reported_level": "beginner",
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertEqual(data["phase"], "teaching")
        self.assertEqual(data["teaching_mode"], "mode_2_teach_first")
        self.assertIn("binary_search_fundamentals", data["active_concept"])
        # All mastery = 0.0
        for cid, val in data["mastery"].items():
            self.assertEqual(val, 0.0)

        # Message is an explanation, not a quiz
        latest = data["chat_history"][-1]
        self.assertIn("Beginner", latest["content"])
        self.assertIsNone(latest.get("question"))

    def test_04_bank_diagnostic_covers_all_topics(self):
        """Requirement 1.B: Diagnostic covers every topic from the question bank."""
        qs = build_bank_diagnostic_questions("Binary Search")
        rich = load_rich_curriculum("Binary Search")
        covered_concepts = {q.concept for q in qs}
        all_topic_ids = {t.topic_id for t in rich.topics}
        self.assertEqual(covered_concepts, all_topic_ids, "Diagnostic must cover every topic in curriculum.")
        self.assertGreaterEqual(len(qs), 6, "Must draw 1-2 questions per topic.")

    def test_05_forgetting_decay_model(self):
        """Requirement 4: Forgetting decays toward retention floor (0.20), never toward 0."""
        # Immediate return (0 days): no change
        p0 = apply_forgetting(0.85, days_elapsed=0.0)
        self.assertEqual(p0, 0.85)

        # After 10 days: decayed but bounded above floor
        p10 = apply_forgetting(0.85, days_elapsed=10.0, lambda_decay=0.05, retention_floor=0.20)
        self.assertLess(p10, 0.85)
        self.assertGreater(p10, 0.20)

        # After 500 days: reaches floor, NEVER 0.0
        p_far = apply_forgetting(0.85, days_elapsed=500.0, retention_floor=0.20)
        self.assertEqual(p_far, 0.20)

    async def test_06_mid_lesson_switch_to_beginner(self):
        """Requirement 1.6: Student saying 'actually I'm a beginner' resets priors to 0.0 in Mode 2."""
        sid = "test_mid_switch_01"
        res0 = self.client.post("/api/session/start", json={
            "topic": "Binary Search",
            "student_id": sid,
            "self_reported_level": "some_knowledge",
        })
        session_id = res0.json()["session_id"]

        # Student sends mid-lesson level switch
        res1 = self.client.post("/api/chat", json={
            "session_id": session_id,
            "message": "Actually I'm a beginner, can we start from scratch?",
        })
        self.assertEqual(res1.status_code, 200)
        data1 = res1.json()

        self.assertEqual(data1["teaching_mode"], "mode_2_teach_first")
        # All mastery reset to 0.0
        for cid, val in data1["mastery"].items():
            self.assertEqual(val, 0.0)
        self.assertIn("Resetting your journey to the **Beginner** path", data1["latest_message"]["content"])
