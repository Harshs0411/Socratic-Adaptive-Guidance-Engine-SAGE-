import os
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

# Persistence directory for Chroma
RAG_DATA_DIR = os.getenv("CHROMA_PERSIST_DIRECTORY") or os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "data", "chroma_db")
)
os.makedirs(RAG_DATA_DIR, exist_ok=True)

_embeddings = None
_vector_store = None


def get_embeddings() -> OpenAIEmbeddings:
    """Singleton getter for OpenAI embeddings."""
    global _embeddings
    if _embeddings is None:
        _embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small",
        )
    return _embeddings


def get_vector_store() -> Chroma:
    """Singleton getter for Chroma vector store."""
    global _vector_store
    if _vector_store is None:
        _vector_store = Chroma(
            collection_name="sage_pedagogical_knowledge",
            embedding_function=get_embeddings(),
            persist_directory=RAG_DATA_DIR,
        )
    return _vector_store


# ----------------------------------------------------------------------
# Dynamic Knowledge Synthesis Schema
# ----------------------------------------------------------------------

class KnowledgeChunk(BaseModel):
    concept: str = Field(description="The specific sub-concept or skill name")
    content: str = Field(description="Authoritative, detailed technical explanation, formulas, intuition, and edge cases")
    source: str = Field(description="Authoritative academic source citation (e.g., textbook name, author, chapter, or standard reference)")
    common_misconceptions: List[str] = Field(default_factory=list, description="Frequent student mistakes or misunderstandings")


class TopicKnowledgePackage(BaseModel):
    topic: str
    chunks: List[KnowledgeChunk] = Field(min_length=3, max_length=8)


_SYNTHESIZER_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """You are the Lead Academic Knowledge Engineer for SAGE, an AI tutoring system.
Your job is to generate authoritative, textbook-grade reference material for a target topic to be ingested into a Chroma vector database.

For the requested topic:
Generate 4 to 6 comprehensive, dense reference chunks covering:
1. Core Definitions & Formal Invariants
2. Mathematical Formulas & Mechanics
3. Real-world Intuition & Conceptual Analogies
4. Edge Cases, Constraints, & Asymptotics
5. Frequent Student Misconceptions & Clarifications

Each chunk must cite a realistic, authoritative academic source (e.g. 'Deep Learning by Goodfellow et al., Ch. 9', 'Introduction to Algorithms (CLRS), Ch. 2', 'Speech & Language Processing by Jurafsky & Martin', or standard domain textbooks).
"""
        ),
        ("human", "Generate the authoritative pedagogical knowledge package for: {topic}")
    ]
)


# ----------------------------------------------------------------------
# Uploaded Document Registry & Deduplication Cache
# ----------------------------------------------------------------------

_UPLOADED_DOCUMENTS: Dict[str, set] = {}
_RAG_SEARCH_CACHE: Dict[tuple, List[Dict[str, Any]]] = {}


def register_uploaded_document(topic: str, source_name: str) -> None:
    """Registers an uploaded document under the specified topic and clears search cache."""
    t = (topic or "general").lower().strip()
    if t not in _UPLOADED_DOCUMENTS:
        _UPLOADED_DOCUMENTS[t] = set()
    _UPLOADED_DOCUMENTS[t].add(source_name)
    _RAG_SEARCH_CACHE.clear()


def get_uploaded_documents(topic: Optional[str] = None, state: Optional[Dict[str, Any]] = None) -> List[str]:
    """Returns the set of uploaded documents for the topic or session."""
    docs = set()
    if state:
        for d in (state.get("uploaded_documents") or []):
            docs.add(d)
    if topic:
        docs.update(_UPLOADED_DOCUMENTS.get(topic.lower().strip(), set()))
    else:
        for s in _UPLOADED_DOCUMENTS.values():
            docs.update(s)
    return list(docs)


def has_uploaded_documents(topic: Optional[str] = None, state: Optional[Dict[str, Any]] = None) -> bool:
    """
    Lightweight, deterministic check whether any document/PDF has been uploaded
    for the current topic or session. Never touches ChromaDB or embedding models.
    """
    if state and (state.get("has_uploaded_docs") or state.get("uploaded_documents")):
        return True
    return len(get_uploaded_documents(topic, state)) > 0


def has_indexed_documents(topic: Optional[str] = None) -> bool:
    """
    Check if the vector store contains any uploaded or indexed documents
    without calling any LLM synthesizer or embedding model.
    """
    if has_uploaded_documents(topic):
        return True
    try:
        store = get_vector_store()
        if topic:
            existing = store.get(where={"topic": topic.lower()}, limit=1)
            return bool(existing and existing.get("ids"))
        else:
            return store._collection.count() > 0
    except Exception:
        return False


def index_topic_knowledge(topic: str, force_refresh: bool = False) -> int:
    """
    Ensure the vector store has indexed reference material for the given topic.
    If the topic is already indexed, skips re-indexing unless force_refresh is True.
    Returns the number of documents added or already present.
    """
    store = get_vector_store()

    # Check if documents already exist for this topic
    if not force_refresh:
        try:
            existing = store.get(where={"topic": topic.lower()})
            if existing and existing.get("ids"):
                return len(existing["ids"])
        except Exception:
            pass

    # Synthesize authoritative knowledge package
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.2)
    synthesizer = llm.with_structured_output(TopicKnowledgePackage, method="function_calling")
    chain = _SYNTHESIZER_PROMPT | synthesizer
    package: TopicKnowledgePackage = chain.invoke({"topic": topic})

    docs = []
    for chunk in package.chunks:
        misc_str = ""
        if chunk.common_misconceptions:
            misc_str = "\n\nCommon Misconceptions:\n- " + "\n- ".join(chunk.common_misconceptions)

        text = (
            f"Topic: {package.topic}\n"
            f"Concept: {chunk.concept}\n\n"
            f"Content:\n{chunk.content}"
            f"{misc_str}"
        )
        metadata = {
            "topic": package.topic.lower(),
            "concept": chunk.concept.lower(),
            "source": chunk.source,
        }
        docs.append(Document(page_content=text, metadata=metadata))

    if docs:
        store.add_documents(docs)

    return len(docs)


def search_knowledge(
    query: str,
    topic: Optional[str] = None,
    k: int = 3,
) -> List[Dict[str, Any]]:
    """
    Perform dense semantic similarity search against the ChromaDB knowledge base.
    Only queries the database if documents exist for this topic (or globally).
    Never automatically synthesizes synthetic LLM chunks on empty searches.
    """
    # If no documents are uploaded or indexed for this topic, skip RAG search entirely
    if not has_indexed_documents(topic):
        return []

    cache_key = (query.strip().lower(), (topic or "general").strip().lower(), k)
    if cache_key in _RAG_SEARCH_CACHE:
        return _RAG_SEARCH_CACHE[cache_key]

    store = get_vector_store()

    filter_dict = {"topic": topic.lower()} if topic else None

    try:
        results = store.similarity_search_with_score(
            query=query,
            k=k,
            filter=filter_dict,
        )
    except Exception:
        results = store.similarity_search_with_score(
            query=query,
            k=k,
        )

    formatted_results = []
    for doc, dist in results:
        # Normalize distance to 0-1 similarity score
        similarity = max(0.0, min(1.0, 1.0 / (1.0 + float(dist))))
        formatted_results.append({
            "content": doc.page_content,
            "source": doc.metadata.get("source", "Authoritative Literature"),
            "concept": doc.metadata.get("concept", "Foundational Concept"),
            "topic": doc.metadata.get("topic", topic or "General"),
            "score": round(similarity, 3),
            "similarity_score": round(similarity, 3),
        })

    _RAG_SEARCH_CACHE[cache_key] = formatted_results
    return formatted_results
