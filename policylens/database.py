from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from policylens.config import settings


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Database:
    """Small SQLite repository for document metadata and conversation history."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        self.db_path = Path(db_path or settings.sqlite_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    document_id TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    stored_path TEXT NOT NULL,
                    policy_group TEXT NOT NULL,
                    document_type TEXT NOT NULL,
                    page_count INTEGER NOT NULL,
                    chunk_count INTEGER NOT NULL,
                    content_sha256 TEXT NOT NULL,
                    uploaded_at TEXT NOT NULL,
                    UNIQUE(policy_group, content_sha256)
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    policy_group TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS messages (
                    message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
                    content TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_documents_group ON documents(policy_group);
                CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, message_id);
                """
            )

    def add_document(self, record: dict[str, Any]) -> None:
        with self.connect() as conn:
            conn.execute(
                """INSERT INTO documents
                (document_id, filename, stored_path, policy_group, document_type,
                 page_count, chunk_count, content_sha256, uploaded_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    record["document_id"], record["filename"], record["stored_path"],
                    record["policy_group"], record["document_type"], record["page_count"],
                    record["chunk_count"], record["content_sha256"], record["uploaded_at"],
                ),
            )

    def list_documents(self, policy_group: str | None = None) -> list[dict[str, Any]]:
        with self.connect() as conn:
            if policy_group:
                rows = conn.execute(
                    "SELECT * FROM documents WHERE policy_group = ? ORDER BY uploaded_at DESC",
                    (policy_group,),
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM documents ORDER BY uploaded_at DESC").fetchall()
        return [dict(row) for row in rows]

    def list_policy_groups(self) -> list[str]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT policy_group FROM documents ORDER BY policy_group COLLATE NOCASE"
            ).fetchall()
        return [row[0] for row in rows]

    def get_document(self, document_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM documents WHERE document_id = ?", (document_id,)
            ).fetchone()
        return dict(row) if row else None

    def delete_document_record(self, document_id: str) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM documents WHERE document_id = ?", (document_id,))

    def create_session(self, policy_group: str, title: str = "New policy conversation") -> str:
        session_id = str(uuid.uuid4())
        now = utc_now()
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO sessions(session_id, title, policy_group, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (session_id, title, policy_group, now, now),
            )
        return session_id

    def list_sessions(self, policy_group: str) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM sessions WHERE policy_group = ? ORDER BY updated_at DESC",
                (policy_group,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,)).fetchone()
        return dict(row) if row else None

    def save_message(
        self, session_id: str, role: str, content: str, metadata: dict[str, Any] | None = None
    ) -> None:
        if role not in {"user", "assistant", "system"}:
            raise ValueError(f"Unsupported message role: {role}")
        now = utc_now()
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO messages(session_id, role, content, metadata_json, created_at) VALUES (?, ?, ?, ?, ?)",
                (session_id, role, content, json.dumps(metadata or {}, ensure_ascii=False), now),
            )
            conn.execute("UPDATE sessions SET updated_at = ? WHERE session_id = ?", (now, session_id))
            if role == "user":
                session = conn.execute(
                    "SELECT title FROM sessions WHERE session_id = ?", (session_id,)
                ).fetchone()
                if session and session["title"] == "New policy conversation":
                    title = content.strip().replace("\n", " ")[:60] or "Policy conversation"
                    conn.execute("UPDATE sessions SET title = ? WHERE session_id = ?", (title, session_id))

    def get_messages(self, session_id: str, limit: int | None = None) -> list[dict[str, Any]]:
        with self.connect() as conn:
            if limit:
                rows = conn.execute(
                    "SELECT * FROM (SELECT * FROM messages WHERE session_id = ? ORDER BY message_id DESC LIMIT ?) ORDER BY message_id ASC",
                    (session_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM messages WHERE session_id = ? ORDER BY message_id ASC", (session_id,)
                ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            try:
                item["metadata"] = json.loads(item.pop("metadata_json"))
            except (TypeError, json.JSONDecodeError):
                item["metadata"] = {}
            result.append(item)
        return result

    def delete_session(self, session_id: str) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
