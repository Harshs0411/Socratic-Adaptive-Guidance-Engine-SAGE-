# SAGE: High-Impact Resume & Portfolio Bullet Points

These bullet points are formatted with the **Google XYZ Formula** (*"Accomplished [X] as measured by [Y], by doing [Z]"*) and cite verified empirical metrics extracted from the 160-trial comparative ablation benchmark (`docs/results/results.csv` and `docs/RESULTS.md`).

---

## 🎯 Executive / Software Engineering (AI / Full-Stack)

* **Engineered SAGE, a distributed multi-agent adaptive tutoring platform** (FastAPI, LangGraph, React 18, SQLite/PostgreSQL) that dynamically personalizes computer science pedagogy, **increasing novice learning gain by 66% ($0.991$ vs $0.597$ Hake's $g$)** and **cutting time-to-mastery by 55% (15.2 vs 34.2 turns)** across 160 benchmarked student trials.
* **Architected a zero-penalty doubt-routing pipeline with a LIFO checkpoint stack**, **eliminating 100% of false grading penalties (0.00 vs 13.3 per session)** for inquisitive students by decoupling conceptual questions from evaluative answers and preserving in-flight quiz state across turns.
* **Designed a Continuous Bayesian Knowledge Tracing (BKT) engine** with continuous evidence interpolation, **slashing latent skill estimation error by 84% ($0.055$ vs $0.337$ MAE)** compared to legacy interviewer architectures by filtering conversational noise from Bayesian posterior updates.
* **Developed a hybrid two-tier intent classifier** (deterministic regex pre-filter + fallback LLM), processing 90%+ of conversational checkpoints with **sub-millisecond latency and zero token cost** while guaranteeing safety invariants on unasked questions.
* **Implemented Mode-Aware Dual-Pedagogy routing** that dynamically switches between **Mode 2 (Teach-First)** with analogies and dual worked examples for novices ($P(L) < 0.65$) and **Mode 1 (Socratic Check & Transfer)** for advanced learners, validated through automated end-to-end API suites (40+ passing tests).

---

## 🔬 Machine Learning & Cognitive AI Focus

* **Built an agentic cognitive modeling system** implementing Continuous Bayesian Knowledge Tracing ($P(L_0)=0.20, P(T)=0.07, P(G)=0.25, P(S)=0.10$) and exponential inter-session forgetting ($\lambda=0.03$), accurately tracking student mastery trajectories across topologically sorted prerequisite DAGs.
* **Implemented an adversarial Pedagogical Critic agent** (`gpt-4o`) that continuously audits generated instruction for factual validity, clarity, and zero-answer leakage, rejecting flawed responses prior to student delivery.
* **Authored an empirical ablation evaluation suite** (`results.csv`) simulating 4 student personas across 20 random seeds, rigorously verifying that SAGE achieves statistically significant gains ($p < 0.001$) over standard single-agent quiz-bot architectures.

---

## 💻 Full-Stack Systems & Backend Engineering Focus

* **Architected an asynchronous FastAPI backend** with connection pooling and transactional SQLite/PostgreSQL persistence, providing crash-safe session rehydration and state synchronization across complex cyclic multi-agent graphs.
* **Crafted a modern React 18 + Vite frontend** featuring interactive Mermaid.js dependency DAGs, real-time BKT mastery telemetry, in-line code execution sandboxes, and context-aware quick-action reply bars.
* **Maintained 100% test suite reliability** across 40+ unit and integration tests covering database migrations, concurrent session isolation, intent edge cases, and end-to-end FastAPI endpoint lifecycles.
