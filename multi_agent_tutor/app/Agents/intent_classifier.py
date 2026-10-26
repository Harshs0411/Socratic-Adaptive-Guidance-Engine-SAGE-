"""
Intent Classifier Agent for SAGE Tutor.
Classifies student messages into:
- ANSWER_ATTEMPT
- DOUBT
- META
- CONFIRMATION
- CHITCHAT

Includes a fast rule-based pre-filter to eliminate LLM latency/cost for common patterns,
enforces strict pedagogical safety (if no pending question, NEVER an answer attempt;
when unsure, prefer DOUBT; extracts mixed attempt+doubt parts).
"""

import re
from typing import Optional, Dict, Any, Tuple
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from multi_agent_tutor.app.schemas.intent import IntentClassification, IntentType
from multi_agent_tutor.app.graph.state import TutorState


# Structured LLM for ambiguous message intent classification
_model = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.0,
)

_intent_llm = _model.with_structured_output(
    IntentClassification,
    method="function_calling"
)

INTENT_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        """You are the Intent Detection Agent of SAGE, an adaptive AI tutor.
Your job is to classify the student's message with high pedagogical safety:
A student is in a dialogue with a tutor. They must NEVER be penalized for asking questions or expressing confusion.

Available Intents:
1. ANSWER_ATTEMPT: The student is providing a direct answer to the pending question asked by the tutor.
   CRITICAL RULE: If awaiting == 'answer' (or has_pending_question is True), any declarative on-topic statement (even long, even starting with "The ...") is an ANSWER_ATTEMPT and MUST be graded!
   It is a DOUBT ONLY if it asks a question or expresses confusion (ends with ?, starts with "why/how/what/explain", "I don't understand", "wait").
   Never classify as ANSWER_ATTEMPT if has_pending_question is False.
2. DOUBT: The student is asking a question, expressing confusion, asking for clarification, or asking for help.
   Examples: "Why does mid use integer division?", "What does invariant mean?", "I don't understand how pointers move", "I don't know".
3. CONFIRMATION: The student is acknowledging understanding or answering an invitation to continue or clarity check.
   Examples: "ok", "got it", "makes sense", "understood", "yes", "clear", "done", "continue", "next", "ready".
4. META: The student is requesting a change in learning flow, pacing, explanation style, or skipping.
   Examples: "can you explain differently?", "give an example", "slow down", "skip this topic", "can we repeat that?".
5. CHITCHAT: Greetings, pleasantries, off-topic or social chatter.
   Examples: "hello!", "thanks", "how are you?", "who created you?".

CRITICAL PEDAGOGICAL ROUTING RULES:
- If awaiting == 'answer':
  A declarative, on-topic statement (even long, even starting with "The ...") is an ANSWER_ATTEMPT and MUST be graded.
  It is a DOUBT only if it asks something or expresses confusion (question mark, why/how/what/explain, "I don't understand", "wait").
  When truly ambiguous, classify as ANSWER_ATTEMPT with reduced confidence instead of treating as a doubt.
- If awaiting == 'clarity_check':
  Affirmations ("yes", "ok", "done", "got it", "makes sense", "clear") are CONFIRMATION.
  Confusion or negation ("no", "still confused", "explain another way") are DOUBT.
- If awaiting == 'continue':
  Affirmations ("yes", "ok", "ready", "next", "continue") are CONFIRMATION.
  Questions are DOUBT. "no" / "wait" are DOUBT.
- MIXED MESSAGES: If the student provides both an answer and a doubt (e.g., "I think it's O(log n), but why doesn't linear search work here?"), mark `is_mixed = True`, set `attempt_part` to the answer and `doubt_part` to the question.
"""
    ),
    (
        "human",
        """Current Context:
Awaiting: {awaiting}
Has Pending Question: {has_pending_question}
Pending Question: {pending_question}
Current Topic: {topic}
Pending Clarity Check: {pending_clarity_check}

Student Message:
"{message}"

Classify the intent according to the rules."""
    )
])

_intent_chain = INTENT_PROMPT | _intent_llm


# =====================================================================
# RULE-BASED PRE-FILTER
# =====================================================================

CONFIRMATION_PATTERNS = {
    "ok", "okay", "got it", "makes sense", "understood", "clear", "i get it",
    "i understand", "i see", "yes", "yep", "yeah", "yup", "sure", "alright",
    "all good", "sounds good", "cool", "perfect", "that makes sense",
    "crystal clear", "got it thanks", "makes sense thanks", "understands",
}

CHITCHAT_PATTERNS = {
    "hi", "hello", "hey", "good morning", "good afternoon", "good evening",
    "how are you", "who are you", "what's up", "whats up", "sup",
    "thank you", "thanks", "bye", "goodbye", "see you", "nice to meet you",
}

HELP_DONT_KNOW_PATTERNS = {
    "i don't know", "i dont know", "i do not know", "dont know", "do not know",
    "idk", "no idea", "have no idea", "i have no idea", "not sure", "im not sure",
    "i am not sure", "no clue", "have no clue", "i have no clue", "help",
    "help me", "i'm stuck", "im stuck", "stuck", "can you help",
}

META_PATTERNS = [
    (r"\b(explain\s+(?:it\s+|this\s+)?differently|different\s+way|another\s+way|different\s+analogy|another\s+analogy)\b", "explain_differently"),
    (r"\b(give\s+(?:me\s+)?an?\s+example|show\s+(?:me\s+)?an?\s+example|worked\s+example|concrete\s+example)\b", "give_example"),
    (r"\b(explain\s+(?:it\s+|this\s+)?again|repeat|say\s+that\s+again|one\s+more\s+time|can\s+you\s+repeat)\b", "repeat"),
    (r"\b(slow\s+down|go\s+slower|slower\s+please|too\s+fast)\b", "slow_down"),
    (r"\b(speed\s+up|go\s+faster|faster\s+please|too\s+slow|already\s+know\s+this)\b", "speed_up"),
    (r"\b(skip\s+this|skip\s+to\s+next|next\s+topic|can\s+we\s+skip|move\s+on)\b", "skip"),
    (r"\b(show\s+(?:me\s+)?(?:a\s+)?diagram|draw\s+it|draw\s+a\s+diagram|can\s+you\s+draw|i\s+can'?t\s+picture\s+this|picture\s+this|show\s+visual|visualize\s+this|show\s+figure|diagram|figure)\b", "request_visual"),
    (r"\b(take\s+a\s+break|pause|stop\s+for\s+now)\b", "break"),
]


def pre_filter_intent(
    message: str,
    has_pending_question: bool,
    pending_clarity_check: bool = False,
    pending_question: Optional[Dict[str, Any]] = None,
    awaiting: Optional[str] = None,
) -> Optional[IntentClassification]:
    """
    Fast, deterministic rule-based pre-filter.
    Enforces that terse answers matching question format are ANSWER_ATTEMPT,
    negations to clarity check are DOUBT (re-explain), and affirmative confirmations
    work safely.
    """
    if awaiting is None:
        awaiting = "clarity_check" if pending_clarity_check else ("answer" if has_pending_question else "none")

    clean_msg = message.strip()
    norm_lower = "".join(c for c in clean_msg.lower() if c.isalnum() or c.isspace()).strip()
    pq_text_lower = (pending_question.get("question", "") if pending_question else "").lower()
    is_yes_no_question = any(pq_text_lower.startswith(w) for w in ["is ", "are ", "does ", "do ", "can ", "could ", "must ", "should "]) or "yes or no" in pq_text_lower

    # 1. Clarity Check Handling
    if awaiting == "clarity_check" or pending_clarity_check:
        # 1a. Negation / still confused to clarity check -> DOUBT (trigger re-explanation with new angle)
        if norm_lower in {"no", "nope", "not really", "not clear", "still confused", "i dont get it", "i don't get it", "explain another way", "another way please"} or norm_lower.startswith("no "):
            return IntentClassification(
                intent="DOUBT",
                confidence=0.98,
                meta_subintent="clarity_negation",
                reasoning="Student indicated they are still confused by the explanation; triggers re-explanation.",
            )
        # 1b. Affirmative confirmation to clarity check -> CONFIRMATION
        if norm_lower in CONFIRMATION_PATTERNS or norm_lower.startswith("yes") or norm_lower.startswith("makes sense") or norm_lower.startswith("clear") or norm_lower.startswith("got it") or norm_lower == "done":
            return IntentClassification(
                intent="CONFIRMATION",
                confidence=0.99,
                reasoning="Responded affirmatively to active clarity check.",
            )
        # 1c. If student IGNORED clarity check and typed a direct answer to the pending question (implicit confirmation)
        # We will let the terse/answer check below classify it as ANSWER_ATTEMPT!

    # 2. Awaiting Continue Handling (Fix 2 & 3)
    if awaiting == "continue":
        if norm_lower in CONFIRMATION_PATTERNS or norm_lower in {"continue", "next", "ready", "proceed", "yes", "yep", "yeah", "yup", "ok", "okay", "done", "sounds good"}:
            return IntentClassification(
                intent="CONFIRMATION",
                confidence=0.99,
                reasoning="Responded affirmatively to continue invitation.",
            )
        if norm_lower in {"no", "wait", "hold on", "stop", "pause"}:
            return IntentClassification(
                intent="DOUBT",
                confidence=0.95,
                reasoning="Student expressed hesitation or asked to pause.",
            )

    # 3. "I don't know" or help request -> Treat as DOUBT (help request), never wrong answer!
    if norm_lower in HELP_DONT_KNOW_PATTERNS or any(norm_lower.startswith(p) for p in ["i dont know", "dont know", "idk", "no idea", "im stuck"]):
        return IntentClassification(
            intent="DOUBT",
            confidence=0.95,
            meta_subintent="help_request",
            reasoning="Student indicated they do not know or requested help; handled as a doubt/help request.",
        )

    # 4. Exact or combined greeting / chitchat
    if any(norm_lower.startswith(g) for g in ["hi ", "hi", "hello ", "hello", "hey ", "hey", "good morning", "good evening", "good afternoon", "how are you"]) or norm_lower in CHITCHAT_PATTERNS:
        technical_keywords = {"array", "search", "binary", "pointer", "index", "complexity", "mid", "target", "sorted", "algorithm", "layer", "osi", "packet", "protocol"}
        if not any(tk in norm_lower for tk in technical_keywords):
            return IntentClassification(
                intent="CHITCHAT",
                confidence=0.98,
                reasoning="Matched greeting or conversational pleasantry.",
            )

    # 5. Meta requests (explain differently, give example, slow down, skip)
    for pattern, subintent in META_PATTERNS:
        if re.search(pattern, clean_msg, re.IGNORECASE):
            return IntentClassification(
                intent="META",
                confidence=0.95,
                meta_subintent=subintent,
                reasoning=f"Matched meta command: {subintent}.",
            )

    # 6. Question mark + question starter -> pure doubt
    doubt_starters = (
        "why ", "how ", "what is ", "what does ", "what do ", "what are ",
        "can you ", "could you ", "is it ", "isn't it ", "are we ",
        "why does ", "why is ", "why do ", "how does ", "how do ", "how is ",
        "where does ", "when does ", "which one ", "what about ", "can i ", "could i ",
        "i don't understand", "i dont understand", "wait "
    )
    lower_raw = clean_msg.lower().strip()
    if lower_raw.startswith(doubt_starters) or (lower_raw.endswith("?") and any(w in lower_raw for w in ["why", "how", "what", "can", "could", "explain", "clarify", "mean", "where", "when", "which", "is"])):
        return IntentClassification(
            intent="DOUBT",
            confidence=0.96,
            reasoning="Identified as a student question/doubt via question structure and syntax.",
        )

    # 7. AWAITING ANSWER (or has_pending_question): TERSE AND DECLARATIVE ANSWERS
    if awaiting == "answer" or has_pending_question:
        # 7a. Option letter: A, B, C, D
        if clean_msg.upper() in {"A", "B", "C", "D", "(A)", "(B)", "(C)", "(D)"}:
            return IntentClassification(
                intent="ANSWER_ATTEMPT",
                confidence=0.98,
                reasoning="Single-letter option answer to pending question.",
            )
        # 7b. Asymptotic / complexity notation: O(log n), O(n), O(1), Theta(log n)
        if re.search(r"\b[O0oΘθ]\s*\([^\)]+\)", clean_msg, re.IGNORECASE) or norm_lower in {"log n", "logn", "o log n", "ologn"}:
            return IntentClassification(
                intent="ANSWER_ATTEMPT",
                confidence=0.98,
                reasoning="Complexity / asymptotic notation answer to pending question.",
            )
        # 7c. Numbers: 3, -1, 42, 3.14
        if re.match(r"^-?\d+(?:\.\d+)?$", clean_msg):
            return IntentClassification(
                intent="ANSWER_ATTEMPT",
                confidence=0.97,
                reasoning="Numerical answer to pending question.",
            )
        # 7d. Variable assignments: mid = 4, low = mid + 1
        if re.match(r"^[a-zA-Z_]\w*\s*=\s*.+$", clean_msg) and not clean_msg.endswith("?"):
            return IntentClassification(
                intent="ANSWER_ATTEMPT",
                confidence=0.97,
                reasoning="Algorithmic assignment answer to pending question.",
            )
        # 7e. Booleans: True / False
        if norm_lower in {"true", "false"}:
            return IntentClassification(
                intent="ANSWER_ATTEMPT",
                confidence=0.98,
                reasoning="Boolean answer to pending question.",
            )
        # 7f. Polar yes/no to a polar question
        if is_yes_no_question and norm_lower in {"yes", "no"}:
            return IntentClassification(
                intent="ANSWER_ATTEMPT",
                confidence=0.96,
                reasoning="Direct yes/no answer to an active polar/yes-no question.",
            )
        # 7g. Code snippets (cannot end with ? and cannot start with doubt starters)
        code_keywords = {"def ", "return ", "while ", "for ", "if ", "arr[", "mid", "low", "high"}
        if any(ck in clean_msg for ck in code_keywords) and ("=" in clean_msg or "{" in clean_msg or ":" in clean_msg or "[" in clean_msg) and not clean_msg.endswith("?") and not any(lower_raw.startswith(ds) for ds in doubt_starters):
            return IntentClassification(
                intent="ANSWER_ATTEMPT",
                confidence=0.95,
                reasoning="Code snippet answer to pending question.",
            )
        # 7h. One-word answer without question mark or doubt keywords
        if len(clean_msg.split()) == 1 and not clean_msg.endswith("?") and norm_lower not in CONFIRMATION_PATTERNS and norm_lower not in CHITCHAT_PATTERNS and norm_lower not in HELP_DONT_KNOW_PATTERNS:
            return IntentClassification(
                intent="ANSWER_ATTEMPT",
                confidence=0.93,
                reasoning="Single-word terse answer to pending question.",
            )
        # 7i. Fix 2: ANY declarative statement when awaiting answer is an ANSWER_ATTEMPT
        if "?" not in clean_msg and not any(lower_raw.startswith(ds) for ds in doubt_starters):
            return IntentClassification(
                intent="ANSWER_ATTEMPT",
                confidence=0.95,
                reasoning="Declarative response provided in presence of an active pending question.",
            )

    # 8. Confirmation when no clarity check is active
    if (
        norm_lower in CONFIRMATION_PATTERNS
        or any(norm_lower.startswith(p) for p in ["ok", "okay", "got it", "makes sense", "understood", "all good", "sounds good"])
        or any(norm_lower.endswith(p) for p in ["got it", "makes sense", "understood"])
    ):
        return IntentClassification(
            intent="CONFIRMATION",
            confidence=0.95,
            reasoning="General affirmative acknowledgement.",
        )

    return None


def detect_mixed_message(message: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Detects if a message combines an answer attempt with a doubt/question.
    e.g. "I think it's O(log n), but why doesn't linear search work here?"
    """
    # Look for split conjunctions like ", but why", " however why", " though how"
    split_match = re.search(r"^(.*?)(?:,\s*but\s+|\s+but\s+|\s+however\s+|\s+though\s+)(why\b.*|how\b.*|what\b.*|\bcan\s+you\b.*)\??$", message, re.IGNORECASE)
    if split_match:
        attempt_part = split_match.group(1).strip()
        doubt_part = split_match.group(2).strip()
        if len(attempt_part) > 2 and len(doubt_part) > 3:
            return True, doubt_part, attempt_part
    return False, None, None


def classify_student_intent(
    message: str,
    pending_question: Optional[Dict[str, Any]] = None,
    current_topic: str = "General",
    pending_clarity_check: bool = False,
    awaiting: Optional[str] = None,
) -> IntentClassification:
    """
    Main intent classification entry point.
    Runs rule pre-filter first, checks for mixed attempt+doubt, falls back to structured LLM.
    Enforces that if pending_question is None, intent can NEVER be ANSWER_ATTEMPT.
    """
    from multi_agent_tutor.app.config import LEGACY_MODE
    if LEGACY_MODE:
        return IntentClassification(
            intent="ANSWER_ATTEMPT",
            confidence=1.0,
            reasoning="LEGACY_MODE active: every message is treated as an answer attempt.",
        )

    has_pending = pending_question is not None and bool(pending_question.get("question"))
    pq_text = pending_question.get("question", "") if pending_question else ""

    if awaiting is None:
        awaiting = "clarity_check" if pending_clarity_check else ("answer" if has_pending else "none")

    # 1. Check for mixed message (attempt + doubt)
    if has_pending or awaiting == "answer":
        is_mixed, doubt_p, attempt_p = detect_mixed_message(message)
        if is_mixed:
            return IntentClassification(
                intent="DOUBT",
                confidence=0.92,
                is_mixed=True,
                doubt_part=doubt_p,
                attempt_part=attempt_p,
                reasoning="Detected mixed message containing both an answer attempt and an embedded doubt.",
            )

    # 2. Fast rule-based pre-filter
    fast_result = pre_filter_intent(message, has_pending, pending_clarity_check, pending_question, awaiting=awaiting)
    if fast_result is not None:
        if not has_pending and awaiting != "answer" and fast_result.intent == "ANSWER_ATTEMPT":
            fast_result.intent = "DOUBT"
        return fast_result

    # 3. LLM Structured Classification
    try:
        result = _intent_chain.invoke({
            "awaiting": awaiting,
            "has_pending_question": has_pending,
            "pending_question": pq_text or "None (tutor has not asked a question yet)",
            "topic": current_topic,
            "pending_clarity_check": pending_clarity_check,
            "message": message,
        })

        # STRICT SAFETY OVERRIDE:
        # If there is no pending question and not awaiting an answer, intent CANNOT be ANSWER_ATTEMPT
        if not has_pending and awaiting != "answer" and result.intent == "ANSWER_ATTEMPT":
            result.intent = "DOUBT"
            result.reasoning = "Overridden to DOUBT because there was no active pending question to answer."

        # FIX 2: If awaiting answer and declarative on-topic, grade it with reduced confidence rather than treat as DOUBT
        if (awaiting == "answer" or has_pending) and result.intent == "DOUBT" and "?" not in message:
            lower_msg = message.lower().strip()
            doubt_words = ("why", "how", "what", "can you", "could you", "explain", "i don't understand", "wait")
            if not any(lower_msg.startswith(dw) for dw in doubt_words):
                result.intent = "ANSWER_ATTEMPT"
                result.confidence = 0.75
                result.reasoning = "Declarative on-topic statement while awaiting answer: graded with reduced confidence."

        return result
    except Exception as e:
        # Fallback: if awaiting answer and declarative, fallback to ANSWER_ATTEMPT; otherwise DOUBT
        if (awaiting == "answer" or has_pending) and "?" not in message:
            return IntentClassification(
                intent="ANSWER_ATTEMPT",
                confidence=0.70,
                reasoning=f"Classifier fallback due to error: {e}. Defaulting to ANSWER_ATTEMPT for declarative answer."
            )
        return IntentClassification(
            intent="DOUBT",
            confidence=0.5,
            reasoning=f"Classifier fallback due to error: {e}. Defaulting safely to DOUBT."
        )


def intent_classifier_node(state: TutorState) -> dict:
    """
    LangGraph node: Classifies the student's incoming message and attaches
    detected_intent to state before routing.
    """
    student_msg = state.get("student_input", "").strip()
    if not student_msg:
        return {}

    pending_q = state.get("pending_question")
    # Also check if teaching.current_question exists if pending_question wasn't explicitly populated
    if not pending_q and state.get("teaching", {}).get("current_question"):
        pending_q = {"question": state["teaching"]["current_question"]}

    doubt_state = state.get("doubt_state") or {}
    pending_clarity = doubt_state.get("pending_clarity_check", False)
    topic = state.get("target_topic", "General")
    awaiting = state.get("awaiting") or ("clarity_check" if pending_clarity else ("answer" if (pending_q and bool(pending_q.get("question"))) else "none"))

    classification = classify_student_intent(
        message=student_msg,
        pending_question=pending_q,
        current_topic=topic,
        pending_clarity_check=pending_clarity,
        awaiting=awaiting,
    )

    return {
        "detected_intent": classification.model_dump(),
    }
