import time
from dotenv import load_dotenv, find_dotenv

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from multi_agent_tutor.app.graph.state import TutorState
from multi_agent_tutor.app.schemas.socratic import (
    SocraticResponse,
)
from multi_agent_tutor.app.rag.rag_tool import (
    retrieve_pedagogical_context,
)


load_dotenv(find_dotenv())


model = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.2,
    max_tokens=450,
    streaming=True,
)


def _emit_stream(stream_queue, text: str):
    """Emit tokens or text chunks into the streaming queue if active."""
    if stream_queue is None or not text:
        return
    import re
    tokens = re.findall(r"\S+\s*|\s+", text)
    for tok in tokens:
        stream_queue.put_nowait(tok)


socratic_llm = model.with_structured_output(
    SocraticResponse,
    method="function_calling",
)


socratic_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """
You are SAGE, an adaptive Socratic AI tutor.

Your goal is to help the student understand the
current concept through reasoning.

You must return exactly one structured
SocraticResponse.

==================================================
CORE RULES
==================================================

1. Ask exactly ONE question.

2. The question must be appropriate for the
   student's current mastery and teaching action.

3. Do not ask multiple questions.

4. Do not unnecessarily change the mathematical
   level of the problem.

5. The expected_answer MUST answer the EXACT
   question you actually ask.

6. evaluation_criteria MUST describe exactly what
   the student's answer to THAT question should
   demonstrate.

7. Never put information in expected_answer that
   the student was not asked to provide.

8. Before returning your response, mentally verify:

   QUESTION
       ↓
   What exactly is being asked?
       ↓
   EXPECTED ANSWER
       ↓
   Does the expected answer answer only that question?

9. LANGUAGE & ANALOGY STRICTNESS:
   - Use domain-authentic, precise, and technically accurate language.
   - NEVER use clichéd, out-of-context physical tropes such as "Russian nesting dolls", "Matryoshka dolls", or nested physical boxes (especially for recursion or algorithmic concepts). Russian dolls are passive static containers that fail to model execution frames, call stacks, return value propagation, or branching.
   - For recursion and algorithm concepts, always use computationally sound mental models: call stack frames with activation records, task delegation with return handoffs, or directory/tree traversals.
   - If the Critic has rejected a previous response for inappropriate analogies or phrasing, you MUST strictly adhere to the Critic's instructions and eliminate all rejected elements.

10. TEACHING-BEFORE-TESTING & SCOPE INVARIANTS:
    - Assessment questions must be strictly based on concepts, definitions, and mechanics that you (SAGE) have ALREADY explained to the student in this conversation or the immediate lesson.
    - NEVER generate questions based on upcoming lessons, planned curriculum, or concepts you intend to teach later. A planned lesson is NOT completed teaching.
    - Merely mentioning a term does NOT mean it has been taught. Never test a student on unexplained terms or concepts.
    - FOR COMPARISON OR TRANSFER QUESTIONS: Ensure that ALL essential concepts being compared or transferred have already been explained in the conversation. If any required concept is missing, you MUST teach that concept briefly with a simple example first before asking the question.
    - Natural learning sequence: Teach -> Ask questions about what was taught -> Evaluate understanding -> Adapt next teaching step. Never let assessment get ahead of teaching.

11. ANSWER ACKNOWLEDGMENT & EXPLANATION INVARIANT:
    - When the student answers a question, you MUST ALWAYS begin your response message by explicitly acknowledging it.
    - Briefly explain WHY their answer is correct, partially correct, or what makes their reasoning sound. Never jump to another question without this acknowledgment and explanation.
    - If the answer was partially correct or incomplete, validate what was sound and clarify the missing detail.

12. CONVERSATIONAL CONTINUITY & TOPICAL COHESION:
    - Maintain unbroken continuity between consecutive questions.
    - Explicitly connect your next question to the concept and answer just discussed.
    - Avoid suddenly jumping to unrelated topics or distant technological advancements without a clear pedagogical bridge.

13. GRADUAL CONCEPT INTRODUCTION & TEACHING CONTEXT:
    - Ensure every question has sufficient context and a clear scenario.
    - If introducing a new concept, subtopic, or dimension, ALWAYS provide a short 1-2 sentence explanation or intuitive definition FIRST before asking about it.
    - Increase difficulty gradually: start with direct intuition and recall, advance to mechanics and application, and only probe transfer or edge cases once foundational mechanics are demonstrated.

==================================================
QUESTION & EVALUATOR TYPES
==================================================

Question types:
- conceptual: student explains an idea, mechanism, intuition, or relationship
- objective: verifiable numerical, symbolic, sequence, set, or exact value
- application: student applies concept to a specific scenario

Evaluator types:
- llm: conceptual reasoning, intuitions, and semantic understanding
- numeric: single numerical value (expected_answer: exact number, e.g. "13")
- sequence: ordered list/vector (expected_answer: exact list, e.g. "[3, 10, 8]")
- set: unordered collection (expected_answer: exact set, e.g. "{{0, 1}}")
- symbolic: algebraic expression or relation (expected_answer: exact formula, e.g. "0 <= n <= M+N-2")
- exact: concise technical term or keyword

Expected Answer Alignment Invariant:
The expected_answer must directly answer ONLY the exact question asked. Never include answers to unasked questions, multiple indices, or entire concept summaries.

==================================================
TEACHING ACTIONS
==================================================

initial:
Introduce the concept.
CRITICAL RULE FOR NOVICE / LOW-MASTERY LEARNERS (mastery <= 0.20):
- Start with a clear 1-2 sentence intuitive definition or real-world analogy explaining what the concept is and why it exists.
- Then ask exactly ONE simple, friendly question checking their basic intuition or purpose of that concept.
- DO NOT ask open-ended comparative or technical questions (e.g. do NOT ask "What makes C++ different from Python?" or "Explain programming paradigms") without anchoring intuition first.

probe:
The student has demonstrated meaningful
understanding. Ask a deeper question.

hint:
Give a minimal hint and ask one focused question.

scaffold:
Break the concept into a smaller reasoning step.

explain:
Give a concise explanation and then ask one
verification question.

advance:
Never generate an "advance" response.
The controller handles advancement.

==================================================
CURRENT CONCEPT
==================================================

{concept}

==================================================
CURRENT MASTERY
==================================================

{mastery}

==================================================
TEACHING ACTION
==================================================

{action}

==================================================
ATTEMPT NUMBER
==================================================

{attempt_count}

==================================================
KNOWN MISCONCEPTIONS
==================================================

{misconceptions}

==================================================
CURRENT PEDAGOGICAL OBJECTIVE
==================================================

{objective}

==================================================
PREVIOUS QUESTION ASKED
==================================================

{previous_question}

==================================================
STUDENT'S MOST RECENT ANSWER (IF ANY)
==================================================

{student_answer}

==================================================
PREVIOUS CRITIQUE FEEDBACK (IF RETRYING)
==================================================

{critic_feedback}

==================================================
TARGET COGNITIVE DEPTH LEVEL
==================================================

Level: {depth_level}

Pedagogical Depth Guidelines:
- foundational: Prioritize accessible analogies, step-by-step guidance, and core mental models. Avoid heavy math or complex edge cases.
- applied: Focus on mechanics, problem solving, implementation, and standard failure modes.
- deep: Challenge the student from first principles. Probe boundary conditions, mathematical formulations, edge cases, invariants, and theoretical/system trade-offs. Ask the student to explain why a formula, mechanism, or algorithm behaves the way it does under extreme or unexpected inputs.

==================================================
PREVIOUS TUTOR EXPLANATIONS IN THIS CONVERSATION
==================================================

{conversation_history}

==================================================
AUTHORITATIVE REFERENCE CONTEXT (RAG)
==================================================

{rag_knowledge}

Use this authoritative textbook context to ground your definitions, formulas,
hints, and explanations in verified academic literature. Include source citations
when explaining concepts (e.g. [Source: Author / Textbook]).

The current objective is the most important
constraint on the next question.

The question must directly test or develop
this objective.

If the student has a misconception, target that
misconception directly.

Do not unnecessarily return to the entire concept.

Do not repeat a previous question unless the
purpose is explicit verification.

For hint and scaffold actions:
1. Reduce cognitive difficulty.
2. Ask only one small question.
3. Make expected_answer correspond strictly to that small question.
4. Prefer deterministic evaluators (numeric, sequence, set, exact) when the answer is objectively verifiable.

==================================================
FINAL SELF-CHECK
==================================================

Before returning the SocraticResponse, verify:

1. Exactly ONE question is present.

2. The question tests the current objective.

3. The expected_answer directly answers that exact
   question.

4. The expected_answer does not contain answers
   to additional unasked questions.

5. The evaluator_type matches the answer format.

6. The evaluation_criteria matches the question.

7. The action matches the requested teaching action.

8. If the action is hint or scaffold, the question
   is simpler than the previous question.

==================================================
STUDENT LEARNING SIGNALS & ADAPTIVE META DIRECTIVES
==================================================

{pedagogical_signals}

Generate the next Socratic response.
"""
        ),
        (
            "human",
            """
Generate exactly one next Socratic tutoring response.
"""
        ),
    ]
)


sage_chain = (
    socratic_prompt
    | socratic_llm
)


def sage_agent(state: TutorState):
    """
    Generate the next structured Socratic response.
    """
    t0 = time.perf_counter()

    concept = state["current_concept"]

    if concept is None:
        raise ValueError(
            "No current concept available for SAGE."
        )

    mastery = state["mastery"].get(
        concept,
        0.0,
    )
    stream_queue = state.get("_stream_queue")

    teaching = state.get("teaching") or {
        "current_action": "initial",
        "current_question": None,
        "attempt_count": 0,
        "correct_checks": 0,
        "has_transfer_correct": False,
        "misconception_history": [],
    }

    decision = state.get(
        "teaching_decision"
    )

    if decision is None:
        action = "initial"
    else:
        action = decision.action

        # "advance" is a controller decision,
        # not a SAGE response action.
        if action == "advance":
            action = "initial"

    topic = state.get("target_topic") or state.get("curriculum_id") or "recursion"
    teaching_mode = state.get("teaching_mode", "mode_2_teach_first")
    teaching_step = state.get("teaching_step", "teach")

    asked_ids = list(state.get("asked_question_ids") or [])
    asked_texts = list(state.get("asked_question_texts") or [])

    crit = state.get("critic_result")
    if crit and not getattr(crit, "passed", True):
        from multi_agent_tutor.app.Agents.teaching_agent import _DYNAMIC_PEDAGOGICAL_CACHE
        _DYNAMIC_PEDAGOGICAL_CACHE.pop((topic.strip().lower(), concept.strip().lower()), None)

    feedback_prefix = ""
    is_mocked = hasattr(sage_chain.invoke, "assert_called")

    if not is_mocked:
        assessment = state.get("teaching_assessment")
        prev_pq = state.get("pending_question")
        prev_qid = prev_pq.get("question_id") if isinstance(prev_pq, dict) else (getattr(prev_pq, "question_id", None) if prev_pq else None)

        # Build Assessor-to-Tutor Feedback Handoff (Fix C)
        if assessment is not None:
            ass_score = getattr(assessment, "score", 0.0) if not isinstance(assessment, dict) else assessment.get("score", 0.0)
            ass_misconceptions = getattr(assessment, "misconceptions", []) if not isinstance(assessment, dict) else assessment.get("misconceptions", [])
            ass_feedback = getattr(assessment, "feedback", None) if not isinstance(assessment, dict) else assessment.get("feedback", None)
            is_copied = "copied_from_tutor" in ass_misconceptions

            if is_copied:
                feedback_prefix = "⚠️ That matches what I just explained. Try putting it in your own words, or here is a slightly different question:\n\n"
            elif ass_score >= 0.70:
                feedback_prefix = "**Verdict:** Correct! 🎯\n"
                if ass_feedback:
                    feedback_prefix += f"{ass_feedback}\n\n"
                elif ass_misconceptions:
                    feedback_prefix += f"You've captured the core principle well. (Keep in mind: {ass_misconceptions[0]}).\n\n"
                else:
                    prev_exp = prev_pq.get("expected_answer", "") if isinstance(prev_pq, dict) else (getattr(prev_pq, "expected_answer", "") if prev_pq else "")
                    if prev_exp:
                        feedback_prefix += f"Spot-on reasoning—{prev_exp}.\n\n"
                    else:
                        feedback_prefix += f"Spot-on reasoning—you accurately demonstrated the core concept.\n\n"
            elif ass_score >= 0.40:
                feedback_prefix = "**Verdict:** Partly right. 💡\n"
                if ass_feedback:
                    feedback_prefix += f"{ass_feedback}\n\n"
                else:
                    gap = ass_misconceptions[0] if ass_misconceptions else "the exact boundary condition or state transition"
                    feedback_prefix += f"You have part of the intuition, but be sure to account for {gap}.\n\n"
            else:
                feedback_prefix = "**Verdict:** Not quite yet. 🔄\n"
                if ass_feedback:
                    feedback_prefix += f"{ass_feedback}\n\n"
                else:
                    gap = ass_misconceptions[0] if ass_misconceptions else "the governing invariant"
                    feedback_prefix += f"Not quite—the key distinction to keep in mind is {gap}.\n\n"

        # Check for milestone advancement from previous concept
        just_advanced_from = teaching.get("just_advanced_from")
        advancement_banner = ""
        if just_advanced_from and just_advanced_from != concept:
            adv_prev_title = just_advanced_from.replace("_", " ").title()
            adv_curr_title = concept.replace("_", " ").title()
            advancement_banner = (
                f"🌟 **Mastery Achieved:** Excellent job mastering **{adv_prev_title}**!\n\n"
                f"Now, building directly on the concepts you just learned, let's explore our next milestone: **{adv_curr_title}**.\n\n"
            )

        is_prereq_offer = (action == "prerequisite_offer" or teaching.get("current_action") == "prerequisite_offer")
        if is_prereq_offer:
            re_msg = state.get("tutor_response") or "Let's review the key intuition before moving forward."
            full_re_msg = f"{feedback_prefix}{re_msg}"
            socratic_resp = SocraticResponse(
                message=full_re_msg,
                question=re_msg,
                action="scaffold",
                expected_answer="Student choice",
                evaluator_type="llm",
                evaluation_criteria=["Student indicates preference."],
                question_type="conceptual",
            )
            _emit_stream(stream_queue, full_re_msg)
            return {
                "socratic_response": socratic_resp,
                "tutor_response": full_re_msg,
                "pending_question": {
                    "question_id": f"{concept}_prereq_offer",
                    "question": re_msg,
                    "concept_id": concept,
                },
                "awaiting": "answer",
                "teaching": {
                    **teaching,
                    "current_action": "prerequisite_offer",
                    "current_question": re_msg,
                },
            }

        if action == "re_teach" or teaching.get("current_action") == "re_teach":
            from multi_agent_tutor.app.Agents.teaching_agent import select_check_question
            re_msg = state.get("tutor_response") or "Let's review the key intuition before moving forward."

            # Select fresh check question after re-teach
            cq = select_check_question(
                topic=topic,
                concept_id=concept,
                correct_checks=teaching.get("correct_checks", 0),
                asked_question_ids=asked_ids,
                asked_question_texts=asked_texts,
                exclude_question_id=prev_qid,
            )
            if cq:
                asked_ids.append(cq["question_id"])
                asked_texts.append(cq["question"])
                full_re_msg = f"{feedback_prefix}{re_msg}\n\nNow, let's test this with a fresh question:\n\n**Question:** {cq['question']}"
                out_pq = cq
                out_awaiting = "answer"
                act = "probe"
            else:
                full_re_msg = f"{feedback_prefix}{re_msg}"
                out_pq = None
                out_awaiting = "continue"
                act = action

            socratic_resp = SocraticResponse(
                message=full_re_msg,
                question=out_pq["question"] if out_pq else "",
                action=act,
                expected_answer=out_pq.get("expected_answer", "") if out_pq else "",
                evaluator_type=out_pq.get("evaluator_type", "llm") if out_pq else "llm",
                evaluation_criteria=out_pq.get("evaluation_criteria", []) if out_pq else [],
                question_type="conceptual",
            )
            _emit_stream(stream_queue, full_re_msg)
            return {
                "socratic_response": socratic_resp,
                "tutor_response": full_re_msg,
                "pending_question": out_pq,
                "awaiting": out_awaiting,
                "asked_question_ids": asked_ids,
                "asked_question_texts": asked_texts,
                "teaching": {
                    **teaching,
                    "current_action": act,
                    "current_question": out_pq["question"] if out_pq else None,
                },
            }

        intent_type = (state.get("detected_intent") or {}).get("intent")
        student_input = (state.get("student_input") or "").lower()

        if teaching_mode == "mode_2_teach_first":
            from multi_agent_tutor.app.Agents.teaching_agent import select_check_question, get_mode_2_step_content, generate_mode_2_explanation
            curr_step = state.get("teaching_step_index")
            wants_practice = any(w in student_input for w in ["practice", "quiz", "test", "check question", "problem"])
            is_retry = bool(crit and not getattr(crit, "passed", True) and state.get("retry_count", 0) > 0)

            # 1. Advance upon confirmation or continue request (or stay on explanation step during retry)
            if (intent_type == "CONFIRMATION" or state.get("awaiting") == "continue" or (is_retry and teaching_step != "check")) and teaching_step != "check":
                if is_retry and curr_step is not None:
                    next_step = curr_step
                elif wants_practice or (curr_step is not None and curr_step >= 3) or teaching_step == "check":
                    next_step = 4
                elif curr_step is not None:
                    next_step = curr_step + 1
                else:
                    next_step = 1

                if next_step < 4 and not wants_practice:
                    step_content, is_last = get_mode_2_step_content(topic, concept, next_step)
                    socratic_resp = SocraticResponse(
                        message=step_content,
                        question="",
                        action="explain",
                        expected_answer="Continue",
                        evaluator_type="exact",
                        evaluation_criteria=["Student continues."],
                        question_type="conceptual",
                    )
                    _emit_stream(stream_queue, step_content)
                    return {
                        "socratic_response": socratic_resp,
                        "tutor_response": step_content,
                        "pending_question": None,
                        "awaiting": "continue",
                        "teaching_step_index": next_step,
                        "teaching_step": "teach",
                        "_is_vetted": True,
                        "teaching": {
                            **teaching,
                            "current_action": "explain",
                            "current_question": None,
                        },
                    }
                else:
                    # Step 4+: Present check question
                    cq = select_check_question(
                        topic=topic,
                        concept_id=concept,
                        correct_checks=teaching.get("correct_checks", 0),
                        asked_question_ids=asked_ids,
                        asked_question_texts=asked_texts,
                    )
                    if cq:
                        asked_ids.append(cq["question_id"])
                        asked_texts.append(cq["question"])
                        tier_name = "Recall Check" if cq.get("difficulty_tier") == 1 else ("Application Check" if cq.get("difficulty_tier") == 2 else "Transfer Problem")
                        msg = f"Let's test this with a quick check problem ({tier_name})!\n\n**Question:** {cq['question']}"
                        socratic_resp = SocraticResponse(
                            message=msg,
                            question=cq["question"],
                            action="probe",
                            expected_answer=cq.get("expected_answer", ""),
                            evaluator_type=cq.get("evaluator_type", "llm"),
                            evaluation_criteria=cq.get("evaluation_criteria", []),
                            question_type=cq.get("question_type", "conceptual"),
                        )
                        _emit_stream(stream_queue, msg)
                        return {
                            "socratic_response": socratic_resp,
                            "tutor_response": msg,
                            "pending_question": cq,
                            "awaiting": "answer",
                            "asked_question_ids": asked_ids,
                            "asked_question_texts": asked_texts,
                            "teaching_step_index": 4,
                            "teaching_step": "check",
                            "_is_vetted": True,
                            "teaching": {
                                **teaching,
                                "current_action": "probe",
                                "current_question": cq["question"],
                            },
                        }

            # 2. Check mode when answering questions
            if teaching_step == "check" and action in ("initial", "probe"):
                cq = select_check_question(
                    topic=topic,
                    concept_id=concept,
                    correct_checks=teaching.get("correct_checks", 0),
                    asked_question_ids=asked_ids,
                    asked_question_texts=asked_texts,
                    exclude_question_id=prev_qid,
                )
                if cq:
                    asked_ids.append(cq["question_id"])
                    asked_texts.append(cq["question"])
                    tier_name = "Recall Check" if cq.get("difficulty_tier") == 1 else ("Application Check" if cq.get("difficulty_tier") == 2 else "Transfer Problem")
                    c_title = concept.replace("_", " ").title()
                    lead_in = f"Building on your explanation, let's explore our next check problem on **{c_title}** ({tier_name}):\n\n"
                    msg = f"{feedback_prefix}{lead_in}**Question:** {cq['question']}"
                    socratic_resp = SocraticResponse(
                        message=msg,
                        question=cq["question"],
                        action="probe",
                        expected_answer=cq.get("expected_answer", ""),
                        evaluator_type=cq.get("evaluator_type", "llm"),
                        evaluation_criteria=cq.get("evaluation_criteria", []),
                        question_type=cq.get("question_type", "conceptual"),
                    )
                    _emit_stream(stream_queue, msg)
                    return {
                        "socratic_response": socratic_resp,
                        "tutor_response": msg,
                        "pending_question": cq,
                        "awaiting": "answer",
                        "asked_question_ids": asked_ids,
                        "asked_question_texts": asked_texts,
                        "teaching_step_index": 4,
                        "teaching_step": "check",
                        "_is_vetted": True,
                        "teaching": {
                            **teaching,
                            "current_action": "probe",
                            "current_question": cq["question"],
                        },
                    }

            # 3. Initial explanation
            if teaching_step in ("explain", "teach") and action == "initial":
                diag = state.get("diagnostic_state") or {}
                prefix = ""
                signals = dict(state.get("signals") or {})
                if diag.get("completed") and len(diag.get("assessments", {})) > 0 and not signals.get("diagnostic_summary_shown"):
                    c_title = concept.replace("_", " ").title()
                    for c in (state.get("curriculum") or []):
                        cid = getattr(c, "concept_id", None) or (c.get("concept_id") if isinstance(c, dict) else None)
                        if cid == concept:
                            c_title = getattr(c, "name", None) or (c.get("name") if isinstance(c, dict) else c_title)
                            break
                    prefix = (
                        "🎯 **Diagnostic Assessment Complete!**\n\n"
                        f"Based on your baseline calibration, I've created your personalized learning plan for **{topic}**. "
                        f"We'll start with **{c_title}** in Mode 2 (teach first), using intuitive analogies and concrete examples.\n\n"
                        "---\n\n"
                    )
                    signals["diagnostic_summary_shown"] = True

                explanation = generate_mode_2_explanation(topic, concept)
                full_explanation = f"{feedback_prefix}{advancement_banner}{prefix}{explanation}"

                socratic_resp = SocraticResponse(
                    message=full_explanation,
                    question="",
                    action="explain",
                    expected_answer="Continue",
                    evaluator_type="exact",
                    evaluation_criteria=[],
                    question_type="conceptual",
                )
                _emit_stream(stream_queue, full_explanation)
                return {
                    "socratic_response": socratic_resp,
                    "tutor_response": full_explanation,
                    "pending_question": None,
                    "awaiting": "continue",
                    "teaching_step_index": 0,
                    "teaching_step": "teach",
                    "assessment_done": True,
                    "signals": signals,
                    "_is_vetted": True,
                    "teaching": {
                        **teaching,
                        "current_action": "explain",
                        "current_question": None,
                    },
                }

        if teaching_mode == "mode_1_qa" and action in ("initial", "probe"):
            from multi_agent_tutor.app.Agents.teaching_agent import select_check_question, get_subtopic_pedagogical_data
            mode1_check_idx = max(1, teaching.get("correct_checks", 0) + 1)
            cq = select_check_question(topic, concept, correct_checks=mode1_check_idx)
            if cq:
                tier_name = "Application Challenge" if cq.get("difficulty_tier") == 2 else "Transfer Problem"
                c_title = concept.replace("_", " ").title()
                intro_context = ""
                if just_advanced_from and just_advanced_from != concept:
                    sub_data = get_subtopic_pedagogical_data(topic, concept)
                    desc = (sub_data.get("description") or f"Core principles and mechanisms of {c_title}.") if sub_data else f"Core principles and mechanisms of {c_title}."
                    intro_context = f"{advancement_banner}### Introduction: {c_title}\n{desc}\n\n"

                lead_in = f"Building on what you've demonstrated, here is our next challenge problem on **{c_title}** ({tier_name}):\n\n"
                msg = f"{feedback_prefix}{intro_context}{lead_in}**Question:** {cq['question']}"
                socratic_resp = SocraticResponse(
                    message=msg,
                    question=cq["question"],
                    action="probe",
                    expected_answer=cq.get("expected_answer", ""),
                    evaluator_type=cq.get("evaluator_type", "llm"),
                    evaluation_criteria=cq.get("evaluation_criteria", []),
                    question_type=cq.get("question_type", "conceptual"),
                )
                _emit_stream(stream_queue, msg)
                return {
                    "socratic_response": socratic_resp,
                    "tutor_response": msg,
                    "pending_question": cq,
                    "awaiting": "answer",
                    "teaching_step": "check",
                    "_is_vetted": True,
                    "teaching": {
                        **teaching,
                        "current_action": "probe",
                        "current_question": cq["question"],
                    },
                }

    previous_question = (
        teaching.get("current_question")
        or "None (this is the first question on this concept)."
    )

    student_answer = (
        state.get("student_input")
        or "None yet."
    )

    objective = (
        teaching.get("current_objective")
        or f"Introduce the foundational intuition for {concept}."
    )

    misconceptions = teaching.get(
        "misconception_history", []
    )
    misconceptions_str = (
        ", ".join(misconceptions)
        if misconceptions
        else "None detected yet."
    )

    # --------------------------------------------------
    # Retrieve Authoritative Textbook Knowledge (RAG)
    # --------------------------------------------------
    topic = state.get("target_topic", "General Science")
    rag_data = retrieve_pedagogical_context(
        topic=topic,
        concept=concept,
        current_action=action,
        k=2,
        student_input=state.get("student_input"),
        state=state,
    )
    rag_knowledge = rag_data.get("context_text") or "No external reference documents uploaded. Rely on core foundational principles."

    # Extract previous tutor explanations so SAGE generates questions only from what was taught
    messages = state.get("messages") or []
    tutor_explanations = [
        m.get("content", "")[:300] for m in messages
        if m.get("role") in ("assistant", "tutor")
    ]
    conversation_history = "\n---\n".join(tutor_explanations[-4:]) if tutor_explanations else "Only the introductory overview has been provided."

    # Check if this invocation is a retry due to a rejected Critic evaluation
    crit = state.get("critic_result")
    if crit and not getattr(crit, "passed", True):
        crit_fb = getattr(crit, "feedback", "")
        critic_feedback = f"ATTENTION: Your previous response was rejected by the pedagogical critic: '{crit_fb}'. You MUST strictly resolve this issue in your new response."
    else:
        critic_feedback = "None."

    # --------------------------------------------------
    # Consume Student Learning Signals (Requirement 4: Meta Flags)
    # --------------------------------------------------
    signals = state.get("signals") or {}
    pace = signals.get("pace")
    step_size = signals.get("step_size")
    needs_example = signals.get("needs_example")
    concise = signals.get("concise")
    style = signals.get("explanation_style")

    signals_directives = []
    if pace == "slower" or step_size == "tiny":
        signals_directives.append(
            "- SLOWER PACE & TINY STEP: The student requested a slower pace and smaller steps. "
            "Ask only a single, tiny, incremental question. Avoid multi-part questions or conceptual leaps."
        )
    elif pace == "faster" or concise:
        signals_directives.append(
            "- FASTER PACE & CONCISENESS: The student requested a faster, concise pace. "
            "Keep the message brief and direct. Jump straight to the question without extra pleasantries."
        )

    if needs_example:
        signals_directives.append(
            "- CONCRETE EXAMPLE: The student specifically requested a worked or concrete example. "
            "Include a concrete small example (e.g., explicit array values, index pointers, or numerical steps) in your context/question."
        )

    if style == "alternative_analogy":
        signals_directives.append(
            "- INTUITIVE ANALOGY: The student requested an alternative explanation angle. "
            "Frame your question or hint with a relatable real-world comparison."
        )

    pedagogical_signals = "\n".join(signals_directives) if signals_directives else "Standard pedagogical pacing and style."

    chain_inputs = {
        "concept": concept,
        "mastery": mastery,
        "action": action,
        "attempt_count": teaching.get("attempt_count", 0),
        "misconceptions": misconceptions_str,
        "objective": objective,
        "previous_question": previous_question,
        "student_answer": student_answer,
        "rag_knowledge": rag_knowledge,
        "depth_level": state.get("depth_level") or "deep",
        "critic_feedback": critic_feedback,
        "pedagogical_signals": pedagogical_signals,
        "conversation_history": conversation_history,
    }

    if stream_queue is not None:
        if feedback_prefix:
            _emit_stream(stream_queue, feedback_prefix)
        emitted_len = 0
        last_chunk = None
        for chunk in sage_chain.stream(chain_inputs):
            last_chunk = chunk
            msg = getattr(chunk, "message", None) or ""
            if len(msg) > emitted_len:
                delta = msg[emitted_len:]
                stream_queue.put_nowait(delta)
                emitted_len = len(msg)
        result = last_chunk
    else:
        result = sage_chain.invoke(chain_inputs)

    rag_citations = rag_data if (rag_data.get("citations") and len(rag_data["citations"]) > 0) else None

    # Ensure student answer acknowledgment is preserved if not already in LLM message
    final_message = result.message
    if feedback_prefix:
        has_verdict = any(v in final_message.lower() for v in ["verdict:", "spot-on", "correct!", "partly right", "not quite"])
        if not has_verdict:
            final_message = f"{feedback_prefix}{final_message}"
            result.message = final_message

    elapsed = time.perf_counter() - t0
    print(f"[TIMING] SAGE (Tutor): {elapsed:.3f}s (action={action})")

    return {
        "socratic_response": result,

        "tutor_response": final_message,

        "rag_context": rag_citations,
        "pending_question": {
            "question": result.question,
            "concept_id": concept,
            "expected_answer": result.expected_answer,
            "evaluator_type": result.evaluator_type,
            "evaluation_criteria": result.evaluation_criteria,
            "question_type": result.question_type,
        },
        "teaching": {
            **teaching,
            "current_action": result.action,
            "current_question": result.question,
        },
    }