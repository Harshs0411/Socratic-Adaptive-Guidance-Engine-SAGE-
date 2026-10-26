"""
Visual Explanation Agent for SAGE Tutor (Step 4).
Handles:
1. Pre-authored visual retrieval from the rich curriculum (Mermaid flowcharts, ASCII pointer diagrams, trace tables).
2. Dynamic fallback generation if no pre-authored visual matches.
3. Embedding into Mode 2 explanations and REQUEST_VISUAL meta-intent responses.
"""

from typing import Optional, List, Dict, Any
from multi_agent_tutor.app.curriculum_loader import load_rich_curriculum
from multi_agent_tutor.app.schemas.curriculum import VisualItem


def get_visual_for_concept(topic: str, concept_id: Optional[str], visual_type: Optional[str] = None) -> Optional[VisualItem]:
    """
    Retrieves the most relevant visual for a topic and concept.
    Uses pre-authored visual from rich curriculum if available, otherwise retrieves
    the dynamic visual generated for that custom concept.
    """
    rich = load_rich_curriculum(topic)
    if rich:
        # 1. Search in matching topic / subtopics
        for t in rich.topics:
            if concept_id and (t.topic_id == concept_id or any(s.subtopic_id == concept_id for s in t.subtopics)):
                for s in t.subtopics:
                    if s.visuals:
                        for v in s.visuals:
                            if not visual_type or v.type == visual_type:
                                return v
                    # Check worked example visuals
                    for ex in s.worked_examples:
                        if ex.visuals:
                            for v in ex.visuals:
                                if not visual_type or v.type == visual_type:
                                    return v

    # For custom topics, fetch the dynamic visual item
    if concept_id:
        from multi_agent_tutor.app.Agents.teaching_agent import get_subtopic_pedagogical_data
        ped = get_subtopic_pedagogical_data(topic, concept_id)
        if ped and ped.get("visual_mermaid"):
            return VisualItem(
                visual_id=f"vis_dyn_{concept_id}",
                title=ped.get("visual_title", f"{concept_id.replace('_', ' ').title()} Visual Model"),
                type="mermaid",
                content=ped.get("visual_mermaid", ""),
                caption=ped.get("visual_caption", f"Architectural model for {concept_id.replace('_', ' ').title()}"),
            )

    return None


def get_all_visuals_for_subtopic(topic: str, concept_id: Optional[str]) -> List[VisualItem]:
    """Retrieves all visual items associated with a subtopic and its worked examples."""
    rich = load_rich_curriculum(topic)
    if not rich:
        v = get_visual_for_concept(topic, concept_id)
        return [v] if v else []

    collected: List[VisualItem] = []
    for t in rich.topics:
        if concept_id and (t.topic_id == concept_id or any(s.subtopic_id == concept_id for s in t.subtopics)):
            for s in t.subtopics:
                if s.visuals:
                    collected.extend(s.visuals)
                for ex in s.worked_examples:
                    if ex.visuals:
                        collected.extend(ex.visuals)
            break

    return collected


def generate_fallback_visual(concept: str) -> VisualItem:
    """Deterministic fallback diagram if no pre-authored visual is found."""
    clean_name = concept.replace("_", " ").title() if concept else "System"
    return VisualItem(
        visual_id=f"vis_fallback_{concept}",
        title=f"{clean_name} Structural Overview",
        type="ascii",
        content=(
            f"[ Input / State ] ---> [ {clean_name} ] ---> [ Verified Output ]\n"
            f"       |                         |\n"
            f"       +---> [ Invariant Check ] -+"
        ),
        caption=f"Operational state flow and invariant boundary for {clean_name}."
    )
