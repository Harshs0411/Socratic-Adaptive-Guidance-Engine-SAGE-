import sys
import select
import warnings

warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")
warnings.filterwarnings("ignore", message=".*NotOpenSSLWarning.*")

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

from multi_agent_tutor.app.graph.workflow import master_graph


def get_student_input() -> str:
    """
    Read student input from stdin.
    Supports single-line responses and pasted multi-line markdown/LaTeX blocks.
    """
    try:
        first_line = input("\nYOUR ANSWER (or 'quit'): ")
    except EOFError:
        return "quit"

    if first_line.strip().lower() == "quit":
        return "quit"

    if not sys.stdin.isatty():
        return first_line.strip()

    lines = [first_line]
    while True:
        rlist, _, _ = select.select([sys.stdin], [], [], 0.05)
        if rlist:
            line = sys.stdin.readline()
            if not line:
                break
            if line.strip().lower() == "quit":
                break
            lines.append(line.rstrip("\r\n"))
        else:
            break

    return "\n".join(lines).strip()


def print_banner(title: str, symbol: str = "="):
    print("\n" + symbol * 70)
    print(title.center(70))
    print(symbol * 70)


def print_diagnostic_report(state):
    print_banner("DIAGNOSTIC ASSESSMENT REPORT", "=")
    diagnostic = state.get("diagnostic_state", {})
    assessments = diagnostic.get("assessments", {})

    print(f"\nTotal Diagnostic Questions Evaluated: {len(assessments)}")
    for q_id, result in assessments.items():
        score = getattr(result, "score", 0.0)
        correctness = getattr(result, "correctness", "N/A")
        misconceptions = getattr(result, "misconceptions", [])
        print(f"\n• Question [{q_id}]: {correctness.upper()} (Score: {score:.2f})")
        if misconceptions:
            print(f"  Misconceptions: {', '.join(misconceptions)}")

    profile = state.get("learner_profile")
    if profile:
        print("\n--- Initial Concept Mastery (from Diagnostic) ---")
        for concept, c_prof in getattr(profile, "concepts", {}).items():
            print(f"  {concept.replace('_', ' ').title():<25}: {c_prof.mastery:.1%} (Confidence: {c_prof.confidence:.1%})")
        print(f"\nOverall Diagnostic Readiness: {profile.overall_readiness:.1%}")
    print("=" * 70)


def print_teaching_state(state):
    concept = state.get("current_concept", "N/A")
    mastery = state.get("mastery", {}).get(concept, 0.0)
    teaching = state.get("teaching", {})
    decision = state.get("teaching_decision")
    assessment = state.get("teaching_assessment")

    print_banner(f"SAGE TUTOR | Concept: {concept.replace('_', ' ').title()} (Mastery: {mastery:.1%})", "-")

    if assessment:
        print(f"\n[Assessor Feedback] Understanding: {assessment.understanding.title()} | Score: {assessment.score:.2f}")
        if assessment.misconceptions:
            print(f"  Identified Gaps: {', '.join(assessment.misconceptions)}")

    if decision:
        print(f"[Pedagogy Decision] Action: {decision.action.upper()} - {decision.reason}")

    resp = state.get("socratic_response")
    if resp:
        print(f"\nSAGE:\n{resp.message}")
        print(f"\nQUESTION:\n{resp.question}")
    elif state.get("tutor_response"):
        print(f"\nSAGE:\n{state['tutor_response']}")

    # Display RAG citations if present
    rag_ctx = state.get("rag_context")
    if rag_ctx and rag_ctx.get("citations"):
        print("\n[Authoritative Academic Literature Grounding (RAG)]")
        for cit in rag_ctx.get("citations", []):
            if isinstance(cit, dict):
                src = cit.get("source", "Academic Literature")
                rel = cit.get("relevance_score", 0.85)
                print(f"  • Source: {src} (Relevance: {rel:.1%})")
            else:
                print(f"  • Source: {cit}")
    print("-" * 70)


def main():
    print_banner("WELCOME TO SAGE: SOCRATIC AI TUTOR", "=")
    print("SAGE is an adaptive multi-agent Socratic tutor that can teach ANY topic,")
    print("from comprehensive subjects (e.g. CNN, NLP, Operating Systems)")
    print("to atomic base concepts (e.g. Binary Search, Ohm's Law, Recursion).")
    print("=" * 70)

    try:
        user_topic = input("\nEnter topic to learn [Default: Convolutional Neural Networks]: ").strip()
    except EOFError:
        user_topic = ""

    target_topic = user_topic if user_topic else "Convolutional Neural Networks"
    print(f"\nTarget Topic: {target_topic}")
    print("SAGE will analyze the topic, calibrate prerequisite knowledge, and guide your Socratic reasoning.")
    print("=" * 70)

    initial_state = {
        "student_id": "student_001",
        "target_topic": target_topic,
        "messages": [],
        "student_input": None,
        "curriculum": None,
        "diagnostic_state": {
            "completed": False,
            "questions": [],
            "current_question_id": None,
            "answers": {},
            "assessments": {},
        },
        "learner_profile": None,
        "mastery": {},
        "bkt_states": {},
        "learning_path": None,
        "current_concept": None,
        "teaching": {
            "current_action": "initial",
            "current_question": None,
            "attempt_count": 0,
            "misconception_history": [],
            "current_objective": None,
            "concept_completed": False,
        },
        "teaching_assessment": None,
        "teaching_decision": None,
        "socratic_response": None,
        "tutor_response": None,
        "critic_result": None,
        "retry_count": 0,
        "misconceptions": [],
        "hint_level": 0,
        "rag_context": None,
    }

    state = master_graph.invoke(initial_state)

    diagnostic_finished_announced = False

    while True:
        diag = state.get("diagnostic_state", {})

        # Check if diagnostic phase just completed
        if diag.get("completed", False) and not diagnostic_finished_announced:
            print_diagnostic_report(state)
            print_banner("BEGINNING PERSONALIZED SOCRATIC TUTORING", "=")
            diagnostic_finished_announced = True

        # Check if curriculum is fully completed
        lp = state.get("learning_path")
        if lp is not None and getattr(lp, "completed", False):
            print_banner("GRADUATION: ALL CONCEPTS MASTERED!", "=")
            print(state.get("tutor_response", "Congratulations on completing the curriculum!"))

            # Calculate Hake's Normalized Learning Gain
            diag_assessments = diag.get("assessments", {})
            pre_scores = [
                getattr(a, "score", 0.20) if not isinstance(a, dict) else a.get("score", 0.20)
                for a in diag_assessments.values()
            ]
            pre_score = sum(pre_scores) / len(pre_scores) if pre_scores else 0.20
            mastery_map = state.get("mastery", {})
            post_scores = list(mastery_map.values()) if mastery_map else [0.95]
            post_score = sum(post_scores) / len(post_scores)

            if 1.0 - pre_score > 1e-4:
                hake_g = (post_score - pre_score) / (1.0 - pre_score)
            else:
                hake_g = 1.0
            hake_g = min(max(hake_g, 0.0), 1.0)
            gain_label = "High Gain (Optimal Pedagogy)" if hake_g >= 0.70 else ("Medium Gain" if hake_g >= 0.30 else "Low Gain")

            print("\n" + "-" * 70)
            print("SCIENTIFIC LEARNING GAIN EVALUATION (Hake's Normalized Gain)".center(70))
            print("-" * 70)
            print(f"• Pre-Instruction Baseline Diagnostic Score : {pre_score:.1%}")
            print(f"• Post-Instruction Concept Mastery Score    : {post_score:.1%}")
            print(f"• Hake's Normalized Learning Gain (g)       : {hake_g:.2f} [{gain_label}]")
            print(f"• Formula: g = (Post - Pre) / (1 - Pre) = ({post_score:.2f} - {pre_score:.2f}) / (1 - {pre_score:.2f}) = {hake_g:.2f}")
            print("=" * 70)
            break

        # Display current state
        if not diag.get("completed", False):
            print_banner("DIAGNOSTIC PHASE", "-")
            print(state.get("tutor_response", ""))
            print("-" * 70)
        else:
            print_teaching_state(state)

        # Get student answer
        student_answer = get_student_input()

        if student_answer.lower() == "quit":
            print("\nSession ended by user. Thank you for learning with SAGE!")
            break

        if not student_answer:
            print("Please enter a response.")
            continue

        state["student_input"] = student_answer

        # Run master graph tick
        state = master_graph.invoke(state)


if __name__ == "__main__":
    main()


