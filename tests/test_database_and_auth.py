import datetime
import pytest
from core.auth import create_session, get_user_from_session, hash_password, revoke_session, verify_password
from database.connection import SessionLocal
from database.models import Document, Session as DbSession, User, utc_now


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_password_hashing():
    raw = "MySecretPassword123!"
    hashed = hash_password(raw)
    assert hashed != raw
    assert verify_password(raw, hashed) is True
    assert verify_password("WrongPassword", hashed) is False


def test_long_password_hashing():
    long_pwd = "A" * 120  # Exceeds standard 72-byte bcrypt limit
    hashed = hash_password(long_pwd)
    assert hashed != long_pwd
    assert verify_password(long_pwd, hashed) is True
    assert verify_password("A" * 72, hashed) is True
    assert verify_password("WrongPassword", hashed) is False


def test_seeded_users(db):
    junior = db.query(User).filter(User.email == "junior@folio.demo").first()
    assert junior is not None
    assert junior.role == "junior"
    assert junior.name == "Alex Morgan"
    assert verify_password("Junior@123", junior.password_hash) is True

    senior = db.query(User).filter(User.email == "senior@folio.demo").first()
    assert senior is not None
    assert senior.role == "senior"
    assert senior.name == "Taylor Reed"
    assert verify_password("Senior@123", senior.password_hash) is True

    pub = junior.public_dict()
    assert pub == {
        "id": "demo-junior",
        "name": "Alex Morgan",
        "email": "junior@folio.demo",
        "role": "junior",
    }


def test_session_lifecycle(db):
    user = db.query(User).filter(User.email == "junior@folio.demo").first()
    assert user is not None

    # 1. Create session
    token = create_session(db, user.id, duration_days=7)
    assert isinstance(token, str)
    assert len(token) > 20

    # 2. Retrieve user from session
    retrieved_user = get_user_from_session(db, token)
    assert retrieved_user is not None
    assert retrieved_user.id == user.id

    # 3. Revoke session
    assert revoke_session(db, token) is True
    assert get_user_from_session(db, token) is None


def test_expired_session(db):
    user = db.query(User).filter(User.email == "senior@folio.demo").first()
    assert user is not None

    # Create an already-expired session
    expired_token = "test-expired-token-12345"
    now = utc_now()
    db_sess = DbSession(
        id=expired_token,
        user_id=user.id,
        created_at=now - datetime.timedelta(days=10),
        expires_at=now - datetime.timedelta(days=3),
    )
    db.add(db_sess)
    db.commit()

    # Should detect expiration, clean up, and return None
    assert get_user_from_session(db, expired_token) is None
    still_there = db.query(DbSession).filter(DbSession.id == expired_token).first()
    assert still_there is None


def test_seeded_documents(db):
    docs = db.query(Document).all()
    assert len(docs) == 9

    junior_docs = db.query(Document).filter(Document.level == "junior").all()
    senior_docs = db.query(Document).filter(Document.level == "senior").all()
    assert len(junior_docs) == 6
    assert len(senior_docs) == 3

    handbook = db.query(Document).filter(Document.id == "team-handbook").first()
    assert handbook is not None
    summary = handbook.summary_dict()
    assert summary["title"] == "The team handbook"
    assert "content" not in summary

    detail = handbook.detail_dict()
    assert "content" in detail
    assert "How we work together" in detail["content"]
