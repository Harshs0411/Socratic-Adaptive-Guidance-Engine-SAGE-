from dotenv import load_dotenv, find_dotenv

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from multi_agent_tutor.app.graph.state import TutorState
from multi_agent_tutor.app.schemas.critic import CriticOutput


import time
load_dotenv(find_dotenv())


model = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0,
    max_tokens=250,
)

structured_model = model.with_structured_output(
    CriticOutput,
    method="function_calling"
)


prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """
You are the Critic Agent in an AI tutoring system.

Your job is to strictly evaluate a proposed tutor response before it is shown to the student.

EVALUATION MODES:
1. When evaluation_mode is "explanation_only" (Mode 2 explanations, teach steps, doubt resolutions, or worked examples):
   - 1. Is it factually correct and technically sound?
   - 2. Is the language clear, precise, and domain-authentic?
   - 3. ANALOGY & LANGUAGE STRICTNESS:
        * All analogies, mental models, and examples MUST be computationally authentic, rigorous, and contextually relevant.
        * REJECT out-of-context, lazy, superficial, or misleading physical metaphors.
        * SPECIFICALLY REJECT "Russian nesting dolls" (Matryoshka dolls) or nested physical boxes for recursion or algorithms. A Russian doll is a passive physical container that misrepresents computation: it has no call stack, no activation frames, no return value propagation, and no branching.
        * ACCEPTABLE AND RECOMMENDED MODELS: Task delegation with return handoffs (e.g. lead engineer delegating sub-tasks to assistants and propagating returned results), call stack activation records/frames, call stack unwinding, or directory/tree traversals. These are valid, computationally authentic analogies and MUST PASS.
   - Do NOT penalize for explaining directly or revealing information, because the student is learning or asking a doubt!
   - Do NOT require a Socratic question.

2. When evaluation_mode is "socratic_question" (Mode 1, probe, hint, scaffold, or check questions):
   - 1. Is it factually correct?
   - 2. Does it encourage the student to reason?
   - 3. Does it follow the Socratic tutoring approach and avoid unnecessarily leaking the answer?
   - 4. Does it ask exactly ONE clear question? (Note: A friendly introductory lead-in like "Let's test this with a quick check problem:" does NOT count as a second question).
   - 5. Is it appropriate for the student's current mastery?
   - 6. FEEDBACK HANDOFF: When the tutor begins by giving an explicit verdict on the previous answer (e.g. "**Verdict:** Correct!", "**Verdict:** Partly right.", "**Verdict:** Not quite yet.") and explaining what was missing or acknowledging the student's response before asking the question, this is permitted and encouraged practice. Do NOT penalize or fail for providing this evaluative feedback, and do NOT penalize responses that do not include a verdict (such as introductory questions, hint steps, or new challenges).
   - 7. ANALOGY & LANGUAGE STRICTNESS: Reject any question, hint, or scaffold that relies on out-of-context physical tropes (like Russian nesting dolls) instead of sound computational concepts.
   - 8. TEACHING-BEFORE-TESTING GROUNDING (CRITICAL):
        * The proposed question MUST only test concepts, definitions, and mechanics that SAGE has ALREADY explained to the student in previous conversation messages or the current message.
        * REJECT questions based on upcoming lessons, planned curriculum, or future concepts SAGE intends to teach later. A planned lesson is NOT completed teaching.
        * Merely mentioning a term does NOT mean it has been taught.
        * FOR COMPARISON OR TRANSFER QUESTIONS: Verify that ALL essential concepts being compared or transferred have already been explained. If one concept is missing, REJECT the question with instructions to teach the missing concept first before questioning.
   - 9. PRODUCTIVE STRUGGLE & REASONING: Questions that prompt the student to reason through an explained concept or comparison (e.g. asking which half of a sorted array to eliminate when target < arr[mid]) are GOOD pedagogical practice. Do NOT fail or penalize valid reasoning questions as "lacking context" or "too challenging" if the basic prerequisite concept was taught.

CRITICAL FAILURE CONDITIONS:
The tutor MUST FAIL (passed=False, score <= 5.0) ONLY if:
- There is a significant factual error or misleading technical claim.
- It uses clichéd, out-of-context analogies (such as Russian nesting dolls for recursion) that obscure actual computational mechanisms.
- In Socratic mode: it simply gives the answer when the student should be guided through reasoning, or asks multiple distinct queries requiring separate answers.
- In Socratic/Question mode: the proposed question tests concepts, terms, or upcoming lessons that have not yet been taught or explained to the student, or asks a comparison where one of the concepts has not been explained yet.
Do NOT fail questions simply for prompting the student to reason through an explained condition or calculation.

Evaluation Mode:
{evaluation_mode}

Concept:
{concept}

Student mastery:
{mastery}

Teaching action:
{action}

Conversation Explanations Given So Far:
{conversation_history}

Tutor message:
{message}

Exact question:
{question}
"""
        )
    ]
)


critic_chain = (
    prompt
    | structured_model
)


def critic_agent(
    state: TutorState
):

    concept = state["current_concept"]

    mastery = state["mastery"].get(
        concept,
        0.0
    )

    socratic_response = state["socratic_response"]

    if socratic_response is None:
        raise ValueError(
            "No Socratic response available for criticism."
        )

    action = getattr(socratic_response, "action", None) or (socratic_response.get("action") if isinstance(socratic_response, dict) else "initial")
    message = getattr(socratic_response, "message", None) or (socratic_response.get("message") if isinstance(socratic_response, dict) else "")
    question = getattr(socratic_response, "question", None) or (socratic_response.get("question") if isinstance(socratic_response, dict) else "")

    mode = state.get("teaching_mode")
    step = state.get("teaching_step")
    if action in ("explain", "teach", "doubt_resolution") or (mode == "mode_2_teach_first" and step in ("teach", "explain")):
        evaluation_mode = "explanation_only"
    else:
        evaluation_mode = "socratic_question"

    # Deterministic Quality Gate 1: strictly reject out-of-context physical tropes (e.g. Russian dolls)
    lower_content = f"{message} {question}".lower()
    banned_tropes = ["russian doll", "nesting doll", "matryoshka", "babushka doll"]
    for banned in banned_tropes:
        if banned in lower_content:
            result = CriticOutput(
                passed=False,
                score=3.5,
                feedback=(
                    f"Rejected: Response contains the clichéd and out-of-context '{banned}' analogy. "
                    "Russian dolls are passive physical containers that fail to model computational execution, "
                    "call stack activation frames, and return value propagation. Replace it with an authentic "
                    "computational model such as call stack frames, task delegation with return handoff, "
                    "or recursive directory/tree traversal."
                )
            )
            print("\nCRITIC RESULT (DETERMINISTIC REJECTION):")
            print(result)
            new_retries = state.get("retry_count", 0) + 1
            return {
                "critic_result": result,
                "retry_count": new_retries,
            }

    # Deterministic Quality Gate 2: Zero-Token fast-pass for pre-vetted curriculum content
    pq = state.get("pending_question")
    has_vetted_qid = bool(pq and isinstance(pq, dict) and pq.get("question_id"))
    is_vetted = bool(state.get("_is_vetted") or has_vetted_qid)

    if is_vetted and len(message.strip()) > 0:
        if evaluation_mode == "explanation_only" or question.count("?") <= 1:
            print("[TIMING] Critic: 0.000s (deterministic quality pass for pre-vetted curriculum)")
            result = CriticOutput(
                passed=True,
                score=9.5,
                feedback="Pre-vetted pedagogical curriculum content passed deterministic quality gate."
            )
            return {
                "critic_result": result,
                "retry_count": 0,
            }

    # Extract conversation history so Critic verifies that concepts were actually taught
    messages = state.get("messages") or []
    tutor_explanations = [
        m.get("content", "")[:300] for m in messages
        if m.get("role") in ("assistant", "tutor")
    ]
    history_summary = "\n---\n".join(tutor_explanations[-4:]) if tutor_explanations else "Only the initial introduction."

    t0 = time.perf_counter()
    result = critic_chain.invoke(
        {
            "concept": concept,
            "mastery": mastery,
            "action": action,
            "message": message,
            "question": question,
            "evaluation_mode": evaluation_mode,
            "conversation_history": history_summary,
        }
    )
    elapsed = time.perf_counter() - t0

    passed = getattr(result, "passed", True)
    crit_score = getattr(result, "score", None)
    print(f"[TIMING] Critic: {elapsed:.3f}s (passed={passed}, score={crit_score})")
    new_retries = 0 if passed else state.get("retry_count", 0) + 1

    return {
        "critic_result": result,
        "retry_count": new_retries,
    }