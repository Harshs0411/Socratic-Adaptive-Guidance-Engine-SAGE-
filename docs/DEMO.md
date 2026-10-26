# SAGE: 5-Minute Viva Demonstration Script & Examiner Q&A Guide

## Part 1: Step-by-Step 5-Minute Viva Demonstration Script

### Minute 1: Onboarding & Zero-Quiz Beginner Calibration
* **Action:** Launch the frontend at `http://localhost:5173`. Select **"Binary Search & Invariants"**. Click the **"🌱 Beginner"** starting level card and click **"Start Learning"**.
* **What to Show the Examiner:**
  - Notice the tutor greets warmly and **does not ask a single diagnostic test question**.
  - Show the BKT Knowledge Meter in the left sidebar: all topics are initialized to $P(L) = 0.0\%$.
  - Highlight the top header badge: `📘 Mode 2: Teach First` is active.
* **Talking Point:** *"Most AI tutors behave like rapid-fire interviewers that immediately quiz novices on concepts they've never seen. SAGE recognizes beginners and skips diagnostics entirely to teach first from scratch."*

---

### Minute 2: Mode 2 Teach-First Scaffolding & Visual Models
* **Action:** Point out the components of SAGE's first response in the chat feed.
* **What to Show the Examiner:**
  - **Intuitive Mental Model:** Grounded real-world analogy (flipping directly to the middle of a printed dictionary).
  - **Visual Model:** An embedded, interactive Mermaid flowchart rendering the 3-way decision branch.
  - **Two Worked Examples:** Walkthrough 1 (target present) and Walkthrough 2 (target absent, pointers cross).
  - **Conversational Invitation:** The tutor does not demand an immediate answer; it asks: *"Any questions on this, or shall we try a quick check problem together?"*
* **Talking Point:** *"In Mode 2, SAGE grounds conceptual intuition with analogies, visual models, and dual worked examples before testing understanding."*

---

### Minute 3: The Doubt Invariant & Checkpoint Stack
* **Action:** Type *"Let's practice"* to trigger the first Recall Check (*"Why does Binary Search require the input array to be sorted?"*). Instead of answering, type a genuine conceptual doubt:  
  `"Wait, why do we use integer division '// 2' here?"`
* **What to Show the Examiner:**
  - Point to the **Doubts Asked Badge** in the header: `💬 Doubts: 1 (0 BKT Penalty)`.
  - Check the sidebar: BKT mastery has **not dropped by even 0.01%**.
  - SAGE explains integer division conceptually and closes with a clarity check: *"Does that make sense, or should I explain it another way?"*
* **Talking Point:** *"In a standard tutor or baseline system, this message would be graded as an incorrect answer to the pending question, penalizing the student's mastery score. In SAGE, our Doubt Agent checkpoints the pending question onto a stack and answers the doubt with zero BKT penalty."*

---

### Minute 4: Checkpoint Pop, Resume Bridge & Differentiated Re-Teaching
* **Action:** Type `"makes sense"`.
* **What to Show the Examiner:**
  - SAGE pops the checkpoint and outputs the **Resume Bridge**: *"Awesome, glad that's clear! Let's get right back to where we were: Why does Binary Search require the input array to be sorted?"*
  - Now submit a deliberate misconception: `"It works on unsorted arrays if we sort each half separately."`
  - Show that SAGE triggers **Differentiated Re-Teach Cycle 1** (alternative analogy) instead of a generic "Incorrect, try again".
* **Talking Point:** *"SAGE seamlessly restores the pending question without requiring the user to scroll up or re-read, and deploys differentiated re-teaching modalities when students struggle."*

---

### Minute 5: Subtopic Completion Rule & Graduation Report
* **Action:** Walk through correct answers for Tier 1 Recall, Tier 2 Application, and Tier 3 Transfer.
* **What to Show the Examiner:**
  - Explain the **Triple Completion Rule**: $P(L) \ge 0.85$ AND $\ge 3$ correct check questions AND at least one correct Transfer question.
  - Show the Graduation Confetti, the final DAG with green nodes, and click **"Download Official Academic Report (.md)"**.
  - Review **Hake's Normalized Learning Gain** calculation ($g = \frac{\text{Post} - \text{Pre}}{1 - \text{Pre}}$) rendered with LaTeX.
* **Talking Point:** *"SAGE doesn't let a student game the system with lucky guesses. Graduation mathematically requires probabilistic mastery, multi-turn consistency, and novel transfer problem solving."*

---

## Part 2: 8 Likely Viva Questions & Model Examiner Answers

### Q1: How does SAGE differ from a basic ChatGPT wrapper with a system prompt?
**Model Answer:**  
*"A system prompt in ChatGPT creates a purely reactive, conversational persona that lacks persistent cognitive state. When a student talks to ChatGPT, it has no mathematical model of the learner's knowledge, no stateful DAG traversal, and easily leaks answers or loses track of pending questions when the student asks a doubt. SAGE is a distributed multi-agent state graph built on LangGraph, FastAPI, and SQLite/PostgreSQL. It decouples pedagogical routing into dedicated agents (Intent Classifier, Doubt Agent, Teaching Assessor, Critic), tracks latent mastery using Continuous Bayesian Knowledge Tracing, and enforces rigid architectural invariants like the Doubt Checkpoint Stack and the Triple Completion Rule that cannot be bypassed by prompt drift."*

---

### Q2: Why did you choose Continuous Bayesian Knowledge Tracing (BKT) over Deep Knowledge Tracing (DKT)?
**Model Answer:**  
*"While Deep Knowledge Tracing using RNNs or Transformers is powerful on massive fixed datasets like Assistments, it is a black box that requires thousands of student interaction traces to train and cannot provide transparent, real-time explainability. In contrast, Continuous BKT provides interpretable Bayesian probabilities parameterized by well-established cognitive psychometrics: initial prior $P(L_0)=0.20$, learning rate $P(T)=0.07$, guess rate $P(G)=0.25$, and slip rate $P(S)=0.10$. Furthermore, standard BKT only handles binary (0/1) answers; we extended it with continuous evidence interpolation $e \in [0, 1]$ so that semantic nuances evaluated by the LLM Assessor proportionally inform the posterior update."*

---

### Q3: How do you prevent the LLM from hallucinating or prematurely leaking the answer?
**Model Answer:**  
*"We implement a multi-layered defense. First, SAGE uses an Agentic Pedagogical RAG pipeline that retrieves authoritative textbook passages and definitions from a ChromaDB vector store, grounding prompts in validated academic literature. Second, every generated tutor question passes through an adversarial Pedagogical Critic agent (`gpt-4o`) before reaching the student. The Critic audits the response against strict criteria: factual accuracy, clarity, and zero-answer leakage. If the Critic detects that the tutor leaked the answer or violated Socratic constraints, it rejects the message with specific feedback and triggers an internal regeneration loop."*

---

### Q4: What is the Doubt Invariant and why is it so critical for educational systems?
**Model Answer:**  
*"In an educational setting, curiosity and clarification must never be punished. In our Step 0 reproduction and legacy baseline, every user message was routed to the Teaching Assessor. When a student asked 'Why is mid rounded down?', the Assessor graded it as a 0% incorrect answer to the pending question, causing $P(L)$ to plummet and triggering unnecessary remedial loops. Our evaluation benchmark showed that Doubt-Heavy students suffered an average of 13.3 false grading penalties per session. The Doubt Invariant guarantees that genuine questions never touch BKT parameters, preserve pending questions on a LIFO stack, and resume gracefully upon confirmation."*

---

### Q5: If SAGE is a Socratic tutor, why do you have Mode 2 (Teach-First)? Isn't pure Socratic questioning better?
**Model Answer:**  
*"Pure Socratic dialogue assumes the learner possesses foundational intuitions that can be elicited through questioning. However, cognitive load theory and Bloom's educational taxonomy demonstrate that asking questions to a total beginner with zero prior schema causes extreme cognitive overload and frustration. Mode 2 activates when estimated mastery is below 0.65. It provides an initial anchor—a real-world analogy, visual flowchart, and two worked examples—before transitioning into Mode 1 Socratic check questions once foundational schema is established."*

---

### Q6: How do you handle terse answers or 'I don't know' without breaking intent classification?
**Model Answer:**  
*"We implemented a two-tier Intent Classifier. The first tier is a deterministic rule-based pre-filter that inspects whether a question is pending. If a question is pending, terse answers like '3', 'O(log n)', 'True', or code snippets are immediately classified as `ANSWER_ATTEMPT`. When a student says 'I don't know', it is classified as a help request rather than a failing attempt; SAGE responds by moving down the hint ladder or offering a scaffold, applying a non-punitive floor rather than a harsh BKT penalty."*

---

### Q7: What empirical methodology did you use to evaluate SAGE, and what were the results?
**Model Answer:**  
*"We conducted an empirical ablation benchmark across 160 seeded trials (4 student personas: Beginner, Intermediate, Advanced, Doubt-Heavy $\times$ 20 random seeds $\times$ 2 architectures: SAGE vs Legacy Interviewer Baseline). We measured Hake's normalized learning gain $g$, turns to completion, false doubt grading penalties, and BKT estimation error. For Beginners, SAGE achieved a Hake's gain of 0.991 vs 0.597 for the baseline, cutting turns from 34.2 down to 15.2. For Doubt-Heavy students, SAGE completely eliminated false penalties (0.00 vs 13.30) and reduced cognitive modeling error from 0.337 to 0.055."*

---

### Q8: What are the primary threats to validity or limitations of your system?
**Model Answer:**  
*"We maintain honest academic rigor regarding three limitations: First, our evaluation benchmark utilizes parameterized Bernoulli student simulations grounded in cognitive science rather than live human cohort trials in a classroom. Second, semantic LLM evaluation introduces 800ms–1200ms latency per turn compared to deterministic code compilation. Third, our gold curriculum is currently curated for Binary Search (6 topologically ordered topics with 12 question bank items); while SAGE includes an autonomous Curriculum Architect for any subject, dynamic DAG generation for arbitrary topics requires careful domain-expert verification."*
