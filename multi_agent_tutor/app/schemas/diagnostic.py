from typing import List, Literal,Optional
from pydantic import BaseModel, Field

class DiagnosticQuestion(BaseModel):

    question_id: str = Field(
        description=(
            "A unique short identifier for this question, "
            "for example q1, q2, q3"
        )
    )

    concept: str = Field(
        description="The primary concept being tested"
    )

    question: str = Field(
        description="The diagnostic question for the student"
    )

    difficulty: Literal[
        "beginner",
        "intermediate",
        "advanced"
    ] = Field(
        description="Difficulty level of the question"
    )

    question_type: Literal[
        "conceptual",
        "objective",
        "application"
    ] = Field(
        description="The type of diagnostic question"
    )

    reason: str = Field(
        description="Why this question helps diagnose the student"
    )

    evaluation_criteria: List[str] = Field(
        description=(
            "Concepts or ideas that should be demonstrated "
            "for a strong answer"
        )
    )
    is_follow_up: bool = False

    parent_question_id: Optional[str] = None


class DiagnosticQuestionSet(BaseModel):

    topic: str = Field(
        description="The topic being diagnosed"
    )

    questions: List[DiagnosticQuestion] = Field(
        min_length=1,
        max_length=7,
        description="Ordered diagnostic questions"
    )