"""
Database Engine & Session Factory for SAGE.
Supports PostgreSQL (for production deployment on Render) and SQLite (for easy local development without Docker).
"""

import os
import logging
import asyncio
from pathlib import Path
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional, Dict, Any

from sqlalchemy import text
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

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_SQLITE_PATH = PROJECT_ROOT / "multi_agent_tutor" / "data" / "sage_sessions.db"
DEFAULT_SQLITE_URL = f"sqlite+aiosqlite:///{DEFAULT_SQLITE_PATH}"
DEFAULT_POSTGRES_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/sage_db"

_engine: Optional[AsyncEngine] = None
_engine_loop: Optional[asyncio.AbstractEventLoop] = None
_session_factory: Optional[async_sessionmaker[AsyncSession]] = None


def normalize_database_url(raw_url: Optional[str]) -> str:
    """
    Normalizes database URL. Supports PostgreSQL (Render production)
    and SQLite (local zero-setup development).
    """
    if not raw_url or not raw_url.strip():
        return DEFAULT_SQLITE_URL

    url = raw_url.strip()

    # Normalize standard postgres/postgresql URIs to asyncpg driver
    if url.startswith("postgres://"):
        url = "postgresql+asyncpg://" + url[len("postgres://"):]
    elif url.startswith("postgresql://") and not url.startswith("postgresql+asyncpg://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://"):]
    elif url.startswith("sqlite://") and not url.startswith("sqlite+aiosqlite://"):
        url = "sqlite+aiosqlite://" + url[len("sqlite://"):]

    return url


async def get_or_create_engine() -> AsyncEngine:
    """
    Initializes or returns the global SQLAlchemy AsyncEngine.
    If PostgreSQL is configured but fails to connect, gracefully falls back to local SQLite
    so that the app runs seamlessly without requiring Docker.
    """
    global _engine, _engine_loop, _session_factory

    current_loop = None
    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        pass

    if _engine is not None and (_engine_loop is current_loop or current_loop is None):
        return _engine

    if _engine is not None and current_loop is not None and _engine_loop is not current_loop:
        _engine = None
        _session_factory = None

    raw_url = os.getenv("DATABASE_URL")
    target_url = normalize_database_url(raw_url)

    engine_created = False

    try:
        if target_url.startswith("postgresql"):
            pg_engine = create_async_engine(
                target_url,
                pool_size=10,
                max_overflow=20,
                pool_pre_ping=True,
                pool_recycle=1800,
                echo=False,
            )
            async with pg_engine.connect() as conn:
                await conn.execute(text("SELECT 1;"))
            _engine = pg_engine
            logger.info("✅ Connected to PostgreSQL database successfully.")
        else:
            DEFAULT_SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
            sq_engine = create_async_engine(
                target_url,
                echo=False,
                connect_args={"timeout": 30.0},
            )
            async with sq_engine.connect() as conn:
                await conn.execute(text("SELECT 1;"))
            _engine = sq_engine
            logger.info(f"✅ Connected to local SQLite database: {target_url}")
        engine_created = True
    except Exception as e:
        logger.warning(
            f"⚠️ Could not connect to '{target_url}' ({e}). Falling back to local SQLite..."
        )

    if not engine_created:
        fallback_url = DEFAULT_SQLITE_URL
        DEFAULT_SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
        sq_engine = create_async_engine(
            fallback_url,
            echo=False,
            connect_args={"timeout": 30.0},
        )
        async with sq_engine.connect() as conn:
            await conn.execute(text("SELECT 1;"))
        _engine = sq_engine
        logger.info(f"✅ Successfully initialized local SQLite database: {fallback_url}")

    _engine_loop = current_loop
    _session_factory = async_sessionmaker(
        _engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    return _engine


async def init_db() -> None:
    """
    Initializes database tables automatically on startup.
    Works for both PostgreSQL and SQLite without requiring external migration tools.
    """
    engine = await get_or_create_engine()
    async with engine.begin() as conn:
        if engine.dialect.name == "sqlite":
            await conn.execute(text("PRAGMA journal_mode=WAL;"))
            await conn.execute(text("PRAGMA busy_timeout=30000;"))
        await conn.run_sync(Base.metadata.create_all)
        if engine.dialect.name == "postgresql":
            try:
                await conn.execute(
                    text("SELECT setval(pg_get_serial_sequence('bkt_logs', 'id'), COALESCE((SELECT MAX(id) FROM bkt_logs), 1));")
                )
            except Exception:
                pass
    logger.info(f"✅ SAGE database initialized successfully ({engine.dialect.name}).")


def get_db_status() -> Dict[str, Any]:
    """Returns database status and dialect name for health check."""
    return {
        "connected": _engine is not None,
        "dialect": _engine.dialect.name if _engine is not None else "disconnected",
    }


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Async context manager for transactional database sessions with automatic rollback on error."""
    global _session_factory
    await get_or_create_engine()

    assert _session_factory is not None
    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
