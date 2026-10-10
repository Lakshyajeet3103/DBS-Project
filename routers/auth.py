import os
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from core.auth import create_session, revoke_session, verify_password
from core.dependencies import SESSION_COOKIE_NAME, get_current_user
from database.connection import get_db
from database.models import User

router = APIRouter()


class LoginRequest(BaseModel):
    email: str
    password: str


@router.post("/login")
def login(req: LoginRequest, response: Response, db: Session = Depends(get_db)):
    """Authenticate user with email and password, set HttpOnly cookie, return public profile."""
    clean_email = req.email.strip().lower()
    user = db.query(User).filter(User.email == clean_email).first()

    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="The email or password is incorrect.",
        )

    duration_days = int(os.getenv("SESSION_DURATION_DAYS", "7"))
    is_production = os.getenv("ENVIRONMENT", "development").lower() == "production"

    # Create session token in database
    token = create_session(db, user.id, duration_days=duration_days)

    # Set secure HttpOnly session cookie
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=is_production,
        max_age=86400 * duration_days,
        path="/",
    )

    return user.public_dict()


@router.get("/me")
def get_current_user_profile(user: User = Depends(get_current_user)):
    """Return the authenticated user profile based on the active session cookie."""
    return user.public_dict()


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, db: Session = Depends(get_db)):
    """Revoke active session from database and clear the session cookie."""
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if session_id:
        revoke_session(db, session_id)

    is_production = os.getenv("ENVIRONMENT", "development").lower() == "production"
    res = Response(status_code=status.HTTP_204_NO_CONTENT)
    res.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        httponly=True,
        samesite="lax",
        secure=is_production,
    )
    return res
