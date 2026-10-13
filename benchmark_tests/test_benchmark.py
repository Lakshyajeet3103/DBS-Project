import numpy as np
import pytest
import faiss
from src.benchmark import recall_at_k, validate_embeddings, load_embeddings
from src.benchmark_data import make_workload
from src.vector_index import create_flat_index, create_hnsw_index, create_ivf_index


def test_recall_ignores_order_and_missing_neighbours():
    assert recall_at_k(np.array([[3, 2, -1, -1, -1]]), np.array([[1, 2, 3, 4, 5]])) == .4
    with pytest.raises(ValueError):
        recall_at_k(np.array([[1]]), np.array([[1, 2]]))


def test_workload_is_unique_reproducible_and_queries_are_disjoint():
    a, q = make_workload(seed=17)
    assert len(a) == len(set(a)) == 10000
    assert len(q) == len(set(q)) == 120
    assert not set(a) & set(q)
    assert (a, q) == make_workload(seed=17)


def test_saved_documents_replay_and_seed_changes_selection():
    from src.sample_documents import load_sample_workload
    a, q, manifest, count = load_sample_workload(10000, 120, 1)
    assert len(a) == len(set(a)) == 10000
    assert len(q) == len(set(q)) == 120
    assert not set(a) & set(q)
    assert count >= 10000
    assert any(item['path'] == 'data/documents/senior/leadership-strategy.md' for item in manifest)
    assert (a, q, manifest, count) == load_sample_workload(10000, 120, 1)
    assert (a, q) != load_sample_workload(10000, 120, 2)[:2]


def test_index_builders_use_cosine_equivalent_inner_product():
    faiss.omp_set_num_threads(1)
    x = np.random.default_rng(17).normal(size=(640, 32)).astype('float32')
    faiss.normalize_L2(x)
    query = x[[12, 45, 200]]
    for builder in (create_flat_index, create_hnsw_index, lambda x: create_ivf_index(x, 16)):
        index = builder(x)
        assert index.metric_type == faiss.METRIC_INNER_PRODUCT
        if isinstance(index, faiss.IndexIVFFlat):
            index.nprobe = 4
        scores, ids = index.search(query, 1)
        np.testing.assert_array_equal(ids[:, 0], [12, 45, 200])
        np.testing.assert_allclose(scores, 1, atol=1e-5)


def test_index_configuration_is_explicit():
    x = np.random.default_rng(1).normal(size=(640, 32)).astype('float32')
    faiss.normalize_L2(x)
    hnsw = create_hnsw_index(x, M=32, ef_construction=55, ef_search=24)
    assert hnsw.hnsw.efConstruction == 55
    assert hnsw.hnsw.efSearch == 24
    ivf = create_ivf_index(x, nlist=16, nprobe=4, seed=17)
    assert ivf.nlist == 16 and ivf.nprobe == 4 and ivf.cp.seed == 17


@pytest.mark.parametrize('fault', ['rows', 'dimensions', 'dtype', 'nan', 'normalization'])
def test_rejects_invalid_cached_embeddings(fault):
    x = np.zeros((2, 384), dtype='float32')
    x[:, 0] = 1
    q = x[:1].copy()
    if fault == 'rows':
        x = x[:1]
    elif fault == 'dimensions':
        x = x[:, :32]
    elif fault == 'dtype':
        x = x.astype('float64')
    elif fault == 'nan':
        x[0, 0] = np.nan
    else:
        x[0, 0] = 2
    with pytest.raises(ValueError):
        validate_embeddings(x, q, 2, 1)


def test_cache_invalidates_on_revision_and_detects_tampering(tmp_path, monkeypatch):
    from src import benchmark
    calls = []

    def encode(texts, **kwargs):
        calls.append(kwargs)
        x = np.zeros((len(texts), 384), dtype='float32')
        x[:, 0] = 1
        return x

    monkeypatch.setattr(benchmark, 'generate_embeddings', encode)
    load_embeddings(['a', 'b'], ['q'], tmp_path)
    load_embeddings(['a', 'b'], ['q'], tmp_path)
    assert len(calls) == 1
    cache_file = next(tmp_path.glob('*.npz'))
    with np.load(cache_file) as saved:
        x, q = saved['corpus'], saved['queries']
    x[0] = 0
    x[0, 1] = 1  # Still normalized: only the content checksum can detect this.
    np.savez_compressed(cache_file, corpus=x, queries=q)
    with pytest.raises(ValueError, match='checksum'):
        load_embeddings(['a', 'b'], ['q'], tmp_path)
    load_embeddings(['a', 'b'], ['q'], tmp_path, refresh=True)
    monkeypatch.setattr(benchmark, 'MODEL_REVISION', 'different-revision')
    load_embeddings(['a', 'b'], ['q'], tmp_path)
    assert len(calls) == 3
    assert calls[-1] == {'revision': 'different-revision', 'device': 'cpu'}
    original_version = benchmark.importlib.metadata.version
    monkeypatch.setattr(benchmark.importlib.metadata, 'version',
                        lambda name: 'changed-version' if name == 'torch' else original_version(name))
    load_embeddings(['a', 'b'], ['q'], tmp_path)
    assert len(calls) == 4


def test_benchmark_suite_does_not_import_backend():
    import sys
    assert 'database.connection' not in sys.modules
    assert 'main' not in sys.modules


def test_runner_outputs_match_raw_measurements(tmp_path, monkeypatch):
    import argparse
    import csv
    import json
    from src import benchmark

    corpus_path, queries_path = tmp_path/'corpus.jsonl', tmp_path/'queries.jsonl'
    corpus_path.write_text('\n'.join(json.dumps({'text': f'document {i}'}) for i in range(640)), encoding='utf-8')
    queries_path.write_text('\n'.join(json.dumps({'text': f'question {i}'}) for i in range(100)), encoding='utf-8')

    def encode(texts, **kwargs):
        x = np.random.default_rng(19).normal(size=(len(texts), 384)).astype('float32')
        faiss.normalize_L2(x)
        return x

    original_loader = benchmark.load_embeddings
    monkeypatch.setattr(benchmark, 'generate_embeddings', encode)
    monkeypatch.setattr(benchmark, 'load_embeddings',
                        lambda corpus, queries, cache, **kwargs:
                        original_loader(corpus, queries, tmp_path/'cache', **kwargs))
    output = tmp_path/'results'
    benchmark.run_benchmarks(argparse.Namespace(
        sizes=[640], queries_count=100, seed=None, threads=1, repeats=2,
        corpus=corpus_path, queries=queries_path, output=output, refresh_cache=False))
    with (output/'benchmark_results.csv').open() as handle:
        rows = list(csv.DictReader(handle))
    with (output/'benchmark_queries.csv').open() as handle:
        raw = list(csv.DictReader(handle))
    with (output/'benchmark_trials.csv').open() as handle:
        trials = list(csv.DictReader(handle))
    assert len(rows) == 3 and len(raw) == 600 and len(trials) == 6
    for row in rows:
        times = [float(r['Latency_ms']) for r in raw if r['Index'] == row['Index']]
        assert float(row['Search_Latency_ms']) == pytest.approx(np.mean(times))
        assert float(row['P95_Latency_ms']) == pytest.approx(np.percentile(times, 95))
        assert float(row['P99_Latency_ms']) == pytest.approx(np.percentile(times, 99))
        for field in ('Indexing_Time_ms', 'Memory_MB', 'Recall_at_K'):
            values = [float(t[field]) for t in trials if t['Index'] == row['Index']]
            assert float(row[field]) == pytest.approx(np.mean(values))
    assert float(rows[0]['Recall_at_K']) == 1
    metadata = json.loads((output/'benchmark_metadata.json').read_text())
    assert metadata['input_files'] == []
    assert metadata['embedding_device'] == 'cpu'
    assert isinstance(metadata['seed'], int) and 0 <= metadata['seed'] <= 2**32 - 1
    assert metadata['model_cache_provenance']['provenance']['revision'] == benchmark.MODEL_REVISION
