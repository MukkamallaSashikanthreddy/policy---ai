from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from statistics import mean
from typing import Literal

from pydantic import BaseModel, Field

from policylens.config import settings
from policylens.database import Database
from policylens.evaluation import ingest_sample_documents
from policylens.llm import invoke_structured
from policylens.rag import RAGService


class JudgeResult(BaseModel):
    faithfulness: float = Field(ge=0, le=1, description="Share of answer claims entailed by the cited evidence, from 0 to 1.")
    relevance: float = Field(ge=0, le=1, description="How directly the answer addresses the user question, from 0 to 1.")
    explanation: str


def main() -> None:
    parser = argparse.ArgumentParser(description="Run answer-level PolicyLens evaluation (requires Gemini API key).")
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()
    ingest_sample_documents()
    db = Database()
    group = "PolicyLens Sample Motor Policy"
    session_id = db.create_session(group, "Answer evaluation")
    questions = json.loads((settings.root_dir / "evaluation" / "answer_questions.json").read_text(encoding="utf-8"))[: args.limit]
    rag = RAGService()
    outputs = []

    for test in questions:
        start = time.perf_counter()
        result = rag.ask(test["question"], group, history=[])
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        db.save_message(session_id, "user", test["question"])
        db.save_message(session_id, "assistant", result["answer"], {"citations": result["citations"]})
        citations = result["citations"]
        cited_sources = {c.get("source") for c in citations}
        if test["should_answer"]:
            citation_correct = bool(cited_sources.intersection(test["expected_sources"])) and all(
                c.get("page_number") not in (None, "Unknown") for c in citations
            )
        else:
            citation_correct = (not result["has_sufficient_evidence"]) and (len(citations) == 0)

        cited_context = "\n\n".join(c.get("passage", "") for c in citations)
        judge_prompt = f"""You are an independent evaluator of a retrieval-augmented insurance-policy answer.
Score faithfulness based ONLY on whether the answer's factual claims are supported by the cited source passages. A cautious abstention when no evidence exists can score high faithfulness.
Score relevance based on whether the answer directly addresses the question. Use 0.0 to 1.0.
Do not reward facts from outside the citations. If citations are empty and the answer appropriately abstains, faithfulness can be high.

QUESTION: {test['question']}
ANSWER: {result['answer']}
CITED SOURCE PASSAGES:
{cited_context or '(No citations)'}

Return scores and a concise explanation."""
        judge = invoke_structured(judge_prompt, JudgeResult)
        outputs.append({
            "id": test["id"],
            "question": test["question"],
            "answer": result["answer"],
            "has_sufficient_evidence": result["has_sufficient_evidence"],
            "citation_correct_for_expected_source": citation_correct,
            "citation_count": len(citations),
            "faithfulness_judge_score": judge.faithfulness,
            "relevance_judge_score": judge.relevance,
            "judge_explanation": judge.explanation,
            "latency_ms": latency_ms,
        })

    report = {
        "question_count": len(outputs),
        "faithfulness_llm_judge_mean": round(mean(x["faithfulness_judge_score"] for x in outputs), 4) if outputs else None,
        "answer_relevance_llm_judge_mean": round(mean(x["relevance_judge_score"] for x in outputs), 4) if outputs else None,
        "citation_correctness_rate": round(mean(1.0 if x["citation_correct_for_expected_source"] else 0.0 for x in outputs), 4) if outputs else None,
        "mean_latency_ms": round(mean(x["latency_ms"] for x in outputs), 2) if outputs else None,
        "per_question": outputs,
        "warning": "LLM-as-judge scores are approximate and can be biased. Review the source passages and score a sample manually before using results in a report or publication.",
    }
    output_path = settings.root_dir / "evaluation" / "answer_results.json"
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"\nSaved report: {output_path}")


if __name__ == "__main__":
    main()
