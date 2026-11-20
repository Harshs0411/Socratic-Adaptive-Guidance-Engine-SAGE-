import unittest
from multi_agent_tutor.app.rag.rag_tool import (
    retrieve_pedagogical_context,
    should_invoke_rag,
    get_rag_metrics,
    reset_rag_metrics,
)
from multi_agent_tutor.app.rag.vector_store import (
    register_uploaded_document,
    has_uploaded_documents,
    _UPLOADED_DOCUMENTS,
    _RAG_SEARCH_CACHE,
)
from multi_agent_tutor.app.Agents.tutor import sage_agent
from multi_agent_tutor.app.Agents.doubt_agent import doubt_agent_node
from multi_agent_tutor.app.schemas.socratic import SocraticResponse


class TestRAGOptimization(unittest.TestCase):

    def setUp(self):
        reset_rag_metrics()
        _UPLOADED_DOCUMENTS.clear()
        _RAG_SEARCH_CACHE.clear()

    def test_1_normal_conversation_without_pdf_zero_rag_calls(self):
        """
        Verify: Normal conversation messages (e.g. 'Hi', 'Continue', 'Got it')
        without a PDF result in zero RAG calls and skip vector searches entirely.
        """
        state = {
            "current_concept": "binary_search",
            "target_topic": "Binary Search",
            "student_input": "Hi SAGE, I am ready to start learning!",
            "mastery": {"binary_search": 0.1},
            "teaching_mode": "mode_2_teach_first",
            "teaching_step": "teach",
            "teaching_step_index": 0,
            "teaching": {
                "current_action": "explain",
                "current_question": None,
                "attempt_count": 0,
            },
            "retry_count": 0,
        }

        # Check lightweight router directly
        self.assertFalse(
            should_invoke_rag(topic="Binary Search", student_input=state["student_input"], state=state),
            "should_invoke_rag must be False when no PDF is uploaded"
        )

        # Execute retrieval call
        result = retrieve_pedagogical_context(
            topic="Binary Search",
            concept="binary_search",
            current_action="explain",
            student_input=state["student_input"],
            state=state,
        )

        metrics = get_rag_metrics()
        self.assertEqual(metrics["rag_invoked"], 0, "RAG should NOT be invoked without PDF")
        self.assertEqual(metrics["rag_skipped"], 1, "RAG should be marked as skipped")
        self.assertEqual(result["context_text"], "")
        self.assertEqual(result["citations"], [])

    def test_2_general_teaching_without_pdf_zero_rag_calls(self):
        """
        Verify: General teaching prompts (explanations, probe questions, worked examples)
        without an uploaded PDF do NOT invoke RAG.
        """
        state = {
            "current_concept": "base_case",
            "target_topic": "Recursion",
            "student_input": "Base case stops the recursive calls.",
            "mastery": {"base_case": 0.5},
            "teaching_mode": "mode_1_qa",
            "teaching_step": "check",
            "teaching": {
                "current_action": "probe",
                "current_question": "What is the role of the base case?",
                "attempt_count": 1,
            },
            "retry_count": 0,
        }

        # Verify router
        self.assertFalse(
            should_invoke_rag(topic="Recursion", student_input=state["student_input"], state=state),
            "should_invoke_rag must be False for general teaching without PDF"
        )

        result = retrieve_pedagogical_context(
            topic="Recursion",
            concept="base_case",
            current_action="probe",
            student_input=state["student_input"],
            state=state,
        )

        metrics = get_rag_metrics()
        self.assertEqual(metrics["rag_invoked"], 0, "General teaching should make 0 RAG calls")
        self.assertEqual(metrics["rag_skipped"], 1)

    def test_3_question_about_uploaded_pdf_rag_is_invoked(self):
        """
        Verify: When a PDF is provided and the student specifically asks about the PDF content,
        RAG is invoked and retrieves document chunks.
        """
        topic = "operating_systems"
        filename = "os_three_easy_pieces_ch5.pdf"

        # Simulate uploading a document
        register_uploaded_document(topic=topic, source_name=filename)
        self.assertTrue(has_uploaded_documents(topic=topic))

        state = {
            "current_concept": "process_creation",
            "target_topic": topic,
            "uploaded_documents": [filename],
            "has_uploaded_docs": True,
        }

        student_queries = [
            "What does the uploaded PDF say about fork() and exec()?",
            "According to the notes in the document, how does process isolation work?",
            "In the textbook pdf, what is the return value of fork in the child process?",
            "What is mentioned in os_three_easy_pieces_ch5 about zombie processes?",
        ]

        for q in student_queries:
            reset_rag_metrics()
            needs_rag = should_invoke_rag(topic=topic, student_input=q, state=state)
            self.assertTrue(
                needs_rag,
                f"Expected RAG to be invoked for query: '{q}'"
            )

            # Invocation should route to search
            result = retrieve_pedagogical_context(
                topic=topic,
                concept="process_creation",
                current_action="probe",
                student_input=q,
                state=state,
            )

            metrics = get_rag_metrics()
            self.assertEqual(metrics["rag_invoked"], 1, f"RAG should be invoked for: {q}")
            self.assertEqual(metrics["rag_skipped"], 0)

    def test_4_unrelated_question_with_pdf_uploaded_rag_is_skipped(self):
        """
        Verify: Even when a PDF is uploaded, if the student asks an unrelated general question,
        RAG is skipped and SAGE relies on general knowledge.
        """
        topic = "data_structures"
        filename = "advanced_b_trees.pdf"

        # Register uploaded PDF
        register_uploaded_document(topic=topic, source_name=filename)
        self.assertTrue(has_uploaded_documents(topic=topic))

        state = {
            "current_concept": "arrays",
            "target_topic": topic,
            "uploaded_documents": [filename],
            "has_uploaded_docs": True,
        }

        unrelated_student_queries = [
            "What is 2 + 2?",
            "Can you explain what a basic while loop does in Python?",
            "Why is index 0 used as the first element of an array?",
            "I answered 42.",
            "Let's move on to the next practice problem.",
            "Can you give me an analogy for arrays?",
        ]

        for q in unrelated_student_queries:
            reset_rag_metrics()
            needs_rag = should_invoke_rag(topic=topic, student_input=q, state=state)
            self.assertFalse(
                needs_rag,
                f"Expected RAG to be SKIPPED for unrelated question: '{q}'"
            )

            result = retrieve_pedagogical_context(
                topic=topic,
                concept="arrays",
                current_action="probe",
                student_input=q,
                state=state,
            )

            metrics = get_rag_metrics()
            self.assertEqual(metrics["rag_invoked"], 0, f"RAG must NOT be invoked for unrelated query: {q}")
            self.assertEqual(metrics["rag_skipped"], 1)
            self.assertEqual(result["context_text"], "")

    def test_5_repeated_queries_use_cache(self):
        """
        Verify: Consecutive queries for the same content utilize the deduplication cache
        to prevent repeated retrieval calls.
        """
        from multi_agent_tutor.app.rag.vector_store import search_knowledge

        topic = "algorithms"
        filename = "clrs_ch1.pdf"
        register_uploaded_document(topic=topic, source_name=filename)

        query = "What does the pdf say about insertion sort invariants?"
        state = {"target_topic": topic, "uploaded_documents": [filename]}

        # First call: populates cache
        res1 = retrieve_pedagogical_context(
            topic=topic,
            concept="sorting",
            student_input=query,
            state=state,
        )

        # Check cache entry
        cache_key = (query.strip().lower(), topic.lower(), 2)
        self.assertIn(cache_key, _RAG_SEARCH_CACHE, "Search results should be cached")

        # Second call: uses cache
        res2 = retrieve_pedagogical_context(
            topic=topic,
            concept="sorting",
            student_input=query,
            state=state,
        )

        self.assertEqual(res1["chunks"], res2["chunks"])


if __name__ == "__main__":
    unittest.main()
