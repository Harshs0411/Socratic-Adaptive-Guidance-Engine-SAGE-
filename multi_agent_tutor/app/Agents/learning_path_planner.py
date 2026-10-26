from multi_agent_tutor.app.graph.state import TutorState
from multi_agent_tutor.app.schemas.learning_path import (
    LearningPath,
    LearningPathStep,
)


# ==========================================================
# PLANNER CONFIGURATION
# ==========================================================

PREREQUISITE_THRESHOLD = 0.60
REVIEW_THRESHOLD = 0.60
MASTERY_THRESHOLD = 0.85


# ==========================================================
# PREREQUISITE CHECKING
# ==========================================================

def prerequisites_mastered(
    concept,
    mastery_map: dict[str, float],
) -> bool:
    """
    Return True when all prerequisites of a concept
    have reached the minimum mastery threshold.
    """

    for prerequisite in concept.prerequisites:
        mastery = mastery_map.get(
            prerequisite,
            0.0,
        )

        if mastery < PREREQUISITE_THRESHOLD:
            return False

    return True


# ==========================================================
# CONCEPT STATUS
# ==========================================================

def determine_status(
    concept,
    mastery: float,
    mastery_map: dict[str, float],
    skipped_concepts: list[str] | None = None,
) -> tuple[str, str]:
    """
    Determine the current learning status of one concept.

    Status meanings:

        mastered
            Sufficiently learned.

        skipped
            Skipped by student; preserved with original mastery to revisit later.

        needs_review
            Previously learned but mastery is not yet strong.

        ready
            Prerequisites are satisfied and the concept
            can be started.

        locked
            One or more prerequisites are not ready.
    """

    if mastery >= MASTERY_THRESHOLD:
        return (
            "mastered",
            "The learner has reached the mastery threshold.",
        )

    if skipped_concepts and concept.concept_id in skipped_concepts:
        return (
            "skipped",
            "Concept was skipped by student and will be revisited before curriculum completion.",
        )

    if mastery >= REVIEW_THRESHOLD:
        return (
            "needs_review",
            "The concept has been learned but should be reinforced.",
        )

    if prerequisites_mastered(
        concept,
        mastery_map,
    ):
        return (
            "ready",
            "Prerequisites are sufficiently mastered to begin this concept.",
        )

    return (
        "locked",
        "One or more prerequisites need additional learning first.",
    )


# ==========================================================
# PRIORITY CALCULATION
# ==========================================================

def calculate_priority(
    concept,
    mastery: float,
    status: str,
) -> float:
    """
    Calculate a deterministic priority for selecting
    the next concept.

    Higher value = higher priority.

    The planner prefers:

        1. concepts needing review
        2. concepts with lower mastery
        3. concepts that are ready to learn

    Mastered and locked concepts receive no priority.
    """

    if status == "mastered":
        return 0.0

    if status == "locked":
        return 0.0

    # ------------------------------------------------------
    # Base priority from knowledge gap
    # ------------------------------------------------------

    knowledge_gap = 1.0 - mastery

    # ------------------------------------------------------
    # Review gets a small priority boost.
    #
    # A concept around 0.60-0.84 should normally be
    # reinforced before introducing something completely
    # new at the same stage.
    # ------------------------------------------------------

    review_bonus = 0.15 if status == "needs_review" else 0.0
    skipped_bonus = 0.10 if status == "skipped" else 0.0

    # ------------------------------------------------------
    # Difficulty is used only as a small tie-breaker.
    #
    # We do NOT want the planner to simply choose the
    # hardest concept.
    # ------------------------------------------------------

    difficulty_bonus = min(
        concept.difficulty * 0.02,
        0.10,
    )

    return (
        knowledge_gap
        + review_bonus
        + skipped_bonus
        + difficulty_bonus
    )


# ==========================================================
# NEXT CONCEPT SELECTION
# ==========================================================

def select_next_concept(
    candidates: list[tuple],
) -> str | None:
    """
    Select the highest-priority available concept.

    candidates contains:

        (
            concept,
            mastery,
            status,
            priority
        )

    Deterministic tie-breaking:

        1. Higher priority
        2. Lower mastery
        3. Lower curriculum difficulty
    """

    # 1. First priority: concepts that are ready or need review
    available = [
        item
        for item in candidates
        if item[2] in {
            "ready",
            "needs_review",
        }
    ]

    if not available:
        # 2. If no ready concepts remain, revisit previously skipped concepts!
        skipped = [
            item
            for item in candidates
            if item[2] == "skipped"
        ]
        if skipped:
            skipped.sort(
                key=lambda item: (
                    -item[3],       # priority
                    item[1],        # lower mastery first
                    item[0].difficulty,
                )
            )
            return skipped[0][0].concept_id
        return None

    available.sort(
        key=lambda item: (
            -item[3],       # priority
            item[1],        # lower mastery first
            item[0].difficulty,
        )
    )

    return available[0][0].concept_id


# ==========================================================
# LEARNING PATH BUILDER
# ==========================================================

def build_learning_path(
    state: TutorState,
):
    """
    Build an adaptive learning path from:

        - curriculum structure
        - learner mastery
        - prerequisite relationships

    The planner is fully domain-agnostic and builds the learning
    path from whatever curriculum concepts are active in TutorState.
    """

    mastery_map = state["mastery"]
    skipped_concepts = state.get("skipped_concepts") or []
    review_queue = state.get("review_queue") or []
    review_ids = {item.get("concept_id") if isinstance(item, dict) else item for item in review_queue}

    steps = []

    candidates = []

    # ------------------------------------------------------
    # Evaluate every curriculum concept
    # ------------------------------------------------------

    curriculum = state.get("curriculum") or []

    for concept in curriculum:

        mastery = mastery_map.get(
            concept.concept_id,
            0.0,
        )

        status, reason = determine_status(
            concept=concept,
            mastery=mastery,
            mastery_map=mastery_map,
            skipped_concepts=skipped_concepts,
        )

        if concept.concept_id in review_ids:
            status = "needs_review"
            reason = "Concept is in review queue for reinforcement before final completion."

        priority = calculate_priority(
            concept=concept,
            mastery=mastery,
            status=status,
        )

        # --------------------------------------------------
        # Store candidate information for selection.
        # --------------------------------------------------

        candidates.append(
            (
                concept,
                mastery,
                status,
                priority,
            )
        )

        steps.append(
            LearningPathStep(
                concept_id=concept.concept_id,
                status=status,
                mastery=mastery,
                reason=reason,
            )
        )

    # ------------------------------------------------------
    # Select adaptive next concept
    # ------------------------------------------------------

    current_concept_id = select_next_concept(
        candidates
    )

    # ------------------------------------------------------
    # Check whether the entire curriculum is mastered
    # ------------------------------------------------------

    completed = all(
        step.status == "mastered"
        for step in steps
    )

    # ------------------------------------------------------
    # If everything is mastered, there is no next concept.
    # ------------------------------------------------------

    if completed:
        current_concept_id = None

    # ------------------------------------------------------
    # Build LearningPath object
    # ------------------------------------------------------

    learning_path = LearningPath(
        target_topic=state["target_topic"],
        steps=steps,
        current_concept_id=current_concept_id,
        completed=completed,
    )

    return {
        "learning_path": learning_path,
        "current_concept": current_concept_id,
    }