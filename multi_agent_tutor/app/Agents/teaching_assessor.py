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


# ==========================================================
# MODEL
# ==========================================================

model = ChatOpenAI(
    model="gpt-5-mini",
    temperature=0.2,
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

Do NOT assume knowledge that the student did not
demonstrate.

==================================================
EXACT QUESTION
==================================================

You MUST evaluate the answer against the exact
question that was asked.

Do not evaluate a broader question that the student
was not asked.

For example:

Question:
"What index of x is used when evaluating x[-n]
at n=-3?"

Student:
"3"

This is correct.

Do NOT expect the student to explain all of
time reversal unless the question asks for it.

==================================================
EXPECTED ANSWER
==================================================

The expected answer is a reference, not necessarily
a literal string that the student must reproduce.

Mathematical equivalence and equivalent wording
must receive credit.

For example:

Expected:
y[n] = sum from k=-infinity to infinity of
x[k]h[n-k]

Student:
y[n]=(x*h)[n]=sum(x[k]h[n-k])

This is mathematically equivalent and should
receive strong credit.

Another example:

Expected:
"The convolution output has indices 0 through
M+N-2."

Student:
"The minimum n is 0 and the maximum is M+N-2."

This is correct.

Another example:

Expected:
"Multiply corresponding overlapping samples and
sum the products."

Student:
"At each shift, multiply the overlapping values
and add all the products."

This is correct.

==================================================
SYMBOLIC MATHEMATICS
==================================================

For symbolic mathematical answers, evaluate the
mathematical meaning rather than literal text.

Recognize equivalent:

- notation
- LaTeX forms
- algebraic forms
- variable naming where appropriate
- equivalent summation notation
- equivalent mathematical expressions

Do NOT mark a mathematically equivalent answer
wrong merely because formatting differs.

For example:

Expected:
y[n] = sum x[k]h[n-k]

Student:
y[n] = (x*h)[n]

This can be correct if the question asks for
the convolution expression and the notation is
mathematically sufficient.

However, if the question specifically asks for
the expanded summation form, evaluate whether the
student actually provided the required expansion.

==================================================
NUMERICAL CALCULATIONS AND SHORT ANSWERS
==================================================

When the question asks for a calculation, numerical result, sequence, or specific term:

1. Look for the student's final result or calculation within their response.
2. If the student gives the correct numerical value or sequence (e.g. 10 or [2, 5, 8, 3]), award full credit (score 1.0, understanding 'mastered').
3. Do NOT penalize the student if they also include steps, explanations, formulas, or conversational context alongside the number (e.g. "y[1] = 10 because 1*4 + 2*3 = 10").
4. If the student shows the correct method and reasoning but made a minor arithmetic error, award partial credit (score 0.5 - 0.7, understanding 'partial').

==================================================
MATHEMATICAL DERIVATIONS & REASONING (WHY QUESTIONS)
==================================================

When the question asks why an operation occurs (such as why convolution flips one signal, or the role of indices like h[n-k]):

1. Credit equivalent algebraic explanations:
   - For example: recognizing that in y[n] = sum x[k] h[n-k], the -k index means h[k] is time-reversed to h[-k] and then shifted by n (i.e. h[-k+n] = h[n-k]).
2. Credit equivalent intuitive explanations:
   - For example: explaining that reversing makes samples of h line up with x in opposing directions so as one slides across the other, each overlap is accumulated properly.
3. If the student explains both the algebraic reversal (the -k) and the sliding/matching intuition, this is EXCELLENT reasoning. Award score 0.95 - 1.0, understanding 'mastered', and reasoning_quality 'strong'.
4. Do NOT mark such answers wrong or invent misconceptions merely because their phrasing differs from expected_answer.

==================================================
MARKDOWN, LATEX, AND FORMATTING
==================================================

The student may use LaTeX math ($$...$$, \\(...\\)), bullet points, bold text, or line breaks.
Focus entirely on the semantic mathematical meaning, never on formatting style.

==================================================
SCORE
==================================================

The score represents the quality of the student's
demonstrated understanding of THIS question.

Use approximately:

1.0
    Fully correct and well-reasoned.

0.8-0.99
    Correct with a minor omission or limited detail.

0.6-0.79
    Substantially correct but missing an important
    part of the requested reasoning.

0.4-0.59
    Partial understanding with significant gaps.

0.2-0.39
    Weak understanding.

0.0-0.19
    Incorrect, irrelevant, or no meaningful attempt.

Do not give a high score merely because the student
used some correct terminology.

==================================================
UNDERSTANDING
==================================================

The understanding field must agree with the score.

Use:

mastered
    Strongly correct answer demonstrating the
    required understanding.

good
    Correct answer with minor limitations.

partial
    Some correct understanding but meaningful gaps.

weak
    Limited understanding.

incorrect
    Incorrect or no meaningful understanding.

==================================================
CONSISTENCY
==================================================

All fields MUST agree.

NEVER produce:

understanding = mastered
score = 1.0
misconceptions = ["student is wrong"]

That is contradictory.

If the student has a substantive error, the
assessment must reflect that error.

If the student is correct, do NOT invent a
misconception.

==================================================
MISCONCEPTIONS
==================================================

Only include misconceptions actually supported
by the student's answer.

Do NOT turn missing detail into a misconception.

Bad:

Student:
"M+N"

Question:
"Why is convolution length M+N-1?"

Misconception:
"Student does not understand convolution."

This is too broad.

Better:

"Off-by-one error when determining the inclusive
convolution output length."

Only identify a technical misconception if the
student's answer provides evidence for it.

==================================================
REASONING QUALITY
==================================================

Use:

strong
    Correct reasoning with a clear explanation.

partial
    Some correct reasoning but incomplete or unclear.

weak
    Incorrect reasoning, unsupported answer, or
    no meaningful reasoning.

For a question requiring only a numerical answer,
do not penalize the student for not providing a
long explanation if the question did not ask for one.

==================================================
CONFIDENCE
==================================================

Confidence represents how certain you are about
your assessment.

Use:

0.9-1.0
    Clearly correct or clearly incorrect.

0.7-0.89
    Mostly clear but with some ambiguity.

0.4-0.69
    Significant ambiguity.

Do not artificially use high confidence for an
ambiguous response.

==================================================
NO ANSWER / I DON'T KNOW
==================================================

If the student says:

"I don't know"
"I dont know"
"I don't understand"
"not sure"
"no idea"

or gives no meaningful answer:

understanding = incorrect

score = approximately 0.0

reasoning_quality = weak

confidence = high

The misconception should describe the lack of
demonstrated understanding.

Do NOT invent a technical misconception.

For example:

"No meaningful understanding was demonstrated."

==================================================
IMPORTANT DISTINCTION
==================================================

Do not confuse:

missing explanation

with

incorrect understanding.

If the question asks:

"What is the convolution result?"

and the student gives the correct result,
they can receive full credit even without a
long explanation.

If the question asks:

"Explain why convolution reverses one signal."

and the student only gives a formula without
explaining the reversal, the answer is incomplete.

==================================================
PREVIOUS MISCONCEPTIONS
==================================================

Previous misconceptions are context only.

Do not automatically assume they are present
in the current answer.

The student's CURRENT answer is the primary evidence.

==================================================
FINAL CHECK
==================================================

Before returning the assessment, verify:

1. Did I evaluate the exact question?

2. Is the student's answer mathematically correct?

3. Did I allow equivalent mathematical notation?

4. Does the score agree with understanding?

5. Does reasoning_quality agree with the answer?

6. Are misconceptions actually supported?

7. Did I avoid inventing a misconception?

8. Did I avoid assuming knowledge not demonstrated?

9. If the student said "I don't know", did I mark
   the response as incorrect/very low score?

10. Am I returning ONLY TeachingAssessment?

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

    Deterministic evaluation is used for answers where
    correctness can be reliably verified using a formal
    rule.

    LLM evaluation is used for:

        - conceptual questions
        - application questions
        - symbolic mathematical reasoning
        - semantic/explanatory answers

    Every assessment passes through a consistency
    validation layer before reaching BKT.
    """

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

    # Fast-path for explicit 'don't know' / unknowledgeable responses
    from multi_agent_tutor.app.Agents.assessment import is_dont_know_response
    if is_dont_know_response(student_answer):
        result = TeachingAssessment(
            understanding="incorrect",
            score=0.0,
            confidence=1.0,
            reasoning_quality="weak",
            misconceptions=["No prior knowledge demonstrated"],
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

    return return_state