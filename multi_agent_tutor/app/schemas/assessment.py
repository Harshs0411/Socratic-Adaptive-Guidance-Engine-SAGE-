#for structured output
from typing import List, Literal, Optional
from pydantic import BaseModel, Field

class AssessmentResult(BaseModel):

    correctness: Literal[
        "correct",
        "partially_correct",
        "incorrect"
    ] = Field(
        description="Overall correctness of the student's answer"
    )

    score: float = Field(
        ge=0.0,
        le=1.0,
        description="Normalized understanding score from 0 to 1"
    )

    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description=(
            "Confidence in the assessment. "
            "This represents evaluator confidence, "
            "not student confidence."
        )
    )

    evidence_of_understanding: List[str] = Field(
        description="Specific ideas the student demonstrated correctly"
    )

    misconceptions: List[str] = Field(
        description="Incorrect ideas or misconceptions detected"
    )

    feedback: str = Field(
        description=(
            "Short feedback explaining the assessment. "
            "Do not provide a full lesson."
        )
    )