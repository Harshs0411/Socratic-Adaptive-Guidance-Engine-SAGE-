from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field


class DoubtCheckpoint(BaseModel):
    """
    State snapshot saved when a student interrupts with a doubt.
    Allows exact resumption once the doubt is fully resolved.
    """
    checkpoint_id: str
    topic: str
    subtopic: Optional[str] = None
    teaching_mode: str = "mode_2_teach_first"
    teaching_step: str = "check"
    pending_question: Optional[Dict[str, Any]] = None
    attempt_count: int = 0
    doubt_text: str
    timestamp: Optional[str] = None


class DoubtLogEntry(BaseModel):
    """
    Log of student doubts for pedagogical adaptation (e.g. adding more examples).
    Doubts NEVER penalize BKT.
    """
    topic: str
    subtopic: Optional[str] = None
    doubt_text: str
    resolved: bool = True
    clarity_confirmed: bool = True
    timestamp: Optional[str] = None


class DoubtState(BaseModel):
    """
    State container for doubt management, checkpointing, and clarity tracking.
    """
    doubt_stack: List[Dict[str, Any]] = Field(default_factory=list)
    doubt_log: List[Dict[str, Any]] = Field(default_factory=list)
    pending_clarity_check: bool = False
    clarity_doubt_id: Optional[str] = None
    active_doubt_response: Optional[str] = None
