"""Read saved benchmark documents; no runtime corpus synthesis or vector replication."""
import hashlib
import json
from pathlib import Path
import random

from src.chunking import chunk_text, load_document

ROOT = Path(__file__).resolve().parents[1]


def load_sample_workload(size, query_count, seed, documents_dir=None):
    folder = Path(documents_dir) if documents_dir else ROOT/'data/benchmark_samples/documents'
    paths = [ROOT/'data/sample_documents.txt']
    paths += sorted((ROOT/'data/documents').rglob('*.txt'))
    paths += sorted((ROOT/'data/documents').rglob('*.md'))
    paths += sorted(folder.glob('*.md'))
    corpus, manifest, seen = [], [], set()
    for path in paths:
        text = load_document(path)
        pieces = []
        for paragraph in text.split('\n\n'):
            if paragraph.strip().startswith('#'):
                continue
            pieces.extend(chunk_text(paragraph.strip(), chunk_size=500, overlap=50))
        for piece in pieces:
            if piece not in seen:
                corpus.append(piece)
                seen.add(piece)
        manifest.append({'path': path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path),
                         'sha256': hashlib.sha256(text.encode('utf-8')).hexdigest(), 'chunks': len(pieces)})
    query_path = folder.parent/'queries.jsonl'
    queries = [json.loads(line)['text'] for line in load_document(query_path).splitlines() if line.strip()]
    if len(corpus) < size or len(queries) < query_count:
        raise ValueError(f'Insufficient saved samples: {len(corpus)} chunks / {len(queries)} queries')
    rng = random.Random(seed)
    rng.shuffle(corpus)
    rng.shuffle(queries)
    manifest.append({'path': query_path.relative_to(ROOT).as_posix() if query_path.is_relative_to(ROOT) else str(query_path),
                     'sha256': hashlib.sha256(load_document(query_path).encode('utf-8')).hexdigest()})
    return corpus[:size], queries[:query_count], manifest, len(corpus)
