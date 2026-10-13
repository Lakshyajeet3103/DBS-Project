# Person 4: document-based FAISS benchmark

This branch starts from Person 2 PR #7, commit
`cfc947143ee364b52c615c2aa0106c890f55b23e`, on `person_2`.
It compares FlatIP, HNSW and IVF using real MiniLM encodings of saved sample files.
The new PR targets `person_2` while that PR is unmerged; retarget to main after
the dependency merges. The older Person 4 PR #6 is a separate superseded proposal.

## Run in an isolated research environment

Use Python 3.11 from the repository root. Keep this environment separate from the
backend requirements, which constrain NumPy and sentence-transformers differently.

```powershell
py -3.11 -m venv data/vector_store/benchmark-venv
.\data\vector_store\benchmark-venv\Scripts\python.exe -m pip install -r results/requirements-benchmark.lock.txt
.\data\vector_store\benchmark-venv\Scripts\python.exe -m pip check
.\data\vector_store\benchmark-venv\Scripts\python.exe -m pytest -c benchmark_tests/pytest.ini benchmark_tests -v
.\data\vector_store\benchmark-venv\Scripts\python.exe -m src.benchmark
```

`requirements-benchmark.txt` lists direct pins; the lock captures the tested
Windows/Python 3.11 environment. Other platforms need their own validation.
The first model load may require access to Hugging Face.

## Random default, explicit replay

Every invocation without `--seed` generates a fresh random 32-bit seed using
`secrets.randbits`. It prints that seed and writes it to
`results/benchmark_metadata.json`. It controls corpus/query selection and query
ordering, plus NumPy/Torch RNGs. Supply the recorded seed to replay:

```powershell
python -m src.benchmark --seed <recorded-seed> --output data/vector_store/replay
```

The IVF clustering seed is derived from the low 31 bits of the run seed to fit
FAISS's signed integer interface and is recorded separately. There is no fixed
default workload or IVF clustering seed. Repeat runs with the same seed reproduce text selection and recall
on the tested environment; timings vary with hardware and system load.

## Sample files and measurements

The runner reads `data/sample_documents.txt`, Person 2's TXT/Markdown samples in
`data/documents`, and the 20 additional Markdown documents in
`data/benchmark_samples/documents`. The new documents contain 10,000 fictional
practice scenarios across 20 topics. They are generated fixtures, explicitly
not production documents or a human-labelled relevance dataset. Inspect or share
them directly; generation is a separate maintenance command,
`python -m src.create_benchmark_samples`, never part of a benchmark run.

Text is split paragraph-by-paragraph using `src.chunking.chunk_text` (500-character
chunks, 50 overlap), deduplicated, shuffled and sampled into nested sets of 500,
2,000 and 10,000 chunks. The original files are part of the candidate pool; random
sampling does not guarantee every file is represented at every size.
Queries are read from `data/benchmark_samples/queries.jsonl`, which contains
2,000 separately worded prompts; 120 are selected per run. Exact duplicates and
query/corpus overlaps are rejected. No vectors are copied or perturbed to scale.

MiniLM revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41` runs on CPU and produces
normalized float32 vectors with 384 dimensions. Cache identity includes revision,
embedding-library versions and text hashes. Shape, normalization and checksum
validation rejects corrupt caches. Use `--refresh-cache` to re-encode.

Each configuration uses three builds, ten warmup queries, then 120 shuffled
single-query searches with one FAISS thread. FlatIP supplies exact top-five ground
truth. HNSW uses M=32, efConstruction=40, efSearch=16; IVF uses nlist=16/nprobe=4.
IVF build time includes training and insertion. Search excludes embedding,
network and generation. Serialized memory is bytes / 1024 squared (MiB).

## Outputs and limits

Recorded run seed: **4079965474**. At 10,000 vectors:

| Index | Build ms | Mean search ms | Recall@5 | MiB |
|---|---:|---:|---:|---:|
| Flat | 9.461 | 1.9815 | 1.0000 | 14.648 |
| HNSW | 1000.261 | 0.0570 | 0.9233 | 17.240 |
| IVF | 59.170 | 0.4110 | 1.0000 | 14.748 |

HNSW trades accuracy, memory and build time for lower search latency. Flat builds
fastest and guarantees exact neighbours. IVF is intermediate in latency on this
sample; its 1.0 recall at 10,000 does not generalize to all datasets or queries.

- `benchmark_results.csv`: nine summaries with required columns, p99 and query count.
- `benchmark_queries.csv`: 3,240 individual timings (120 queries reused across repetitions).
- `benchmark_trials.csv`: 27 build/recall/memory records.
- `benchmark_metadata.json`: run seed, file/source hashes, text/embedding hashes,
  machine/package details and exact-neighbour boundary ties.
- The console prints progress and a Markdown comparison table.

Text/source file hashes normalize newlines to UTF-8/LF for cross-checkout checks.
`git_commit` is HEAD at run time; source hashes identify pre-commit code precisely.
The assigned 500-vector IVF case retains the FAISS warning recommending at least
624 training samples. Small sample sizes limit tail-percentile interpretation.
Recall is agreement with exact vector neighbours, not answer relevance. IVF can
achieve perfect recall for particular queries without being an exact algorithm.

The benchmark is independent of Chroma ingestion and does not validate a live
Gemini response or real OCR installation. Additional backend tests use disposable
SQL and controlled vector/generation fixtures. See `results/document_validation.md`
for the actual checks, failures and limitations on this branch.

External pre-chunked JSONL corpus/query pairs are supported with `--corpus` and
`--queries`. Both require nonempty `{"text":"..."}` records and enough unique
records for the requested sizes. In this mode no default samples are added.
