from typing import Callable, List
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from core.auth import get_user_from_session
from database.connection import get_db
from database.models import User

SESSION_COOKIE_NAME = "folio_session"


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """
    Extract and validate the active user from the HttpOnly session cookie.
    Raises 401 if missing or expired to trigger frontend re-login.
    """
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your session has expired. Please sign in again.",
        )

    user = get_user_from_session(db, session_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your session has expired. Please sign in again.",
        )

    if user.role not in ("junior", "senior"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The account has no supported access level. Contact your team lead.",
        )

    return user


def require_role(allowed_roles: List[str]) -> Callable[[User], User]:
    """Dependency helper to enforce specific role access on protected routes."""
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this content.",
            )
        return current_user
    return role_checker
