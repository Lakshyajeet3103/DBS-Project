"""Document library endpoints (`/api/documents`), filtered by the session role."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core.access import allowed_levels, can_access_level
from core.dependencies import get_current_user
from database.connection import get_db
from database.models import Document, User

router = APIRouter()

FORBIDDEN_DETAIL = "You do not have permission to access this content."


@router.get("")
def list_documents(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return metadata for every document the caller's role is cleared to see."""
    levels = allowed_levels(user.role)  # get_current_user already rejects unknown roles
    docs = (
        db.query(Document)
        .filter(Document.level.in_(levels))
        .order_by(Document.date.desc(), Document.title)
        .all()
    )
    return [doc.summary_dict() for doc in docs]


@router.get("/{document_id}")
def get_document(
    document_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return one authorized document including its full text content."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    if not can_access_level(user.role, doc.level):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=FORBIDDEN_DETAIL)

    return doc.detail_dict()

