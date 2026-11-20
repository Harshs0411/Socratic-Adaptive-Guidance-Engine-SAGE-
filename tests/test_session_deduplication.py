import pytest
import asyncio
import httpx
from sqlalchemy import select
from multi_agent_tutor.api.server import app
from multi_agent_tutor.db.database import get_db_session, init_db
from multi_agent_tutor.db.models import LearningSessionModel
from multi_agent_tutor.db.repository import SessionRepository
from multi_agent_tutor.app.Agents.curriculum_generator import (
    get_curriculum_llm_call_count,
    reset_curriculum_llm_call_count,
    clear_curriculum_cache,
)


@pytest.mark.asyncio
async def test_session_deduplication_and_curriculum_reuse():
    """
    Verifies the 5 scenarios specified in the user request:
    1. User starts Cars -> one session and one curriculum.
    2. User requests Cars again -> existing active session resumes; zero new sessions and zero curriculum-generation calls.
    3. User starts Operating Systems -> new session and curriculum.
    4. User requests Cars again -> existing Cars session resumes.
    5. User explicitly selects Start Fresh -> new session, but existing Cars curriculum is reused.
    """
    await init_db()
    reset_curriculum_llm_call_count()
    clear_curriculum_cache()

    test_student = "student_verify_dedup_01"

    # Clean any prior sessions for this test student to start completely clean
    async with get_db_session() as session:
        existing = await session.execute(
            select(LearningSessionModel).where(LearningSessionModel.student_id == test_student)
        )
        for s in existing.scalars().all():
            await session.delete(s)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:

        # ======================================================================
        # SCENARIO 1: User starts Cars -> one session and one curriculum
        # ======================================================================
        initial_llm_calls = get_curriculum_llm_call_count()
        res1 = await client.post("/api/session/start", json={
            "student_id": test_student,
            "topic": "Cars",
            "depth_level": "deep",
            "self_reported_level": "beginner",
        })
        assert res1.status_code == 200, f"Scenario 1 failed: {res1.text}"
        data1 = res1.json()
        session_id_1 = data1["session_id"]
        assert data1["resumed"] is False
        assert len(data1["curriculum"]) > 0

        # Verify DB has exactly 1 session for this student
        student_sessions_1 = await SessionRepository.list_student_sessions(test_student)
        assert len(student_sessions_1) == 1
        assert student_sessions_1[0]["session_id"] == session_id_1
        calls_after_1 = get_curriculum_llm_call_count()

        print(f"\n[SCENARIO 1] Topic: 'Cars'")
        print(f"  Session ID: {session_id_1}")
        print(f"  Resumed: {data1['resumed']}")
        print(f"  Curriculum Concepts: {len(data1['curriculum'])}")
        print(f"  Total Curriculum LLM Calls: {calls_after_1}")

        # ======================================================================
        # SCENARIO 2: User requests Cars again -> active session resumes
        # Zero new sessions and zero curriculum-generation calls
        # ======================================================================
        res2 = await client.post("/api/session/start", json={
            "student_id": test_student,
            "topic": "cars",  # test normalization (lowercase)
            "depth_level": "deep",
            "self_reported_level": "beginner",
        })
        assert res2.status_code == 200, f"Scenario 2 failed: {res2.text}"
        data2 = res2.json()
        assert data2["session_id"] == session_id_1, "Expected to resume session_id_1"
        assert data2["resumed"] is True, "Expected resumed to be True"
        
        # Verify DB still has exactly 1 session
        student_sessions_2 = await SessionRepository.list_student_sessions(test_student)
        assert len(student_sessions_2) == 1, "Duplicate session created in DB!"
        
        calls_after_2 = get_curriculum_llm_call_count()
        assert calls_after_2 == calls_after_1, "Curriculum LLM was invoked unnecessarily on resume!"

        print(f"\n[SCENARIO 2] Request 'cars' again")
        print(f"  Session ID: {data2['session_id']} (Matches session 1: {data2['session_id'] == session_id_1})")
        print(f"  Resumed: {data2['resumed']}")
        print(f"  DB Sessions Count: {len(student_sessions_2)}")
        print(f"  Curriculum LLM Calls (Added: {calls_after_2 - calls_after_1}, Total: {calls_after_2})")

        # ======================================================================
        # SCENARIO 3: User starts Operating Systems -> new session and curriculum
        # ======================================================================
        res3 = await client.post("/api/session/start", json={
            "student_id": test_student,
            "topic": "Operating Systems",
            "depth_level": "deep",
            "self_reported_level": "beginner",
        })
        assert res3.status_code == 200, f"Scenario 3 failed: {res3.text}"
        data3 = res3.json()
        session_id_2 = data3["session_id"]
        assert session_id_2 != session_id_1
        assert data3["resumed"] is False

        student_sessions_3 = await SessionRepository.list_student_sessions(test_student)
        assert len(student_sessions_3) == 2, "Expected exactly 2 sessions in DB"
        calls_after_3 = get_curriculum_llm_call_count()

        print(f"\n[SCENARIO 3] Topic: 'Operating Systems'")
        print(f"  Session ID: {session_id_2}")
        print(f"  Resumed: {data3['resumed']}")
        print(f"  DB Sessions Count: {len(student_sessions_3)}")
        print(f"  Curriculum LLM Calls (Added: {calls_after_3 - calls_after_2}, Total: {calls_after_3})")

        # ======================================================================
        # SCENARIO 4: User requests Cars again -> existing Cars session resumes
        # ======================================================================
        res4 = await client.post("/api/session/start", json={
            "student_id": test_student,
            "topic": "Cars ",  # test trailing whitespace
            "depth_level": "deep",
            "self_reported_level": "beginner",
        })
        assert res4.status_code == 200, f"Scenario 4 failed: {res4.text}"
        data4 = res4.json()
        assert data4["session_id"] == session_id_1, f"Expected session_id_1 but got {data4['session_id']}"
        assert data4["resumed"] is True

        student_sessions_4 = await SessionRepository.list_student_sessions(test_student)
        assert len(student_sessions_4) == 2, "Duplicate session created in DB!"
        calls_after_4 = get_curriculum_llm_call_count()
        assert calls_after_4 == calls_after_3, "Curriculum LLM was invoked unnecessarily on resume!"

        print(f"\n[SCENARIO 4] Request 'Cars ' again")
        print(f"  Session ID: {data4['session_id']} (Resumed session 1: {data4['session_id'] == session_id_1})")
        print(f"  Resumed: {data4['resumed']}")
        print(f"  DB Sessions Count: {len(student_sessions_4)}")
        print(f"  Curriculum LLM Calls (Added: {calls_after_4 - calls_after_3}, Total: {calls_after_4})")

        # ======================================================================
        # SCENARIO 5: User explicitly selects Start Fresh -> new session,
        # but existing Cars curriculum is reused (Zero LLM calls)
        # ======================================================================
        res5 = await client.post("/api/session/start", json={
            "student_id": test_student,
            "topic": "Cars",
            "depth_level": "deep",
            "self_reported_level": "beginner",
            "start_fresh": True,
        })
        assert res5.status_code == 200, f"Scenario 5 failed: {res5.text}"
        data5 = res5.json()
        session_id_3 = data5["session_id"]
        assert session_id_3 != session_id_1, "Start fresh should generate a new session ID"
        assert session_id_3 != session_id_2
        assert data5["resumed"] is False

        student_sessions_5 = await SessionRepository.list_student_sessions(test_student)
        assert len(student_sessions_5) == 3, "Expected 3 sessions in DB after start_fresh"

        calls_after_5 = get_curriculum_llm_call_count()
        assert calls_after_5 == calls_after_4, "Curriculum LLM was called instead of reusing existing Cars curriculum!"

        print(f"\n[SCENARIO 5] Start Fresh on 'Cars'")
        print(f"  Session ID: {session_id_3} (New session created)")
        print(f"  Resumed: {data5['resumed']}")
        print(f"  DB Sessions Count: {len(student_sessions_5)}")
        print(f"  Curriculum LLM Calls (Added: {calls_after_5 - calls_after_4}, Total: {calls_after_5})")
        print("  -> Existing Cars curriculum successfully reused with 0 LLM calls!")


@pytest.mark.asyncio
async def test_concurrent_session_creation_safety():
    """
    Verifies that concurrent session start requests for the same student and topic
    are serialized safely by the mutex lock and do not produce duplicate sessions.
    """
    await init_db()
    test_student = "student_concurrent_test"

    # Clean test student
    async with get_db_session() as session:
        existing = await session.execute(
            select(LearningSessionModel).where(LearningSessionModel.student_id == test_student)
        )
        for s in existing.scalars().all():
            await session.delete(s)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Launch 5 concurrent requests simultaneously
        tasks = [
            client.post("/api/session/start", json={
                "student_id": test_student,
                "topic": "Machine Learning",
                "depth_level": "deep",
                "self_reported_level": "beginner",
            })
            for _ in range(5)
        ]
        results = await asyncio.gather(*tasks)

        session_ids = set()
        for r in results:
            assert r.status_code == 200
            session_ids.add(r.json()["session_id"])

        # All concurrent requests must resolve to the EXACT SAME session ID
        assert len(session_ids) == 1, f"Concurrent requests created multiple sessions: {session_ids}"

        # DB must have exactly 1 record
        db_sessions = await SessionRepository.list_student_sessions(test_student)
        assert len(db_sessions) == 1, f"Expected 1 session in DB, found {len(db_sessions)}"
        print(f"\n[CONCURRENCY TEST] 5 concurrent requests resolved to 1 session: {list(session_ids)[0]}")


@pytest.mark.asyncio
async def test_user_independence():
    """
    Verifies that different users have independent sessions and learning progress,
    while still benefiting from cross-user curriculum reuse.
    """
    await init_db()
    user_a = "student_user_alpha"
    user_b = "student_user_beta"

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        res_a = await client.post("/api/session/start", json={
            "student_id": user_a,
            "topic": "Robotics",
            "depth_level": "deep",
            "self_reported_level": "beginner",
        })
        sess_a = res_a.json()["session_id"]

        calls_before = get_curriculum_llm_call_count()

        res_b = await client.post("/api/session/start", json={
            "student_id": user_b,
            "topic": "Robotics",
            "depth_level": "deep",
            "self_reported_level": "beginner",
        })
        sess_b = res_b.json()["session_id"]

        calls_after = get_curriculum_llm_call_count()

        # Sessions are independent
        assert sess_a != sess_b, "Different users should have different session IDs"

        # User B reuses the Robotics curriculum synthesized for User A (zero extra LLM calls)
        assert calls_after == calls_before, "User B should reuse User A's synthesized curriculum"
        print(f"\n[USER INDEPENDENCE] User A session: {sess_a}, User B session: {sess_b} (Curriculum shared, 0 extra LLM calls)")
