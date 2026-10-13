# Import documents

Run commands from the repository root using the backend Python environment.

1. Put PDF, TXT, Markdown, PNG, JPG or JPEG files in `data/documents/junior/`
   or `data/documents/senior/`. Use unique filenames across both folders.
2. Configure `.env` with the same database, Chroma collection and embedding
   provider used by the backend. The default Gemini provider needs
   `GEMINI_API_KEY`. Image OCR also needs the Tesseract executable installed.
3. Run `python ingest.py` and refresh the document library.

On this Windows setup, the backend interpreter is:

```powershell
$backendPython = "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe"
& $backendPython ingest.py
```

Ingestion registers new files in SQL, updates the text shown in the document
reader, and writes chunks with matching document IDs to Chroma. Existing SQL
access levels are preserved; a conflicting role folder causes an error.
Shortening a file replaces its previous chunks. Duplicate document IDs,
unassigned roles, empty files and failed OCR stop the import with an error.
The filename stem, lowercased with spaces/underscores replaced by hyphens,
is the document ID.

The sample PDF at `data/sample_document.pdf` is only a loader check during
`ingest.py`; place PDFs in the role folders to import them into the library.
Removing a source file does not delete its SQL document. Document removal must
be explicit in the registry; the next successful ingestion prunes orphan chunks.
SQL and Chroma do not share a transaction: after a partial vector-store failure,
rerun ingestion to reconcile them. Embedding failures do not trigger pruning or
commit new SQL records. Other Chroma collections are preserved.

Do not change embedding providers against an existing collection: vector
dimensions and meaning must match. Use a separate collection and rebuild when
changing embedding models.

## Tests without Gemini calls

The isolation plugin prevents the tests' seed/reset operations from touching
your working database. Test files imported directly can seed the configured DB.

```powershell
& $backendPython -m pytest -p benchmark_tests.backend_isolation tests -q -p no:cacheprovider --basetemp=data/vector_store/ingestion-tests
```

The real Chroma round-trip test uses deterministic local test embeddings, not
Gemini. OCR tests mock Tesseract; they do not prove Tesseract is installed.
