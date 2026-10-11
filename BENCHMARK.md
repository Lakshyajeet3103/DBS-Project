# Person 4: FAISS indexing benchmark

This standalone research track compares exact FlatIP, HNSW and IVF search using
normalized 384-dimensional `all-MiniLM-L6-v2` embeddings. It does not run the
backend, Chroma, Gemini, or API security acceptance tests.

## Reproduce on Windows / Python 3.11

Run from the repository root. Keep this environment separate from the backend:
its NumPy and sentence-transformers requirements have different version ranges.

```powershell
py -3.11 -m venv data/vector_store/benchmark-venv
.\data\vector_store\benchmark-venv\Scripts\python.exe -m pip install -r results/requirements-benchmark.lock.txt
.\data\vector_store\benchmark-venv\Scripts\python.exe -m pip check
.\data\vector_store\benchmark-venv\Scripts\python.exe -m pytest -c benchmark_tests/pytest.ini benchmark_tests -v
.\data\vector_store\benchmark-venv\Scripts\python.exe -m src.benchmark
```

`requirements-benchmark.txt` records direct dependencies. The lock file records
the complete isolated Windows/Python 3.11 environment used for the published run.
Other platforms may resolve different platform dependencies and require their own
validation. The first model load may need internet access to Hugging Face.

The benchmark tests have their own pytest configuration and directory; they do
not load `tests/conftest.py` or seed the backend database. They cover actual FAISS
builders, cache corruption/invalidation, embedding validation, recall, and CSV
aggregation. The runner test substitutes deterministic vectors for MiniLM to run
without a model download; the published benchmark uses real MiniLM embeddings.

## Method

- Corpus sizes: 500, 2,000 and 10,000 nested records. Eight chunks from
  `data/sample_documents.txt` are followed by unique fictional template texts.
  Vectors are encoded from text, not copied or randomly perturbed.
- 120 unique, separately worded queries from the same synthetic distribution;
  exact query/corpus overlap is rejected. This is not a human-labelled relevance
  dataset or a sample of production traffic.
- Three index builds per configuration, ten warmup queries per build, followed by
  shuffled serial single-query searches. One FAISS thread and CPU embedding.
- FlatIP supplies exact top-five ground truth. Recall@5 is the mean set overlap
  with those five IDs. The manifest records fifth/sixth-neighbour exact score ties.
- HNSW: M=32, efConstruction=40, efSearch=16. IVF: nlist=16, nprobe=4,
  clustering seed=1234, trained on the indexed corpus. Build time includes IVF
  training and insertion. FAISS may subsample training to 256*nlist vectors.
- Search timing excludes embedding, network, generation and index construction.
  Mean/p95/p99 aggregate all 360 timed searches per configuration. Repetitions
  reuse the same 120 queries; they are not 360 distinct queries.
- `Memory_MB` uses serialized bytes divided by 1024 squared (MiB), as required
  by the assignment. It is not peak process memory.

## Reproducibility safeguards

MiniLM is pinned to revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`.
The ignored cache under `data/vector_store/person4` includes model revision,
embedding-library versions, CPU/normalization settings and text hashes in its
identity. Loaded arrays must have matching row counts, 384 columns, float32
dtype, finite normalized values and the recorded content checksum. Invalid
caches fail explicitly; use `--refresh-cache` to regenerate them. Older caches
from before this schema are not reused.

The manifest includes hardware, package versions, seeds, text/embedding hashes
and SHA-256 hashes of the benchmark sources (UTF-8 with normalized newlines).
`git_commit` identifies HEAD at execution time; source hashes identify the exact
code even when results were generated before committing. Timings will vary with
hardware, scheduling and temperature; byte-identical timing results are not a
reproducibility expectation.

## Outputs and interpretation

`results/benchmark_results.csv` contains nine summary rows, including every
assignment column plus p99 and query count. `benchmark_queries.csv` contains
3,240 raw timings; `benchmark_trials.csv` contains 27 build/recall/memory records.
`benchmark_metadata.json` describes the run.

The recorded 10,000-vector run illustrates the trade-off:

| Index | Build ms | Mean search ms | Recall@5 | Serialized MiB |
| --- | ---: | ---: | ---: | ---: |
| Flat | 5.12 | 1.1861 | 1.000 | 14.648 |
| HNSW | 932.74 | 0.0711 | 0.925 | 17.240 |
| IVF | 65.74 | 0.5998 | 1.000 | 14.748 |

HNSW searches fastest here, at the cost of recall, build time and memory. Flat
builds fastest and supplies exact neighbours. IVF is between them in search
latency; its perfect recall at this size is specific to these queries and is not
a general exact-search guarantee. At 500 vectors its recall is 0.9567.
All 12 standalone tests passed in the isolated environment, and all saved
summary values were independently checked against their raw records.

The 500-vector IVF case is deliberately retained because it is an assigned size.
FAISS warns that 624 training records are recommended for 16 centroids. Treat
this case as a small-data comparison. Tail percentiles use a modest query set.
Recall measures agreement with exact vector neighbours, not answer correctness.

To use an external dataset, supply both JSONL files (one nonempty `{"text":"..."}`
record per line), with enough unique records for the requested sizes/query count:

```powershell
python -m src.benchmark --corpus corpus.jsonl --queries queries.jsonl --output results/external
```

Document dataset provenance and split methodology separately. External inputs
are treated as already prepared retrieval records; sample chunks are not added.
