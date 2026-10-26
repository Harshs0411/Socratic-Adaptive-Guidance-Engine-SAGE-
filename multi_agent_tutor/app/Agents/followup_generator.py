#it creates a follow up question based on the original question and the student's answer

from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from multi_agent_tutor.app.schemas.diagnostic import (
    DiagnosticQuestion
)
load_dotenv()

model = ChatOpenAI(
    model="gpt-5-mini",
    temperature=0.3
)

follow_up_llm = model.with_structured_output(
    DiagnosticQuestion
)
follow_up_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """
You generate a diagnostic follow-up question.

The student has demonstrated weak or incomplete
understanding of a concept.

Your goal is NOT to teach the student.

Generate ONE diagnostic follow-up question that:

1. Targets the specific misconception.
2. Is simpler or more focused than the original question.
3. Tests the prerequisite needed to understand
   the original concept.
4. Does not reveal the answer.
5. Does not contain hints.
6. Has a new unique question ID.
7. Sets is_follow_up to true.
8. Sets parent_question_id to the original question ID.

Return only the structured question.
"""
        ),
        (
            "human",
            """
Original concept:

{concept}

Original question:

{question}

Evaluation criteria:

{criteria}

Student answer:

{student_answer}

Detected misconceptions:

{misconceptions}

Create a focused follow-up diagnostic question.
"""
        )
    ]
)
follow_up_chain = (
    follow_up_prompt
    | follow_up_llm
)
def generate_follow_up_question(
    question_id: str,
    concept: str,
    question: str,
    criteria: list[str],
    student_answer: str,
    misconceptions: list[str]
) -> DiagnosticQuestion:

    result = follow_up_chain.invoke(
        {
            "question_id": question_id,
            "concept": concept,
            "question": question,
            "criteria": criteria,
            "student_answer": student_answer,
            "misconceptions": misconceptions
        }
    )
    result.question_id = (
        f"{question_id}_followup"
    )
 
    result.is_follow_up = True

    result.parent_question_id = (
        question_id
    )
    return result