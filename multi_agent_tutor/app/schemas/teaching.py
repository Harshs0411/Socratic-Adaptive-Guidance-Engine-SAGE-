from typing import List, Literal, Optional

from pydantic import BaseModel, Field


TeachingAction = Literal[
    "initial",
    "probe",
    "hint",
    "scaffold",
    "explain",
    "advance",
]


class TeachingState(BaseModel):
    """
    State associated with the current teaching session.
    """

    current_action: Optional[TeachingAction] = None

    current_question: Optional[str] = None

    attempt_count: int = 0

    misconception_history: List[str] = Field(
        default_factory=list
    )

    current_objective: Optional[str] = None

    concept_completed: bool = False


class TeachingDecision(BaseModel):
    """
    Decision made by the teaching controller
    about what SAGE should do next.
    """

    action: Literal[
        "probe",
        "hint",
        "scaffold",
        "explain",
        "advance",
    ]

    reason: str