import os
import re
import sys
import uuid
import warnings
from typing import Dict, Any, List, Optional

warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from multi_agent_tutor.app.graph.workflow import master_graph
from multi_agent_tutor.app.rag.document_loader import (
    extract_text_from_bytes,
    ingest_text_content,
)
from multi_agent_tutor.db.database import init_db, get_db_status, get_or_create_engine
from multi_agent_tutor.db.repository import SessionRepository
from multi_agent_tutor.app.tools.code_runner import execute_code
from multi_agent_tutor.app.Agents.curriculum_generator import generate_sub_curriculum


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan managing database startup and connection pool lifecycle."""
    await init_db()
    yield


app = FastAPI(
    title="SAGE: Socratic AI Tutor API",
    description="Full-stack asynchronous multi-agent Socratic tutoring system with Continuous BKT and PostgreSQL Persistence.",
    version="2.1.0",
    lifespan=lifespan,
)

# Enable CORS for React frontend (Vite default: http://localhost:5173)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class StartSessionRequest(BaseModel):
    topic: str = Field(min_length=2, max_length=150, description="The subject or concept to learn")
    student_id: Optional[str] = Field(default="student_001")
    depth_level: Optional[str] = Field(default="deep", description="foundational, applied, or deep")
    self_reported_level: Optional[str] = Field(default=None, description="beginner, some_knowledge, comfortable")
    force_onboarding: Optional[bool] = Field(default=False, description="Explicitly ask level question on start")


class ChatRequest(BaseModel):
    session_id: str
    message: str = Field(min_length=1)


class RunCodeRequest(BaseModel):
    code: str = Field(min_length=1, description="Code content to compile and execute")
    language: str = Field(default="cpp", description="cpp or python")
    stdin_input: Optional[str] = Field(default="", description="Optional standard input")


class DrilldownRequest(BaseModel):
    session_id: str
    concept_id: str


class ResetSessionRequest(BaseModel):
    session_id: str


def _get(obj: Any, key: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def compute_topic_status(
    concept_id: str,
    score: float,
    is_active: bool,
    is_skipped: bool,
    is_done: bool,
    children_statuses: Optional[List[str]] = None,
) -> str:
    """
    Unified status function (Fix 6).
    - Done: rule met (score >= 0.85), OR all children are done.
    - In Progress: is_active is true.
    - Review: score > 0 (or was tested/taught) but not done and not active.
    - Pending: score == 0 AND not tested AND not active.
    - Skipped: student skipped it.
    - Parent status: roll up from children.
    """
    if is_skipped:
        return "skipped"

    # Parent rollup: if has children, done when all children are done
    if children_statuses and len(children_statuses) > 0:
        if all(s in ("mastered", "done") for s in children_statuses):
            return "mastered"
        if is_active or any(s in ("active", "in_progress") for s in children_statuses):
            return "active"
        if any(s in ("review", "mastered", "done") for s in children_statuses) or score > 0.0:
            return "review"
        return "pending"

    if is_done or score >= 0.85:
        return "mastered"
    if is_active:
        return "active"
    if score > 0.0:
        return "review"
    return "pending"


def sanitize_mermaid_label(label: str) -> str:
    cleaned = str(label).replace('"', "'").replace("(", "[").replace(")", "]")
    return cleaned


def generate_mermaid_dag(curriculum: list, active_concept: Optional[str], mastery_map: dict) -> str:
    if not curriculum:
        return ""

    lines = [
        "graph TD",
        "    classDef mastered fill:#10b981,stroke:#059669,stroke-width:2px,color:#fff;",
        "    classDef active fill:#3b82f6,stroke:#2563eb,stroke-width:3px,color:#fff;",
        "    classDef review fill:#f59e0b,stroke:#d97706,stroke-width:2px,color:#fff;",
        "    classDef pending fill:#6b7280,stroke:#4b5563,stroke-width:1px,color:#fff;",
    ]

    valid_ids = {_get(c, "concept_id", "") for c in curriculum}
    edges_added = set()
    has_explicit_edges = False

    for c in curriculum:
        c_id = _get(c, "concept_id", "")
        if not c_id:
            continue
        safe_id = re.sub(r"[^a-zA-Z0-9_]", "_", str(c_id))
        score = mastery_map.get(c_id, 0.0)
        pct = int(round(score * 100))

        if score >= 0.85:
            cls = "mastered"
        elif c_id == active_concept:
            cls = "active"
        elif score > 0.0:
            cls = "review"
        else:
            cls = "pending"

        clean_name = sanitize_mermaid_label(_get(c, "name", c_id))
        lines.append(f'    {safe_id}["{clean_name} ({pct}%)"]:::{cls}')

        pid = _get(c, "parent_id")
        if pid and pid in valid_ids:
            safe_p = re.sub(r"[^a-zA-Z0-9_]", "_", str(pid))
            edge = (safe_p, safe_id)
            if edge not in edges_added:
                lines.append(f"    {safe_p} --> {safe_id}")
                edges_added.add(edge)
                has_explicit_edges = True

        prereqs = _get(c, "prerequisites", []) or []
        for p in prereqs:
            if p in valid_ids and p != c_id:
                safe_p = re.sub(r"[^a-zA-Z0-9_]", "_", str(p))
                edge = (safe_p, safe_id)
                if edge not in edges_added:
                    lines.append(f"    {safe_p} --> {safe_id}")
                    edges_added.add(edge)
                    has_explicit_edges = True

    if not has_explicit_edges and len(curriculum) > 1:
        for i in range(len(curriculum) - 1):
            src_id = _get(curriculum[i], "concept_id", "")
            dst_id = _get(curriculum[i + 1], "concept_id", "")
            if src_id and dst_id:
                src = re.sub(r"[^a-zA-Z0-9_]", "_", str(src_id))
                dst = re.sub(r"[^a-zA-Z0-9_]", "_", str(dst_id))
                lines.append(f"    {src} --> {dst}")

    return "\n".join(lines)


def format_curriculum_nodes(curriculum: list, active_concept: Optional[str], mastery_map: dict, skipped_topics: Optional[list] = None) -> list:
    skipped_set = set(skipped_topics or [])

    # Map children by parent_id
    children_by_parent: Dict[str, list] = {}
    for c in (curriculum or []):
        pid = _get(c, "parent_id")
        if pid:
            children_by_parent.setdefault(pid, []).append(c)

    # Roll up parent mastery from children
    computed_mastery = dict(mastery_map)
    for c in (curriculum or []):
        cid = _get(c, "concept_id", "")
        if cid in children_by_parent:
            kids = children_by_parent[cid]
            kid_scores = [computed_mastery.get(_get(k, "concept_id", ""), 0.0) for k in kids]
            if kid_scores:
                computed_mastery[cid] = sum(kid_scores) / len(kid_scores)

    nodes = []
    for c in (curriculum or []):
        c_id = _get(c, "concept_id", "")
        score = computed_mastery.get(c_id, 0.0)
        c_status = _get(c, "status")
        is_skipped = (c_status == "skipped" or c_id in skipped_set)
        is_active = (c_id == active_concept)
        is_done = (c_status in ("mastered", "done") or score >= 0.85)

        children = children_by_parent.get(c_id, [])
        children_statuses = None
        if children:
            children_statuses = [
                compute_topic_status(
                    concept_id=_get(k, "concept_id", ""),
                    score=computed_mastery.get(_get(k, "concept_id", ""), 0.0),
                    is_active=(_get(k, "concept_id", "") == active_concept),
                    is_skipped=(_get(k, "concept_id", "") in skipped_set),
                    is_done=computed_mastery.get(_get(k, "concept_id", ""), 0.0) >= 0.85,
                )
                for k in children
            ]

        status = compute_topic_status(
            concept_id=c_id,
            score=score,
            is_active=is_active,
            is_skipped=is_skipped,
            is_done=is_done,
            children_statuses=children_statuses,
        )

        nodes.append({
            "concept_id": c_id,
            "name": _get(c, "name", c_id),
            "description": _get(c, "description", ""),
            "difficulty": _get(c, "difficulty", 1),
            "prerequisites": _get(c, "prerequisites", []),
            "parent_id": _get(c, "parent_id", None),
            "score": score,
            "status": status,
        })
    return nodes


def calculate_hake_gain(diag_assessments: dict, mastery_map: dict) -> dict:
    pre_scores = [
        getattr(a, "score", 0.20) if not isinstance(a, dict) else a.get("score", 0.20)
        for a in (diag_assessments or {}).values()
    ]
    pre = sum(pre_scores) / len(pre_scores) if pre_scores else 0.20
    post_scores = list(mastery_map.values()) if mastery_map else [0.95]
    post = sum(post_scores) / len(post_scores)

    if 1.0 - pre > 1e-4:
        g = (post - pre) / (1.0 - pre)
    else:
        g = 1.0
    g = min(max(g, 0.0), 1.0)
    label = "High Gain (Optimal Pedagogy) 🚀" if g >= 0.70 else ("Medium Gain" if g >= 0.30 else "Low Gain")
    return {
        "pre": pre,
        "post": post,
        "hake_g": round(g, 3),
        "label": label,
    }


@app.get("/api/health")
async def health_check():
    """Returns 200 OK without calling any LLM (Zero tokens) and reports database connectivity."""
    await get_or_create_engine()
    db_status = get_db_status()
    return {
        "status": "healthy",
        "service": "SAGE Socratic AI Tutor API",
        "database": db_status,
    }


@app.post("/api/session/start")
async def start_session(req: StartSessionRequest):
    """
    Zero-Token-Waste Entrypoint:
    Called ONLY after the user submits their chosen topic.
    Initializes state, runs curriculum synthesis and initial diagnostic question,
    then persists the entire session transactionally to PostgreSQL.
    """
    topic = req.topic.strip()
    session_id = str(uuid.uuid4())
    student_id = req.student_id or "student_001"

    # Step 1.5: RETURNING STUDENT check
    prev_sessions = await SessionRepository.list_student_sessions(student_id)
    matching_prev = [s for s in prev_sessions if s["topic"].lower() == topic.lower()]

    if matching_prev and not req.self_reported_level and not req.force_onboarding:
        last_s = await SessionRepository.get_session(matching_prev[0]["session_id"])
        if last_s and last_s.get("state"):
            state = dict(last_s["state"])
            created_str = matching_prev[0].get("updated_at") or matching_prev[0].get("created_at")
            from datetime import datetime, timezone
            days_elapsed = 0.0
            if created_str:
                try:
                    last_dt = datetime.fromisoformat(created_str)
                    now_dt = datetime.now(timezone.utc)
                    if last_dt.tzinfo is None:
                        last_dt = last_dt.replace(tzinfo=timezone.utc)
                    days_elapsed = max(0.0, (now_dt - last_dt).total_seconds() / 86400.0)
                except Exception:
                    days_elapsed = 0.0

            # Apply forgetting decay only if >= 1 day has passed
            from multi_agent_tutor.app.utils.bkt import apply_forgetting
            if days_elapsed >= 1.0:
                mastery_map = dict(state.get("mastery") or {})
                for cid, p in mastery_map.items():
                    mastery_map[cid] = apply_forgetting(p, days_elapsed)
                state["mastery"] = mastery_map
                for cid, bkt in (state.get("bkt_states") or {}).items():
                    if isinstance(bkt, dict):
                        bkt["p_know"] = mastery_map.get(cid, bkt.get("p_know", 0.20))
                    elif hasattr(bkt, "p_know"):
                        bkt.p_know = mastery_map.get(cid, bkt.p_know)

            curr_c = state.get("current_concept") or "binary_search_fundamentals"
            curriculum_list = state.get("curriculum") or []
            curr_title = curr_c.replace("_", " ").title()
            for c in curriculum_list:
                if _get(c, "concept_id") == curr_c:
                    curr_title = _get(c, "name", curr_title)
                    break

            curr_p = int(round(state.get("mastery", {}).get(curr_c, 0.85) * 100))
            recap_msg = (
                f"👋 Welcome back! Last time we finished work on **{curr_title}** "
                f"and reached {curr_p}% mastery. Ready to pick up right where we left off, "
                f"or would you like a 2-minute refresher?"
            )
            state["tutor_response"] = recap_msg
            state["assessment_done"] = True
            if "diagnostic_state" in state and isinstance(state["diagnostic_state"], dict):
                state["diagnostic_state"]["completed"] = True

            curriculum = state.get("curriculum") or []
            mastery_map = state.get("mastery", {})
            active_concept = state.get("current_concept")
            chat_history = [
                {
                    "id": str(uuid.uuid4()),
                    "role": "assistant",
                    "content": recap_msg,
                    "question": None,
                    "action": "resume",
                    "metadata": None,
                    "rag_context": None,
                }
            ]
            bkt_history = []
            if curriculum:
                bkt_history.append({
                    "turn": 0,
                    "mastery": {_get(c, "name", _get(c, "concept_id", "")): round(mastery_map.get(_get(c, "concept_id", ""), 0.0) * 100, 1) for c in curriculum}
                })

            await SessionRepository.create_session(
                session_id=session_id,
                student_id=student_id,
                topic=topic,
                state=state,
                initial_message=chat_history[0],
                bkt_history=bkt_history,
            )

            return {
                "session_id": session_id,
                "topic": topic,
                "chat_history": chat_history,
                "curriculum": format_curriculum_nodes(curriculum, active_concept, mastery_map, state.get("skipped_topics", [])),
                "mermaid_dag": generate_mermaid_dag(curriculum, active_concept, mastery_map),
                "mastery": mastery_map,
                "active_concept": active_concept,
                "depth_level": state.get("depth_level", "deep"),
                "phase": "teaching",
                "teaching_mode": state.get("teaching_mode", "mode_2_teach_first"),
                "doubts_asked": len(state.get("doubt_state", {}).get("doubt_log", [])),
                "visuals": state.get("signals", {}).get("visuals") or state.get("visuals") or [],
            }

    initial_state = {
        "student_id": student_id,
        "target_topic": topic,
        "messages": [],
        "student_input": None,
        "curriculum": None,
        "diagnostic_state": {
            "completed": False,
            "questions": [],
            "current_question_id": None,
            "answers": {},
            "assessments": {},
        },
        "learner_profile": None,
        "mastery": {},
        "bkt_states": {},
        "learning_path": None,
        "current_concept": None,
        "teaching": {
            "current_action": "initial",
            "current_question": None,
            "attempt_count": 0,
            "misconception_history": [],
            "current_objective": None,
            "concept_completed": False,
        },
        "teaching_assessment": None,
        "teaching_decision": None,
        "socratic_response": None,
        "tutor_response": None,
        "critic_result": None,
        "retry_count": 0,
        "misconceptions": [],
        "hint_level": 0,
        "rag_context": None,
        "depth_level": req.depth_level or "deep",
        "assessment_done": False,
        "self_reported_level": req.self_reported_level,
        "teaching_mode": "mode_2_teach_first",
        "teaching_step": "teach",
        "pending_question": None,
        "current_subtopic": None,
        "subtopic_mastery": {},
        "detected_intent": None,
        "doubt_state": {
            "doubt_stack": [],
            "doubt_log": [],
            "pending_clarity_check": False,
            "clarity_doubt_id": None,
            "active_doubt_response": None,
        },
        "misconceptions_log": [],
        "signals": {
            "hints_used": 0,
            "attempts": 0,
            "response_time": 0.0,
            "stated_confidence": None,
        },
        "last_practice_time": None,
        "study_plan": None,
        "skipped_concepts": [],
    }

    # Step 1.A: BEGINNER
    if req.self_reported_level == "beginner":
        from multi_agent_tutor.app.Agents.onboarding_agent import handle_beginner_onboarding
        state = handle_beginner_onboarding(initial_state)

    # Step 1: FIRST VISIT LEVEL QUESTION
    elif req.force_onboarding or (not req.self_reported_level and student_id.startswith("new_")):
        from multi_agent_tutor.app.Agents.onboarding_agent import get_onboarding_greeting
        greeting = get_onboarding_greeting(topic)
        initial_state["onboarding_step"] = "awaiting_level"
        initial_state["pending_question"] = {
            "question_id": "onboarding_level",
            "question": greeting,
            "concept": "onboarding",
        }
        initial_state["tutor_response"] = greeting
        state = initial_state

    # Step 1.B: "I KNOW SOME" / "COMFORTABLE" / DEFAULT
    else:
        state = master_graph.invoke(initial_state)

    resp = state.get("socratic_response")
    initial_text = state.get("tutor_response", f"Welcome to SAGE! Let's begin learning {topic}.")
    awaiting_status = state.get("awaiting") or ("answer" if not state.get("diagnostic_state", {}).get("completed") and state.get("pending_question") else "none")
    initial_question = getattr(resp, "question", None) if resp else None
    if awaiting_status != "answer":
        initial_question = None

    chat_history = [
        {
            "id": str(uuid.uuid4()),
            "role": "assistant",
            "content": initial_text,
            "question": initial_question,
            "awaiting": awaiting_status,
            "action": "diagnostic" if not state.get("diagnostic_state", {}).get("completed") else "initial",
            "metadata": None,
            "rag_context": state.get("rag_context"),
        }
    ]

    curriculum = state.get("curriculum") or []
    mastery_map = state.get("mastery", {})
    active_concept = state.get("current_concept")

    # Record initial BKT snapshot
    bkt_history = []
    if curriculum:
        bkt_history.append({
            "turn": 0,
            "mastery": {_get(c, "name", _get(c, "concept_id", "")): round(mastery_map.get(_get(c, "concept_id", ""), 0.0) * 100, 1) for c in curriculum}
        })

    # Persist new session transactionally to PostgreSQL / SQLite
    await SessionRepository.create_session(
        session_id=session_id,
        student_id=req.student_id or "student_001",
        topic=topic,
        state=state,
        initial_message=chat_history[0],
        bkt_history=bkt_history,
    )

    return {
        "session_id": session_id,
        "topic": topic,
        "chat_history": chat_history,
        "latest_message": chat_history[0],
        "curriculum": format_curriculum_nodes(curriculum, active_concept, mastery_map, state.get("skipped_topics", [])),
        "mermaid_dag": generate_mermaid_dag(curriculum, active_concept, mastery_map),
        "mastery": mastery_map,
        "active_concept": active_concept,
        "depth_level": state.get("depth_level", "deep"),
        "phase": "diagnostic" if not state.get("diagnostic_state", {}).get("completed") else "teaching",
        "teaching_mode": state.get("teaching_mode", "mode_2_teach_first"),
        "doubts_asked": len(state.get("doubt_state", {}).get("doubt_log", [])),
        "visuals": state.get("signals", {}).get("visuals") or state.get("visuals") or [],
    }


@app.post("/api/chat")
async def handle_chat(req: ChatRequest):
    """
    Submits student response, advances multi-agent state graph, and returns Socratic guidance.
    Persists updated state, conversation history, and BKT logs to PostgreSQL.
    """
    session = await SessionRepository.get_session(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found. Please start a new session.")

    state = session["state"]
    chat_history = session["chat_history"]
    bkt_history = session["bkt_history"]

    user_msg = req.message.strip()
    user_msg_obj = {
        "id": str(uuid.uuid4()),
        "role": "user",
        "content": user_msg,
    }
    chat_history.append(user_msg_obj)

    # 1. Mid-lesson switch: "actually I'm a beginner"
    from multi_agent_tutor.app.Agents.onboarding_agent import (
        is_level_change_to_beginner,
        detect_student_level,
        get_clarifying_question,
        handle_beginner_onboarding,
    )

    if is_level_change_to_beginner(user_msg):
        confirm_msg = (
            "Got it! Resetting your journey to the **Beginner** path right now. 🚀\n"
            "We'll skip all quiz questions and start fresh with intuitive analogies, "
            "step-by-step explanations, and concrete worked examples.\n\n"
        )
        updated_state = handle_beginner_onboarding(state)
        updated_state["tutor_response"] = confirm_msg + updated_state["tutor_response"]

    # 2. Onboarding step awaiting level response
    elif state.get("onboarding_step") in ("awaiting_level", "awaiting_clarification"):
        detected_lvl, is_vague = detect_student_level(user_msg)
        if detected_lvl == "beginner":
            updated_state = handle_beginner_onboarding(state)
            updated_state.pop("onboarding_step", None)
        elif detected_lvl in ("some_knowledge", "comfortable"):
            state["self_reported_level"] = detected_lvl
            state.pop("onboarding_step", None)
            state["student_input"] = None
            state["messages"].append({"role": "user", "content": user_msg})
            updated_state = master_graph.invoke(state)
        elif is_vague:
            if state.get("onboarding_step") == "awaiting_level":
                clarify_q = get_clarifying_question(state.get("target_topic", "Binary Search"))
                updated_state = dict(state)
                updated_state["onboarding_step"] = "awaiting_clarification"
                updated_state["tutor_response"] = clarify_q
                updated_state["pending_question"] = {
                    "question_id": "onboarding_clarify",
                    "question": clarify_q,
                    "concept": "onboarding",
                }
            else:
                # Default to some knowledge on second vague answer
                state["self_reported_level"] = "some_knowledge"
                state.pop("onboarding_step", None)
                state["student_input"] = None
                state["messages"].append({"role": "user", "content": user_msg})
                updated_state = master_graph.invoke(state)
        else:
            clarify_q = get_clarifying_question(state.get("target_topic", "Binary Search"))
            updated_state = dict(state)
            updated_state["onboarding_step"] = "awaiting_clarification"
            updated_state["tutor_response"] = clarify_q
            updated_state["pending_question"] = {
                "question_id": "onboarding_clarify",
                "question": clarify_q,
                "concept": "onboarding",
            }

    # 3. Standard chat message
    else:
        state["student_input"] = user_msg
        state["retry_count"] = 0
        state["critic_result"] = None
        updated_state = master_graph.invoke(state)

    # Gather assessment metadata
    meta = {}
    ass = updated_state.get("teaching_assessment")
    if ass:
        meta["score"] = _get(ass, "score")
        meta["understanding"] = _get(ass, "understanding")
        meta["misconceptions"] = _get(ass, "misconceptions", [])
        c = updated_state.get("current_concept")
        if c:
            meta["p_know"] = updated_state.get("mastery", {}).get(c, 0.0)

    crit = updated_state.get("critic_result")
    if crit:
        meta["critic"] = {
            "passed": _get(crit, "passed", True),
            "score": _get(crit, "score", 10),
            "feedback": _get(crit, "feedback", ""),
        }

    resp = updated_state.get("socratic_response")
    msg_text = _get(resp, "message") if resp else updated_state.get("tutor_response", "Thank you.")
    awaiting_status = updated_state.get("awaiting") or "none"
    q_text = _get(resp, "question") if resp else None
    action = _get(resp, "action", "info") if resp else "info"

    # Fix 1: The 'GUIDING SOCRATIC QUESTION:' label and message question appear ONLY when awaiting == "answer"
    if awaiting_status != "answer":
        q_text = None

    # Loop guard check: never emit identical message twice
    last_tutor_msg = state.get("last_tutor_message") or ""
    loop_guard_fired = False
    if last_tutor_msg and msg_text.strip() == last_tutor_msg.strip():
        import logging
        logging.getLogger(__name__).warning("LOOP GUARD FIRED: identical tutor message detected. Advancing state.")
        loop_guard_fired = True
        if updated_state.get("teaching_mode") == "mode_2_teach_first":
            curr_s = updated_state.get("teaching_step_index", 0) or 0
            if curr_s < 3:
                from multi_agent_tutor.app.Agents.teaching_agent import get_mode_2_step_content
                next_s = curr_s + 1
                s_topic = updated_state.get("target_topic") or updated_state.get("curriculum_id") or "General"
                step_c, _ = get_mode_2_step_content(s_topic, updated_state.get("current_concept", ""), next_s)
                msg_text = step_c
                updated_state["teaching_step_index"] = next_s
                updated_state["awaiting"] = "continue"
                updated_state["pending_question"] = None
                q_text = None
            else:
                from multi_agent_tutor.app.Agents.teaching_agent import select_check_question
                s_topic = updated_state.get("target_topic") or updated_state.get("curriculum_id") or "General"
                s_concept = updated_state.get("current_concept", "")
                asked_ids = list(updated_state.get("asked_question_ids") or [])
                asked_texts = list(updated_state.get("asked_question_texts") or [])
                cq = select_check_question(s_topic, s_concept, correct_checks=0, asked_question_ids=asked_ids, asked_question_texts=asked_texts)
                if cq:
                    asked_ids.append(cq["question_id"])
                    asked_texts.append(cq["question"])
                    updated_state["asked_question_ids"] = asked_ids
                    updated_state["asked_question_texts"] = asked_texts
                    msg_text = f"Let's move into our check question:\n\n**Question:** {cq['question']}"
                    q_text = cq["question"]
                    updated_state["awaiting"] = "answer"
                    updated_state["pending_question"] = cq
                    updated_state["teaching_step_index"] = 4

    # HARD TOPIC ISOLATION GUARD (Fix A)
    norm_topic = (updated_state.get("target_topic") or "").lower().replace(" ", "_")
    forbidden_map = {
        "recursion": ["binary search", "sorted array", "low + high", "mid = "],
        "osi_model": ["binary search", "sorted array", "base case", "call stack"],
    }
    forbidden = forbidden_map.get(norm_topic, [])
    found_forbidden = [w for w in forbidden if w in msg_text.lower()]
    if found_forbidden:
        import logging
        logging.getLogger(__name__).error(f"CONTAMINATION DETECTED: {found_forbidden} found in tutor message for topic {norm_topic}. Regenerating.")
        from multi_agent_tutor.app.Agents.teaching_agent import get_mode_2_step_content
        safe_c, _ = get_mode_2_step_content(updated_state.get("target_topic", norm_topic), updated_state.get("current_concept", ""), 0)
        msg_text = safe_c
        q_text = None
        updated_state["awaiting"] = "continue"
        updated_state["pending_question"] = None

    asst_msg = {
        "id": str(uuid.uuid4()),
        "role": "assistant",
        "content": msg_text,
        "question": q_text,
        "awaiting": updated_state.get("awaiting"),
        "action": action,
        "metadata": meta if meta else None,
        "rag_context": updated_state.get("rag_context"),
    }
    chat_history.append(asst_msg)
    updated_state["last_tutor_message"] = msg_text

    # Record Debug Trace entry
    c_active = updated_state.get("current_concept")
    trace_entry = {
        "turn": len(chat_history),
        "student_input": user_msg,
        "awaiting_before": state.get("awaiting"),
        "awaiting_after": updated_state.get("awaiting"),
        "detected_intent": (updated_state.get("detected_intent") or {}).get("intent"),
        "graded": bool(ass or (updated_state.get("diagnostic_state", {}).get("assessments") and user_msg in str(updated_state.get("diagnostic_state", {}).get("answers", {})))),
        "score": meta.get("score"),
        "bkt_before": state.get("mastery", {}).get(c_active, 0.0) if c_active else 0.0,
        "bkt_after": updated_state.get("mastery", {}).get(c_active, 0.0) if c_active else 0.0,
        "step_index": updated_state.get("teaching_step_index"),
        "loop_guard_fired": loop_guard_fired,
    }
    d_trace = list(updated_state.get("debug_trace") or [])
    d_trace.append(trace_entry)
    updated_state["debug_trace"] = d_trace

    # Update BKT history
    curriculum = updated_state.get("curriculum") or []
    mastery_map = updated_state.get("mastery", {})
    active_concept = updated_state.get("current_concept")

    if curriculum:
        bkt_history.append({
            "turn": len(bkt_history),
            "mastery": {_get(c, "name", _get(c, "concept_id", "")): round(mastery_map.get(_get(c, "concept_id", ""), 0.0) * 100, 1) for c in curriculum}
        })

    # Check graduation
    lp = updated_state.get("learning_path")
    is_graduated = lp is not None and getattr(lp, "completed", False)
    hake_data = None
    if is_graduated:
        diag = updated_state.get("diagnostic_state", {})
        hake_data = calculate_hake_gain(diag.get("assessments", {}), mastery_map)

    is_diag = not updated_state.get("diagnostic_state", {}).get("completed", False)
    phase = "graduated" if is_graduated else ("diagnostic" if is_diag else "teaching")

    # Persist updated turn transactionally to PostgreSQL / SQLite
    await SessionRepository.update_session_turn(
        session_id=req.session_id,
        updated_state=updated_state,
        new_messages=[user_msg_obj, asst_msg],
        bkt_history=bkt_history,
        is_graduated=is_graduated,
        hake_gain=hake_data.get("hake_g") if hake_data else None,
    )

    return {
        "session_id": req.session_id,
        "chat_history": chat_history,
        "latest_message": asst_msg,
        "curriculum": format_curriculum_nodes(curriculum, active_concept, mastery_map, updated_state.get("skipped_topics", [])),
        "mermaid_dag": generate_mermaid_dag(curriculum, active_concept, mastery_map),
        "mastery": mastery_map,
        "active_concept": active_concept,
        "phase": phase,
        "is_graduated": is_graduated,
        "hake_gain": hake_data,
        "bkt_history": bkt_history,
        "teaching_mode": updated_state.get("teaching_mode", "mode_2_teach_first"),
        "doubts_asked": len(updated_state.get("doubt_state", {}).get("doubt_log", [])),
        "visuals": updated_state.get("signals", {}).get("visuals") or updated_state.get("visuals") or [],
        "review_queue": updated_state.get("review_queue") or [],
        "concept_transitions": updated_state.get("concept_transitions") or [],
    }


@app.get("/api/session/{session_id}")
async def get_session(session_id: str):
    session = await SessionRepository.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    state = session["state"]
    curriculum = state.get("curriculum") or []
    mastery_map = session.get("mastery", {}) or state.get("mastery", {})
    active_concept = session.get("current_concept") or state.get("current_concept")
    lp = state.get("learning_path")
    is_graduated = session.get("is_graduated", False) or (lp is not None and getattr(lp, "completed", False))
    hake_data = None
    if is_graduated:
        diag = state.get("diagnostic_state", {})
        hake_data = calculate_hake_gain(diag.get("assessments", {}), mastery_map)

    is_diag = not state.get("diagnostic_state", {}).get("completed", False)
    phase = "graduated" if is_graduated else ("diagnostic" if is_diag else "teaching")

    return {
        "session_id": session_id,
        "topic": session.get("topic", "General"),
        "chat_history": session["chat_history"],
        "curriculum": format_curriculum_nodes(curriculum, active_concept, mastery_map),
        "mermaid_dag": generate_mermaid_dag(curriculum, active_concept, mastery_map),
        "mastery": mastery_map,
        "active_concept": active_concept,
        "phase": phase,
        "is_graduated": is_graduated,
        "hake_gain": hake_data,
        "bkt_history": session["bkt_history"],
        "teaching_mode": state.get("teaching_mode", "mode_2_teach_first"),
        "doubts_asked": len(state.get("doubt_state", {}).get("doubt_log", [])),
        "visuals": state.get("signals", {}).get("visuals") or state.get("visuals") or [],
        "review_queue": state.get("review_queue") or [],
        "concept_transitions": state.get("concept_transitions") or [],
    }


@app.get("/api/sessions/student/{student_id}")
async def list_student_sessions(student_id: str):
    """
    Returns all learning journeys recorded for a student across all topics.
    Allows resuming any past session directly from the frontend.
    """
    student_sessions = await SessionRepository.list_student_sessions(student_id)
    return {"student_id": student_id, "sessions": student_sessions}


@app.post("/api/documents/upload")
async def upload_document(
    session_id: str = Form(...),
    file: UploadFile = File(...),
):
    session = await SessionRepository.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    topic = session.get("topic", "General")
    file_bytes = await file.read()
    filename = file.filename or "uploaded_notes.txt"

    try:
        text = extract_text_from_bytes(file_bytes, filename)
        count = ingest_text_content(text=text, topic=topic, source_name=filename)
        return {
            "success": True,
            "filename": filename,
            "chunks_added": count,
            "topic": topic,
            "message": f"Successfully indexed {count} chunks from '{filename}' into ChromaDB for '{topic}'."
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/code/run")
async def run_code(req: RunCodeRequest):
    """
    Sandboxed compilation and execution service for C++20 and Python 3.
    Enforces a strict 5.0s timeout and output limits.
    """
    return execute_code(
        code=req.code,
        language=req.language,
        stdin_input=req.stdin_input or "",
    )


def normalize_concept_text(text: str) -> str:
    cleaned = text.lower().strip()
    cleaned = re.sub(r"\b(the|of\s+the|a|an|in|and|for)\b", " ", cleaned)
    cleaned = re.sub(r"[^a-z0-9\s]", "", cleaned)
    return " ".join(cleaned.split())


def is_duplicate_concept(candidate_name: str, candidate_id: str, existing_concepts: list) -> bool:
    norm_cand_name = normalize_concept_text(candidate_name)
    norm_cand_id = normalize_concept_text(candidate_id.replace("_", " "))
    cand_words = set(norm_cand_name.split())

    for ec in existing_concepts:
        ec_id = getattr(ec, "concept_id", "") if hasattr(ec, "concept_id") else ec.get("concept_id", "")
        ec_name = getattr(ec, "name", "") if hasattr(ec, "name") else ec.get("name", "")
        norm_ec_name = normalize_concept_text(ec_name)
        norm_ec_id = normalize_concept_text(ec_id.replace("_", " "))

        if ec_id == candidate_id or norm_cand_name == norm_ec_name or norm_cand_id == norm_ec_id:
            return True
        ec_words = set(norm_ec_name.split())
        if cand_words and ec_words:
            overlap = len(cand_words & ec_words) / max(len(cand_words), len(ec_words))
            if overlap >= 0.8:
                return True
    return False


@app.post("/api/session/drilldown")
async def drilldown_concept(req: DrilldownRequest):
    """
    Dynamically decomposes any concept in the curriculum into a focused sub-curriculum DAG,
    enabling deep-dive exploration of sub-facets without losing global session state.
    """
    session = await SessionRepository.get_session(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    state = session["state"]
    curriculum = state.get("curriculum", [])
    topic = session.get("topic", "General")
    depth = state.get("depth_level") or "deep"

    target_concept = None
    target_idx = -1
    for idx, c in enumerate(curriculum):
        c_id = getattr(c, "concept_id", "") if hasattr(c, "concept_id") else (c.get("concept_id") if isinstance(c, dict) else "")
        if c_id == req.concept_id:
            target_concept = c
            target_idx = idx
            break

    if not target_concept:
        raise HTTPException(status_code=404, detail=f"Concept '{req.concept_id}' not found in curriculum.")

    # Depth limit 1: Reject if parent_id is set
    target_pid = getattr(target_concept, "parent_id", None) or (target_concept.get("parent_id") if isinstance(target_concept, dict) else None)
    if target_pid:
        raise HTTPException(status_code=400, detail="Maximum depth reached")

    c_name = getattr(target_concept, "name", "") if hasattr(target_concept, "name") else target_concept.get("name", req.concept_id)

    # Generate sub-curriculum
    sub_concepts = generate_sub_curriculum(
        parent_topic=topic,
        concept_name=c_name,
        concept_id=req.concept_id,
        depth_level=depth,
    )

    valid_new_children = []
    for sc in sub_concepts:
        if not is_duplicate_concept(sc.name, sc.concept_id, curriculum):
            sc.parent_id = req.concept_id
            valid_new_children.append(sc)
            if len(valid_new_children) >= 5:
                break

    updated_curriculum = list(curriculum[:target_idx + 1]) + valid_new_children + list(curriculum[target_idx + 1:])
    state["curriculum"] = updated_curriculum

    from multi_agent_tutor.app.schemas.bkt import BKTState
    mastery_map = state.get("mastery", {})
    bkt_states = state.get("bkt_states", {})
    for sc in valid_new_children:
        mastery_map[sc.concept_id] = 0.0
        bkt_states[sc.concept_id] = BKTState(p_know=0.0)

    state["mastery"] = mastery_map
    state["bkt_states"] = bkt_states

    first_sub = valid_new_children[0].concept_id if valid_new_children else req.concept_id
    first_sub_name = valid_new_children[0].name if valid_new_children else c_name

    # Start first child in Mode 2 step 0 (Intuition & Analogy)
    from multi_agent_tutor.app.Agents.teaching_agent import get_mode_2_step_content
    step0_content, _ = get_mode_2_step_content(topic, first_sub, 0)
    sub_list_str = "\n".join([f"- **{sc.name}**: {sc.description}" for sc in valid_new_children])
    drill_text = (
        f"🔬 **Deep-Dive Activated**: Drilling down into **{c_name}** with {len(valid_new_children)} specialized sub-milestones:\n"
        f"{sub_list_str}\n\n---\n\n"
        f"{step0_content}"
    )

    drill_msg = {
        "id": str(uuid.uuid4()),
        "role": "assistant",
        "content": drill_text,
        "question": None,
        "awaiting": "continue",
        "action": "drilldown",
        "metadata": None,
        "rag_context": None,
    }

    state["current_concept"] = first_sub
    state["teaching_mode"] = "mode_2_teach_first"
    state["teaching_step"] = "teach"
    state["teaching_step_index"] = 0
    state["awaiting"] = "continue"
    state["pending_question"] = None
    state["last_tutor_message"] = drill_text
    state["teaching"]["concept_completed"] = False
    state["teaching"]["current_action"] = "explain"
    state["teaching"]["current_question"] = None
    state["teaching"]["current_objective"] = f"Master foundational mechanics of {first_sub_name}"

    chat_history = session.get("chat_history", [])
    chat_history.append(drill_msg)

    # Persist updated turn
    await SessionRepository.update_session_turn(
        session_id=req.session_id,
        updated_state=state,
        new_messages=[drill_msg],
        bkt_history=session.get("bkt_history", []),
        is_graduated=False,
    )

    return {
        "success": True,
        "session_id": req.session_id,
        "curriculum": format_curriculum_nodes(updated_curriculum, first_sub, mastery_map),
        "mermaid_dag": generate_mermaid_dag(updated_curriculum, first_sub, mastery_map),
        "mastery": mastery_map,
        "active_concept": first_sub,
        "sub_concepts_added": [sc.name for sc in valid_new_children],
        "latest_message": drill_msg,
        "chat_history": chat_history,
        "message": f"Successfully expanded '{c_name}' into {len(valid_new_children)} deep sub-facets.",
    }


@app.post("/api/session/reset")
async def reset_session(req: ResetSessionRequest):
    deleted = await SessionRepository.delete_session(req.session_id)
    return {"success": True, "message": f"Session {req.session_id} reset."}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
