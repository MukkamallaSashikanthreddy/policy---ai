from policylens.citations import build_citations, validate_evidence_ids


def test_citation_ids_are_limited_to_retrieved_chunks():
    chunks = [{
        "chunk_id": "doc_0",
        "text": "The compulsory deductible is INR 1,000.",
        "metadata": {"source": "schedule.pdf", "page_number": 2, "document_type": "policy_schedule", "clause_type": "deductible"},
        "similarity": 0.8,
    }]
    assert validate_evidence_ids(["doc_0", "made_up_id", "doc_0"], chunks) == ["doc_0"]
    citations = build_citations(["doc_0", "made_up_id"], chunks)
    assert len(citations) == 1
    assert citations[0]["page_number"] == 2
    assert "INR 1,000" in citations[0]["passage"]
