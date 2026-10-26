"""
Teaching Agent for SAGE Tutor (Part 2: Two Teaching Modes).
Handles:
1. Mode selection: choose_mode(mastery) based on MODE_SWITCH_MASTERY_THRESHOLD.
   Re-evaluated only at the START of each subtopic/concept to prevent mid-lesson flapping.
2. Mode 2 (Teach First):
   - step 'explain': Clear grounded explanation from curriculum JSON (outline, analogy, 2 worked examples)
     plus inviting student doubts.
   - step 'check': Check questions from question bank (recall -> application -> transfer).
   - Re-teach cycling upon incorrect answers (analogy -> step-by-step walkthrough -> worked example with new numbers).
   - Cap at REMEDIATION_CAP (3) -> prerequisite revisit offer or hint ladder.
3. Mode 1 (High Mastery):
   - Socratic question-and-answer from application and transfer tiers.
   - Explains only the gap upon mistakes.
4. Grounded in curriculum JSON and ChromaDB RAG.
5. Evaluated with Critic in 'explanation_only' mode for explanations.
"""

from typing import Dict, Any, Optional, List, Tuple
from multi_agent_tutor.app.config import (
    MODE_SWITCH_MASTERY_THRESHOLD,
    REMEDIATION_CAP,
    HINT_LADDER_MAX_LEVEL,
    SUBTOPIC_MIN_CORRECT_CHECKS,
    SUBTOPIC_REQUIRE_TRANSFER,
    MASTERY_ADVANCE_THRESHOLD,
)
from multi_agent_tutor.app.graph.state import TutorState
from multi_agent_tutor.app.schemas.socratic import SocraticResponse
from multi_agent_tutor.app.curriculum_loader import load_rich_curriculum
from multi_agent_tutor.app.rag.rag_tool import retrieve_pedagogical_context


def choose_mode(topic_mastery: float) -> str:
    """
    Selects teaching mode based on mastery threshold from config (Requirement 2).
    - In LEGACY_MODE: always mode_1_qa (no teach-first)
    - mastery >= MODE_SWITCH_MASTERY_THRESHOLD (0.65) -> Mode 1 (Q&A / Practice)
    - mastery < MODE_SWITCH_MASTERY_THRESHOLD -> Mode 2 (Teach First)
    """
    from multi_agent_tutor.app.config import LEGACY_MODE
    if LEGACY_MODE:
        return "mode_1_qa"
    if topic_mastery >= MODE_SWITCH_MASTERY_THRESHOLD:
        return "mode_1_qa"
    return "mode_2_teach_first"


from pydantic import BaseModel, Field
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

_dyn_model = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.2,
)

_DYNAMIC_PEDAGOGICAL_CACHE: Dict[Tuple[str, str], Dict[str, Any]] = {}


class DynamicWorkedExample(BaseModel):
    title: str = Field(description="Descriptive title of the worked example")
    problem: str = Field(description="Concrete problem scenario with specific numbers, code, or context")
    step_by_step_solution: List[str] = Field(description="At least 3-4 sequential steps showing execution")
    key_takeaway: str = Field(description="Core pedagogical takeaway")


class DynamicCheckQuestion(BaseModel):
    question_id: str = Field(description="Unique snake_case id")
    question: str = Field(description="Question testing conceptual understanding or problem solving")
    expected_answer: str = Field(description="Concise expected correct answer")
    evaluation_criteria: List[str] = Field(description="Criteria to verify correctness")
    difficulty_tier: int = Field(description="1 for recall, 2 for application, 3 for transfer")
    question_type: str = Field(description="conceptual, objective, or application", default="conceptual")
    evaluator_type: str = Field(description="llm or exact", default="llm")


class DynamicPedagogicalPayload(BaseModel):
    topic_title: str
    subtopic_name: str
    description: str
    learning_objectives: List[str]
    analogies: List[str] = Field(description="At least 2 domain-accurate real-world analogies tailored specifically to this topic")
    worked_examples: List[DynamicWorkedExample] = Field(description="Exactly 2 comprehensive worked examples")
    visual_mermaid: str = Field(description="Mermaid diagram code showing the architecture, flow, or mechanism")
    visual_title: str
    visual_caption: str
    common_misconceptions: List[str]
    question_bank: List[DynamicCheckQuestion]


DYNAMIC_PEDAGOGICAL_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        """You are the Lead Pedagogical Content Architect for SAGE, an adaptive AI tutor.
Generate comprehensive, beginner-friendly instructional content for:
Subject: {topic}
Concept: {concept_id}

CRITICAL PEDAGOGICAL SAFETY DIRECTIVES:
1. All analogies, examples, and questions MUST be authentically tailored to '{topic}' and '{concept_id}'.
2. You MUST NOT use Binary Search, array pointers, or phonebook analogies unless the subject is explicitly Binary Search.
3. LANGUAGE & ANALOGY STRICTNESS:
   - For recursion and algorithmic concepts, NEVER use clichéd, out-of-context physical tropes such as "Russian nesting dolls", "Matryoshka dolls", or nested physical boxes. Russian dolls are static containers that fail to model execution frames, call stacks, return value propagation, or branching.
   - For recursion, use authentic computational mechanisms: call stack frames (activation records with local variables popping off), task delegation with return handoffs, or recursive directory/tree traversals.
4. Provide exactly 2 rich worked examples with step-by-step details.
5. Provide a valid, acyclic Mermaid diagram (e.g. flowchart TD or graph LR) that accurately traces the step-by-step state progression without loops or invalid syntax.
6. Provide at least 8 distinct check questions: at least 3 Recall (Tier 1), at least 3 Application (Tier 2), and at least 2 Transfer (Tier 3).
"""
    ),
    (
        "human",
        "Generate complete pedagogical data with at least 8 distinct check questions for concept '{concept_id}' in '{topic}'."
    )
])

_dynamic_payload_chain = DYNAMIC_PEDAGOGICAL_PROMPT | _dyn_model.with_structured_output(DynamicPedagogicalPayload, method="function_calling")


def _generate_fallback_subtopic_data(topic: str, concept_id: str) -> Dict[str, Any]:
    clean_title = concept_id.replace("_", " ").title()
    clean_topic = topic.title()
    return {
        "topic_title": clean_topic,
        "subtopic_name": clean_title,
        "description": f"Core principles, operational guarantees, and mechanisms of {clean_title} within {clean_topic}.",
        "learning_objectives": [
            f"Understand the theoretical foundations of {clean_title}",
            f"Apply the operational mechanisms of {clean_title} to solve concrete challenges",
            f"Analyze edge cases, invariants, and failure modes in {clean_title}",
        ],
        "analogies": [
            f"A real-world regulatory checkpoint in {clean_topic}: just as safety protocols systematically verify constraints before allowing state transitions, {clean_title} establishes the operational boundary for {clean_topic}.",
            f"A dual-verification circuit in {clean_topic}: verifying each phase of execution against defined invariants to maintain deterministic system stability.",
        ],
        "worked_examples": [
            DynamicWorkedExample(
                title=f"Baseline Execution of {clean_title}",
                problem=f"Verify how {clean_title} processes standard input in {clean_topic}.",
                step_by_step_solution=[
                    f"1. Initialize system configuration and specify active constraints for {clean_title}.",
                    f"2. Evaluate incoming parameters against the governing rules of {clean_topic}.",
                    f"3. Execute the core state transition and capture deterministic outputs.",
                    f"4. Confirm that post-execution invariant conditions remain satisfied.",
                ],
                key_takeaway=f"{clean_title} provides predictable, verified execution boundaries in {clean_topic}.",
            ),
            DynamicWorkedExample(
                title=f"Edge Case Handling in {clean_title}",
                problem=f"Trace how {clean_title} behaves under boundary conditions in {clean_topic}.",
                step_by_step_solution=[
                    f"1. Inject boundary inputs near the tolerance threshold of {clean_title}.",
                    f"2. Verify that guard mechanisms intercept out-of-range deviations.",
                    f"3. Apply error containment or fallback recovery routines.",
                    f"4. Restore nominal system operation without violating consistency.",
                ],
                key_takeaway=f"Robust boundary checking in {clean_title} prevents cascading system failures.",
            ),
        ],
        "visual_mermaid": f"graph TD\n    A[Input State] --> B[{clean_title}]\n    B --> C{{Invariant Check}}\n    C -- Passed --> D[Verified Result]\n    C -- Failed --> E[Fallback Recovery]",
        "visual_title": f"{clean_title} Architectural Flow",
        "visual_caption": f"State progression and invariant verification pipeline for {clean_title}.",
        "common_misconceptions": [
            f"Assuming {clean_title} can be bypassed without compromising global system guarantees in {clean_topic}.",
            f"Treating {clean_title} as a passive filter rather than an active operational mechanism.",
        ],
        "question_bank": [
            # Tier 1: Recall
            DynamicCheckQuestion(
                question_id=f"{concept_id}_check_1",
                question=f"In your own words, what is the core role and primary definition of {clean_title} in {clean_topic}?",
                expected_answer=f"To enforce operational boundaries and guarantee foundational mechanisms in {clean_topic}.",
                evaluation_criteria=[f"Mentions core role of {clean_title}", "Explains primary operational definition"],
                difficulty_tier=1,
            ),
            DynamicCheckQuestion(
                question_id=f"{concept_id}_check_2",
                question=f"What condition or prerequisite must be met before {clean_title} can execute successfully?",
                expected_answer=f"Valid configuration parameters and initial state guarantees specific to {clean_title}.",
                evaluation_criteria=["Identifies prerequisite condition", "Describes initial state requirements"],
                difficulty_tier=1,
            ),
            DynamicCheckQuestion(
                question_id=f"{concept_id}_check_3",
                question=f"Why is {clean_title} indispensable to the correct functioning of {clean_topic}?",
                expected_answer=f"Because without {clean_title}, executions lack termination or correctness guarantees.",
                evaluation_criteria=["Explains necessity of concept", "Connects to system correctness"],
                difficulty_tier=1,
            ),
            # Tier 2: Application
            DynamicCheckQuestion(
                question_id=f"{concept_id}_check_4",
                question=f"How would you apply {clean_title} to handle an unexpected boundary input in {clean_topic}?",
                expected_answer=f"By validating against constraints, intercepting violations, and executing fallback recovery.",
                evaluation_criteria=["Identifies boundary condition", "Describes systematic handling/validation"],
                difficulty_tier=2,
            ),
            DynamicCheckQuestion(
                question_id=f"{concept_id}_check_5",
                question=f"Walk through how {clean_title} modifies or preserves state during a single execution step.",
                expected_answer=f"It computes the current step transition, checks invariants, and produces verified outputs.",
                evaluation_criteria=["Traces state change accurately", "Maintains invariant constraints"],
                difficulty_tier=2,
            ),
            DynamicCheckQuestion(
                question_id=f"{concept_id}_check_6",
                question=f"Suppose an edge case triggers in {clean_title}. What exact sequence of events resolves it?",
                expected_answer=f"Detection of threshold breach, state containment, and deterministic error handling.",
                evaluation_criteria=["Specifies detection mechanism", "Details resolution steps"],
                difficulty_tier=2,
            ),
            # Tier 3: Transfer
            DynamicCheckQuestion(
                question_id=f"{concept_id}_check_7",
                question=f"If the operational constraints of {clean_title} were relaxed, what failure modes could emerge in {clean_topic}?",
                expected_answer="State corruption, cascading invariant violations, or loss of deterministic guarantees.",
                evaluation_criteria=["Identifies specific failure modes", "Connects relaxed constraints to systemic impact"],
                difficulty_tier=3,
            ),
            DynamicCheckQuestion(
                question_id=f"{concept_id}_check_8",
                question=f"How can the design principles of {clean_title} be extended to related domains or larger architectures?",
                expected_answer="By abstracting the invariant boundary check and modularizing state transitions.",
                evaluation_criteria=["Abstracts core concept", "Applies principles to broader system architecture"],
                difficulty_tier=3,
            ),
        ],
    }


BANNED_ANALOGY_TERMS = ["russian doll", "nesting doll", "matryoshka", "babushka"]


def sanitize_analogy(analogy: str, topic: str, concept_id: str) -> str:
    """
    Replaces clichéd, out-of-context physical metaphors (like Russian nesting dolls)
    with authentic computational analogies (call stack frames, task delegation with return handoffs).
    """
    if not analogy:
        return analogy
    lower_a = analogy.lower()
    if any(b in lower_a for b in BANNED_ANALOGY_TERMS):
        if "recurs" in topic.lower() or "recurs" in concept_id.lower() or "base_case" in concept_id.lower():
            return (
                "Task Delegation with Return Handoff: Imagine a lead engineer who delegates a smaller version of the problem "
                "to an assistant, who in turn delegates further, creating a stack of pending execution frames. Once the simplest base-case "
                "task is solved directly, the result is handed back up the call stack frame by frame, allowing each caller to synthesize "
                "the return value until the final answer is computed."
            )
        clean_title = concept_id.replace("_", " ").title()
        return f"A structured pipeline in {topic}: each stage operates on an isolated execution frame and returns verified output to its caller."
    return analogy


def _generate_dynamic_subtopic_data(topic: str, concept_id: str) -> Dict[str, Any]:
    cache_key = (topic.strip().lower(), concept_id.strip().lower())
    if cache_key in _DYNAMIC_PEDAGOGICAL_CACHE:
        cached = _DYNAMIC_PEDAGOGICAL_CACHE[cache_key]
        cached_analogies = cached.get("analogies", [])
        if any(any(b in str(a).lower() for b in BANNED_ANALOGY_TERMS) for a in cached_analogies):
            _DYNAMIC_PEDAGOGICAL_CACHE.pop(cache_key, None)
        else:
            return cached

    # Try LLM generation with 1 retry
    for attempt in range(2):
        try:
            res = _dynamic_payload_chain.invoke({
                "topic": topic,
                "concept_id": concept_id,
            })
            if res and res.worked_examples and len(res.worked_examples) >= 2 and res.analogies:
                sanitized_analogies = [sanitize_analogy(a, topic, concept_id) for a in res.analogies]
                data = {
                    "topic_title": res.topic_title,
                    "subtopic_name": res.subtopic_name,
                    "description": res.description,
                    "learning_objectives": res.learning_objectives,
                    "analogies": sanitized_analogies,
                    "worked_examples": res.worked_examples,
                    "visual_mermaid": res.visual_mermaid,
                    "visual_title": res.visual_title,
                    "visual_caption": res.visual_caption,
                    "misconceptions": res.common_misconceptions,
                    "question_bank": res.question_bank,
                }
                _DYNAMIC_PEDAGOGICAL_CACHE[cache_key] = data
                return data
        except Exception:
            if attempt == 1:
                break

    fallback = _generate_fallback_subtopic_data(topic, concept_id)
    _DYNAMIC_PEDAGOGICAL_CACHE[cache_key] = fallback
    return fallback


def get_subtopic_pedagogical_data(topic: str, concept_id: str) -> Optional[Dict[str, Any]]:
    """
    Fetches the rich subtopic explanation, analogy, worked examples, and question bank.
    Uses pre-authored gold curriculum when available; dynamically generates rich pedagogical
    data for any custom topic (never falls back to Binary Search or phonebook).
    """
    rich = load_rich_curriculum(topic)
    if rich:
        for top in rich.topics:
            if top.topic_id == concept_id:
                sub = top.subtopics[0]
                return {
                    "topic_title": top.title,
                    "subtopic_name": sub.name,
                    "description": sub.description,
                    "learning_objectives": sub.learning_objectives,
                    "analogies": sub.analogies,
                    "worked_examples": sub.worked_examples,
                    "misconceptions": sub.common_misconceptions,
                    "question_bank": sub.question_bank,
                }
            for sub in top.subtopics:
                if sub.subtopic_id == concept_id:
                    return {
                        "topic_title": top.title,
                        "subtopic_name": sub.name,
                        "description": sub.description,
                        "learning_objectives": sub.learning_objectives,
                        "analogies": sub.analogies,
                        "worked_examples": sub.worked_examples,
                        "misconceptions": sub.common_misconceptions,
                        "question_bank": sub.question_bank,
                    }
    # For non-gold topics, dynamically generate domain-specific pedagogical content
    return _generate_dynamic_subtopic_data(topic, concept_id)


def generate_mode_2_explanation(topic: str, concept_id: str, subtopic_data: Optional[Dict[str, Any]] = None) -> str:
    """
    Builds a clear, beginner-friendly Mode 2 explanation:
    - Overview and learning objective
    - Real-world analogy
    - 2 concrete worked examples with step-by-step details
    - Visual model
    - Invites doubts
    """
    if not subtopic_data:
        subtopic_data = get_subtopic_pedagogical_data(topic, concept_id)

    clean_cid_title = concept_id.replace("_", " ").title() if concept_id else topic
    title = subtopic_data.get("subtopic_name", clean_cid_title) if subtopic_data else clean_cid_title
    analogies = subtopic_data.get("analogies", []) if subtopic_data else []
    raw_analogy = analogies[0] if analogies else f"An intuitive system model illustrating the core mechanisms of {title} in {topic}."
    analogy = sanitize_analogy(raw_analogy, topic, concept_id)
    examples = subtopic_data.get("worked_examples", []) if subtopic_data else []

    ex_text_1 = ""
    ex_text_2 = ""
    if len(examples) >= 1:
        ex1 = examples[0]
        steps_list = getattr(ex1, "step_by_step_solution", []) if not isinstance(ex1, dict) else ex1.get("step_by_step_solution", [])
        steps_1 = "\n".join(f"   {step}" for step in steps_list)
        ex1_title = getattr(ex1, "title", "Worked Example 1") if not isinstance(ex1, dict) else ex1.get("title", "Worked Example 1")
        ex1_prob = getattr(ex1, "problem", "") if not isinstance(ex1, dict) else ex1.get("problem", "")
        ex1_takeaway = getattr(ex1, "key_takeaway", "") if not isinstance(ex1, dict) else ex1.get("key_takeaway", "")
        ex_text_1 = f"### Worked Example 1: {ex1_title}\n**Problem:** {ex1_prob}\n**Walkthrough:**\n{steps_1}\n**Key Takeaway:** {ex1_takeaway}\n"

    if len(examples) >= 2:
        ex2 = examples[1]
        steps_list2 = getattr(ex2, "step_by_step_solution", []) if not isinstance(ex2, dict) else ex2.get("step_by_step_solution", [])
        steps_2 = "\n".join(f"   {step}" for step in steps_list2)
        ex2_title = getattr(ex2, "title", "Worked Example 2") if not isinstance(ex2, dict) else ex2.get("title", "Worked Example 2")
        ex2_prob = getattr(ex2, "problem", "") if not isinstance(ex2, dict) else ex2.get("problem", "")
        ex2_takeaway = getattr(ex2, "key_takeaway", "") if not isinstance(ex2, dict) else ex2.get("key_takeaway", "")
        ex_text_2 = f"### Worked Example 2: {ex2_title}\n**Problem:** {ex2_prob}\n**Walkthrough:**\n{steps_2}\n**Key Takeaway:** {ex2_takeaway}\n"

    visual_text = ""
    from multi_agent_tutor.app.Agents.visual_agent import get_visual_for_concept
    vis = get_visual_for_concept(topic, concept_id)
    if vis:
        if vis.type == "mermaid":
            visual_text = f"### 📊 Visual Model: {vis.title}\n```mermaid\n{vis.content}\n```\n*{vis.caption}*\n\n"
        else:
            visual_text = f"### 📊 Visual Model: {vis.title}\n```\n{vis.content}\n```\n*{vis.caption}*\n\n"
    elif subtopic_data and subtopic_data.get("visual_mermaid"):
        v_title = subtopic_data.get("visual_title", f"{title} Architecture")
        v_caption = subtopic_data.get("visual_caption", f"Visual model for {title}")
        v_code = subtopic_data["visual_mermaid"]
        visual_text = f"### 📊 Visual Model: {v_title}\n```mermaid\n{v_code}\n```\n*{v_caption}*\n\n"

    explanation = (
        f"## 📚 Lesson: {title}\n\n"
        f"### Intuitive Mental Model\n"
        f"💡 **Analogy:** {analogy}\n\n"
        f"{visual_text}"
        f"{ex_text_1}\n"
        f"{ex_text_2}\n"
        "---\n"
        "💬 **Invitation:** Any questions on this, or shall we move on to try a quick check problem together?"
    )
    return explanation


def get_mode_2_step_content(
    topic: str,
    concept_id: str,
    step_index: int,
    subtopic_data: Optional[Dict[str, Any]] = None,
) -> Tuple[str, bool]:
    """
    Returns (content_markdown, is_last_explanation_step) for small digestible Mode 2 steps:
      Step 0: Intuition & Analogy (no quiz)
      Step 1: Worked Example 1 (walked through step by step)
      Step 2: Worked Example 2 (edge case or alternative)
      Step 3: Visual / Mental Model (clean table / visual diagram)
    """
    if not subtopic_data:
        subtopic_data = get_subtopic_pedagogical_data(topic, concept_id)

    clean_cid_title = concept_id.replace("_", " ").title() if concept_id else topic
    title = subtopic_data.get("subtopic_name", clean_cid_title) if subtopic_data else clean_cid_title
    invitation = "\n\n---\n💬 Any questions on this, or click **Continue** when you're ready to proceed!"

    if step_index == 0:
        analogies = subtopic_data.get("analogies", []) if subtopic_data else []
        raw_analogy = analogies[0] if analogies else f"An intuitive mental model illustrating the core mechanisms of {title} in {topic}."
        analogy = sanitize_analogy(raw_analogy, topic, concept_id)
        desc = subtopic_data.get("description", "") if subtopic_data else ""
        content = (
            f"## 📚 {title} (Part 1/4: Intuition & Core Problem)\n\n"
            f"{desc}\n\n"
            f"### Intuitive Mental Model\n"
            f"💡 **Analogy:** {analogy}"
            f"{invitation}"
        )
        return content, False

    elif step_index == 1:
        examples = subtopic_data.get("worked_examples", []) if subtopic_data else []
        ex_text = ""
        if len(examples) >= 1:
            ex1 = examples[0]
            steps_list = getattr(ex1, "step_by_step_solution", []) if not isinstance(ex1, dict) else ex1.get("step_by_step_solution", [])
            steps_1 = "\n".join(f"   {step}" for step in steps_list)
            ex1_title = getattr(ex1, "title", "Worked Example 1") if not isinstance(ex1, dict) else ex1.get("title", "Worked Example 1")
            ex1_prob = getattr(ex1, "problem", "") if not isinstance(ex1, dict) else ex1.get("problem", "")
            ex1_takeaway = getattr(ex1, "key_takeaway", "") if not isinstance(ex1, dict) else ex1.get("key_takeaway", "")
            ex_text = (
                f"### Worked Example 1: {ex1_title}\n\n"
                f"**Problem Scenario:** {ex1_prob}\n\n"
                f"**Step-by-Step Walkthrough:**\n{steps_1}\n\n"
                f"**Key Takeaway:** {ex1_takeaway}"
            )
        else:
            ex_text = f"Consider how {title} systematically processes normal inputs step-by-step to preserve consistency in {topic}."
        content = (
            f"## 📚 {title} (Part 2/4: Concrete Walkthrough)\n\n"
            f"{ex_text}"
            f"{invitation}"
        )
        return content, False

    elif step_index == 2:
        examples = subtopic_data.get("worked_examples", []) if subtopic_data else []
        ex_text = ""
        if len(examples) >= 2:
            ex2 = examples[1]
            steps_list2 = getattr(ex2, "step_by_step_solution", []) if not isinstance(ex2, dict) else ex2.get("step_by_step_solution", [])
            steps_2 = "\n".join(f"   {step}" for step in steps_list2)
            ex2_title = getattr(ex2, "title", "Worked Example 2") if not isinstance(ex2, dict) else ex2.get("title", "Worked Example 2")
            ex2_prob = getattr(ex2, "problem", "") if not isinstance(ex2, dict) else ex2.get("problem", "")
            ex2_takeaway = getattr(ex2, "key_takeaway", "") if not isinstance(ex2, dict) else ex2.get("key_takeaway", "")
            ex_text = (
                f"### Worked Example 2: {ex2_title} (Edge Case / Variation)\n\n"
                f"**Problem Scenario:** {ex2_prob}\n\n"
                f"**Step-by-Step Walkthrough:**\n{steps_2}\n\n"
                f"**Key Takeaway:** {ex2_takeaway}"
            )
        else:
            ex_text = f"Boundary case in {title}: When handling unexpected or edge conditions, {title} enforces invariants and executes recovery routines."
        content = (
            f"## 📚 {title} (Part 3/4: Edge Cases & Variations)\n\n"
            f"{ex_text}"
            f"{invitation}"
        )
        return content, False

    else:
        from multi_agent_tutor.app.Agents.visual_agent import get_visual_for_concept
        vis = get_visual_for_concept(topic, concept_id)
        visual_text = ""
        if vis:
            if vis.type == "mermaid":
                visual_text = f"### 📊 Visual Model: {vis.title}\n```mermaid\n{vis.content}\n```\n*{vis.caption}*\n\n"
            else:
                visual_text = f"### 📊 Visual Model: {vis.title}\n```\n{vis.content}\n```\n*{vis.caption}*\n\n"
        elif subtopic_data and subtopic_data.get("visual_mermaid"):
            v_title = subtopic_data.get("visual_title", f"{title} Architecture")
            v_caption = subtopic_data.get("visual_caption", f"Visual model for {title}")
            v_code = subtopic_data["visual_mermaid"]
            visual_text = f"### 📊 Visual Model: {v_title}\n```mermaid\n{v_code}\n```\n*{v_caption}*\n\n"
        else:
            visual_text = (
                f"### 📊 Architecture & State Flow for {title}\n\n"
                f"| Step | Action | State / Output |\n"
                f"|---|---|---|\n"
                f"| 1 | Invariant Check | Validates constraints |\n"
                f"| 2 | Execution | Computes operational transition |\n"
                f"| 3 | State Verification | Guarantees post-conditions |\n\n"
            )
        content = (
            f"## 📚 {title} (Part 4/4: Visual Architecture)\n\n"
            f"{visual_text}"
            f"We've covered the intuition, examples, and architecture for **{title}**.\n"
            f"Next, we'll try a few quick check questions to solidify what you've learned!"
            f"{invitation}"
        )
        return content, True


def generate_re_teach_explanation(
    topic: str,
    concept_id: str,
    attempt_count: int,
    misconception_notes: List[str],
    subtopic_data: Optional[Dict[str, Any]] = None,
) -> Tuple[str, bool]:
    """
    Cycles through different pedagogical approaches upon student difficulty:
    - Cycle 1 (attempt 1): Alternate analogy
    - Cycle 2 (attempt 2): Smaller step-by-step walkthrough
    - Cycle 3 (attempt 3): Worked example with different scenario/numbers
    - Above cap (REMEDIATION_CAP=3): Offer to revisit prerequisite or move to hint ladder.
    Returns (explanation_text, reached_cap_flag).
    """
    if not subtopic_data:
        subtopic_data = get_subtopic_pedagogical_data(topic, concept_id)

    clean_cid_title = concept_id.replace("_", " ").title() if concept_id else topic
    title = subtopic_data.get("subtopic_name", clean_cid_title) if subtopic_data else clean_cid_title

    if attempt_count >= REMEDIATION_CAP:
        offer_msg = (
            "We've looked at this from a few different angles, and it's completely normal for tricky concepts to take time! "
            "Would you like to:\n"
            "1. Revisit the prerequisite foundational concept first, or\n"
            "2. Try a smaller hint ladder where I guide you step-by-step through the problem?"
        )
        return offer_msg, True

    miscon_mention = f"\n*(Note: Keep in mind that {misconception_notes[0]}!)*\n" if misconception_notes else ""

    if attempt_count == 1:
        # Approach 1: Alternate analogy
        analogies = subtopic_data.get("analogies", []) if subtopic_data else []
        alt_analogy = analogies[1] if len(analogies) > 1 else (analogies[0] if analogies else f"A fresh operational mental model for {title} in {topic}.")
        text = (
            f"Let's look at this from a completely fresh angle! 🔄\n\n"
            f"💡 **Alternative Analogy:** {alt_analogy}{miscon_mention}\n\n"
            f"Notice how each principle in {title} builds directly on foundational rules."
        )
        return text, False

    elif attempt_count == 2:
        # Approach 2: Smaller step-by-step walkthrough
        ex1 = subtopic_data.get("worked_examples", [None])[0] if subtopic_data else None
        if ex1:
            steps_list = getattr(ex1, "step_by_step_solution", []) if not isinstance(ex1, dict) else ex1.get("step_by_step_solution", [])
            steps_formatted = "\n".join(f"{s}" for s in steps_list)
            text = (
                f"Let's break this down into tiny, bite-sized steps: 🧩\n\n"
                f"{steps_formatted}\n"
                f"{miscon_mention}\n"
                f"Each tiny step follows deterministically from the governing principles of {title}."
            )
        else:
            text = (
                f"Let's break this down into tiny, bite-sized steps for {title}: 🧩\n\n"
                f"1. Define the operational boundary and inputs.\n"
                f"2. Trace each state transition step-by-step.\n"
                f"3. Verify the outcome against expected invariants.\n"
                f"{miscon_mention}"
            )
        return text, False

    else:
        # Approach 3: Worked example with new scenario
        ex2 = subtopic_data.get("worked_examples", [None, None])[1] if subtopic_data and len(subtopic_data.get("worked_examples", [])) > 1 else None
        if ex2:
            ex_title = getattr(ex2, "title", "Worked Example") if not isinstance(ex2, dict) else ex2.get("title", "Worked Example")
            ex_prob = getattr(ex2, "problem", "") if not isinstance(ex2, dict) else ex2.get("problem", "")
            steps_list = getattr(ex2, "step_by_step_solution", []) if not isinstance(ex2, dict) else ex2.get("step_by_step_solution", [])
            steps_formatted = "\n".join(f"  {s}" for s in steps_list)
            text = (
                f"Let's walk through another concrete scenario for {title}: 🔢\n\n"
                f"**Scenario ({ex_title}):** {ex_prob}\n\n"
                f"**Step-by-step Execution:**\n{steps_formatted}\n\n"
                f"{miscon_mention}"
            )
        else:
            text = f"Let's walk through a concrete scenario for {title} in {topic}.{miscon_mention}"
        return text, False


import re


def normalize_text(s: str) -> str:
    if not s:
        return ""
    return re.sub(r"[^\w\s]", "", s.lower()).strip()


def compute_word_jaccard(s1: str, s2: str) -> float:
    w1 = set(normalize_text(s1).split())
    w2 = set(normalize_text(s2).split())
    if not w1 or not w2:
        return 0.0
    inter = len(w1 & w2)
    union = len(w1 | w2)
    return inter / union if union > 0 else 0.0


def compute_char_ngram_overlap(s1: str, s2: str, n: int = 3) -> float:
    norm1 = normalize_text(s1)
    norm2 = normalize_text(s2)
    if len(norm1) < n or len(norm2) < n:
        return 1.0 if norm1 == norm2 and norm1 else 0.0
    ngrams1 = set(norm1[i : i + n] for i in range(len(norm1) - n + 1))
    ngrams2 = set(norm2[i : i + n] for i in range(len(norm2) - n + 1))
    inter = len(ngrams1 & ngrams2)
    union = len(ngrams1 | ngrams2)
    return inter / union if union > 0 else 0.0


def compute_word_ngram_overlap(s1: str, s2: str, n: int = 3) -> float:
    w1 = normalize_text(s1).split()
    w2 = normalize_text(s2).split()
    if len(w1) < n or len(w2) < n:
        return 1.0 if w1 == w2 and w1 else 0.0
    ngrams1 = set(tuple(w1[i : i + n]) for i in range(len(w1) - n + 1))
    ngrams2 = set(tuple(w2[i : i + n]) for i in range(len(w2) - n + 1))
    inter = len(ngrams1 & ngrams2)
    union = len(ngrams1 | ngrams2)
    return inter / union if union > 0 else 0.0


def check_copy_detection(student_answer: str, last_tutor_text: str) -> Tuple[bool, float]:
    """
    Returns (is_copied, similarity_score).
    Triggers if word Jaccard >= 0.60 or 3-gram overlap (word or char) >= 0.60.
    Also triggers if the student answer (>= 15 chars) is directly contained in the tutor text.
    """
    if not student_answer or not last_tutor_text:
        return False, 0.0
    s_ans = normalize_text(student_answer)
    s_tut = normalize_text(last_tutor_text)
    if len(s_ans) >= 15 and s_ans in s_tut:
        return True, 1.0
    jaccard = compute_word_jaccard(student_answer, last_tutor_text)
    w_overlap = compute_word_ngram_overlap(student_answer, last_tutor_text, n=3)
    c_overlap = compute_char_ngram_overlap(student_answer, last_tutor_text, n=3)
    max_sim = max(jaccard, w_overlap, c_overlap)
    return (max_sim >= 0.60), max_sim


def is_near_duplicate_question(candidate_text: str, asked_texts: List[str]) -> bool:
    for asked in asked_texts:
        if not asked:
            continue
        jaccard = compute_word_jaccard(candidate_text, asked)
        c_overlap = compute_char_ngram_overlap(candidate_text, asked, n=3)
        if jaccard >= 0.70 or c_overlap >= 0.75:
            return True
    return False


def select_check_question(
    topic: str,
    concept_id: str,
    correct_checks: int,
    subtopic_data: Optional[Dict[str, Any]] = None,
    asked_question_ids: Optional[List[str]] = None,
    asked_question_texts: Optional[List[str]] = None,
    exclude_question_id: Optional[str] = None,
    target_tier_override: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """
    Selects check questions with strict no-repeat and diversification guarantees:
    - Never asks a question already in asked_question_ids or matching exclude_question_id.
    - Never asks a question near-duplicate (Jaccard >= 0.70 or char 3-gram >= 0.75) with asked_question_texts.
    - Tiered progression:
        * Check 0: Tier 1 (Recall / Foundational intuition)
        * Check 1: Tier 2 (Application / Calculation)
        * Check 2+: Tier 3 (Transfer / Edge case synthesis)
    - If candidate pool is exhausted, dynamically synthesizes 3 fresh questions for this concept.
    """
    if not subtopic_data:
        subtopic_data = get_subtopic_pedagogical_data(topic, concept_id)
    if not subtopic_data:
        return None

    q_bank = subtopic_data.get("question_bank", [])
    if not q_bank:
        return None

    asked_ids = set(asked_question_ids or [])
    if exclude_question_id:
        asked_ids.add(exclude_question_id)
    asked_texts = [t for t in (asked_question_texts or []) if t]

    target_tier = target_tier_override if target_tier_override is not None else (1 if correct_checks == 0 else (2 if correct_checks == 1 else 3))

    def is_candidate_valid(q) -> bool:
        qid = getattr(q, "question_id", "") if not isinstance(q, dict) else q.get("question_id", "")
        qtext = getattr(q, "question", "") if not isinstance(q, dict) else q.get("question", "")
        if qid and qid in asked_ids:
            return False
        if qtext and is_near_duplicate_question(qtext, asked_texts):
            return False
        return True

    # 1. Filter candidates matching the target tier
    tier_candidates = [q for q in q_bank if getattr(q, "difficulty_tier", 1) == target_tier and is_candidate_valid(q)]

    # 2. If no valid candidates in target tier, search other tiers
    chosen_q = None
    if tier_candidates:
        chosen_q = tier_candidates[0]
    else:
        other_candidates = [q for q in q_bank if is_candidate_valid(q)]
        if other_candidates:
            # Prefer higher tier if correct_checks >= 2, else lowest available
            if correct_checks >= 2:
                other_candidates.sort(key=lambda q: getattr(q, "difficulty_tier", 1), reverse=True)
            else:
                other_candidates.sort(key=lambda q: getattr(q, "difficulty_tier", 1))
            chosen_q = other_candidates[0]

    # 3. If still exhausted, dynamically append 3 fresh questions for this concept
    if not chosen_q:
        clean_title = concept_id.replace("_", " ").title() if concept_id else topic
        clean_topic = topic.replace("_", " ").title()
        curr_len = len(q_bank)
        fresh_q1 = DynamicCheckQuestion(
            question_id=f"{concept_id}_dyn_{curr_len + 1}",
            question=f"In the context of {clean_title}, how do system constraints prevent state corruption or incorrect outcomes?",
            expected_answer=f"System constraints enforce boundary invariants and validate state transitions in {clean_topic}.",
            evaluation_criteria=["Mentions invariant validation", "Explains protection against corruption"],
            difficulty_tier=target_tier,
            is_transfer=(target_tier == 3),
        )
        fresh_q2 = DynamicCheckQuestion(
            question_id=f"{concept_id}_dyn_{curr_len + 2}",
            question=f"Contrast the nominal operation of {clean_title} against its behavior when unexpected input occurs.",
            expected_answer=f"Nominal operation performs deterministic state updates; unexpected inputs trigger validation guards or fallbacks.",
            evaluation_criteria=["Contrasts nominal vs unexpected behavior", "Mentions guard/fallback actions"],
            difficulty_tier=target_tier,
            is_transfer=(target_tier == 3),
        )
        fresh_q3 = DynamicCheckQuestion(
            question_id=f"{concept_id}_dyn_{curr_len + 3}",
            question=f"How would an engineer verify that {clean_title} has executed correctly in an end-to-end {clean_topic} pipeline?",
            expected_answer=f"By asserting post-conditions, checking output invariants, and confirming state consistency.",
            evaluation_criteria=["Specifies post-condition verification", "Checks state consistency"],
            difficulty_tier=target_tier,
            is_transfer=(target_tier == 3),
        )
        q_bank.extend([fresh_q1, fresh_q2, fresh_q3])
        chosen_q = fresh_q1

    chosen_tier = getattr(chosen_q, "difficulty_tier", target_tier)
    return {
        "question_id": getattr(chosen_q, "question_id", f"{concept_id}_q"),
        "question": getattr(chosen_q, "question", ""),
        "expected_answer": getattr(chosen_q, "expected_answer", ""),
        "evaluation_criteria": getattr(chosen_q, "evaluation_criteria", []),
        "evaluator_type": getattr(chosen_q, "evaluator_type", "llm"),
        "question_type": getattr(chosen_q, "question_type", "conceptual"),
        "difficulty_tier": chosen_tier,
        "is_transfer": getattr(chosen_q, "is_transfer", chosen_tier == 3),
        "concept_id": concept_id,
    }
