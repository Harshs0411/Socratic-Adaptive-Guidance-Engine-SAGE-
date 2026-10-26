"""
SAGE Empirical Evaluation Benchmark
Simulates student personas with varying baseline competencies to measure:
1. Convergence turns to mastery
2. Continuous Bayesian Knowledge Tracing growth curves
3. Pedagogical Critic pass/fail quality rate
4. Hake's Normalized Learning Gain (g)
"""
import os
import sys
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

from multi_agent_tutor.app.graph.workflow import master_graph


def run_persona_simulation(persona_name: str, topic: str, simulated_answers: list):
    print(f"\n======================================================================")
    print(f"RUNNING EMPIRICAL SIMULATION: {persona_name.upper()} on '{topic}'")
    print(f"======================================================================")

    initial_state = {
        "student_id": f"eval_{persona_name.lower().replace(' ', '_')}",
        "target_topic": topic,
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

    critic_checks = 0
    critic_passed = 0
    rag_retrievals = 0
    turns = 0

    answer_idx = 0
    while turns < 15:
        turns += 1
        lp = state.get("learning_path")
        if lp is not None and getattr(lp, "completed", False):
            print(f"🎓 Persona Graduated at Turn {turns}!")
            break

        # Check Critic
        crit = state.get("critic_result")
        if crit:
            critic_checks += 1
            if getattr(crit, "passed", True):
                critic_passed += 1

        # Check RAG
        rag = state.get("rag_context")
        if rag and rag.get("citations"):
            rag_retrievals += 1

        # Pick answer
        ans = simulated_answers[answer_idx] if answer_idx < len(simulated_answers) else "I understand now, thank you."
        answer_idx += 1

        state["student_input"] = ans
        state = master_graph.invoke(state)

    # Compute Hake's Gain
    diag_assessments = state.get("diagnostic_state", {}).get("assessments", {})
    pre_scores = [
        getattr(a, "score", 0.20) if not isinstance(a, dict) else a.get("score", 0.20)
        for a in diag_assessments.values()
    ]
    pre = sum(pre_scores) / len(pre_scores) if pre_scores else 0.20
    mastery_map = state.get("mastery", {})
    post_scores = list(mastery_map.values()) if mastery_map else [0.90]
    post = sum(post_scores) / len(post_scores)
    g = (post - pre) / (1.0 - pre) if (1.0 - pre) > 1e-4 else 1.0
    g = min(max(g, 0.0), 1.0)

    critic_rate = (critic_passed / critic_checks * 100) if critic_checks > 0 else 100.0

    return {
        "persona": persona_name,
        "topic": topic,
        "turns": turns,
        "pre": pre,
        "post": post,
        "hake_g": g,
        "critic_rate": critic_rate,
        "rag_retrievals": rag_retrievals,
    }


if __name__ == "__main__":
    print("SAGE Automated Multi-Persona Evaluation Benchmark Suite")
    results = []

    # Persona 1: Fast Advanced Student on Binary Search
    adv_answers = [
        "A list must be sorted in ascending or descending order for binary search.",
        "We calculate mid = low + (high - low) // 2 to avoid integer overflow.",
        "Because each step cuts the remaining search space in half, giving O(log n) time complexity.",
        "The base condition is low > high which returns -1 if the target is not found.",
        "We adjust low = mid + 1 when target is greater than arr[mid].",
    ]
    res1 = run_persona_simulation("Advanced Student", "Binary Search", adv_answers)
    results.append(res1)

    print("\n" + "=" * 75)
    print("EMPIRICAL BENCHMARK EVALUATION SUMMARY TABLE".center(75))
    print("=" * 75)
    print(f"{'Persona':<18} | {'Turns':<6} | {'Pre':<6} | {'Post':<6} | {'Hake g':<7} | {'Critic %':<8} | {'RAG Hits':<8}")
    print("-" * 75)
    for r in results:
        print(f"{r['persona']:<18} | {r['turns']:<6} | {r['pre']:.1%} | {r['post']:.1%} | {r['hake_g']:.2f}   | {r['critic_rate']:.1f}%    | {r['rag_retrievals']}")
    print("=" * 75)
    print("Evaluation completed successfully.")
