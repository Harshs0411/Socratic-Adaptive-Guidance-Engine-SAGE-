from multi_agent_tutor.app.graph.state import TutorState
from multi_agent_tutor.app.schemas.bkt import BKTState
from multi_agent_tutor.app.schemas.teaching import (
    TeachingDecision,
)


from multi_agent_tutor.app.config import (
    MASTERY_ADVANCE_THRESHOLD,
    SUBTOPIC_MIN_CORRECT_CHECKS,
    SUBTOPIC_REQUIRE_TRANSFER,
)


def choose_objective(
    assessment,
    previous_objective,
):
    """
    Determine the pedagogical target for the next
    tutoring turn.

    We prefer the student's actual misconception
    over repeatedly testing the whole concept.
    """
    misconceptions = getattr(assessment, "misconceptions", None) or (assessment.get("misconceptions", []) if isinstance(assessment, dict) else [])
    score = getattr(assessment, "score", 0.0) if not isinstance(assessment, dict) else assessment.get("score", 0.0)

    if misconceptions:
        return misconceptions[0]

    if score < 0.60:
        return (
            "Identify the smallest missing idea "
            "needed to understand the current concept."
        )

    if previous_objective:
        return previous_objective

    return (
        "Demonstrate a deeper understanding of "
        "the current concept."
    )


def teaching_controller(
    state: TutorState
):
    """
    Decide the next teaching action and pedagogical
    objective.
    """

    assessment = state.get(
        "teaching_assessment"
    )

    if assessment is None:
        raise ValueError(
            "Teaching assessment is required."
        )

    ass_score = getattr(assessment, "score", 0.0) if not isinstance(assessment, dict) else assessment.get("score", 0.0)
    ass_misconceptions = getattr(assessment, "misconceptions", None) or (assessment.get("misconceptions", []) if isinstance(assessment, dict) else [])
    ass_reasoning = getattr(assessment, "reasoning_quality", "weak") if not isinstance(assessment, dict) else assessment.get("reasoning_quality", "weak")

    concept = state["current_concept"]

    if concept is None:
        raise ValueError(
            "No current concept."
        )

    bkt = state.get("bkt_states", {}).get(
        concept
    )

    if bkt is None:
        fallback_p = state.get("mastery", {}).get(concept, 0.20)
        bkt = BKTState(p_know=fallback_p)
        if "bkt_states" in state and isinstance(state["bkt_states"], dict):
            state["bkt_states"][concept] = bkt
    elif isinstance(bkt, dict):
        bkt = BKTState(**bkt)
        if "bkt_states" in state and isinstance(state["bkt_states"], dict):
            state["bkt_states"][concept] = bkt

    teaching = state.get("teaching") or {
        "attempt_count": 0,
        "correct_checks": 0,
        "has_transfer_correct": False,
        "misconception_history": [],
    }

    attempt_count = (
        teaching.get("attempt_count", 0) + 1
    )

    misconceptions = list(
        teaching.get("misconception_history", [])
    )

    for misconception in ass_misconceptions:
        if misconception not in misconceptions:
            misconceptions.append(
                misconception
            )

    objective = choose_objective(
        assessment,
        teaching.get("current_objective"),
    )

    # Track correct check counts and transfer questions
    correct_checks = teaching.get("correct_checks", 0)
    has_transfer_correct = teaching.get("has_transfer_correct", False)

    if ass_score >= 0.75:
        correct_checks += 1
        pq = state.get("pending_question") or {}
        if pq.get("is_transfer") or pq.get("question_type") == "application":
            has_transfer_correct = True

    # Check for student META skip request (Requirement 3: Skip Handling)
    if state.get("signals", {}).get("skip_requested"):
        signals = dict(state.get("signals") or {})
        signals.pop("skip_requested", None)
        concept = state.get("current_concept")
        skipped_concepts = list(state.get("skipped_concepts") or [])
        if concept and concept not in skipped_concepts:
            skipped_concepts.append(concept)

        decision = TeachingDecision(
            action="advance",
            reason="Student requested to skip this concept. Marked status=skipped with mastery unchanged to be revisited before curriculum completion.",
        )
        return {
            "teaching_decision": decision,
            "signals": signals,
            "skipped_concepts": skipped_concepts,
            "teaching": {
                **teaching,
                "current_action": "advance",
                "attempt_count": attempt_count,
                "correct_checks": correct_checks,
                "has_transfer_correct": has_transfer_correct,
                "misconception_history": misconceptions,
                "current_objective": objective,
                "concept_completed": False,  # MUST NOT mark as completed/mastered
                "concept_skipped": True,     # Flag for advancer to bypass completion check
            },
        }

    # ==================================================
    # MASTERY & SUBTOPIC COMPLETION RULE (Requirement D)
    # ==================================================
    meets_bkt = (bkt.p_know >= MASTERY_ADVANCE_THRESHOLD)
    meets_score = (ass_score >= 0.85 and ass_reasoning == "strong" and not ass_misconceptions)
    meets_min_checks = (correct_checks >= SUBTOPIC_MIN_CORRECT_CHECKS)
    meets_transfer = (not SUBTOPIC_REQUIRE_TRANSFER or has_transfer_correct)

    if meets_bkt and meets_score and meets_min_checks and meets_transfer:
        decision = TeachingDecision(
            action="advance",
            reason=(
                f"The learner demonstrates strong reasoning, P(L)={bkt.p_know:.2f} >= {MASTERY_ADVANCE_THRESHOLD}, "
                f"answered {correct_checks} check questions correctly (min {SUBTOPIC_MIN_CORRECT_CHECKS}), "
                "including at least 1 transfer application question."
            ),
        )

        return {
            "teaching_decision": decision,
            "teaching": {
                **teaching,
                "current_action": "advance",
                "attempt_count": attempt_count,
                "correct_checks": correct_checks,
                "has_transfer_correct": has_transfer_correct,
                "misconception_history": misconceptions,
                "current_objective": objective,
                "concept_completed": True,
            },
        }

    # If P(L) is high but hasn't satisfied the check count or transfer requirement yet:
    if meets_bkt and meets_score and (not meets_min_checks or not meets_transfer):
        transfer_objective = f"Apply {concept} to an unfamiliar transfer problem to demonstrate robust mastery."
        decision = TeachingDecision(
            action="probe",
            reason=(
                f"The learner has high estimated mastery ({bkt.p_know:.2f}), but must verify understanding with "
                f"{SUBTOPIC_MIN_CORRECT_CHECKS} correct checks and at least 1 transfer problem before completing."
            ),
        )
        return {
            "teaching_decision": decision,
            "teaching": {
                **teaching,
                "current_action": "probe",
                "attempt_count": attempt_count,
                "correct_checks": correct_checks,
                "has_transfer_correct": has_transfer_correct,
                "misconception_history": misconceptions,
                "current_objective": transfer_objective,
                "concept_completed": False,
            },
        }

    # ==================================================
    # STRONG BUT NOT MASTERED
    # ==================================================

    if ass_score >= 0.75:

        decision = TeachingDecision(
            action="probe",
            reason=(
                "The learner demonstrates good understanding "
                "but needs additional evidence before mastery."
            ),
        )

        return {
            "teaching_decision": decision,

            "teaching": {
                **teaching,
                "current_action": "probe",
                "attempt_count": attempt_count,
                "misconception_history": misconceptions,
                "current_objective": objective,
                "concept_completed": False,
            },
        }

    # ==================================================
    # PARTIAL UNDERSTANDING
    # ==================================================

    if ass_score >= 0.50:

        decision = TeachingDecision(
            action="probe",
            reason=(
                "The learner has partial understanding. "
                "Target the remaining knowledge gap."
            ),
        )

        return {
            "teaching_decision": decision,

            "teaching": {
                **teaching,
                "current_action": "probe",
                "attempt_count": attempt_count,
                "misconception_history": misconceptions,
                "current_objective": objective,
                "concept_completed": False,
            },
        }

    # ==================================================
    # STRUGGLING / INCORRECT: RE-TEACH CYCLES (Part 2)
    # ==================================================
    mode = state.get("teaching_mode", "mode_2_teach_first")
    if mode == "mode_2_teach_first":
        from multi_agent_tutor.app.Agents.teaching_agent import (
            generate_re_teach_explanation,
            REMEDIATION_CAP,
        )
        re_teach_msg, reached_cap = generate_re_teach_explanation(
            topic=state.get("target_topic", "Binary Search"),
            concept_id=concept,
            attempt_count=attempt_count,
            misconception_notes=misconceptions,
        )

        if reached_cap:
            decision = TeachingDecision(
                action="scaffold",
                reason=f"Reached remediation cap ({REMEDIATION_CAP}). Offering prerequisite revisit or hint ladder.",
            )
            return {
                "teaching_decision": decision,
                "tutor_response": re_teach_msg,
                "teaching": {
                    **teaching,
                    "current_action": "prerequisite_offer",
                    "attempt_count": attempt_count,
                    "correct_checks": correct_checks,
                    "has_transfer_correct": has_transfer_correct,
                    "misconception_history": misconceptions,
                    "current_objective": "Revisit prerequisite or scaffold",
                    "concept_completed": False,
                },
            }
        else:
            decision = TeachingDecision(
                action="explain",
                reason=f"Re-teaching with differentiated pedagogical cycle approach #{attempt_count}.",
            )
            return {
                "teaching_decision": decision,
                "tutor_response": re_teach_msg,
                "teaching": {
                    **teaching,
                    "current_action": "re_teach",
                    "attempt_count": attempt_count,
                    "correct_checks": correct_checks,
                    "has_transfer_correct": has_transfer_correct,
                    "misconception_history": misconceptions,
                    "current_objective": f"Re-teach cycle {attempt_count}",
                    "concept_completed": False,
                },
            }

    # MODE 1 FALLBACK (High Mastery Q&A)
    if attempt_count <= 2:
        decision = TeachingDecision(
            action="hint",
            reason="Mode 1 Q&A: provide a small hint targeting the missing idea.",
        )
        return {
            "teaching_decision": decision,
            "teaching": {
                **teaching,
                "current_action": "hint",
                "attempt_count": attempt_count,
                "correct_checks": correct_checks,
                "has_transfer_correct": has_transfer_correct,
                "misconception_history": misconceptions,
                "current_objective": objective,
                "concept_completed": False,
            },
        }

    decision = TeachingDecision(
        action="explain",
        reason="Mode 1 Q&A: explain only the gap after repeated errors.",
    )
    return {
        "teaching_decision": decision,
        "teaching": {
            **teaching,
            "current_action": "explain",
            "attempt_count": attempt_count,
            "correct_checks": correct_checks,
            "has_transfer_correct": has_transfer_correct,
            "misconception_history": misconceptions,
            "current_objective": objective,
            "concept_completed": False,
        },
    }