"""Unit & integration tests for Person 2 (Tasks 2.1, 2.2, 2.3, 2.4): Multi-Format Ingestion & Tagged ChromaDB."""
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
import pytest

from database.connection import SessionLocal
from database.models import Document
from database.seed import seed_database
from ingest import (
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    REQUIRED_METADATA_KEYS,
    build_chunk_metadata,
    chunk_document_record,
    ingest_all,
    load_file_content,
    load_image_file,
    load_pdf_file,
    load_sql_registry_documents,
    load_text_or_markdown_file,
    process_and_save_pdf,
    scan_external_documents,
    split_text_into_chunks,
    verify_ingestion,
)
from services.ocr_service import SUPPORTED_IMAGE_EXTENSIONS, extract_text_from_image


@dataclass
class FakeVectorDoc:
    page_content: str
    metadata: Dict[str, Any]


class FakeChromaStore:
    """In-memory Chroma substitute supporting add_texts and metadata-filtered similarity_search."""

    def __init__(self):
        self.items: Dict[str, FakeVectorDoc] = {}

    def add_texts(
        self,
        texts: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        ids: Optional[List[str]] = None,
    ) -> List[str]:
        metas = metadatas or [{} for _ in texts]
        doc_ids = ids or [f"id_{i}" for i in range(len(texts))]
        for text, meta, cid in zip(texts, metas, doc_ids):
            self.items[cid] = FakeVectorDoc(page_content=text, metadata=dict(meta))
        return doc_ids

    def similarity_search(
        self,
        query: str,
        k: int = 5,
        filter: Optional[Dict[str, Any]] = None,
    ) -> List[FakeVectorDoc]:
        results: List[FakeVectorDoc] = []
        for doc in self.items.values():
            if filter:
                matched = True
                for key, val in filter.items():
                    if doc.metadata.get(key) != val:
                        matched = False
                        break
                if not matched:
                    continue
            results.append(doc)
        return results[:k]


# ---------------------------------------------------------------------------
# Task 2.1: Multi-Format Document Loaders & OCR Service
# ---------------------------------------------------------------------------

def test_extract_text_from_image_missing_file_returns_empty(tmp_path: Path):
    missing = tmp_path / "does_not_exist.png"
    assert extract_text_from_image(missing) == ""


def test_load_file_content_unsupported_extension_raises(tmp_path: Path):
    bad_file = tmp_path / "notes.bmp"
    bad_file.write_bytes(b"BM")
    with pytest.raises(ValueError, match="Unsupported file format"):
        load_file_content(bad_file)


def test_extract_text_from_image_graceful_when_tesseract_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """If Tesseract binary is not installed on host, extract_text_from_image returns '' without crashing."""
    from PIL import Image
    import pytesseract

    img_path = tmp_path / "scan.png"
    Image.new("RGB", (60, 30), color=(255, 255, 255)).save(img_path)

    def raise_tesseract_not_found(*args: Any, **kwargs: Any) -> str:
        raise pytesseract.TesseractNotFoundError()

    monkeypatch.setattr(pytesseract, "image_to_string", raise_tesseract_not_found)
    result = extract_text_from_image(img_path)
    assert result == ""


def test_extract_text_from_image_with_mocked_tesseract(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from PIL import Image
    import pytesseract

    img_path = tmp_path / "diagram.jpg"
    Image.new("RGB", (60, 30), color=(255, 255, 255)).save(img_path)

    monkeypatch.setattr(pytesseract, "image_to_string", lambda img: "  Extracted OCR Architecture Notes  \n")
    assert load_image_file(img_path) == "Extracted OCR Architecture Notes"
    assert load_file_content(img_path) == "Extracted OCR Architecture Notes"


def test_load_text_and_markdown_files(tmp_path: Path):
    txt_file = tmp_path / "readme.txt"
    md_file = tmp_path / "guide.md"
    txt_file.write_text("Plain text onboarding policy.", encoding="utf-8")
    md_file.write_text("# Markdown Heading\n\nDetailed runbook.", encoding="utf-8")

    assert load_text_or_markdown_file(txt_file) == "Plain text onboarding policy."
    assert load_file_content(txt_file) == "Plain text onboarding policy."
    assert load_file_content(md_file) == "# Markdown Heading\n\nDetailed runbook."


def test_load_pdf_file_extracts_sample_document():
    assert Path("data/sample_document.pdf").is_file()
    content = load_pdf_file("data/sample_document.pdf")
    assert isinstance(content, str)
    assert len(content) > 50


def test_load_sql_registry_documents_returns_seeded_records():
    seed_database()
    docs = load_sql_registry_documents()
    assert len(docs) >= 9
    doc_ids = {d.id for d in docs}
    assert "getting-started" in doc_ids
    assert "leadership-strategy" in doc_ids


# ---------------------------------------------------------------------------
# Task 2.2: Text Splitting & Strict Metadata Injection
# ---------------------------------------------------------------------------

def test_split_text_into_chunks_respects_size_and_overlap():
    long_text = ("Folio engineering handbook paragraph with security policies. " * 40).strip()
    chunks = split_text_into_chunks(long_text, chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    assert len(chunks) >= 3
    assert all(len(c) <= CHUNK_SIZE for c in chunks)


def test_build_chunk_metadata_enforces_schema():
    meta = build_chunk_metadata(
        document_id="team-handbook",
        title="The team handbook",
        level="JUNIOR",
        category="People & culture",
        doc_type="Policy",
        year=2026,
        chunk_index=0,
    )
    assert set(meta.keys()) == REQUIRED_METADATA_KEYS
    assert meta == {
        "document_id": "team-handbook",
        "title": "The team handbook",
        "level": "junior",
        "category": "People & culture",
        "type": "Policy",
        "year": "2026",
        "chunk_index": 0,
    }


def test_build_chunk_metadata_rejects_invalid_level_or_empty_doc_id():
    with pytest.raises(ValueError, match="level"):
        build_chunk_metadata("team-handbook", "Title", "intern", "Cat", "Policy", "2026", 0)
    with pytest.raises(ValueError, match="document_id"):
        build_chunk_metadata("   ", "Title", "junior", "Cat", "Policy", "2026", 0)


def test_chunk_document_record_builds_deterministic_ids_and_metadata():
    doc = Document(
        id="leadership-strategy",
        title="2026 strategic priorities & M&A roadmap",
        category="Strategy",
        level="senior",
        type="Strategy",
        year="2026",
        date="2026-10-01",
        minutes=8,
        author="Leadership",
        description="Confidential strategy.",
        content=("Strategic M&A target evaluation and executive capital allocation. " * 30).strip(),
    )
    texts, metas, ids = chunk_document_record(doc)
    assert len(texts) == len(metas) == len(ids) >= 2
    for idx, (meta, cid) in enumerate(zip(metas, ids)):
        assert cid == f"leadership-strategy_chunk_{idx}"
        assert set(meta.keys()) == REQUIRED_METADATA_KEYS
        assert meta["document_id"] == "leadership-strategy"
        assert meta["level"] == "senior"
        assert meta["year"] == "2026"
        assert meta["chunk_index"] == idx


# ---------------------------------------------------------------------------
# Task 2.3 & 2.4: External Directory Scan, Idempotent Ingestion & Verification
# ---------------------------------------------------------------------------

def test_scan_external_documents_tags_files_from_data_documents():
    seed_database()
    texts, metas, ids = scan_external_documents("data/documents")
    assert len(texts) >= 2
    for meta, cid in zip(metas, ids):
        assert set(meta.keys()) == REQUIRED_METADATA_KEYS
        assert meta["level"] in ("junior", "senior")
        assert cid.startswith(f"{meta['document_id']}_chunk_")


def test_ingest_all_and_verify_ingestion_with_fake_chroma(monkeypatch: pytest.MonkeyPatch):
    seed_database()
    fake_store = FakeChromaStore()

    monkeypatch.setattr("ingest.get_vector_db", lambda *args, **kwargs: fake_store)

    summary = ingest_all(run_verification=True)
    assert summary["collection_name"] == "folio_knowledge_base"
    assert summary["total_chunks"] >= 9
    assert len(fake_store.items) >= 9

    # Verify idempotent deterministic IDs on re-ingestion
    count_after_first = len(fake_store.items)
    ingest_all(run_verification=True)
    assert len(fake_store.items) == count_after_first

    # Confirm every stored vector has all 7 required metadata keys
    for doc in fake_store.items.values():
        assert set(doc.metadata.keys()) == REQUIRED_METADATA_KEYS
        assert doc.metadata["level"] in ("junior", "senior")


def test_verify_ingestion_detects_senior_leak_in_junior_filter():
    leaky_store = FakeChromaStore()
    leaky_store.items["bad"] = FakeVectorDoc(
        page_content="Leaked senior chunk",
        metadata={"document_id": "leadership-strategy", "level": "senior"},
    )

    class BrokenFilterStore:
        def similarity_search(self, query: str, k: int = 5, filter: Optional[Dict[str, Any]] = None):
            # Simulates a store that ignores filter={"level": "junior"} and returns a senior chunk
            return [leaky_store.items["bad"]]

    with pytest.raises(AssertionError, match="leaked"):
        verify_ingestion(vector_db=BrokenFilterStore())


def test_persisted_chroma_has_folio_knowledge_base_with_acl_metadata():
    """Verify the persisted ./chroma store contains folio_knowledge_base with tagged chunks."""
    import sqlite3
    from services.rag_service import resolve_collection_name

    assert resolve_collection_name("./chroma") == "folio_knowledge_base"
    conn = sqlite3.connect("./chroma/chroma.sqlite3")
    try:
        collections = {row[0] for row in conn.execute("SELECT name FROM collections").fetchall()}
        assert collections == {"folio_knowledge_base"}

        rows = conn.execute(
            """
            SELECT e.embedding_id, em.key, COALESCE(em.string_value, CAST(em.int_value AS TEXT))
            FROM collections c
            JOIN segments s ON s.collection = c.id
            JOIN embeddings e ON e.segment_id = s.id
            JOIN embedding_metadata em ON em.id = e.id
            WHERE c.name = 'folio_knowledge_base'
            """
        ).fetchall()
        by_chunk: Dict[str, Dict[str, str]] = {}
        for emb_id, key, val in rows:
            by_chunk.setdefault(emb_id, {})[key] = val

        assert len(by_chunk) >= 9
        for emb_id, meta in by_chunk.items():
            assert REQUIRED_METADATA_KEYS.issubset(set(meta.keys())), f"Missing keys on {emb_id}: {meta}"
            assert meta["level"] in ("junior", "senior")
    finally:
        conn.close()

