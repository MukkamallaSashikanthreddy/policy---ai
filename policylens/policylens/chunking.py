from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from langchain_text_splitters import RecursiveCharacterTextSplitter

from policylens.config import settings
from policylens.pdf_ingestion import PageText


@dataclass(frozen=True)
class TextChunk:
    chunk_id: str
    text: str
    metadata: dict[str, Any]


CLAUSE_PATTERNS: dict[str, tuple[str, ...]] = {
    "exclusion": ("not covered", "excluded", "exclusion", "we will not pay", "shall not be liable"),
    "deductible": ("deductible", "excess", "compulsory excess", "voluntary excess"),
    "claim_procedure": ("claim intimation", "notify the insurer", "claim procedure", "settlement of claim"),
    "claim_documents": ("documents required", "documents to be submitted", "claim form", "driving licence", "fir", "registration certificate"),
    "condition": ("subject to", "provided that", "condition", "within 24 hours", "reasonable care", "shall not"),
    "coverage": ("we will cover", "is covered", "insured against", "indemnify the insured against", "loss of or damage to the vehicle insured", "own damage", "third party liability", "roadside assistance", "towing"),
}


def classify_clause(text: str) -> str:
    lowered = text.casefold()
    # Give explicit benefit wording precedence over incidental claim-document/condition terms.
    for label in ("exclusion", "deductible", "coverage", "claim_procedure", "claim_documents", "condition"):
        if any(term in lowered for term in CLAUSE_PATTERNS[label]):
            return label
    return "general"


def build_chunks(
    pages: list[PageText],
    *,
    document_id: str,
    source: str,
    policy_group: str,
    document_type: str,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list[TextChunk]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size or settings.chunk_size,
        chunk_overlap=chunk_overlap if chunk_overlap is not None else settings.chunk_overlap,
        separators=["\n\n", "\n", ". ", "; ", " ", ""],
        add_start_index=True,
    )
    chunks: list[TextChunk] = []
    counter = 0
    for page in pages:
        for item in splitter.create_documents([page.text]):
            content = re.sub(r"\s+", " ", item.page_content).strip()
            if len(content) < 35:
                continue
            metadata = {
                "document_id": document_id,
                "source": source,
                "policy_group": policy_group,
                "document_type": document_type,
                "page_number": int(page.page_number),
                "chunk_index": int(counter),
                "clause_type": classify_clause(content),
                "start_index": int(item.metadata.get("start_index", 0)),
            }
            chunks.append(TextChunk(chunk_id=f"{document_id}_{counter}", text=content, metadata=metadata))
            counter += 1
    return chunks
