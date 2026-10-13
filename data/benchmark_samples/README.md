# Fictional sample documents for Person 4

The `documents` folder contains 20 topic-based Markdown files with 500 short
practice scenarios each (10,000 distinct paragraphs in total). Topics include
incident response, database recovery, access review, backup verification,
employee onboarding, and document classification. These are generated fictional
fixtures, not real organizational policies or independent research data.

The files are materialized by `python -m src.create_benchmark_samples` and checked
into Git so teammates can inspect the exact text being embedded. The benchmark
only reads these files; it does not generate new paragraphs during a run.
`queries.jsonl` contains 2,000 separately worded prompts. Each run selects 120
using its recorded random seed. Prompts share the fictional scenario distribution.

The default corpus also reads the original `data/sample_documents.txt` and Person
2's saved TXT/Markdown files under `data/documents`. All files are hashed in the
result manifest. Paragraphs are chunked at 500 characters with 50-character
overlap, exact duplicates removed, then shuffled and selected with the run seed.
The FAISS research benchmark does not ingest these fixtures into the product's
Chroma database, assign access permissions, or claim semantic relevance accuracy.

These fixtures are deliberately stored outside `data/documents` so running the
product ingestion script does not accidentally ingest the research scenario set.
