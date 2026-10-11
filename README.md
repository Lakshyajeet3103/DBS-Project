# Folio — Access-Controlled RAG Knowledge Engine

Folio is a Retrieval-Augmented Generation (RAG) system for enterprise knowledge access. Employees sign in with an assigned access level (**Junior** or **Senior**), browse only the documents they are cleared to see, and ask an assistant that answers from that same authorized corpus — never from restricted material outside their role.

| Layer | Status | Role |
| --- | --- | --- |
| **Folio frontend** (`frontend/`) | Implemented | Login, role-aware library, document reader, assistant (demo or live API) |
| **RAG backend** (`main.py`, routers, services) | Implemented | FastAPI + SQLite sessions + ChromaDB with ACL filter pushdown |
| **Ingestion** (`ingest.py`) | Implemented | Multi-format loaders, chunk metadata (`level`, `document_id`, …), Chroma upsert |
| **Indexing research** (`src/`) | Implemented | FAISS Flat / HNSW / IVF benchmarks (optional, separate env recommended) |

> **Security note:** Demo login (`VITE_DATA_MODE=demo`) is presentation-only. Production safety depends on live API mode with server sessions and metadata-filtered retrieval *before* context reaches the LLM.

---

## Prerequisites

| Component | Minimum | Notes |
| --- | --- | --- |
| **Python** | 3.10+ | Backend, ingest, tests (3.12 verified) |
| **Node.js** | 18+ | Folio React + Vite frontend |
| **npm** | 9+ | Frontend package manager |
| **SQLite** | 3.35+ | Bundled with Python; used for users, sessions, documents |
| **Google Gemini API key** | Optional | Required when `EMBEDDING_PROVIDER=gemini` / `LLM_PROVIDER=gemini` |
| **Tesseract OCR** | Optional | Only needed to ingest scanned images (`.png` / `.jpg`) |

Detailed external setup (OCR packages, Gemini key steps, local offline mode) is in [PREREQUISITES_AND_EXTERNAL_SETUP.md](PREREQUISITES_AND_EXTERNAL_SETUP.md).

### Optional: Tesseract (image OCR)

```bash
# Debian / Ubuntu
sudo apt update && sudo apt install -y tesseract-ocr

# macOS
brew install tesseract
```

Without Tesseract, the app still runs; image OCR is skipped gracefully.

---

## Quick start for new users

Pick one path:

1. **Frontend demo only** — UI with fictional documents, no Python API key required.
2. **Full stack (recommended)** — Backend + seeded DB + vector ingest + live frontend.

---

### Option A — Frontend demo only

```bash
cd frontend
npm install
npm run dev -- --host 127.0.0.1
```

Open http://127.0.0.1:5173 and sign in with a demo account below.

Default mode is `VITE_DATA_MODE=demo` (no backend). Chat uses keyword excerpts from accessible sample docs, not an LLM.

---

### Option B — Full stack (backend + frontend)

Run all commands from the **repository root** unless noted.

#### 1. Clone and enter the project

```bash
cd DBS-Project
```

#### 2. Create a Python virtual environment and install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```

#### 3. Configure backend environment

```bash
cp .env.example .env
```

Edit `.env` as needed. Minimum useful settings:

| Variable | Example | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite:///./data/folio.db` | SQLite user / session / document store |
| `SECRET_KEY` | any long random string | Session crypto salt (change for real deployments) |
| `ENVIRONMENT` | `development` | Use `production` to set Secure cookies |
| `SESSION_DURATION_DAYS` | `7` | HttpOnly cookie lifetime |
| `CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Allowed frontend origins |
| `GEMINI_API_KEY` | your key from [Google AI Studio](https://aistudio.google.com/) | Cloud embeddings + chat |
| `EMBEDDING_PROVIDER` | `gemini` or `local` | `local` uses MiniLM (no Gemini key) |
| `LLM_PROVIDER` | `gemini` or `local` | Chat generation provider |
| `LLM_MODEL` | `gemini-1.5-flash` | Gemini model name when using cloud LLM |

**No Gemini key?** Set:

```ini
EMBEDDING_PROVIDER=local
LLM_PROVIDER=local
```

Local embeddings use `sentence-transformers/all-MiniLM-L6-v2` (first run downloads the model).

#### 4. Seed the database

```bash
python -m database.seed
```

Creates `data/folio.db` with demo users and 9 canonical documents (6 Junior, 3 Senior).

#### 5. Ingest documents into ChromaDB

```bash
python ingest.py
```

Loads the SQL document registry (and related files under `data/`), chunks text, attaches ACL metadata, and upserts into `./chroma` (`folio_knowledge_base`). Re-run after changing seed documents.

#### 6. Start the API

```bash
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

Health check: http://127.0.0.1:8000/ → `{"status":"AI backend is running"}`  
Interactive docs: http://127.0.0.1:8000/docs

#### 7. Start the frontend in API mode (second terminal)

```bash
cd frontend
cp .env.example .env.local
```

Set `frontend/.env.local` to:

```ini
VITE_DATA_MODE=api
VITE_API_BASE_URL=http://127.0.0.1:8000
```

Then:

```bash
npm install
npm run dev -- --host 127.0.0.1
```

Open http://127.0.0.1:5173. Use the same hostname family for UI and API (`127.0.0.1` with `127.0.0.1`) so session cookies work with CORS + credentials.

---

## Demo accounts

| Account | Password | Access |
| --- | --- | --- |
| `junior@folio.demo` | `Junior@123` | Junior documents only (6) |
| `senior@folio.demo` | `Senior@123` | Junior + Senior documents (9) |

Roles are assigned on the account; users cannot choose a role after sign-in.

---

## Access model

| Role | Library | Assistant retrieval |
| --- | --- | --- |
| **Junior** | Junior documents only | Chunks with `level=junior` only |
| **Senior** | Junior + Senior | Chunks with `level` in `{junior, senior}` |
| **Unknown / invalid** | Denied | Denied |

Senior inherits Junior access. Live API derives role from the server session cookie, not from the client request body. Retrieval uses Chroma metadata filter pushdown, then re-checks chunks against the SQL document registry before prompting the LLM.

---

## Verify the install

### Backend tests

```bash
source .venv/bin/activate
pytest -v
```

### Frontend tests and production build

```bash
cd frontend
npm test
npm run build
```

### Smoke-check auth (with API running)

```bash
curl -c cookies.txt -X POST http://127.0.0.1:8000/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"junior@folio.demo","password":"Junior@123"}'

curl -b cookies.txt http://127.0.0.1:8000/api/auth/me
curl -b cookies.txt http://127.0.0.1:8000/api/documents
```

---

## How it works (full stack)

```
┌─────────────┐   login    ┌──────────────────┐
│  Folio UI   │───────────►│  Auth / Session  │  role from server cookie
│  (React)    │◄───────────│  (HttpOnly)      │
└──────┬──────┘            └────────┬─────────┘
       │ documents / chat           │
       ▼                            ▼
┌──────────────────────────────────────────────┐
│              FastAPI application             │
│  1. Authenticate request (folio_session)     │
│  2. Resolve role → Chroma metadata filter    │
│  3. Embed query (Gemini or local MiniLM)     │
│  4. Similarity search WITH ACL filter        │
│  5. Re-verify chunks against SQL registry    │
│  6. Generate answer + sources                │
└──────────────────────────────────────────────┘
       ▲
       │ ingest (offline / admin)
┌──────┴───────┐    chunks + metadata     ┌────────────┐
│  Documents   │ ───────────────────────► │  ChromaDB  │
│ PDF / MD /…  │   level, type, year…     │  ./chroma  │
└──────────────┘                          └────────────┘
```

### Main API surfaces

| Endpoint | Purpose |
| --- | --- |
| `POST /api/auth/login` | Email/password → HttpOnly `folio_session` cookie |
| `GET /api/auth/me` | Current user profile |
| `POST /api/auth/logout` | Revoke session, clear cookie |
| `GET /api/documents` | Role-filtered document list |
| `GET /api/documents/{id}` | Authorized document detail (`403`/`404` if denied) |
| `POST /api/chat` | Permission-aware RAG (`message`, optional `document_id`) → `reply` + `sources` |

Contract details: [frontend/API_CONTRACT.md](frontend/API_CONTRACT.md).

---

## Project structure

```
DBS-Project/
├── main.py                      # FastAPI entrypoint
├── ingest.py                    # Multi-format ingest → Chroma
├── requirements.txt             # Backend + research Python deps
├── .env.example                 # Backend config template
├── PREREQUISITES_AND_EXTERNAL_SETUP.md
├── BENCHMARK.md                 # FAISS research track runbook
├── database/
│   ├── connection.py            # SQLAlchemy engine / sessions
│   ├── models.py                # User, Session, Document
│   └── seed.py                  # Demo users + document catalog
├── core/                        # Auth helpers, ACL, FastAPI deps
├── routers/                     # auth, documents, chat
├── services/                    # rag_service, ocr_service
├── data/
│   ├── documents/               # Sample junior/senior files
│   ├── folio.db                 # SQLite DB (created by seed)
│   └── sample_document.pdf
├── chroma/                      # Persisted vector store (created by ingest)
├── src/                         # FAISS Flat / HNSW / IVF research
├── tests/                       # Backend pytest suite
└── frontend/                    # React 18 + Vite 5
    ├── .env.example
    ├── API_CONTRACT.md
    └── src/                     # App, api adapter, access helpers
```

---

## Objectives

1. **Least-privilege knowledge access** — Junior → Junior docs; Senior → Junior + Senior.
2. **Grounded answers** — Retrieve authorized passages, then generate from that context.
3. **Role consistency** — Library, reader, downloads, and chat share the same access rules.
4. **Practical RAG pipeline** — Ingest → chunk → embed → filter → retrieve → prompt → cite.
5. **Research track** — Compare FAISS index strategies as the corpus grows (`src/`, [BENCHMARK.md](BENCHMARK.md)).

---

## Tech stack

| Area | Choice |
| --- | --- |
| Frontend | React 18, Vite 5 |
| Backend API | FastAPI, Uvicorn, CORS + credentials |
| Auth | SQLite sessions, bcrypt, HttpOnly cookies |
| Embeddings | Gemini `gemini-embedding-001` or local MiniLM |
| LLM | Gemini chat or local provider setting |
| Vector store | ChromaDB (`./chroma`) |
| Ingest | PDF, TXT, Markdown, optional OCR images |
| Research indexes | FAISS Flat / HNSW / IVF |

---

## Optional: FAISS indexing benchmarks

The research suite is separate from the Folio product path and may prefer its own Python environment (see [BENCHMARK.md](BENCHMARK.md) and `requirements-benchmark.txt`).

```bash
# From repo root, with research deps available:
python -m src.benchmark
# Replay a recorded run:
python -m src.benchmark --seed <recorded-seed>
```

---

## Scope notes

**In scope:** Two-tier RBAC, SQL user/document registry, permission-aware chat with sources, multi-format ingest with chunk metadata, frontend demo + live API modes.

**Out of scope (for now):** Role admin UI, self-service signup, upload UI, multi-tenant orgs, fine-grained ABAC beyond Junior/Senior, server-synced bookmarks, multi-turn LLM memory.

---

## Troubleshooting

| Problem | What to check |
| --- | --- |
| Frontend cannot reach API | Backend on `:8000`; `VITE_API_BASE_URL` matches; restart Vite after editing `.env.local` |
| Login works in curl but not browser | Use `127.0.0.1` (or `localhost`) consistently for UI and API; confirm `CORS_ORIGINS` |
| Chat returns empty / no context | Run `python ingest.py` after seeding; confirm `./chroma` exists |
| Gemini errors | Set a valid `GEMINI_API_KEY`, or switch providers to `local` |
| OCR failures on images | Install Tesseract, or ignore if you are not ingesting images |

Do not commit `.env`, `.env.local`, `.venv/`, `node_modules/`, or secrets. Sample documents are **fictional** and for demonstration only.

---

## Further reading

- [PREREQUISITES_AND_EXTERNAL_SETUP.md](PREREQUISITES_AND_EXTERNAL_SETUP.md) — system packages, keys, local mode
- [frontend/README.md](frontend/README.md) — frontend-only notes
- [frontend/API_CONTRACT.md](frontend/API_CONTRACT.md) — auth / documents / chat contract
- [BENCHMARK.md](BENCHMARK.md) — FAISS Flat / HNSW / IVF evaluation
- [Chroma metadata filtering](https://docs.trychroma.com/docs/querying-collections/metadata-filtering)
- [Google Gemini embeddings](https://ai.google.dev/gemini-api/docs/embeddings)
