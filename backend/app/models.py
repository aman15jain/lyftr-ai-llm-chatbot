"""SQLAlchemy table definition matching the required `messages` schema."""
from sqlalchemy import Index, Integer, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)  # system | user | assistant
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # Column is named "metadata" in SQLite; the attribute name differs because
    # `metadata` is reserved by SQLAlchemy's declarative base.
    metadata_json: Mapped[str | None] = mapped_column("metadata", Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (Index("ix_messages_session_id", "session_id", "id"),)
