import os
import re
from typing import List, Optional
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from multi_agent_tutor.app.graph.state import TutorState
from multi_agent_tutor.app.schemas.curriculum import (
    Curriculum,
    CurriculumConcept,
)


model = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.2,
)

curriculum_llm = model.with_structured_output(
    Curriculum,
    method="function_calling",
)

CURRICULUM_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """You are the Lead Curriculum Architect Agent of SAGE, a universal Socratic AI tutoring system designed to teach ANY subject or skill to mastery.
Your role is to analyze any user-requested subject (across Computer Science, Mathematics, Physics, Engineering, Biology, Economics, Medicine, Philosophy, etc.) and synthesize an educational prerequisite graph (Directed Acyclic Graph / DAG).

Target Cognitive Depth Level: {depth_level}
Levels:
- foundational: 3 to 4 high-level intuitive concepts (Bloom 1-2). Focus on basic definitions, analogies, and core intuition.
- applied: 4 to 6 concepts (Bloom 3-4). Focus on practical problem solving, implementation mechanics, standard patterns, and common pitfalls.
- deep: 6 to 8 rigorous milestones (Bloom 5-6). Designed for deep mastery. Decompose the topic from first principles, mathematical derivations, internal mechanisms, system trade-offs, to advanced boundary conditions and failure modes.

Curriculum Structure Rules:
1. If the topic is ATOMIC (single narrow concept like 'Binary Search', 'Ohm\\'s Law', 'Page Replacement'):
   - Set `is_atomic = True`.
   - Decompose into 3 to 4 cognitive facets:
     * Facet 1: First Principles & Problem Motivation (Prereqs: [])
     * Facet 2: Core Mechanics & Mathematical Formulation (Prereqs: [facet 1])
     * Facet 3: Invariants, Boundary Conditions & Edge Cases (Prereqs: [facet 2])
     * Facet 4: System Trade-offs & Practical Optimization (Prereqs: [facet 3])

2. If the topic is BROAD / MODULAR (e.g. 'Operating Systems', 'Machine Learning', 'Quantum Mechanics', 'C++', 'Microeconomics'):
   - Set `is_atomic = False`.
   - If depth is 'deep', generate 6 to 8 topologically ordered milestones that progress logically from foundational building blocks to graduate/expert edge cases.
   - The first 1-2 concepts MUST be root prerequisites (prerequisites = []).
   - Subsequent concepts must explicitly list earlier concept_ids in `prerequisites`.

DAG Design Rules:
- `concept_id` MUST be concise, lowercase, alphanumeric with underscores only (e.g. 'virtual_memory', 'svd_decomposition', 'nash_equilibrium').
- Every concept referenced in `prerequisites` MUST be present in the `concepts` list!
- Never create circular dependencies (A -> B -> A).
- Sort the concepts in topological learning order (root prerequisites first).
- Difficulty: integer from 1 (introductory) to 5 (advanced expert).
"""
        ),
        (
            "human",
            "Target topic to design a curriculum for: {topic}\nTarget Depth Level: {depth_level}"
        ),
    ]
)

SUB_CURRICULUM_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """You are the Sub-Curriculum Architect Agent of SAGE.
The student is currently mastering the parent topic '{parent_topic}' and wants to DRILL DOWN into depth on the specific concept: '{concept_name}' (ID: {concept_id}).

Your role is to unpack this single concept into a focused, high-resolution sub-curriculum DAG of 3 to 5 granular sub-facets.
Follow Bloom's Taxonomy:
1. Intuition & Theoretical Motivation (Prerequisites: [])
2. Core Mechanics, Mathematical Derivation or Implementation (Prerequisites: [subfacet 1])
3. Boundary Conditions, Edge Cases & Failure Modes (Prerequisites: [subfacet 2])
4. Real-world Synthesis & Advanced Optimization (Prerequisites: [subfacet 3])

Ensure all `concept_id` values are lowercase alphanumeric with underscores, prefixed by '{concept_id}_' to prevent namespace collisions.
Difficulty: 1 to 5.
"""
        ),
        (
            "human",
            "Generate drill-down sub-curriculum for '{concept_name}' within '{parent_topic}'. Depth: {depth_level}."
        ),
    ]
)


def _sanitize_concept_id(raw_id: str) -> str:
    """Ensure concept_id is clean lowercase snake_case."""
    cleaned = re.sub(r"[^a-zA-Z0-9_]", "_", raw_id.lower().strip())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned or "concept"


def _validate_and_fix_dag(concepts: List[CurriculumConcept]) -> List[CurriculumConcept]:
    """
    Ensure the concepts form a strictly valid Directed Acyclic Graph (DAG):
    - All IDs sanitized
    - Prerequisites exist in the list
    - No self-loops or circular references
    - Topologically ordered
    """
    valid_ids = set()
    cleaned_concepts = []

    for c in concepts:
        c_id = _sanitize_concept_id(c.concept_id)
        filtered_prereqs = [
            _sanitize_concept_id(p)
            for p in c.prerequisites
            if _sanitize_concept_id(p) in valid_ids and _sanitize_concept_id(p) != c_id
        ]
        
        cleaned_c = CurriculumConcept(
            concept_id=c_id,
            name=c.name,
            description=c.description,
            prerequisites=filtered_prereqs,
            difficulty=max(1, min(5, c.difficulty)),
        )
        valid_ids.add(c_id)
        cleaned_concepts.append(cleaned_c)

    if cleaned_concepts and cleaned_concepts[0].prerequisites:
        cleaned_concepts[0].prerequisites = []

    return cleaned_concepts


def generate_sub_curriculum(
    parent_topic: str,
    concept_name: str,
    concept_id: str,
    depth_level: str = "deep",
) -> List[CurriculumConcept]:
    """
    Generates a focused sub-curriculum DAG to drill down into a specific concept in depth.
    """
    chain = SUB_CURRICULUM_PROMPT | curriculum_llm
    result: Curriculum = chain.invoke({
        "parent_topic": parent_topic,
        "concept_name": concept_name,
        "concept_id": concept_id,
        "depth_level": depth_level,
    })
    return _validate_and_fix_dag(result.concepts)


from multi_agent_tutor.app.curriculum_loader import load_curriculum_concepts


def curriculum_agent(state: TutorState) -> dict:
    """
    LangGraph node: Generates the prerequisite curriculum DAG for any target topic.
    Uses pre-authored gold reference curricula (e.g. binary_search_curriculum.json)
    when available, and falls back to the dynamic Curriculum Architect LLM for custom topics.
    """
    if state.get("curriculum"):
        return {}

    topic = state.get("target_topic", "").strip() or "General Science"
    depth = state.get("depth_level") or "deep"

    # 1. Check for pre-authored gold standard curriculum (e.g. Binary Search)
    static_concepts = load_curriculum_concepts(topic)
    if static_concepts:
        return {
            "curriculum": static_concepts,
            "target_topic": topic,
            "depth_level": depth,
        }

    # 2. Fall back to LLM dynamic generator
    chain = CURRICULUM_PROMPT | curriculum_llm
    result: Curriculum = chain.invoke({
        "topic": topic,
        "depth_level": depth,
    })

    validated_concepts = _validate_and_fix_dag(result.concepts)

    return {
        "curriculum": validated_concepts,
        "target_topic": result.topic or topic,
        "depth_level": depth,
    }
