# 📚 SAGE Custom Document Repository (RAG Knowledge Base)

Drop your study materials, lecture slides, textbook chapters, or personal notes here to ground SAGE with your own authoritative documents!

## 📂 Supported Formats
- **PDF Documents** (`.pdf`)
- **Text Files** (`.txt`)
- **Markdown Notes** (`.md`)

---

## 🚀 How to Ingest Files into SAGE ChromaDB

### Method 1: Web Interface (Easiest)
1. Open the SAGE Web App (`python run_app.py` or [http://localhost:5173](http://localhost:5173)).
2. In the left sidebar under **⚡ Dynamic RAG Vector Store**, use the **"Upload Notes / Textbook"** drag-and-drop dropzone.
3. Upload your `.pdf`, `.txt`, or `.md` file. SAGE will automatically chunk, embed, and index it into ChromaDB for your active topic!

---

### Method 2: Command Line (CLI)

**Ingest a single file:**
```bash
python -m multi_agent_tutor.app.rag.document_loader --file "multi_agent_tutor/data/documents/my_notes.pdf" --topic "Convolutional Neural Networks"
```

**Ingest all files in this directory:**
```bash
python -m multi_agent_tutor.app.rag.document_loader --dir "multi_agent_tutor/data/documents" --topic "Convolutional Neural Networks"
```

---

## 🔍 How SAGE Uses Your Documents
1. Your files are automatically chunked into 800-character segments with 150-character semantic overlaps using LangChain.
2. High-dimensional vector embeddings are computed via OpenAI `text-embedding-3-small`.
3. Chunks are stored in the persistent ChromaDB collection at `multi_agent_tutor/data/chroma_db/`.
4. When SAGE generates Socratic questions, hints, or scaffolds, it retrieves the most relevant excerpts and cites your document as the authoritative source!
