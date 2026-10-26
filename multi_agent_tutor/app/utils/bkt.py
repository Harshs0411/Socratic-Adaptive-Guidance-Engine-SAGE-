from typing import Any, Union, Dict
from pydantic import BaseModel, Field
from multi_agent_tutor.app.schemas.bkt import BKTState
from multi_agent_tutor.app.config import (
    DEFAULT_P_L0,
    DEFAULT_P_TRANSIT,
    DEFAULT_P_GUESS,
    DEFAULT_P_SLIP,
)


def _ensure_bkt_state(bkt: Any) -> BKTState:
    """Guarantees bkt is a typed BKTState instance, converting from dict if needed."""
    if isinstance(bkt, BKTState):
        return bkt
    if isinstance(bkt, dict):
        return BKTState(
            p_know=float(bkt.get("p_know", DEFAULT_P_L0)),
            p_learn=float(bkt.get("p_learn", DEFAULT_P_TRANSIT)),
            p_guess=float(bkt.get("p_guess", DEFAULT_P_GUESS)),
            p_slip=float(bkt.get("p_slip", DEFAULT_P_SLIP)),
        )
    if isinstance(bkt, (int, float)):
        return BKTState(
            p_know=float(bkt),
            p_learn=DEFAULT_P_TRANSIT,
            p_guess=DEFAULT_P_GUESS,
            p_slip=DEFAULT_P_SLIP,
        )
    p = getattr(bkt, "p_know", DEFAULT_P_L0)
    return BKTState(p_know=float(p))


def probability_correct(
    bkt: Union[BKTState, Dict[str, Any]]
) -> float:
    """
    Probability that the learner will answer
    the next question correctly.

    P(C) =
        P(K) * (1 - P(S))
        +
        (1 - P(K)) * P(G)
    """
    bkt = _ensure_bkt_state(bkt)
    return (
        bkt.p_know * (1.0 - bkt.p_slip)
        + (1.0 - bkt.p_know) * bkt.p_guess
    )


def posterior_if_correct(
    bkt: Union[BKTState, Dict[str, Any]]
) -> float:
    """
    P(Know | Correct)
    """
    bkt = _ensure_bkt_state(bkt)
    p_correct = probability_correct(bkt)

    if p_correct <= 1e-8:
        return bkt.p_know

    posterior = (
        bkt.p_know
        * (1.0 - bkt.p_slip)
    ) / p_correct

    return max(
        0.0,
        min(1.0, posterior)
    )


def posterior_if_incorrect(
    bkt: Union[BKTState, Dict[str, Any]]
) -> float:
    """
    P(Know | Incorrect)
    """
    bkt = _ensure_bkt_state(bkt)
    p_correct = probability_correct(bkt)

    p_incorrect = 1.0 - p_correct

    if p_incorrect <= 1e-8:
        return bkt.p_know

    posterior = (
        bkt.p_know
        * bkt.p_slip
    ) / p_incorrect

    return max(
        0.0,
        min(1.0, posterior)
    )


def update_bkt(
    bkt: Union[BKTState, Dict[str, Any]],
    evidence: float,
) -> BKTState:
    """
    Update BKT using continuous evidence.

    evidence is in [0, 1]:

        1.0 = fully correct evidence
        0.8 = strong evidence
        0.6 = partial evidence
        0.3 = weak evidence
        0.0 = incorrect evidence

    Instead of converting the assessment into
    True/False, we interpolate between the Bayesian
    posterior for a correct and incorrect observation.
    """
    bkt = _ensure_bkt_state(bkt)

    current_p = bkt.p_know

    # 1. Continuous Bayesian posterior calculation
    correct_posterior = posterior_if_correct(bkt)
    incorrect_posterior = posterior_if_incorrect(bkt)

    posterior = (
        evidence * correct_posterior
        + (1.0 - evidence) * incorrect_posterior
    )

    # 2. Learning transition only occurs when evidence demonstrates acquisition
    if evidence >= 0.50:
        learning_factor = (evidence - 0.50) * 2.0  # Normalized between 0.0 and 1.0
        updated_p_know = posterior + (1.0 - posterior) * (bkt.p_learn * learning_factor)
    else:
        # On incorrect or 'don't know' responses, mastery does not increase
        updated_p_know = posterior

    updated_p_know = max(
        0.0,
        min(0.99, round(updated_p_know, 4))
    )

    return BKTState(
        p_know=updated_p_know,
        p_learn=bkt.p_learn,
        p_guess=bkt.p_guess,
        p_slip=bkt.p_slip,
    )


def assessment_to_evidence(
    score: float,
    confidence: float,
) -> float:
    """
    Convert TeachingAssessment into BKT evidence.

    The assessment score represents how correct the
    learner's response was.

    Confidence determines how strongly we trust
    that assessment.

    We shrink uncertain assessments toward 0.5.

    Examples:

        score=1.0, confidence=1.0
            -> 1.00

        score=1.0, confidence=0.5
            -> 0.75

        score=0.6, confidence=1.0
            -> 0.60

        score=0.6, confidence=0.5
            -> 0.55

        score=0.0, confidence=1.0
            -> 0.00

        score=0.0, confidence=0.5
            -> 0.25
    """

    score = max(
        0.0,
        min(1.0, score)
    )

    confidence = max(
        0.0,
        min(1.0, confidence)
    )

    evidence = (
        confidence * score
        + (1.0 - confidence) * 0.5
    )

    return max(
        0.0,
        min(1.0, evidence)
    )


    return score >= 0.70


def apply_forgetting(
    p_know: float,
    days_elapsed: float,
    lambda_decay: float = 0.05,
    retention_floor: float = 0.20,
) -> float:
    """
    Applies exponential forgetting decay toward retention floor over elapsed days.
    Decays toward retention_floor (default 0.20), never toward 0.
    Applied strictly between sessions, never mid-lesson.
    """
    import math
    if days_elapsed <= 0:
        return p_know
    if p_know <= retention_floor:
        return p_know
    decayed = retention_floor + (p_know - retention_floor) * math.exp(-lambda_decay * days_elapsed)
    return round(max(retention_floor, min(1.0, decayed)), 4)