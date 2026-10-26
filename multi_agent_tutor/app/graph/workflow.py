from langgraph.graph import StateGraph, START, END
from multi_agent_tutor.app.graph.state import TutorState

# Agent imports
from multi_agent_tutor.app.Agents.curriculum_generator import curriculum_agent
from multi_agent_tutor.app.Agents.diagnostic import diagnostic_agent
from multi_agent_tutor.app.Agents.question_presenter import present_diagnostic_question
from multi_agent_tutor.app.Agents.assessment import assessment_agent
from multi_agent_tutor.app.Agents.next_question_shifting_id import advance_diagnostic
from multi_agent_tutor.app.Agents.learner import build_learner_profile
from multi_agent_tutor.app.Agents.bkt_intializer import initialize_bkt_states
from multi_agent_tutor.app.Agents.learning_path_planner import build_learning_path
from multi_agent_tutor.app.Agents.tutor import sage_agent
from multi_agent_tutor.app.Agents.critic import critic_agent
from multi_agent_tutor.app.Agents.teaching_assessor import assess_teaching_response
from multi_agent_tutor.app.Agents.mastery_updater import update_mastery
from multi_agent_tutor.app.Agents.teaching_controller import teaching_controller
from multi_agent_tutor.app.Agents.concept_advancer import advance_concept

# Intent and Non-Interviewer Agents (Requirement 3 & 5)
from multi_agent_tutor.app.Agents.intent_classifier import intent_classifier_node
from multi_agent_tutor.app.Agents.doubt_agent import doubt_agent_node
from multi_agent_tutor.app.Agents.meta_agent import meta_agent_node
from multi_agent_tutor.app.Agents.chitchat_agent import chitchat_agent_node


def route_start(state: TutorState) -> str:
    """
    Master entry router:
    If student sent input, route directly to the Intent Classifier first!
    Otherwise, directs to Curriculum Generation, Diagnostic Assessment,
    Transition/Planning, or the Socratic Teaching loop.
    """
    # 0. If the student provided input, classify intent first!
    if state.get("student_input"):
        return "intent_classifier"

    # 1. Check if curriculum is already complete
    lp = state.get("learning_path")
    if lp is not None and getattr(lp, "completed", False):
        return END

    # 2. Check if curriculum needs to be generated for the topic
    if not state.get("curriculum"):
        return "curriculum_generator"

    # 3. Diagnostic Phase Check
    diag = state.get("diagnostic_state", {})
    if not diag.get("completed", False):
        if not diag.get("questions"):
            return "diagnostic"
        return "present_diagnostic"

    # 4. Teaching Phase Check
    # If diagnostic is done but learning path is not yet planned
    if state.get("learning_path") is None:
        return "learner_model"

    # Default teaching step: generate or present SAGE question
    return "sage"


def route_after_intent(state: TutorState) -> str:
    """
    Pedagogical Intent Router (Requirement 3):
    Routes non-answer messages to dedicated agents that NEVER touch BKT:
    - DOUBT -> doubt_agent
    - CONFIRMATION -> doubt_agent (if pending clarity check) or chitchat_agent
    - META -> meta_agent
    - CHITCHAT -> chitchat_agent
    - ANSWER_ATTEMPT -> assess_diagnostic or assess_teaching
    """
    intent_data = state.get("detected_intent") or {}
    intent = intent_data.get("intent", "DOUBT")
    doubt_state = state.get("doubt_state") or {}
    pending_clarity = doubt_state.get("pending_clarity_check", False)
    awaiting = state.get("awaiting") or ("clarity_check" if pending_clarity else ("answer" if state.get("pending_question") else "none"))

    if intent == "DOUBT":
        return "doubt_agent"

    if intent == "CONFIRMATION":
        if awaiting == "clarity_check" or pending_clarity:
            return "doubt_agent"
        # In all teaching and continue states, confirmation advances the lesson via sage
        return "sage"

    if intent == "META":
        return "meta_agent"

    if intent == "CHITCHAT":
        return "chitchat_agent"

    if intent == "ANSWER_ATTEMPT":
        diag = state.get("diagnostic_state", {})
        if not diag.get("completed", False):
            return "assess_diagnostic"
        return "assess_teaching"

    # Default safe fallback: doubt_agent (never grade)
    return "doubt_agent"


def route_after_advance_diag(state: TutorState) -> str:
    """
    After advancing diagnostic questions:
    If diagnostic just finished, transition to learner modeling & planning.
    Otherwise, present the next diagnostic question to the student.
    """
    if state.get("diagnostic_state", {}).get("completed", False):
        return "learner_model"
    return "present_diagnostic"


def route_after_controller(state: TutorState) -> str:
    """
    Route based on the teaching controller's decision:
    If 'advance', advance the concept.
    Otherwise continue Socratic dialogue on the current concept.
    """
    decision = state.get("teaching_decision")
    if decision is not None and decision.action == "advance":
        return "advance_concept"
    return "sage"


def route_after_advancing_concept(state: TutorState) -> str:
    """
    After concept advancement:
    If the curriculum is completed, terminate.
    Otherwise generate the initial question for the new concept.
    """
    lp = state.get("learning_path")
    if lp is not None and getattr(lp, "completed", False):
        return END
    return "sage"


def route_after_critic(state: TutorState) -> str:
    """
    Safety & Quality Gate:
    If the critic passes the tutor response, present it to the student (END).
    If it fails and retries remain, regenerate the question with SAGE.
    """
    critic_result = state.get("critic_result")
    retries = state.get("retry_count", 0)

    if critic_result and getattr(critic_result, "passed", True):
        return END

    # Allow at most 1 retry (2 attempts total) so API responses stay fast (<10s)
    # Note: State mutation must happen inside node functions, not conditional edge routers.
    if retries <= 1:
        return "sage"

    return END


def build_master_graph() -> StateGraph:
    """
    Construct the unified multi-agent SAGE tutor StateGraph.
    """
    builder = StateGraph(TutorState)

    # ------------------------------------------------------------------
    # Nodes: Curriculum & Diagnostic
    # ------------------------------------------------------------------
    builder.add_node("curriculum_generator", curriculum_agent)
    builder.add_node("diagnostic", diagnostic_agent)
    builder.add_node("present_diagnostic", present_diagnostic_question)
    builder.add_node("assess_diagnostic", assessment_agent)
    builder.add_node("advance_diagnostic", advance_diagnostic)
    builder.add_node("learner_model", build_learner_profile)
    builder.add_node("bkt_init", initialize_bkt_states)
    builder.add_node("plan_path", build_learning_path)

    # ------------------------------------------------------------------
    # Nodes: Intent Detection & Doubt Flow (Requirement 3 & 5)
    # ------------------------------------------------------------------
    builder.add_node("intent_classifier", intent_classifier_node)
    builder.add_node("doubt_agent", doubt_agent_node)
    builder.add_node("meta_agent", meta_agent_node)
    builder.add_node("chitchat_agent", chitchat_agent_node)

    # ------------------------------------------------------------------
    # Nodes: Socratic Teaching Loop
    # ------------------------------------------------------------------
    builder.add_node("sage", sage_agent)
    builder.add_node("critic", critic_agent)
    builder.add_node("assess_teaching", assess_teaching_response)
    builder.add_node("update_mastery", update_mastery)
    builder.add_node("controller", teaching_controller)
    builder.add_node("advance_concept", advance_concept)

    # ------------------------------------------------------------------
    # Master Entry Point
    # ------------------------------------------------------------------
    builder.add_conditional_edges(
        START,
        route_start,
        {
            "intent_classifier": "intent_classifier",
            "curriculum_generator": "curriculum_generator",
            "diagnostic": "diagnostic",
            "present_diagnostic": "present_diagnostic",
            "learner_model": "learner_model",
            "sage": "sage",
            END: END,
        },
    )

    # ------------------------------------------------------------------
    # Intent Classification Routing
    # ------------------------------------------------------------------
    builder.add_conditional_edges(
        "intent_classifier",
        route_after_intent,
        {
            "doubt_agent": "doubt_agent",
            "meta_agent": "meta_agent",
            "chitchat_agent": "chitchat_agent",
            "assess_diagnostic": "assess_diagnostic",
            "assess_teaching": "assess_teaching",
            "sage": "sage",
        },
    )
    builder.add_edge("doubt_agent", END)
    builder.add_edge("meta_agent", END)
    builder.add_edge("chitchat_agent", END)

    # ------------------------------------------------------------------
    # Curriculum -> Diagnostic Flow
    # ------------------------------------------------------------------
    builder.add_edge("curriculum_generator", "diagnostic")
    builder.add_edge("diagnostic", "present_diagnostic")
    builder.add_edge("present_diagnostic", END)

    builder.add_edge("assess_diagnostic", "advance_diagnostic")
    builder.add_conditional_edges(
        "advance_diagnostic",
        route_after_advance_diag,
        {
            "present_diagnostic": "present_diagnostic",
            "learner_model": "learner_model",
        },
    )

    # ------------------------------------------------------------------
    # Transition: Diagnostic -> Learner Model -> BKT -> Learning Path
    # ------------------------------------------------------------------
    builder.add_edge("learner_model", "bkt_init")
    builder.add_edge("bkt_init", "plan_path")
    builder.add_edge("plan_path", "sage")

    # ------------------------------------------------------------------
    # Teaching Flow
    # ------------------------------------------------------------------
    builder.add_edge("assess_teaching", "update_mastery")
    builder.add_edge("update_mastery", "controller")

    builder.add_conditional_edges(
        "controller",
        route_after_controller,
        {
            "sage": "sage",
            "advance_concept": "advance_concept",
        },
    )

    builder.add_conditional_edges(
        "advance_concept",
        route_after_advancing_concept,
        {
            "sage": "sage",
            END: END,
        },
    )

    # ------------------------------------------------------------------
    # SAGE -> Critic Quality Gate -> Present to Student
    # ------------------------------------------------------------------
    builder.add_edge("sage", "critic")
    builder.add_conditional_edges(
        "critic",
        route_after_critic,
        {
            "sage": "sage",
            END: END,
        },
    )

    return builder.compile()


# Export the compiled master graph
master_graph = build_master_graph()