# Document Intelligence Refinery

> **Production-grade, multi-stage agentic pipeline for unstructured document extraction at enterprise scale.**

A five-stage pipeline that transforms heterogeneous PDFs (native-digital, scanned, table-heavy, mixed) into structured, queryable, spatially-indexed knowledge — complete with provenance tracking, confidence-gated extraction escalation, and a LangGraph query interface.

---

## Table of Contents

- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Quick Start](#quick-start)
  - [Prerequisites](#prerequisites)
  - [Option A — Python (uv)](#option-a--python-uv)
  - [Option B — Docker](#option-b--docker)
- [Configuration](#configuration)
- [Usage](#usage)
  - [CLI Pipeline](#cli-pipeline)
  - [API Server](#api-server)
  - [Query & Audit](#query--audit)
- [API Reference](#api-reference)
- [Target Corpus](#target-corpus)
- [Artifacts & Outputs](#artifacts--outputs)
- [Testing](#testing)

---

## Architecture

The refinery implements a five-stage agentic pipeline:

```
Raw PDF
  │
  ▼
┌─────────────────────────┐
│  Stage 1: Triage Agent  │  → DocumentProfile (.refinery/profiles/)
│  (classify & cost-gate) │
└──────────┬──────────────┘
           │
  ┌────────▼────────────────────────────────────────┐
  │  Stage 2: Extraction Router                      │
  │   ├── Strategy A: FastText  (pdfplumber)         │
  │   ├── Strategy B: Layout    (Docling)            │  → ExtractedDocument
  │   └── Strategy C: Vision    (Ollama VLM)         │
  │  Confidence-gated escalation guard               │
  └────────┬─────────────────────────────────────────┘
           │                  ↓ logs every attempt
           │          .refinery/extraction_ledger.jsonl
  ┌────────▼───────────────────┐
  │  Stage 3: Chunking Engine  │  → List[LDU]  (semantic, rule-based)
  └────────┬───────────────────┘
  ┌────────▼───────────────────┐
  │  Stage 4: PageIndex Builder│  → PageIndex tree (.refinery/pageindex/)
  └────────┬───────────────────┘
  ┌────────▼──────────────────────────────────┐
  │  Stage 5: Query Interface Agent (LangGraph)│
  │   Tools: pageindex_navigate               │
  │           semantic_search (ChromaDB)      │  → Verified answer +
  │           structured_query  (SQLite)      │    ProvenanceChain
  └───────────────────────────────────────────┘
```

---

## Project Structure

```
document-intelligence-refinery/
├── src/
│   ├── server.py                  # FastAPI server (REST API)
│   ├── agents/
│   │   ├── triage.py              # Stage 1 – Triage Agent & DocumentProfile
│   │   ├── extractor.py           # Stage 2 – ExtractionRouter + escalation guard
│   │   ├── chunker.py             # Stage 3 – ChunkingEngine + ChunkValidator
│   │   ├── indexer.py             # Stage 4 – NavigationAgent / PageIndex builder
│   │   ├── query_agent.py         # Stage 5 – LangGraph RefineryAssistant
│   │   ├── retrieval.py           # RetrievalAgent (vector + SQL)
│   │   ├── fact_extractor.py      # FactTable extractor → SQLite
│   │   └── audit_mode.py          # Claim verification agent
│   ├── models/                    # Pydantic schemas (DocumentProfile, LDU, PageIndex…)
│   ├── strategies/
│   │   ├── fast_text.py           # Strategy A – pdfplumber
│   │   ├── layout_extractor.py    # Strategy B – Docling
│   │   └── vision_extractor.py    # Strategy C – Ollama VLM
│   └── utils/
│       ├── db_utils.py            # SQLite helpers
│       ├── vector_utils.py        # ChromaDB ingestion
│       └── logging_utils.py       # Structured logging
├── frontend/                      # Vite/React demo UI
├── data/                          # Place corpus PDFs here
├── rubric/
│   └── extraction_rules.yaml      # Externalized thresholds & chunking constitution
├── research/
│   └── Domain_Notes.md            # Phase 0 domain analysis
├── tests/                         # pytest unit tests
├── docs/                          # Challenge spec & interim report
├── .refinery/                     # Runtime artifacts (git-ignored)
│   ├── profiles/                  # DocumentProfile JSONs
│   ├── pageindex/                 # PageIndex tree JSONs
│   └── extraction_ledger.jsonl    # Full audit log
├── main.py                        # CLI entrypoint
├── pyproject.toml                 # Dependencies (uv/pip)
├── Dockerfile                     # Container build
└── .env.example                   # Environment variable template
```

---

## Quick Start

### Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | ≥ 3.12 | Required |
| uv *(recommended)* | latest | `pip install uv` |
| Docker *(optional)* | latest | For containerised run |


### Option A — Python (uv)

```bash
# 1. Clone & enter
git clone https://github.com/martha-ketsela-mengistu/document-intelligence-refinery
cd document-intelligence-refinery

# 2. Install dependencies
uv sync           # creates .venv and installs from uv.lock
# or with pip:
pip install -e .

# 3. Configure environment
cp .env.example .env
# Edit .env — set OLLAMA_API_KEY, etc.

# 4. Place corpus PDFs
cp /path/to/your/*.pdf data/

# 5. Run the API server
uv run uvicorn src.server:app --reload --port 8000
# or:
python -m uvicorn src.server:app --reload --port 8000
```

### Option B — Docker

```bash
# Build
docker build -t refinery:latest .

# Run (mounts data dir and .env, exposes API on 8000)
docker run --rm -it \
  --env-file .env \
  -v "$(pwd)/data":/app/data \
  -v "$(pwd)/.refinery":/app/.refinery \
  -p 8000:8000 \
  refinery:latest
```

---

## Configuration

Copy `.env.example` to `.env` and set:

```dotenv
OLLAMA_API_KEY=your_key_here
```

Thresholds and chunking rules live in `rubric/extraction_rules.yaml` — modify these, **not code**, to onboard a new document domain.

---

## Usage

### CLI Pipeline

Run the full five-stage pipeline on a single document:
```bash
python main.py --file data/CBE_Annual_Report_2023-24.pdf
```

Run on first N pages only (useful for demos):
```bash
python main.py --file data/sample.pdf --pages 5
```

### API Server

Start the FastAPI server:
```bash
uvicorn src.server:app --reload --port 8000
```

Interactive docs available at: `http://localhost:8000/docs`

### Query & Audit

**Python SDK:**
```python
from src.agents.query_agent import RefineryAssistant
from src.agents.indexer import NavigationAgent
from src.agents.retrieval import RetrievalAgent

nav_agent = NavigationAgent()
ret_agent = RetrievalAgent()
page_index = nav_agent.load_tree("CBE_Annual_Report_2023-24.pdf")

assistant = RefineryAssistant(nav_agent=nav_agent, ret_agent=ret_agent, page_index=page_index)

# Natural language query with ProvenanceChain
answer = assistant.run("What is the net interest income for FY 2024?")
print(answer)

# Audit a claim against source
result = assistant.audit_claim("The report states total assets exceeded ETB 1 trillion in 2024.")
print(result)
```

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/files` | List all available corpus documents |
| `POST` | `/upload` | Upload a new PDF for processing |
| `GET` | `/triage/{doc_id}` | Run Stage 1: returns `DocumentProfile` JSON |
| `GET` | `/extract/{doc_id}` | Run Stage 2: returns per-page extraction results |
| `GET` | `/pageindex/{doc_id}` | Run Stages 3–4: returns `PageIndex` tree |
| `POST` | `/query` | Run Stage 5: natural language query → answer + `ProvenanceChain` |
| `POST` | `/audit` | Verify a claim against source with citation or "unverifiable" |

**Example — Triage:**
```bash
curl http://localhost:8000/triage/CBE_Annual_Report_2023-24.pdf | jq
```

**Example — Query:**
```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"doc_id": "CBE_Annual_Report_2023-24.pdf", "query": "What is total revenue?"}'
```

---

## Target Corpus

The pipeline is validated against four real-world document classes:

| Class | Description | Key Challenge |
|---|---|---|
| **A** | CBE Annual Report 2023-24 *(native digital)* | Multi-column layouts, embedded financial tables, footnotes |
| **B** | DBE Auditor's Report 2023 *(scanned image)* | No character stream — pure OCR required |
| **C** | FTA Assessment Report 2022 *(mixed)* | Narrative + tables + hierarchical sections |
| **D** | Ethiopia Tax Expenditure Report *(table-heavy)* | Multi-year fiscal tables, numerical precision |

Place PDFs in `data/` before running.

---

## Artifacts & Outputs

| Path | Description |
|---|---|
| `.refinery/profiles/{doc_id}.json` | DocumentProfile — classification result |
| `.refinery/pageindex/{doc_id}.json` | PageIndex navigation tree |
| `.refinery/extraction_ledger.jsonl` | Full audit log: strategy, confidence, cost, time |
| `data/uploads/` | User-uploaded documents (runtime) |

---

## Testing

```bash
# Run all tests
uv run pytest tests/ -v

# Triage unit tests
uv run pytest tests/test_triage.py -v

# Extractor confidence scoring
uv run pytest tests/test_extractor.py -v
```
