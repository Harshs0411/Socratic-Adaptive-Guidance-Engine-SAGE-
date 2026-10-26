import os
import sys
import argparse
from io import BytesIO
from typing import List, Optional, Union
from pypdf import PdfReader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

from multi_agent_tutor.app.rag.vector_store import get_vector_store


DOCUMENTS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "data", "documents")
)
os.makedirs(DOCUMENTS_DIR, exist_ok=True)


def extract_text_from_file(file_path: str) -> str:
    """Extract text content from a .pdf, .txt, or .md file."""
    ext = os.path.splitext(file_path)[1].lower()

    if ext in {".txt", ".md", ".markdown"}:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()

    elif ext == ".pdf":
        reader = PdfReader(file_path)
        pages_text = []
        for idx, page in enumerate(reader.pages):
            txt = page.extract_text()
            if txt:
                pages_text.append(txt)
        return "\n\n".join(pages_text)

    else:
        raise ValueError(f"Unsupported file format: '{ext}'. Supported formats: .pdf, .txt, .md")


def extract_text_from_bytes(file_bytes: bytes, filename: str) -> str:
    """Extract text content from in-memory file bytes (e.g. FastAPI / React upload)."""
    ext = os.path.splitext(filename)[1].lower()

    if ext in {".txt", ".md", ".markdown"}:
        return file_bytes.decode("utf-8", errors="ignore")

    elif ext == ".pdf":
        stream = BytesIO(file_bytes)
        reader = PdfReader(stream)
        pages_text = []
        for page in reader.pages:
            txt = page.extract_text()
            if txt:
                pages_text.append(txt)
        return "\n\n".join(pages_text)

    else:
        raise ValueError(f"Unsupported file format: '{ext}'. Supported formats: .pdf, .txt, .md")


def ingest_text_content(
    text: str,
    topic: str,
    source_name: str,
    chunk_size: int = 800,
    chunk_overlap: int = 150,
) -> int:
    """
    Split extracted text into chunks and store them into the ChromaDB vector store
    under the specified topic.
    """
    if not text.strip():
        return 0

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_text(text)

    docs = []
    for idx, chunk in enumerate(chunks):
        metadata = {
            "topic": topic.lower(),
            "concept": "general",
            "source": source_name,
            "chunk_id": idx,
        }
        docs.append(Document(page_content=chunk, metadata=metadata))

    if docs:
        store = get_vector_store()
        store.add_documents(docs)

    return len(docs)


def ingest_file(
    file_path: str,
    topic: str,
    source_name: Optional[str] = None,
) -> int:
    """Ingest a single .pdf, .txt, or .md file into ChromaDB."""
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    source = source_name or os.path.basename(file_path)
    text = extract_text_from_file(file_path)
    return ingest_text_content(text, topic, source)


def ingest_directory(
    dir_path: str,
    topic: str,
) -> int:
    """Ingest all supported documents from a directory into ChromaDB."""
    if not os.path.isdir(dir_path):
        raise NotADirectoryError(f"Directory not found: {dir_path}")

    total_chunks = 0
    supported_exts = {".pdf", ".txt", ".md", ".markdown"}

    for root, _, files in os.walk(dir_path):
        for f in sorted(files):
            ext = os.path.splitext(f)[1].lower()
            if ext in supported_exts:
                full_path = os.path.join(root, f)
                try:
                    chunks = ingest_file(full_path, topic)
                    total_chunks += chunks
                    print(f"✓ Ingested '{f}': {chunks} chunks added to topic '{topic}'")
                except Exception as e:
                    print(f"✗ Failed to ingest '{f}': {e}")

    return total_chunks


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest custom documents (PDF, TXT, MD) into SAGE ChromaDB.")
    parser.add_argument("--file", type=str, help="Path to a single file (.pdf, .txt, .md)")
    parser.add_argument("--dir", type=str, default=DOCUMENTS_DIR, help="Path to a directory containing documents")
    parser.add_argument("--topic", type=str, required=True, help="Topic name to associate documents with (e.g. 'Convolutional Neural Networks')")

    args = parser.parse_args()

    if args.file:
        count = ingest_file(args.file, args.topic)
        print(f"Successfully ingested {count} chunks into topic '{args.topic}' from {args.file}")
    else:
        count = ingest_directory(args.dir, args.topic)
        print(f"Successfully ingested {count} total chunks into topic '{args.topic}' from directory {args.dir}")
