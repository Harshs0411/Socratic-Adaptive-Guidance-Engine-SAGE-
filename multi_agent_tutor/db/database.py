"""
Asynchronous Database Engine & Session Factory for SAGE.
Provides enterprise-grade PostgreSQL connectivity with asyncpg,
connection pooling, schema auto-creation, and seamless SQLite fallback.
"""

import os
import sys
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Dict, Any, Optional

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    create_async_engine,
    async_sessionmaker,
)
from dotenv import load_dotenv, find_dotenv

from multi_agent_tutor.db.models import Base

load_dotenv(find_dotenv())

logger = logging.getLogger("sage.database")

# Project paths
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA_DIR = os.path.join(PROJECT_ROOT, "multi_agent_tutor", "data")
os.makedirs(DATA_DIR, exist_ok=True)
SQLITE_PATH = os.path.join(DATA_DIR, "sage_sessions.db")

_engine: Optional[AsyncEngine] = None
_session_factory: Optional[async_sessionmaker[AsyncSession]] = None
_active_dialect: str = "unknown"
_db_connected: bool = False


def normalize_database_url(raw_url: Optional[str]) -> str:
    """Normalize database URL for async driver compatibility."""
    if not raw_url or not raw_url.strip():
        return f"sqlite+aiosqlite:///{SQLITE_PATH}"

    url = raw_url.strip()
    # Normalize postgres/postgresql to asyncpg
    if url.startswith("postgres://"):
        url = "postgresql+asyncpg://" + url[len("postgres://"):]
    elif url.startswith("postgresql://") and not url.startswith("postgresql+asyncpg://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://"):]

    return url


async def get_or_create_engine() -> AsyncEngine:
    """Initialize or return the global SQLAlchemy AsyncEngine with fallback protection."""
    global _engine, _session_factory, _active_dialect, _db_connected

    if _engine is not None:
        return _engine

    raw_url = os.getenv("DATABASE_URL")
    target_url = normalize_database_url(raw_url)

    is_postgres = target_url.startswith("postgresql")

    if is_postgres:
        try:
            # Create PostgreSQL async engine with production connection pooling
            pg_engine = create_async_engine(
                target_url,
                pool_size=10,
                max_overflow=20,
                pool_pre_ping=True,
                echo=False,
            )
            # Test connection
            async with pg_engine.connect() as conn:
                await conn.execute(Base.metadata.tables["learning_sessions"].select().limit(1) if "learning_sessions" in Base.metadata.tables else "SELECT 1")
            
            _engine = pg_engine
            _active_dialect = "postgresql"
            _db_connected = True
            logger.info("✅ Connected to PostgreSQL database successfully.")
        except Exception as e:
            logger.warning(
                f"⚠️ PostgreSQL connection to '{target_url}' failed ({e}). "
                f"Seamlessly falling back to local persistent SQLite at {SQLITE_PATH}."
            )
            fallback_url = f"sqlite+aiosqlite:///{SQLITE_PATH}"
            _engine = create_async_engine(fallback_url, echo=False)
            _active_dialect = "sqlite"
            _db_connected = True
    else:
        _engine = create_async_engine(target_url, echo=False)
        _active_dialect = "sqlite"
        _db_connected = True
        logger.info(f"📁 Using persistent SQLite session store at {target_url}.")

    _session_factory = async_sessionmaker(
        _engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    return _engine


async def init_db() -> None:
    """Creates tables if they don't exist and automatically migrates missing columns."""
    engine = await get_or_create_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        def migrate_columns(sync_conn):
            from sqlalchemy import inspect, text
            inspector = inspect(sync_conn)
            if "learning_sessions" in inspector.get_table_names():
                existing_cols = {col["name"] for col in inspector.get_columns("learning_sessions")}
                json_col_type = "JSONB" if _active_dialect == "postgresql" else "JSON"
                if "assessment_done" not in existing_cols:
                    sync_conn.execute(text("ALTER TABLE learning_sessions ADD COLUMN assessment_done BOOLEAN DEFAULT 0"))
                if "self_reported_level" not in existing_cols:
                    sync_conn.execute(text("ALTER TABLE learning_sessions ADD COLUMN self_reported_level VARCHAR(32)"))
                if "teaching_mode" not in existing_cols:
                    sync_conn.execute(text("ALTER TABLE learning_sessions ADD COLUMN teaching_mode VARCHAR(32) DEFAULT 'mode_2_teach_first'"))
                if "teaching_step" not in existing_cols:
                    sync_conn.execute(text("ALTER TABLE learning_sessions ADD COLUMN teaching_step VARCHAR(32) DEFAULT 'teach'"))
                if "current_subtopic" not in existing_cols:
                    sync_conn.execute(text("ALTER TABLE learning_sessions ADD COLUMN current_subtopic VARCHAR(128)"))
                if "doubt_state" not in existing_cols:
                    sync_conn.execute(text(f"ALTER TABLE learning_sessions ADD COLUMN doubt_state {json_col_type}"))
                if "pending_question" not in existing_cols:
                    sync_conn.execute(text(f"ALTER TABLE learning_sessions ADD COLUMN pending_question {json_col_type}"))
                if "awaiting" not in existing_cols:
                    sync_conn.execute(text("ALTER TABLE learning_sessions ADD COLUMN awaiting VARCHAR(32) DEFAULT 'none'"))
                if "teaching_step_index" not in existing_cols:
                    sync_conn.execute(text("ALTER TABLE learning_sessions ADD COLUMN teaching_step_index INTEGER DEFAULT 0"))
                if "last_tutor_message" not in existing_cols:
                    sync_conn.execute(text("ALTER TABLE learning_sessions ADD COLUMN last_tutor_message TEXT"))
                if "subtopic_mastery" not in existing_cols:
                    sync_conn.execute(text(f"ALTER TABLE learning_sessions ADD COLUMN subtopic_mastery {json_col_type}"))
                if "misconceptions_log" not in existing_cols:
                    sync_conn.execute(text(f"ALTER TABLE learning_sessions ADD COLUMN misconceptions_log {json_col_type}"))
                if "signals" not in existing_cols:
                    sync_conn.execute(text(f"ALTER TABLE learning_sessions ADD COLUMN signals {json_col_type}"))
                if "study_plan" not in existing_cols:
                    sync_conn.execute(text(f"ALTER TABLE learning_sessions ADD COLUMN study_plan {json_col_type}"))

        await conn.run_sync(migrate_columns)
    logger.info(f"✅ SAGE session tables verified/created on {_active_dialect}.")


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Async context manager for transactional database sessions."""
    global _session_factory
    if _session_factory is None:
        await get_or_create_engine()

    assert _session_factory is not None
    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def get_db_status() -> Dict[str, Any]:
    """Return live database connectivity metrics for health checks."""
    return {
        "connected": _db_connected,
        "dialect": _active_dialect,
        "mode": "production (PostgreSQL)" if _active_dialect == "postgresql" else "local (SQLite fallback)",
    }
