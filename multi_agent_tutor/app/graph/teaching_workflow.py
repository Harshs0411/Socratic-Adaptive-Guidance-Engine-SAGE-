from langgraph.graph import StateGraph, START, END

from multi_agent_tutor.app.graph.state import TutorState

from multi_agent_tutor.app.Agents.tutor import sage_agent
from multi_agent_tutor.app.Agents.teaching_assessor import (
    assess_teaching_response,
)
from multi_agent_tutor.app.Agents.mastery_updater import (
    update_mastery,
)
from multi_agent_tutor.app.Agents.teaching_controller import (
    teaching_controller,
)
from multi_agent_tutor.app.Agents.concept_advancer import (
    advance_concept,
)


def route_from_start(state: TutorState):
    """
    Decide whether the graph should generate a new
    Socratic question or evaluate the student's answer.

    If student_input exists, the student has answered
    the previous question.

    Otherwise SAGE needs to generate a question.
    """

    if state.get("student_input"):
        return "teaching_assessor"

    return "sage"


def route_after_controller(state: TutorState):
    """
    Decide whether to continue teaching the current
    concept or advance to another concept.
    """

    decision = state.get("teaching_decision")

    if decision is None:
        raise ValueError(
            "Teaching decision is missing."
        )

    if decision.action == "advance":
        return "concept_advancer"

    return "sage"


def build_teaching_workflow():
    """
    Build the LangGraph responsible for the
    Socratic teaching loop.
    """

    graph = StateGraph(TutorState)

    # --------------------------------------------------
    # Nodes
    # --------------------------------------------------

    graph.add_node(
        "sage",
        sage_agent,
    )

    graph.add_node(
        "teaching_assessor",
        assess_teaching_response,
    )

    graph.add_node(
        "mastery_updater",
        update_mastery,
    )

    graph.add_node(
        "teaching_controller",
        teaching_controller,
    )

    graph.add_node(
        "concept_advancer",
        advance_concept,
    )

    # --------------------------------------------------
    # START
    # --------------------------------------------------

    graph.add_conditional_edges(
        START,
        route_from_start,
        {
            "sage": "sage",
            "teaching_assessor": "teaching_assessor",
        },
    )

    # --------------------------------------------------
    # SAGE
    #
    # SAGE generates the question and then stops.
    #
    # The application displays the response to the
    # student and waits for student_input.
    # --------------------------------------------------

    graph.add_edge(
        "sage",
        END,
    )

    # --------------------------------------------------
    # Assessment
    # --------------------------------------------------

    graph.add_edge(
        "teaching_assessor",
        "mastery_updater",
    )

    # --------------------------------------------------
    # BKT
    # --------------------------------------------------

    graph.add_edge(
        "mastery_updater",
        "teaching_controller",
    )

    # --------------------------------------------------
    # Teaching decision
    # --------------------------------------------------

    graph.add_conditional_edges(
        "teaching_controller",
        route_after_controller,
        {
            "sage": "sage",
            "concept_advancer": "concept_advancer",
        },
    )

    # --------------------------------------------------
    # Concept advancement
    #
    # After moving to the next concept, SAGE generates
    # the first question for that concept.
    # --------------------------------------------------

    graph.add_edge(
        "concept_advancer",
        "sage",
    )

    return graph.compile()


teaching_workflow = build_teaching_workflow()