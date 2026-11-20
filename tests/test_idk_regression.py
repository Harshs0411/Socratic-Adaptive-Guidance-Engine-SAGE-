import pytest
from unittest.mock import patch, MagicMock
from multi_agent_tutor.app.graph.state import TutorState
from multi_agent_tutor.app.Agents.doubt_agent import doubt_agent_node, handle_doubt_question
from multi_agent_tutor.app.Agents.intent_classifier import pre_filter_intent
from multi_agent_tutor.app.schemas.diagnostic import DiagnosticQuestion


def test_intent_classification_idk_and_variants():
    """Verify intent classifier classifies 'I don't know' and variants as DOUBT / help_request."""
    inputs_to_verify = [
        "I don't know",
        "i dont know",
        "I'm not sure",
        "not sure",
        "idk",
        "no idea",
    ]
    for user_input in inputs_to_verify:
        intent_res = pre_filter_intent(
            message=user_input,
            has_pending_question=True,
            pending_clarity_check=False,
            awaiting="answer",
        )
        assert intent_res is not None, f"Failed to classify: {user_input}"
        assert intent_res.intent == "DOUBT", f"Expected DOUBT for '{user_input}', got {intent_res.intent}"
        assert intent_res.meta_subintent == "help_request", f"Expected help_request for '{user_input}'"


def test_intent_classification_confirmation():
    """Verify intent classifier classifies 'I understand' as CONFIRMATION."""
    intent_res = pre_filter_intent(
        message="I understand",
        has_pending_question=True,
        pending_clarity_check=True,
        awaiting="clarity_check",
    )
    assert intent_res is not None
    assert intent_res.intent == "CONFIRMATION"


def test_intent_classification_normal_answer():
    """Verify normal answer attempts are classified as ANSWER_ATTEMPT."""
    intent_res = pre_filter_intent(
        message="The loop terminates because left exceeds right",
        has_pending_question=True,
        pending_clarity_check=False,
        awaiting="answer",
    )
    assert intent_res is not None
    assert intent_res.intent == "ANSWER_ATTEMPT"


def test_idk_teaching_check_question_no_unbound_local():
    """
    Regression test for:
    'cannot access local variable actual_doubt where it is not associated with a value'
    Ensures 'I don't know' in teaching check phase runs cleanly through doubt_agent_node.
    """
    state: TutorState = {
        "student_id": "test_student",
        "target_topic": "Binary Search",
        "current_subtopic": "pointer_movement",
        "teaching_mode": "mode_2_teach_first",
        "teaching_step": "check",
        "pending_question": {
            "question_id": "check_q1",
            "question": "What is the update rule for high when arr[mid] > target?",
            "expected_answer": "high = mid - 1",
            "difficulty_tier": 1,
        },
        "student_input": "I don't know",
        "detected_intent": {
            "intent": "DOUBT",
            "confidence": 0.95,
            "meta_subintent": "help_request",
        },
        "doubt_state": {
            "doubt_stack": [],
            "doubt_log": [],
            "pending_clarity_check": False,
        },
        "teaching": {
            "attempt_count": 0,
        },
        "hint_level_per_question": {},
    }

    mock_llm_response = MagicMock()
    mock_llm_response.content = "Remember that mid has already been checked. Since arr is sorted, target must be to the left."

    with patch("multi_agent_tutor.app.Agents.doubt_agent._doubt_chain") as mock_chain, \
         patch("multi_agent_tutor.app.Agents.doubt_agent._model") as mock_model:
        mock_chain.invoke.return_value = mock_llm_response
        mock_model.invoke.return_value = mock_llm_response
        res = doubt_agent_node(state)

    assert res is not None
    assert "tutor_response" in res
    assert "socratic_response" in res
    assert "💡" in res["tutor_response"] or "hint" in res["tutor_response"].lower()
    # Check that pending question is preserved with hint level tracked
    assert res["pending_question"]["question_id"] == "check_q1"
    assert res["pending_question"]["hint_given"] is True
    assert res["hint_level_per_question"]["check_q1"] == 1
    assert res["awaiting"] == "answer"


def test_im_not_sure_diagnostic_no_unbound_local():
    """
    Ensures 'I'm not sure' during diagnostic question runs cleanly through doubt_agent_node.
    """
    q1 = DiagnosticQuestion(
        question_id="diag_q1",
        concept="binary_search_bounds",
        question="Why do we initialize high to n - 1?",
        difficulty="beginner",
        question_type="conceptual",
        reason="Check 0-indexed bounds knowledge",
        evaluation_criteria=["Mentions 0-indexing"],
    )
    state: TutorState = {
        "student_id": "test_student",
        "target_topic": "Binary Search",
        "current_subtopic": "boundary_conditions",
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
        "student_input": "I'm not sure",
        "detected_intent": {
            "intent": "DOUBT",
            "confidence": 0.95,
            "meta_subintent": "help_request",
        },
        "doubt_state": {
            "doubt_stack": [],
            "doubt_log": [],
            "pending_clarity_check": False,
        },
    }

    mock_llm_response = MagicMock()
    mock_llm_response.content = "Think about 0-indexed arrays."

    with patch("multi_agent_tutor.app.Agents.doubt_agent._doubt_chain") as mock_chain, \
         patch("multi_agent_tutor.app.Agents.doubt_agent._model") as mock_model:
        mock_chain.invoke.return_value = mock_llm_response
        mock_model.invoke.return_value = mock_llm_response
        res = doubt_agent_node(state)

    assert res is not None
    assert "No worries at all! Here's a small hint" in res["tutor_response"]
    assert res["diagnostic_state"]["hints_given"]["diag_q1"] is True
    assert res["pending_question"]["question_id"] == "diag_q1"
    assert res["awaiting"] == "answer"
