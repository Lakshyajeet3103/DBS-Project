"""Integration tests for Task 3.4: `POST /api/chat` route, ACL scoping, and tamper resistance."""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import pytest
from fastapi.testclient import TestClient

from database.seed import seed_database
from main import app
from services import rag_service
from services.rag_service import NO_CONTEXT_REPLY

seed_database()


@dataclass
class FakeChunk:
    page_content: str
    metadata: Dict[str, Any]


@dataclass
class FakeAIMessage:
    content: str


class FilteredFakeVectorDB:
    """Simulates Chroma's `where` metadata filter so integration tests verify end-to-end chat behavior."""

    def __init__(self, corpus: List[FakeChunk]):
        self.corpus = corpus
        self.last_filter: Optional[Dict[str, Any]] = None

    def similarity_search(self, query: str, k: int = 3, filter: Optional[Dict[str, Any]] = None) -> List[FakeChunk]:
        self.last_filter = filter
        matched = [c for c in self.corpus if self._matches(c.metadata, filter)]
        return matched[:k]

    @classmethod
    def _matches(cls, meta: Dict[str, Any], flt: Optional[Dict[str, Any]]) -> bool:
        if not flt:
            return True
        if "$and" in flt:
            return all(cls._matches(meta, sub) for sub in flt["$and"])
        for key, cond in flt.items():
            val = meta.get(key)
            if isinstance(cond, dict) and "$in" in cond:
                if val not in cond["$in"]:
                    return False
            elif val != cond:
                return False
        return True


SAMPLE_CORPUS = [
    FakeChunk(
        page_content="Project reviews run every Friday with written notes.",
        metadata={"document_id": "project-playbook", "title": "Project playbook", "level": "junior"},
    ),
    FakeChunk(
        page_content="Core hours are 10:00 to 16:00 in your local timezone.",
        metadata={"document_id": "team-handbook", "title": "The team handbook", "level": "junior"},
    ),
    FakeChunk(
        page_content="2027 leadership strategy focuses on enterprise margin expansion.",
        metadata={"document_id": "leadership-strategy", "title": "Leadership strategy", "level": "senior"},
    ),
]


def _login(email: str, password: str) -> TestClient:
    client = TestClient(app)
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200
    return client


def junior_client() -> TestClient:
    return _login("junior@folio.demo", "Junior@123")


def senior_client() -> TestClient:
    return _login("senior@folio.demo", "Senior@123")


def test_chat_requires_authentication():
    res = TestClient(app).post("/api/chat", json={"message": "How do project reviews work?"})
    assert res.status_code == 401


def test_chat_rejects_empty_message():
    client = junior_client()
    res = client.post("/api/chat", json={"message": "   "})
    assert res.status_code == 422


def test_junior_forbidden_from_scoping_chat_to_senior_document():
    client = junior_client()
    res = client.post(
        "/api/chat",
        json={"message": "Summarize this document", "document_id": "leadership-strategy"},
    )
    assert res.status_code == 403


def test_chat_forbidden_for_nonexistent_document_scope():
    client = senior_client()
    res = client.post(
        "/api/chat",
        json={"message": "Summarize this document", "document_id": "nonexistent-doc"},
    )
    assert res.status_code == 403


def test_junior_chat_answers_junior_questions_and_blocks_senior_context(monkeypatch):
    fake_db = FilteredFakeVectorDB(SAMPLE_CORPUS)
    monkeypatch.setattr(rag_service, "get_vector_db", lambda: fake_db)

    def fake_llm(prompt: str) -> FakeAIMessage:
        if "enterprise margin expansion" in prompt:
            return FakeAIMessage(content="Enterprise margin expansion.")
        if "How do project reviews work?" in prompt and "Project reviews run every Friday" in prompt:
            return FakeAIMessage(content="Project reviews run every Friday with written notes.")
        return FakeAIMessage(content=NO_CONTEXT_REPLY)

    monkeypatch.setattr(rag_service, "get_chat_model", lambda: fake_llm)

    client = junior_client()

    # 1. Junior question succeeds with citation
    ok_res = client.post("/api/chat", json={"message": "How do project reviews work?"})
    assert ok_res.status_code == 200
    body = ok_res.json()
    assert body["reply"] == "Project reviews run every Friday with written notes."
    assert body["sources"] == [
        {"id": "project-playbook", "title": "Project playbook"},
        {"id": "team-handbook", "title": "The team handbook"},
    ]
    assert fake_db.last_filter == {"level": "junior"}

    # 2. Junior asking about senior strategy never receives senior chunks -> refusal & 0 senior sources
    denied_res = client.post("/api/chat", json={"message": "What is the 2027 leadership strategy?"})
    assert denied_res.status_code == 200
    denied_body = denied_res.json()
    assert denied_body["reply"] == NO_CONTEXT_REPLY
    assert denied_body["sources"] == []


def test_senior_chat_retrieves_across_junior_and_senior_documents(monkeypatch):
    fake_db = FilteredFakeVectorDB(SAMPLE_CORPUS)
    monkeypatch.setattr(rag_service, "get_vector_db", lambda: fake_db)
    monkeypatch.setattr(
        rag_service,
        "get_chat_model",
        lambda: (
            lambda prompt: FakeAIMessage(content="2027 strategy focuses on enterprise margin expansion.")
            if "enterprise margin expansion" in prompt
            else FakeAIMessage(content=NO_CONTEXT_REPLY)
        ),
    )

    client = senior_client()
    res = client.post("/api/chat", json={"message": "What is the 2027 leadership strategy?"})
    assert res.status_code == 200
    body = res.json()
    assert "enterprise margin expansion" in body["reply"]
    assert fake_db.last_filter == {"level": {"$in": ["junior", "senior"]}}
    source_ids = {s["id"] for s in body["sources"]}
    assert "leadership-strategy" in source_ids


def test_chat_ignores_spoofed_role_in_request_body_and_headers(monkeypatch):
    fake_db = FilteredFakeVectorDB(SAMPLE_CORPUS)
    monkeypatch.setattr(rag_service, "get_vector_db", lambda: fake_db)
    monkeypatch.setattr(rag_service, "get_chat_model", lambda: (lambda prompt: FakeAIMessage(content=NO_CONTEXT_REPLY)))

    client = junior_client()
    res = client.post(
        "/api/chat",
        headers={"X-User-Role": "senior"},
        json={"message": "What is the 2027 leadership strategy?", "role": "senior"},
    )
    assert res.status_code == 200
    assert fake_db.last_filter == {"level": "junior"}
    assert res.json()["sources"] == []


def test_chat_sql_registry_verification_blocks_mistagged_reclassified_and_unregistered_chunks(monkeypatch):
    """Verify POST /api/chat checks the live SQL document registry before building prompts or citations."""
    from database.connection import SessionLocal
    from database.models import Document

    adversarial_corpus = [
        # 1. Senior document incorrectly tagged 'junior' in vector metadata
        FakeChunk(
            page_content="SECRET_MISTAGGED_SENIOR_STRATEGY",
            metadata={"document_id": "leadership-strategy", "title": "Leadership strategy", "level": "junior"},
        ),
        # 2. Chunk with missing document_id
        FakeChunk(
            page_content="SECRET_MISSING_DOC_ID",
            metadata={"title": "No ID", "level": "junior"},
        ),
        # 3. Chunk with nonexistent document_id
        FakeChunk(
            page_content="SECRET_NONEXISTENT_DOC_ID",
            metadata={"document_id": "deleted-or-fake-id", "title": "Fake ID", "level": "junior"},
        ),
        # 4. Document ('brand-guide') that will be reclassified to 'senior' in SQL
        FakeChunk(
            page_content="SECRET_RECLASSIFIED_BRAND_GUIDE",
            metadata={"document_id": "brand-guide", "title": "Brand guide", "level": "junior"},
        ),
    ]

    fake_db = FilteredFakeVectorDB(adversarial_corpus)
    seen_prompts: List[str] = []

    def spy_llm(prompt: str) -> FakeAIMessage:
        seen_prompts.append(prompt)
        return FakeAIMessage(content="Leaked answer!")

    monkeypatch.setattr(rag_service, "get_vector_db", lambda: fake_db)
    monkeypatch.setattr(rag_service, "get_chat_model", lambda: spy_llm)

    db = SessionLocal()
    try:
        brand_doc = db.query(Document).filter(Document.id == "brand-guide").first()
        assert brand_doc is not None
        brand_doc.level = "senior"
        db.commit()

        client = junior_client()
        res = client.post("/api/chat", json={"message": "Tell me everything"})
        assert res.status_code == 200
        assert res.json() == {"reply": NO_CONTEXT_REPLY, "sources": []}
        assert seen_prompts == []
    finally:
        brand_doc = db.query(Document).filter(Document.id == "brand-guide").first()
        if brand_doc is not None:
            brand_doc.level = "junior"
            db.commit()
        db.close()

