"""Permission-aware RAG assistant endpoint (`POST /api/chat`).

Implements Task 3.4:
- Authenticates caller via `Depends(get_current_user)` (HttpOnly session cookie).
- Validates optional `document_id` scope against the SQL document registry and caller's role.
- Invokes `services.rag_service.query_rag` using the server-verified `user.role` and active SQL
  session `db` so every retrieved chunk is verified against the live SQL document registry.
"""
import inspect
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from core.access import can_access_level
from core.dependencies import get_current_user
from database.connection import get_db
from database.models import Document, User
from services import rag_service

router = APIRouter()

FORBIDDEN_DOCUMENT_DETAIL = "You do not have permission to access this content."


class ChatRequest(BaseModel):
    """Request payload for `POST /api/chat`.

    Extra client-supplied fields (such as a spoofed `role`) are ignored so the role is
    always derived strictly from the server session.
    """

    model_config = ConfigDict(extra="ignore")

    message: str
    document_id: Optional[str] = None


@router.post("/chat")
def chat_endpoint(
    req: ChatRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Answer a user question grounded in their role-authorized document corpus."""
    clean_message = req.message.strip()
    if not clean_message:
        raise HTTPException(
            status_code=422,
            detail="Message cannot be empty.",
        )

    scoped_doc_id = req.document_id.strip() if isinstance(req.document_id, str) and req.document_id.strip() else None
    if scoped_doc_id:
        doc = db.query(Document).filter(Document.id == scoped_doc_id).first()
        if not doc or not can_access_level(user.role, doc.level):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=FORBIDDEN_DOCUMENT_DETAIL,
            )

    kwargs = {
        "query": clean_message,
        "user_role": user.role,
        "document_id": scoped_doc_id,
    }
    try:
        sig = inspect.signature(rag_service.query_rag)
        if "db" in sig.parameters:
            kwargs["db"] = db
    except (TypeError, ValueError):
        pass

    try:
        return rag_service.query_rag(**kwargs)
    except HTTPException:
        raise
    except Exception as exc:
        # SDK versions expose HTTP status as either code or status_code.
        code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
        if code in (429, 503, 504) or isinstance(exc, TimeoutError):
            raise HTTPException(
                status_code=503,
                detail="The AI service is temporarily busy. Please try again shortly.",
            ) from exc
        raise
