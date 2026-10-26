#it just shifts the question to next question 
from multi_agent_tutor.app.graph.state import (
    TutorState
)

from multi_agent_tutor.app.utils.diagnostic import (
    get_question_by_id,
    has_follow_up
)

from multi_agent_tutor.app.Agents.followup_generator import (
    generate_follow_up_question
)

def advance_diagnostic(
    state: TutorState
):

    diagnostic = state["diagnostic_state"]

    current_question_id = (
        diagnostic["current_question_id"]
    )

    if current_question_id is None:
        return {}

    current_question = get_question_by_id(
        diagnostic["questions"],
        current_question_id
    )

    assessment = (
        diagnostic["assessments"][current_question_id]
    )

    hints_given = diagnostic.get("hints_given") or {}
    hint_was_given = bool(hints_given.get(current_question_id))
    student_ans = diagnostic.get("answers", {}).get(current_question_id, "")
    from multi_agent_tutor.app.Agents.assessment import is_dont_know_response
    is_idk = is_dont_know_response(student_ans)

    needs_follow_up = (
        not getattr(current_question, "is_follow_up", False)
        and not is_idk
        and not hint_was_given
        and assessment.score < 0.5
        and assessment.confidence >= 0.7
        and len(assessment.misconceptions) > 0
    )

    follow_up_exists = has_follow_up(
        diagnostic["questions"],
        current_question_id
    )

    if (
        needs_follow_up
        and not follow_up_exists
    ):

        follow_up_question = (
            generate_follow_up_question(
                question_id=current_question.question_id,

                concept=current_question.concept,

                question=current_question.question,

                criteria=current_question.evaluation_criteria,

                student_answer=(
                    diagnostic["answers"]
                    [current_question_id]
                ),

                misconceptions=(
                    assessment.misconceptions
                )
            )
        )
        current_index = next(
            index
            for index, question
            in enumerate(
                diagnostic["questions"]
            )
            if question.question_id
            == current_question_id
        )

        updated_questions = (
            diagnostic["questions"][:current_index + 1]
            + [follow_up_question]
            + diagnostic["questions"][current_index + 1:]
        )
        return {
            "diagnostic_state": {
                **diagnostic,

                "questions":
                    updated_questions,

                "current_question_id":
                    follow_up_question.question_id
            }
        }
    questions = diagnostic["questions"]
    current_index = next(
        index
        for index, question
        in enumerate(questions)
        if question.question_id
        == current_question_id
    )

    # -----------------------------------------------------------------
    # EARLY STOPPING & "I DON'T KNOW" HANDLING (Requirement 1.4)
    # -----------------------------------------------------------------
    student_ans = diagnostic.get("answers", {}).get(current_question_id, "")
    from multi_agent_tutor.app.Agents.assessment import is_dont_know_response
    is_idk = is_dont_know_response(student_ans)

    curr_concept = getattr(current_question, "concept", "")
    assessments = diagnostic.get("assessments", {})

    # Gather scores for current concept so far
    concept_scores = [
        ass.score for qid, ass in assessments.items()
        if any(q.question_id == qid and getattr(q, "concept", "") == curr_concept for q in questions)
    ]

    stop_current_concept = False
    if is_idk or (hint_was_given and assessment.score < 0.5):
        # Stop probing current concept; low prior without penalty
        stop_current_concept = True
    elif len(concept_scores) >= 2:
        # 2 right in a row (both >= 0.8) or 2 wrong in a row (both < 0.5)
        last_two = concept_scores[-2:]
        if all(s >= 0.8 for s in last_two) or all(s < 0.5 for s in last_two):
            stop_current_concept = True

    # Global early stopping check: if >= 4 questions answered or all concepts evaluated
    total_answered = len(assessments)
    unique_concepts_evaluated = len({
        getattr(q, "concept", "") for qid in assessments.keys()
        for q in questions if q.question_id == qid
    })

    if total_answered >= 4 and unique_concepts_evaluated >= 2:
        # Picture is clear: stop diagnostic early!
        return {
            "diagnostic_state": {
                **diagnostic,
                "completed": True,
                "current_question_id": None
            }
        }

    # Find next question (skip remaining on current concept if stop_current_concept)
    next_index = current_index + 1
    while next_index < len(questions):
        next_q = questions[next_index]
        if stop_current_concept and getattr(next_q, "concept", "") == curr_concept:
            next_index += 1
            continue
        break

    if next_index >= len(questions):
        return {
            "diagnostic_state": {
                **diagnostic,
                "completed": True,
                "current_question_id": None
            }
        }

    next_question = questions[next_index]

    return {
        "diagnostic_state": {
            **diagnostic,
            "current_question_id": next_question.question_id
        }
    }
