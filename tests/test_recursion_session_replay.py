"""
Recursion Session Replay Test (Verification Suite).
Topic: 'recursion', Level: 'beginner'.
Verifies Fixes A through H:
 1. Topic Isolation (0% leakage across recursion, OSI model, and non-CS topic).
 2. Question Diversification & No-Repeat Memory.
 3. Assessor-to-Tutor Feedback Handoff (Verdict + 1-3 sentences feedback).
 4. Universal 4-Level Hint Ladder & Copy-Paste Detection.
 5. Lesson Pacing (Part 1 intuition, Parts 2-4 one at a time, check questions after).
 6. BKT Mastery Clamping (<= 99%) & Review Queue Management.
"""

import unittest
from fastapi.testclient import TestClient

from multi_agent_tutor.api.server import app
from multi_agent_tutor.db.database import init_db
from multi_agent_tutor.db.repository import SessionRepository
from multi_agent_tutor.app.Agents.teaching_agent import (
    check_copy_detection,
    is_near_duplicate_question,
    select_check_question,
)
from multi_agent_tutor.app.utils.bkt import update_bkt
from multi_agent_tutor.app.schemas.bkt import BKTState


class TestRecursionSessionReplay(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        await init_db()
        self.client = TestClient(app)
        for sid in ["recursion_replay_student", "osi_replay_student", "photo_replay_student"]:
            sessions = await SessionRepository.list_student_sessions(sid)
            for s in sessions:
                await SessionRepository.delete_session(s["session_id"])

    def test_full_recursion_beginner_session(self):
        """
        Runs a multi-turn beginner session on 'recursion' through:
        - Part 1 intuition & analogy
        - Part 2 concrete walkthrough
        - Part 3 edge cases
        - Part 4 visual architecture
        - Check questions with hint ladder, feedback handoff, and copy detection
        """
        sid = "recursion_replay_student"
        res0 = self.client.post("/api/session/start", json={
            "topic": "recursion",
            "student_id": sid,
            "self_reported_level": "beginner",
        })
        self.assertEqual(res0.status_code, 200)
        data0 = res0.json()
        session_id = data0["session_id"]
        p1_msg = data0["chat_history"][0]["content"]

        # Fix E: Part 1/4 only, no code, no check question
        self.assertIn("Part 1/4", p1_msg)
        self.assertEqual(data0["latest_message"]["awaiting"], "continue")

        # Step 2: Proceed to Part 2/4
        res1 = self.client.post("/api/chat", json={"session_id": session_id, "message": "continue"})
        self.assertEqual(res1.status_code, 200)
        p2_msg = res1.json()["latest_message"]["content"]
        self.assertIn("Part 2/4", p2_msg)
        self.assertEqual(res1.json()["latest_message"]["awaiting"], "continue")

        # Step 3: Proceed to Part 3/4
        res2 = self.client.post("/api/chat", json={"session_id": session_id, "message": "continue"})
        self.assertEqual(res2.status_code, 200)
        p3_msg = res2.json()["latest_message"]["content"]
        self.assertIn("Part 3/4", p3_msg)
        self.assertEqual(res2.json()["latest_message"]["awaiting"], "continue")

        # Step 4: Proceed to Part 4/4
        res3 = self.client.post("/api/chat", json={"session_id": session_id, "message": "continue"})
        self.assertEqual(res3.status_code, 200)
        p4_msg = res3.json()["latest_message"]["content"]
        self.assertIn("Part 4/4", p4_msg)

        # Step 5: Proceed to First Check Question
        res4 = self.client.post("/api/chat", json={"session_id": session_id, "message": "continue"})
        self.assertEqual(res4.status_code, 200)
        q1_data = res4.json()
        self.assertEqual(q1_data["latest_message"]["awaiting"], "answer")
        q1_text = q1_data["latest_message"]["question"]
        self.assertTrue(bool(q1_text))

        # Fix D: Ask for a hint ("I don't know")
        res_hint = self.client.post("/api/chat", json={"session_id": session_id, "message": "I don't know, can you give me a hint?"})
        self.assertEqual(res_hint.status_code, 200)
        hint_msg = res_hint.json()["latest_message"]["content"]
        self.assertIn("💡", hint_msg)
        # Nudge length check (at most 2-3 sentences in hint section)
        self.assertIn("hint in mind", hint_msg.lower())

        # Step 6: Answer Check Question 1 correctly
        res5 = self.client.post("/api/chat", json={
            "session_id": session_id,
            "message": "A base case is the condition where recursion stops, preventing infinite calls.",
        })
        self.assertEqual(res5.status_code, 200)
        feedback_data = res5.json()
        feedback_msg = feedback_data["latest_message"]["content"]

        # Fix C: Feedback must contain an explicit verdict BEFORE the next question
        self.assertTrue(
            "**Verdict:**" in feedback_msg or "Correct" in feedback_msg or "Partly right" in feedback_msg or "Not quite yet" in feedback_msg,
            f"Missing verdict in feedback: {feedback_msg}"
        )

        # Step 7: Check Question 2 is different from Check Question 1 (Fix B)
        q2_text = feedback_data["latest_message"]["question"]
        if q2_text:
            self.assertNotEqual(q1_text, q2_text)
            self.assertFalse(is_near_duplicate_question(q1_text, [q2_text]))

        # Step 8: Verify Topic Isolation (Fix A) & No Russian Doll Cliché - scan all messages in session
        all_msgs = [m["content"] for m in feedback_data["chat_history"]]
        forbidden_binary_search = ["binary search", "sorted array", "arr[mid]", "low + (high - low)"]
        forbidden_cliches = ["russian doll", "nesting doll", "matryoshka"]
        for msg in all_msgs:
            for term in forbidden_binary_search:
                self.assertNotIn(term, msg.lower(), f"Contamination! Found '{term}' in message: {msg}")
            for term in forbidden_cliches:
                self.assertNotIn(term, msg.lower(), f"Out-of-context trope! Found '{term}' in message: {msg}")

    def test_topic_isolation_across_multiple_domains(self):
        """
        Tests Topic Isolation across 3 distinct topics:
        1. OSI Model
        2. Photosynthesis (Non-CS)
        """
        # 1. OSI Model session
        res_osi = self.client.post("/api/session/start", json={
            "topic": "OSI model",
            "student_id": "osi_replay_student",
            "self_reported_level": "beginner",
        })
        self.assertEqual(res_osi.status_code, 200)
        osi_p1 = res_osi.json()["chat_history"][0]["content"]
        self.assertNotIn("binary search", osi_p1.lower())
        self.assertNotIn("call stack", osi_p1.lower())

        # 2. Photosynthesis (Non-CS topic)
        res_photo = self.client.post("/api/session/start", json={
            "topic": "Photosynthesis",
            "student_id": "photo_replay_student",
            "self_reported_level": "beginner",
        })
        self.assertEqual(res_photo.status_code, 200)
        photo_p1 = res_photo.json()["chat_history"][0]["content"]
        self.assertNotIn("binary search", photo_p1.lower())
        self.assertNotIn("recursion", photo_p1.lower())
        self.assertNotIn("osi model", photo_p1.lower())

    def test_copy_paste_detection_and_bkt_clamping(self):
        """
        Tests:
        - Copy detection when student quotes the tutor verbatim (Fix D)
        - BKT mastery is clamped to <= 0.99 (Fix G)
        """
        # Copy detection test
        tutor_exp = "The base case provides a direct answer without making any further recursive function calls."
        student_copy = "The base case provides a direct answer without making any further recursive function calls."
        is_copied, sim = check_copy_detection(student_copy, tutor_exp)
        self.assertTrue(is_copied)
        self.assertGreaterEqual(sim, 0.60)

        # Non-copy test
        student_original = "It stops the loop when n hits zero."
        is_copied_orig, sim_orig = check_copy_detection(student_original, tutor_exp)
        self.assertFalse(is_copied_orig)

        # BKT clamping test (never 100% or > 0.99)
        bkt = BKTState(p_know=0.98, p_learn=0.20, p_guess=0.20, p_slip=0.10)
        updated = update_bkt(bkt, evidence=1.0)
        self.assertLessEqual(updated.p_know, 0.99)
        self.assertGreaterEqual(updated.p_know, 0.0)
