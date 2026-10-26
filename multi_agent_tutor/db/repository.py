"""
Repository Layer for SAGE Learning Sessions.
Handles asynchronous CRUD operations, transaction boundaries,
and bi-directional serialization between LangGraph Pydantic state and PostgreSQL JSONB.
"""

from typing import Optional, Dict, Any, List
import logging
from sqlalchemy import select, delete, desc
from sqlalchemy.orm import selectinload

from multi_agent_tutor.db.database import get_db_session
from multi_agent_tutor.db.models import LearningSessionModel, ChatMessageModel, BKTLogModel

from multi_agent_tutor.app.schemas.curriculum import CurriculumConcept
from multi_agent_tutor.app.schemas.diagnostic import DiagnosticQuestion
from multi_agent_tutor.app.schemas.assessment import AssessmentResult
from multi_agent_tutor.app.schemas.learner import LearnerProfile
from multi_agent_tutor.app.schemas.learning_path import LearningPath
from multi_agent_tutor.app.schemas.teaching import TeachingDecision
from multi_agent_tutor.app.schemas.teaching_assessment import TeachingAssessment
from multi_agent_tutor.app.schemas.socratic import SocraticResponse
from multi_agent_tutor.app.schemas.critic import CriticOutput
from multi_agent_tutor.app.schemas.bkt import BKTState

logger = logging.getLogger("sage.repository")


def serialize_for_storage(obj: Any) -> Any:
    """Recursively converts Pydantic models, dicts, and collections into JSON-serializable primitives."""
    if obj is None:
        return None
    if hasattr(obj, "model_dump"):
        return serialize_for_storage(obj.model_dump())
    if hasattr(obj, "dict"):
        return serialize_for_storage(obj.dict())
    if isinstance(obj, dict):
        return {k: serialize_for_storage(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [serialize_for_storage(item) for item in obj]
    return obj


def rehydrate_state(raw_state: Dict[str, Any]) -> Dict[str, Any]:
    """Rehydrates JSON primitives back into typed Pydantic models required by LangGraph nodes."""
    if not raw_state:
        return {}

    state = dict(raw_state)

    # Rehydrate Curriculum
    if "curriculum" in state and state["curriculum"]:
        rehydrated_c = []
        for c in state["curriculum"]:
            try:
                rehydrated_c.append(CurriculumConcept(**c) if isinstance(c, dict) else c)
            except Exception as e:
                logger.debug(f"Could not rehydrate CurriculumConcept: {e}")
                rehydrated_c.append(c)
        state["curriculum"] = rehydrated_c

    # Rehydrate Diagnostic State
    diag = state.get("diagnostic_state")
    if isinstance(diag, dict):
        diag_copy = dict(diag)
        if "questions" in diag_copy and diag_copy["questions"]:
            rehydrated_q = []
            for q in diag_copy["questions"]:
                try:
                    rehydrated_q.append(DiagnosticQuestion(**q) if isinstance(q, dict) else q)
                except Exception:
                    rehydrated_q.append(q)
            diag_copy["questions"] = rehydrated_q

        if "assessments" in diag_copy and diag_copy["assessments"]:
            rehydrated_a = {}
            for qid, a in diag_copy["assessments"].items():
                try:
                    rehydrated_a[qid] = AssessmentResult(**a) if isinstance(a, dict) else a
                except Exception:
                    rehydrated_a[qid] = a
            diag_copy["assessments"] = rehydrated_a
        state["diagnostic_state"] = diag_copy

    # Rehydrate Learner Profile
    prof = state.get("learner_profile")
    if isinstance(prof, dict):
        try:
            state["learner_profile"] = LearnerProfile(**prof)
        except Exception:
            pass

    # Rehydrate Learning Path
    lp = state.get("learning_path")
    if isinstance(lp, dict):
        try:
            state["learning_path"] = LearningPath(**lp)
        except Exception:
            pass

    # Rehydrate Teaching Assessment
    ass = state.get("teaching_assessment")
    if isinstance(ass, dict):
        try:
            state["teaching_assessment"] = TeachingAssessment(**ass)
        except Exception:
            pass

    # Rehydrate Teaching Decision
    dec = state.get("teaching_decision")
    if isinstance(dec, dict):
        try:
            state["teaching_decision"] = TeachingDecision(**dec)
        except Exception:
            pass

    # Rehydrate Socratic Response
    resp = state.get("socratic_response")
    if isinstance(resp, dict):
        try:
            state["socratic_response"] = SocraticResponse(**resp)
        except Exception:
            pass

    # Rehydrate Critic Result
    crit = state.get("critic_result")
    if isinstance(crit, dict):
        try:
            state["critic_result"] = CriticOutput(**crit)
        except Exception:
            pass

    # Rehydrate BKT States
    bkt_states = state.get("bkt_states")
    if isinstance(bkt_states, dict):
        rehydrated_bkt = {}
        for cid, b in bkt_states.items():
            if isinstance(b, dict):
                try:
                    rehydrated_bkt[cid] = BKTState(**b)
                except Exception:
                    rehydrated_bkt[cid] = b
            else:
                rehydrated_bkt[cid] = b
        state["bkt_states"] = rehydrated_bkt

    # Rehydrate extended pedagogical fields: load stored values, default ONLY if missing (legacy sessions)
    if "doubt_state" in raw_state and isinstance(raw_state["doubt_state"], dict):
        state["doubt_state"] = raw_state["doubt_state"]
    else:
        state["doubt_state"] = {
            "doubt_stack": [],
            "doubt_log": [],
            "pending_clarity_check": False,
            "clarity_doubt_id": None,
            "active_doubt_response": None,
        }

    if "pending_question" in raw_state:
        state["pending_question"] = raw_state["pending_question"]
    else:
        current_q = state.get("teaching", {}).get("current_question") if isinstance(state.get("teaching"), dict) else None
        state["pending_question"] = {"question": current_q} if current_q else None

    # Fix 1: Explicit awaiting state (answer, clarity_check, continue, none)
    if "awaiting" in raw_state:
        state["awaiting"] = raw_state["awaiting"]
    else:
        state["awaiting"] = "clarity_check" if state.get("doubt_state", {}).get("pending_clarity_check") else ("answer" if state.get("pending_question") else "none")

    # Fix 3: Mode 2 teaching step chunk index (0: concept+analogy, 1: ex1, 2: ex2, 3: figure, 4: checks)
    state["teaching_step_index"] = raw_state.get("teaching_step_index", 0) or 0
    state["last_tutor_message"] = raw_state.get("last_tutor_message")
    state["debug_trace"] = raw_state.get("debug_trace", [])

    if "assessment_done" in raw_state:
        state["assessment_done"] = raw_state["assessment_done"]
    else:
        state["assessment_done"] = state.get("diagnostic_state", {}).get("completed", False) if isinstance(state.get("diagnostic_state"), dict) else False

    if "self_reported_level" in raw_state:
        state["self_reported_level"] = raw_state["self_reported_level"]
    else:
        state["self_reported_level"] = "some_knowledge" if state.get("assessment_done") else None

    if "teaching_mode" in raw_state:
        state["teaching_mode"] = raw_state["teaching_mode"]
    else:
        c = state.get("current_concept")
        c_mastery = state.get("mastery", {}).get(c, 0.0) if c else 0.0
        state["teaching_mode"] = "mode_1_qa" if c_mastery >= 0.65 else "mode_2_teach_first"

    if "teaching_step" in raw_state:
        state["teaching_step"] = raw_state["teaching_step"]
    else:
        state["teaching_step"] = "check" if state.get("teaching_mode") == "mode_1_qa" else "teach"

    if "current_subtopic" in raw_state:
        state["current_subtopic"] = raw_state["current_subtopic"]
    else:
        state["current_subtopic"] = None

    if "subtopic_mastery" in raw_state:
        state["subtopic_mastery"] = raw_state["subtopic_mastery"]
    else:
        state["subtopic_mastery"] = {}

    if "detected_intent" in raw_state:
        state["detected_intent"] = raw_state["detected_intent"]
    else:
        state["detected_intent"] = None

    if "misconceptions_log" in raw_state:
        state["misconceptions_log"] = raw_state["misconceptions_log"]
    else:
        state["misconceptions_log"] = []

    if "signals" in raw_state:
        state["signals"] = raw_state["signals"]
    else:
        state["signals"] = {"hints_used": 0, "attempts": 0, "response_time": 0.0, "stated_confidence": None}

    if "last_practice_time" in raw_state:
        state["last_practice_time"] = raw_state["last_practice_time"]
    else:
        state["last_practice_time"] = None

    if "study_plan" in raw_state:
        state["study_plan"] = raw_state["study_plan"]
    else:
        state["study_plan"] = None

    if "skipped_concepts" in raw_state:
        state["skipped_concepts"] = raw_state["skipped_concepts"]
    else:
        state["skipped_concepts"] = []

    # FIX A, B, G, H: Topic isolation, Question queue, Review queue, Transitions
    state["curriculum_id"] = raw_state.get("curriculum_id")
    state["asked_question_ids"] = list(raw_state.get("asked_question_ids", []))
    state["asked_question_texts"] = list(raw_state.get("asked_question_texts", []))
    state["question_attempts"] = dict(raw_state.get("question_attempts", {}))
    state["question_results"] = dict(raw_state.get("question_results", {}))
    state["concept_question_queue"] = dict(raw_state.get("concept_question_queue", {}))
    state["hint_level_per_question"] = dict(raw_state.get("hint_level_per_question", {}))
    state["review_queue"] = list(raw_state.get("review_queue", []))
    state["concept_transitions"] = list(raw_state.get("concept_transitions", []))

    return state


class SessionRepository:
    """Enterprise-grade async repository managing SAGE persistent learning sessions."""

    @staticmethod
    async def create_session(
        session_id: str,
        student_id: str,
        topic: str,
        state: Dict[str, Any],
        initial_message: Dict[str, Any],
        bkt_history: List[Dict[str, Any]],
    ) -> LearningSessionModel:
        """Saves a newly initialized learning session with its first diagnostic message."""
        async with get_db_session() as session:
            serialized_curriculum = serialize_for_storage(state.get("curriculum"))
            serialized_state = serialize_for_storage(state)

            db_session = LearningSessionModel(
                session_id=session_id,
                student_id=student_id,
                topic=topic,
                phase="diagnostic" if not state.get("diagnostic_state", {}).get("completed") else "teaching",
                current_concept=state.get("current_concept"),
                is_graduated=False,
                hake_gain=None,
                assessment_done=state.get("assessment_done", False),
                self_reported_level=state.get("self_reported_level"),
                teaching_mode=state.get("teaching_mode", "mode_2_teach_first"),
                teaching_step=state.get("teaching_step", "teach"),
                current_subtopic=state.get("current_subtopic"),
                doubt_state=serialize_for_storage(state.get("doubt_state")),
                pending_question=serialize_for_storage(state.get("pending_question")),
                awaiting=state.get("awaiting", "none"),
                teaching_step_index=state.get("teaching_step_index", 0),
                last_tutor_message=state.get("last_tutor_message"),
                subtopic_mastery=serialize_for_storage(state.get("subtopic_mastery")),
                misconceptions_log=serialize_for_storage(state.get("misconceptions_log")),
                signals=serialize_for_storage(state.get("signals")),
                study_plan=serialize_for_storage(state.get("study_plan")),
                curriculum_data=serialized_curriculum,
                mastery_map=state.get("mastery", {}),
                bkt_history=bkt_history,
                state_snapshot=serialized_state,
            )
            session.add(db_session)

            # Add initial greeting/diagnostic message
            db_msg = ChatMessageModel(
                id=initial_message.get("id", f"msg_{session_id}_0"),
                session_id=session_id,
                role=initial_message.get("role", "assistant"),
                content=initial_message.get("content", ""),
                question=initial_message.get("question"),
                action=initial_message.get("action", "diagnostic"),
                metadata_info=serialize_for_storage(initial_message.get("metadata")),
                rag_citations=serialize_for_storage(initial_message.get("rag_context")),
            )
            session.add(db_msg)
            await session.flush()
            logger.info(f"💾 Persisted new session '{session_id}' for topic '{topic}' to database.")
            return db_session

    @staticmethod
    async def get_session(session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a full session with complete message history and rehydrated state."""
        async with get_db_session() as session:
            stmt = (
                select(LearningSessionModel)
                .options(selectinload(LearningSessionModel.messages))
                .where(LearningSessionModel.session_id == session_id)
            )
            result = await session.execute(stmt)
            db_sess = result.scalar_one_or_none()

            if not db_sess:
                return None

            chat_history = [
                {
                    "id": m.id,
                    "role": m.role,
                    "content": m.content,
                    "question": m.question,
                    "action": m.action,
                    "metadata": m.metadata_info,
                    "rag_context": m.rag_citations,
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                }
                for m in db_sess.messages
            ]

            rehydrated = rehydrate_state(db_sess.state_snapshot or {})
            if db_sess.topic:
                if not rehydrated.get("target_topic"):
                    rehydrated["target_topic"] = db_sess.topic
                if not rehydrated.get("curriculum_id"):
                    rehydrated["curriculum_id"] = db_sess.topic.lower().replace(" ", "_")

            return {
                "session_id": db_sess.session_id,
                "student_id": db_sess.student_id,
                "topic": db_sess.topic,
                "phase": db_sess.phase,
                "current_concept": db_sess.current_concept,
                "is_graduated": db_sess.is_graduated,
                "hake_gain": db_sess.hake_gain,
                "state": rehydrated,
                "chat_history": chat_history,
                "bkt_history": db_sess.bkt_history or [],
                "mastery": db_sess.mastery_map or {},
            }

    @staticmethod
    async def update_session_turn(
        session_id: str,
        updated_state: Dict[str, Any],
        new_messages: List[Dict[str, Any]],
        bkt_history: List[Dict[str, Any]],
        is_graduated: bool = False,
        hake_gain: Optional[float] = None,
    ) -> None:
        """Appends new messages and updates the state snapshot transactionally."""
        async with get_db_session() as session:
            stmt = select(LearningSessionModel).where(LearningSessionModel.session_id == session_id)
            result = await session.execute(stmt)
            db_sess = result.scalar_one_or_none()

            if not db_sess:
                raise ValueError(f"Session {session_id} not found in database.")

            # Update session attributes
            diag_completed = updated_state.get("diagnostic_state", {}).get("completed", False)
            phase = "graduated" if is_graduated else ("teaching" if diag_completed else "diagnostic")

            db_sess.phase = phase
            db_sess.current_concept = updated_state.get("current_concept")
            db_sess.is_graduated = is_graduated
            if hake_gain is not None:
                db_sess.hake_gain = hake_gain
            db_sess.assessment_done = updated_state.get("assessment_done", False)
            db_sess.self_reported_level = updated_state.get("self_reported_level")
            db_sess.teaching_mode = updated_state.get("teaching_mode", "mode_2_teach_first")
            db_sess.teaching_step = updated_state.get("teaching_step", "teach")
            db_sess.current_subtopic = updated_state.get("current_subtopic")
            db_sess.doubt_state = serialize_for_storage(updated_state.get("doubt_state"))
            db_sess.pending_question = serialize_for_storage(updated_state.get("pending_question"))
            db_sess.awaiting = updated_state.get("awaiting", "none")
            db_sess.teaching_step_index = updated_state.get("teaching_step_index", 0)
            db_sess.last_tutor_message = updated_state.get("last_tutor_message")
            db_sess.subtopic_mastery = serialize_for_storage(updated_state.get("subtopic_mastery"))
            db_sess.misconceptions_log = serialize_for_storage(updated_state.get("misconceptions_log"))
            db_sess.signals = serialize_for_storage(updated_state.get("signals"))
            db_sess.study_plan = serialize_for_storage(updated_state.get("study_plan"))
            db_sess.mastery_map = updated_state.get("mastery", {})
            db_sess.bkt_history = bkt_history
            db_sess.state_snapshot = serialize_for_storage(updated_state)

            # Append new messages
            for msg in new_messages:
                db_msg = ChatMessageModel(
                    id=msg.get("id"),
                    session_id=session_id,
                    role=msg.get("role", "user"),
                    content=msg.get("content", ""),
                    question=msg.get("question"),
                    action=msg.get("action"),
                    metadata_info=serialize_for_storage(msg.get("metadata")),
                    rag_citations=serialize_for_storage(msg.get("rag_context")),
                )
                session.add(db_msg)

            # Log concept BKT mastery point
            c_id = updated_state.get("current_concept")
            if c_id and db_sess.mastery_map:
                p_know = db_sess.mastery_map.get(c_id, 0.0)
                bkt_log = BKTLogModel(
                    session_id=session_id,
                    concept_id=c_id,
                    concept_name=c_id.replace("_", " ").title(),
                    p_mastery=p_know,
                    action=new_messages[-1].get("action", "unknown") if new_messages else "turn",
                )
                session.add(bkt_log)

            await session.flush()
            logger.debug(f"💾 Updated session '{session_id}' in database.")

    @staticmethod
    async def delete_session(session_id: str) -> bool:
        """Deletes session and all associated messages and logs."""
        async with get_db_session() as session:
            stmt = select(LearningSessionModel).where(LearningSessionModel.session_id == session_id)
            result = await session.execute(stmt)
            db_sess = result.scalar_one_or_none()
            if db_sess:
                await session.delete(db_sess)
                return True
            return False

    @staticmethod
    async def list_student_sessions(student_id: str) -> List[Dict[str, Any]]:
        """Lists all previous sessions for a given student to support learning journey continuation."""
        async with get_db_session() as session:
            stmt = (
                select(LearningSessionModel)
                .options(selectinload(LearningSessionModel.messages))
                .where(LearningSessionModel.student_id == student_id)
                .order_by(desc(LearningSessionModel.updated_at))
            )
            result = await session.execute(stmt)
            sessions = result.scalars().all()

            return [
                {
                    "session_id": s.session_id,
                    "topic": s.topic,
                    "phase": s.phase,
                    "current_concept": s.current_concept,
                    "is_graduated": s.is_graduated,
                    "hake_gain": s.hake_gain,
                    "message_count": len(s.messages),
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                    "updated_at": s.updated_at.isoformat() if s.updated_at else None,
                }
                for s in sessions
            ]
