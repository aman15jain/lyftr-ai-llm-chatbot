"""SQLite access through SQLAlchemy Core/ORM."""
import json
from datetime import datetime, timezone

from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from .models import Base, Message


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Database:
    def __init__(self, database_url: str) -> None:
        self.engine: Engine = create_engine(database_url, future=True)

    def init(self) -> None:
        """Create the tables (and the folder holding the SQLite file) if needed."""
        path = self.engine.url.database
        if path and path != ":memory:":
            import os

            folder = os.path.dirname(os.path.abspath(path))
            os.makedirs(folder, exist_ok=True)
        Base.metadata.create_all(self.engine)

    def ping(self) -> bool:
        with self.engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True

    def dispose(self) -> None:
        self.engine.dispose()

    # --- reads -------------------------------------------------------------
    def session_exists(self, session_id: str) -> bool:
        with Session(self.engine) as s:
            row = s.execute(
                select(Message.id).where(Message.session_id == session_id).limit(1)
            ).first()
            return row is not None

    def get_messages(self, session_id: str) -> list[Message]:
        """All rows (including system) for a session, oldest first."""
        with Session(self.engine) as s:
            rows = s.execute(
                select(Message).where(Message.session_id == session_id).order_by(Message.id)
            ).scalars().all()
            s.expunge_all()
            return list(rows)

    # --- writes ------------------------------------------------------------
    def save_exchange(
        self,
        session_id: str,
        user_content: str,
        assistant_content: str,
        assistant_metadata: dict,
        system_prompt: str | None = None,
    ) -> None:
        """Persist user + assistant (and optionally a new system prompt) atomically."""
        now = utcnow_iso()
        with Session(self.engine) as s, s.begin():
            if system_prompt is not None:
                s.add(Message(session_id=session_id, role="system", content=system_prompt, created_at=now))
            s.add(Message(session_id=session_id, role="user", content=user_content, created_at=now))
            s.add(
                Message(
                    session_id=session_id,
                    role="assistant",
                    content=assistant_content,
                    metadata_json=json.dumps(assistant_metadata),
                    created_at=utcnow_iso(),
                )
            )
