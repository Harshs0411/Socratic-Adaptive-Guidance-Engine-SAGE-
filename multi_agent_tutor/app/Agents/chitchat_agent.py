"""
Chitchat & Steer Agent for SAGE Tutor (Requirement 14).
Handles greetings, pleasantries, off-topic or social chatter warmly,
and gently steers back to learning without grading or breaking flow.
"""

from typing import Dict, Any
from multi_agent_tutor.app.graph.state import TutorState
from multi_agent_tutor.app.schemas.socratic import SocraticResponse


def chitchat_agent_node(state: TutorState) -> Dict[str, Any]:
    """
    LangGraph node: Kind social response that steers gently back to current learning.
    """
    pending_q = state.get("pending_question")
    topic = state.get("target_topic", "General")
    user_msg = (state.get("student_input") or "").strip().lower()

    q_text = ""
    if isinstance(pending_q, dict):
        q_text = pending_q.get("question", "")
    elif pending_q:
        q_text = str(pending_q)

    # Tailor greeting or thank you
    if any(w in user_msg for w in ["thank", "thx", "appreciate"]):
        greeting = "You're very welcome! I'm really glad to help you master this."
    elif any(w in user_msg for w in ["hi", "hello", "hey"]):
        greeting = f"Hello! Great to be working with you on {topic}."
    elif any(w in user_msg for w in ["who are you", "what are you"]):
        greeting = "I'm SAGE, your personal adaptive AI tutor! I'm here to help you truly understand each concept from first principles."
    else:
        greeting = f"I'm here with you! Let's keep exploring {topic}."

    if q_text:
        steer_msg = f"{greeting}\n\nWhenever you're ready, let's look back at our question:\n**{q_text}**"
    else:
        steer_msg = f"{greeting}\n\nShall we jump into our next topic in {topic}?"

    awaiting = "answer" if q_text else "continue"
    socratic_resp = SocraticResponse(
        message=steer_msg,
        question=q_text if q_text else "",
        action="initial",
        question_type="conceptual",
        expected_answer="Student response",
        evaluator_type="llm",
        evaluation_criteria=["Student acknowledges chitchat."],
    )

    return {
        "tutor_response": steer_msg,
        "socratic_response": socratic_resp,
        "awaiting": awaiting,
        "pending_question": pending_q if q_text else None,
        "student_input": None,
    }
