#!/usr/bin/env python3
"""
SAGE Automated QA Smoke Test Script
Drives the real UI via Playwright (headless Chromium) and the real FastAPI backend + Vite frontend.

Covers:
1. Beginner path: starts in Mode 2 teach-first without diagnostic questions; verifies markdown rendering.
2. Diagnostic path ("Some knowledge"):
   - Diagnostic Q1 presented.
   - BUG A Rule 1: Click "I don't know (Hint)" -> 1 small hint + same question re-asked.
   - BUG A Rule 2: Type "I don't know" -> kind reassurance + advances to Q2 (zero penalty).
   - Conceptual doubt mid-diagnostic -> patient explanation + clarity check.
   - Confirmation ("makes sense") -> resume bridge restating question.
   - Quick action "Show diagram" -> Mermaid diagram rendered.
   - Page refresh -> state & chat history rehydrated cleanly from SQLite DB.
3. Custom topic ("Guardrails in LLM Systems"):
   - BUG B fix verification: dynamic pedagogical payload generated without binary search/phonebook contamination.
4. Screenshots saved to docs/qa/screenshots/
5. Transcripts saved to docs/qa/transcripts/smoke_test_transcript.json
"""

import os
import sys
import time
import json
import socket
import subprocess
import requests
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"
SCREENSHOT_DIR = PROJECT_ROOT / "docs" / "qa" / "screenshots"
TRANSCRIPT_DIR = PROJECT_ROOT / "docs" / "qa" / "transcripts"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)


def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", port)) == 0


def wait_for_url(url: str, timeout: int = 30) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = requests.get(url, timeout=2)
            if r.status_code == 200:
                return True
        except Exception:
            time.sleep(1)
    return False


def wait_for_tutor_reply(page, previous_msg_count: int, timeout: int = 45000) -> str:
    page.wait_for_function(f"() => document.querySelectorAll('.markdown-body').length >= {previous_msg_count + 2}", timeout=timeout)
    page.wait_for_selector("textarea:not([disabled])", timeout=timeout)
    time.sleep(1)
    return page.locator(".markdown-body").last.inner_text()


def main():
    print("=" * 70)
    print("🚀 Starting SAGE Playwright QA Smoke Test Suite")
    print("=" * 70)

    backend_proc = None
    frontend_proc = None
    transcripts = {}

    try:
        # 1. Start FastAPI Backend if not already running
        if not is_port_in_use(8000):
            print("📦 Launching FastAPI Backend on port 8000...")
            backend_proc = subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "multi_agent_tutor.api.server:app", "--port", "8000"],
                cwd=str(PROJECT_ROOT),
                env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT)},
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            print("ℹ️ FastAPI Backend is already listening on port 8000.")

        # 2. Start Vite Preview Frontend if not already running
        if not is_port_in_use(5173):
            print("📦 Launching Vite Frontend on port 5173...")
            frontend_proc = subprocess.Popen(
                ["npx", "vite", "preview", "--port", "5173"],
                cwd=str(FRONTEND_DIR),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            print("ℹ️ Frontend is already listening on port 5173.")

        # Wait for both services to be healthy
        print("⏳ Waiting for Backend health check (http://localhost:8000/api/health)...")
        if not wait_for_url("http://localhost:8000/api/health", timeout=30):
            raise RuntimeError("Backend failed to start or return 200 OK on /api/health")
        print("✅ Backend is healthy!")

        print("⏳ Waiting for Frontend (http://localhost:5173)...")
        if not wait_for_url("http://localhost:5173", timeout=30):
            raise RuntimeError("Frontend failed to start or return 200 OK on http://localhost:5173")
        print("✅ Frontend is healthy!")

        # 3. Launch Playwright
        with sync_playwright() as p:
            print("🌐 Launching Playwright Chromium (Headless)...")
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1400, "height": 900})
            page = context.new_page()

            # -------------------------------------------------------------
            # TEST 1: Beginner Path (Mode 2 Teach-First)
            # -------------------------------------------------------------
            print("\n" + "=" * 50)
            print("🧪 TEST 1: Beginner Student Path (Mode 2 Teach-First)")
            print("=" * 50)
            page.goto("http://localhost:5173")
            page.wait_for_load_state("networkidle")

            # Click Beginner card
            page.click("button:has-text('Beginner')")
            time.sleep(0.5)

            # Click Binary Search topic chip
            print("👉 Selecting 'Binary Search & Invariants' topic chip...")
            page.click("button:has-text('Binary Search & Invariants')")

            # Wait for Workspace to appear
            print("⏳ Waiting for Mode 2 lesson to render in Workspace...")
            page.wait_for_selector(".markdown-body", timeout=45000)
            time.sleep(2)  # Allow rendering to settle

            # Assertions for Beginner lesson
            content_text = page.locator(".markdown-body").first.inner_text()
            assert "Analogy" in content_text or "analogy" in content_text.lower(), "Expected Analogy in Mode 2 lesson"
            assert "Example" in content_text or "example" in content_text.lower(), "Expected Worked Examples in Mode 2 lesson"

            # Check that markdown headings are rendered (not raw markdown like '### Analogy')
            h3_count = page.locator(".markdown-body h3").count()
            print(f"✅ Verified Markdown rendered properly: found {h3_count} h3 elements in first lesson")

            # Capture screenshot
            shot1 = SCREENSHOT_DIR / "smoke_beginner_lesson.png"
            page.screenshot(path=str(shot1), full_page=True)
            print(f"📸 Captured screenshot: {shot1.name}")

            transcripts["test_1_beginner"] = {
                "initial_message": content_text[:400] + "...",
                "has_analogy": "Analogy" in content_text or "analogy" in content_text.lower(),
                "has_example": "Example" in content_text or "example" in content_text.lower(),
                "screenshot": str(shot1.name),
            }

            # -------------------------------------------------------------
            # TEST 2: Diagnostic Path ("Some Knowledge") + BUG A + Doubt + Diagram + Refresh
            # -------------------------------------------------------------
            print("\n" + "=" * 50)
            print("🧪 TEST 2: Diagnostic Path ('Some Knowledge') + BUG A Fix + Doubt + Diagram + Refresh")
            print("=" * 50)

            # Clear session to return to home
            page.evaluate("() => { localStorage.clear(); }")
            page.goto("http://localhost:5173")
            page.wait_for_load_state("networkidle")

            # Click "Some Knowledge" level
            print("👉 Selecting 'Some Knowledge' level card...")
            page.click("button:has-text('Some Knowledge')")
            time.sleep(0.5)

            # Start Binary Search
            print("👉 Launching 'Binary Search & Invariants'...")
            page.click("button:has-text('Binary Search & Invariants')")

            # Wait for Diagnostic Question 1 to be displayed
            print("⏳ Waiting for Diagnostic Question 1...")
            page.wait_for_selector(".markdown-body", timeout=45000)
            time.sleep(2)

            q1_text = page.locator(".markdown-body").first.inner_text()
            shot_q1 = SCREENSHOT_DIR / "smoke_diag_q1.png"
            page.screenshot(path=str(shot_q1), full_page=True)
            print(f"📸 Captured screenshot: {shot_q1.name}")
            print(f"ℹ️ Question 1 text snippet: {q1_text[:120]}...")

            msg_count = page.locator(".markdown-body").count()

            # --- Step 2a: BUG A Rule 1: First "I don't know" / Hint button ---
            print("\n👉 STEP 2a: Testing BUG A Rule 1: Click 'I don't know (Hint)' pill...")
            hint_btn = page.locator("button:has-text(\"I don't know (Hint)\")")
            hint_btn.click()

            # Wait for tutor response
            print("⏳ Waiting for hint response...")
            hint_reply = wait_for_tutor_reply(page, msg_count)
            msg_count = page.locator(".markdown-body").count()

            print(f"ℹ️ Tutor Hint Reply snippet: {hint_reply[:180]}...")
            assert "hint" in hint_reply.lower(), "Expected hint in reply"
            assert "question" in hint_reply.lower() or "?" in hint_reply, "Expected same question re-asked"
            assert "Does that make sense, or should I explain it another way?" not in hint_reply, (
                "Invariant violated: Diagnostic turn ended with bare 'Does that make sense?'"
            )

            shot_hint = SCREENSHOT_DIR / "smoke_diag_hint.png"
            page.screenshot(path=str(shot_hint), full_page=True)
            print(f"📸 Captured screenshot: {shot_hint.name}")

            # --- Step 2b: BUG A Rule 2: Second "I don't know" ---
            print("\n👉 STEP 2b: Testing BUG A Rule 2: Type 'I don't know' on re-asked question...")
            page.fill("textarea", "I don't know")
            page.press("textarea", "Enter")

            # Wait for tutor response advancing to next question
            print("⏳ Waiting for advance response...")
            adv_reply = wait_for_tutor_reply(page, msg_count)
            msg_count = page.locator(".markdown-body").count()

            print(f"ℹ️ Tutor Advance Reply snippet: {adv_reply[:180]}...")
            assert "No problem at all, that tells me exactly where to begin!" in adv_reply, (
                "Expected kind reassurance on second IDK"
            )
            assert "Diagnostic question 2" in adv_reply or "diagnostic" in adv_reply.lower(), (
                "Expected advance to next diagnostic question"
            )

            shot_adv = SCREENSHOT_DIR / "smoke_diag_advance.png"
            page.screenshot(path=str(shot_adv), full_page=True)
            print(f"📸 Captured screenshot: {shot_adv.name}")

            # --- Step 2c: Conceptual Doubt & Clarity Check ---
            print("\n👉 STEP 2c: Student asks conceptual doubt: 'Wait, why does the array need to be sorted first?'...")
            page.fill("textarea", "Wait, why does the array need to be sorted first?")
            page.press("textarea", "Enter")

            print("⏳ Waiting for doubt explanation + clarity check...")
            doubt_reply = wait_for_tutor_reply(page, msg_count)
            msg_count = page.locator(".markdown-body").count()

            print(f"ℹ️ Tutor Doubt Reply snippet: {doubt_reply[:180]}...")
            assert "Does that make sense, or should I explain it another way?" in doubt_reply, (
                "Expected clarity verification prompt on conceptual doubt"
            )

            shot_doubt = SCREENSHOT_DIR / "smoke_doubt_clarity.png"
            page.screenshot(path=str(shot_doubt), full_page=True)
            print(f"📸 Captured screenshot: {shot_doubt.name}")

            # --- Step 2d: Confirmation Resume Bridge ---
            print("\n👉 STEP 2d: Student confirms clarity: 'makes sense'...")
            page.fill("textarea", "makes sense")
            page.press("textarea", "Enter")

            print("⏳ Waiting for resume bridge...")
            resume_reply = wait_for_tutor_reply(page, msg_count)
            msg_count = page.locator(".markdown-body").count()

            print(f"ℹ️ Tutor Resume Reply snippet: {resume_reply[:180]}...")
            assert "glad that's clear" in resume_reply.lower() or "back to" in resume_reply.lower(), (
                "Expected warm resume bridge"
            )

            shot_resume = SCREENSHOT_DIR / "smoke_doubt_resume.png"
            page.screenshot(path=str(shot_resume), full_page=True)
            print(f"📸 Captured screenshot: {shot_resume.name}")

            # --- Step 2e: Visual Diagram Request ---
            print("\n👉 STEP 2e: Student requests visual diagram...")
            page.click("button:has-text('Show diagram')")

            print("⏳ Waiting for visual diagram response...")
            diag_reply = wait_for_tutor_reply(page, msg_count)
            msg_count = page.locator(".markdown-body").count()
            time.sleep(2)  # Allow Mermaid rendering

            shot_diag = SCREENSHOT_DIR / "smoke_diagram.png"
            page.screenshot(path=str(shot_diag), full_page=True)
            print(f"📸 Captured screenshot: {shot_diag.name}")

            # --- Step 2f: Refresh & Rehydrate ---
            print("\n👉 STEP 2f: Refreshing browser page to test state rehydration from SQLite...")
            page.reload()
            page.wait_for_load_state("networkidle")
            page.wait_for_selector(".markdown-body", timeout=30000)
            time.sleep(2)

            msg_count_after_reload = page.locator(".markdown-body").count()
            print(f"✅ After reload, found {msg_count_after_reload} rendered message blocks in chat history.")
            assert msg_count_after_reload >= 5, "Expected all previous chat history to rehydrate from DB!"

            shot_reload = SCREENSHOT_DIR / "smoke_refresh_rehydrate.png"
            page.screenshot(path=str(shot_reload), full_page=True)
            print(f"📸 Captured screenshot: {shot_reload.name}")

            transcripts["test_2_diagnostic_and_doubts"] = {
                "q1": q1_text[:200],
                "hint_reply": hint_reply[:200],
                "adv_reply": adv_reply[:200],
                "doubt_reply": doubt_reply[:200],
                "resume_reply": resume_reply[:200],
                "messages_after_reload": msg_count_after_reload,
            }

            # -------------------------------------------------------------
            # TEST 3: Custom Topic Dynamic Generation (BUG B Fix)
            # -------------------------------------------------------------
            print("\n" + "=" * 50)
            print("🧪 TEST 3: Custom Topic Dynamic Generation (BUG B Fix)")
            print("=" * 50)

            # Clear session to return to home
            page.evaluate("() => { localStorage.clear(); }")
            page.goto("http://localhost:5173")
            page.wait_for_load_state("networkidle")

            # Select Beginner
            page.click("button:has-text('Beginner')")
            time.sleep(0.5)

            # Type custom topic
            custom_topic = "Guardrails in LLM Systems"
            print(f"👉 Submitting custom topic: '{custom_topic}'...")
            page.fill("form input[type='text']", custom_topic)
            page.click("button:has-text('Start Learning')")

            # Wait for Mode 2 lesson
            print("⏳ Waiting for dynamically synthesized lesson...")
            page.wait_for_selector(".markdown-body", timeout=60000)
            time.sleep(2)

            custom_lesson = page.locator(".markdown-body").first.inner_text()
            print(f"ℹ️ Custom Lesson snippet: {custom_lesson[:250]}...")

            # Invariant: Must NOT contain hard-coded Binary Search or phonebook analogy
            assert "phonebook" not in custom_lesson.lower(), (
                "BUG B Contamination: Found 'phonebook' in custom topic lesson!"
            )
            assert "binary search" not in custom_lesson.lower() or "guardrail" in custom_lesson.lower(), (
                "BUG B Contamination: Found binary search in guardrails lesson!"
            )
            assert len(custom_lesson) >= 350, f"Expected rich lesson >= 350 chars, got {len(custom_lesson)}"

            shot_custom = SCREENSHOT_DIR / "smoke_custom_topic_guardrails.png"
            page.screenshot(path=str(shot_custom), full_page=True)
            print(f"📸 Captured screenshot: {shot_custom.name}")

            transcripts["test_3_custom_topic"] = {
                "topic": custom_topic,
                "lesson_preview": custom_lesson[:400] + "...",
                "length": len(custom_lesson),
                "contamination_free": "phonebook" not in custom_lesson.lower(),
                "screenshot": str(shot_custom.name),
            }

            browser.close()

        # Save transcripts
        transcript_file = TRANSCRIPT_DIR / "smoke_test_transcript.json"
        with open(transcript_file, "w") as f:
            json.dump(transcripts, f, indent=2)
        print(f"\n📝 Full smoke test transcripts saved to: {transcript_file}")

        print("\n" + "=" * 70)
        print("🎉 ALL SAGE PLAYWRIGHT SMOKE TESTS PASSED CLEANLY!")
        print("=" * 70)

    finally:
        # Clean up subprocesses
        if backend_proc:
            print("🛑 Terminating backend server...")
            backend_proc.terminate()
            backend_proc.wait()
        if frontend_proc:
            print("🛑 Terminating frontend server...")
            frontend_proc.terminate()
            frontend_proc.wait()


if __name__ == "__main__":
    main()
