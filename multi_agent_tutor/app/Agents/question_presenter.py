from multi_agent_tutor.app.graph.state import (
    TutorState
)

from multi_agent_tutor.app.utils.diagnostic import (
    get_question_by_id
)

from multi_agent_tutor.app.utils.progress_tracker_question import (
    get_diagnostic_progress
)


def present_diagnostic_question(
    state: TutorState
):

    diagnostic = state["diagnostic_state"]

    if diagnostic["completed"]:

        return {
            "tutor_response":
                "The diagnostic assessment is complete."
        }

    current_question_id = (
        diagnostic["current_question_id"]
    )

    if current_question_id is None:

        return {
            "tutor_response":
                "The diagnostic assessment is complete."
        }

    question = get_question_by_id(
        diagnostic["questions"],
        current_question_id
    )

    progress = get_diagnostic_progress(
        diagnostic
    )

    prefix = ""
    assessments = diagnostic.get("assessments") or {}
    hints_given = diagnostic.get("hints_given") or {}
    if assessments:
        last_qid = list(assessments.keys())[-1]
        last_ass = assessments[last_qid]
        if (hints_given.get(last_qid) and getattr(last_ass, "score", 1.0) < 0.5) or getattr(last_ass, "score", 1.0) == 0.0:
            prefix = "No problem at all, that tells me exactly where to begin!\n\n"

    is_fu = getattr(question, "is_follow_up", False) or (isinstance(question, dict) and question.get("is_follow_up"))
    if is_fu:
        header = f"Follow-up Question (Diagnostic question {progress['answered_questions']} of {progress['total_questions']})"
    else:
        header = f"Diagnostic question {progress['answered_questions'] + 1} of {progress['total_questions']}"

    response = (
        f"{prefix}"
        f"{header}\n\n"
        f"{question.question}"
    )

    from multi_agent_tutor.app.schemas.socratic import SocraticResponse
    socratic_resp = SocraticResponse(
        message=response,
        question=question.question,
        action="probe",
        question_type=getattr(question, "question_type", "conceptual"),
        expected_answer="Diagnostic response",
        evaluator_type="llm",
        evaluation_criteria=question.evaluation_criteria,
    )

    return {
        "tutor_response": response,
        "socratic_response": socratic_resp,
        "awaiting": "answer",
        "pending_question": {
            "question_id": question.question_id,
            "concept": question.concept,
            "question": question.question,
            "evaluation_criteria": question.evaluation_criteria,
        }
    }