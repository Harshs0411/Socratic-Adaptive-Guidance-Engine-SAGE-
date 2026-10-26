from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from multi_agent_tutor.app.utils.diagnostic import get_question_by_id
from multi_agent_tutor.app.graph.state import TutorState
from multi_agent_tutor.app.schemas.assessment import (
    AssessmentResult
)
load_dotenv()

model = ChatOpenAI(
    model="gpt-5-mini",
    temperature=0
)

assessment_llm = model.with_structured_output(
    AssessmentResult
)

assessment_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """
You are the Assessment Agent for SAGE,
an adaptive AI tutoring system.

Your task is to evaluate a student's answer
to a diagnostic question.

Evaluate conceptual understanding,
not merely keyword matching.

Assessment rules:

1. Determine whether the answer is correct,
   partially correct, or incorrect.

2. A partially correct answer should be used when
   the student demonstrates meaningful understanding
   but contains important omissions or errors.

3. Identify specific misconceptions only when they
   are supported by the student's answer.

4. Do not invent misconceptions.

5. Do not over-penalize short answers if they are
   conceptually correct.

6. The score must represent demonstrated understanding
   from 0.0 to 1.0.

7. confidence represents your confidence in the
   assessment, not the student's confidence.

8. Feedback should be concise and helpful.

9. Do not provide a complete lesson or a long explanation.

Concept being tested:

{concept}

Diagnostic question:

{question}

Student answer:

{student_answer}

Expected_understanding: The student should demonstrate understanding of the concept being tested, including key principles, relationships, and reasoning.
{evaluation_criteria}
"""
        )
    ]
)
assessment_chain = (
    assessment_prompt
    | assessment_llm
)
def is_dont_know_response(answer: str) -> bool:
    """Detect if the student response indicates they do not know the concept."""
    cleaned = "".join(c for c in (answer or "").lower().strip() if c.isalnum() or c.isspace()).strip()
    dont_know_phrases = {
        "I don't know",
        "i dont know",
        "i do not know",
        "dont know",
        "do not know",
        "idk",
        "no idea",
        "have no idea",
        "i have no idea",
        "not sure",
        "im not sure",
        "i am not sure",
        "no clue",
        "have no clue",
        "pass",
        "skip",
        "i dont understand",
        "i do not understand",
        "dont understand",
        "na",
        "none",
        "nothing",
    }
    if cleaned in dont_know_phrases:
        return True
    return any(cleaned.startswith(p) and len(cleaned) <= len(p) + 8 for p in ["i dont know", "dont know", "idk", "no idea", "not sure", "no clue"])


def assess_answer(
    concept: str,
    question: str,
    student_answer: str,
    evaluation_criteria: list[str]
) -> AssessmentResult:

    if is_dont_know_response(student_answer):
        return AssessmentResult(
            correctness="incorrect",
            score=0.0,
            confidence=1.0,
            evidence_of_understanding=[],
            misconceptions=[],
            feedback="The student indicated they have no prior knowledge of this concept.",
        )

    result = assessment_chain.invoke(
        {
            "concept": concept,
            "question": question,
            "student_answer": student_answer,
            "evaluation_criteria": evaluation_criteria
        }
    )
    return result

def assessment_agent(
    state: TutorState
):

    diagnostic = state["diagnostic_state"]
    current_question_id = diagnostic["current_question_id"]

    if current_question_id is None:
        raise ValueError(
            "No active diagnostic question."
        )
    question = get_question_by_id(
        diagnostic["questions"],
        current_question_id
    )

    student_answer = state["student_input"]

    if not student_answer:
        raise ValueError(
            "No student answer received."
        )

    result = assess_answer(
        concept=question.concept,
        question=question.question,
        evaluation_criteria=question.evaluation_criteria,
        student_answer=student_answer
    )

    # Fix 5: If hint was given on this diagnostic question, cap score at 0.5
    hints_given = diagnostic.get("hints_given") or {}
    if hints_given.get(current_question_id):
        if result.score >= 0.5:
            result.score = min(result.score * 0.5, 0.5)
            result.feedback = f"{result.feedback} (Graded with hint discount: capped at {result.score:.2f})"
        else:
            result.score = 0.0
            result.feedback = "No problem at all, that tells me exactly where to begin!"

    return {
        "student_input": None,
        "diagnostic_state": {
            **diagnostic,
            "answers": {
                **diagnostic["answers"],
                current_question_id: student_answer
            },
            "assessments": {
                **diagnostic["assessments"],
                current_question_id: result
            }
        }
    }