from dotenv import load_dotenv, find_dotenv

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from multi_agent_tutor.app.graph.state import TutorState

from multi_agent_tutor.app.schemas.teaching_assessment import (
    TeachingAssessment,
)

from multi_agent_tutor.app.utils.objective_evaluator import (
    evaluate_objective_answer,
)


load_dotenv(find_dotenv())


import time

# ==========================================================
# MODEL
# ==========================================================

model = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.1,
    max_tokens=300,
)


assessment_llm = model.with_structured_output(
    TeachingAssessment,
    method="function_calling",
)


# ==========================================================
# LLM ASSESSMENT PROMPT
# ==========================================================

assessment_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """
You are the Teaching Assessment Agent for SAGE.

Your ONLY job is to evaluate the student's answer
to the exact question asked by SAGE.

You are NOT the tutor.

Do not teach the student.
Do not provide a new question.
Do not rewrite the student's answer.

Return ONLY a structured TeachingAssessment.

==================================================
WHAT YOU MUST EVALUATE
==================================================

Evaluate only what the student actually demonstrated.

Consider:

1. Correctness
2. Conceptual understanding
3. Quality of reasoning
4. Important misconceptions
5. Whether the student has enough understanding
   to proceed
6. Feedback explanation: In the 'feedback' field, provide a concise 1-2 sentence
   explanation explicitly acknowledging the student's answer and explaining WHY it
   is correct or what makes their reasoning sound. If partially correct or incorrect,
   constructively explain what specific mechanism or detail was missing.

Do NOT assume knowledge that the student did not
demonstrate.

==================================================
EVALUATION PRINCIPLES & EQUIVALENCE
==================================================

1. EXACT QUESTION SCOPE:
   - Evaluate against the exact question asked. Never penalize for omitted unasked details.
   - Do not confuse a missing unsolicited explanation with incorrect understanding.

2. EQUIVALENCE & SEMANTIC CREDIT:
   - Symbolic & Math: Credit equivalent algebraic forms, summation notation, LaTeX ($$...$$), and variable names.
   - Numerical & Objective: If the correct value or sequence is present, award full credit (1.0, 'mastered'), even if accompanied by workings or conversational context. If method is sound with a minor arithmetic error, award partial credit (0.5 - 0.7, 'partial').
   - Reasoning / Explanations: Credit sound intuition, mechanisms, and physical/computational models even if phrased differently from expected_answer.

3. SCORING & UNDERSTANDING LEVELS:
   - 1.0 (mastered): Fully correct and soundly reasoned.
   - 0.80 - 0.99 (good): Correct with minor omission or limited detail.
   - 0.50 - 0.79 (partial): Substantially correct but missing an important part of the requested reasoning.
   - 0.20 - 0.49 (weak): Partial intuition with significant errors or gaps.
   - 0.00 - 0.19 (incorrect): Incorrect, irrelevant, or no meaningful attempt.

4. REASONING QUALITY:
   - strong: Correct reasoning with clear explanation.
   - partial: Some correct reasoning but incomplete or unclear.
   - weak: Incorrect reasoning, unsupported answer, or no attempt.

5. MISCONCEPTIONS & CONSISTENCY:
   - All fields MUST agree: never produce mastered + misconceptions.
   - Only include specific misconceptions directly evidenced in the answer. Never invent a misconception.
   - Previous misconceptions are background context only; current answer is primary evidence.

6. NO ANSWER / "I DON'T KNOW":
   - If student expresses inability to answer ("I don't know", "not sure", "no idea"):
     understanding="incorrect", score=0.0, reasoning_quality="weak", confidence=1.0.

7. FINAL SELF-CHECK:
   - Did I evaluate the exact question?
   - Did I credit equivalent mathematical/semantic formulations?
   - Do score, understanding, and reasoning_quality agree consistently?
   - Is the 'feedback' explanation constructive, clear, and acknowledging of the student's reasoning?

==================================================
CURRENT INPUT
==================================================

Evaluate the following:

Current concept:
{concept}

Question:
{question}

Expected answer:
{expected_answer}

Evaluation criteria:
{evaluation_criteria}

Student answer:
{student_answer}

Known misconceptions from previous attempts:
{misconceptions}

Deterministic check reference (if applicable, your semantic judgment takes precedence):
{advisory_check}
"""
        ),
        (
            "human",
            """
Evaluate the student's response and return the
structured TeachingAssessment.
"""
        ),
    ]
)


assessment_chain = (
    assessment_prompt
    | assessment_llm
)


# ==========================================================
# VALIDATION
# ==========================================================

def _validate_assessment(
    result: TeachingAssessment,
) -> TeachingAssessment:
    """
    Enforce basic consistency between assessment fields.

    This protects the learner model from contradictory
    LLM output.
    """

    score = result.score

    understanding = result.understanding

    misconceptions = list(
        result.misconceptions
    )

    reasoning_quality = result.reasoning_quality

    confidence = result.confidence

    # ------------------------------------------------------
    # Score bounds by understanding
    # ------------------------------------------------------

    if understanding == "mastered":

        score = max(
            score,
            0.85,
        )

    elif understanding == "good":

        score = max(
            0.70,
            min(
                score,
                0.99,
            ),
        )

    elif understanding == "partial":

        score = min(
            score,
            0.79,
        )

    elif understanding == "weak":

        score = min(
            score,
            0.49,
        )

    elif understanding == "incorrect":

        score = min(
            score,
            0.39,
        )

    # ------------------------------------------------------
    # Contradiction protection
    # ------------------------------------------------------

    if (
        understanding == "mastered"
        and misconceptions
    ):

        understanding = "good"

        score = min(
            score,
            0.84,
        )

        if reasoning_quality == "strong":

            reasoning_quality = "partial"

    # ------------------------------------------------------
    # Incorrect + strong reasoning is suspicious.
    #
    # Strong reasoning can exist with an incorrect
    # conclusion, but for the current learner model
    # we avoid treating it as strong overall evidence.
    # ------------------------------------------------------

    if (
        understanding == "incorrect"
        and score < 0.40
        and reasoning_quality == "strong"
    ):

        reasoning_quality = "partial"

    # ------------------------------------------------------
    # Clamp numerical fields
    # ------------------------------------------------------

    score = max(
        0.0,
        min(
            1.0,
            score,
        ),
    )

    confidence = max(
        0.0,
        min(
            1.0,
            confidence,
        ),
    )

    return TeachingAssessment(
        understanding=understanding,

        score=score,

        confidence=confidence,

        misconceptions=misconceptions,

        reasoning_quality=reasoning_quality,
    )


# ==========================================================
# MAIN ASSESSMENT AGENT
# ==========================================================

def assess_teaching_response(
    state: TutorState
):
    """
    Evaluate a student's response.
    """
    t0 = time.perf_counter()

    concept = state["current_concept"]

    if concept is None:

        raise ValueError(
            "No current concept available."
        )

    response = state.get("pending_question") or state.get("socratic_response")

    if response is None:

        raise ValueError(
            "No Socratic response available."
        )

    student_answer = state[
        "student_input"
    ]

    if not student_answer:

        raise ValueError(
            "No student answer received."
        )

    evaluator_type = getattr(response, "evaluator_type", None) or (response.get("evaluator_type") if isinstance(response, dict) else "llm")
    resp_question = getattr(response, "question", None) or (response.get("question") if isinstance(response, dict) else "")
    resp_expected = getattr(response, "expected_answer", None) or (response.get("expected_answer") if isinstance(response, dict) else "")
    resp_criteria = getattr(response, "evaluation_criteria", None) or (response.get("evaluation_criteria") if isinstance(response, dict) else [])

    # Check for teaching gap claims: never penalize a student for a teaching gap!
    from multi_agent_tutor.app.Agents.intent_classifier import TEACHING_GAP_PATTERNS
    import re
    if any(re.search(p, student_answer, re.IGNORECASE) for p in TEACHING_GAP_PATTERNS):
        result = TeachingAssessment(
            understanding="neutral",
            score=1.0,
            confidence=1.0,
            reasoning_quality="Student identified a teaching gap; no penalty applied.",
            misconceptions=[],
        )
        return {
            "teaching_assessment": result,
        }

    # Fast-path for explicit 'don't know' / unknowledgeable responses
    from multi_agent_tutor.app.Agents.assessment import is_dont_know_response
    from multi_agent_tutor.app.config import DONT_KNOW_EVIDENCE_FLOOR
    if is_dont_know_response(student_answer):
        result = TeachingAssessment(
            understanding="incorrect",
            score=DONT_KNOW_EVIDENCE_FLOOR,
            confidence=0.85,
            reasoning_quality="Student expressed uncertainty / requested guidance.",
            misconceptions=[],
            feedback="The student indicated they are unsure and would like guided scaffolding.",
        )
        return {
            "teaching_assessment": result,
        }

    # ======================================================
    # ADVISORY DETERMINISTIC CHECK (NON-BLOCKING)
    # ======================================================
    advisory_check = "No deterministic check requested."
    deterministic_evaluators = {
        "numeric",
        "sequence",
        "set",
        "exact",
    }

    if evaluator_type in deterministic_evaluators:
        try:
            correct, feedback = evaluate_objective_answer(
                evaluator_type=evaluator_type,
                expected_answer=resp_expected,
                student_answer=student_answer,
            )
            advisory_check = (
                f"Evaluator '{evaluator_type}' check: correct={correct}, feedback='{feedback}'"
            )
        except Exception as exc:
            advisory_check = (
                f"Evaluator '{evaluator_type}' could not parse cleanly ({exc}). "
                "Evaluate the student's answer using semantic reasoning."
            )

    # ======================================================
    # LLM SEMANTIC EVALUATION (UNIVERSAL)
    # ======================================================

    result = assessment_chain.invoke(
        {
            "concept": concept,
            "question": resp_question,
            "expected_answer": resp_expected,
            "evaluation_criteria": resp_criteria,
            "student_answer": student_answer,
            "misconceptions": (state.get("teaching") or {}).get("misconception_history", []),
            "advisory_check": advisory_check,
        }
    )

    result = _validate_assessment(
        result
    )

    # Universal hint ladder scaling and copy detection (Fix D)
    pq = state.get("pending_question")
    qid = ""
    if isinstance(pq, dict):
        qid = pq.get("question_id", "")
    elif isinstance(response, dict):
        qid = response.get("question_id", "")
    elif hasattr(response, "question_id"):
        qid = getattr(response, "question_id", "")

    hint_levels = dict(state.get("hint_level_per_question") or {})
    h_level = hint_levels.get(qid, 0)
    signals = state.get("signals", {}) or {}
    hint_given = bool(isinstance(response, dict) and response.get("hint_given")) or bool(signals.get("hint_used")) or bool(signals.get("hints_used"))
    if hint_given and h_level == 0:
        h_level = 1

    max_caps = {0: 1.0, 1: 0.5, 2: 0.5, 3: 0.3, 4: 0.15}
    cap = max_caps.get(h_level, 0.15 if h_level >= 4 else 1.0)
    if hint_given:
        cap = min(cap, 0.5)
    if result.score > cap:
        result.score = min(result.score, cap)

    # Copy detection (Fix D)
    from multi_agent_tutor.app.Agents.teaching_agent import check_copy_detection
    last_tutor_msg = state.get("tutor_response") or ""
    is_copied, sim_score = check_copy_detection(student_answer, last_tutor_msg)
    if is_copied and len(student_answer.strip()) > 3:
        result.score = min(result.score, 0.2)
        if "copied_from_tutor" not in result.misconceptions:
            result.misconceptions.append("copied_from_tutor")

    # Record question attempt history
    q_attempts = dict(state.get("question_attempts") or {})
    q_results = dict(state.get("question_results") or {})
    if qid:
        q_attempts[qid] = q_attempts.get(qid, 0) + 1
        res_list = list(q_results.get(qid, []))
        res_list.append({
            "score": result.score,
            "understanding": result.understanding,
            "student_answer": student_answer,
            "hint_level": h_level,
            "copied": is_copied,
        })
        q_results[qid] = res_list

    return_state = {
        "teaching_assessment": result,
        "question_attempts": q_attempts,
        "question_results": q_results,
        "student_input": None,
    }

    # Implicit confirmation (B.2): If student answered while clarity check was pending,
    # pop the checkpoint and reset pending_clarity_check.
    doubt_state = state.get("doubt_state")
    if doubt_state and doubt_state.get("pending_clarity_check"):
        updated_doubt = dict(doubt_state)
        stack = list(updated_doubt.get("doubt_stack", []))
        if stack:
            stack.pop()
        updated_doubt["doubt_stack"] = stack
        updated_doubt["pending_clarity_check"] = False
        return_state["doubt_state"] = updated_doubt

    elapsed = time.perf_counter() - t0
    print(f"[TIMING] TeachingAssessor: {elapsed:.3f}s (understanding={result.understanding}, score={result.score})")
    return return_state