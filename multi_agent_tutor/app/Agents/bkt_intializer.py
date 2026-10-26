from multi_agent_tutor.app.graph.state import TutorState
from multi_agent_tutor.app.schemas.bkt import BKTState


CONCEPT_ALIASES = {
    "matrices": "matrix",
    "matrix": "matrix",
    "image": "image_representation",
    "images": "image_representation",
    "imagerepresentation": "image_representation",
    "convolution": "convolution",
    "convolutions": "convolution",
    "conv": "convolution",
    "featuremap": "feature_maps",
    "featuremaps": "feature_maps",
    "features": "feature_maps",
    "pooling": "pooling",
    "maxpooling": "pooling",
    "averagepooling": "pooling",
    "pool": "pooling",
    "cnn": "cnn_architecture",
    "cnns": "cnn_architecture",
    "cnnarchitecture": "cnn_architecture",
    "convolutionalneuralnetwork": "cnn_architecture",
    "convolutionalneuralnetworks": "cnn_architecture",
}


def _normalize_name(name: str) -> str:
    """Normalize concept name for robust fuzzy matching."""
    return "".join(c for c in name.lower() if c.isalnum())


def _find_matching_score(
    concept_id: str,
    concept_name: str,
    mastery: dict[str, float],
) -> float | None:
    """
    Find initial mastery score from diagnostic assessment by checking
    exact ID, normalized name, alias lookup, or substring matching.
    """
    if concept_id in mastery:
        return mastery[concept_id]

    norm_id = _normalize_name(concept_id)
    norm_name = _normalize_name(concept_name)

    for key, score in mastery.items():
        norm_key = _normalize_name(key)
        # Check alias
        canonical_alias = CONCEPT_ALIASES.get(norm_key)
        if canonical_alias == concept_id:
            return score

        if norm_key in (norm_id, norm_name):
            return score
        # Substring / partial matches
        if norm_id in norm_key or norm_key in norm_id:
            return score
        if norm_name in norm_key or norm_key in norm_name:
            return score

    return None


def initialize_bkt_states(state: TutorState):
    """
    Initialize Bayesian Cognitive Mastery states for all curriculum concepts
    using evidence gathered during the diagnostic phase.

    If a student answers 'I don't know' or scores 0.0 across diagnostic questions,
    their demonstrated baseline mastery is strictly 0.0 (0%) for all concepts.
    Concepts directly assessed receive their exact demonstrated score without an artificial floor.
    Unobserved concepts inherit proportionally from overall diagnostic readiness.
    """
    mastery_input = dict(state.get("mastery", {}))
    bkt_states = {}
    mastery_output = {}

    profile = state.get("learner_profile")
    overall_readiness = float(getattr(profile, "overall_readiness", 0.0)) if profile else 0.0

    level = state.get("self_reported_level", "some_knowledge")
    from multi_agent_tutor.app.config import DEFAULT_P_L0

    # 1. Initialize all curriculum concepts
    curriculum = state.get("curriculum") or []
    for concept in curriculum:
        concept_id = concept.concept_id
        matched_score = _find_matching_score(
            concept_id,
            concept.name,
            mastery_input,
        )

        if level == "beginner":
            # Requirement 1.3: Beginner path sets P(L) of EVERY topic to 0.0
            p_know = 0.0
        elif matched_score is not None:
            # Concept was directly assessed: use demonstrated score
            p_know = max(0.0, min(1.0, float(matched_score)))
        else:
            # Unobserved concept:
            # "Some knowledge" caps untested topics at conservative default (DEFAULT_P_L0=0.20)
            if level == "some_knowledge":
                p_know = min(DEFAULT_P_L0, max(0.05, float(overall_readiness * 0.5)))
            elif level == "comfortable":
                # A "Comfortable" student who failed gets low priors
                if overall_readiness < 0.5:
                    p_know = 0.15
                else:
                    p_know = min(0.35, max(0.15, float(overall_readiness * 0.5)))
            else:
                p_know = DEFAULT_P_L0

        bkt_states[concept_id] = BKTState(p_know=round(p_know, 4))
        mastery_output[concept_id] = round(p_know, 4)

    # 2. Preserve any extra diagnostic concepts in bkt_states
    for key, val in mastery_input.items():
        if key not in bkt_states:
            score = max(0.0, min(1.0, float(val)))
            bkt_states[key] = BKTState(p_know=round(score, 4))
            mastery_output[key] = round(score, 4)

    return {
        "bkt_states": bkt_states,
        "mastery": mastery_output,
    }