from multi_agent_tutor.app.graph.state import TutorState

from multi_agent_tutor.app.Agents.learning_path_planner import (
    build_learning_path,
)


def advance_concept(state: TutorState):
    """
    Advance the learner to the next available concept
    after the current concept has been mastered.

    The learning path is rebuilt using the latest
    mastery values already stored in TutorState.
    """

    current_concept = state["current_concept"]

    if current_concept is None:
        raise ValueError(
            "No current concept to advance from."
        )

    teaching = state["teaching"]
    is_completed = teaching.get("concept_completed", False)
    is_skipped = teaching.get("concept_skipped", False) or (current_concept in (state.get("skipped_concepts") or []))

    review_queue = list(state.get("review_queue") or [])
    transitions = list(state.get("concept_transitions") or [])
    import time

    # If moving on without meeting completion criteria, add to review_queue (Fix G)
    if not is_completed:
        reason = "skipped" if is_skipped else (
            "attempt_cap_reached" if teaching.get("attempt_count", 0) >= 3 else "incomplete_mastery"
        )
        if not any((item.get("concept_id") if isinstance(item, dict) else item) == current_concept for item in review_queue):
            review_queue.append({
                "concept_id": current_concept,
                "reason": reason,
                "p_l": state.get("mastery", {}).get(current_concept, 0.0),
                "correct_checks": teaching.get("correct_checks", 0),
            })

    # --------------------------------------------------
    # REBUILD LEARNING PATH
    # --------------------------------------------------
    state_for_plan = dict(state)
    state_for_plan["review_queue"] = review_queue
    result = build_learning_path(state_for_plan)

    learning_path = result["learning_path"]
    next_concept = result["current_concept"]

    diverted = False
    # If review_queue has >= 2 items, must offer/divert to review before opening a third new concept (Fix G)
    if len(review_queue) >= 2 and not learning_path.completed:
        review_item = review_queue.pop(0)
        next_concept = review_item["concept_id"] if isinstance(review_item, dict) else review_item
        diverted = True

    transitions.append({
        "concept_id": current_concept,
        "from_concept": current_concept,
        "to_concept": next_concept,
        "reason": "review_diverted" if diverted else ("mastered" if is_completed else ("skipped" if is_skipped else "needs_review")),
        "p_l": state.get("mastery", {}).get(current_concept, 0.0),
        "correct_checks": teaching.get("correct_checks", 0),
        "timestamp": time.time(),
    })

    # If the entire curriculum is completed
    if learning_path.completed:
        return {
            "learning_path": learning_path,
            "current_concept": None,
            "review_queue": review_queue,
            "concept_transitions": transitions,
            "tutor_response": (
                "🎓 Congratulations! You have successfully mastered all concepts in the "
                f"{state.get('target_topic', 'Curriculum')}!\n\n"
                "You have demonstrated strong conceptual understanding, accurate mathematical "
                "reasoning, and deep mastery across all learning objectives."
            ),
            "teaching": {
                **teaching,
                "concept_completed": True,
                "current_action": "advance",
                "current_question": None,
            },
            "teaching_assessment": None,
            "teaching_decision": None,
            "socratic_response": None,
        }

    from multi_agent_tutor.app.Agents.teaching_agent import choose_mode
    next_mastery = state.get("mastery", {}).get(next_concept, 0.0)
    next_mode = choose_mode(next_mastery)
    next_step = "explain" if next_mode == "mode_2_teach_first" else "check"

    return {
        "learning_path": learning_path,
        "current_concept": next_concept,
        "review_queue": review_queue,
        "concept_transitions": transitions,
        "teaching_mode": next_mode,
        "teaching_step": next_step,
        "teaching": {
            "current_action": "initial",
            "current_question": None,
            "attempt_count": 0,
            "correct_checks": 0,
            "has_transfer_correct": False,
            "misconception_history": [],
            "current_objective": None,
            "concept_completed": False,
        },
        "teaching_assessment": None,
        "teaching_decision": None,
        "socratic_response": None,
    }