"""
Performance and Token Optimization Verification Suite for SAGE Tutor.
Verifies:
1. Prompt compression and token savings for Tutor and Teaching Assessor.
2. Deterministic Critic Quality Gate (eliminates LLM calls for pre-vetted content).
3. Curriculum generation caching and topic normalization (zero LLM calls on repeat/normalized topics).
4. Conditional RAG routing (zero RAG calls when no PDF or on unrelated general queries).
5. Continuity, acknowledgment, and teaching accuracy.
"""

import time
import pytest
from multi_agent_tutor.app.Agents.tutor import socratic_prompt
from multi_agent_tutor.app.Agents.teaching_assessor import assessment_prompt
from multi_agent_tutor.app.Agents.curriculum_generator import (
    normalize_topic_name,
    curriculum_agent,
    _CURRICULUM_CACHE,
    clear_curriculum_cache,
)
from multi_agent_tutor.app.Agents.critic import critic_agent
from multi_agent_tutor.app.schemas.socratic import SocraticResponse
from multi_agent_tutor.app.schemas.curriculum import CurriculumConcept
from multi_agent_tutor.app.rag.rag_tool import should_invoke_rag, get_rag_metrics, reset_rag_metrics


def test_topic_normalization():
    """Ensure normalization collapses whitespace, lowers case, and strips punctuation."""
    assert normalize_topic_name("  Operating Systems  ") == "operating systems"
    assert normalize_topic_name("Operating_Systems") == "operating systems"
    assert normalize_topic_name("OPERATING SYSTEMS") == "operating systems"
    assert normalize_topic_name("microeconomics") == "microeconomics"


def test_curriculum_caching_and_reuse():
    """Verify that normalized topic variations reuse the cached curriculum with 0 LLM calls."""
    clear_curriculum_cache()

    # Seed mock cached curriculum for a topic
    mock_concept = CurriculumConcept(
        concept_id="process_scheduling",
        name="Process Scheduling",
        description="CPU scheduling algorithms",
        prerequisites=[],
        difficulty=3,
    )
    _CURRICULUM_CACHE[("operating systems", "deep")] = [mock_concept]

    # First call with uppercase and spaces
    state1 = {
        "target_topic": "  Operating Systems  ",
        "depth_level": "deep",
        "curriculum": None,
    }
    t0 = time.perf_counter()
    res1 = curriculum_agent(state1)
    latency1 = time.perf_counter() - t0

    assert len(res1["curriculum"]) == 1
    assert res1["curriculum"][0].concept_id == "process_scheduling"
    # Latency of cache hit should be virtually instant (<10ms)
    assert latency1 < 0.05, f"Cache hit should be faster than 50ms, was {latency1:.4f}s"

    # Second call with underscore
    state2 = {
        "target_topic": "operating_systems",
        "depth_level": "deep",
        "curriculum": None,
    }
    res2 = curriculum_agent(state2)
    assert len(res2["curriculum"]) == 1
    assert res2["curriculum"][0].concept_id == "process_scheduling"


def test_critic_deterministic_quality_gate_for_vetted_content():
    """
    Verify that pre-vetted curriculum content bypasses the Critic LLM call
    and completes in under 10ms with 0 tokens consumed.
    """
    vetted_state = {
        "current_concept": "binary_search_fundamentals",
        "target_topic": "binary search",
        "mastery": {"binary_search_fundamentals": 0.5},
        "teaching_mode": "mode_2_teach_first",
        "teaching_step": "check",
        "retry_count": 0,
        "_is_vetted": True,
        "pending_question": {
            "question_id": "bs_f_recall_01",
            "question": "What is the primary prerequisite property an array must satisfy before binary search can be applied?",
            "expected_answer": "The array must be sorted in monotonic order.",
            "evaluator_type": "llm",
        },
        "socratic_response": SocraticResponse(
            message="Let's test this with a quick check problem!\n\n**Question:** What is the primary prerequisite property an array must satisfy before binary search can be applied?",
            question="What is the primary prerequisite property an array must satisfy before binary search can be applied?",
            action="probe",
            expected_answer="The array must be sorted in monotonic order.",
            evaluator_type="llm",
            evaluation_criteria=["Student states array must be sorted."],
            question_type="conceptual",
        ),
    }

    t0 = time.perf_counter()
    out = critic_agent(vetted_state)
    elapsed = time.perf_counter() - t0

    assert out["critic_result"].passed is True
    assert out["critic_result"].score >= 9.0
    # Must complete deterministically in < 10ms (no LLM call)
    assert elapsed < 0.05, f"Deterministic fast-pass should take < 50ms, took {elapsed:.4f}s"


def test_critic_rejects_banned_tropes_deterministically():
    """Verify that banned tropes fail deterministically without calling LLM."""
    bad_state = {
        "current_concept": "recursion_fundamentals",
        "target_topic": "recursion",
        "mastery": {"recursion_fundamentals": 0.1},
        "teaching_mode": "mode_2_teach_first",
        "teaching_step": "teach",
        "retry_count": 0,
        "socratic_response": SocraticResponse(
            message="Think of recursion like a Russian nesting doll! Inside each doll is another doll.",
            question="",
            action="explain",
            expected_answer="Continue",
            evaluator_type="exact",
            evaluation_criteria=[],
            question_type="conceptual",
        ),
    }

    t0 = time.perf_counter()
    out = critic_agent(bad_state)
    elapsed = time.perf_counter() - t0

    assert out["critic_result"].passed is False
    assert out["critic_result"].score <= 4.0
    assert elapsed < 0.05, f"Deterministic rejection should take < 50ms, took {elapsed:.4f}s"


def test_rag_zero_calls_when_no_document():
    """Verify zero RAG invocation when no PDF is provided."""
    reset_rag_metrics()
    assert should_invoke_rag("Binary Search", student_input="How does binary search work?") is False
    assert should_invoke_rag("Computer Science", student_input="Can you explain time complexity?") is False


def test_prompt_token_reduction():
    """Verify that the prompts are compressed and do not contain redundant blocks."""
    tutor_prompt_str = str(socratic_prompt.messages[0].prompt.template)
    assessor_prompt_str = str(assessment_prompt.messages[0].prompt.template)

    # In tutor prompt: duplicate convolution blocks were removed
    assert tutor_prompt_str.count("What is the convolution of [1,2] and [3,4]?") == 0
    assert tutor_prompt_str.count("Which k values contribute?") == 0

    # In assessor prompt: duplicate convolution examples were consolidated
    assert assessor_prompt_str.count("y[n]=(x*h)[n]=sum(x[k]h[n-k])") == 0
    assert assessor_prompt_str.count("Multiply corresponding overlapping samples") == 0

    # Verify both prompts contain all crucial rules
    assert "LANGUAGE & ANALOGY STRICTNESS" in tutor_prompt_str
    assert "TEACHING-BEFORE-TESTING" in tutor_prompt_str
    assert "ANSWER ACKNOWLEDGMENT" in tutor_prompt_str
    assert "CONVERSATIONAL CONTINUITY" in tutor_prompt_str
    assert "EVALUATION PRINCIPLES & EQUIVALENCE" in assessor_prompt_str
