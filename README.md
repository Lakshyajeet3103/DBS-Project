# Folio — Access-Controlled RAG Knowledge Engine

Folio is a Retrieval-Augmented Generation (RAG) system for enterprise knowledge access. Employees sign in with an assigned access level (**Junior** or **Senior**), browse only the documents they are cleared to see, and ask an assistant that answers from that same authorized corpus — never from restricted material outside their role.

The project combines:

| Layer | Status | Role |
| --- | --- | --- |
| **Folio frontend** (`frontend/`) | Implemented (demo + API adapter) | Login, role-aware library, document reader, assistant UI |
| **RAG backend** (`main.py`, `ingest.py`) | Partial | FastAPI + ChromaDB + Gemini embeddings/LLM chat |
| **Indexing research** (`src/`) | Prototype | FAISS Flat / HNSW / IVF indexing experiments |
| **Server-side auth & ACL retrieval** | Proposed | Required for production access control |

> **Security note:** Demo login and frontend filters are presentation behavior, not a security boundary. Production safety depends on authenticating every request on the server and filtering vector retrieval by role *before* context reaches the LLM.

---

## Objectives

1. **Least-privilege knowledge access** — Each employee sees and queries only documents matching their access level (Junior → Junior docs; Senior → Junior + Senior).
2. **Grounded answers** — The assistant retrieves relevant passages from an authorized knowledge base and generates replies from that context, reducing hallucination on internal policies and guides.
3. **Role consistency across surfaces** — Library search, document open, downloads, and chat all obey the same access rules.
4. **Practical RAG pipeline** — Ingest documents → chunk → embed → store in a vector index → retrieve top-k → prompt an LLM with filtered context.
5. **Path to production** — Define auth sessions, metadata-aware retrieval, and multi-format ingestion so the demo can grow into an enterprise knowledge workspace.

---

## Scope

### In scope (current + proposed)

- Two-tier RBAC: `junior` and `senior` (deny-by-default for unknown roles)
- Document metadata: title, category, type, year, access level, author, content
- RAG chat over authorized documents (demo keyword matching today; LLM + vectors when backend is wired)
- PDF ingestion into ChromaDB (backend prototype)
- Frontend filters by text query, document type, year, and access level
- Per-account bookmarks (browser `localStorage` in demo)
- API contract for auth, documents, and chat (`frontend/API_CONTRACT.md`)
- Optional extensions documented under [Improvements](#improvements): SQL user store, richer segregation (year, doc type), multi-format ingest, OCR

### Out of scope (for now)

- Role administration UI / self-service account creation
- Upload pipeline in the product UI
- Multi-tenant isolation across separate organizations
- Fine-grained ABAC (department, region, document owner) beyond Junior/Senior
- Real-time sync of bookmarks to a server
- Conversation memory across chat turns (each question is independent today)

---

## Access model

| Role | Library | Assistant retrieval |
| --- | --- | --- |
| **Junior** | Junior documents only | Chunks tagged `level=junior` only |
| **Senior** | Junior + Senior documents | Chunks tagged `level` in `{junior, senior}` |
| **Unknown / invalid** | Denied | Denied |

Senior inherits Junior access. Roles are assigned to accounts by the organization; users cannot pick a role after sign-in.

**Demo accounts** (local preview only):

| Account | Password | Access |
| --- | --- | --- |
| `junior@folio.demo` | `Junior@123` | 6 Junior sample documents |
| `senior@folio.demo` | `Senior@123` | All 9 sample documents |

---

## How it works

### End-to-end flow (target)

```
┌─────────────┐   login    ┌──────────────────┐
│  Folio UI   │───────────►│  Auth / Session  │  role from server, not client
│  (React)    │◄───────────│  (HttpOnly cookie)│
└──────┬──────┘            └────────┬─────────┘
       │ documents / chat           │
       ▼                            ▼
┌──────────────────────────────────────────────┐
│              FastAPI application             │
│  1. Authenticate request                     │
│  2. Resolve role → metadata filter           │
│  3. Embed query (Gemini embeddings)          │
│  4. Chroma similarity search WITH filter     │
│  5. Stuff authorized chunks into prompt      │
│  6. Generate answer (Gemini chat) + sources  │
└──────────────────────────────────────────────┘
       ▲
       │ ingest (offline / admin)
┌──────┴───────┐    chunks + metadata     ┌────────────┐
│  Documents   │ ───────────────────────► │  ChromaDB  │
│ PDF / text…  │   level, type, year…     │  ./chroma  │
└──────────────┘                          └────────────┘
```

### Frontend (implemented)

1. User signs in → session stored in `sessionStorage` (demo) or cookie (live API).
2. Document list is filtered with `canAccess(user, doc)` — Senior sees both levels; Junior never sees Senior titles, search hits, or excerpts.
3. Opening a document by ID fails closed if the ID is outside the user’s level.
4. Assistant chat:
   - **Demo mode** (`VITE_DATA_MODE=demo`): keyword-scored excerpts from *accessible* documents only; no LLM call.
   - **API mode** (`VITE_DATA_MODE=api`): `POST /api/chat` with `{ message, document_id? }`; server must enforce ACL.

### Backend RAG pipeline (partial)

1. **`ingest.py`** — Load PDF via `PyPDFLoader`, split with `RecursiveCharacterTextSplitter` (chunk size 1000, overlap 200), embed with `gemini-embedding-001`, persist to Chroma at `./chroma`.
2. **`main.py`** — FastAPI app with CORS for Vite (`localhost:5173`). Loads Chroma, retrieves top-3 chunks, runs a stuff-documents RAG chain with `ChatGoogleGenerativeAI`, exposes:
   - `GET /` — health
   - `POST /api/chat` — `{ message }` → `{ reply }`  
   **Missing today:** auth, document listing, and **role metadata filters on retrieval**.

### Industry-aligned ACL pattern (verified)

Production RAG systems should **push authorization into the vector query**, not only hide results in the UI:

- Tag every chunk at ingest with metadata such as `level`, `type`, `year`, department, etc. ([Chroma metadata filtering](https://docs.trychroma.com/docs/querying-collections/metadata-filtering)).
- At query time, derive an allow-list from the **server session** and pass a `where` / `filter` into similarity search (e.g. Junior: `{"level": "junior"}`; Senior: `{"level": {"$in": ["junior", "senior"]}}`).
- Only authorized chunks enter the LLM prompt ([Cerbos RAG authorization](https://docs.cerbos.dev/cerbos/latest/recipes/ai/rag-authorization/), [AWS Bedrock + Verified Permissions](https://aws.amazon.com/blogs/architecture/secure-multi-tenant-rag-with-amazon-bedrock-and-verified-permissions/)).
- Prefer filter **pushdown** in the vector store; post-retrieval filtering alone can leak sensitive text into top-k candidates and hurt recall for authorized users ([ACM: Securing the Agent](https://dl.acm.org/doi/pdf/10.1145/3786335.3813145)).

---

## Proposed final architecture

### 1. Identity & session

- `POST /api/auth/login`, `GET /api/auth/me`, `POST /api/auth/logout`
- HttpOnly, Secure (HTTPS), SameSite cookie; CORS limited to the frontend origin with credentials
- Role stored server-side; never trusted from the request body
- Optional SQL store for users, password hashes, and role assignments

### 2. Document registry & ingestion

- Canonical document records (id, title, level, type, year, category, storage URI)
- Ingest pipeline attaches **chunk metadata** matching registry fields
- Loaders: PDF (current), plain text / Markdown (planned), images via OCR (optional)
- Re-index on document update; revoke by removing or re-tagging chunks

### 3. Permission-aware retrieval

```text
role = session.role
filter = { "level": "junior" }                         # junior
        | { "level": { "$in": ["junior", "senior"] } } # senior
        | deny                                         # anything else

retriever = vector_db.as_retriever(
    search_kwargs={ "k": 3, "filter": filter }
)
# Optional: AND year / type / document_id scopes from the request
```

### 4. Generation

- Prompt: answer **only** from provided context; refuse when missing
- Response includes `reply` + `sources[{id, title}]` for citation in the UI
- Optional `document_id` scopes retrieval to one authorized document

### 5. Indexing strategy (research track)

`src/` prototypes FAISS indexes for latency/recall trade-offs as the corpus grows:

| Strategy | Behavior |
| --- | --- |
| **Flat** | Exact search; perfect recall; latency grows with corpus size |
| **HNSW** | Graph ANN; strong recall, higher memory |
| **IVF** | Clustered ANN; tunable via `nlist` / `nprobe` |

Embeddings experiment path uses `sentence-transformers/all-MiniLM-L6-v2`; the live Gemini path uses `gemini-embedding-001`.

### 6. Presentation

Folio UI: Overview, Document library (search + filters), Reader + text download, AI assistant, Saved documents, Access explanation — all role-aware.

---

## Project structure

```
DBS-Project/
├── main.py                 # FastAPI RAG chat service
├── ingest.py               # PDF → chunks → Chroma embeddings
├── requirements.txt        # FAISS / sentence-transformers research deps
├── data/
│   ├── sample_document.pdf
│   └── sample_documents.txt
├── src/
│   ├── chunking.py         # Text / token chunking utilities
│   ├── embeddings.py       # Local MiniLM embeddings
│   ├── vector_index.py     # FAISS Flat / HNSW / IVF builders
│   └── benchmark.py        # Benchmark harness (stub)
├── results/                # Benchmark outputs
├── chroma/                 # Persisted Chroma vector store (local)
├── additional features.txt # Product backlog notes
└── frontend/               # Folio — React + Vite workspace
    ├── API_CONTRACT.md     # Auth / documents / chat contract
    ├── src/
    │   ├── App.jsx         # Screens & session lifecycle
    │   ├── api.js          # Demo vs live API adapter
    │   ├── access.js       # RBAC helpers & demo retrieval
    │   └── data.js         # Fictional sample documents
    └── tests/access.test.js
```

---

## Current status

| Capability | Frontend demo | Backend today | Proposed production |
| --- | --- | --- | --- |
| Login / roles | Simulated | Missing | Cookie session + SQL users |
| List / open documents | Yes (RBAC) | Missing | Authorized document APIs |
| Chat | Keyword excerpts | Unfiltered RAG | Session + Chroma metadata filter |
| Citations / sources | Yes | Reply only | `sources` array |
| Multi-format ingest | N/A | PDF only | PDF, TXT, MD, OCR images |
| Index benchmarking | N/A | FAISS prototypes | Guide choice of Flat/HNSW/IVF |

---

## Limitations

1. **No server-side authorization** — Current `POST /api/chat` retrieves from the full Chroma collection; any caller who can reach the API could get unrestricted context.
2. **Demo auth is not security** — Credentials and documents ship in the JS bundle for preview; never put real restricted content there.
3. **Unlabeled chunks** — Ingest does not yet write `level` / `type` / `year` metadata required for ACL filters.
4. **Single chat endpoint** — Auth and document APIs from `API_CONTRACT.md` are not implemented on the backend.
5. **No conversational memory** — Each question is independent; history is UI-only.
6. **Dependency split** — Root `requirements.txt` lists research packages (FAISS, sentence-transformers); the Gemini/LangChain/FastAPI stack used by `main.py` / `ingest.py` is not fully declared there.
7. **Benchmark suite incomplete** — `results/benchmark_results.csv` is a header-only stub; `benchmark.py` is empty.
8. **Scale & ops** — Local Chroma folder, no rate limiting, audit logging, or revocation workflow for departed employees.
9. **Model grounding risk** — Even with filters, LLMs can still produce incorrect paraphrases; users should verify important answers against source documents.

---

## Improvements

Prioritized toward the enterprise backlog in `additional features.txt` and industry RAG ACL practice:

1. **Implement the API contract** — Auth, documents, and permission-aware chat; filter retrieval by session role before the LLM.
2. **Metadata at ingest** — Persist `level`, `type`, `year`, `document_id` on every chunk; support Chroma `$and` / `$in` filters.
3. **SQL (or equivalent) user store** — Hashed passwords, role assignment, session revocation.
4. **Richer segregation** — Combine role with year and document type in both library filters and vector `where` clauses.
5. **Multi-format loaders** — Text, Markdown, and optional image OCR alongside PDF.
6. **Model options** — Configurable LLM vs smaller SLM; optional local embeddings for air-gapped deployments.
7. **Post-retrieval re-check** — Dual-layer ACL: metadata filter plus verify each candidate against the document registry before prompting ([Amazon Quick ACL pattern](https://aws.amazon.com/blogs/machine-learning/rethinking-access-control-for-rag-with-amazon-quick-and-amazon-bedrock/)).
8. **Indexing guidance** — Complete Flat/HNSW/IVF benchmarks to pick an index as the corpus grows.
9. **Observability** — Audit which documents were retrieved per user/query; rate limits; redaction of secrets in logs.
10. **Admin tooling** — Controlled upload, role changes, and re-indexing without shipping restricted PDFs to the browser.

---

## Tech stack

| Area | Choice |
| --- | --- |
| Frontend | React 18, Vite 5 |
| Backend API | FastAPI, Uvicorn, CORS middleware |
| Embeddings (live path) | Google `gemini-embedding-001` via LangChain |
| LLM | Google Gemini chat (`ChatGoogleGenerativeAI`) |
| Vector store | ChromaDB (persisted `./chroma`) |
| Ingest | LangChain `PyPDFLoader`, `RecursiveCharacterTextSplitter` |
| Research embeddings | `sentence-transformers/all-MiniLM-L6-v2` |
| Research indexes | FAISS Flat / HNSW / IVF |

---

## Quick start

### Folio frontend (demo — no API key required)

```sh
cd frontend
npm install
npm run dev -- --host 127.0.0.1
```

Open http://127.0.0.1:5173 and use a demo account from the login panel.

```sh
npm test
npm run build
```

### Live API mode (when backend endpoints exist)

```sh
cp frontend/.env.example frontend/.env.local
# Set VITE_DATA_MODE=api and VITE_API_BASE_URL=http://127.0.0.1:8000
```

See [frontend/API_CONTRACT.md](frontend/API_CONTRACT.md) and [frontend/README.md](frontend/README.md).

### RAG backend (prototype)

1. Create a `.env` with `GEMINI_API_KEY` (never commit it; `.env` is gitignored).
2. Install the LangChain / FastAPI / Chroma / Google GenAI packages used by `main.py` and `ingest.py`.
3. Ingest once:

```sh
python ingest.py   # expects data/sample_document.pdf
```

4. Serve:

```sh
uvicorn main:app --reload
```

Until auth and metadata filters are added, treat this API as a **local lab only**.

---

## Acceptance criteria (production)

1. A Junior session cannot fetch any Senior document by guessing an ID.
2. Search and chat never expose Senior-only facts to Juniors.
3. Senior sessions can retrieve both levels.
4. Editing browser storage, request bodies, or URLs cannot elevate a server session.
5. Logout and expiration invalidate protected requests.
6. Wrong-origin mutations are rejected by CORS / CSRF controls.

---

## References

- [Chroma metadata filtering](https://docs.trychroma.com/docs/querying-collections/metadata-filtering)
- [Cerbos — Authorization in RAG systems](https://docs.cerbos.dev/cerbos/latest/recipes/ai/rag-authorization/)
- [AWS — Secure multi-tenant RAG with Bedrock & Verified Permissions](https://aws.amazon.com/blogs/architecture/secure-multi-tenant-rag-with-amazon-bedrock-and-verified-permissions/)
- [AWS — Real-time ACL checks for RAG](https://aws.amazon.com/blogs/machine-learning/rethinking-access-control-for-rag-with-amazon-quick-and-amazon-bedrock/)
- [Google Gemini embeddings](https://ai.google.dev/gemini-api/docs/embeddings)
- [LangChain — Google Generative AI embeddings](https://docs.langchain.com/oss/python/integrations/embeddings/google_generative_ai)

---

## License / data disclaimer

Sample documents in the frontend are **fictional** and for demonstration only. Do not store or ship real restricted employee or company documents in client bundles or public repositories.
