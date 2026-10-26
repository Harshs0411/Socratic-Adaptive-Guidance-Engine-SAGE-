"""
Meta Request Agent for SAGE Tutor (Requirement 3 & 12).
Handles student requests regarding learning flow, pacing, explanation strategies,
and skipping:
- 'explain differently'
- 'give an example'
- 'slow down' / 'speed up'
- 'skip this'
- 'take a break'
"""

from typing import Dict, Any
from multi_agent_tutor.app.graph.state import TutorState
from multi_agent_tutor.app.schemas.socratic import SocraticResponse


def meta_agent_node(state: TutorState) -> Dict[str, Any]:
    """
    LangGraph node: Addresses metacognitive and pacing requests warmly and constructively.
    """
    intent_data = state.get("detected_intent") or {}
    subintent = intent_data.get("meta_subintent", "explain_differently")
    pending_q = state.get("pending_question")
    topic = state.get("target_topic", "General")

    q_text = ""
    if isinstance(pending_q, dict):
        q_text = pending_q.get("question", "")
    elif pending_q:
        q_text = str(pending_q)

    signals = dict(state.get("signals") or {})
    if subintent == "slow_down":
        signals["pace"] = "slower"
        signals["step_size"] = "tiny"
    elif subintent == "speed_up":
        signals["pace"] = "faster"
        signals["concise"] = True
    elif subintent == "give_example":
        signals["needs_example"] = True
    elif subintent == "explain_differently":
        signals["explanation_style"] = "alternative_analogy"
    elif subintent == "skip":
        signals["skip_requested"] = True

    if subintent == "slow_down":
        msg = (
            f"Understood! Let's take a breath and slow our pace down. There's no rush in {topic}. "
            f"We'll take this one tiny step at a time.\n\n"
        )
        if q_text:
            msg += f"Looking back at our question:\n**{q_text}**\n\nWhat is the very first piece of information you notice?"
        else:
            msg += "What part of this concept felt a bit too fast for you?"

    elif subintent == "speed_up":
        msg = (
            f"Got it! Let's pick up the momentum. "
        )
        if q_text:
            msg += f"Here is our challenge question:\n**{q_text}**"
        else:
            msg += "Let's move straight into a quick check problem to test your understanding."

    elif subintent == "give_example":
        from multi_agent_tutor.app.Agents.teaching_agent import get_subtopic_pedagogical_data
        ped = get_subtopic_pedagogical_data(topic, state.get("current_concept") or "")
        ex1 = ped.get("worked_examples", [None])[0] if ped else None
        if ex1:
            ex_title = getattr(ex1, "title", "Worked Example") if not isinstance(ex1, dict) else ex1.get("title", "Worked Example")
            ex_prob = getattr(ex1, "problem", "") if not isinstance(ex1, dict) else ex1.get("problem", "")
            ex_steps = getattr(ex1, "step_by_step_solution", []) if not isinstance(ex1, dict) else ex1.get("step_by_step_solution", [])
            steps_str = "\n".join(f"  {s}" for s in ex_steps)
            ex_takeaway = getattr(ex1, "key_takeaway", "") if not isinstance(ex1, dict) else ex1.get("key_takeaway", "")
            msg = (
                f"Here is a concrete worked example in {topic} ({ex_title}):\n\n"
                f"**Problem:** {ex_prob}\n\n"
                f"**Walkthrough:**\n{steps_str}\n\n"
                f"**Key Takeaway:** {ex_takeaway}\n\n"
            )
        else:
            msg = f"Here is a concrete worked example in {topic}:\n\nLet's trace how the fundamental mechanism operates step-by-step.\n\n"
        if q_text:
            msg += f"Now with that example in mind, back to our question:\n**{q_text}**"
        else:
            msg += "Does seeing this worked example step-by-step make the idea clearer?"

    elif subintent == "explain_differently":
        from multi_agent_tutor.app.Agents.teaching_agent import get_subtopic_pedagogical_data
        ped = get_subtopic_pedagogical_data(topic, state.get("current_concept") or "")
        analogies = ped.get("analogies", []) if ped else []
        alt_analogy = analogies[1] if len(analogies) > 1 else (analogies[0] if analogies else f"An intuitive mental model for {topic}.")
        msg = (
            f"Let's look at this from a completely fresh angle! 🔄\n\n"
            f"💡 **Alternative Analogy:** {alt_analogy}\n\n"
        )
        if q_text:
            msg += f"Connecting this to our question:\n**{q_text}**"
        else:
            msg += "Does that real-world comparison feel more intuitive?"

    elif subintent == "request_visual":
        from multi_agent_tutor.app.Agents.visual_agent import get_visual_for_concept, generate_fallback_visual
        concept = state.get("current_concept", "binary_search_fundamentals")
        vis = get_visual_for_concept(topic, concept) or generate_fallback_visual(concept)
        visual_data = [vis.model_dump() if hasattr(vis, "model_dump") else vis.dict()]
        signals["visuals"] = visual_data

        if vis.type == "mermaid":
            rendered_block = f"```mermaid\n{vis.content}\n```"
        else:
            rendered_block = f"```\n{vis.content}\n```"

        msg = (
            f"Here is a helpful visual diagram for **{vis.title}**:\n\n"
            f"{rendered_block}\n\n"
            f"*{vis.caption}*\n\n"
        )
        if q_text:
            msg += f"With this diagram in mind, let's look back at our question:\n**{q_text}**"
        else:
            msg += "Does seeing this diagram help you picture the idea more clearly?"

    elif subintent == "skip":
        msg = (
            f"You got it. Let's adjust our path in {topic}. "
            "If this concept is a hard prerequisite for later topics, we'll keep it light, but let's make sure you have the essentials.\n\n"
        )
        if q_text:
            msg += "Let's move past that specific check. Would you like to try a different challenge, or move to the next sub-concept?"
        else:
            msg += "Moving forward to the next milestone!"

    else:
        # Default break or general meta
        msg = (
            f"Take all the time you need! Learning {topic} deeply takes patience. "
            "Whenever you're ready, let me know and we'll pick right back up."
        )

    socratic_resp = SocraticResponse(
        message=msg,
        question=q_text or "How would you like to proceed?",
        action="explain",
        question_type="conceptual",
        expected_answer="Student response",
        evaluator_type="llm",
        evaluation_criteria=["Student acknowledges guidance."],
    )

    return {
        "tutor_response": msg,
        "socratic_response": socratic_resp,
        "signals": signals,
        "student_input": None,
    }
