from dotenv import load_dotenv, find_dotenv

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from multi_agent_tutor.app.graph.state import TutorState
from multi_agent_tutor.app.schemas.critic import CriticOutput


load_dotenv(find_dotenv())


model = ChatOpenAI(
    model="gpt-4o",
    temperature=0
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
        * Acceptable analogies for recursion MUST actively model execution frames, delegation with return handoffs, call stack unwinding, or tree/directory traversals.
   - Do NOT penalize for explaining directly or revealing information, because the student is learning or asking a doubt!
   - Do NOT require a Socratic question.

2. When evaluation_mode is "socratic_question" (Mode 1, probe, hint, scaffold, or check questions):
   - 1. Is it factually correct?
   - 2. Does it encourage the student to reason?
   - 3. Does it follow the Socratic tutoring approach and avoid unnecessarily leaking the answer?
   - 4. Does it ask exactly ONE clear question? (Note: A friendly introductory lead-in like "Let's test this with a quick check problem:" does NOT count as a second question).
   - 5. Is it appropriate for the student's current mastery?
   - 6. FEEDBACK HANDOFF: When the tutor begins by giving an explicit verdict on the previous answer (e.g. "**Verdict:** Correct!", "**Verdict:** Partly right.", "**Verdict:** Not quite yet.") and explaining what was missing or acknowledging the student's response before asking the question, this is REQUIRED pedagogical practice. Do NOT penalize or fail for providing this evaluative feedback.
   - 7. ANALOGY & LANGUAGE STRICTNESS: Reject any question, hint, or scaffold that relies on out-of-context physical tropes (like Russian nesting dolls) instead of sound computational concepts.

CRITICAL FAILURE CONDITIONS:
The tutor MUST FAIL (passed=False, score <= 5.0) if:
- There is a significant factual error or misleading technical claim.
- It uses clichéd, out-of-context analogies (such as Russian nesting dolls for recursion) that obscure actual computational mechanisms.
- In Socratic mode: it simply gives the answer when the student should be guided through reasoning, or asks multiple distinct queries requiring separate answers.

Evaluation Mode:
{evaluation_mode}

Concept:
{concept}

Student mastery:
{mastery}

Teaching action:
{action}

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

    # Deterministic Quality Gate: strictly reject out-of-context physical tropes (e.g. Russian dolls)
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

    result = critic_chain.invoke(
        {
            "concept": concept,
            "mastery": mastery,
            "action": action,
            "message": message,
            "question": question,
            "evaluation_mode": evaluation_mode,
        }
    )

    print("\nCRITIC RESULT:")
    print(result)
    print("TYPE:", type(result))

    passed = getattr(result, "passed", True)
    new_retries = 0 if passed else state.get("retry_count", 0) + 1

    return {
        "critic_result": result,
        "retry_count": new_retries,
    }