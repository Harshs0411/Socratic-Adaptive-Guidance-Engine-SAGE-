import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")
warnings.filterwarnings("ignore", message=".*NotOpenSSLWarning.*")

import sys
import select
from pprint import pprint

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

from multi_agent_tutor.app.schemas.bkt import BKTState
from multi_agent_tutor.app.graph.teaching_workflow import (
    teaching_workflow,
)


def create_initial_state():
    """
    Create the initial state for a teaching session.

    In the real application, most of this state will
    come from the diagnostic and learner-model phases.
    """

    return {
        "student_id": "test_student",

        "target_topic": "CNN",

        "messages": [],

        "student_input": None,

        "diagnostic": {
            "completed": True,
            "questions": [],
            "current_question_id": None,
            "answers": {},
            "assessments": {},
        },

        "learner_profile": None,

        "mastery": {
            "matrix": 0.90,
            "image_representation": 0.75,
            "convolution": 0.35,
            "feature_maps": 0.20,
            "pooling": 0.10,
            "cnn_architecture": 0.05,
        },

        "bkt_states": {
            "matrix": BKTState(
                p_know=0.90,
                p_learn=0.15,
                p_guess=0.20,
                p_slip=0.10
            ),

            "image_representation": BKTState(
                p_know=0.75,
                p_learn=0.15,
                p_guess=0.20,
                p_slip=0.10
            ),

            "convolution": BKTState(
                p_know=0.35,
                p_learn=0.15,
                p_guess=0.20,
                p_slip=0.10
            ),

            "feature_maps": BKTState(
                p_know=0.20,
                p_learn=0.15,
                p_guess=0.20,
                p_slip=0.10
            ),

            "pooling": BKTState(
                p_know=0.10,
                p_learn=0.15,
                p_guess=0.20,
                p_slip=0.10
            ),

            "cnn_architecture": BKTState(
                p_know=0.05,
                p_learn=0.15,
                p_guess=0.20,
                p_slip=0.10
            ),
        },

        "learning_path": None,

        "current_concept": "convolution",

        "teaching": {
            "current_action": "initial",
            "current_question": None,
            "attempt_count": 0,
            "misconception_history": [],
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
    }


def print_tutor_state(state):
    """
    Print the most important information from the
    current tutoring state.
    """

    print("\n" + "=" * 70)

    current_concept = state.get(
        "current_concept"
    )

    print(
        f"CURRENT CONCEPT: {current_concept}"
    )

    mastery_map = state.get(
        "mastery",
        {}
    )

    current_mastery = mastery_map.get(
        current_concept,
        0.0
    )

    print(
        f"MASTERY: {current_mastery:.3f}"
    )

    # --------------------------------------------------
    # Socratic Response
    # --------------------------------------------------

    response = state.get(
        "socratic_response"
    )

    if response:

        print("\nSAGE:")
        print(
            response.message
        )

        print("\nQUESTION:")
        print(
            response.question
        )

        print(
            f"\nACTION: {response.action}"
        )

    # --------------------------------------------------
    # Teaching Decision
    # --------------------------------------------------

    decision = state.get(
        "teaching_decision"
    )

    if decision:

        print("\nTEACHING DECISION:")

        print(
            f"{decision.action} "
            f"- {decision.reason}"
        )

    # --------------------------------------------------
    # Teaching Assessment
    # --------------------------------------------------

    assessment = state.get(
        "teaching_assessment"
    )

    if assessment:

        print("\nASSESSMENT:")

        print(
            f"Understanding: "
            f"{assessment.understanding}"
        )

        print(
            f"Score: "
            f"{assessment.score:.2f}"
        )

        print(
            f"Confidence: "
            f"{assessment.confidence:.2f}"
        )

        print(
            f"Reasoning: "
            f"{assessment.reasoning_quality}"
        )

        if assessment.misconceptions:

            print(
                "Misconceptions:"
            )

            for misconception in (
                assessment.misconceptions
            ):

                print(
                    f"  - {misconception}"
                )

    print("=" * 70)

    
def get_student_input() -> str:
    """
    Read student input from stdin.
    Supports single-line responses, pasted multi-line markdown/LaTeX blocks,
    and piped input without leaving unread lines in the stdin buffer.
    """
    try:
        first_line = input("\nStudent: ")
    except EOFError:
        return "quit"

    if first_line.strip().lower() == "quit":
        return "quit"

    # For non-interactive piped input (e.g. automated tests), process one line per turn
    if not sys.stdin.isatty():
        return first_line.strip()

    lines = [first_line]

    # If additional lines were pasted or buffered, consume them into this single response
    while True:
        rlist, _, _ = select.select([sys.stdin], [], [], 0.05)
        if rlist:
            line = sys.stdin.readline()
            if not line:
                break
            lines.append(line.rstrip("\r\n"))
        else:
            break

    return "\n".join(lines).strip()


def main():

    state = create_initial_state()

    print(
        "\nStarting SAGE teaching session..."
    )

    # --------------------------------------------------
    # First turn
    # --------------------------------------------------

    state = teaching_workflow.invoke(
        state
    )

    print_tutor_state(state)

    # --------------------------------------------------
    # Interactive student loop
    # --------------------------------------------------

    while True:

        print(
            "\nType your answer "
            "(or 'quit' to stop):"
        )

        student_answer = get_student_input()

        if student_answer.lower() == "quit":
            print(
                "\nEnding session."
            )
            break

        if not student_answer:
            print(
                "Please enter an answer."
            )
            continue

        # Put the student's answer into state.
        state["student_input"] = (
            student_answer
        )

        # Run the graph again.
        state = teaching_workflow.invoke(
            state
        )

        print_tutor_state(state)


if __name__ == "__main__":
    main()