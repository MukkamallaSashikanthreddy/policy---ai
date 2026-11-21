from __future__ import annotations

from typing import Any


def validate_evidence_ids(requested_ids: list[str], retrieved: list[dict[str, Any]]) -> list[str]:
    """Only allow citations that refer to chunks actually returned by this retrieval call."""
    valid = {item["chunk_id"] for item in retrieved}
    seen: set[str] = set()
    validated: list[str] = []
    for chunk_id in requested_ids:
        if chunk_id in valid and chunk_id not in seen:
            validated.append(chunk_id)
            seen.add(chunk_id)
    return validated


def build_citations(
    evidence_ids: list[str], retrieved: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    by_id = {item["chunk_id"]: item for item in retrieved}
    citations: list[dict[str, Any]] = []
    for chunk_id in evidence_ids:
        item = by_id.get(chunk_id)
        if not item:
            continue
        meta = item.get("metadata", {})
        text = item.get("text", "").strip()
        citations.append(
            {
                "chunk_id": chunk_id,
                "source": meta.get("source", "Uploaded document"),
                "page_number": meta.get("page_number", "Unknown"),
                "document_type": meta.get("document_type", "document"),
                "clause_type": meta.get("clause_type", "general"),
                "passage": text[:900] + ("…" if len(text) > 900 else ""),
                "similarity": item.get("similarity"),
            }
        )
    return citations


def citation_ids_for_items(items: list[Any], retrieved: list[dict[str, Any]]) -> list[Any]:
    """Return copies of checklist items with citation IDs filtered to retrieved evidence."""
    result = []
    valid = {item["chunk_id"] for item in retrieved}
    for item in items:
        clone = item.model_copy(update={"evidence_ids": [x for x in item.evidence_ids if x in valid]})
        result.append(clone)
    return result
