import pytest
from multi_agent_tutor.app.graph.state import TutorState
from multi_agent_tutor.app.schemas.diagnostic import DiagnosticQuestion
from multi_agent_tutor.app.Agents.doubt_agent import handle_doubt_question
from multi_agent_tutor.app.Agents.teaching_agent import (
    generate_mode_2_explanation,
    get_subtopic_pedagogical_data,
    select_check_question,
)


def test_bug_a_first_idk_gives_hint_and_reasks_same_question():
    """
    BUG A Rule 1: First 'I don't know' or hint click on a diagnostic question:
    give ONE small hint, then re-ask the SAME question. Mark hint_given=True.
    Invariant: Ends with re-asked question, not bare 'Does that make sense?'.
    """
    q1 = DiagnosticQuestion(
        question_id="diag_q1",
        concept="monotonicity_concept",
        question="Why must an array be sorted for binary search to work?",
        difficulty="beginner",
        question_type="conceptual",
        reason="Check monotonicity understanding",
        evaluation_criteria=["Mentions deterministic elimination or sorting invariant"],
    )
    state = {
        "student_id": "test_qa_student",
        "target_topic": "Binary Search",
        "diagnostic_state": {
            "completed": False,
            "questions": [q1],
            "current_question_id": "diag_q1",
            "answers": {},
            "assessments": {},
            "hints_given": {},
        },
        "pending_question": {
            "question_id": "diag_q1",
            "question": q1.question,
            "concept": q1.concept,
        },
        "doubt_state": {
            "doubt_stack": [],
            "doubt_log": [],
            "pending_clarity_check": False,
        },
        "mastery": {},
    }

    # First "I don't know"
    res = handle_doubt_question(
        state,
        "I don't know, could you give me a hint?",
        doubt_info={"meta_subintent": "help_request"}
    )

    tutor_reply = res["tutor_response"]
    assert "No worries at all! Here's a small hint" in tutor_reply or "hint" in tutor_reply.lower()
    assert q1.question in tutor_reply
    # Verify invariant: does NOT end with bare "Does that make sense?"
    assert not tutor_reply.strip().endswith("Does that make sense, or should I explain it another way?")
    # Verify hint marked in diagnostic_state
    assert res["diagnostic_state"]["hints_given"]["diag_q1"] is True
    # Verify question still pending
    assert res["pending_question"]["question_id"] == "diag_q1"


def test_bug_a_second_idk_records_zero_prior_and_advances():
    """
    BUG A Rule 2: Second 'I don't know' on that question:
    - Treat concept as unknown ('No problem at all, that tells me exactly where to begin!').
    - Record low prior (score = 0.0) with zero penalty.
    - Stop probing that topic.
    - In the SAME reply, present next question (or summary if last).
    """
    q1 = DiagnosticQuestion(
        question_id="diag_q1",
        concept="concept_a",
        question="Question A1?",
        difficulty="beginner",
        question_type="conceptual",
        reason="Check A1",
        evaluation_criteria=["Crit A"],
    )
    q2 = DiagnosticQuestion(
        question_id="diag_q2",
        concept="concept_b",
        question="Question B1 on next concept?",
        difficulty="beginner",
        question_type="conceptual",
        reason="Check B1",
        evaluation_criteria=["Crit B"],
    )
    state = {
        "student_id": "test_qa_student",
        "target_topic": "Binary Search",
        "curriculum": [],
        "diagnostic_state": {
            "completed": False,
            "questions": [q1, q2],
            "current_question_id": "diag_q1",
            "answers": {},
            "assessments": {},
            "hints_given": {"diag_q1": True},  # Hint was already given!
        },
        "pending_question": {
            "question_id": "diag_q1",
            "question": q1.question,
            "concept": q1.concept,
        },
        "doubt_state": {
            "doubt_stack": [],
            "doubt_log": [],
            "pending_clarity_check": False,
        },
        "mastery": {},
    }

    # Second "I don't know"
    res = handle_doubt_question(
        state,
        "I don't know",
        doubt_info={"meta_subintent": "help_request"}
    )

    tutor_reply = res["tutor_response"]
    assert "No problem at all, that tells me exactly where to begin!" in tutor_reply
    # Must present next diagnostic question in the same reply
    assert q2.question in tutor_reply
    # Score must be 0.0 with zero penalty
    assessments = res["diagnostic_state"]["assessments"]
    assert "diag_q1" in assessments
    assert assessments["diag_q1"].score == 0.0
    # Must have advanced to next question
    assert res["diagnostic_state"]["current_question_id"] == "diag_q2"
    assert res["pending_question"]["question_id"] == "diag_q2"


def test_bug_b_custom_topic_generates_rich_explanation_without_contamination():
    """
    BUG B: For custom topics (e.g. 'guardrails', 'Quantum mechanics'):
    - Mode 2 explanation length >= 350 characters
    - Must NOT contain hard-coded Binary Search or phonebook analogies
    - Has 2 worked examples and question bank
    """
    custom_topic = "guardrails"
    custom_concept = "input_validation_safety"

    ped_data = get_subtopic_pedagogical_data(custom_topic, custom_concept)
    assert ped_data is not None
    assert len(ped_data.get("worked_examples", [])) >= 2
    assert len(ped_data.get("question_bank", [])) >= 3

    explanation = generate_mode_2_explanation(custom_topic, custom_concept, ped_data)
    assert len(explanation) >= 350, f"Explanation too short: {len(explanation)}"

    # Contamination checks
    lower_exp = explanation.lower()
    assert "phonebook" not in lower_exp, "Found phonebook analogy in custom topic!"
    assert "telephone directory" not in lower_exp, "Found phonebook in custom topic!"
    assert "binary search" not in lower_exp, "Found Binary Search in custom topic!"
    assert "arr[mid]" not in lower_exp, "Found array index notation in custom topic!"
    assert "left pointer" not in lower_exp, "Found pointer notation in custom topic!"

    # Verify check question selection works for custom topic
    cq = select_check_question(custom_topic, custom_concept, correct_checks=0, subtopic_data=ped_data)
    assert cq is not None
    assert cq.get("difficulty_tier") == 1
    assert "question" in cq
