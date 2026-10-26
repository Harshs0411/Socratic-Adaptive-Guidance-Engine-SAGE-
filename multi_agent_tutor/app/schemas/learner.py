from typing import Dict, List
from pydantic import BaseModel, Field

class ConceptProfile(BaseModel):

    concept: str
    mastery: float = Field(
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
    evidence_count: int = Field(
        default=0
    )


class LearnerProfile(BaseModel):

    concepts: Dict[
        str,
        ConceptProfile
    ] = Field(
        default_factory=dict
    )
    overall_readiness: float = Field(
        ge=0.0,
        le=1.0
    )
    diagnostic_complete: bool = False