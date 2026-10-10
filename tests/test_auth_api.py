import pytest
from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient
from main import app
from database.seed import seed_database
from database.connection import SessionLocal
from database.models import User
from core.auth import hash_password
from core.dependencies import get_current_user, require_role

# Ensure database is seeded for tests
seed_database()

# Mount a temporary test endpoint to verify require_role dependency
role_gating_router = APIRouter()

@role_gating_router.get("/api/test/senior-only")
def senior_only_endpoint(user: User = Depends(require_role(["senior"]))):
    return {"status": "senior_access_granted", "user": user.name}

app.include_router(role_gating_router)


def test_health_check():
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"status": "AI backend is running"}


def test_unauthenticated_me():
    client = TestClient(app)
    response = client.get("/api/auth/me")
    assert response.status_code == 401
    assert "Your session has expired" in response.json()["detail"]


def test_login_invalid_credentials():
    client = TestClient(app)
    response = client.post(
        "/api/auth/login",
        json={"email": "junior@folio.demo", "password": "WrongPassword123"}
    )
    assert response.status_code == 401
    assert "The email or password is incorrect" in response.json()["detail"]


def test_login_case_and_whitespace_insensitivity():
    client = TestClient(app)
    response = client.post(
        "/api/auth/login",
        json={"email": "   JUNIOR@FOLIO.DEMO  \n", "password": "Junior@123"}
    )
    assert response.status_code == 200
    assert response.json()["email"] == "junior@folio.demo"
    assert response.json()["role"] == "junior"


def test_login_and_me_lifecycle_junior():
    client = TestClient(app)

    # 1. Login as junior
    login_res = client.post(
        "/api/auth/login",
        json={"email": "junior@folio.demo", "password": "Junior@123"}
    )
    assert login_res.status_code == 200
    user_data = login_res.json()
    assert user_data["email"] == "junior@folio.demo"
    assert user_data["role"] == "junior"
    assert user_data["name"] == "Alex Morgan"
    assert "folio_session" in login_res.cookies

    # 2. Get profile with cookie
    me_res = client.get("/api/auth/me")
    assert me_res.status_code == 200
    assert me_res.json() == user_data

    # 3. Logout and check cookie deletion header
    logout_res = client.post("/api/auth/logout")
    assert logout_res.status_code == 204
    set_cookie_header = logout_res.headers.get("set-cookie", "")
    assert "folio_session" in set_cookie_header
    assert "Max-Age=0" in set_cookie_header

    # 4. Check that session is revoked
    me_after_logout = client.get("/api/auth/me")
    assert me_after_logout.status_code == 401


def test_login_and_me_lifecycle_senior():
    client = TestClient(app)

    login_res = client.post(
        "/api/auth/login",
        json={"email": "senior@folio.demo", "password": "Senior@123"}
    )
    assert login_res.status_code == 200
    user_data = login_res.json()
    assert user_data["email"] == "senior@folio.demo"
    assert user_data["role"] == "senior"
    assert user_data["name"] == "Taylor Reed"
    assert "folio_session" in login_res.cookies

    me_res = client.get("/api/auth/me")
    assert me_res.status_code == 200
    assert me_res.json() == user_data


def test_require_role_enforcement():
    # 1. Anonymous access denied
    anon_client = TestClient(app)
    res = anon_client.get("/api/test/senior-only")
    assert res.status_code == 401

    # 2. Junior access forbidden
    junior_client = TestClient(app)
    junior_client.post(
        "/api/auth/login",
        json={"email": "junior@folio.demo", "password": "Junior@123"}
    )
    res = junior_client.get("/api/test/senior-only")
    assert res.status_code == 403
    assert "You do not have permission to access this content" in res.json()["detail"]

    # 3. Senior access granted
    senior_client = TestClient(app)
    senior_client.post(
        "/api/auth/login",
        json={"email": "senior@folio.demo", "password": "Senior@123"}
    )
    res = senior_client.get("/api/test/senior-only")
    assert res.status_code == 200
    assert res.json()["status"] == "senior_access_granted"
    assert res.json()["user"] == "Taylor Reed"


def test_unsupported_role_rejected():
    # Insert a user with an unknown role in database
    db = SessionLocal()
    invalid_user = User(
        id="demo-unknown",
        email="guest@folio.demo",
        name="Guest User",
        role="guest",  # Neither junior nor senior
        password_hash=hash_password("Guest@123")
    )
    db.merge(invalid_user)
    db.commit()
    db.close()

    client = TestClient(app)
    login_res = client.post(
        "/api/auth/login",
        json={"email": "guest@folio.demo", "password": "Guest@123"}
    )
    assert login_res.status_code == 200

    # Requesting /api/auth/me should fail closed with 403
    me_res = client.get("/api/auth/me")
    assert me_res.status_code == 403
    assert "The account has no supported access level" in me_res.json()["detail"]
