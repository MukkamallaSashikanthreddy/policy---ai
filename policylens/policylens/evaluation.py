from __future__ import annotations

import json
import re
from pathlib import Path
from statistics import mean
from typing import Any

from policylens.config import settings
from policylens.ingestion import IngestionService
from policylens.retrieval import PolicyRetriever
from policylens.vector_store import ChromaVectorStore
from policylens.database import Database


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.casefold())


def evaluate_retrieval(
    questions_path: Path | str,
    *,
    policy_group: str = "PolicyLens Sample Motor Policy",
    top_k: int = 6,
) -> dict[str, Any]:
    questions = json.loads(Path(questions_path).read_text(encoding="utf-8"))
    retriever = PolicyRetriever()
    per_question = []
    precisions: list[float] = []
    recalls: list[float] = []
    abstention_cases = []

    # The benchmark's expected phrases are manually selected from sample policy passages.
    all_chunks = retriever.retrieve("motor insurance policy claim coverage exclusions", policy_group, top_k=200)
    for test in questions:
        results = retriever.retrieve(test["question"], policy_group, top_k=top_k)
        expected_terms = [_normalize(term) for term in test.get("expected_terms", [])]
        relevant_pool = [
            chunk for chunk in all_chunks
            if expected_terms and any(term in _normalize(chunk["text"]) for term in expected_terms)
        ]
        retrieved_relevant = [
            chunk for chunk in results
            if expected_terms and any(term in _normalize(chunk["text"]) for term in expected_terms)
        ]
        if expected_terms:
            precision = len(retrieved_relevant) / max(1, len(results))
            recall = len(retrieved_relevant) / max(1, len(relevant_pool))
            precisions.append(precision)
            recalls.append(recall)
            per_question.append({
                "id": test["id"], "question": test["question"], "expected_answerable": True,
                "retrieved": len(results), "relevant_retrieved": len(retrieved_relevant),
                "relevant_in_index": len(relevant_pool), "precision_at_k": round(precision, 4),
                "recall_at_k": round(recall, 4),
                "support_found": bool(retrieved_relevant),
            })
        else:
            support_found = any(
                _normalize(term) in _normalize(chunk["text"])
                for term in test.get("absent_terms", []) for chunk in results
            )
            abstention_cases.append(not support_found)
            per_question.append({
                "id": test["id"], "question": test["question"], "expected_answerable": False,
                "retrieved": len(results), "abstention_success_by_gold_phrase_check": not support_found,
            })

    return {
        "policy_group": policy_group,
        "top_k": top_k,
        "question_count": len(questions),
        "retrieval_precision_at_k_mean": round(mean(precisions), 4) if precisions else None,
        "retrieval_recall_at_k_mean": round(mean(recalls), 4) if recalls else None,
        "absent_evidence_checks_passed": sum(abstention_cases),
        "absent_evidence_checks_total": len(abstention_cases),
        "per_question": per_question,
        "note": "Retrieval-only benchmark. Answer faithfulness, answer relevance, Gemini latency and final citation correctness require answer-level runs and human review; they are not inferred from retrieval metrics.",
    }


def ingest_sample_documents() -> None:
    db = Database()
    store = ChromaVectorStore()
    service = IngestionService(db, store)
    sample_dir = settings.root_dir / "sample_policies"
    mapping = {
        "sample_motor_policy_wording.pdf": "policy_wording",
        "sample_motor_policy_schedule.pdf": "policy_schedule",
        "sample_claim_guide.pdf": "claim_guide",
    }
    for filename, doc_type in mapping.items():
        file_path = sample_dir / filename
        if not file_path.exists():
            raise FileNotFoundError(f"Missing sample policy PDF: {file_path}")
        existing = [d for d in db.list_documents("PolicyLens Sample Motor Policy") if d["filename"] == filename]
        if not existing:
            service.add_pdf(
                filename=filename,
                file_bytes=file_path.read_bytes(),
                policy_group="PolicyLens Sample Motor Policy",
                document_type=doc_type,
            )
