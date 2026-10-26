from typing import (
    TypedDict,
    List,
    Dict,
    Optional,
    Any
)

from multi_agent_tutor.app.schemas.critic import (
    CriticOutput
)

from multi_agent_tutor.app.schemas.diagnostic import (
    DiagnosticQuestion
)

from multi_agent_tutor.app.schemas.assessment import (
    AssessmentResult
)

from multi_agent_tutor.app.schemas.learner import (
    LearnerProfile
)

from multi_agent_tutor.app.schemas.curriculum import (
    CurriculumConcept
)

from multi_agent_tutor.app.schemas.learning_path import (
    LearningPath
)

from multi_agent_tutor.app.schemas.bkt import (
    BKTState
)

from multi_agent_tutor.app.schemas.teaching import (
    TeachingState,
    TeachingDecision
)

from multi_agent_tutor.app.schemas.teaching_assessment import (
    TeachingAssessment
)

from multi_agent_tutor.app.schemas.socratic import (
    SocraticResponse
)


class DiagnosticState(TypedDict):

    completed: bool

    questions: List[DiagnosticQuestion]

    current_question_id: Optional[str]

    answers: Dict[str, str]

    assessments: Dict[
        str,
        AssessmentResult
    ]


class TutorState(TypedDict):

    # -----------------------------
    # Student / session information
    # -----------------------------

    student_id: str

    target_topic: str

    messages: List[Dict[str, str]]

    student_input: Optional[str]


    # -----------------------------
    # Diagnostic system
    # -----------------------------

    diagnostic_state: DiagnosticState


    # -----------------------------
    # Learner model
    # -----------------------------

    learner_profile: Optional[
        LearnerProfile
    ]

    mastery: Dict[str, float]

    bkt_states: Dict[
        str,
        BKTState
    ]


    # -----------------------------
    # Curriculum
    # -----------------------------

    curriculum: Optional[
        List[CurriculumConcept]
    ]

    learning_path: Optional[
        LearningPath
    ]

    current_concept: Optional[str]


    # -----------------------------
    # Teaching system
    # -----------------------------

    teaching: TeachingState

    teaching_assessment: Optional[
        TeachingAssessment
    ]

    teaching_decision: Optional[
        TeachingDecision
    ]

    socratic_response: Optional[
        SocraticResponse
    ]

    rag_context: Optional[
        Dict[str, Any]
    ]


    # -----------------------------
    # Output
    # -----------------------------

    tutor_response: Optional[str]


    # -----------------------------
    # Critic
    # -----------------------------

    critic_result: Optional[
        CriticOutput
    ]

    retry_count: int


    # -----------------------------
    # Miscellaneous
    # -----------------------------

    misconceptions: List[str]

    hint_level: int

    depth_level: Optional[str]


    # -----------------------------
    # Onboarding & Pedagogical Mode
    # -----------------------------

    assessment_done: bool

    self_reported_level: Optional[str]

    teaching_mode: Optional[str]  # "mode_1_qa" or "mode_2_teach_first"

    teaching_step: Optional[str]  # "teach", "check", "re_teach"

    pending_question: Optional[Dict[str, Any]]

    awaiting: Optional[str]  # "answer", "clarity_check", "continue", "none"

    teaching_step_index: Optional[int]  # 0: concept+analogy, 1: ex1, 2: ex2, 3: figure, 4: checks

    last_tutor_message: Optional[str]  # For loop guard

    debug_trace: Optional[List[Dict[str, Any]]]

    current_subtopic: Optional[str]

    subtopic_mastery: Dict[str, Dict[str, float]]


    # -----------------------------
    # Intent Detection & Doubt Flow
    # -----------------------------

    detected_intent: Optional[Dict[str, Any]]

    doubt_state: Dict[str, Any]

    misconceptions_log: List[Dict[str, Any]]

    signals: Dict[str, Any]

    last_practice_time: Optional[str]

    study_plan: Optional[Dict[str, Any]]

    skipped_concepts: List[str]

    # FIX A, B, G, H: Topic isolation, Question queue, Review queue, and Transitions audit
    curriculum_id: Optional[str]

    asked_question_ids: List[str]

    asked_question_texts: List[str]

    question_attempts: Dict[str, int]

    question_results: Dict[str, str]

    concept_question_queue: Dict[str, List[Dict[str, Any]]]

    hint_level_per_question: Dict[str, int]

    review_queue: List[Dict[str, Any]]

    concept_transitions: List[Dict[str, Any]]