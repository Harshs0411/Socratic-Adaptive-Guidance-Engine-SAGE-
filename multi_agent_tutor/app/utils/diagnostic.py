#it is used to get the question by id from the list of questions

from multi_agent_tutor.app.schemas.diagnostic import (
    DiagnosticQuestion
)


def get_question_by_id(
    questions: list[DiagnosticQuestion],
    question_id: str
) -> DiagnosticQuestion:

    for question in questions:

        if question.question_id == question_id:
            return question

    raise ValueError(
        f"Question not found: {question_id}"
    )
def has_follow_up(
    questions,
    parent_question_id: str
) -> bool:

    return any(
        question.parent_question_id
        == parent_question_id
        for question in questions
    )