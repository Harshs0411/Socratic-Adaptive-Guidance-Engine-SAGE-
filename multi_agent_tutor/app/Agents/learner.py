#it creates the learner profile 

from collections import defaultdict
from multi_agent_tutor.app.graph.state import (
    TutorState
)
from multi_agent_tutor.app.schemas.learner import (
    ConceptProfile,
    LearnerProfile
)
def calculate_weighted_mastery(
    scores: list[float],
    confidences: list[float]
) -> float:

    total_weight = sum(confidences)

    if total_weight == 0:
        return 0.0

    weighted_sum = sum(
        score * confidence
        for score, confidence
        in zip(
            scores,
            confidences
        )
    )

    return weighted_sum / total_weight


def build_learner_profile(
    state: TutorState
):

    diagnostic = state["diagnostic_state"]

    concept_data = defaultdict(
        lambda: {
            "scores": [],
            "confidences": [],
            "misconceptions": []
        }
    )

    for question in diagnostic["questions"]:

        question_id = question.question_id

        if question_id not in (
            diagnostic["assessments"]
        ):
            continue

        assessment = (
            diagnostic["assessments"]
            [question_id]
        )

        concept = question.concept

        concept_data[concept]["scores"].append(
            assessment.score
        )

        concept_data[concept]["confidences"].append(
            assessment.confidence
        )

        concept_data[concept]["misconceptions"].extend(
            assessment.misconceptions
        )


    concept_profiles = {}

    for concept, data in (
        concept_data.items()
    ):

        mastery = calculate_weighted_mastery(
            scores=data["scores"],
            confidences=data[
                "confidences"
            ]
        )

        average_confidence = sum(
            data["confidences"]
        ) / len(data["confidences"])

        concept_profiles[concept] = (
            ConceptProfile(
                concept=concept,

                mastery=mastery,

                confidence=(
                    average_confidence
                ),

                misconceptions=list(
                    set(
                        data[
                            "misconceptions"
                        ]
                    )
                ),

                evidence_count=len(
                    data["scores"]
                )
            )
        )

    if concept_profiles:
        overall_readiness = sum(
            profile.mastery
            for profile in concept_profiles.values()
        ) / len(concept_profiles)
    else:
        overall_readiness = 0.0

    learner_profile = LearnerProfile(
        concepts=concept_profiles,
        overall_readiness=overall_readiness,
        diagnostic_complete=True
    )

    return {
        "learner_profile": learner_profile,
        "mastery": {
            concept: profile.mastery
            for concept, profile in concept_profiles.items()
        }
    }