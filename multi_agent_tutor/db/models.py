"""
SQLAlchemy 2.0 Data Models for SAGE Learning Session Persistence.
Supports PostgreSQL (with JSONB) and SQLite (with JSON) transparently.
"""

from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from sqlalchemy import String, Float, Boolean, DateTime, ForeignKey, Integer, Text, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# Cross-dialect JSON: uses native JSONB on PostgreSQL for indexing, JSON on SQLite
JSON_TYPE = JSON().with_variant(JSONB, "postgresql")


class Base(DeclarativeBase):
    pass


class LearningSessionModel(Base):
    __tablename__ = "learning_sessions"

    session_id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    student_id: Mapped[str] = mapped_column(String(64), index=True, default="student_001")
    topic: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    phase: Mapped[str] = mapped_column(String(32), default="diagnostic")  # diagnostic, teaching, graduated
    current_concept: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    is_graduated: Mapped[bool] = mapped_column(Boolean, default=False)
    hake_gain: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    assessment_done: Mapped[Optional[bool]] = mapped_column(Boolean, default=False, nullable=True)
    self_reported_level: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    teaching_mode: Mapped[Optional[str]] = mapped_column(String(32), default="mode_2_teach_first", nullable=True)
    teaching_step: Mapped[Optional[str]] = mapped_column(String(32), default="teach", nullable=True)
    current_subtopic: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    # Explicit JSON Columns for Extended State
    doubt_state: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON_TYPE, nullable=True)
    pending_question: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON_TYPE, nullable=True)
    awaiting: Mapped[Optional[str]] = mapped_column(String(32), default="none", nullable=True)
    teaching_step_index: Mapped[Optional[int]] = mapped_column(Integer, default=0, nullable=True)
    last_tutor_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    subtopic_mastery: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON_TYPE, nullable=True)
    misconceptions_log: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON_TYPE, nullable=True)
    signals: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON_TYPE, nullable=True)
    study_plan: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON_TYPE, nullable=True)

    # Rich State JSONB Columns
    curriculum_data: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON_TYPE, nullable=True)
    mastery_map: Mapped[Optional[Dict[str, float]]] = mapped_column(JSON_TYPE, nullable=True)
    bkt_history: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON_TYPE, nullable=True)
    state_snapshot: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON_TYPE, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    messages: Mapped[List["ChatMessageModel"]] = relationship(
        "ChatMessageModel", back_populates="session", cascade="all, delete-orphan", order_by="ChatMessageModel.created_at"
    )
    bkt_logs: Mapped[List["BKTLogModel"]] = relationship(
        "BKTLogModel", back_populates="session", cascade="all, delete-orphan", order_by="BKTLogModel.created_at"
    )


class ChatMessageModel(Base):
    __tablename__ = "chat_messages"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("learning_sessions.session_id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user, assistant, system
    content: Mapped[str] = mapped_column(Text, nullable=False)
    question: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    action: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    # Metadata & Citations (JSONB)
    metadata_info: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON_TYPE, nullable=True)
    rag_citations: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON_TYPE, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )

    session: Mapped["LearningSessionModel"] = relationship("LearningSessionModel", back_populates="messages")


class BKTLogModel(Base):
    __tablename__ = "bkt_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("learning_sessions.session_id", ondelete="CASCADE"), index=True
    )
    concept_id: Mapped[str] = mapped_column(String(128), nullable=False)
    concept_name: Mapped[str] = mapped_column(String(255), nullable=False)
    p_mastery: Mapped[float] = mapped_column(Float, nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )

    session: Mapped["LearningSessionModel"] = relationship("LearningSessionModel", back_populates="bkt_logs")

