"""
Curriculum Loader for SAGE Tutor (Requirement 4 & Section E).
Loads gold-standard hand-authored curriculum files (such as binary_search_curriculum.json)
for predefined domains, and falls back seamlessly to the LLM curriculum generator for
custom or arbitrary user-selected topics.
"""

import json
import os
from pathlib import Path
from typing import Optional, List, Tuple
from multi_agent_tutor.app.schemas.curriculum import (
    RichCurriculum,
    CurriculumConcept,
    Curriculum,
)


CURRICULUM_DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "curriculum"


def get_curriculum_file_for_topic(topic: str) -> Optional[Path]:
    """
    Resolves a canonical file path for topics with pre-authored curricula.
    """
    norm = topic.lower().strip()
    if norm in ["binary search", "binary_search"]:
        gold_file = CURRICULUM_DATA_DIR / "binary_search_curriculum.json"
        if gold_file.exists():
            return gold_file
    return None


def load_rich_curriculum(topic: str) -> Optional[RichCurriculum]:
    """
    Loads and validates the RichCurriculum object for a topic if available on disk.
    """
    file_path = get_curriculum_file_for_topic(topic)
    if not file_path:
        return None

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return RichCurriculum.model_validate(data)
    except Exception as e:
        print(f"Warning: Failed to load rich curriculum from {file_path}: {e}")
        return None


def load_curriculum_concepts(topic: str) -> Optional[List[CurriculumConcept]]:
    """
    Returns the CurriculumConcept DAG list for the topic if a static file exists.
    """
    rich_curriculum = load_rich_curriculum(topic)
    if rich_curriculum:
        return rich_curriculum.to_curriculum().concepts
    return None
