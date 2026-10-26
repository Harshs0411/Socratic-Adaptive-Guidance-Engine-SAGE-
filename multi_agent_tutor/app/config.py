"""
Centralized Configuration for SAGE Multi-Agent Adaptive AI Tutor.
Eliminates magic numbers across all agents, BKT cognitive modeling,
teaching policies, remediation caps, and retention schedules.
"""

# =====================================================================
# MASTERY & THRESHOLDS (Requirement 2 & 11)
# =====================================================================
# Threshold above which a topic is taught in Mode 1 (High Mastery Q&A)
# Below this, topic is taught in Mode 2 (Teach First -> Check Understanding)
MODE_SWITCH_MASTERY_THRESHOLD: float = 0.65

# Threshold for marking a concept/topic as fully mastered
MASTERY_ADVANCE_THRESHOLD: float = 0.85

# Prerequisite gating threshold: concepts cannot be started until all prereqs >= this
PREREQUISITE_THRESHOLD: float = 0.60

# Review threshold: concept learned but should be reinforced if below this
REVIEW_THRESHOLD: float = 0.60


# =====================================================================
# PEDAGOGICAL POLICY & CAPS (Requirement 3, 10, 11)
# =====================================================================
# Maximum number of nested doubts allowed in the doubt stack
DOUBT_STACK_MAX_DEPTH: int = 3

# Maximum remediation re-teach attempts before changing strategy or flagging
REMEDIATION_CAP: int = 3

# Hint ladder maximum level (1: gentle nudge, 2: bigger hint, 3: partial step, 4: full explanation)
HINT_LADDER_MAX_LEVEL: int = 4

# Target zone for adaptive question selection (70-80% expected success)
TARGET_SUCCESS_MIN: float = 0.70
TARGET_SUCCESS_MAX: float = 0.80

# Subtopic completion criteria: minimum correct checks needed to complete subtopic
SUBTOPIC_MIN_CORRECT_CHECKS: int = 3
SUBTOPIC_REQUIRE_TRANSFER: bool = True


# =====================================================================
# COGNITIVE MODELING (Continuous BKT & Forgetting - Requirement 7 & 11)
# =====================================================================
# Default BKT parameters (Single Source of Truth)
DEFAULT_P_L0: float = 0.20       # Default prior mastery for unassessed topics
DEFAULT_P_TRANSIT: float = 0.07  # Transition (learning rate) during instruction (tuned for 4-6 checks)
DEFAULT_P_GUESS: float = 0.25    # Default guess probability
DEFAULT_P_SLIP: float = 0.10     # Default slip probability

# Forgetting decay parameter lambda (applied only between sessions or at session start)
# Decay model: P(L_t) = max(RETENTION_FLOOR, P(L_0) + (P(L_{t-1}) - RETENTION_FLOOR) * exp(-lambda * delta_days))
FORGETTING_LAMBDA: float = 0.05
RETENTION_FLOOR: float = 0.20

# "I don't know" response handling: minimum evidence floor without harsh penalty
DONT_KNOW_EVIDENCE_FLOOR: float = 0.35

# =====================================================================
# EVALUATION & COMPARATIVE ABLATION (Part 3)
# =====================================================================
# When True, every student message is graded as an answer, with no intent routing
# and no teach-first (the original baseline interviewer behavior).
LEGACY_MODE: bool = False
