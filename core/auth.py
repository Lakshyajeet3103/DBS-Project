import datetime
import os
import secrets
from typing import Optional
import bcrypt
from sqlalchemy.orm import Session
from database.models import Session as DbSession, User, utc_now

DEFAULT_SESSION_DURATION_DAYS = int(os.getenv("SESSION_DURATION_DAYS", "7"))


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt with salt, safely bounded at 72 bytes."""
    pwd_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    try:
        pwd_bytes = plain_password.encode("utf-8")[:72]
        return bcrypt.checkpw(
            pwd_bytes,
            hashed_password.encode("utf-8")
        )
    except Exception:
        return False


def create_session(db: Session, user_id: str, duration_days: int = DEFAULT_SESSION_DURATION_DAYS) -> str:
    """Generate a cryptographically secure session token and store in DB."""
    token = secrets.token_urlsafe(32)
    now = utc_now()
    expires_at = now + datetime.timedelta(days=duration_days)

    db_session = DbSession(
        id=token,
        user_id=user_id,
        created_at=now,
        expires_at=expires_at
    )
    db.add(db_session)
    db.commit()
    db.refresh(db_session)
    return token


def get_user_from_session(db: Session, session_id: str) -> Optional[User]:
    """Retrieve and validate the user associated with a session token."""
    if not session_id:
        return None

    db_session = db.query(DbSession).filter(DbSession.id == session_id).first()
    if not db_session:
        return None

    if db_session.is_expired():
        # Clean up expired session
        db.delete(db_session)
        db.commit()
        return None

    return db_session.user


def revoke_session(db: Session, session_id: str) -> bool:
    """Revoke (delete) a session token from the database."""
    if not session_id:
        return False

    db_session = db.query(DbSession).filter(DbSession.id == session_id).first()
    if db_session:
        db.delete(db_session)
        db.commit()
        return True
    return False
