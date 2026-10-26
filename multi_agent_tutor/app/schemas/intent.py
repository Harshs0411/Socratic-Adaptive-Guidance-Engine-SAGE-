from typing import Literal, Optional
from pydantic import BaseModel, Field

IntentType = Literal[
    "ANSWER_ATTEMPT",
    "DOUBT",
    "META",
    "CONFIRMATION",
    "CHITCHAT"
]


class IntentClassification(BaseModel):
    """
    Structured output for student message intent classification.
    """
    intent: IntentType = Field(
        description="The primary classified intent of the student message."
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence score for this classification."
    )
    is_mixed: bool = Field(
        default=False,
        description="True if message contains both an answer attempt and a doubt."
    )
    doubt_part: Optional[str] = Field(
        default=None,
        description="The extracted doubt/question part if message is mixed."
    )
    attempt_part: Optional[str] = Field(
        default=None,
        description="The extracted answer attempt part if message is mixed."
    )
    meta_subintent: Optional[str] = Field(
        default=None,
        description="Subcategory for META intents: 'slow_down', 'speed_up', 'skip', 'repeat', 'explain_differently', 'break'."
    )
    reasoning: Optional[str] = Field(
        default=None,
        description="Brief justification for why this intent was selected."
    )
