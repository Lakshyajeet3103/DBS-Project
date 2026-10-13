# Folio - Access-Controlled RAG Knowledge Engine

Folio is a document library and Retrieval-Augmented Generation (RAG) assistant with Junior and Senior access levels. The React frontend connects to a FastAPI backend that authenticates users, filters documents by role, retrieves authorized Chroma chunks, and generates answers with source links.

## Implemented features

| Component | Current behavior |
| --- | --- |
| Frontend | Login, overview, document library, reader, assistant, saved documents and access information |
| Authentication | SQL users, bcrypt password hashes and server-side sessions in HttpOnly cookies |
| Document API | Role-filtered listing and authorized document access |
| RAG | Chroma metadata filtering followed by SQL registry authorization checks before generation |
| Ingestion | SQL records, PDF, TXT, Markdown and image OCR; document registration and tagged chunks |
| Benchmarks | Reproducible FAISS FlatIP, HNSW and IVF comparisons using local MiniLM embeddings |

Demo mode uses fictional documents and simulated authentication. API mode uses the backend and does not fall back to demo data when an API call fails.

## Access model

| Role | Documents and retrieval |
| --- | --- |
| Junior | Junior documents only |
| Senior | Junior and Senior documents |
| Unknown or invalid | Access denied |

The backend derives the role from the authenticated session. Chat cannot elevate access by supplying a role in its request. Retrieved chunks must also resolve to an authorized document in the SQL registry; orphan or reclassified chunks are checked before reaching the model.

The seeded local accounts are:

| Email | Password | Seeded access |
| --- | --- | --- |
| `junior@folio.demo` | `Junior@123` | Six Junior documents |
| `senior@folio.demo` | `Senior@123` | All nine sample documents |

These are demonstration credentials. Do not use them for a public deployment.

## Run locally

Run backend commands from the repository root. You need Python with the backend dependencies, Node.js/npm for the frontend, and a Gemini API key for live embeddings and chat. Image OCR additionally requires the Tesseract executable.

### 1. Select the backend Python environment

Use the interpreter where the backend dependencies are installed. On the current Windows setup:

```powershell
$backendPython = "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe"
```

For a fresh installation, create a virtual environment using a Python version compatible with `requirements.txt`, then install the dependencies with that environment's Python:

```powershell
python -m venv .venv
$backendPython = ".\.venv\Scripts\python.exe"
& $backendPython -m pip install -r requirements.txt
```

The existing Python 3.13 environment was used for the recent checks; a fresh installation from the requirements file was not verified in that run. Keep the separately pinned benchmark environment apart from the backend environment.

### 2. Configure the backend

Create `.env` from `.env.example` only if it does not already exist:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Set the following values in `.env`, including your own API key:

```dotenv
DATABASE_URL=sqlite:///./data/folio.db
ENVIRONMENT=development
SESSION_DURATION_DAYS=7
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
GEMINI_API_KEY=your_gemini_api_key_here
EMBEDDING_PROVIDER=gemini
LLM_PROVIDER=gemini
LLM_MODEL=gemini-3.5-flash-lite
```

The default embedding model is `gemini-embedding-001`. The live chat implementation uses Gemini; setting `LLM_PROVIDER` alone does not install or select another provider. Restart the backend after changing `.env`.

For an initial demo setup, create the sample accounts and documents:

```powershell
& $backendPython -m database.seed
```

Seeding resets the sample account passwords and updates the canonical sample documents. It is a setup/reset command, not a required step each time the server starts.

### 3. Ingest documents and start the API

```powershell
& $backendPython ingest.py
& $backendPython -m uvicorn main:app --reload --port 8000
```

Ingestion makes embedding API calls. The API runs at `http://127.0.0.1:8000`; its interactive documentation is at `/docs`.

### 4. Start the frontend in another terminal

From the repository root, create `frontend/.env.local` if needed:

```powershell
if (-not (Test-Path frontend/.env.local)) {
    Copy-Item frontend/.env.example frontend/.env.local
}
```

Set these values in `frontend/.env.local`:

```dotenv
VITE_DATA_MODE=api
VITE_API_BASE_URL=
```

Leave the API base URL blank for local development. Vite proxies `/api` to port 8000, keeping browser requests and session cookies on the same origin. This works with both `localhost:5173` and `127.0.0.1:5173`.

```powershell
cd frontend
npm.cmd ci
npm.cmd run dev
```

Open `http://localhost:5173` and sign in with a seeded account. Restart Vite after changing its environment settings. `npm.cmd` avoids PowerShell's script execution-policy issue with `npm.ps1`.

For a frontend-only preview, set `VITE_DATA_MODE=demo` and restart Vite. This mode needs neither the backend nor a Gemini key. A separately hosted production frontend needs an API URL or reverse proxy; Vite's development proxy is not included in the static build.

## Ingest additional documents

Place files in the corresponding access folder:

```text
data/documents/
  junior/
    onboarding.md
    equipment-policy.pdf
  senior/
    planning.txt
```

Then run `ingest.py` from the project root and refresh the library.

- Supported formats: PDF, TXT, MD, PNG, JPG and JPEG. Images use Tesseract OCR; scanned PDFs do not automatically use image OCR.
- New files are registered in SQL so they appear in the library and pass retrieval authorization checks.
- Existing document text is updated before chunking. Chunks use an 800-character size and 150-character overlap, with document ID, title, role, category, type, year and chunk index metadata.
- Filenames must produce unique document IDs across folders. IDs use the lowercase filename stem with spaces and underscores replaced by hyphens.
- New files require a `junior/` or `senior/` folder. A folder conflicting with an existing SQL access level causes an error.
- Empty files, failed OCR and duplicate document IDs produce errors. Shortening a file replaces its old chunks after replacement embeddings are saved.
- Removing a source file does not delete its SQL document. Remove the registry record explicitly when a document should be removed; subsequent successful ingestion prunes orphan chunks.
- `data/sample_document.pdf` is a loader check during the main ingestion command. Put PDFs in the role folders to import them into the library.

SQL and Chroma do not share a transaction. After a partial vector-store failure, rerun ingestion to reconcile them. Changing embedding models requires a compatible rebuilt collection; do not mix vector dimensions or models in an existing collection.

See [INGESTION.md](INGESTION.md) for details and isolated tests.

## API endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/` | Backend health check |
| POST | `/api/auth/login` | Authenticate and set the session cookie |
| GET | `/api/auth/me` | Return the current user |
| POST | `/api/auth/logout` | Revoke the session and clear the cookie |
| GET | `/api/documents` | List authorized documents |
| GET | `/api/documents/{document_id}` | Read one authorized document |
| POST | `/api/chat` | Answer from authorized context with source links |

Chat accepts `{"message": "...", "document_id": "optional-document-id"}` and returns `{"reply": "...", "sources": [{"id": "...", "title": "..."}]}`. Requests without an authorized session are rejected. Questions without suitable authorized context receive a refusal rather than an answer from unrestricted documents.

## Run benchmarks

The research pipeline compares FlatIP, HNSW and IVF using normalized MiniLM embeddings of saved sample documents. It measures build time, search latency, Recall@5 against exact vector neighbours, and serialized index size. It does not measure ingestion correctness, Gemini response time, OCR or answer quality.

The current Windows Python environment can run the benchmark tests and CLI. From the repository root:

```powershell
$benchmarkPython = "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe"
$env:HF_HOME = Join-Path (Get-Location) 'data/vector_store/huggingface'

# Small trial: 500 vectors, 100 queries, one build per index.
& $benchmarkPython -m src.benchmark --sizes 500 --queries-count 100 --repeats 1 --seed 42 --output data/vector_store/benchmark-smoke

# Full comparison: 500, 2000 and 10000 vectors, three builds per index.
& $benchmarkPython -m src.benchmark --seed 42 --output data/vector_store/benchmark-full
```

The first run downloads MiniLM from Hugging Face and needs internet access. Embedding and index evaluation then run locally; no Gemini key is required. The recent smoke-run attempt stalled during that initial download, so it did not produce new measurements.

Each output directory contains summary, query and trial CSV files plus `benchmark_metadata.json`. An explicit seed reproduces workload selection; timings still vary. Omitting `--seed` generates and records a fresh seed. Results use synthetic sample documents, so recall is neighbour agreement rather than human-rated relevance.

See [BENCHMARK.md](BENCHMARK.md) for the recorded measurements, dataset details, external JSONL inputs and the isolated Python 3.11 environment with pinned dependencies. The current Python 3.13 package versions differ from that recorded environment. Do not install the benchmark lock into the working backend environment.

## Verification

Backend tests seed data during collection. Use the isolation plugin to protect the working SQL database:

```powershell
& $backendPython -m pytest -p benchmark_tests.backend_isolation tests -q -p no:cacheprovider --basetemp=data/vector_store/backend-tests
& $benchmarkPython -m pytest -c benchmark_tests/pytest.ini benchmark_tests -q -p no:cacheprovider --basetemp=data/vector_store/benchmark-tests
```

Frontend checks, from `frontend/`:

```powershell
npm.cmd test
npm.cmd run build
```

Recent checks passed: 79 backend tests, one additional real-Chroma ingestion round trip, 13 benchmark tests, and five frontend tests plus the production build. The Chroma ingestion test uses local deterministic test embeddings; OCR tests mock Tesseract. These results do not establish production readiness or a completed fresh benchmark run.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Session expires immediately after login | Leave `VITE_API_BASE_URL` blank locally, restart Vite, and verify the backend is on port 8000. |
| Cannot reach the backend | Start Uvicorn with the correct Python environment and check the health endpoint. |
| Assistant is busy or times out | Check provider availability and the configured model. The chat client has a 20-second request timeout and a limited retry configuration; supported provider busy errors return HTTP 503. |
| New document is missing | Check the role folder, filename uniqueness, ingestion output and SQL registration. Refresh the library after a successful import. |
| Image yields no text | Install Tesseract and ensure its executable is available to the backend process. |
| Benchmark fails before measurements | Allow the initial MiniLM download to finish and use the documented dependency environment. |

## Project structure

```text
main.py                  FastAPI entry point
core/                    Authentication and access-control helpers
routers/                 Auth, document and chat APIs
database/                SQL connection, models and demo seeding
services/                RAG retrieval/generation and OCR
ingest.py                File import, SQL synchronization and Chroma ingestion
frontend/                React/Vite application and frontend tests
tests/                   Backend and ingestion tests
src/                     FAISS benchmarks, chunking and MiniLM embeddings
benchmark_tests/         Benchmark tests and backend-isolation plugin
data/documents/          Role-organized source files
data/benchmark_samples/  Fictional benchmark documents and queries
data/vector_store/       Ignored local caches, test data and benchmark outputs
chroma/                  Persisted application vector store
results/                 Recorded benchmark outputs and environment lock
```

## Remaining limitations

There is no upload/admin UI, self-service registration, multi-tenant isolation, or server-side conversation memory. Bookmarks are stored in the browser. Public deployment still needs operational controls such as rate limiting, audit logging and deployment-specific cookie/CORS configuration. Generated answers can be wrong; verify important claims against the cited documents.

Sample accounts and documents are fictional. Keep API keys in ignored environment files and real restricted documents out of frontend bundles and public repositories.
