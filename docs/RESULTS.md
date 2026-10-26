# SAGE Empirical Evaluation & Comparative Ablation Report

> **Benchmark Design:** 20 seeded simulated trials per persona across 4 cognitive profiles (Beginner, Intermediate, Advanced, Doubt-Heavy) comparing **SAGE** (Intent-Routed Multi-Agent Socratic Tutor) against **Legacy Mode** (Interviewer Baseline that treats every message as an answer attempt without teach-first scaffolding).

## 1. Summary Results Table

| Persona | Architecture | Hake's Gain $g$ (Mean ± SD) | Turns to Mastery (Mean ± SD) | Doubts Wrongly Graded | BKT Error $|P(L) - \theta|$ |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Beginner** | **SAGE** | **0.991 ± 0.037** | **15.2 ± 4.7** | **0.00 ± 0.00** | **0.085 ± 0.025** |
| Beginner | Legacy Mode | 0.597 ± 0.415 | 34.2 ± 2.1 | 8.65 ± 1.77 | 0.345 ± 0.297 |
| **Intermediate** | **SAGE** | **1.000 ± 0.000** | **6.9 ± 1.7** | **0.00 ± 0.00** | **0.061 ± 0.046** |
| Intermediate | Legacy Mode | 1.000 ± 0.000 | 10.9 ± 5.4 | 2.50 ± 2.20 | 0.092 ± 0.030 |
| **Advanced** | **SAGE** | **1.000 ± 0.000** | **3.7 ± 1.0** | **0.00 ± 0.00** | **0.013 ± 0.014** |
| Advanced | Legacy Mode | 1.000 ± 0.000 | 3.9 ± 1.0 | 0.15 ± 0.36 | 0.076 ± 0.023 |
| **Doubt-Heavy** | **SAGE** | **1.000 ± 0.000** | **18.1 ± 7.5** | **0.00 ± 0.00** | **0.055 ± 0.043** |
| Doubt-Heavy | Legacy Mode | 0.997 ± 0.009 | 23.5 ± 8.9 | 13.30 ± 6.19 | 0.337 ± 0.370 |

## 2. Benchmark Visualizations

![Evaluation Benchmark Chart](evaluation_metrics.png)

## 3. In-Depth Empirical Findings

### A. Zero Penalty for Inquisitive Students (Doubt Invariant)
- In **Legacy Mode**, students who ask frequent questions (the **Doubt-Heavy** persona) suffer an average of **13.3 false grading penalties** per session. Because every message is graded as an answer attempt, authentic questions like *'Wait, why must the array be sorted?'* are marked incorrect, artificially depressing $P(L)$ and triggering unwanted remedial loops.
- In **SAGE**, doubts wrongly graded are **strictly 0.00 across all runs**. The rule-based intent pre-filter and LLM classifier reliably route doubts to `doubt_agent`, preserving pending questions on the checkpoint stack without touching BKT parameters.

### B. Superior Learning Efficiency via Teach-First Mode 2
- For **Beginners**, SAGE achieves **Hake's normalized gain of 0.991** vs **0.597** in Legacy mode.
- Legacy mode quizzes beginners immediately on concepts they have never seen, leading to consecutive failures. SAGE provides grounded real-world analogies, 2 worked examples, and visual trace models before testing understanding with tiered check questions (Recall -> Application -> Transfer).

### C. Cognitive Modeling Accuracy (BKT Convergence)
- SAGE reduces BKT estimation error from **0.337** down to **0.055** on Doubt-Heavy students.
- In Legacy mode, noise from conversational messages pollutes Bayesian probability updates, making BKT diverge from the student's true latent mastery.

## 4. Threats to Validity & Honest Limitations

1. **Simulated Student Behavior:** The empirical benchmark simulates student personas using parameterized Bernoulli choice models grounded in educational literature (Bloom's 2-sigma problem and Anderson's cognitive tutoring). While stochastic seeds provide statistical variance, human learners exhibit unpredictable misconceptions and conversational nuances.
2. **LLM Assessor Latency in Production:** Real-time semantic evaluation via LLMs introduces 800ms-1200ms latency compared to deterministic rule checks. The hybrid advisory architecture mitigates this by running deterministic regex/exact checks first where applicable.
3. **Scope of Curriculum:** The primary verified curriculum is Binary Search (6 topologically ordered topics with 12 question-bank items). Broader topics rely on the LLM Curriculum Architect, whose DAG generation requires domain-specific expert curation.
