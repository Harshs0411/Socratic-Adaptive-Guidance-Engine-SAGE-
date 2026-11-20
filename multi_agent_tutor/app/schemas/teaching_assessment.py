from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class TeachingAssessment(BaseModel):

    understanding: Literal[
        "mastered",
        "good",
        "partial",
        "weak",
        "incorrect"
    ]

    score: float = Field(
        ge=0.0,
        le=1.0
    )

    confidence: float = Field(
        ge=0.0,
        le=1.0
    )

    misconceptions: List[str] = Field(
        default_factory=list
    )

    reasoning_quality: Literal[
        "strong",
        "partial",
        "weak"
    ]

    feedback: Optional[str] = Field(
        default=None,
        description="A concise 1-2 sentence explanation of why the student's answer is correct, partially correct, or what specific mechanism was missing."
    )
