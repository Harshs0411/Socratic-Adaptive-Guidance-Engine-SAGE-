#11 point in prompt is added by me

from dotenv import load_dotenv, find_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from multi_agent_tutor.app.graph.state import TutorState
from multi_agent_tutor.app.schemas.diagnostic import (
    DiagnosticQuestionSet
)

load_dotenv(find_dotenv())

model = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.3
)

diagnostic_llm = model.with_structured_output(
    DiagnosticQuestionSet,
    method="function_calling"
)
prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """
You are the Diagnostic Agent of SAGE, an adaptive
Socratic AI tutoring system.

Your role is to create an INITIAL diagnostic plan
for a student before tutoring begins.

The purpose is NOT to teach the topic.

Your purpose is to estimate:

- prerequisite knowledge
- conceptual understanding
- misconceptions
- readiness to begin the target topic

Create between 1 and 6 diagnostic questions tailored to the curriculum concepts.

Curriculum Concepts to Diagnose:
Assign the `concept` field of each question to one of these exact concept IDs:
{concepts_description}

Question design rules:

1. Begin with foundational prerequisite concepts.
2. Progress from basic understanding toward deeper reasoning.
3. Test understanding rather than memorization.
4. Prefer open-ended questions when conceptual reasoning
   is important.
5. Use objective questions only when objective evaluation
   provides useful evidence.
6. Each question should primarily test one concept.
7. Avoid teaching, hints, explanations, or answers.
8. Do not ask unnecessarily advanced questions.
9. Make every question useful for adapting future tutoring.
10. Assign unique question IDs: q1, q2, q3, and so on.

Return questions in a logical learning order.

Target topic:

{topic}
"""
        )
    ]
)

def generate_diagnostic_questions(state: TutorState) -> DiagnosticQuestionSet:
    curriculum = state.get("curriculum") or []
    concepts_description = "\n".join(
        f"- {c.concept_id} ({c.name}): {c.description}"
        for c in curriculum
    )

    chain = prompt | diagnostic_llm

    result = chain.invoke(
        {
            "topic": state.get("target_topic", "Computer Science"),
            "concepts_description": concepts_description,
        }
    )

    return result


def diagnostic_agent(
    state: TutorState
):
    diagnostic = state.get("diagnostic_state") or {}

    if diagnostic.get("questions"):
        return {}

    # If student is beginner, skip diagnostic completely
    if state.get("self_reported_level") == "beginner":
        return {
            "diagnostic_state": {
                "completed": True,
                "questions": [],
                "current_question_id": None,
                "answers": {},
                "assessments": {}
            }
        }

    # Requirement 1.4: Draw 1-2 questions per topic from the curriculum question bank
    topic = state.get("target_topic", "Binary Search")
    from multi_agent_tutor.app.Agents.onboarding_agent import build_bank_diagnostic_questions
    bank_questions = build_bank_diagnostic_questions(topic, level=state.get("self_reported_level"))

    if bank_questions:
        questions = bank_questions
    else:
        result = generate_diagnostic_questions(state)
        questions = result.questions

    if not questions:
        return {
            "diagnostic_state": {
                "completed": True,
                "questions": [],
                "current_question_id": None,
                "answers": {},
                "assessments": {}
            }
        }

    return {
        "diagnostic_state": {
            "completed": False,
            "questions": questions,
            "current_question_id": questions[0].question_id,
            "answers": {},
            "assessments": {}
        }
    }
