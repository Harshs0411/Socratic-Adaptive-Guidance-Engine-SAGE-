from pydantic import BaseModel, Field
from multi_agent_tutor.app.config import (
    DEFAULT_P_TRANSIT,
    DEFAULT_P_GUESS,
    DEFAULT_P_SLIP,
)


class BKTState(BaseModel):

    p_know: float = Field(
        ge=0.0,
        le=1.0
    )

    p_learn: float = Field(
        ge=0.0,
        le=1.0,
        default=DEFAULT_P_TRANSIT
    )

    p_guess: float = Field(
        ge=0.0,
        le=1.0,
        default=DEFAULT_P_GUESS
    )

    p_slip: float = Field(
        ge=0.0,
        le=1.0,
        default=DEFAULT_P_SLIP
    )