"""Reproducible FAISS benchmark. Run: python -m src.benchmark.

Default data is explicitly synthetic; use --corpus/--queries JSONL files with
one {"text": ...} record per line for a more representative independent dataset.
"""
import argparse
import csv
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import time
from datetime import datetime, timezone

import faiss
import numpy as np
import psutil

from src.benchmark_data import make_workload
from src.chunking import load_document, chunk_text
from src.embeddings import generate_embeddings, MODEL_NAME
from src.vector_index import create_flat_index, create_hnsw_index, create_ivf_index

ROOT = Path(__file__).resolve().parents[1]
MODEL_REVISION = '1110a243fdf4706b3f48f1d95db1a4f5529b4d41'
EMBEDDING_PACKAGES = ('numpy', 'sentence-transformers', 'torch', 'transformers',
                      'tokenizers', 'huggingface-hub')
FIELDS = ['Index', 'Corpus_Size', 'Indexing_Time_ms', 'Search_Latency_ms',
          'P95_Latency_ms', 'Recall_at_K', 'Memory_MB', 'P99_Latency_ms', 'Query_Count']


def digest(texts):
    return hashlib.sha256(json.dumps(texts, ensure_ascii=False).encode()).hexdigest()


def recall_at_k(actual, expected):
    if actual.shape != expected.shape or actual.ndim != 2 or actual.shape[1] == 0:
        raise ValueError('Expected equally shaped, nonempty top-k arrays')
    return float(np.mean([len(set(a[a >= 0]) & set(b[b >= 0])) / len(b)
                          for a, b in zip(actual, expected)]))


def load_jsonl(path):
    return [json.loads(line)['text'] for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


def validate_embeddings(vectors, query_vectors, corpus_count, query_count):
    for matrix, count in ((vectors, corpus_count), (query_vectors, query_count)):
        if matrix.shape != (count, 384):
            raise ValueError(f'Expected embedding shape {(count, 384)}, got {matrix.shape}')
        if matrix.dtype != np.float32 or not np.isfinite(matrix).all():
            raise ValueError('Embeddings must be finite float32')
        if not np.allclose(np.linalg.norm(matrix, axis=1), 1, atol=1e-5):
            raise ValueError('Embeddings must be normalized')


def embedding_digest(vectors, query_vectors):
    return hashlib.sha256(vectors.tobytes()+query_vectors.tobytes()).hexdigest()


def load_embeddings(corpus, queries, cache, *, refresh=False):
    provenance = dict(schema=2, model=MODEL_NAME, revision=MODEL_REVISION,
                      device='cpu', dimension=384, normalize_embeddings=True,
                      corpus_sha256=digest(corpus), queries_sha256=digest(queries),
                      versions={p: importlib.metadata.version(p) for p in EMBEDDING_PACKAGES})
    key = digest(provenance)
    cache.mkdir(parents=True, exist_ok=True)
    cache_file = cache / f'{key}.npz'
    manifest_file = cache_file.with_suffix('.json')
    if cache_file.exists() and not refresh:
        if not manifest_file.exists():
            raise ValueError('Embedding cache manifest missing; rerun with --refresh-cache')
        manifest = json.loads(manifest_file.read_text(encoding='utf-8'))
        if manifest.get('provenance') != provenance:
            raise ValueError('Embedding cache provenance mismatch; rerun with --refresh-cache')
        with np.load(cache_file, allow_pickle=False) as saved:
            vectors, query_vectors = saved['corpus'], saved['queries']
        validate_embeddings(vectors, query_vectors, len(corpus), len(queries))
        if manifest.get('embedding_sha256') != embedding_digest(vectors, query_vectors):
            raise ValueError('Embedding cache checksum mismatch; rerun with --refresh-cache')
        print(f'Loaded validated MiniLM embeddings: {cache_file.name}', flush=True)
    else:
        print(f'Embedding {len(corpus)} corpus texts and {len(queries)} query texts '
              f'with {MODEL_NAME}@{MODEL_REVISION} on CPU', flush=True)
        all_vectors = generate_embeddings(corpus + queries, revision=MODEL_REVISION, device='cpu')
        vectors, query_vectors = all_vectors[:len(corpus)], all_vectors[len(corpus):]
        validate_embeddings(vectors, query_vectors, len(corpus), len(queries))
        manifest = dict(provenance=provenance, embedding_sha256=embedding_digest(vectors, query_vectors))
        np.savez_compressed(cache_file, corpus=vectors, queries=query_vectors)
        manifest_file.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    return vectors, query_vectors, manifest


def run_benchmarks(args):
    if args.queries_count < 100:
        raise ValueError('At least 100 queries are required')
    if args.threads < 1 or args.repeats < 1:
        raise ValueError('threads and repeats must be positive')
    faiss.omp_set_num_threads(args.threads)
    np.random.seed(args.seed)
    import torch
    torch.manual_seed(args.seed)
    torch.set_num_threads(args.threads)
    sample_chunks = []
    if bool(args.corpus) != bool(args.queries):
        raise ValueError('--corpus and --queries must be supplied together')
    if args.corpus:
        corpus, queries = load_jsonl(args.corpus), load_jsonl(args.queries)
        method = 'External JSONL text; provenance must be supplied by dataset owner'
    else:
        sample_chunks = chunk_text(load_document(ROOT / 'data/sample_documents.txt'))
        corpus, queries = make_workload(10000, args.queries_count, args.seed)
        # Preserve the assignment sample as part of the measured corpus.
        corpus = sample_chunks + corpus
        method = ('Sample chunks plus unique fictional template combinations; no vector replication '
                  'or perturbation. Queries are separately worded from the same template distribution. '
                  'Not representative of production traffic or a human-labelled relevance benchmark.')
    corpus = corpus[:max(args.sizes)]
    queries = queries[:args.queries_count]
    if any(not isinstance(text, str) or not text.strip() for text in corpus + queries):
        raise ValueError('Corpus and queries must contain nonempty strings')
    if len(corpus) < max(args.sizes) or len(queries) < args.queries_count:
        raise ValueError('Insufficient corpus or query records')
    if len(set(corpus)) != len(corpus) or len(set(queries)) != len(queries) or set(corpus) & set(queries):
        raise ValueError('Duplicate corpus/query text or exact query/corpus overlap')
    if any(n < 16 for n in args.sizes):
        raise ValueError('IVF16 requires at least 16 training vectors')
    args.output.mkdir(parents=True, exist_ok=True)
    corpus_hash, query_hash = digest(corpus), digest(queries)
    # Cache identity includes immutable model revision and embedding library versions.
    cache = ROOT / 'data/vector_store/person4'
    vectors, query_vectors, cache_manifest = load_embeddings(corpus, queries, cache, refresh=args.refresh_cache)
    versions = {p: importlib.metadata.version(p) for p in
                ['faiss-cpu', 'numpy', 'sentence-transformers', 'torch', 'transformers', 'psutil']}
    metadata = dict(timestamp_utc=datetime.now(timezone.utc).isoformat(), seed=args.seed,
                    python=platform.python_version(), platform=platform.platform(),
                    cpu=platform.processor(), logical_cpus=os.cpu_count(),
                    physical_cpus=psutil.cpu_count(logical=False), ram_bytes=psutil.virtual_memory().total,
                    versions=versions, model=MODEL_NAME, model_cache_provenance=cache_manifest,
                    dimension=int(vectors.shape[1]),
                    faiss_threads=args.threads, embedding_device='cpu',
                    dataset_method=method, corpus_sha256=corpus_hash, queries_sha256=query_hash,
                    embedding_sha256=embedding_digest(vectors, query_vectors),
                    sample_chunk_count=len(sample_chunks), query_count=len(queries), repeats=args.repeats,
                    sizes=args.sizes, k=5, hnsw={'M':32, 'efConstruction':40, 'efSearch':16},
                    ivf={'nlist':16, 'nprobe':4, 'training':'indexed corpus only; FAISS may subsample to 256*nlist vectors', 'seed':1234},
                    timing='perf_counter_ns, serial single-query search, 10 warmups, no embedding/LLM/network time',
                    memory='serialized bytes / 2**20 (MiB), not process RAM',
                    limitations=['Synthetic template distribution; near-duplicates possible',
                                 'Recall is neighbour agreement, not human relevance',
                                 'P99 is based on a small query sample; inspect raw timings',
                                 '500-vector IVF training is below FAISS recommended 39*nlist=624 samples',
                                 'One machine; timings can vary with scheduling and thermal state'])
    try:
        metadata['git_commit'] = subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        metadata['git_commit'] = None
    metadata['source_sha256'] = {
        name: hashlib.sha256((ROOT/name).read_text(encoding='utf-8').encode('utf-8')).hexdigest()
        for name in ('src/benchmark.py', 'src/benchmark_data.py', 'src/embeddings.py',
                     'src/chunking.py', 'src/vector_index.py', 'requirements-benchmark.txt',
                     'results/requirements-benchmark.lock.txt')}
    rows, raw, trials = [], [], []
    metadata['ground_truth_boundary_ties'] = {}
    for n in args.sizes:
        x = np.ascontiguousarray(vectors[:n])
        exact_scores, exact_ids = create_flat_index(x).search(query_vectors, 6)
        truth = exact_ids[:,:5]
        metadata['ground_truth_boundary_ties'][str(n)] = int(np.sum(exact_scores[:,4] == exact_scores[:,5]))
        for label, builder in [('Flat', create_flat_index),
                               ('HNSW', lambda v: create_hnsw_index(v, M=32, ef_construction=40, ef_search=16)),
                               ('IVF', lambda v: create_ivf_index(v, nlist=16, nprobe=4, seed=1234))]:
            builds, elapsed, recalls, memory = [], [], [], []
            for repeat in range(args.repeats):
                start = time.perf_counter_ns()
                index = builder(x)
                builds.append((time.perf_counter_ns()-start)/1e6)
                for q in query_vectors[:10]:
                    index.search(q.reshape(1,-1), 5)
                order = np.random.default_rng(args.seed + repeat).permutation(len(queries))
                hits = np.empty_like(truth)
                for i in order:
                    start = time.perf_counter_ns()
                    _, ids = index.search(query_vectors[i:i+1], 5)
                    ms = (time.perf_counter_ns()-start)/1e6
                    hits[i] = ids[0]
                    elapsed.append(ms)
                    raw.append(dict(Index=label, Corpus_Size=n, Repeat=repeat, Query_ID=int(i), Latency_ms=ms))
                recalls.append(recall_at_k(hits, truth))
                memory.append(faiss.serialize_index(index).nbytes / (1024*1024))
                trials.append(dict(Index=label, Corpus_Size=n, Repeat=repeat,
                                   Indexing_Time_ms=builds[-1], Recall_at_K=recalls[-1], Memory_MB=memory[-1]))
                del index
            row = dict(zip(FIELDS, [label, n, float(np.mean(builds)), float(np.mean(elapsed)),
                                   float(np.percentile(elapsed,95)), float(np.mean(recalls)),
                                   float(np.mean(memory)), float(np.percentile(elapsed,99)), len(queries)]))
            rows.append(row)
            print(f'{label:5} N={n:5} build={row["Indexing_Time_ms"]:9.3f}ms mean={row["Search_Latency_ms"]:.4f}ms '
                  f'p95={row["P95_Latency_ms"]:.4f}ms p99={row["P99_Latency_ms"]:.4f}ms '
                  f'recall@5={row["Recall_at_K"]:.4f} size={row["Memory_MB"]:.3f}MiB', flush=True)
    for name, values in [('benchmark_results.csv', rows), ('benchmark_queries.csv', raw), ('benchmark_trials.csv',trials)]:
        with (args.output/name).open('w', newline='', encoding='utf-8') as handle:
            writer = csv.DictWriter(handle, fieldnames=list(values[0]))
            writer.writeheader()
            writer.writerows(values)
    (args.output/'benchmark_metadata.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    print(f'{"External JSONL" if args.corpus else "Synthetic"} workload. Timings exclude embedding '
          'and generation. See benchmark_metadata.json.', flush=True)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sizes', nargs='+', type=int, default=[500,2000,10000])
    parser.add_argument('--queries-count', type=int, default=120)
    parser.add_argument('--seed', type=int, default=20261010)
    parser.add_argument('--threads', type=int, default=1)
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--corpus', type=Path)
    parser.add_argument('--queries', type=Path)
    parser.add_argument('--output', type=Path, default=ROOT/'results')
    parser.add_argument('--refresh-cache', action='store_true', help='Re-encode texts and replace this workload cache')
    run_benchmarks(parser.parse_args())


if __name__ == '__main__':
    main()
