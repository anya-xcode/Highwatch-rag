# 🔍 Highwatch RAG — Personal ChatGPT over Google Drive

A production-ready **Retrieval-Augmented Generation (RAG)** system that connects to Google Drive, fetches documents (PDF/Docs/TXT), processes and chunks them, generates embeddings, stores knowledge in a vector database, and answers user questions grounded in your documents.

![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi)
![FAISS](https://img.shields.io/badge/FAISS-Vector_Search-orange)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker)

---

## 📐 Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        Highwatch RAG System                      │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐  │
│   │  Google Drive │───▶│   Connector  │───▶│  Document Store   │  │
│   │   (OAuth2)   │    │  (gdrive.py) │    │  (local files)   │  │
│   └──────────────┘    └──────────────┘    └────────┬─────────┘  │
│                                                     │            │
│                              ┌──────────────────────▼──────┐    │
│                              │     Document Processing      │    │
│                              │  ┌────────┐  ┌───────────┐  │    │
│                              │  │ Parser │  │  Chunker  │  │    │
│                              │  │PDF/DOCX│  │ Semantic  │  │    │
│                              │  │  /TXT  │  │ Overlap   │  │    │
│                              │  └────────┘  └───────────┘  │    │
│                              └──────────────┬──────────────┘    │
│                                             │                    │
│                              ┌──────────────▼──────────────┐    │
│                              │     Embedding Layer          │    │
│                              │   SentenceTransformers       │    │
│                              │   (all-MiniLM-L6-v2)        │    │
│                              │   + Batch Processing         │    │
│                              │   + LRU Caching              │    │
│                              └──────────────┬──────────────┘    │
│                                             │                    │
│   ┌──────────────┐           ┌──────────────▼──────────────┐    │
│   │   User Query │──────────▶│      FAISS Vector Store      │    │
│   └──────┬───────┘           │   Cosine Similarity Search   │    │
│          │                   │   + Metadata Filtering       │    │
│          │                   └──────────────┬──────────────┘    │
│          │                                  │                    │
│          │    ┌──────────────────────────────▼──────────────┐    │
│          └───▶│          LLM Answer Layer                   │    │
│               │   OpenAI GPT-4o / Google Gemini             │    │
│               │   Context-Grounded Answers                  │    │
│               │   + Source Citations                        │    │
│               └────────────────────────────────────────────┘    │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Features

### Core
- ✅ **Google Drive Integration** — OAuth2 authentication, fetch PDFs/Docs/TXT
- ✅ **Document Processing** — PDF parsing (pdfplumber + PyPDF2), DOCX, TXT with text normalization
- ✅ **Smart Chunking** — Semantic-aware splitting (sections → paragraphs → sentences) with overlap
- ✅ **Embedding Generation** — SentenceTransformers with batch processing and LRU caching
- ✅ **Vector Search** — FAISS index with cosine similarity and metadata filtering
- ✅ **AI Answers** — OpenAI GPT-4o or Google Gemini with source citations
- ✅ **Direct Upload** — Upload documents via API without Google Drive

### Advanced
- 🔄 **Incremental Sync** — MD5-based change detection, only re-process modified files
- ⚡ **Caching** — Embedding cache (LRU), sync state persistence
- 🔍 **Metadata Filtering** — Filter search results by source file
- 🔄 **Async Pipeline** — Non-blocking API with `asyncio.to_thread` for CPU-bound tasks
- 🐳 **Docker Ready** — Dockerfile + docker-compose with health checks
- 📊 **Structured Logging** — Production-grade logging with `structlog`

---

## 📁 Project Structure

```
highwatch-rag/
├── connectors/              # External data source connectors
│   ├── __init__.py
│   └── gdrive.py            # Google Drive OAuth + file fetching
├── processing/              # Document parsing and chunking
│   ├── __init__.py
│   ├── parser.py            # PDF, DOCX, TXT text extraction
│   └── chunker.py           # Semantic-aware text chunking
├── embedding/               # Vector embedding generation
│   ├── __init__.py
│   └── embedder.py          # SentenceTransformers + caching
├── search/                  # Vector storage and retrieval
│   ├── __init__.py
│   └── vector_store.py      # FAISS index with metadata
├── api/                     # FastAPI endpoints
│   ├── __init__.py
│   ├── models.py            # Pydantic request/response models
│   ├── routes.py            # API route handlers
│   └── llm_service.py       # LLM integration (OpenAI/Gemini)
├── config/                  # Configuration management
│   ├── __init__.py
│   └── settings.py          # Pydantic Settings
├── main.py                  # Application entry point
├── requirements.txt         # Python dependencies
├── Dockerfile               # Container configuration
├── docker-compose.yml       # Docker Compose setup
├── .env.example             # Environment template
├── .gitignore
└── README.md
```

---

## 🛠️ Setup

### Prerequisites
- Python 3.11+
- Google Cloud project with Drive API enabled
- OpenAI API key OR Google Gemini API key

### 1. Clone & Install

```bash
git clone https://github.com/your-username/highwatch-rag.git
cd highwatch-rag

# Create virtual environment
python -m venv venv
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt
```

### 2. Google Drive Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project (or select existing)
3. Enable **Google Drive API**
4. Go to **APIs & Services → Credentials**
5. Create **OAuth 2.0 Client ID** (Desktop Application)
6. Download the JSON file as `credentials.json` in the project root

### 3. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your settings:

```env
# Choose your LLM provider
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-key-here

# Or use Gemini
# LLM_PROVIDER=gemini
# GEMINI_API_KEY=your-gemini-key

# Optional: specific Google Drive folders
# GOOGLE_DRIVE_FOLDER_IDS=folder_id_1,folder_id_2
```

### 4. Run the Server

```bash
# Development mode with auto-reload
python main.py

# Or directly with uvicorn
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at `http://localhost:8000`  
Interactive docs at `http://localhost:8000/docs`

### 5. Docker (Optional)

```bash
docker-compose up --build
```

---

## 📡 API Reference

### `POST /sync-drive` — Sync Google Drive

Connects to Google Drive, fetches documents, and indexes them.

```bash
curl -X POST http://localhost:8000/sync-drive \
  -H "Content-Type: application/json" \
  -d '{}'
```

With specific folders:
```bash
curl -X POST http://localhost:8000/sync-drive \
  -H "Content-Type: application/json" \
  -d '{"folder_ids": ["1abc123", "2def456"]}'
```

**Response:**
```json
{
  "status": "success",
  "message": "Sync completed. Processed 5 files, created 47 chunks.",
  "new_files": [
    {"id": "abc123", "name": "company_policy.pdf", "path": "...", "mime_type": "application/pdf"}
  ],
  "updated_files": [],
  "unchanged_files": [],
  "errors": [],
  "total_chunks_created": 47,
  "timestamp": "2024-01-15T10:30:00"
}
```

### `POST /ask` — Ask a Question

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"query": "What is our refund policy?"}'
```

With options:
```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are the compliance requirements?",
    "top_k": 5,
    "filter_source": "compliance_handbook.pdf"
  }'
```

**Response:**
```json
{
  "answer": "According to the company policy document, the refund policy states that customers can request a full refund within 30 days of purchase...",
  "sources": ["company_policy.pdf", "refund_guidelines.docx"],
  "source_details": [
    {
      "file_name": "company_policy.pdf",
      "chunk_text": "Section 4.2 - Refund Policy: All customers are entitled to...",
      "score": 0.89,
      "doc_id": "abc123",
      "chunk_index": 12
    }
  ],
  "query": "What is our refund policy?",
  "chunks_retrieved": 5
}
```

### `POST /upload` — Upload a Document

```bash
curl -X POST http://localhost:8000/upload \
  -F "file=@/path/to/document.pdf"
```

**Response:**
```json
{
  "status": "success",
  "message": "Document processed successfully. Created 15 chunks.",
  "doc_id": "uuid-here",
  "file_name": "document.pdf",
  "chunks_created": 15
}
```

### `GET /documents` — List Indexed Documents

```bash
curl http://localhost:8000/documents
```

### `DELETE /documents/{doc_id}` — Delete a Document

```bash
curl -X DELETE http://localhost:8000/documents/abc123
```

### `GET /health` — Health Check

```bash
curl http://localhost:8000/health
```

---

## 🧪 Sample Test Cases

### Test Case 1: Company Policy Q&A

1. Upload a company policy PDF
2. Ask: *"What is our refund policy?"*
3. Expected: Answer extracted from the policy document with source citation

### Test Case 2: Multi-Document Query

1. Sync multiple SOP documents from Google Drive
2. Ask: *"What are the steps for employee onboarding?"*
3. Expected: Synthesized answer from relevant SOPs with all sources listed

### Test Case 3: Compliance Check

1. Upload compliance handbook
2. Ask: *"What are our data retention requirements?"*
3. Expected: Specific retention periods and policies from the handbook

### Test Case 4: Filtered Search

```bash
curl -X POST http://localhost:8000/ask \
  -d '{"query": "What is the vacation policy?", "filter_source": "hr_handbook.pdf"}'
```

---

## ⚙️ Configuration Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `openai` | LLM provider: `openai` or `gemini` |
| `OPENAI_API_KEY` | — | OpenAI API key |
| `OPENAI_MODEL` | `gpt-4o-mini` | OpenAI model name |
| `GEMINI_API_KEY` | — | Google Gemini API key |
| `GEMINI_MODEL` | `gemini-1.5-flash` | Gemini model name |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | SentenceTransformer model |
| `EMBEDDING_BATCH_SIZE` | `64` | Batch size for embedding |
| `CHUNK_SIZE` | `512` | Max characters per chunk |
| `CHUNK_OVERLAP` | `64` | Overlap between chunks |
| `TOP_K_RESULTS` | `5` | Default search results |
| `SIMILARITY_THRESHOLD` | `0.3` | Min similarity score |

---

## 🧠 Design Decisions

### Chunking Strategy
Uses a 3-tier semantic chunking approach:
1. **Section-level**: Split by headings and major boundaries
2. **Paragraph-level**: Split large sections by paragraphs
3. **Sentence-level**: Split oversized paragraphs by sentences
4. **Overlap**: 64-char overlap between chunks for context continuity

### Why FAISS over OpenSearch?
- Zero infrastructure overhead (in-process)
- Fast cosine similarity on normalized vectors
- Persistent to disk with simple save/load
- Suitable for up to millions of vectors

### Incremental Sync
- Tracks `modifiedTime` from Google Drive API
- Computes MD5 hashes of downloaded files
- Only re-processes files that have actually changed
- Prevents redundant embedding computation

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

Built with ❤️ for **Highwatch AI**
