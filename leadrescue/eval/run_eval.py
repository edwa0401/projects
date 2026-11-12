"""Evaluate an analysis provider against the labeled synthetic dataset.

Usage (from the leadrescue/ folder):
    python eval/run_eval.py                      # deterministic demo analyzer (no AWS)
    python eval/run_eval.py --provider bedrock   # live Bedrock (needs AWS credentials + BEDROCK_MODEL_ID)
    python eval/run_eval.py --limit 10           # quick subset

Reports: classification accuracy, urgent-case recall, extraction errors,
invented (ungrounded) facts in the RAW model output (before guardrails remove
them), latency, and token usage when the provider reports it. Results are
written to eval/results/<provider>-latest.json and .md.

These are measurements on 52 synthetic messages. They are evidence about this
dataset only, not a guarantee of production accuracy.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "backend" / "src"))

from leadrescue.analysis.contract import CATEGORIES, EXTRACTED_FIELDS  # noqa: E402
from leadrescue.analysis.guardrails import _norm, build_source_text, is_grounded  # noqa: E402
from leadrescue.analysis.provider import get_provider, run_analysis  # noqa: E402
from leadrescue.config import Config  # noqa: E402
from leadrescue.errors import AnalysisError  # noqa: E402

TARGETS = {"accuracy": 0.90, "urgentRecall": 1.0, "inventedFacts": 0}


def _match(expected: str, predicted: str) -> bool:
    e, p = _norm(expected), _norm(predicted)
    return e == p or e in p or p in e


def evaluate(provider_name: str, limit: int | None = None) -> dict:
    import os

    os.environ["AI_PROVIDER"] = provider_name
    config = Config.from_env()
    provider = get_provider(config)
    rows = [json.loads(line) for line in (HERE / "dataset.jsonl").read_text().splitlines() if line.strip()]
    if limit:
        rows = rows[:limit]

    confusion = defaultdict(Counter)
    correct = urgent_total = urgent_hit = 0
    latencies, in_tokens, out_tokens = [], [], []
    missed = mismatched = invented_raw = invented_after = extra_grounded = 0
    failures, per_case = [], []

    for row in rows:
        label = row["label"]
        customer = row.get("customer", {})
        started = time.perf_counter()
        try:
            result = run_analysis(provider, row["message"], row["channel"], customer)
        except AnalysisError as exc:
            failures.append({"id": row["id"], "code": exc.code})
            confusion[label["category"]]["<failed>"] += 1
            if label["urgent"]:
                urgent_total += 1
            continue
        latencies.append((time.perf_counter() - started) * 1000)
        meta = result["meta"]
        if meta.get("inputTokens") is not None:
            in_tokens.append(meta["inputTokens"])
            out_tokens.append(meta["outputTokens"])

        pred = result["category"]
        confusion[label["category"]][pred] += 1
        correct += pred == label["category"]
        if label["urgent"]:
            urgent_total += 1
            urgent_hit += pred == "urgent_issue" and result["priority"] == "urgent"

        source = build_source_text(row["message"], customer)
        errors = []
        for field in EXTRACTED_FIELDS:
            expected = label["facts"].get(field)
            raw_val = result["rawExtracted"].get(field)
            final_val = result["extracted"].get(field)
            if raw_val and not is_grounded(raw_val, source, field):
                invented_raw += 1
                errors.append(f"{field}: invented '{raw_val}' (removed by guardrail)")
            if final_val and not is_grounded(final_val, source, field):
                invented_after += 1
            if expected:
                if not final_val:
                    missed += 1
                    errors.append(f"{field}: missed '{expected}'")
                elif not _match(expected, final_val):
                    mismatched += 1
                    errors.append(f"{field}: expected '{expected}', got '{final_val}'")
            elif final_val:
                extra_grounded += 1
        per_case.append({"id": row["id"], "expected": label["category"], "predicted": pred, "priority": result["priority"],
                         "correct": pred == label["category"], "extractionErrors": errors})

    n = len(rows)
    evaluated = n - len(failures)
    labeled_facts = sum(len(r["label"]["facts"]) for r in rows)
    report = {
        "provider": provider_name,
        "modelId": getattr(provider, "model_id", None),
        "runAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "cases": n,
        "failedCalls": failures,
        "classificationAccuracy": round(correct / n, 4) if n else None,
        "urgentRecall": round(urgent_hit / urgent_total, 4) if urgent_total else None,
        "urgentCases": urgent_total,
        "urgentFlagged": urgent_hit,
        "extraction": {
            "labeledFacts": labeled_facts,
            "missed": missed,
            "mismatched": mismatched,
            "inventedInRawOutput": invented_raw,
            "inventedAfterGuardrails": invented_after,
            "groundedValuesForUnlabeledFields": extra_grounded,
        },
        "latencyMs": {
            "p50": round(statistics.median(latencies), 1) if latencies else None,
            "p95": round(sorted(latencies)[max(0, int(len(latencies) * 0.95) - 1)], 1) if latencies else None,
            "mean": round(sum(latencies) / len(latencies), 1) if latencies else None,
        },
        "tokens": {
            "reported": bool(in_tokens),
            "inputTotal": sum(in_tokens) if in_tokens else None,
            "outputTotal": sum(out_tokens) if out_tokens else None,
            "inputMeanPerCase": round(sum(in_tokens) / len(in_tokens), 1) if in_tokens else None,
            "outputMeanPerCase": round(sum(out_tokens) / len(out_tokens), 1) if out_tokens else None,
        },
        "confusion": {k: dict(v) for k, v in confusion.items()},
        "targets": TARGETS,
        "targetsMet": {
            "accuracy": n > 0 and correct / n >= TARGETS["accuracy"],
            "urgentRecall": urgent_total > 0 and urgent_hit == urgent_total,
            "noInventedFactsAfterGuardrails": invented_after == 0 and evaluated == n,
        },
        "perCase": per_case,
        "caveat": "Synthetic dataset of 52 messages. Results describe this dataset only and do not establish production accuracy.",
    }
    return report


def to_markdown(r: dict) -> str:
    ex = r["extraction"]
    lines = [
        f"# Evaluation results: {r['provider']} ({r['modelId']})",
        "",
        f"Run at {r['runAt']} on {r['cases']} synthetic inquiries. {r['caveat']}",
        "",
        "| Metric | Result | Target | Met |",
        "|---|---|---|---|",
        f"| Classification accuracy | {r['classificationAccuracy']:.1%} | at least 90% | {'yes' if r['targetsMet']['accuracy'] else 'no'} |",
        f"| Urgent recall | {r['urgentFlagged']}/{r['urgentCases']} | all urgent cases | {'yes' if r['targetsMet']['urgentRecall'] else 'no'} |",
        f"| Invented facts after guardrails | {ex['inventedAfterGuardrails']} | 0 | {'yes' if r['targetsMet']['noInventedFactsAfterGuardrails'] else 'no'} |",
        f"| Invented facts in raw output (before guardrails) | {ex['inventedInRawOutput']} | 0 | {'yes' if ex['inventedInRawOutput'] == 0 else 'no'} |",
        f"| Labeled facts missed | {ex['missed']} of {ex['labeledFacts']} | informational | - |",
        f"| Labeled facts mismatched | {ex['mismatched']} of {ex['labeledFacts']} | informational | - |",
        f"| Failed calls | {len(r['failedCalls'])} | 0 | {'yes' if not r['failedCalls'] else 'no'} |",
        f"| Latency p50 / p95 | {r['latencyMs']['p50']} ms / {r['latencyMs']['p95']} ms | informational | - |",
        f"| Tokens (input / output total) | {r['tokens']['inputTotal'] if r['tokens']['reported'] else 'not reported'} / {r['tokens']['outputTotal'] if r['tokens']['reported'] else 'not reported'} | informational | - |",
        "",
        "## Confusion (expected -> predicted)",
        "",
        "| Expected | " + " | ".join(CATEGORIES) + " | failed |",
        "|---|" + "---|" * (len(CATEGORIES) + 1),
    ]
    for cat in CATEGORIES:
        row = r["confusion"].get(cat, {})
        lines.append(f"| {cat} | " + " | ".join(str(row.get(c, 0)) for c in CATEGORIES) + f" | {row.get('<failed>', 0)} |")
    wrong = [c for c in r["perCase"] if not c["correct"]]
    lines += ["", "## Misclassified cases", ""]
    lines += [f"- {c['id']}: expected {c['expected']}, predicted {c['predicted']}" for c in wrong] or ["- None"]
    errs = [c for c in r["perCase"] if c["extractionErrors"]]
    lines += ["", "## Extraction errors", ""]
    lines += [f"- {c['id']}: " + "; ".join(c["extractionErrors"]) for c in errs] or ["- None"]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", choices=["demo", "bedrock"], default="demo")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    report = evaluate(args.provider, args.limit)
    out = HERE / "results"
    out.mkdir(exist_ok=True)
    (out / f"{args.provider}-latest.json").write_text(json.dumps(report, indent=2))
    (out / f"{args.provider}-latest.md").write_text(to_markdown(report))
    ex = report["extraction"]
    print(f"Provider: {report['provider']} ({report['modelId']})  cases={report['cases']}  failed={len(report['failedCalls'])}")
    print(f"Classification accuracy: {report['classificationAccuracy']:.1%}  (target >= 90%)")
    print(f"Urgent recall: {report['urgentFlagged']}/{report['urgentCases']}  (target: all)")
    print(f"Extraction: missed={ex['missed']} mismatched={ex['mismatched']} of {ex['labeledFacts']} labeled facts; "
          f"invented raw={ex['inventedInRawOutput']} after guardrails={ex['inventedAfterGuardrails']}")
    print(f"Latency p50={report['latencyMs']['p50']} ms p95={report['latencyMs']['p95']} ms; tokens: "
          + (f"in={report['tokens']['inputTotal']} out={report['tokens']['outputTotal']}" if report["tokens"]["reported"] else "not reported by provider"))
    print(f"Wrote {out / (args.provider + '-latest.md')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
