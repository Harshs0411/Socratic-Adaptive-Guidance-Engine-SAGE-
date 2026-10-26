from typing import List, Literal

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