# Optimizing Vector Database Indexing Strategies for Low-Latency Retrieval-Augmented Generation (RAG)

## Objective

This project investigates different vector database indexing strategies to improve retrieval speed in Retrieval-Augmented Generation (RAG) systems. As knowledge bases scale from thousands to millions of vectors, retrieval — not just LLM inference — becomes a major latency bottleneck. This project benchmarks common indexing strategies to identify the right trade-off between speed, accuracy, memory, and build time for different deployment scenarios.

## Motivation

- RAG latency is increasingly dominated by the retrieval step as corpus size grows.
- Flat indexing guarantees perfect recall but scales linearly with corpus size, making it impractical at large scale.
- Approximate Nearest Neighbor (ANN) methods like HNSW and IVF trade a small amount of recall for large latency gains — but the right trade-off point depends on dataset size, dimensionality, and query patterns.
- Choosing the wrong index can silently degrade RAG answer quality (via poor recall) or make an application unusably slow.

## Indexing Strategies

| Strategy | Description |
|---|---|
| **Flat / Brute Force** | Exhaustive search over all vectors. Guarantees perfect recall; latency scales linearly with corpus size. |
| **HNSW** | Hierarchical Navigable Small World graph-based ANN index. Fast approximate search with strong recall, higher memory usage. |
| **IVF** | Inverted File Index. Clusters vectors and searches only relevant clusters (`nprobe`), trading recall for speed and lower memory. |

## Evaluation Metrics

- **Retrieval latency** — average and p95/p99 query response time
- **Recall@K** — proportion of true top-K nearest neighbors (from exhaustive Flat search) retrieved
- **Indexing time** — time to build/populate each index
- **Memory usage** — RAM footprint of each index at rest

## Approach

1. **Data preparation** — Load a representative document set, chunk it, and generate embeddings using a consistent embedding model so indexing strategy is the only variable under test.
2. **Index construction** — Build Flat, HNSW, and IVF indexes over the same embedded corpus, varying key hyperparameters (e.g., `M` / `efConstruction` for HNSW, `nlist` / `nprobe` for IVF).
3. **Benchmarking** — Run a fixed query set against each index and record latency, recall, indexing time, and memory usage.
4. **Analysis** — Compare strategies across corpus sizes (small / medium / large) to identify inflection points where one strategy outperforms another.

## Project Structure

```
data/       - Sample documents and datasets
src/        - Implementation code
results/    - Benchmark results
```

## Deliverables

- Reproducible benchmark suite (`src/`) for running indexing and retrieval experiments
- Benchmark results and comparison plots (`results/`) across strategies and corpus sizes
- A findings report summarizing the recommended indexing strategy by use case (e.g., low-latency chatbot vs. high-recall research assistant)

## Expected Outcome

A practical, data-backed guide for selecting a vector indexing strategy in RAG systems — clarifying when the recall guarantees of Flat search are worth the latency cost, and when HNSW or IVF's approximate search is the better engineering trade-off.
