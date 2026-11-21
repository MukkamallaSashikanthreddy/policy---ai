from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from policylens.config import settings
from policylens.database import Database, utc_now
from policylens.pdf_ingestion import extract_pdf_pages, sha256_bytes
from policylens.chunking import build_chunks
from policylens.vector_store import ChromaVectorStore


class IngestionService:
    def __init__(self, database: Database | None = None, vector_store: ChromaVectorStore | None = None) -> None:
        self.database = database or Database()
        self.vector_store = vector_store or ChromaVectorStore()

    def add_pdf(
        self,
        *,
        filename: str,
        file_bytes: bytes,
        policy_group: str,
        document_type: str,
    ) -> dict[str, Any]:
        if not filename.lower().endswith(".pdf"):
            raise ValueError("Only PDF files can be uploaded.")
        if len(file_bytes) > settings.max_upload_mb * 1024 * 1024:
            raise ValueError(f"File exceeds the {settings.max_upload_mb} MB upload limit.")
        policy_group = policy_group.strip()
        if not policy_group:
            raise ValueError("Enter a policy group/name before uploading.")
        content_hash = sha256_bytes(file_bytes)
        for existing in self.database.list_documents(policy_group):
            if existing["content_sha256"] == content_hash:
                raise ValueError("This exact PDF is already indexed in the selected policy group.")

        pages, page_count = extract_pdf_pages(file_bytes)
        document_id = str(uuid.uuid4())
        chunks = build_chunks(
            pages,
            document_id=document_id,
            source=Path(filename).name,
            policy_group=policy_group,
            document_type=document_type,
        )
        if not chunks:
            raise ValueError("No useful text chunks could be created from this PDF.")

        stored_path = settings.uploads_dir / f"{document_id}.pdf"
        stored_path.write_bytes(file_bytes)
        try:
            self.vector_store.add_chunks(chunks)
            record = {
                "document_id": document_id,
                "filename": Path(filename).name,
                "stored_path": str(stored_path),
                "policy_group": policy_group,
                "document_type": document_type,
                "page_count": page_count,
                "chunk_count": len(chunks),
                "content_sha256": content_hash,
                "uploaded_at": utc_now(),
            }
            self.database.add_document(record)
        except Exception:
            self.vector_store.delete_document(document_id)
            stored_path.unlink(missing_ok=True)
            raise
        return record

    def delete_pdf(self, document_id: str) -> bool:
        record = self.database.get_document(document_id)
        if not record:
            return False
        self.vector_store.delete_document(document_id)
        self.database.delete_document_record(document_id)
        Path(record["stored_path"]).unlink(missing_ok=True)
        return True
