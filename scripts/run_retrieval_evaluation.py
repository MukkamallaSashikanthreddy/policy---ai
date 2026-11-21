from __future__ import annotations

import argparse
import json
from pathlib import Path

from policylens.config import settings
from policylens.evaluation import evaluate_retrieval, ingest_sample_documents


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the PolicyLens retrieval-only benchmark.")
    parser.add_argument("--top-k", type=int, default=6)
    args = parser.parse_args()
    ingest_sample_documents()
    report = evaluate_retrieval(settings.root_dir / "evaluation" / "gold_questions.json", top_k=args.top_k)
    output = settings.root_dir / "evaluation" / "latest_results.json"
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"\nSaved report: {output}")


if __name__ == "__main__":
    main()
