"""Role-based access rules shared by the document API and RAG retrieval.

Senior inherits Junior access. Unknown roles fail closed (deny-by-default).
"""
from typing import Tuple

ROLE_LEVELS = {
    "junior": ("junior",),
    "senior": ("junior", "senior"),
}


def allowed_levels(role: str) -> Tuple[str, ...]:
    """Return the document levels a role may read. Raises PermissionError for unknown roles."""
    levels = ROLE_LEVELS.get(role)
    if levels is None:
        raise PermissionError(f"Unsupported role: {role!r}")
    return levels


def can_access_level(role: str, level: str) -> bool:
    """True if a user with `role` may read a document tagged with `level`."""
    try:
        return level in allowed_levels(role)
    except PermissionError:
        return False

