"""
Doubt Resolution Agent for SAGE Tutor (Requirement 3).
Handles student questions, confusions, help requests ("I don't know"),
and clarity confirmations.

Key Pedagogical Invariants:
1. Doubts NEVER update BKT mastery.
2. Checkpoints are pushed onto a doubt stack with max depth cap.
3. Every doubt explanation ends with a clarity verification:
   "Does that make sense, or should I explain it another way?"
4. Affirmative confirmation pops the checkpoint and resumes with a bridge:
   "Awesome, back to where we were..." and restates the pending question.
"""

import uuid
import re
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from multi_agent_tutor.app.config import DOUBT_STACK_MAX_DEPTH
from multi_agent_tutor.app.graph.state import TutorState
from multi_agent_tutor.app.schemas.socratic import SocraticResponse
from multi_agent_tutor.app.rag.rag_tool import retrieve_pedagogical_context


_model = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.3,
)

DOUBT_EXPLANATION_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        """You are the Patient Doubt-Resolution Tutor for SAGE.
The student has asked a question, expressed confusion, or asked for help while learning.

Your mission:
1. Answer the student's doubt directly, thoroughly, and warmly.
2. Use an intuitive analogy, a concrete mini-example, or step-by-step reasoning where helpful.
3. Ground your explanation in verified authoritative computer science literature.
4. NEVER quiz or interrogate the student inside this explanation.
5. Keep the tone encouraging, patient, and clear.
6. If the student said "I don't know" or requested help, reassure them warmly that this is completely normal, and break down the core concept into a simple, bite-sized intuition or hint.
7. If the student asked a mixed question (e.g. an answer attempt + a question), address their question first, acknowledging their answer warmly.
8. LANGUAGE & ANALOGY STRICTNESS: Use domain-authentic computational analogies (e.g. call stack frames, task delegation with return handoffs). NEVER use clichéd or misleading physical metaphors like 'Russian nesting dolls' for recursion.

Active Topic: {topic}
Active Subtopic: {subtopic}
Active Pending Question (which they paused): {pending_question}
Doubt Stack Depth: {stack_depth}
Authoritative Reference Context (RAG):
{rag_knowledge}

Write a helpful, pedagogical explanation. Do NOT include the final clarity check sentence (it will be formatted automatically).
"""
    ),
    (
        "human",
        "Student's doubt / confusion / question:\n\"{student_doubt}\""
    )
])

_doubt_chain = DOUBT_EXPLANATION_PROMPT | _model


def generate_safe_hint(
    topic: str,
    concept: str,
    question_text: str,
    expected_answer: str,
    raw_explanation: str,
) -> str:
    """
    Ensures a hint is at most 2 short sentences, a subtle nudge toward the idea,
    and does NOT reveal or contain key terms from the expected answer.
    """
    stopwords = {
        "the", "a", "an", "is", "are", "of", "to", "in", "for", "on", "with", "by",
        "and", "or", "it", "that", "this", "at", "from", "as", "be", "was", "were",
        "into", "each", "which", "what", "their", "have", "has", "can", "will", "header", "headers"
    }
    ans_words = set(re.findall(r"\b[a-zA-Z]{4,}\b", expected_answer.lower())) - stopwords

    def leaks_answer(text: str) -> bool:
        if not ans_words:
            return False
        text_lower = text.lower()
        matches = [w for w in ans_words if w in text_lower]
        return len(matches) >= 2 or any(len(w) >= 6 and w in text_lower for w in ans_words)

    # First check raw explanation sentences
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", raw_explanation) if s.strip()]
    candidate = " ".join(sentences[:2])

    if candidate and not leaks_answer(candidate) and len(candidate) <= 220:
        return candidate

    # Strict retry with LLM
    try:
        strict_prompt = (
            f"You are an AI tutor providing a small conceptual hint. "
            f"Subject: {topic}. Concept: {concept}. Question: {question_text}. "
            f"CRITICAL SAFETY RULE: You must NOT reveal or mention the answer terms: {', '.join(ans_words)}. "
            f"Give ONLY a subtle 1-to-2 sentence nudge that guides the student's reasoning without giving away the answer."
        )
        resp = _model.invoke(strict_prompt)
        text = resp.content.strip()
        resp_sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
        candidate = " ".join(resp_sentences[:2])
        if not leaks_answer(candidate) and candidate:
            return candidate
    except Exception:
        pass

    clean_c = concept.replace("_", " ").title() if concept else topic
    return f"Think about how {clean_c} coordinates structured information and standard boundaries between different layers."


def generate_guidance_hint(
    topic: str,
    concept: str,
    question_text: str,
    expected_answer: str,
    raw_explanation: str,
) -> str:
    """Level 2: Partial guidance (<= 3 sentences). Eliminates one wrong path, highlights governing rule."""
    stopwords = {"the", "a", "an", "is", "are", "of", "to", "in", "for", "on", "with", "by", "and", "or", "it", "that"}
    ans_words = set(re.findall(r"\b[a-zA-Z]{4,}\b", expected_answer.lower())) - stopwords
    try:
        prompt = (
            f"You are an AI tutor providing Level 2 guidance for a student. "
            f"Subject: {topic}. Concept: {concept}. Question: {question_text}. "
            f"Rule: Do NOT give away the answer terms: {', '.join(ans_words)}. "
            f"Write 2 to 3 sentences that rule out a common misstep and point clearly to the governing rule or principle."
        )
        resp = _model.invoke(prompt)
        text = resp.content.strip()
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
        return " ".join(sentences[:3])
    except Exception:
        clean_c = concept.replace("_", " ").title() if concept else topic
        return f"Avoid confusing the mechanism with unrelated system layers. In {clean_c}, the governing invariant strictly determines the outcome."


def generate_worked_step_hint(
    topic: str,
    concept: str,
    question_text: str,
    expected_answer: str,
    raw_explanation: str,
) -> str:
    """Level 3: Partial worked step. Shows how to start, leaves final step to the student."""
    stopwords = {"the", "a", "an", "is", "are", "of", "to", "in", "for", "on", "with", "by", "and", "or", "it", "that"}
    ans_words = set(re.findall(r"\b[a-zA-Z]{4,}\b", expected_answer.lower())) - stopwords
    try:
        prompt = (
            f"You are an AI tutor providing Level 3 scaffolding. "
            f"Subject: {topic}. Concept: {concept}. Question: {question_text}. "
            f"Show the first step of reasoning or set up the formula/distinction, but do NOT state the final answer ({', '.join(ans_words)}). "
            f"Keep it to 2 to 3 sentences."
        )
        resp = _model.invoke(prompt)
        text = resp.content.strip()
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
        return " ".join(sentences[:3])
    except Exception:
        clean_c = concept.replace("_", " ").title() if concept else topic
        return f"Step 1: Check the prerequisite input state for {clean_c}. Now, what state transition immediately follows?"


def handle_doubt_question(
    state: TutorState,
    student_msg: str,
    doubt_info: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Handles a student doubt or help request:
    1. Saves checkpoint to doubt_stack (with stored_attempt if mixed).
    2. Enforces stack depth cap (defers 4th doubt to log).
    3. Handles 'I don't know' / help request by giving hint and re-asking pending question.
    4. Handles 'still confused' / clarity negation with alternative angles and prereq offers.
    5. Grounds explanations in textbook RAG context.
    """
    topic = state.get("target_topic", "General")
    subtopic = state.get("current_subtopic")
    mode = state.get("teaching_mode", "mode_2_teach_first")
    step = state.get("teaching_step", "check")
    pending_q = state.get("pending_question")
    attempt_count = state.get("teaching", {}).get("attempt_count", 0)

    doubt_state = dict(state.get("doubt_state") or {})
    doubt_stack: List[Dict[str, Any]] = list(doubt_state.get("doubt_stack", []))
    doubt_log: List[Dict[str, Any]] = list(doubt_state.get("doubt_log", []))

    now_iso = datetime.now(timezone.utc).isoformat()
    subintent = doubt_info.get("meta_subintent") if doubt_info else None
    is_help_request = (subintent == "help_request")
    is_clarity_negation = (subintent == "clarity_negation")
    pq_text = pending_q.get("question", "None") if isinstance(pending_q, dict) else str(pending_q or "None")

    # 1. Check depth cap (C.3): 4th nested doubt gets saved to log and deferred
    if len(doubt_stack) >= DOUBT_STACK_MAX_DEPTH:
        doubt_log.append({
            "topic": topic,
            "subtopic": subtopic,
            "doubt_text": student_msg,
            "timestamp": now_iso,
            "deferred": True,
        })
        doubt_state["doubt_log"] = doubt_log
        cap_msg = (
            "We're exploring some great rabbit holes! But let's finish this one first, then we'll come back to that.\n\n"
            f"I've saved your question for later so we won't forget it. Shall we get back to our current question?"
        )
        doubt_state["pending_clarity_check"] = True
        return {
            "tutor_response": cap_msg,
            "socratic_response": SocraticResponse(
                message=cap_msg,
                question=cap_msg,
                action="explain",
                question_type="conceptual",
                expected_answer="Confirmation of clarity",
                evaluator_type="exact",
                evaluation_criteria=["Student acknowledges clarity."],
            ),
            "doubt_state": doubt_state,
            "student_input": None,
        }

    # 2. Check for Clarity Negation / "Still confused" (C.2)
    if is_clarity_negation:
        re_count = doubt_state.get("re_explain_count", 0) + 1
        doubt_state["re_explain_count"] = re_count

        if re_count >= 2:
            prereq_msg = (
                f"I completely understand! When a concept in {topic} feels stubborn, that usually means a foundational piece needs a quick refresher or we need a totally different angle.\n\n"
                f"Would you like to take a step back and revisit the foundational prerequisites, or try a concrete visual walkthrough?"
            )
            doubt_state["pending_clarity_check"] = True
            return {
                "tutor_response": prereq_msg,
                "socratic_response": SocraticResponse(
                    message=prereq_msg,
                    question=prereq_msg,
                    action="explain",
                    question_type="conceptual",
                    expected_answer="Student preference",
                    evaluator_type="llm",
                    evaluation_criteria=["Student indicates preference."],
                ),
                "doubt_state": doubt_state,
                "student_input": None,
            }

    # Retrieve RAG context to ground the explanation (C.5)
    rag_data = retrieve_pedagogical_context(
        topic=topic,
        concept=subtopic or topic,
        current_action="explain",
        k=2,
    )
    rag_text = rag_data.get("context_text") or "Standard textbook algorithmic principles."

    # Save checkpoint
    stored_attempt = doubt_info.get("attempt_part") if doubt_info and doubt_info.get("is_mixed") else None
    checkpoint = {
        "checkpoint_id": str(uuid.uuid4()),
        "topic": topic,
        "subtopic": subtopic,
        "teaching_mode": mode,
        "teaching_step": step,
        "pending_question": pending_q,
        "attempt_count": attempt_count,
        "doubt_text": student_msg,
        "stored_attempt": stored_attempt,
        "timestamp": now_iso,
    }
    doubt_stack.append(checkpoint)

    # Log the doubt (never affects BKT)
    doubt_log.append({
        "topic": topic,
        "subtopic": subtopic,
        "doubt_text": student_msg,
        "timestamp": now_iso,
    })

    # Generate patient explanation
    actual_doubt = doubt_info.get("doubt_part") if doubt_info and doubt_info.get("is_mixed") else student_msg

    try:
        response = _doubt_chain.invoke({
            "topic": topic,
            "subtopic": subtopic or "Overview",
            "pending_question": pq_text,
            "stack_depth": len(doubt_stack),
            "student_doubt": actual_doubt,
            "rag_knowledge": rag_text,
        })
        explanation_body = response.content.strip()
    except Exception as e:
        explanation_body = (
            f"Here is the key intuition: In {topic}, each step builds logically on the fundamental rules. "
            "Let's break it down simply."
        )

    # 3. Diagnostic Phase Overriding Invariant (BUG A)
    diag_state = state.get("diagnostic_state")
    is_diag = isinstance(diag_state, dict) and not diag_state.get("completed", False) and diag_state.get("current_question_id") is not None

    if is_diag:
        current_qid = diag_state["current_question_id"]
        diagnostic_state = dict(diag_state)
        hints_given = dict(diagnostic_state.get("hints_given") or {})

        if is_help_request:
            if not hints_given.get(current_qid):
                # RULE 1: First "I don't know" or hint click on a diagnostic question:
                # Give ONE small hint, then re-ask the SAME question. Mark hint_given=True.
                hints_given[current_qid] = True
                diagnostic_state["hints_given"] = hints_given
                doubt_state["doubt_stack"] = doubt_stack
                doubt_state["doubt_log"] = doubt_log
                doubt_state["pending_clarity_check"] = False

                exp_ans = pending_q.get("expected_answer", "") if isinstance(pending_q, dict) else ""
                hint_text = generate_safe_hint(topic, subtopic or topic, pq_text, exp_ans, explanation_body)

                full_message = (
                    f"No worries at all! Here's a small hint to point you in the right direction:\n\n"
                    f"💡 {hint_text}\n\n"
                    f"With that hint in mind, let's give the question another shot:\n\n"
                    f"**Question:** {pq_text}"
                )
                doubt_state["active_doubt_response"] = full_message
                socratic_resp = SocraticResponse(
                    message=full_message,
                    question=pq_text,
                    action="hint",
                    question_type="conceptual",
                    expected_answer=pending_q.get("expected_answer", "Correct response") if isinstance(pending_q, dict) else "Answer",
                    evaluator_type=pending_q.get("evaluator_type", "llm") if isinstance(pending_q, dict) else "llm",
                    evaluation_criteria=pending_q.get("evaluation_criteria", ["Correct understanding"]) if isinstance(pending_q, dict) else ["Correct understanding"],
                )
                pq_copy = dict(pending_q) if isinstance(pending_q, dict) else {"question": pq_text}
                pq_copy["hint_given"] = True
                return {
                    "tutor_response": full_message,
                    "socratic_response": socratic_resp,
                    "doubt_state": doubt_state,
                    "diagnostic_state": diagnostic_state,
                    "pending_question": pq_copy,
                    "awaiting": "answer",
                    "student_input": None,
                }
            else:
                # RULE 2: Second "I don't know" on that question:
                # - Treat the concept as unknown ("No problem at all, that tells me exactly where to begin!").
                # - Record low prior for that topic (score = 0.0) with zero penalty.
                # - Stop probing that topic.
                # - In the SAME tutor reply, present the NEXT diagnostic question (or final summary with first lesson).
                from multi_agent_tutor.app.schemas.assessment import AssessmentResult
                from multi_agent_tutor.app.Agents.next_question_shifting_id import advance_diagnostic
                from multi_agent_tutor.app.utils.diagnostic import get_question_by_id
                from multi_agent_tutor.app.utils.progress_tracker_question import get_diagnostic_progress

                answers = dict(diagnostic_state.get("answers") or {})
                assessments = dict(diagnostic_state.get("assessments") or {})
                answers[current_qid] = student_msg
                assessments[current_qid] = AssessmentResult(
                    correctness="incorrect",
                    score=0.0,
                    confidence=1.0,
                    evidence_of_understanding=[],
                    misconceptions=[],
                    feedback="Concept unknown during diagnostic baseline calibration.",
                )
                diagnostic_state["answers"] = answers
                diagnostic_state["assessments"] = assessments

                # Advance with stop probing current concept
                adv_res = advance_diagnostic({"diagnostic_state": diagnostic_state})
                diagnostic_state = adv_res.get("diagnostic_state", diagnostic_state)

                doubt_state["doubt_stack"] = doubt_stack
                doubt_state["doubt_log"] = doubt_log
                doubt_state["pending_clarity_check"] = False

                if not diagnostic_state.get("completed", False) and diagnostic_state.get("current_question_id"):
                    next_qid = diagnostic_state["current_question_id"]
                    next_q = get_question_by_id(diagnostic_state["questions"], next_qid)
                    progress = get_diagnostic_progress(diagnostic_state)
                    next_msg = (
                        "No problem at all, that tells me exactly where to begin! We'll make sure to explore that from the ground up.\n\n"
                        f"Let's move to our next diagnostic question:\n\n"
                        f"Diagnostic question {progress['answered_questions'] + 1} of {progress['total_questions']}\n\n"
                        f"{next_q.question}"
                    )
                    next_pq = {
                        "question_id": next_q.question_id,
                        "concept": next_q.concept,
                        "question": next_q.question,
                        "evaluation_criteria": next_q.evaluation_criteria,
                    }
                    socratic_resp = SocraticResponse(
                        message=next_msg,
                        question=next_q.question,
                        action="probe",
                        question_type=getattr(next_q, "question_type", "conceptual"),
                        expected_answer="Diagnostic response",
                        evaluator_type="llm",
                        evaluation_criteria=next_q.evaluation_criteria,
                    )
                    return {
                        "tutor_response": next_msg,
                        "socratic_response": socratic_resp,
                        "diagnostic_state": diagnostic_state,
                        "doubt_state": doubt_state,
                        "pending_question": next_pq,
                        "awaiting": "answer",
                        "student_input": None,
                    }
                else:
                    # Diagnostic is complete: transition to learner modeling, BKT, and first Mode 2 lesson!
                    from multi_agent_tutor.app.Agents.learner import build_learner_profile
                    from multi_agent_tutor.app.Agents.bkt_intializer import initialize_bkt_states
                    from multi_agent_tutor.app.Agents.learning_path_planner import build_learning_path
                    from multi_agent_tutor.app.Agents.teaching_agent import generate_mode_2_explanation

                    diagnostic_state["completed"] = True
                    diagnostic_state["current_question_id"] = None
                    curriculum = state.get("curriculum") or []

                    lp_profile_res = build_learner_profile({"diagnostic_state": diagnostic_state})
                    learner_profile = lp_profile_res.get("learner_profile")
                    bkt_init_res = initialize_bkt_states({
                        "learner_profile": learner_profile,
                        "curriculum": curriculum,
                        "target_topic": topic,
                    })
                    mastery_map = bkt_init_res.get("mastery", {})
                    bkt_states_map = bkt_init_res.get("bkt_states", {})

                    lp_res = build_learning_path({
                        "target_topic": topic,
                        "curriculum": curriculum,
                        "mastery": mastery_map,
                        "skipped_concepts": [],
                    })
                    learning_path = lp_res.get("learning_path")
                    first_cid = getattr(learning_path, "current_concept_id", None) or (curriculum[0].concept_id if curriculum else None)

                    first_explanation = generate_mode_2_explanation(topic, first_cid) if first_cid else ""
                    first_title = first_cid.replace("_", " ").title() if first_cid else topic
                    for c in curriculum:
                        cid = getattr(c, "concept_id", None) or (c.get("concept_id") if isinstance(c, dict) else None)
                        if cid == first_cid:
                            first_title = getattr(c, "name", None) or (c.get("name") if isinstance(c, dict) else first_title)
                            break

                    summary_msg = (
                        "No problem at all, that tells me exactly where to begin!\n\n"
                        "🎯 **Diagnostic Assessment Complete!**\n\n"
                        f"Based on your baseline calibration, I've created your personalized learning plan for **{topic}**. "
                        f"We'll start with **{first_title}** in Mode 2 (teach first), using intuitive analogies and concrete examples.\n\n"
                        "---\n\n"
                        f"{first_explanation}"
                    )
                    socratic_resp = SocraticResponse(
                        message=summary_msg,
                        question="",
                        action="explain",
                        question_type="conceptual",
                        expected_answer="",
                        evaluator_type="llm",
                        evaluation_criteria=[],
                    )
                    return {
                        "tutor_response": summary_msg,
                        "socratic_response": socratic_resp,
                        "diagnostic_state": diagnostic_state,
                        "doubt_state": doubt_state,
                        "pending_question": None,
                        "awaiting": "continue",
                        "teaching_step_index": 0,
                        "assessment_done": True,
                        "learner_profile": learner_profile,
                        "mastery": mastery_map,
                        "bkt_states": bkt_states_map,
                        "learning_path": learning_path,
                        "current_concept": first_cid,
                        "teaching_mode": "mode_2_teach_first",
                        "teaching_step": "check",
                        "student_input": None,
                    }
    # 4. Standard Flow (Both Diagnostic & Teaching Conceptual Doubts, or Teaching Help Requests)
    # 4a. Universal 4-Level Hint Ladder for Check Questions (Fix D)
    if is_help_request:
        from multi_agent_tutor.app.Agents.teaching_agent import select_check_question
        hint_levels = dict(state.get("hint_level_per_question") or {})
        qid = pending_q.get("question_id") if isinstance(pending_q, dict) else (getattr(pending_q, "question_id", None) or "current_q")
        curr_lvl = hint_levels.get(qid, 0) + 1
        hint_levels[qid] = curr_lvl
        exp_ans = pending_q.get("expected_answer", "") if isinstance(pending_q, dict) else ""

        asked_ids = list(state.get("asked_question_ids") or [])
        asked_texts = list(state.get("asked_question_texts") or [])

        if curr_lvl == 1:
            hint_text = generate_safe_hint(topic, subtopic or topic, pq_text, exp_ans, explanation_body)
            full_message = (
                f"No worries at all! Here's a small hint to point you in the right direction:\n\n"
                f"💡 {hint_text}\n\n"
                f"With that hint in mind, let's try the question again:\n\n**Question:** {pq_text}"
            )
            out_pq = dict(pending_q) if isinstance(pending_q, dict) else {"question": pq_text}
            out_pq["hint_given"] = True
            next_awaiting = "answer"
        elif curr_lvl == 2:
            hint_text = generate_guidance_hint(topic, subtopic or topic, pq_text, exp_ans, explanation_body)
            full_message = (
                f"Let's narrow down the focus:\n\n"
                f"💡 {hint_text}\n\n"
                f"Give it another shot:\n\n**Question:** {pq_text}"
            )
            out_pq = dict(pending_q) if isinstance(pending_q, dict) else {"question": pq_text}
            out_pq["hint_given"] = True
            next_awaiting = "answer"
        elif curr_lvl == 3:
            hint_text = generate_worked_step_hint(topic, subtopic or topic, pq_text, exp_ans, explanation_body)
            full_message = (
                f"Let's walk through the initial step together:\n\n"
                f"💡 {hint_text}\n\n"
                f"Can you complete the next step?\n\n**Question:** {pq_text}"
            )
            out_pq = dict(pending_q) if isinstance(pending_q, dict) else {"question": pq_text}
            out_pq["hint_given"] = True
            next_awaiting = "answer"
        else:
            # Level 4: Full explanation, THEN swap to a DIFFERENT question on the same concept!
            teaching_info = state.get("teaching") or {}
            correct_checks = teaching_info.get("correct_checks", 0)
            fresh_q = select_check_question(
                topic=topic,
                concept_id=subtopic or (state.get("current_concept") or topic),
                correct_checks=correct_checks,
                asked_question_ids=asked_ids,
                asked_question_texts=asked_texts,
                exclude_question_id=qid,
            )
            if fresh_q:
                out_pq = fresh_q
                asked_ids.append(fresh_q["question_id"])
                asked_texts.append(fresh_q["question"])
                full_message = (
                    f"Here is the complete walkthrough:\n\n{explanation_body}\n\n"
                    f"Now, let's try a fresh check problem on this concept to lock in the understanding:\n\n"
                    f"**Question:** {fresh_q['question']}"
                )
            else:
                out_pq = dict(pending_q) if isinstance(pending_q, dict) else {"question": pq_text}
                full_message = (
                    f"Here is the complete walkthrough:\n\n{explanation_body}\n\n"
                    f"Let's try this question again:\n\n**Question:** {pq_text}"
                )
            next_awaiting = "answer"

        doubt_state["doubt_stack"] = doubt_stack
        doubt_state["doubt_log"] = doubt_log
        doubt_state["pending_clarity_check"] = False
        doubt_state["active_doubt_response"] = full_message

        socratic_resp = SocraticResponse(
            message=full_message,
            question=out_pq.get("question", pq_text) if isinstance(out_pq, dict) else pq_text,
            action="hint" if curr_lvl < 4 else "probe",
            question_type="conceptual",
            expected_answer=out_pq.get("expected_answer", "Correct response") if isinstance(out_pq, dict) else "Answer",
            evaluator_type=out_pq.get("evaluator_type", "llm") if isinstance(out_pq, dict) else "llm",
            evaluation_criteria=out_pq.get("evaluation_criteria", ["Correct understanding"]) if isinstance(out_pq, dict) else ["Correct understanding"],
        )

        return {
            "tutor_response": full_message,
            "socratic_response": socratic_resp,
            "doubt_state": doubt_state,
            "pending_question": out_pq,
            "awaiting": next_awaiting,
            "hint_level_per_question": hint_levels,
            "asked_question_ids": asked_ids,
            "asked_question_texts": asked_texts,
            "student_input": None,
        }

    # 4b. Standard Teaching Doubt Explanation with clarity verification prompt
    clarity_check = "\n\nDoes that make sense, or should I explain it another way?"
    full_message = explanation_body + clarity_check

    doubt_state["doubt_stack"] = doubt_stack
    doubt_state["doubt_log"] = doubt_log
    doubt_state["pending_clarity_check"] = True
    doubt_state["active_doubt_response"] = full_message

    socratic_resp = SocraticResponse(
        message=full_message,
        question="",
        action="explain",
        question_type="conceptual",
        expected_answer="Yes / Makes sense / Need another way",
        evaluator_type="exact",
        evaluation_criteria=["Student confirms clarity or asks for re-explanation."],
    )

    return {
        "tutor_response": full_message,
        "socratic_response": socratic_resp,
        "doubt_state": doubt_state,
        "awaiting": "clarity_check",
        "pending_question": state.get("pending_question"),
        "student_input": None,
    }


def handle_clarity_confirmation(state: TutorState) -> Dict[str, Any]:
    """
    Handles student confirmation ("ok", "got it", "makes sense", "yes") after a doubt:
    1. Pops the checkpoint from doubt_stack.
    2. Resets pending_clarity_check = False.
    3. Resets re_explain_count = 0.
    4. Builds a warm resume bridge:
       "Awesome, back to where we were..." and restates pending question
       (referencing stored_attempt if this was a mixed message).
    """
    doubt_state = dict(state.get("doubt_state") or {})
    doubt_stack: List[Dict[str, Any]] = list(doubt_state.get("doubt_stack", []))

    if doubt_stack:
        resolved_checkpoint = doubt_stack.pop()
    else:
        resolved_checkpoint = None

    doubt_state["doubt_stack"] = doubt_stack
    doubt_state["pending_clarity_check"] = False
    doubt_state["re_explain_count"] = 0

    # Check if there is still a pending question from the checkpoint or state
    pending_q = None
    if resolved_checkpoint and resolved_checkpoint.get("pending_question"):
        pending_q = resolved_checkpoint["pending_question"]
    elif state.get("pending_question"):
        pending_q = state.get("pending_question")

    stored_attempt = resolved_checkpoint.get("stored_attempt") if resolved_checkpoint else None

    q_text = ""
    if isinstance(pending_q, dict):
        q_text = pending_q.get("question", "")
    elif pending_q:
        q_text = str(pending_q)

    topic = state.get("target_topic", "General")
    subtopic = state.get("current_subtopic") or (resolved_checkpoint.get("subtopic") if resolved_checkpoint else None)

    if q_text:
        if stored_attempt:
            bridge_msg = (
                f"Awesome, glad that's clear! Earlier you mentioned: '{stored_attempt}'. "
                f"Now that we've cleared up that question, let's return to where we were:\n\n"
                f"**Question:** {q_text}"
            )
        else:
            bridge_msg = (
                f"Awesome, glad that's clear! Let's get right back to where we were:\n\n"
                f"**Question:** {q_text}"
            )
        socratic_resp = SocraticResponse(
            message=bridge_msg,
            question=q_text,
            action="probe",
            question_type="conceptual",
            expected_answer=pending_q.get("expected_answer", "Correct response") if isinstance(pending_q, dict) else "Answer",
            evaluator_type=pending_q.get("evaluator_type", "llm") if isinstance(pending_q, dict) else "llm",
            evaluation_criteria=pending_q.get("evaluation_criteria", ["Correct understanding"]) if isinstance(pending_q, dict) else ["Correct understanding"],
        )
        awaiting = "answer"
        out_pending_q = pending_q
    else:
        curr_sub = subtopic or state.get("current_concept")
        c_title = curr_sub.replace("_", " ").title() if curr_sub else topic
        bridge_msg = (
            f"Awesome, glad that's clear! Let's continue our lesson on **{c_title}**.\n\n"
            f"Click **Continue** when you're ready for the next step, or let me know if you have another question!"
        )
        socratic_resp = SocraticResponse(
            message=bridge_msg,
            question="",
            action="explain",
            question_type="conceptual",
            expected_answer="Continue",
            evaluator_type="exact",
            evaluation_criteria=["Student continues."],
        )
        awaiting = "continue"
        out_pending_q = None

    return {
        "tutor_response": bridge_msg,
        "socratic_response": socratic_resp,
        "doubt_state": doubt_state,
        "awaiting": awaiting,
        "pending_question": out_pending_q,
        "student_input": None,
    }


def doubt_agent_node(state: TutorState) -> Dict[str, Any]:
    """
    LangGraph node: Routes between doubt resolution and clarity confirmation resume flow.
    """
    intent_data = state.get("detected_intent") or {}
    intent_type = intent_data.get("intent", "DOUBT")
    doubt_state = state.get("doubt_state") or {}
    is_clarity_check_active = doubt_state.get("pending_clarity_check", False)

    student_msg = (state.get("student_input") or "").strip()

    # If student confirmed clarity while pending_clarity_check is True:
    if is_clarity_check_active and intent_type in ("CONFIRMATION", "CHITCHAT"):
        return handle_clarity_confirmation(state)

    # Otherwise, handle doubt question
    return handle_doubt_question(state, student_msg, intent_data)
