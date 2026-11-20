import os
import pytest
from datetime import datetime, timezone
from multi_agent_tutor.db.database import (
    normalize_database_url,
    get_db_status,
    get_or_create_engine,
)
from scripts.migrate_sqlite_to_postgres import parse_sqlite_datetime, parse_json_field
from multi_agent_tutor.db.models import LearningSessionModel, ChatMessageModel, BKTLogModel


def test_normalize_database_url():
    """Verify that PostgreSQL URLs are properly normalized to asyncpg for SQLAlchemy 2.0."""
    # Render default format: postgres://
    url1 = "postgres://user:pass@dpg-abc123-a.oregon-postgres.render.com/sage_db"
    norm1 = normalize_database_url(url1)
    assert norm1.startswith("postgresql+asyncpg://")

    # Standard format: postgresql://
    url2 = "postgresql://user:pass@localhost:5432/sage_db"
    norm2 = normalize_database_url(url2)
    assert norm2.startswith("postgresql+asyncpg://")

    # Already normalized: postgresql+asyncpg://
    url3 = "postgresql+asyncpg://user:pass@localhost:5432/sage_db"
    norm3 = normalize_database_url(url3)
    assert norm3 == url3

    # Empty / None defaults to SQLite
    assert "sqlite+aiosqlite" in normalize_database_url(None)
    assert "sqlite+aiosqlite" in normalize_database_url("")


def test_migration_datetime_parsing():
    """Verify that SQLite ISO timestamps are parsed into timezone-aware datetimes."""
    # Standard format
    dt1 = parse_sqlite_datetime("2026-11-20 05:33:50.070547")
    assert isinstance(dt1, datetime)
    assert dt1.tzinfo is not None

    # ISO with T
    dt2 = parse_sqlite_datetime("2026-11-20T14:30:00+00:00")
    assert isinstance(dt2, datetime)
    assert dt2.tzinfo is not None

    # None handling
    assert parse_sqlite_datetime(None) is None


def test_migration_json_parsing():
    """Verify JSON deserialization from SQLite text fields to Python primitives."""
    # JSON string
    raw_json = '{"automotive_history": 0.85, "engine": 0.5}'
    parsed = parse_json_field(raw_json)
    assert isinstance(parsed, dict)
    assert parsed["automotive_history"] == 0.85

    # Already a dict/list
    assert parse_json_field({"a": 1}) == {"a": 1}
    assert parse_json_field([1, 2, 3]) == [1, 2, 3]

    # None / Empty string
    assert parse_json_field(None) is None
    assert parse_json_field("") is None


def test_health_status_format():
    """Verify that get_db_status reports clean schema without exposing credentials."""
    status = get_db_status()
    assert "connected" in status
    assert "dialect" in status
    assert "mode" in status
    assert status["mode"] in ("production", "development")
    # Verify no credentials leaked
    assert "password" not in status
    assert "url" not in status
