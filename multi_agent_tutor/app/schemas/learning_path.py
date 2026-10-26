from typing import List, Literal, Optional
from pydantic import BaseModel, Field

class LearningPathStep(BaseModel):

    concept_id: str

    status: Literal[
        "mastered",
        "ready",
        "learning",
        "locked",
        "needs_review",
        "skipped"
    ]

    mastery: float = Field(
        ge=0.0,
        le=1.0
    )

    reason: str


class LearningPath(BaseModel):

    target_topic: str

    steps: List[LearningPathStep]

    current_concept_id: Optional[str]

    completed: bool = False