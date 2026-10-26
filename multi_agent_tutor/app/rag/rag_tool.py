from typing import Dict, Any, List
from multi_agent_tutor.app.rag.vector_store import search_knowledge


def retrieve_pedagogical_context(
    topic: str,
    concept: str,
    current_action: str = "probe",
    k: int = 2,
) -> Dict[str, Any]:
    """
    Retrieve authoritative textbook knowledge chunks for SAGE and the Assessor.
    Formulates a targeted semantic search query based on the active concept and pedagogical action.
    """
    # Build query tailored to the pedagogical goal
    if current_action == "initial":
        query = f"Introduction, core definition, intuition, and real world analogy for {concept} in {topic}"
    elif current_action in {"hint", "scaffold"}:
        query = f"Step by step mechanics, breakdown, formula, and common misconceptions for {concept}"
    elif current_action == "explain":
        query = f"Formal explanation, mathematical derivation, and full definition of {concept}"
    else: # probe / advance
        query = f"Mathematical verification, edge cases, and reasoning criteria for {concept}"

    try:
        chunks = search_knowledge(
            query=query,
            topic=topic,
            k=k,
        )
    except Exception as exc:
        chunks = []

    if not chunks:
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

    return {
        "context_text": "\n\n".join(formatted_context_parts),
        "citations": citations,
        "chunks": chunks,
    }
