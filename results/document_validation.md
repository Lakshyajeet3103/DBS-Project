# Person 4 validation on Person 2's latest PR

Base: PR #7 `person_2`, commit `cfc947143ee364b52c615c2aa0106c890f55b23e`.
New branch: `codex/person4-document-benchmark`. The new PR targets `person_2`.
The earlier Person 4 PR #6 was not updated or closed by this work.

## Checks

- Full saved-document benchmark: **9 configurations, 3,240 query timings, 27
  build trials**. Random seed **4079965474**, IVF seed **1932481826**. All summary
  calculations, input/source hashes and pinned package versions independently
  verified. The candidate pool contains 24 source documents plus a query file.
- Full replay with `--seed 4079965474`: identical corpus/query/embedding hashes,
  recall and serialized memory for all nine configurations. Timings vary, as
  expected; the published CSV retains the initial run rather than selecting the
  fastest run.

- Standalone benchmark suite: **13 passed**. Covers FAISS builders, cache
  corruption/invalidation, validation, saved document selection, seeded replay,
  random seed allocation, recall and CSV aggregation.
- Inherited Person 1/2/3 suites: **69 passed**, using a disposable SQL database
  and the shareable `benchmark_tests.backend_isolation` plugin.
- Additional existing local security QA: combined **91 passed, 1 expected failure**
  (69 inherited + 14 earlier PR regressions + 9 auth cases). These supplementary
  local QA files are not part of the benchmark PR. The previously failing registry,
  stale-permission, unregistered-chunk, PDF-path and collection checks now pass.
- Frontend: **5 tests passed**, and Vite production build passed after installing
  the existing lock with `npm ci`. No frontend source or dependency changes.
- Dependency audit: **3 inherited findings: 2 high, 1 moderate** in vite,
  source-map-js and esbuild. Follow up with the frontend owner; do not interpret
  the successful build as a clean dependency audit.
- The existing bcrypt 72-byte truncation defect remains an expected failure in
  supplementary authentication QA. Follow up with Person 1.

The initial backend run lacked Pillow/pytesseract/pypdf; installing those Python
dependencies resolved the four setup failures. The final ingestion tests exercise
real PDF extraction but mock Chroma and OCR results. They do not establish that
Tesseract is installed or that live Chroma/Gemini integration works.

## Reproduce the inherited suite safely

Use the backend environment with pytest, FastAPI/httpx, SQLAlchemy, bcrypt,
python-dotenv, Pillow, pytesseract and pypdf installed. The plugin configures a
temporary DB before collection because inherited tests seed at import time.

```powershell
python -m pytest --noconftest -p benchmark_tests.backend_isolation tests/test_auth_api.py tests/test_database_and_auth.py tests/test_chat_api.py tests/test_documents_api.py tests/test_ingestion.py tests/test_rag_acl.py -v
```

Run the standalone benchmark using the separate environment and commands in
`BENCHMARK.md`. Do not claim the entire product has passed end-to-end acceptance:
the six-criterion Person 4 acceptance-suite handoff and live service smoke tests
are separate work. The benchmark tests and inherited test suites are explicitly
identified above; the local incomplete acceptance adapter was not run as a passing
product test.

Screenshots and raw local test logs are shared privately in the user's chat,
not added to this public PR.
