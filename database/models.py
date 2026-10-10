import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from database.connection import Base


def utc_now() -> datetime.datetime:
    """Return current naive UTC datetime for database timestamp consistency."""
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"

    id = Column(String(64), primary_key=True, index=True)
    name = Column(String(128), nullable=False)
    email = Column(String(128), unique=True, index=True, nullable=False)
    password_hash = Column(String(256), nullable=False)
    role = Column(String(16), nullable=False)  # "junior" or "senior"
    created_at = Column(DateTime, default=utc_now)

    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")

    def public_dict(self):
        """Return safe user profile matching frontend API contract."""
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "role": self.role,
        }


class Session(Base):
    __tablename__ = "sessions"

    id = Column(String(128), primary_key=True, index=True)  # Cryptographic session token
    user_id = Column(String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=utc_now)
    expires_at = Column(DateTime, nullable=False)

    user = relationship("User", back_populates="sessions")

    def is_expired(self) -> bool:
        return utc_now() >= self.expires_at


class Document(Base):
    __tablename__ = "documents"

    id = Column(String(64), primary_key=True, index=True)  # URL-safe identifier e.g. "team-handbook"
    title = Column(String(256), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(64), nullable=False)
    type = Column(String(32), nullable=False)              # "Guide", "Policy", "Playbook", etc.
    year = Column(String(8), nullable=False)               # "2025", "2026"
    level = Column(String(16), nullable=False)             # "junior" or "senior"
    date = Column(String(16), nullable=False)              # ISO format "YYYY-MM-DD"
    minutes = Column(Integer, default=5)
    author = Column(String(128), nullable=False)
    content = Column(Text, nullable=False)
    file_path = Column(String(256), nullable=True)
    created_at = Column(DateTime, default=utc_now)

    def summary_dict(self):
        """Metadata representation for library listing."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "category": self.category,
            "type": self.type,
            "year": self.year,
            "level": self.level,
            "date": self.date,
            "minutes": self.minutes,
            "author": self.author,
        }

    def detail_dict(self):
        """Full representation including plain text content."""
        data = self.summary_dict()
        data["content"] = self.content
        return data
