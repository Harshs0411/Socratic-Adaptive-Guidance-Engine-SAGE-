from multi_agent_tutor.app.graph.state import TutorState
from multi_agent_tutor.app.schemas.bkt import BKTState

from multi_agent_tutor.app.utils.bkt import (
    update_bkt,
    assessment_to_evidence,
)


def update_mastery(
    state: TutorState
):
    """
    Update BKT knowledge for the current concept
    after evaluating a student's answer.

    The TeachingAssessment score and confidence
    are converted into continuous evidence.
    """

    # Credit assignment: update the concept that the question belongs to (Fix G)
    target_concept_id = None
    pq = state.get("pending_question")
    if isinstance(pq, dict):
        target_concept_id = pq.get("concept_id")

    if not target_concept_id:
        resp = state.get("socratic_response")
        if isinstance(resp, dict):
            target_concept_id = resp.get("concept_id")
        elif hasattr(resp, "concept_id"):
            target_concept_id = getattr(resp, "concept_id", None)

    if not target_concept_id:
        target_concept_id = state.get("current_concept")

    if target_concept_id is None:
        raise ValueError(
            "No current or target concept available for credit assignment."
        )

    concept_id = target_concept_id

    assessment = state["teaching_assessment"]

    if assessment is None:
        raise ValueError(
            "No teaching assessment available."
        )

    bkt_states = dict(
        state.get("bkt_states", {})
    )

    current_bkt = bkt_states.get(
        concept_id
    )

    if current_bkt is None:
        # Graceful fallback: initialize from mastery map or default BKT prior (0.20)
        fallback_p = state.get("mastery", {}).get(concept_id, 0.20)
        current_bkt = BKTState(p_know=fallback_p)
        bkt_states[concept_id] = current_bkt
    elif isinstance(current_bkt, dict):
        current_bkt = BKTState(**current_bkt)
        bkt_states[concept_id] = current_bkt

    # --------------------------------------------------
    # SOFT EVIDENCE
    # --------------------------------------------------

    score = getattr(assessment, "score", 0.0) if not isinstance(assessment, dict) else assessment.get("score", 0.0)
    confidence = getattr(assessment, "confidence", 1.0) if not isinstance(assessment, dict) else assessment.get("confidence", 1.0)

    evidence = assessment_to_evidence(
        score=score,
        confidence=confidence,
    )

    updated_bkt = update_bkt(
        current_bkt,
        evidence,
    )

    bkt_states[concept_id] = updated_bkt

    # Keep the simpler mastery dictionary
    # synchronized with BKT.
    mastery = dict(
        state["mastery"]
    )

    mastery[concept_id] = (
        updated_bkt.p_know
    )

    # Roll up mastery to parent concept if this is a drilldown child
    curriculum = state.get("curriculum", [])
    parent_id = None
    for c in curriculum:
        cid = getattr(c, "concept_id", "") if hasattr(c, "concept_id") else c.get("concept_id", "")
        if cid == concept_id:
            parent_id = getattr(c, "parent_id", None) if hasattr(c, "parent_id") else c.get("parent_id")
            break

    if parent_id:
        child_ids = []
        for c in curriculum:
            c_pid = getattr(c, "parent_id", None) if hasattr(c, "parent_id") else c.get("parent_id")
            cid = getattr(c, "concept_id", "") if hasattr(c, "concept_id") else c.get("concept_id", "")
            if c_pid == parent_id and cid:
                child_ids.append(cid)
        if child_ids:
            parent_avg = sum(mastery.get(cid, 0.0) for cid in child_ids) / len(child_ids)
            parent_avg = max(0.0, min(0.99, parent_avg))
            mastery[parent_id] = round(parent_avg, 4)
            if parent_id in bkt_states:
                bkt_states[parent_id] = BKTState(p_know=round(parent_avg, 4))

    return {
        "bkt_states": bkt_states,
        "mastery": mastery,
    }