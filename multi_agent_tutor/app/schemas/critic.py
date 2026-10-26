#for structured output 
from pydantic import BaseModel, Field, field_validator

class CriticOutput(BaseModel):
    passed: bool = Field(
        description="Whether the tutor response passes or fails"
    )

    score: float = Field(
        ge=0,
        le=10,
        description="Score based on the tutor response, between 0 and 10"
    )

    feedback: str = Field(
        description="Short explanation of the evaluation"
    )

    @field_validator("feedback")
    @classmethod
    def validate_feedback(cls, value: str):
        value = value.strip()

        if len(value) < 5:
            raise ValueError("Feedback is too short")

        return value

