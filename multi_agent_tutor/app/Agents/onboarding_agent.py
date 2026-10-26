"""
Onboarding & First-Time Assessment Agent for SAGE Tutor (Requirement 1 & Part 1).
Handles:
1. Warm conversational onboarding greeting for new students.
2. Level detection: Beginner / Some knowledge / Comfortable.
3. Vague answer handling (asks ONE clarifying question, then defaults to Some knowledge).
4. Beginner path: ZERO test questions, all P(L)=0.0, pre-score 0, Topic 1 in Mode 2 (teach first).
5. Diagnostic path: Draws 1-2 questions per topic from curriculum question bank with early stopping.
6. Returning students: Skips onboarding, opens with one-line recap from stored state.
7. Mid-lesson level change: "actually I'm a beginner" resets priors to beginner.
"""

import re
from typing import Dict, Any, Optional, List, Tuple
from multi_agent_tutor.app.config import (
    DEFAULT_P_TRANSIT,
    DEFAULT_P_GUESS,
    DEFAULT_P_SLIP,
    DEFAULT_P_L0,
)
from multi_agent_tutor.app.graph.state import TutorState
from multi_agent_tutor.app.schemas.bkt import BKTState
from multi_agent_tutor.app.schemas.diagnostic import DiagnosticQuestion
from multi_agent_tutor.app.schemas.socratic import SocraticResponse
from multi_agent_tutor.app.curriculum_loader import load_rich_curriculum, load_curriculum_concepts
from multi_agent_tutor.app.Agents.learning_path_planner import build_learning_path


BEGINNER_KEYWORDS = {
    "beginner", "beginners", "new", "totally new", "completely new",
    "never learned", "scratch", "zero", "1", "start from scratch",
    "first time", "novice", "no knowledge", "none",
}

SOME_KNOWLEDGE_KEYWORDS = {
    "some knowledge", "some", "a bit", "basics", "basic",
    "intermediate", "2", "know some", "know the basics",
    "learned it before", "rusty",
}

COMFORTABLE_KEYWORDS = {
    "comfortable", "advanced", "expert", "confident",
    "3", "know it well", "ready", "deep", "proficient",
}

VAGUE_KEYWORDS = {
    "a little", "not sure", "maybe", "idk", "sort of",
    "kind of", "somewhat", "hard to say", "guess so",
}


def detect_student_level(message: str) -> Tuple[Optional[str], bool]:
    """
    Detects student level from message:
    Returns (level, is_vague):
    - ("beginner", False)
    - ("some_knowledge", False)
    - ("comfortable", False)
    - (None, True) if vague
    - (None, False) if completely unrelated
    """
    clean = message.lower().strip()
    norm = "".join(c for c in clean if c.isalnum() or c.isspace()).strip()

    # Direct match or exact number
    if norm in {"1", "beginner"}:
        return "beginner", False
    if norm in {"2", "some", "some knowledge"}:
        return "some_knowledge", False
    if norm in {"3", "comfortable", "advanced"}:
        return "comfortable", False

    # Check beginner
    if any(k in norm for k in ["beginner", "never", "scratch", "totally new", "completely new", "start from the basics"]):
        return "beginner", False

    # Check comfortable
    if any(k in norm for k in ["comfortable", "advanced", "expert", "confident", "know it well"]):
        return "comfortable", False

    # Check some knowledge
    if any(k in norm for k in ["some knowledge", "know some", "basics", "intermediate", "rusty"]):
        return "some_knowledge", False

    # Check vague
    if any(k in norm for k in VAGUE_KEYWORDS) or "a little" in norm:
        return None, True

    # Fallback substring checks
    if "some" in norm or "bit" in norm:
        return "some_knowledge", False

    return None, False


def is_level_change_to_beginner(message: str) -> bool:
    """Detects if student explicitly asks to switch to beginner mid-session."""
    clean = message.lower().strip()
    patterns = [
        r"\b(actually\s+(?:i'm|im|i\s+am)\s+a\s+beginner)\b",
        r"\b(switch\s+to\s+beginner)\b",
        r"\b(treat\s+me\s+as\s+a\s+beginner)\b",
        r"\b(start\s+from\s+scratch)\b",
        r"\b(i\s+don't\s+know\s+anything\s+about\s+this)\b",
    ]
    return any(re.search(p, clean) for p in patterns)


def get_onboarding_greeting(topic: str) -> str:
    """Generates the warm, conversational onboarding greeting."""
    return (
        f"👋 Welcome to SAGE! I'm your interactive tutor, and I'm excited to explore **{topic}** with you.\n\n"
        "To make sure our lessons are tailored to your pace, how would you describe your current experience with this topic?\n\n"
        "1. **Beginner**: Completely new (we'll start from scratch with step-by-step explanations, real-world analogies, and worked examples)\n"
        "2. **Some knowledge**: I know the basics, but want to strengthen my intuition and problem-solving\n"
        "3. **Comfortable**: Confident with core ideas, ready for tricky variants and deep algorithmic analysis\n\n"
        "*(You can click a button or just reply naturally!)*"
    )


def get_clarifying_question(topic: str) -> str:
    """Generates a single clarifying question for vague student replies."""
    return (
        f"No worries at all! Let me help calibrate: Have you ever implemented or traced a search algorithm in code before?\n\n"
        "- If you've never written or seen one, we can start right as a **Beginner**.\n"
        "- If you've seen the general idea before, we can start with **Some knowledge**.\n\n"
        "Which of those feels closer?"
    )


def build_bank_diagnostic_questions(topic: str, level: Optional[str] = None) -> List[DiagnosticQuestion]:
    """
    Draws 1-2 questions per topic from the curriculum question bank
    (tiers 1 & 2: recall and application) rather than calling an LLM.
    For 'comfortable' learners, prioritizes tier 2 questions first.
    """
    rich = load_rich_curriculum(topic)
    questions: List[DiagnosticQuestion] = []
    preferred_tiers = [2, 1] if level == "comfortable" else [1, 2]

    if rich and rich.topics:
        for topic_obj in rich.topics:
            t_id = topic_obj.topic_id
            t_title = topic_obj.title
            q_count = 0
            for tier in preferred_tiers:
                for subtopic in topic_obj.subtopics:
                    for q_item in subtopic.question_bank:
                        if q_item.difficulty_tier == tier:
                            q_type = q_item.question_type
                            if q_type not in ("conceptual", "objective", "application"):
                                if q_type in ("numeric", "multiple_choice"):
                                    q_type = "objective"
                                elif q_type in ("code", "implementation"):
                                    q_type = "application"
                                else:
                                    q_type = "conceptual"
                            questions.append(
                                DiagnosticQuestion(
                                    question_id=f"diag_{q_item.question_id}",
                                    concept=t_id,
                                    question=q_item.question,
                                    difficulty="beginner" if q_item.difficulty_tier == 1 else "intermediate",
                                    question_type=q_type,
                                    reason=f"Diagnostic check for {t_title}",
                                    evaluation_criteria=q_item.evaluation_criteria,
                                )
                            )
                            q_count += 1
                            if q_count >= 2:
                                break
                    if q_count >= 2:
                        break
                if q_count >= 2:
                    break
    return questions


def handle_beginner_onboarding(state: TutorState) -> Dict[str, Any]:
    """
    Initializes a beginner student (Requirement 1.A):
    - ZERO test questions asked.
    - P(L) = 0.0 for every topic in the curriculum.
    - P(T) > 0 so mastery can grow after the first correct answer.
    - pre_score for Hake's gain = 0.0.
    - Starts Topic 1 in Mode 2 (teach first).
    """
    topic = state.get("target_topic") or state.get("topic") or "General"
    curriculum = state.get("curriculum")
    if not curriculum:
        curriculum = load_curriculum_concepts(topic)
    if not curriculum:
        from multi_agent_tutor.app.Agents.curriculum_generator import curriculum_agent
        curr_res = curriculum_agent({"target_topic": topic, "depth_level": state.get("depth_level", "deep")})
        curriculum = curr_res.get("curriculum") or []

    mastery = {}
    bkt_states = {}
    subtopic_mastery = {}

    for concept in curriculum:
        cid = concept.concept_id
        mastery[cid] = 0.0
        bkt_states[cid] = BKTState(
            p_know=0.0,
            p_learn=DEFAULT_P_TRANSIT,
            p_guess=DEFAULT_P_GUESS,
            p_slip=DEFAULT_P_SLIP,
        )
        subtopic_mastery[cid] = {"p_know": 0.0, "correct_checks": 0}

    # First concept whose prerequisites are satisfied (Topic 1)
    first_concept = curriculum[0].concept_id if curriculum else None

    # Build initial learning path with P(L)=0
    planner_state = {
        "target_topic": topic,
        "curriculum": curriculum,
        "mastery": mastery,
        "skipped_concepts": [],
    }
    lp_res = build_learning_path(planner_state)

    welcome_msg = (
        f"Awesome! Welcome aboard to **{topic}** as a Beginner! 🚀\n\n"
        "We won't do any tests or diagnostics. We'll start straight away from the foundational concepts, "
        "using intuitive analogies, clear step-by-step explanations, and real-world worked examples.\n\n"
        "Feel free to ask any doubt at any point—there are no silly questions here!"
    )
    # FIX E: First message is Part 1 only (Intuition & Analogy)
    from multi_agent_tutor.app.Agents.teaching_agent import get_mode_2_step_content
    step0_content, _ = get_mode_2_step_content(topic, first_concept, 0) if first_concept else ("", False)
    full_first_message = f"{welcome_msg}\n\n---\n\n{step0_content}" if step0_content else welcome_msg

    return {
        "target_topic": topic,
        "curriculum_id": topic.lower().replace(" ", "_"),
        "curriculum": curriculum,
        "mastery": mastery,
        "bkt_states": bkt_states,
        "subtopic_mastery": subtopic_mastery,
        "assessment_done": True,
        "self_reported_level": "beginner",
        "diagnostic_state": {
            "completed": True,
            "questions": [],
            "current_question_id": None,
            "answers": {},
            "assessments": {},
        },
        "learning_path": lp_res["learning_path"],
        "current_concept": first_concept,
        "teaching_mode": "mode_2_teach_first",
        "teaching_step": "explain",
        "teaching_step_index": 0,
        "awaiting": "continue",
        "pending_question": None,
        "tutor_response": full_first_message,
        "teaching": {
            "current_action": "explain",
            "current_question": None,
            "attempt_count": 0,
            "correct_checks": 0,
            "has_transfer_correct": False,
            "misconception_history": [],
        },
        "signals": {
            "pre_score": 0.0,
            "hints_used": 0,
            "attempts": 0,
        },
    }
