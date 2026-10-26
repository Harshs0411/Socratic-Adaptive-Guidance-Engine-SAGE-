from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


# =====================================================================
# RICH CURRICULUM SCHEMA (Requirement 4 & Section E)
# =====================================================================

class QuestionItem(BaseModel):
    """
    Structured question item from the 3-tier question bank.
    Tier 1: foundational recall and basic intuition
    Tier 2: mechanical application and calculation
    Tier 3: transfer problem / edge-case synthesis
    """
    question_id: str
    difficulty_tier: int = Field(ge=1, le=3, description="1: foundational, 2: applied, 3: transfer/challenge")
    question_type: str = Field(description="conceptual, objective, application, numeric, sequence, symbolic")
    question: str
    expected_answer: str
    evaluation_criteria: List[str]
    evaluator_type: str = "llm"
    is_transfer: bool = False
    rubric: Optional[Dict[str, Any]] = None


class VisualItem(BaseModel):
    """
    Visual explanation artifact: Mermaid diagram, ASCII diagram, or trace table.
    """
    visual_id: str
    title: str
    type: str = Field(description="'mermaid', 'trace_table', or 'ascii'")
    content: str
    caption: str


class WorkedExample(BaseModel):
    """
    Concrete worked step-by-step example with input, execution trace, and takeaway.
    """
    title: str
    problem: str
    step_by_step_solution: List[str]
    key_takeaway: str
    visuals: Optional[List[VisualItem]] = Field(default_factory=list)


class RichSubtopic(BaseModel):
    """
    Pedagogical unit containing explicit learning objectives, worked examples,
    analogies, common misconceptions, visuals, and a tiered question bank.
    """
    subtopic_id: str
    name: str
    description: str
    explanation_outline: Optional[List[str]] = Field(default_factory=list)
    learning_objectives: List[str]
    worked_examples: List[WorkedExample] = Field(min_length=2)
    analogies: List[str]
    common_misconceptions: List[str]
    visuals: Optional[List[VisualItem]] = Field(default_factory=list)
    question_bank: List[QuestionItem]


class CurriculumTopic(BaseModel):
    """
    High-level topic containing ordered subtopics and prerequisite relationships.
    """
    topic_id: str
    title: str
    description: str
    prerequisites: List[str] = Field(default_factory=list)
    difficulty: int = Field(ge=1, le=5)
    subtopics: List[RichSubtopic]


# =====================================================================
# LEGACY COMPATIBILITY MODELS
# =====================================================================

class CurriculumConcept(BaseModel):
    concept_id: str
    name: str
    description: str
    prerequisites: List[str] = Field(default_factory=list)
    difficulty: int = Field(ge=1, le=5)
    parent_id: Optional[str] = None


class Curriculum(BaseModel):
    """
    Complete prerequisite curriculum for an arbitrary topic.
    Can represent a multi-concept broad subject (e.g. CNN, NLP)
    or an atomic base topic decomposed into cognitive sub-facets.
    """
    topic: str = Field(description="The name of the subject or topic")
    is_atomic: bool = Field(
        default=False,
        description=(
            "True if this is a single base/atomic concept decomposed into "
            "cognitive facets; False if it is a broad multi-concept subject."
        )
    )
    concepts: List[CurriculumConcept] = Field(
        min_length=1,
        max_length=8,
        description="Topologically ordered concepts forming a valid prerequisite DAG"
    )


class RichCurriculum(BaseModel):
    """
    Gold standard rich curriculum containing deep pedagogical metadata.
    """
    curriculum_id: str
    title: str
    domain: str
    description: str
    topics: List[CurriculumTopic]

    def to_curriculum(self) -> Curriculum:
        """
        Converts rich curriculum topics into a legacy Curriculum object
        for seamless compatibility with the existing DAG planner and BKT models.
        """
        concepts = [
            CurriculumConcept(
                concept_id=topic.topic_id,
                name=topic.title,
                description=topic.description,
                prerequisites=topic.prerequisites,
                difficulty=topic.difficulty,
            )
            for topic in self.topics
        ]
        return Curriculum(
            topic=self.title,
            is_atomic=False,
            concepts=concepts,
        )