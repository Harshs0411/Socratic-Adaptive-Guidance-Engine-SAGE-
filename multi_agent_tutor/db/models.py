"""
SQLAlchemy 2.0 Data Models for SAGE Learning Session Persistence.
Strictly PostgreSQL-native architecture utilizing JSONB, composite indexes,
foreign key cascades, and normalized relational entities.
"""

from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from sqlalchemy import (
    String,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    Index,
    JSON,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# Native JSONB on PostgreSQL for high performance; standard JSON on SQLite for easy local dev
JSON_TYPE = JSON().with_variant(JSONB(), "postgresql")


class Base(DeclarativeBase):
    pass


class StudentModel(Base):
    """Authoritative student identity and account entity."""
    __tablename__ = "students"

    student_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    sessions: Mapped[List["LearningSessionModel"]] = relationship(
        "LearningSessionModel", back_populates="student", cascade="all, delete-orphan"
    )


class CurriculumModel(Base):
    """Authoritative reusable curriculum DAGs catalog per normalized topic."""
    __tablename__ = "curricula"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    topic: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_topic: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    concepts_dag: Mapped[List[Dict[str, Any]]] = mapped_column(JSON_TYPE, nullable=False)
    metadata_info: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON_TYPE, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    sessions: Mapped[List["LearningSessionModel"]] = relationship(
        "LearningSessionModel", back_populates="curriculum"
    )


class LearningSessionModel(Base):
    """
    Core metadata entity representing a single student's active or completed learning journey.
    Lightweight and fast to query; decoupled from heavy state payloads and chat messages.
    """
    __tablename__ = "learning_sessions"

    session_id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    student_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("students.student_id", ondelete="CASCADE"), index=True, default="student_001"
    )
    curriculum_id: Mapped[Optional[str]] = mapped_column(
        String(64), ForeignKey("curricula.id", ondelete="SET NULL"), nullable=True, index=True
    )
    topic: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    phase: Mapped[str] = mapped_column(String(32), default="diagnostic")  # diagnostic, teaching, graduated
    current_concept: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    current_subtopic: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    is_graduated: Mapped[bool] = mapped_column(Boolean, default=False)
    hake_gain: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    assessment_done: Mapped[bool] = mapped_column(Boolean, default=False)
    self_reported_level: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    teaching_mode: Mapped[str] = mapped_column(String(32), default="mode_2_teach_first")
    teaching_step: Mapped[str] = mapped_column(String(32), default="teach")
    teaching_step_index: Mapped[int] = mapped_column(Integer, default=0)
    awaiting: Mapped[str] = mapped_column(String(32), default="none")
    last_tutor_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    version_id: Mapped[int] = mapped_column(Integer, default=1)  # Optimistic concurrency control

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        index=True,
    )

    # Relationships
    student: Mapped["StudentModel"] = relationship("StudentModel", back_populates="sessions")
    curriculum: Mapped[Optional["CurriculumModel"]] = relationship("CurriculumModel", back_populates="sessions")
    state_record: Mapped[Optional["SessionStateModel"]] = relationship(
        "SessionStateModel", back_populates="session", uselist=False, cascade="all, delete-orphan"
    )
    concept_masteries: Mapped[List["ConceptMasteryModel"]] = relationship(
        "ConceptMasteryModel", back_populates="session", cascade="all, delete-orphan"
    )
    messages: Mapped[List["ChatMessageModel"]] = relationship(
        "ChatMessageModel",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ChatMessageModel.created_at",
    )
    bkt_logs: Mapped[List["BKTLogModel"]] = relationship(
        "BKTLogModel",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="BKTLogModel.created_at",
    )

    # Composite Indexes for Query Optimization
    __table_args__ = (
        Index("idx_sessions_student_updated", "student_id", "updated_at"),
        Index("idx_sessions_topic_active", "topic", "is_graduated"),
    )

    # Backward-compatible convenience properties
    @property
    def mastery_map(self) -> Dict[str, float]:
        return {m.concept_id: m.p_mastery for m in self.concept_masteries} if self.concept_masteries else {}

    @property
    def curriculum_data(self) -> Optional[List[Dict[str, Any]]]:
        return self.curriculum.concepts_dag if self.curriculum else None

    @property
    def state_snapshot(self) -> Optional[Dict[str, Any]]:
        return self.state_record.state_payload if self.state_record else None

    @property
    def doubt_state(self) -> Optional[Dict[str, Any]]:
        return self.state_record.doubt_state if self.state_record else None

    @property
    def pending_question(self) -> Optional[Dict[str, Any]]:
        return self.state_record.pending_question if self.state_record else None

    @property
    def subtopic_mastery(self) -> Optional[Dict[str, Any]]:
        return self.state_record.subtopic_mastery if self.state_record else None

    @property
    def misconceptions_log(self) -> Optional[List[Dict[str, Any]]]:
        return self.state_record.misconceptions_log if self.state_record else None

    @property
    def signals(self) -> Optional[Dict[str, Any]]:
        return self.state_record.signals if self.state_record else None

    @property
    def study_plan(self) -> Optional[Dict[str, Any]]:
        return self.state_record.study_plan if self.state_record else None


class SessionStateModel(Base):
    """
    Dedicated LangGraph state persistence entity.
    Isolated from session listings so that browsing sessions doesn't load megabytes of JSON.
    """
    __tablename__ = "session_states"

    session_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("learning_sessions.session_id", ondelete="CASCADE"), primary_key=True
    )
    state_payload: Mapped[Dict[str, Any]] = mapped_column(JSON_TYPE, nullable=False)
    doubt_state: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON_TYPE, nullable=True)
    pending_question: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON_TYPE, nullable=True)
    subtopic_mastery: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON_TYPE, nullable=True)
    misconceptions_log: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON_TYPE, nullable=True)
    signals: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON_TYPE, nullable=True)
    study_plan: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON_TYPE, nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    session: Mapped["LearningSessionModel"] = relationship("LearningSessionModel", back_populates="state_record")


class ConceptMasteryModel(Base):
    """
    Authoritative normalized current concept mastery per session.
    Provides fast relational lookups, aggregations, and eliminates duplicate sources of truth.
    """
    __tablename__ = "concept_mastery"

    session_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("learning_sessions.session_id", ondelete="CASCADE"), primary_key=True
    )
    concept_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    concept_name: Mapped[str] = mapped_column(String(255), nullable=False)
    p_mastery: Mapped[float] = mapped_column(Float, nullable=False)
    p_transit: Mapped[float] = mapped_column(Float, default=0.15)
    p_guess: Mapped[float] = mapped_column(Float, default=0.20)
    p_slip: Mapped[float] = mapped_column(Float, default=0.10)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    session: Mapped["LearningSessionModel"] = relationship("LearningSessionModel", back_populates="concept_masteries")

    __table_args__ = (
        Index("idx_concept_mastery_session", "session_id"),
    )


class ChatMessageModel(Base):
    """Individual user and assistant messages with citations and action metadata."""
    __tablename__ = "chat_messages"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("learning_sessions.session_id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user, assistant, system
    content: Mapped[str] = mapped_column(Text, nullable=False)
    question: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    action: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    metadata_info: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON_TYPE, nullable=True)
    rag_citations: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON_TYPE, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )

    session: Mapped["LearningSessionModel"] = relationship("LearningSessionModel", back_populates="messages")

    __table_args__ = (
        Index("idx_chat_messages_session_created", "session_id", "created_at"),
    )


class BKTLogModel(Base):
    """Historical append-only log of Bayesian Knowledge Tracing mastery observations."""
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

    __table_args__ = (
        Index("idx_bkt_logs_session_created", "session_id", "created_at"),
        Index("idx_bkt_logs_session_concept", "session_id", "concept_id"),
    )
