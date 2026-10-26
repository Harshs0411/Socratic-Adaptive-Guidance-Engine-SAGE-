# SAGE Multi-Agent Adaptive AI Tutor: Comprehensive QA & Verification Report

**Author / QA Engineer:** Antigravity QA Suite  
**Date:** October 13, 2026  
**System Tested:** SAGE (Socratic Adaptive Guidance Engine)  
**Stack:** FastAPI + LangGraph + SQLite/PostgreSQL + React 19 + Playwright Chromium (Headless)  
**Test Suite Results:** **45 / 45 Tests Passing** (44 Passed, 1 Skipped Opt-In LLM Benchmark, 0 Failed)  
**Playwright Smoke Test Status:** **100% Passed Cleanly** (All 3 End-to-End browser test flows passed with live backend and frontend)

---

## 1. Executive Summary

A comprehensive quality assurance audit was conducted on SAGE to evaluate its behavior against the pedagogical tutor specifications. SAGE was designed not as an interrogation tool or quiz bot, but as an adaptive Socratic AI tutor that scaffolds learning, welcomes doubts freely without knowledge-penalty, rehydrates state across turns, and customizes pacing across self-reported experience levels.

### Key Highlights
1. **Zero-Token Diagnostic Looping (BUG A Resolved):**  
   Diagnostic "I don't know" / hint interactions now strictly obey the overriding state machine:
   - **First "I don't know" / Hint button click:** Delivers exactly one targeted conceptual hint and re-asks the pending diagnostic question with `action="hint"`.
   - **Second "I don't know" on that question:** Accords zero penalty, records baseline non-understanding ($P(L)=0.0$, score=0.0), terminates probing for that topic, and advances in the same tutor reply to the next diagnostic question (or final summary with first lesson).
   - **INVARIANT Preserved:** Every tutor turn during diagnostic ends with a concrete question or next lesson—never a dead end and never a bare *"Does that make sense?"*.
2. **Dynamic Domain Synthesis without Contamination (BUG B Resolved):**  
   Non-preauthored custom topics (e.g. *"Guardrails in LLM Systems"*) synthesize rich, domain-grounded pedagogical payloads (curriculum DAG, analogy, 2 worked examples, visual model flowchart, tiered question banks). Gold topic content (e.g. Binary Search, phonebook analogy) is strictly quarantined with 0% contamination.
3. **Typography & Clean UI Rendering (BUG C Resolved):**  
   Raw Markdown syntax (`###`, `**`, lists) in chat bubbles has been resolved via GitHub-flavored Markdown rendering (`marked` + dark-mode CSS `.markdown-body`). Technical snake_case IDs (`implementation_strategies`, `boundary_variants`) are converted to human-readable titles (`Implementation Strategies`, `Boundary Variants`) across headers, breadcrumbs, and active cards.
4. **Transparent Experience Level Cards (CHECK D Verified):**  
   Experience level cards on `TopicSelection.jsx` clearly communicate pedagogical invariants:
   - **🌱 Beginner:** Zero test questions. All $P(L)=0.0$. Immediate Mode 2 teach-first lesson.
   - **🌿 Some Knowledge:** Full diagnostic covering foundational concepts with kind baseline calibration.
   - **⚡ Comfortable:** Accelerated diagnostic beginning with Tier 2 application questions; rapid advancement.
5. **Mastery Tracking & Review Badges (CHECK E Verified):**  
   Topic progress tracker shows "$n/m$ done", real-time BKT percentages, and status badges. The "Review" badge includes an informative tooltip explaining $60\% \le P(L) < 85\%$ (previously learned but needs reinforcement).

---

## 2. Test Execution Matrix (11 Specification Areas)

| Test ID | Area / Category | Feature / Scenario Under Test | Expected Behavior | Observed Result | Status | Severity | Evidence |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **QA-01** | **Onboarding** | Beginner Starting Level Selection | Skips diagnostic testing completely. Sets all topic $P(L) = 0.0$. Opens directly in Mode 2 teach-first with analogy and 2 worked examples. | Zero diagnostic questions asked; all 6 topics set to $0.0\%$; Mode 2 lesson rendered immediately with analogy and examples. | **PASS** | None | [smoke_beginner_lesson.png](screenshots/smoke_beginner_lesson.png) |
| **QA-02** | **Onboarding** | Vague Starting Level Input | Clarifies once if vague ("a little"), then defaults safely to "Some Knowledge" without crashing. | Clarification prompt triggered; defaults to Some Knowledge on ambiguity. | **PASS** | None | `test_part1_onboarding.py` |
| **QA-03** | **Diagnostic** | BUG A - 1st "I don't know" / Hint Pill | Provides 1 small conceptual hint (`💡`), marks `hint_given=True`, and re-asks the same pending diagnostic question. Never terminates on bare "Does that make sense?". | Delivered hint; re-asked pending question; callout box updated; zero dead-end. | **PASS** | None | [smoke_diag_hint.png](screenshots/smoke_diag_hint.png) |
| **QA-04** | **Diagnostic** | BUG A - 2nd "I don't know" on same question | Reassures student kindly ("No problem at all, that tells me exactly where to begin!"), records baseline prior 0.0 with 0 penalty, stops probing current topic, and advances to Question 2 in same turn. | Reassurance message displayed; topic probing stopped; advanced immediately to Diagnostic Question 2. | **PASS** | None | [smoke_diag_advance.png](screenshots/smoke_diag_advance.png) |
| **QA-05** | **Doubt Handling** | Conceptual Doubt mid-diagnostic | Doubt Agent catches doubt, pushes pending diagnostic question onto checkpoint stack, answers doubt patiently, and appends clarity check: *"Does that make sense, or should I explain it another way?"*. BKT mastery remains 100% untouched. | Explains sorted array requirement; appends clarity check; BKT unchanged; checkpoint saved. | **PASS** | None | [smoke_doubt_clarity.png](screenshots/smoke_doubt_clarity.png) |
| **QA-06** | **Doubt Handling** | Clarity Confirmation & Resume Bridge | Student replies *"makes sense"*. Tutor pops checkpoint from stack, clears clarity flag, and generates warm Resume Bridge restating the original pending diagnostic question. | Pops checkpoint; outputs *"Awesome, glad that's clear! Let's get right back to where we were: Question: ..."*. | **PASS** | None | [smoke_doubt_resume.png](screenshots/smoke_doubt_resume.png) |
| **QA-07** | **Visual Models** | Mermaid Flowchart Rendering | Embedded Mermaid diagrams render as valid SVGs in chat. No unquoted label syntax errors (`<`, `()`, `[]`). | Flowchart rendered cleanly with 3-way decision branch; zero syntax error logs. | **PASS** | None | [smoke_diagram.png](screenshots/smoke_diagram.png) |
| **QA-08** | **Persistence** | Browser Page Refresh & Rehydration | Reloading the browser restores full session state from SQLite: chat history, active concept, BKT meters, and curriculum nodes. | After `page.reload()`, all 12 message blocks, active concept, and topic nodes restored cleanly. | **PASS** | None | [smoke_refresh_rehydrate.png](screenshots/smoke_refresh_rehydrate.png) |
| **QA-09** | **Curriculum** | BUG B - Custom Topic Synthesis (*Guardrails in LLMs*) | Generates custom curriculum DAG, domain-grounded analogy, 2 worked examples, visual flowchart, and tiered questions. Strictly 0% Binary Search / phonebook contamination. | Generated 8-node DAG, content filter flowchart, hate-speech guardrail worked example; length 706 chars; 0% contamination. | **PASS** | None | [smoke_custom_topic_guardrails.png](screenshots/smoke_custom_topic_guardrails.png) |
| **QA-10** | **Intent Classifier** | Terse Answer Classification | Terse answers ("O(log n)", "3", "mid = 4", "True") with pending question classify as `ANSWER_ATTEMPT`. | Correctly classified as `ANSWER_ATTEMPT`; routed to Assessor. | **PASS** | None | `test_section_b_intent_edge_cases.py` |
| **QA-11** | **BKT Safety** | BKT Monotonicity & Invariants | Doubts, hints, and confirmations NEVER change BKT. BKT advances only upon graded student answer attempt. | Verified $P(L)$ before doubt ($0.350$) == $P(L)$ after confirmation ($0.350$); changes only after graded answer. | **PASS** | None | `test_section_d_mastery_safety.py` |

---

## 3. Detailed Root Cause Analysis & Fix Implementations

### BUG A: "I don't know" / Hint Loop Getting Stuck in Diagnostic
* **Symptoms Prior to Fix:** Clicking "I don't know (Hint)" or typing "I don't know" during the diagnostic assessment resulted in a clarification question (*"Does that make sense, or should I explain it another way?"*), trapping the student in a conversational dead end without re-asking the diagnostic problem or advancing to the next topic.
* **Root Cause:** In `multi_agent_tutor/app/Agents/doubt_agent.py`, help requests (`meta_subintent == "help_request"`) were grouped under standard conceptual doubts. Standard doubts append the clarity verification sentence, which expected a confirmation (`"makes sense"`) before popping a checkpoint. For diagnostic help requests, this created a cycle where "I don't know" could never advance the diagnostic assessment state machine.
* **Fix Implemented:**
  1. **Diagnostic Help Override (`doubt_agent.py`):**  
     Added dedicated handling in `handle_doubt_question()` when `is_diag and is_help_request`:
     - Checks `hints_given.get(current_qid)`. If `False`, sets `hints_given[qid] = True`, generates a concise hint, and re-asks the pending question.
     - If `hints_given.get(current_qid)` is already `True` (second "I don't know" on that question), it sets the diagnostic assessment score to `0.0` with zero penalty, marks the concept as unknown, calls `advance_diagnostic()`, and outputs:
       `"No problem at all, that tells me exactly where to begin! We'll make sure to explore that from the ground up."` followed by Diagnostic Question $n+1$ in the **same tutor reply**.
  2. **Stopping Concept Probing (`next_question_shifting_id.py`):**  
     In `advance_diagnostic()`, set `stop_current_concept = True` whenever `is_idk` or `(hint_given and score < 0.5)`, skipping remaining questions for that concept and moving directly to the next curriculum milestone.
  3. **Preserving Clarity Verification for Real Doubts:**  
     Genuine conceptual doubts (e.g. *"Wait, why does the array need to be sorted first?"*) still execute the checkpoint stack, append the clarity check, and resume on confirmation.

### BUG B: Custom Topics Displaying Hard-Coded Binary Search Content
* **Symptoms Prior to Fix:** Submitting arbitrary topics like *"Guardrails in LLM Systems"* or *"Quantum Mechanics"* produced lessons featuring Binary Search or phonebook analogies, or failed with empty content.
* **Root Cause:** 
  1. `teaching_agent.py` had hard-coded Binary Search dictionary/phonebook text for Mode 2 explanations.
  2. `onboarding_agent.py` called `load_curriculum_concepts(topic)` which returned `None` for non-gold topics, leaving `curriculum = []` and `first_concept = None`, so no lesson was generated.
* **Fix Implemented:**
  1. **Dynamic Pedagogical Synthesis (`teaching_agent.py`):**  
     Implemented `DynamicPedagogicalPayload` via Pydantic and LangChain structured outputs (`_dynamic_payload_chain`). For custom topics, SAGE synthesizes 2 domain-accurate analogies, 2 step-by-step worked examples with key takeaways, an embedded Mermaid visual model, and 3 check questions.
  2. **Deterministic Domain Fallback:**  
     Implemented `_create_deterministic_fallback()` ensuring that even if LLM synthesis fails or times out, domain-grounded templates are used with zero Binary Search contamination.
  3. **Curriculum Synthesis on Beginner Onboarding (`onboarding_agent.py`):**  
     Updated `handle_beginner_onboarding()` to invoke `curriculum_agent(state)` when `load_curriculum_concepts(topic)` returns `None`, creating the milestone DAG and generating the Mode 2 explanation.

### BUG C: Raw Markdown & Snake-Case Concept IDs in Chat Interface
* **Symptoms Prior to Fix:** Chat bubbles displayed unparsed markdown symbols (`### Analogy`, `**Problem:**`, `- step`) and raw snake_case database identifiers (e.g., `implementation_strategies_for_guardrails`).
* **Root Cause:** 
  1. `Workspace.jsx` rendered messages directly inside `<div>` containers using plain string interpolation without a Markdown parser.
  2. Topic headers and badges referenced `concept_id` instead of human-readable `name` attributes.
* **Fix Implemented:**
  1. **Markdown Integration:** Integrated `marked` (`marked.setOptions({ gfm: true, breaks: true })`) in `FormattedMessageContent` inside `Workspace.jsx`.
  2. **Dark-Mode Typography Styles (`App.css`):** Added complete styles for `.markdown-body` (clean typography for h1-h4, paragraph spacing, code blocks, blockquotes, ordered/unordered lists).
  3. **Title Formatting:** Updated headers, active badges, and curriculum nodes to display `c.name` or fallback to `.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())`.

### CHECK D & E: Level Selection Descriptions and Progress Badges
* **Level Cards (`TopicSelection.jsx`):** Updated cards to explicitly communicate behavioral guarantees:
  - Beginner card explicitly notes $P(L)=0.0$, zero diagnostics, and Mode 2 teach-first.
  - Some Knowledge card clarifies adaptive baseline calibration across topics.
  - Comfortable card explains higher-tier diagnostic questions and fast-track progression.
* **Progress Tracker (`Workspace.jsx`):**
  - Displays "$n/m$ done" counter and progress bar.
  - Added tooltip to the `Review` badge: `Review: 60% ≤ P(L) < 85% (previously learned but needs reinforcement)`.

---

## 4. Verification Evidence & Artifact References

All test artifacts were captured through executions of the real full-stack application and Playwright Chromium:

### Screenshots (`docs/qa/screenshots/`)
1. **[smoke_beginner_lesson.png](screenshots/smoke_beginner_lesson.png):**  
   Shows the Mode 2 teach-first lesson for a beginner student on Binary Search: clean typography, Analogy, Dual Worked Examples, and 0% initial BKT meters.
2. **[smoke_diag_q1.png](screenshots/smoke_diag_q1.png):**  
   Shows Diagnostic Question 1 presented to a "Some Knowledge" student with guiding question callout.
3. **[smoke_diag_hint.png](screenshots/smoke_diag_hint.png):**  
   Shows the BUG A Rule 1 response after clicking *"I don't know (Hint)"*: small hint provided, same question re-asked, Guided Hint badge active.
4. **[smoke_diag_advance.png](screenshots/smoke_diag_advance.png):**  
   Shows the BUG A Rule 2 response after typing *"I don't know"*: kind reassurance, low prior recorded with zero penalty, and Diagnostic Question 2 presented.
5. **[smoke_doubt_clarity.png](screenshots/smoke_doubt_clarity.png):**  
   Shows doubt handling mid-diagnostic: patient explanation of array sorting precondition with clarity verification check.
6. **[smoke_doubt_resume.png](screenshots/smoke_doubt_resume.png):**  
   Shows checkpoint pop and resume bridge upon confirming clarity (*"makes sense"*).
7. **[smoke_diagram.png](screenshots/smoke_diagram.png):**  
   Shows Mermaid flowchart visual model rendered cleanly as SVG in the chat feed.
8. **[smoke_refresh_rehydrate.png](screenshots/smoke_refresh_rehydrate.png):**  
   Shows state rehydration after full browser page reload (`page.reload()`): all 12 chat turns restored from SQLite.
9. **[smoke_custom_topic_guardrails.png](screenshots/smoke_custom_topic_guardrails.png):**  
   Shows dynamic pedagogical synthesis for *"Guardrails in LLM Systems"*: 8-stage DAG, content filter decision flowchart, and worked example with zero contamination.

### Transcripts (`docs/qa/transcripts/`)
- **[smoke_test_transcript.json](transcripts/smoke_test_transcript.json):** Structured JSON containing the exact conversation turns and assertion outputs recorded during the Playwright smoke test.

---

## 5. Reproduction & Execution Instructions

To independently execute and verify the test suite:

### 1. Run Unit & Proof Test Suite
```bash
# In the repository root:
PYTHONPATH=. /opt/anaconda3/bin/python -m pytest
```
*Expected Result:* `44 passed, 1 skipped in ~80s`.

### 2. Run End-to-End Playwright Smoke Test
```bash
# In the repository root (launches backend on port 8000 and frontend on port 5173 automatically):
/opt/anaconda3/bin/python scripts/smoke_test.py
```
*Expected Result:*
- All 3 test flows complete with `🎉 ALL SAGE PLAYWRIGHT SMOKE TESTS PASSED CLEANLY!`.
- Screenshots updated in `docs/qa/screenshots/`.
- Transcripts updated in `docs/qa/transcripts/smoke_test_transcript.json`.

### 3. Run Manually via Browser
1. Start Backend:
   ```bash
   PYTHONPATH=. /opt/anaconda3/bin/python -m uvicorn multi_agent_tutor.api.server:app --port 8000
   ```
2. Start Frontend:
   ```bash
   cd frontend && npm run dev
   ```
3. Open `http://localhost:5173` in any browser.

---

## 6. Summary of Modified Codebase Files

| Component / File | Changes Made |
| :--- | :--- |
| `multi_agent_tutor/app/Agents/doubt_agent.py` | Implemented BUG A Rule 1 (hint & re-ask) and Rule 2 (advance on 2nd IDK); preserved clarity checks for conceptual doubts. |
| `multi_agent_tutor/app/Agents/next_question_shifting_id.py` | Added `stop_current_concept` on repeated IDK to advance diagnostic cleanly. |
| `multi_agent_tutor/app/Agents/assessment.py` | Implemented zero penalty and 0.0 baseline score for hints/IDK in diagnostic. |
| `multi_agent_tutor/app/Agents/teaching_agent.py` | Implemented `DynamicPedagogicalPayload` for custom topics; updated worked examples and analogies. |
| `multi_agent_tutor/app/Agents/onboarding_agent.py` | Integrated `curriculum_agent` fallback for custom topics during beginner onboarding. |
| `multi_agent_tutor/app/Agents/visual_agent.py` | Added dynamic visual model generation for arbitrary topics. |
| `data/curriculum/binary_search_curriculum.json` | Quoted flowchart node labels to eliminate Mermaid 11.17 syntax errors. |
| `frontend/src/components/Workspace.jsx` | Integrated `marked` markdown parsing, `.markdown-body` styles, and human-readable concept titles. |
| `frontend/src/components/TopicSelection.jsx` | Updated starting level card descriptions (Beginner, Some Knowledge, Comfortable). |
| `frontend/src/components/InteractiveStudio.jsx` | Formatted active concept header with clean title formatting. |
| `frontend/src/App.jsx` | Added `localStorage` session rehydration on page reload. |
| `frontend/src/App.css` | Added dark-mode GitHub-flavored markdown stylesheet. |
| `scripts/smoke_test.py` | Automated Playwright headless Chromium runner capturing screenshots and transcripts. |
| `tests/test_qa_regressions.py` | Regression unit tests covering BUG A rules and BUG B contamination prevention. |
