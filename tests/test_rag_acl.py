"""Unit tests for Task 3.2 & Task 3.3: ACL filter pushdown, prompt engineering, and source citations."""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import pytest

from services.rag_service import (
    NO_CONTEXT_REPLY,
    build_acl_filter,
    build_prompt,
    extract_unique_sources,
    is_chunk_authorized,
    query_rag,
    retrieve_authorized_chunks,
    verify_and_filter_chunks,
)


@dataclass
class FakeChunk:
    page_content: str
    metadata: Dict[str, Any]


@dataclass
class FakeAIMessage:
    content: str


class SpyLLM:
    def __init__(self, reply_text: str):
        self.reply_text = reply_text
        self.prompts: List[str] = []

    def invoke(self, prompt: str) -> FakeAIMessage:
        self.prompts.append(prompt)
        return FakeAIMessage(content=self.reply_text)


class SpyVectorDB:
    """In-memory spy replacing Chroma to verify filter pushdown and post-retrieval defense-in-depth."""

    def __init__(self, chunks_to_return: List[FakeChunk]):
        self.chunks_to_return = chunks_to_return
        self.calls: List[Dict[str, Any]] = []

    def similarity_search(self, query: str, k: int = 3, filter: Optional[Dict[str, Any]] = None) -> List[FakeChunk]:
        self.calls.append({"query": query, "k": k, "filter": filter})
        return list(self.chunks_to_return)


def test_build_acl_filter_junior():
    assert build_acl_filter("junior") == {"level": "junior"}


def test_build_acl_filter_senior():
    assert build_acl_filter("senior") == {"level": {"$in": ["junior", "senior"]}}


def test_build_acl_filter_with_document_scope_junior():
    assert build_acl_filter("junior", document_id="team-handbook") == {
        "$and": [
            {"level": "junior"},
            {"document_id": "team-handbook"},
        ]
    }


def test_build_acl_filter_with_document_scope_senior():
    assert build_acl_filter("senior", document_id="leadership-strategy") == {
        "$and": [
            {"level": {"$in": ["junior", "senior"]}},
            {"document_id": "leadership-strategy"},
        ]
    }


@pytest.mark.parametrize("bad_role", ["", "guest", "admin", "JUNIOR", None])
def test_build_acl_filter_rejects_unknown_roles(bad_role):
    with pytest.raises(PermissionError):
        build_acl_filter(bad_role)  # type: ignore[arg-type]


def test_retrieve_pushes_filter_to_vector_db():
    junior_chunk = FakeChunk(
        page_content="Onboarding checklist for new hires.",
        metadata={"document_id": "getting-started", "title": "Getting started", "level": "junior"},
    )
    spy_db = SpyVectorDB([junior_chunk])

    results = retrieve_authorized_chunks(
        query="How do I onboard?",
        user_role="junior",
        document_id="getting-started",
        k=3,
        vector_db=spy_db,
    )

    assert len(spy_db.calls) == 1
    assert spy_db.calls[0] == {
        "query": "How do I onboard?",
        "k": 3,
        "filter": {
            "$and": [
                {"level": "junior"},
                {"document_id": "getting-started"},
            ]
        },
    }
    assert results == [junior_chunk]


def test_defense_in_depth_strips_senior_and_untagged_chunks_for_junior():
    """Even if the vector DB returns a senior or untagged chunk, post-retrieval verification drops it."""
    leaked_chunks = [
        FakeChunk(
            page_content="Junior policy text",
            metadata={"document_id": "team-handbook", "title": "The team handbook", "level": "junior"},
        ),
        FakeChunk(
            page_content="Confidential 2027 M&A targets",
            metadata={"document_id": "leadership-strategy", "title": "Leadership strategy", "level": "senior"},
        ),
        FakeChunk(
            page_content="Legacy unlabelled chunk from old ingest.py",
            metadata={"source": "data/sample_document.pdf"},
        ),
    ]
    spy_db = SpyVectorDB(leaked_chunks)

    junior_results = retrieve_authorized_chunks(
        query="strategy",
        user_role="junior",
        vector_db=spy_db,
    )
    assert len(junior_results) == 1
    assert all(c.metadata.get("level") == "junior" for c in junior_results)

    # Senior receives both junior and senior chunks, but still rejects untagged chunks
    senior_results = retrieve_authorized_chunks(
        query="strategy",
        user_role="senior",
        vector_db=spy_db,
    )
    assert [c.metadata["document_id"] for c in senior_results] == [
        "team-handbook",
        "leadership-strategy",
    ]


def test_defense_in_depth_enforces_document_id_scope():
    chunks = [
        FakeChunk(
            page_content="Handbook text",
            metadata={"document_id": "team-handbook", "level": "junior"},
        ),
        FakeChunk(
            page_content="Security basics text",
            metadata={"document_id": "security-basics", "level": "junior"},
        ),
    ]
    filtered = verify_and_filter_chunks(chunks, user_role="junior", document_id="team-handbook")
    assert len(filtered) == 1
    assert filtered[0].metadata["document_id"] == "team-handbook"
    assert not is_chunk_authorized(chunks[1], user_role="junior", document_id="team-handbook")


def test_build_prompt_includes_strict_instructions_and_context():
    chunks = [
        FakeChunk(
            page_content="Core hours are 10:00 to 16:00 local time.",
            metadata={"document_id": "team-handbook", "title": "The team handbook", "level": "junior"},
        )
    ]
    prompt = build_prompt("What are core working hours?", chunks)
    assert "You are the Folio knowledge assistant." in prompt
    assert 'Say: "I cannot find this in your documents."' in prompt
    assert "Core hours are 10:00 to 16:00 local time." in prompt
    assert "What are core working hours?" in prompt
    assert prompt.endswith("Answer:")


def test_extract_unique_sources_deduplicates_preserving_order():
    chunks = [
        FakeChunk(
            page_content="Passage 1",
            metadata={"document_id": "team-handbook", "title": "The team handbook", "level": "junior"},
        ),
        FakeChunk(
            page_content="Passage 2 from same doc",
            metadata={"document_id": "team-handbook", "title": "The team handbook", "level": "junior"},
        ),
        FakeChunk(
            page_content="Passage 3 from another doc",
            metadata={"document_id": "security-basics", "title": "Security basics", "level": "junior"},
        ),
    ]
    sources = extract_unique_sources(chunks)
    assert sources == [
        {"id": "team-handbook", "title": "The team handbook"},
        {"id": "security-basics", "title": "Security basics"},
    ]


def test_query_rag_returns_grounded_reply_and_deduplicated_sources():
    chunks = [
        FakeChunk(
            page_content="Reviews happen every Friday.",
            metadata={"document_id": "project-playbook", "title": "Project playbook", "level": "junior"},
        ),
        FakeChunk(
            page_content="Use the standard review checklist.",
            metadata={"document_id": "project-playbook", "title": "Project playbook", "level": "junior"},
        ),
    ]
    spy_db = SpyVectorDB(chunks)
    spy_llm = SpyLLM("Project reviews happen every Friday using the standard checklist.")

    result = query_rag(
        query="How do project reviews work?",
        user_role="junior",
        vector_db=spy_db,
        llm=spy_llm,
    )

    assert result == {
        "reply": "Project reviews happen every Friday using the standard checklist.",
        "sources": [{"id": "project-playbook", "title": "Project playbook"}],
    }
    assert len(spy_llm.prompts) == 1
    assert "Reviews happen every Friday." in spy_llm.prompts[0]


def test_query_rag_short_circuits_when_no_authorized_chunks():
    """If only senior chunks exist and a junior queries, post-retrieval filtering leaves 0 chunks."""
    senior_only = [
        FakeChunk(
            page_content="2027 leadership expansion plan.",
            metadata={"document_id": "leadership-strategy", "title": "Leadership strategy", "level": "senior"},
        )
    ]
    spy_db = SpyVectorDB(senior_only)
    spy_llm = SpyLLM("Should never be called")

    result = query_rag(
        query="What is the 2027 leadership strategy?",
        user_role="junior",
        vector_db=spy_db,
        llm=spy_llm,
    )

    assert result == {"reply": NO_CONTEXT_REPLY, "sources": []}
    assert spy_llm.prompts == []


def test_query_rag_clears_sources_when_llm_refuses():
    """When the LLM replies that the answer is not in the documents, sources list is empty."""
    unrelated_junior = [
        FakeChunk(
            page_content="Use 2FA on all accounts.",
            metadata={"document_id": "security-basics", "title": "Security basics", "level": "junior"},
        )
    ]
    spy_db = SpyVectorDB(unrelated_junior)
    spy_llm = SpyLLM(NO_CONTEXT_REPLY)

    result = query_rag(
        query="What is the 2027 leadership strategy?",
        user_role="junior",
        vector_db=spy_db,
        llm=spy_llm,
    )

    assert result == {"reply": NO_CONTEXT_REPLY, "sources": []}


def test_senior_doc_mistagged_as_junior_in_vector_is_blocked_by_sql_registry():
    """Review Issue 1a: A Senior document incorrectly tagged 'junior' in vector metadata must never reach the model."""
    mistagged_senior_chunk = FakeChunk(
        page_content="Confidential 2027 leadership roadmap.",
        metadata={
            "document_id": "leadership-strategy",  # Senior in SQL registry!
            "title": "The road ahead: 2027 strategy",
            "level": "junior",  # Incorrectly tagged Junior in vector store
        },
    )
    spy_db = SpyVectorDB([mistagged_senior_chunk])
    spy_llm = SpyLLM("Should never be invoked")

    result = query_rag(
        query="What is the 2027 roadmap?",
        user_role="junior",
        vector_db=spy_db,
        llm=spy_llm,
    )

    assert result == {"reply": NO_CONTEXT_REPLY, "sources": []}
    assert spy_llm.prompts == []


def test_reclassified_document_in_sql_blocks_stale_junior_vector_metadata():
    """Review Issue 1b: A document reclassified to Senior in SQL remains inaccessible despite stale Junior vector metadata."""
    from database.connection import SessionLocal
    from database.models import Document

    stale_vector_chunk = FakeChunk(
        page_content="Handbook working hours policy.",
        metadata={
            "document_id": "team-handbook",
            "title": "The team handbook",
            "level": "junior",  # Stale vector metadata from before reclassification
        },
    )
    spy_db = SpyVectorDB([stale_vector_chunk])
    spy_llm = SpyLLM("Should never be invoked after reclassification")

    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == "team-handbook").first()
        assert doc is not None
        doc.level = "senior"
        db.commit()

        result = query_rag(
            query="What are the working hours?",
            user_role="junior",
            vector_db=spy_db,
            llm=spy_llm,
            db=db,
        )
        assert result == {"reply": NO_CONTEXT_REPLY, "sources": []}
        assert spy_llm.prompts == []
    finally:
        doc = db.query(Document).filter(Document.id == "team-handbook").first()
        if doc is not None:
            doc.level = "junior"
            db.commit()
        db.close()


def test_missing_or_nonexistent_document_ids_blocked_from_prompt_and_sources():
    """Review Issue 1c: Chunks with missing or nonexistent document IDs cannot enter the prompt or citations."""
    bad_chunks = [
        FakeChunk(
            page_content="Orphan chunk with no document_id",
            metadata={"title": "Orphan", "level": "junior"},
        ),
        FakeChunk(
            page_content="Blank document_id chunk",
            metadata={"document_id": "   ", "title": "Blank", "level": "junior"},
        ),
        FakeChunk(
            page_content="Deleted or nonexistent registry document",
            metadata={"document_id": "nonexistent-doc-999", "title": "Ghost Doc", "level": "junior"},
        ),
    ]
    spy_db = SpyVectorDB(bad_chunks)
    spy_llm = SpyLLM("Should never be invoked")

    result = query_rag(
        query="Tell me about orphan or ghost docs",
        user_role="junior",
        vector_db=spy_db,
        llm=spy_llm,
    )
    assert result == {"reply": NO_CONTEXT_REPLY, "sources": []}
    assert spy_llm.prompts == []

    # Direct calls to build_prompt and extract_unique_sources also strip unregistered chunks
    prompt = build_prompt("Any valid context?", bad_chunks, user_role="junior")
    assert "Orphan chunk" not in prompt
    assert "Deleted or nonexistent" not in prompt
    assert extract_unique_sources(bad_chunks, user_role="junior") == []


def test_fresh_metadata_tagged_ingestion_and_collection_alignment(tmp_path):
    """Review Issue 2 & 3: Validate shared collection resolution, fresh tagged ingestion, and PDF path."""
    import os
    import sqlite3
    import ingest
    from services.rag_service import (
        DEFAULT_COLLECTION_NAME,
        LEGACY_COLLECTION_NAME,
        build_registry_chunks,
        ingest_registry_documents,
        resolve_collection_name,
    )

    # 1. Ingestion and retrieval share the same collection configuration and sample PDF exists
    assert ingest.DEFAULT_COLLECTION_NAME == DEFAULT_COLLECTION_NAME
    assert os.path.isfile("data/sample_document.pdf")

    # 2. Fresh metadata-tagged ingestion from the SQL registry produces valid chunks for all 9 documents
    class InMemoryVectorStore:
        def __init__(self):
            self.items: List[FakeChunk] = []

        def add_texts(self, texts, metadatas, ids):
            for t, m, _id in zip(texts, metadatas, ids):
                self.items.append(FakeChunk(page_content=t, metadata=m))

        def similarity_search(self, query: str, k: int = 3, filter: Optional[Dict[str, Any]] = None):
            def matches(meta, flt):
                if not flt:
                    return True
                if "$and" in flt:
                    return all(matches(meta, sub) for sub in flt["$and"])
                for key, cond in flt.items():
                    val = meta.get(key)
                    if isinstance(cond, dict) and "$in" in cond:
                        if val not in cond["$in"]:
                            return False
                    elif val != cond:
                        return False
                return True

            pool = [c for c in self.items if matches(c.metadata, filter)]
            q_words = set(query.lower().split())
            pool.sort(key=lambda c: sum(1 for w in q_words if w in c.page_content.lower()), reverse=True)
            return pool[:k]

    store = InMemoryVectorStore()
    count = ingest_registry_documents(vector_db=store)
    assert count >= 9

    payload = build_registry_chunks()
    doc_ids = {m["document_id"] for m in payload["metadatas"]}
    assert "team-handbook" in doc_ids
    assert "leadership-strategy" in doc_ids
    assert all(
        {"document_id", "title", "level", "category", "type", "year", "chunk_index"} <= set(m.keys())
        for m in payload["metadatas"]
    )

    # Junior retrieval against freshly ingested chunks never returns senior documents
    jr_hits = retrieve_authorized_chunks("2027 strategy investment priorities", user_role="junior", k=5, vector_db=store)
    assert len(jr_hits) > 0
    assert all(h.metadata["level"] == "junior" for h in jr_hits)
    assert all(h.metadata["document_id"] != "leadership-strategy" for h in jr_hits)

    # Senior retrieval against freshly ingested chunks retrieves senior strategy document
    sr_hits = retrieve_authorized_chunks("2027 strategy investment priorities", user_role="senior", k=5, vector_db=store)
    assert any(h.metadata["document_id"] == "leadership-strategy" for h in sr_hits)

    # 3. Collection resolution detects tagged collections across both folio_knowledge_base and langchain
    db_file = tmp_path / "chroma.sqlite3"
    conn = sqlite3.connect(str(db_file))
    conn.execute("CREATE TABLE collections (id TEXT PRIMARY KEY, name TEXT)")
    conn.execute("CREATE TABLE segments (id TEXT PRIMARY KEY, collection TEXT)")
    conn.execute("CREATE TABLE embeddings (id INTEGER PRIMARY KEY, segment_id TEXT)")
    conn.execute("CREATE TABLE embedding_metadata (id INTEGER, key TEXT, string_value TEXT)")
    conn.execute("INSERT INTO collections VALUES ('c1', ?)", (LEGACY_COLLECTION_NAME,))
    conn.execute("INSERT INTO segments VALUES ('s1', 'c1')")
    conn.execute("INSERT INTO embeddings VALUES (1, 's1')")
    conn.commit()
    conn.close()

    assert resolve_collection_name(persist_directory=str(tmp_path)) == LEGACY_COLLECTION_NAME

    conn = sqlite3.connect(str(db_file))
    conn.execute("INSERT INTO collections VALUES ('c2', ?)", (DEFAULT_COLLECTION_NAME,))
    conn.execute("INSERT INTO segments VALUES ('s2', 'c2')")
    conn.execute("INSERT INTO embeddings VALUES (2, 's2')")
    conn.execute("INSERT INTO embedding_metadata VALUES (2, 'level', 'junior')")
    conn.commit()
    conn.close()

    assert resolve_collection_name(persist_directory=str(tmp_path)) == DEFAULT_COLLECTION_NAME

