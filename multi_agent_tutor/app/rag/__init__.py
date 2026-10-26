"""
Pedagogical RAG module for SAGE.
Provides dense vector retrieval using ChromaDB and OpenAI Embeddings.
"""
from multi_agent_tutor.app.rag.vector_store import (
    get_vector_store,
    search_knowledge,
    index_topic_knowledge,
)
from multi_agent_tutor.app.rag.rag_tool import (
    retrieve_pedagogical_context,
)
from multi_agent_tutor.app.rag.document_loader import (
    ingest_file,
    ingest_directory,
    ingest_text_content,
    extract_text_from_bytes,
    DOCUMENTS_DIR,
)

__all__ = [
    "get_vector_store",
    "search_knowledge",
    "index_topic_knowledge",
    "retrieve_pedagogical_context",
    "ingest_file",
    "ingest_directory",
    "ingest_text_content",
    "extract_text_from_bytes",
    "DOCUMENTS_DIR",
]
