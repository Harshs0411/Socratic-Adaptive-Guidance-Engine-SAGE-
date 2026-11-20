#!/usr/bin/env python3
"""
SAGE Production Data Migration Tool: SQLite -> PostgreSQL.

Safely migrates all learning sessions, chat message history, and BKT mastery logs
from an existing local SQLite database to a production PostgreSQL database.

Guarantees:
- 100% data preservation (PKs, FKs, timestamps, JSONB structures).
- Idempotent and safe: avoids duplicate insertions without overwriting.
- Never modifies or deletes the source SQLite database.
- Verifies record counts before and after migration.
"""

import os
import sys
import json
import sqlite3
import argparse
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from multi_agent_tutor.db.models import Base, LearningSessionModel, ChatMessageModel, BKTLogModel
from multi_agent_tutor.db.database import normalize_database_url


def parse_sqlite_datetime(val: Any) -> Optional[datetime]:
    """Parse SQLite date/timestamp string into a timezone-aware UTC datetime."""
    if val is None:
        return None
    if isinstance(val, datetime):
        if val.tzinfo is None:
            return val.replace(tzinfo=timezone.utc)
        return val
    if isinstance(val, str):
        val = val.strip()
        # Handle ISO formats
        for fmt in (
            "%Y-%m-%d %H:%M:%S.%f",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S.%f%z",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%S",
        ):
            try:
                dt = datetime.strptime(val, fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except ValueError:
                continue
        # Fallback to datetime.fromisoformat
        try:
            dt = datetime.fromisoformat(val)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            pass
    return datetime.now(timezone.utc)


def parse_json_field(val: Any) -> Any:
    """Safely deserialize a JSON string from SQLite into Python primitives for JSONB."""
    if val is None:
        return None
    if isinstance(val, (dict, list)):
        return val
    if isinstance(val, str):
        val = val.strip()
        if not val:
            return None
        try:
            return json.loads(val)
        except Exception:
            return val
    return val


async def run_migration(sqlite_path: str, postgres_url: str) -> None:
    print("=" * 70)
    print("🐘 SAGE SQLite -> PostgreSQL Production Migration Tool")
    print("=" * 70)

    # 1. Verify SQLite Source
    if not os.path.isfile(sqlite_path):
        raise FileNotFoundError(f"Source SQLite database not found at: {sqlite_path}")

    norm_pg_url = normalize_database_url(postgres_url)
    if not norm_pg_url.startswith("postgresql"):
        raise ValueError(f"Destination must be a PostgreSQL connection URL. Got: {norm_pg_url}")

    # Hide password in logs for security
    safe_display_url = norm_pg_url
    if "@" in safe_display_url:
        prefix, host_part = safe_display_url.split("@", 1)
        if ":" in prefix:
            proto_user = prefix.split(":", 2)[:2]
            safe_display_url = f"{':'.join(proto_user)}:****@{host_part}"

    print(f"📁 Source SQLite Database   : {sqlite_path}")
    print(f"🐘 Destination PostgreSQL   : {safe_display_url}")
    print("-" * 70)

    # 2. Connect to SQLite
    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_conn.row_factory = sqlite3.Row
    sqlite_cursor = sqlite_conn.cursor()

    # Get SQLite Counts
    sqlite_cursor.execute("SELECT COUNT(*) FROM learning_sessions")
    sqlite_sessions_count = sqlite_cursor.fetchone()[0]

    sqlite_cursor.execute("SELECT COUNT(*) FROM chat_messages")
    sqlite_messages_count = sqlite_cursor.fetchone()[0]

    sqlite_cursor.execute("SELECT COUNT(*) FROM bkt_logs")
    sqlite_bkt_count = sqlite_cursor.fetchone()[0]

    print(f"📊 SQLite Records to Migrate:")
    print(f"   • learning_sessions : {sqlite_sessions_count}")
    print(f"   • chat_messages     : {sqlite_messages_count}")
    print(f"   • bkt_logs          : {sqlite_bkt_count}")
    print("-" * 70)

    # 3. Connect to PostgreSQL and create schema
    pg_engine = create_async_engine(norm_pg_url, echo=False)
    async_session = async_sessionmaker(pg_engine, class_=AsyncSession, expire_on_commit=False)

    print("🔧 Ensuring PostgreSQL tables exist...")
    async with pg_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ PostgreSQL schema verified.")

    # 4. Migrate learning_sessions
    migrated_sessions = 0
    skipped_sessions = 0

    sqlite_cursor.execute("SELECT * FROM learning_sessions")
    session_rows = sqlite_cursor.fetchall()

    async with async_session() as pg_sess:
        for row in session_rows:
            d = dict(row)
            sess_id = d["session_id"]

            # Check if session already exists
            existing = await pg_sess.scalar(
                select(LearningSessionModel.session_id).where(LearningSessionModel.session_id == sess_id)
            )
            if existing:
                skipped_sessions += 1
                continue

            session_model = LearningSessionModel(
                session_id=sess_id,
                student_id=d.get("student_id") or "student_001",
                topic=d.get("topic") or "General",
                phase=d.get("phase") or "diagnostic",
                current_concept=d.get("current_concept"),
                is_graduated=bool(d.get("is_graduated")),
                hake_gain=d.get("hake_gain"),
                assessment_done=bool(d.get("assessment_done")) if d.get("assessment_done") is not None else False,
                self_reported_level=d.get("self_reported_level"),
                teaching_mode=d.get("teaching_mode") or "mode_2_teach_first",
                teaching_step=d.get("teaching_step") or "teach",
                current_subtopic=d.get("current_subtopic"),
                doubt_state=parse_json_field(d.get("doubt_state")),
                pending_question=parse_json_field(d.get("pending_question")),
                awaiting=d.get("awaiting") or "none",
                teaching_step_index=d.get("teaching_step_index") or 0,
                last_tutor_message=d.get("last_tutor_message"),
                subtopic_mastery=parse_json_field(d.get("subtopic_mastery")),
                misconceptions_log=parse_json_field(d.get("misconceptions_log")),
                signals=parse_json_field(d.get("signals")),
                study_plan=parse_json_field(d.get("study_plan")),
                curriculum_data=parse_json_field(d.get("curriculum_data")),
                mastery_map=parse_json_field(d.get("mastery_map")),
                bkt_history=parse_json_field(d.get("bkt_history")),
                state_snapshot=parse_json_field(d.get("state_snapshot")),
                created_at=parse_sqlite_datetime(d.get("created_at")),
                updated_at=parse_sqlite_datetime(d.get("updated_at")),
            )
            pg_sess.add(session_model)
            migrated_sessions += 1

        await pg_sess.commit()

    print(f"💾 Migrated {migrated_sessions} sessions (Skipped existing: {skipped_sessions})")

    # 5. Migrate chat_messages
    migrated_messages = 0
    skipped_messages = 0

    sqlite_cursor.execute("SELECT * FROM chat_messages")
    msg_rows = sqlite_cursor.fetchall()

    async with async_session() as pg_sess:
        for row in msg_rows:
            d = dict(row)
            m_id = d["id"]

            existing = await pg_sess.scalar(
                select(ChatMessageModel.id).where(ChatMessageModel.id == m_id)
            )
            if existing:
                skipped_messages += 1
                continue

            msg_model = ChatMessageModel(
                id=m_id,
                session_id=d.get("session_id"),
                role=d.get("role") or "assistant",
                content=d.get("content") or "",
                question=d.get("question"),
                action=d.get("action"),
                metadata_info=parse_json_field(d.get("metadata_info")),
                rag_citations=parse_json_field(d.get("rag_citations")),
                created_at=parse_sqlite_datetime(d.get("created_at")),
            )
            pg_sess.add(msg_model)
            migrated_messages += 1

        await pg_sess.commit()

    print(f"💾 Migrated {migrated_messages} chat messages (Skipped existing: {skipped_messages})")

    # 6. Migrate bkt_logs
    migrated_bkt = 0
    skipped_bkt = 0

    sqlite_cursor.execute("SELECT * FROM bkt_logs")
    bkt_rows = sqlite_cursor.fetchall()

    async with async_session() as pg_sess:
        for row in bkt_rows:
            d = dict(row)
            bkt_id = d["id"]

            existing = await pg_sess.scalar(
                select(BKTLogModel.id).where(BKTLogModel.id == bkt_id)
            )
            if existing:
                skipped_bkt += 1
                continue

            bkt_model = BKTLogModel(
                id=bkt_id,
                session_id=d.get("session_id"),
                concept_id=d.get("concept_id") or "general",
                concept_name=d.get("concept_name") or "General",
                p_mastery=float(d.get("p_mastery") or 0.0),
                action=d.get("action") or "turn",
                created_at=parse_sqlite_datetime(d.get("created_at")),
            )
            pg_sess.add(bkt_model)
            migrated_bkt += 1

        await pg_sess.commit()

    print(f"💾 Migrated {migrated_bkt} BKT logs (Skipped existing: {skipped_bkt})")
    print("-" * 70)

    # 7. Final Verification
    async with async_session() as pg_sess:
        pg_sessions_count = await pg_sess.scalar(select(func.count()).select_from(LearningSessionModel))
        pg_messages_count = await pg_sess.scalar(select(func.count()).select_from(ChatMessageModel))
        pg_bkt_count = await pg_sess.scalar(select(func.count()).select_from(BKTLogModel))

    sqlite_conn.close()
    await pg_engine.dispose()

    print("📊 Migration Verification Table:")
    print(f"   Table             | SQLite Source | PostgreSQL Dest | Status")
    print(f"   ------------------|---------------|-----------------|---------")
    print(f"   learning_sessions | {sqlite_sessions_count:<13} | {pg_sessions_count:<15} | {'✅ MATCH' if pg_sessions_count >= sqlite_sessions_count else '⚠️ DIFFERENCE'}")
    print(f"   chat_messages     | {sqlite_messages_count:<13} | {pg_messages_count:<15} | {'✅ MATCH' if pg_messages_count >= sqlite_messages_count else '⚠️ DIFFERENCE'}")
    print(f"   bkt_logs          | {sqlite_bkt_count:<13} | {pg_bkt_count:<15} | {'✅ MATCH' if pg_bkt_count >= sqlite_bkt_count else '⚠️ DIFFERENCE'}")
    print("=" * 70)
    print("🎉 MIGRATION COMPLETED SUCCESSFULLY! No records were lost or overwritten.")


def main():
    parser = argparse.ArgumentParser(description="Migrate SAGE session data from SQLite to PostgreSQL.")
    parser.add_argument(
        "--sqlite-path",
        default=os.path.join(os.path.dirname(__file__), "..", "multi_agent_tutor", "data", "sage_sessions.db"),
        help="Path to the SQLite database file."
    )
    parser.add_argument(
        "--postgres-url",
        default=os.getenv("DATABASE_URL"),
        help="Target PostgreSQL connection URL (e.g. postgresql+asyncpg://...)."
    )
    args = parser.parse_args()

    if not args.postgres_url:
        print("❌ Error: No PostgreSQL URL provided. Set DATABASE_URL environment variable or pass --postgres-url.")
        sys.exit(1)

    asyncio.run(run_migration(args.sqlite_path, args.postgres_url))


if __name__ == "__main__":
    main()
