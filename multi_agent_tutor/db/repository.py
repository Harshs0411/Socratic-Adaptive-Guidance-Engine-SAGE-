"""
Repository Layer for SAGE Learning Sessions.
PostgreSQL-optimized persistence engine with normalized relational entities,
instant O(1) curriculum reuse, aggregated message counting, and robust LangGraph state rehydration.
"""

import logging
from typing import Optional, Dict, Any, List
from sqlalchemy import select, desc, func
from sqlalchemy.orm import selectinload

from multi_agent_tutor.db.database import get_db_session
from multi_agent_tutor.db.models import (
    StudentModel,
    CurriculumModel,
    LearningSessionModel,
    SessionStateModel,
    ConceptMasteryModel,
    ChatMessageModel,
    BKTLogModel,
)

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
    if isinstance(obj, (list, tuple, set)):
        return [serialize_for_storage(item) for item in obj]
    return obj


def rehydrate_state(raw_state: Dict[str, Any]) -> Dict[str, Any]:
    """Rehydrates JSON primitives back into typed Pydantic models required by LangGraph nodes."""
    if not raw_state:
        return {}

    state = dict(raw_state)

    # 1. Rehydrate Curriculum
    if "curriculum" in state and state["curriculum"]:
        rehydrated_c = []
        for c in state["curriculum"]:
            try:
                rehydrated_c.append(CurriculumConcept(**c) if isinstance(c, dict) else c)
            except Exception as e:
                logger.debug(f"Could not rehydrate CurriculumConcept: {e}")
                rehydrated_c.append(c)
        state["curriculum"] = rehydrated_c

    # 2. Rehydrate Diagnostic State
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

    # 3. Rehydrate Learner Profile
    prof = state.get("learner_profile")
    if isinstance(prof, dict):
        try:
            state["learner_profile"] = LearnerProfile(**prof)
        except Exception:
            pass

    # 4. Rehydrate Learning Path
    lp = state.get("learning_path")
    if isinstance(lp, dict):
        try:
            state["learning_path"] = LearningPath(**lp)
        except Exception:
            pass

    # 5. Rehydrate Teaching Assessment
    ass = state.get("teaching_assessment")
    if isinstance(ass, dict):
        try:
            state["teaching_assessment"] = TeachingAssessment(**ass)
        except Exception:
            pass

    # 6. Rehydrate Teaching Decision
    dec = state.get("teaching_decision")
    if isinstance(dec, dict):
        try:
            state["teaching_decision"] = TeachingDecision(**dec)
        except Exception:
            pass

    # 7. Rehydrate Socratic Response
    resp = state.get("socratic_response")
    if isinstance(resp, dict):
        try:
            state["socratic_response"] = SocraticResponse(**resp)
        except Exception:
            pass

    # 8. Rehydrate Critic Result
    crit = state.get("critic_result")
    if isinstance(crit, dict):
        try:
            state["critic_result"] = CriticOutput(**crit)
        except Exception:
            pass

    # 9. Rehydrate BKT States
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

    # 10. Rehydrate Pedagogical Mode & Doubt Fields
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

    if "awaiting" in raw_state:
        state["awaiting"] = raw_state["awaiting"]
    else:
        state["awaiting"] = "clarity_check" if state.get("doubt_state", {}).get("pending_clarity_check") else ("answer" if state.get("pending_question") else "none")

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

    state["current_subtopic"] = raw_state.get("current_subtopic")
    state["subtopic_mastery"] = raw_state.get("subtopic_mastery", {})
    state["detected_intent"] = raw_state.get("detected_intent")
    state["misconceptions_log"] = raw_state.get("misconceptions_log", [])
    state["signals"] = raw_state.get("signals", {"hints_used": 0, "attempts": 0, "response_time": 0.0, "stated_confidence": None})
    state["last_practice_time"] = raw_state.get("last_practice_time")
    state["study_plan"] = raw_state.get("study_plan")
    state["skipped_concepts"] = raw_state.get("skipped_concepts", [])

    # Topic isolation, Question queue, Review queue, Transitions
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
    """Enterprise-grade async repository managing SAGE persistent learning sessions on PostgreSQL."""

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
        from multi_agent_tutor.app.Agents.curriculum_generator import normalize_topic_name

        async with get_db_session() as session:
            # 1. Ensure Student Record exists
            st_stmt = select(StudentModel).where(StudentModel.student_id == student_id)
            existing_student = (await session.execute(st_stmt)).scalar_one_or_none()
            if not existing_student:
                student_record = StudentModel(student_id=student_id)
                session.add(student_record)
                await session.flush()

            # 2. Check / Persist Reusable Curriculum
            curriculum_id: Optional[str] = None
            curr_data = state.get("curriculum")
            if curr_data:
                norm_topic = normalize_topic_name(topic)
                c_stmt = select(CurriculumModel).where(CurriculumModel.normalized_topic == norm_topic)
                curr_model = (await session.execute(c_stmt)).scalar_one_or_none()
                if not curr_model:
                    c_id = f"curr_{norm_topic}"
                    curr_model = CurriculumModel(
                        id=c_id,
                        topic=topic,
                        normalized_topic=norm_topic,
                        concepts_dag=serialize_for_storage(curr_data),
                    )
                    session.add(curr_model)
                    await session.flush()
                curriculum_id = curr_model.id

            # 3. Create Session Record
            diag_completed = state.get("diagnostic_state", {}).get("completed", False) if isinstance(state.get("diagnostic_state"), dict) else False
            phase = "teaching" if diag_completed else "diagnostic"

            db_session = LearningSessionModel(
                session_id=session_id,
                student_id=student_id,
                curriculum_id=curriculum_id,
                topic=topic,
                phase=phase,
                current_concept=state.get("current_concept"),
                current_subtopic=state.get("current_subtopic"),
                is_graduated=False,
                hake_gain=None,
                assessment_done=state.get("assessment_done", False),
                self_reported_level=state.get("self_reported_level"),
                teaching_mode=state.get("teaching_mode", "mode_2_teach_first"),
                teaching_step=state.get("teaching_step", "teach"),
                teaching_step_index=state.get("teaching_step_index", 0),
                awaiting=state.get("awaiting", "none"),
                last_tutor_message=state.get("last_tutor_message"),
                version_id=1,
            )
            session.add(db_session)

            # 4. Create Session State Record (for LangGraph resumption)
            state_record = SessionStateModel(
                session_id=session_id,
                state_payload=serialize_for_storage(state),
                doubt_state=serialize_for_storage(state.get("doubt_state")),
                pending_question=serialize_for_storage(state.get("pending_question")),
                subtopic_mastery=serialize_for_storage(state.get("subtopic_mastery")),
                misconceptions_log=serialize_for_storage(state.get("misconceptions_log")),
                signals=serialize_for_storage(state.get("signals")),
                study_plan=serialize_for_storage(state.get("study_plan")),
            )
            session.add(state_record)

            # 5. Populate Initial Concept Mastery
            mastery_dict = state.get("mastery", {})
            bkt_states_dict = state.get("bkt_states", {})
            for c_id, p_know in mastery_dict.items():
                bkt_obj = bkt_states_dict.get(c_id)
                pt = getattr(bkt_obj, "p_transit", 0.15) if bkt_obj else 0.15
                pg = getattr(bkt_obj, "p_guess", 0.20) if bkt_obj else 0.20
                ps = getattr(bkt_obj, "p_slip", 0.10) if bkt_obj else 0.10
                conf = getattr(bkt_obj, "confidence", None) if bkt_obj else None
                cm = ConceptMasteryModel(
                    session_id=session_id,
                    concept_id=c_id,
                    concept_name=c_id.replace("_", " ").title(),
                    p_mastery=float(p_know),
                    p_transit=float(pt),
                    p_guess=float(pg),
                    p_slip=float(ps),
                    confidence=float(conf) if conf is not None else None,
                )
                session.add(cm)

            # 6. Add Initial Greeting/Diagnostic Message
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

            # 7. Add Initial BKT Log if provided
            if bkt_history:
                for b_entry in bkt_history:
                    bkt_log = BKTLogModel(
                        session_id=session_id,
                        concept_id=b_entry.get("concept_id", "initial"),
                        concept_name=b_entry.get("concept_name", "Initial Assessment"),
                        p_mastery=float(b_entry.get("p_mastery", 0.0)),
                        action=b_entry.get("action", "diagnostic"),
                    )
                    session.add(bkt_log)

            await session.flush()
            logger.info(f"💾 Persisted new PostgreSQL session '{session_id}' for topic '{topic}'.")
            return db_session

    @staticmethod
    async def get_session(session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a full session with complete message history, concept mastery, and rehydrated state."""
        async with get_db_session() as session:
            stmt = (
                select(LearningSessionModel)
                .options(
                    selectinload(LearningSessionModel.curriculum),
                    selectinload(LearningSessionModel.state_record),
                    selectinload(LearningSessionModel.concept_masteries),
                    selectinload(LearningSessionModel.messages),
                    selectinload(LearningSessionModel.bkt_logs),
                )
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

            bkt_history = [
                {
                    "concept_id": b.concept_id,
                    "concept_name": b.concept_name,
                    "p_mastery": b.p_mastery,
                    "action": b.action,
                    "created_at": b.created_at.isoformat() if b.created_at else None,
                }
                for b in db_sess.bkt_logs
            ]

            mastery_map = {
                cm.concept_id: cm.p_mastery for cm in db_sess.concept_masteries
            }

            # State payload rehydration
            state_data = db_sess.state_record.state_payload if db_sess.state_record else {}
            rehydrated = rehydrate_state(state_data)

            # Ensure curriculum is populated from authoritative curriculum relation if missing in snapshot
            if db_sess.curriculum and (not rehydrated.get("curriculum") or len(rehydrated.get("curriculum", [])) == 0):
                rehydrated["curriculum"] = [
                    CurriculumConcept(**c) if isinstance(c, dict) else c
                    for c in db_sess.curriculum.concepts_dag
                ]

            if db_sess.topic:
                if not rehydrated.get("target_topic"):
                    rehydrated["target_topic"] = db_sess.topic
                if not rehydrated.get("curriculum_id"):
                    rehydrated["curriculum_id"] = db_sess.topic.lower().replace(" ", "_")

            # Ensure mastery in rehydrated state matches authoritative concept_masteries
            if mastery_map:
                rehydrated["mastery"] = dict(mastery_map)

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
                "bkt_history": bkt_history,
                "mastery": mastery_map,
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
        """Appends new messages and updates state and mastery transactionally with optimistic locking."""
        async with get_db_session() as session:
            stmt = (
                select(LearningSessionModel)
                .options(
                    selectinload(LearningSessionModel.state_record),
                    selectinload(LearningSessionModel.concept_masteries),
                )
                .where(LearningSessionModel.session_id == session_id)
            )
            result = await session.execute(stmt)
            db_sess = result.scalar_one_or_none()

            if not db_sess:
                raise ValueError(f"Session {session_id} not found in database.")

            # Update session attributes
            diag_completed = updated_state.get("diagnostic_state", {}).get("completed", False) if isinstance(updated_state.get("diagnostic_state"), dict) else False
            phase = "graduated" if is_graduated else ("teaching" if diag_completed else "diagnostic")

            db_sess.phase = phase
            db_sess.current_concept = updated_state.get("current_concept")
            db_sess.current_subtopic = updated_state.get("current_subtopic")
            db_sess.is_graduated = is_graduated
            if hake_gain is not None:
                db_sess.hake_gain = hake_gain
            db_sess.assessment_done = updated_state.get("assessment_done", False)
            db_sess.self_reported_level = updated_state.get("self_reported_level")
            db_sess.teaching_mode = updated_state.get("teaching_mode", "mode_2_teach_first")
            db_sess.teaching_step = updated_state.get("teaching_step", "teach")
            db_sess.teaching_step_index = updated_state.get("teaching_step_index", 0)
            db_sess.awaiting = updated_state.get("awaiting", "none")
            db_sess.last_tutor_message = updated_state.get("last_tutor_message")
            db_sess.version_id += 1

            # Update or create session_states record
            if not db_sess.state_record:
                db_sess.state_record = SessionStateModel(
                    session_id=session_id,
                    state_payload=serialize_for_storage(updated_state),
                )
                session.add(db_sess.state_record)

            db_sess.state_record.state_payload = serialize_for_storage(updated_state)
            db_sess.state_record.doubt_state = serialize_for_storage(updated_state.get("doubt_state"))
            db_sess.state_record.pending_question = serialize_for_storage(updated_state.get("pending_question"))
            db_sess.state_record.subtopic_mastery = serialize_for_storage(updated_state.get("subtopic_mastery"))
            db_sess.state_record.misconceptions_log = serialize_for_storage(updated_state.get("misconceptions_log"))
            db_sess.state_record.signals = serialize_for_storage(updated_state.get("signals"))
            db_sess.state_record.study_plan = serialize_for_storage(updated_state.get("study_plan"))

            # Upsert Authoritative Concept Mastery
            mastery_dict = updated_state.get("mastery", {})
            bkt_states_dict = updated_state.get("bkt_states", {})
            existing_masteries = {cm.concept_id: cm for cm in db_sess.concept_masteries}

            for c_id, p_know in mastery_dict.items():
                bkt_obj = bkt_states_dict.get(c_id)
                pt = getattr(bkt_obj, "p_transit", 0.15) if bkt_obj else 0.15
                pg = getattr(bkt_obj, "p_guess", 0.20) if bkt_obj else 0.20
                ps = getattr(bkt_obj, "p_slip", 0.10) if bkt_obj else 0.10
                conf = getattr(bkt_obj, "confidence", None) if bkt_obj else None

                if c_id in existing_masteries:
                    cm = existing_masteries[c_id]
                    cm.p_mastery = float(p_know)
                    cm.p_transit = float(pt)
                    cm.p_guess = float(pg)
                    cm.p_slip = float(ps)
                    if conf is not None:
                        cm.confidence = float(conf)
                else:
                    cm = ConceptMasteryModel(
                        session_id=session_id,
                        concept_id=c_id,
                        concept_name=c_id.replace("_", " ").title(),
                        p_mastery=float(p_know),
                        p_transit=float(pt),
                        p_guess=float(pg),
                        p_slip=float(ps),
                        confidence=float(conf) if conf is not None else None,
                    )
                    session.add(cm)

            # Append New Messages
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

            # Log Concept BKT Mastery Point
            c_id = updated_state.get("current_concept")
            if c_id and mastery_dict:
                p_know = mastery_dict.get(c_id, 0.0)
                bkt_log = BKTLogModel(
                    session_id=session_id,
                    concept_id=c_id,
                    concept_name=c_id.replace("_", " ").title(),
                    p_mastery=float(p_know),
                    action=new_messages[-1].get("action", "turn") if new_messages else "turn",
                )
                session.add(bkt_log)

            await session.flush()
            logger.debug(f"💾 Updated PostgreSQL session '{session_id}' in database.")

    @staticmethod
    async def delete_session(session_id: str) -> bool:
        """Deletes session and all associated records (cascaded via foreign keys)."""
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
        """
        Lists previous sessions for a student with high performance.
        Uses SQL aggregation for message counts; avoids loading full chat bodies into RAM.
        """
        async with get_db_session() as session:
            msg_subq = (
                select(
                    ChatMessageModel.session_id,
                    func.count(ChatMessageModel.id).label("message_count"),
                )
                .group_by(ChatMessageModel.session_id)
                .subquery()
            )

            stmt = (
                select(
                    LearningSessionModel,
                    func.coalesce(msg_subq.c.message_count, 0).label("message_count"),
                )
                .outerjoin(msg_subq, LearningSessionModel.session_id == msg_subq.c.session_id)
                .where(LearningSessionModel.student_id == student_id)
                .order_by(desc(LearningSessionModel.updated_at))
            )

            result = await session.execute(stmt)
            rows = result.all()

            return [
                {
                    "session_id": s.session_id,
                    "topic": s.topic,
                    "phase": s.phase,
                    "current_concept": s.current_concept,
                    "is_graduated": s.is_graduated,
                    "hake_gain": s.hake_gain,
                    "message_count": int(count),
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                    "updated_at": s.updated_at.isoformat() if s.updated_at else None,
                }
                for s, count in rows
            ]

    @staticmethod
    async def find_active_session(student_id: str, norm_topic: str) -> Optional[Dict[str, Any]]:
        """
        Finds active (not graduated) learning session for a student and normalized topic.
        Optimized to pick the session with the most learning progress.
        """
        from multi_agent_tutor.app.Agents.curriculum_generator import normalize_topic_name

        async with get_db_session() as session:
            stmt = (
                select(LearningSessionModel)
                .where(
                    LearningSessionModel.student_id == student_id,
                    LearningSessionModel.is_graduated == False,  # noqa: E712
                )
                .order_by(desc(LearningSessionModel.updated_at))
            )
            result = await session.execute(stmt)
            sessions = result.scalars().all()

            matching = [
                s for s in sessions
                if normalize_topic_name(s.topic) == norm_topic
            ]
            if not matching:
                return None

            return await SessionRepository.get_session(matching[0].session_id)

    @staticmethod
    async def find_curriculum_for_topic(norm_topic: str) -> Optional[List[Dict[str, Any]]]:
        """Searches curricula catalog with O(1) indexed lookup on normalized_topic."""
        async with get_db_session() as session:
            stmt = (
                select(CurriculumModel.concepts_dag)
                .where(CurriculumModel.normalized_topic == norm_topic)
                .limit(1)
            )
            result = await session.execute(stmt)
            dag = result.scalar_one_or_none()
            if dag:
                return dag
        return None

    @staticmethod
    async def save_curriculum(topic: str, concepts_dag: List[Dict[str, Any]], metadata: Optional[Dict[str, Any]] = None) -> CurriculumModel:
        """Stores or updates synthesized curriculum in the authoritative catalog."""
        from multi_agent_tutor.app.Agents.curriculum_generator import normalize_topic_name

        norm_topic = normalize_topic_name(topic)
        async with get_db_session() as session:
            stmt = select(CurriculumModel).where(CurriculumModel.normalized_topic == norm_topic)
            curr = (await session.execute(stmt)).scalar_one_or_none()
            if curr:
                curr.concepts_dag = serialize_for_storage(concepts_dag)
                if metadata:
                    curr.metadata_info = serialize_for_storage(metadata)
            else:
                curr = CurriculumModel(
                    id=f"curr_{norm_topic}",
                    topic=topic,
                    normalized_topic=norm_topic,
                    concepts_dag=serialize_for_storage(concepts_dag),
                    metadata_info=serialize_for_storage(metadata),
                )
                session.add(curr)
            await session.flush()
            return curr
