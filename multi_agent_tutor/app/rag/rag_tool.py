import os
import re
import time
from typing import Dict, Any, List, Optional
from multi_agent_tutor.app.rag.vector_store import (
    search_knowledge,
    has_uploaded_documents,
    get_uploaded_documents,
)

# ----------------------------------------------------------------------
# Metrics Tracking
# ----------------------------------------------------------------------
_RAG_METRICS = {
    "total_requests": 0,
    "rag_invoked": 0,
    "rag_skipped": 0,
}


def get_rag_metrics() -> Dict[str, int]:
    return dict(_RAG_METRICS)


def reset_rag_metrics() -> None:
    global _RAG_METRICS
    _RAG_METRICS = {
        "total_requests": 0,
        "rag_invoked": 0,
        "rag_skipped": 0,
    }


# ----------------------------------------------------------------------
# Lightweight Conditional Routing for RAG Invocation
# ----------------------------------------------------------------------
RAG_TRIGGER_KEYWORDS = {
    "pdf", "document", "doc", "notes", "uploaded", "paper", "textbook",
    "handout", "file", "reading", "slides", "chapter", "passage",
    "article", "page", "author", "source", "excerpt", "citation",
    "syllabus", "reference", "material", "attachment",
}

RAG_TRIGGER_PHRASES = [
    "in the pdf", "from the pdf", "according to the pdf", "in the document",
    "from the document", "according to the document", "in the notes",
    "from the notes", "according to the notes", "in my notes",
    "in the paper", "from the paper", "uploaded file", "uploaded notes",
    "uploaded document", "uploaded pdf", "in the text", "what does the text say",
    "what does the pdf say", "what does the document say", "what do the notes say",
    "in chapter", "on page", "the author states", "the author mentions",
    "according to the author", "in the reading", "from the reading",
    "as per the document", "as per the pdf", "as per the notes",
]


def should_invoke_rag(
    topic: str,
    student_input: Optional[str] = None,
    state: Optional[Dict[str, Any]] = None,
    query: Optional[str] = None,
) -> bool:
    """
    Lightweight, deterministic conditional routing before retrieval:
    1. If NO document/PDF is uploaded for this topic or session:
       -> Immediately return False (skip RAG completely, 0 vector DB searches, 0 embeddings).
    2. If a document/PDF IS uploaded:
       -> Check if the student's query specifically requires or asks about the uploaded PDF content.
       -> If the query is an unrelated general question or normal teaching step:
          -> Return False (use normal LLM workflow instead).
       -> If the query references the PDF, notes, author, or document content:
          -> Return True (invoke RAG pipeline).
    """
    # 1. Condition: No PDF provided -> Skip RAG
    if not has_uploaded_documents(topic=topic, state=state):
        return False

    # 2. Condition: If PDF provided, evaluate if the student's question requires the PDF
    searchable_text = f"{student_input or ''} {query or ''}".lower().strip()
    if not searchable_text:
        return False

    # Check for direct phrase matches
    for phrase in RAG_TRIGGER_PHRASES:
        if phrase in searchable_text:
            return True

    # Check for document keyword tokens
    tokens = set(re.findall(r"\b[a-z0-9_-]+\b", searchable_text))
    if any(kw in tokens for kw in RAG_TRIGGER_KEYWORDS):
        return True

    # Check if student mentions any uploaded document filename or stem
    uploaded_files = get_uploaded_documents(topic=topic, state=state)
    for doc_name in uploaded_files:
        stem = os.path.splitext(doc_name)[0].lower()
        if stem and len(stem) > 2 and stem in searchable_text:
            return True
        if doc_name.lower() in searchable_text:
            return True

    # Unrelated general question with PDF uploaded -> Skip RAG
    return False


def retrieve_pedagogical_context(
    topic: str,
    concept: str,
    current_action: str = "probe",
    k: int = 2,
    student_input: Optional[str] = None,
    query: Optional[str] = None,
    state: Optional[Dict[str, Any]] = None,
    force_rag: bool = False,
) -> Dict[str, Any]:
    """
    Conditionally retrieve authoritative textbook knowledge chunks for SAGE and the Assessor.
    Only queries ChromaDB when a PDF is provided AND the question requires document knowledge.
    """
    t0 = time.perf_counter()
    _RAG_METRICS["total_requests"] += 1

    # ------------------------------------------------------------------
    # Step 1: Lightweight Conditional Routing Check
    # ------------------------------------------------------------------
    needs_rag = force_rag or should_invoke_rag(
        topic=topic,
        student_input=student_input,
        state=state,
        query=query,
    )

    if not needs_rag:
        _RAG_METRICS["rag_skipped"] += 1
        elapsed = time.perf_counter() - t0
        print(f"[RAG ROUTING] Skipped: No uploaded PDF or question does not require document knowledge (topic='{topic}', time={elapsed:.4f}s)")
        return {
            "context_text": "",
            "citations": [],
            "chunks": [],
        }

    # ------------------------------------------------------------------
    # Step 2: Formulate Targeted Query & Retrieve
    # ------------------------------------------------------------------
    _RAG_METRICS["rag_invoked"] += 1

    # Prefer student's explicit question if asking about PDF, else use action-based concept query
    if student_input and any(kw in student_input.lower() for kw in RAG_TRIGGER_KEYWORDS):
        search_query = student_input
    elif query:
        search_query = query
    elif current_action == "initial":
        search_query = f"Introduction, core definition, intuition, and real world analogy for {concept} in {topic}"
    elif current_action in {"hint", "scaffold"}:
        search_query = f"Step by step mechanics, breakdown, formula, and common misconceptions for {concept}"
    elif current_action == "explain":
        search_query = f"Formal explanation, mathematical derivation, and full definition of {concept}"
    else:
        search_query = f"Mathematical verification, edge cases, and reasoning criteria for {concept}"

    try:
        chunks = search_knowledge(
            query=search_query,
            topic=topic,
            k=k,
        )
    except Exception as exc:
        print(f"[RAG ROUTING] Search exception: {exc}")
        chunks = []

    if not chunks:
        elapsed = time.perf_counter() - t0
        print(f"[TIMING] RAG Retrieval: {elapsed:.4f}s (chunks=0, no matches)")
        return {
            "context_text": "",
            "citations": [],
            "chunks": [],
        }

    formatted_context_parts = []
    citations = []

    for idx, c in enumerate(chunks, 1):
        formatted_context_parts.append(
            f"--- Reference Passage {idx} (Source: {c['source']}) ---\n{c['content']}"
        )
        citations.append({
            "source": c["source"],
            "relevance_score": c.get("similarity_score", 0.85),
            "excerpt": c["content"][:280] + ("..." if len(c["content"]) > 280 else ""),
            "concept": c.get("concept", concept),
        })

    elapsed = time.perf_counter() - t0
    print(f"[TIMING] RAG Retrieval: {elapsed:.4f}s (chunks={len(chunks)}, query='{search_query[:50]}...')")

    return {
        "context_text": "\n\n".join(formatted_context_parts),
        "citations": citations,
        "chunks": chunks,
    }
