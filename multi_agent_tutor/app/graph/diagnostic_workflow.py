from langgraph.graph import StateGraph, START, END

from multi_agent_tutor.app.Agents.question_presenter import (
    present_diagnostic_question
)

from multi_agent_tutor.app.graph.state import (
    TutorState
)

from multi_agent_tutor.app.Agents.diagnostic import (
    diagnostic_agent
)

from multi_agent_tutor.app.Agents.assessment import (
    assessment_agent
)

from multi_agent_tutor.app.Agents.next_question_shifting_id import (
    advance_diagnostic
)

from multi_agent_tutor.app.Agents.learner import (
    build_learner_profile
)


builder = StateGraph(TutorState)


builder.add_node(
    "diagnostic",
    diagnostic_agent
)

builder.add_node(
    "assessment",
    assessment_agent
)

builder.add_node(
    "advance",
    advance_diagnostic
)

builder.add_node(
    "present_question",
    present_diagnostic_question
)

builder.add_node(
    "learner_model",
    build_learner_profile
)


def route_diagnostic_start(
    state: TutorState
):
    diagnostic = state["diagnostic_state"]

    if not diagnostic["questions"]:
        return "diagnostic"

    if (
        not diagnostic["completed"]
        and state.get("student_input")
    ):
        return "assessment"

    return END


def route_after_advance(
    state: TutorState
):
    if state["diagnostic_state"]["completed"]:
        return "learner_model"

    return "present_question"


builder.add_conditional_edges(
    START,
    route_diagnostic_start
)


builder.add_edge(
    "diagnostic",
    "present_question"
)


builder.add_edge(
    "assessment",
    "advance"
)


builder.add_conditional_edges(
    "advance",
    route_after_advance,
    {
        "learner_model":
            "learner_model",

        "present_question":
            "present_question"
    }
)


builder.add_edge(
    "learner_model",
    END
)


builder.add_edge(
    "present_question",
    END
)


graph = builder.compile()