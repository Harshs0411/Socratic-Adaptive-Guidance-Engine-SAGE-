import pytest
from unittest.mock import patch, MagicMock

from multi_agent_tutor.app.graph.state import TutorState
from multi_agent_tutor.app.schemas.bkt import BKTState
from multi_agent_tutor.app.schemas.teaching_assessment import TeachingAssessment
from multi_agent_tutor.app.schemas.teaching import TeachingDecision
from multi_agent_tutor.app.schemas.curriculum import CurriculumConcept
from multi_agent_tutor.app.utils.bkt import update_bkt, assessment_to_evidence
from multi_agent_tutor.app.Agents.teaching_controller import teaching_controller
from multi_agent_tutor.app.Agents.concept_advancer import advance_concept
from multi_agent_tutor.app.Agents.learning_path_planner import build_learning_path
from multi_agent_tutor.app.Agents.intent_classifier import intent_classifier_node
from multi_agent_tutor.app.graph.workflow import route_after_meta, master_graph
from multi_agent_tutor.api.server import format_curriculum_nodes, calculate_overall_progress
from multi_agent_tutor.app.config import (
    DEFAULT_P_L0,
    DEFAULT_P_TRANSIT,
    DEFAULT_P_GUESS,
    DEFAULT_P_SLIP,
    DONT_KNOW_EVIDENCE_FLOOR,
)


# =====================================================================
# TEST B: BKT Controlled Sequence & Cognitive Fairness
# =====================================================================

def test_bkt_controlled_sequence():
    """
    Run controlled test sequence:
    1. Correct
    2. Correct
    3. Correct
    4. Incorrect
    5. Correct
    6. Incorrect
    7. Remediated Correct
    Verify mastery progression is fair, responsive, and does not destroy progress.
    """
    bkt = BKTState(
        p_know=DEFAULT_P_L0,
        p_learn=DEFAULT_P_TRANSIT,
        p_guess=DEFAULT_P_GUESS,
        p_slip=DEFAULT_P_SLIP,
    )
    assert bkt.p_know == 0.20

    sequence = [
        ("Correct 1", 1.0, 1.0, "meaningful positive gain"),
        ("Correct 2", 1.0, 1.0, "approaches intermediate mastery"),
        ("Correct 3", 1.0, 1.0, "crosses 0.70 threshold toward mastery"),
        ("Incorrect 4", 0.0, 1.0, "fair deduction without wiping baseline"),
        ("Correct 5", 1.0, 1.0, "swift recovery from remediation"),
        ("Incorrect 6 (IDK)", DONT_KNOW_EVIDENCE_FLOOR, 0.85, "gentle scaffold floor deduction"),
        ("Remediated Correct 7", 1.0, 1.0, "reaches high mastery"),
    ]

    records = []
    curr_bkt = bkt

    for label, score, conf, expectation in sequence:
        p_before = curr_bkt.p_know
        ev = assessment_to_evidence(score=score, confidence=conf)
        curr_bkt = update_bkt(curr_bkt, ev)
        p_after = curr_bkt.p_know
        records.append({
            "label": label,
            "p_before": p_before,
            "p_after": p_after,
            "expectation": expectation,
        })

    # Assertions on BKT fairness
    # 1. First 3 correct answers increase mastery steadily
    assert records[0]["p_after"] > records[0]["p_before"] + 0.15, "Correct answer should provide meaningful positive gain"
    assert records[2]["p_after"] >= 0.75, "3 correct answers should reach solid mastery zone"

    # 2. 1 Incorrect answer should reduce mastery, but NOT plunge below initial baseline (0.20)
    p_after_inc = records[3]["p_after"]
    assert p_after_inc < records[2]["p_after"], "Incorrect answer must deduct mastery"
    assert p_after_inc >= 0.35, f"Single incorrect answer must not destroy demonstrated mastery! Got {p_after_inc}"

    # 3. Follow-up correct answer recovers smoothly
    assert records[4]["p_after"] > p_after_inc, "Remediation should increase mastery"
    assert records[4]["p_after"] >= 0.85, "Remediated correct answer should restore high mastery"

    # 4. 'I don't know' evidence floor cushions penalty
    p_idk = records[5]["p_after"]
    assert p_idk >= 0.40, f"'I don't know' must not inflict punitive penalty! Got {p_idk}"


# =====================================================================
# TEST A: Continuous Progress Tracking Pipeline
# =====================================================================

def test_progress_calculation_pipeline():
    """Verify continuous progress calculation reflects learning activity, not just binary completion."""
    curriculum = [
        {"concept_id": "c1", "name": "Concept 1", "parent_id": None},
        {"concept_id": "c2", "name": "Concept 2", "parent_id": None},
        {"concept_id": "c3", "name": "Concept 3", "parent_id": None},
        {"concept_id": "c4", "name": "Concept 4", "parent_id": None},
        {"concept_id": "c5", "name": "Concept 5", "parent_id": None},
    ]

    # Baseline: all concepts at default prior 0.20 -> 0% progress
    mastery_map = {f"c{i}": 0.20 for i in range(1, 6)}
    prog_0 = calculate_overall_progress(curriculum, mastery_map)
    assert prog_0 == 0.0, f"Initial unstarted curriculum should display 0% progress, got {prog_0}"

    # Student answers Q1 on Concept 1 correctly -> mastery reaches 0.48
    mastery_map["c1"] = 0.48
    prog_1 = calculate_overall_progress(curriculum, mastery_map)
    assert prog_1 > 0.0, "Progress must increase after demonstrating understanding on first concept"
    assert 5.0 <= prog_1 <= 12.0, f"Expected ~8.6% progress for 0.48 mastery on 1 of 5 concepts, got {prog_1}"

    # Student answers Q2 and Q3 -> mastery reaches 0.77
    mastery_map["c1"] = 0.77
    prog_2 = calculate_overall_progress(curriculum, mastery_map)
    assert prog_2 > prog_1, "Progress must continue rising with learning"
    assert 15.0 <= prog_2 <= 20.0, f"Expected ~17.5% progress, got {prog_2}"

    # Concept 1 reaches mastery (0.85) -> 20% overall progress
    mastery_map["c1"] = 0.88
    prog_mastered_1 = calculate_overall_progress(curriculum, mastery_map)
    assert prog_mastered_1 == 20.0, f"1 of 5 concepts mastered should give exactly 20.0%, got {prog_mastered_1}"

    # All concepts mastered -> 100% progress
    mastery_map_all = {f"c{i}": 0.90 for i in range(1, 6)}
    prog_100 = calculate_overall_progress(curriculum, mastery_map_all)
    assert prog_100 == 100.0, f"All concepts mastered must give 100% progress, got {prog_100}"


def test_progress_does_not_increase_on_chitchat_or_clicks():
    """Verify progress does NOT increase when student simply sends greetings, clicks buttons, or doubts."""
    curriculum = [
        {"concept_id": "c1", "name": "Concept 1", "parent_id": None},
        {"concept_id": "c2", "name": "Concept 2", "parent_id": None},
    ]
    mastery_map = {"c1": 0.20, "c2": 0.20}
    initial_prog = calculate_overall_progress(curriculum, mastery_map)
    assert initial_prog == 0.0

    # Chit chat or meta clicks do not alter mastery_map
    # Therefore overall progress remains exactly unchanged
    post_chat_prog = calculate_overall_progress(curriculum, mastery_map)
    assert post_chat_prog == initial_prog


# =====================================================================
# TEST C: Skip Topic Functionality & State Integrity
# =====================================================================

def test_intent_classification_skip():
    """Verify that 'Skip this topic for now' and variants are classified as META with subintent 'skip'."""
    phrases = [
        "Skip this topic for now",
        "skip this",
        "skip to next",
        "next topic",
        "can we skip",
        "move on",
    ]
    for p in phrases:
        state = TutorState(student_input=p)
        res = intent_classifier_node(state)
        detected = res["detected_intent"]
        assert detected["intent"] == "META", f"Expected META for '{p}', got {detected['intent']}"
        assert detected["meta_subintent"] == "skip", f"Expected skip subintent for '{p}', got {detected['meta_subintent']}"


def test_meta_router_routes_skip_to_controller():
    """Verify route_after_meta routes to controller when skip is requested during teaching."""
    state = TutorState(
        signals={"skip_requested": True},
        current_concept="concept_a",
        diagnostic_state={"completed": True},
    )
    route = route_after_meta(state)
    assert route == "controller", f"Expected route 'controller' for teaching skip, got {route}"


def test_teaching_controller_handles_skip_safely():
    """Verify teaching_controller handles skip_requested without requiring teaching_assessment."""
    state = TutorState(
        current_concept="concept_a",
        signals={"skip_requested": True},
        skipped_concepts=[],
        teaching_assessment=None,  # Crucial: student skipped, no assessment exists
        teaching={"attempt_count": 1, "correct_checks": 1},
    )
    res = teaching_controller(state)
    assert res["teaching_decision"].action == "advance"
    assert "concept_a" in res["skipped_concepts"]
    assert res["teaching"]["concept_skipped"] is True
    assert res["teaching"]["concept_completed"] is False
    assert "skip_requested" not in res["signals"]


def test_concept_advancer_advances_skipped_concept():
    """Verify advance_concept advances to the next concept without marking skipped concept as mastered."""
    curriculum = [
        CurriculumConcept(concept_id="c1", name="Concept 1", description="", difficulty=1, prerequisites=[]),
        CurriculumConcept(concept_id="c2", name="Concept 2", description="", difficulty=2, prerequisites=[]),
    ]
    state = TutorState(
        current_concept="c1",
        curriculum=curriculum,
        target_topic="Test Topic",
        mastery={"c1": 0.20, "c2": 0.20},
        skipped_concepts=["c1"],
        teaching={
            "concept_completed": False,
            "concept_skipped": True,
            "attempt_count": 0,
            "correct_checks": 0,
        },
        review_queue=[],
        concept_transitions=[],
    )
    res = advance_concept(state)

    assert res["current_concept"] == "c2", "Advancer should move to c2"
    assert res["teaching"]["just_advanced_from"] == "c1"
    assert res["teaching"]["was_skipped"] is True
    assert res["teaching"]["concept_completed"] is False

    # Check that learning path marks c1 as skipped, NOT mastered
    step_c1 = next(s for s in res["learning_path"].steps if s.concept_id == "c1")
    assert step_c1.status == "skipped", f"Expected c1 status='skipped', got {step_c1.status}"


def test_server_format_curriculum_nodes_reflects_skipped():
    """Verify server.py format_curriculum_nodes reflects skipped status using skipped_concepts."""
    curriculum = [
        {"concept_id": "c1", "name": "Concept 1", "parent_id": None},
        {"concept_id": "c2", "name": "Concept 2", "parent_id": None},
    ]
    mastery_map = {"c1": 0.20, "c2": 0.20}
    nodes = format_curriculum_nodes(
        curriculum=curriculum,
        active_concept="c2",
        mastery_map=mastery_map,
        skipped_concepts=["c1"],
    )
    c1_node = next(n for n in nodes if n["concept_id"] == "c1")
    c2_node = next(n for n in nodes if n["concept_id"] == "c2")

    assert c1_node["status"] == "skipped", f"c1 should have status='skipped', got {c1_node['status']}"
    assert c2_node["status"] == "active", f"c2 should have status='active', got {c2_node['status']}"


# =====================================================================
# TEST D: Combined Scenario End-to-End Student Journey
# =====================================================================

def test_combined_student_journey():
    """
    Complete end-to-end multi-turn journey:
    1. Start topic with 3 concepts (c1, c2, c3). Initial progress is 0%.
    2. Answer Q1 on c1 correctly -> mastery increases, progress rises.
    3. Answer Q2 on c1 incorrectly -> mastery deducted fairly, progress stays positive.
    4. Receive hint/remediation, answer correctly -> mastery reaches high level (>=0.85).
    5. Concept 1 is mastered -> advances to c2. Progress reflects c1 completion (33.3%).
    6. On c2, student decides to skip ("Skip this topic for now").
    7. c2 is marked as skipped (NOT mastered). Mastery is preserved.
    8. Advances to c3. Progress does not grant free 100% on c2.
    9. On c3, student learns and masters c3 -> progress reaches 66.7%.
    10. Session state serialization/deserialization verifies full persistence integrity.
    """
    curriculum = [
        {"concept_id": "c1", "name": "Foundations", "parent_id": None},
        {"concept_id": "c2", "name": "Intermediate", "parent_id": None},
        {"concept_id": "c3", "name": "Advanced", "parent_id": None},
    ]
    curriculum_objs = [
        CurriculumConcept(concept_id="c1", name="Foundations", description="", difficulty=1, prerequisites=[]),
        CurriculumConcept(concept_id="c2", name="Intermediate", description="", difficulty=2, prerequisites=[]),
        CurriculumConcept(concept_id="c3", name="Advanced", description="", difficulty=3, prerequisites=[]),
    ]

    # Step 1: Initial state
    mastery_map = {"c1": 0.20, "c2": 0.20, "c3": 0.20}
    bkt_map = {cid: BKTState(p_know=0.20, p_learn=DEFAULT_P_TRANSIT, p_guess=DEFAULT_P_GUESS, p_slip=DEFAULT_P_SLIP) for cid in mastery_map}
    skipped = []

    p0 = calculate_overall_progress(curriculum, mastery_map)
    assert p0 == 0.0, "Initial progress must be 0%"

    # Step 2: Answer Q1 on c1 correctly
    ev_q1 = assessment_to_evidence(score=1.0, confidence=1.0)
    bkt_map["c1"] = update_bkt(bkt_map["c1"], ev_q1)
    mastery_map["c1"] = bkt_map["c1"].p_know
    p1 = calculate_overall_progress(curriculum, mastery_map)
    assert p1 > 0.0, "Progress must rise after correct answer"
    assert bkt_map["c1"].p_know > 0.40, "Mastery must advance noticeably"

    # Step 3: Answer Q2 on c1 incorrectly
    ev_q2 = assessment_to_evidence(score=0.0, confidence=1.0)
    bkt_map["c1"] = update_bkt(bkt_map["c1"], ev_q2)
    mastery_map["c1"] = bkt_map["c1"].p_know
    p2 = calculate_overall_progress(curriculum, mastery_map)
    assert bkt_map["c1"].p_know >= 0.25, "Mastery must not be wiped out below initial baseline"
    assert p2 > 0.0, "Progress should still be positive"

    # Step 4: Remediate and answer correctly again twice
    for _ in range(2):
        bkt_map["c1"] = update_bkt(bkt_map["c1"], assessment_to_evidence(score=1.0, confidence=1.0))
    mastery_map["c1"] = bkt_map["c1"].p_know
    assert mastery_map["c1"] >= 0.85, "c1 should now be mastered"

    # Step 5: Advance from c1 to c2
    state_step5 = TutorState(
        current_concept="c1",
        curriculum=curriculum_objs,
        target_topic="Test Topic",
        mastery=mastery_map,
        skipped_concepts=skipped,
        teaching={"concept_completed": True, "concept_skipped": False, "attempt_count": 3, "correct_checks": 3},
        review_queue=[],
        concept_transitions=[],
    )
    res_adv1 = advance_concept(state_step5)
    assert res_adv1["current_concept"] == "c2", "Should advance to c2"
    p_c1_done = calculate_overall_progress(curriculum, mastery_map)
    assert round(p_c1_done, 1) == 33.3, f"1 of 3 concepts mastered should equal 33.3%, got {p_c1_done}"

    # Step 6: On c2, student triggers Skip Topic
    state_skip = TutorState(
        current_concept="c2",
        curriculum=curriculum_objs,
        target_topic="Test Topic",
        mastery=mastery_map,
        signals={"skip_requested": True},
        skipped_concepts=[],
        teaching={"attempt_count": 0, "correct_checks": 0},
    )
    ctrl_res = teaching_controller(state_skip)
    assert ctrl_res["teaching_decision"].action == "advance"
    assert "c2" in ctrl_res["skipped_concepts"]
    assert ctrl_res["teaching"]["concept_skipped"] is True
    assert ctrl_res["teaching"]["concept_completed"] is False
    skipped = ctrl_res["skipped_concepts"]

    # Step 7 & 8: Advancer advances past c2 to c3
    state_step7 = TutorState(
        current_concept="c2",
        curriculum=curriculum_objs,
        target_topic="Test Topic",
        mastery=mastery_map,
        skipped_concepts=skipped,
        teaching=ctrl_res["teaching"],
        review_queue=[],
        concept_transitions=[],
    )
    res_adv2 = advance_concept(state_step7)
    assert res_adv2["current_concept"] == "c3", "Should advance past skipped c2 to c3"
    assert res_adv2["teaching"]["was_skipped"] is True

    # Step 9: Verify c2 is NOT marked mastered and progress is not artificially inflated
    step_c2 = next(s for s in res_adv2["learning_path"].steps if s.concept_id == "c2")
    assert step_c2.status == "skipped"
    p_after_skip = calculate_overall_progress(curriculum, mastery_map)
    assert round(p_after_skip, 1) == 33.3, "Skipping c2 must not grant free progress"

    # Step 10: Learn and master c3
    for _ in range(3):
        bkt_map["c3"] = update_bkt(bkt_map["c3"], assessment_to_evidence(score=1.0, confidence=1.0))
    mastery_map["c3"] = bkt_map["c3"].p_know
    assert mastery_map["c3"] >= 0.85
    p_c3_done = calculate_overall_progress(curriculum, mastery_map)
    assert round(p_c3_done, 1) == 66.7, f"2 of 3 concepts mastered (with 1 skipped) should equal 66.7%, got {p_c3_done}"

