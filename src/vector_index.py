import faiss


def create_flat_index(embeddings):
    """Create an exact nearest-neighbor index."""
    dimension = embeddings.shape[1]

    index = faiss.IndexFlatIP(dimension)
    index.add(embeddings)

    return index


def create_hnsw_index(embeddings, M=32, *, ef_construction=40, ef_search=16):
    """Create an HNSW approximate nearest-neighbor index."""
    dimension = embeddings.shape[1]

    index = faiss.IndexHNSWFlat(
        dimension,
        M,
        faiss.METRIC_INNER_PRODUCT
    )

    index.hnsw.efConstruction = ef_construction
    index.hnsw.efSearch = ef_search
    index.add(embeddings)

    return index


def create_ivf_index(embeddings, nlist=4, *, nprobe=1, seed=1234):
    """Create an IVF approximate nearest-neighbor index."""
    dimension = embeddings.shape[1]

    quantizer = faiss.IndexFlatIP(dimension)

    index = faiss.IndexIVFFlat(
        quantizer,
        dimension,
        nlist,
        faiss.METRIC_INNER_PRODUCT
    )

    index.cp.seed = seed
    index.nprobe = nprobe
    index.train(embeddings)
    index.add(embeddings)

    return index
