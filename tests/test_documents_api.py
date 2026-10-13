"""Task 3.1 — role-filtered document API tests."""
from fastapi.testclient import TestClient

from database.connection import SessionLocal
from database.models import Document
from database.seed import seed_database
from main import app

seed_database()

SUMMARY_KEYS = {"id", "title", "description", "category", "type", "year", "level", "date", "minutes", "author"}


def _login(email: str, password: str) -> TestClient:
    client = TestClient(app)
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200
    return client


def junior() -> TestClient:
    return _login("junior@folio.demo", "Junior@123")


def senior() -> TestClient:
    return _login("senior@folio.demo", "Senior@123")


def _ids_by_level(level: str) -> set:
    db = SessionLocal()
    try:
        return {d.id for d in db.query(Document).filter(Document.level == level).all()}
    finally:
        db.close()


def test_list_requires_auth():
    assert TestClient(app).get("/api/documents").status_code == 401


def test_detail_requires_auth():
    any_id = next(iter(_ids_by_level("junior")))
    assert TestClient(app).get(f"/api/documents/{any_id}").status_code == 401


def test_junior_lists_only_junior_documents():
    res = junior().get("/api/documents")
    assert res.status_code == 200
    docs = res.json()
    assert {d["id"] for d in docs} == _ids_by_level("junior")
    assert all(d["level"] == "junior" for d in docs)
    # Listing returns metadata only, matching API_CONTRACT.md
    assert all(set(d.keys()) == SUMMARY_KEYS for d in docs)


def test_senior_lists_all_documents():
    res = senior().get("/api/documents")
    assert res.status_code == 200
    ids = {d["id"] for d in res.json()}
    assert ids == _ids_by_level("junior") | _ids_by_level("senior")


def test_seed_counts_match_spec():
    assert len(_ids_by_level("junior")) == 6
    assert len(_ids_by_level("senior")) == 3


def test_junior_can_open_junior_document():
    doc_id = next(iter(_ids_by_level("junior")))
    res = junior().get(f"/api/documents/{doc_id}")
    assert res.status_code == 200
    body = res.json()
    assert body["id"] == doc_id
    assert isinstance(body["content"], str) and body["content"]


def test_junior_forbidden_from_senior_document_by_guessed_id():
    client = junior()
    for doc_id in _ids_by_level("senior"):
        res = client.get(f"/api/documents/{doc_id}")
        assert res.status_code == 403
        assert res.json() == {"detail": "You do not have permission to access this content."}
        assert "content" not in res.json()


def test_senior_can_open_senior_document():
    doc_id = next(iter(_ids_by_level("senior")))
    res = senior().get(f"/api/documents/{doc_id}")
    assert res.status_code == 200
    assert res.json()["level"] == "senior"
    assert res.json()["content"]


def test_unknown_document_returns_404():
    assert senior().get("/api/documents/does-not-exist").status_code == 404


def test_client_supplied_role_is_ignored():
    client = junior()
    res = client.get(
        "/api/documents",
        params={"role": "senior"},
        headers={"X-User-Role": "senior"},
    )
    assert res.status_code == 200
    assert all(d["level"] == "junior" for d in res.json())


def test_logout_revokes_document_access():
    client = junior()
    assert client.get("/api/documents").status_code == 200
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/documents").status_code == 401

