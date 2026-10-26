def get_diagnostic_progress(
    diagnostic: dict
) -> dict:
    questions = diagnostic.get("questions") or []
    answers = diagnostic.get("answers") or {}

    initial_total = diagnostic.get("initial_total_questions")
    if initial_total is None:
        initial_total = sum(
            1 for q in questions
            if not getattr(q, "is_follow_up", False)
            and not (isinstance(q, dict) and q.get("is_follow_up"))
        )
        if initial_total == 0 and questions:
            initial_total = len(questions)
        diagnostic["initial_total_questions"] = initial_total

    follow_up_qids = {
        getattr(q, "question_id", None) or (q.get("question_id") if isinstance(q, dict) else None)
        for q in questions
        if getattr(q, "is_follow_up", False) or (isinstance(q, dict) and q.get("is_follow_up"))
    }
    base_answered = sum(1 for qid in answers if qid not in follow_up_qids)

    total_questions = max(initial_total, 1) if initial_total else len(questions)
    progress = (
        min(base_answered / total_questions, 1.0)
        if total_questions > 0
        else 0.0
    )

    return {
        "answered_questions": base_answered,
        "total_questions": total_questions,
        "progress": progress,
    }


def format_question_counter(
    current_index: int,
    initial_total: int,
    follow_up_count: int = 0,
) -> str:
    """Format question counter with frozen denominator and clear follow-up tag."""
    if follow_up_count > 0:
        return f"Question {current_index + 1} of {initial_total} (Follow-up {follow_up_count})"
    return f"Question {current_index + 1} of {initial_total}"