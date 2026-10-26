#for structured output
from typing import Literal, Optional
from pydantic import BaseModel, Field

class DiagnosticDecision(BaseModel):

    action: Literal[
        "next_question",
        "skip_question",
        "follow_up",
        "complete"
    ]

    reason: str

    follow_up_question: Optional[str] = Field(
        default=None
    )