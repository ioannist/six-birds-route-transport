#!/usr/bin/env python3
"""Read and summarize the lab ledger JSONL files."""

import json
import sys
from pathlib import Path
from collections import Counter

LEDGER_DIR = Path(__file__).parent.parent / "lab" / "ledger"


def read_jsonl(path: Path) -> list[dict]:
    """Read a JSONL file into a list of dicts."""
    if not path.exists():
        return []
    entries = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


def summarize():
    """Print a summary of all ledger files."""
    hyps = read_jsonl(LEDGER_DIR / "hypotheses.jsonl")
    exps = read_jsonl(LEDGER_DIR / "experiments.jsonl")
    results = read_jsonl(LEDGER_DIR / "results.jsonl")
    closures = read_jsonl(LEDGER_DIR / "closures.jsonl")

    print("=" * 60)
    print("LEDGER SUMMARY")
    print("=" * 60)

    print(f"\nHypotheses: {len(hyps)}")
    if hyps:
        status_counts = Counter(h.get("status", "?") for h in hyps)
        for status, count in sorted(status_counts.items()):
            print(f"  {status}: {count}")

    print(f"\nExperiments: {len(exps)}")
    if exps:
        status_counts = Counter(e.get("status", "?") for e in exps)
        for status, count in sorted(status_counts.items()):
            print(f"  {status}: {count}")

    print(f"\nResults: {len(results)}")
    if results:
        outcome_counts = Counter(r.get("outcome", "?") for r in results)
        for outcome, count in sorted(outcome_counts.items()):
            print(f"  {outcome}: {count}")

        # Per-experiment summary
        exp_results: dict[str, list] = {}
        for r in results:
            eid = r.get("experiment_id", "?")
            exp_results.setdefault(eid, []).append(r)

        print("\n  Per experiment:")
        for eid, runs in sorted(exp_results.items()):
            outcomes = Counter(r.get("outcome", "?") for r in runs)
            print(f"    {eid}: {len(runs)} runs — {dict(outcomes)}")

    print(f"\nClosures: {len(closures)}")
    if closures:
        for c in closures:
            print(f"  {c['id']}: {c.get('description', '?')} [{c.get('status', '?')}]")

    print()


def list_results(exp_id: str | None = None):
    """List result entries, optionally filtered by experiment."""
    results = read_jsonl(LEDGER_DIR / "results.jsonl")
    if exp_id:
        results = [r for r in results if r.get("experiment_id") == exp_id]

    for r in results:
        metrics_str = json.dumps(r.get("metrics", {}), default=str)
        if len(metrics_str) > 80:
            metrics_str = metrics_str[:77] + "..."
        print(f"{r['id']}  outcome={r.get('outcome', '?')}  {metrics_str}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "list":
        exp_filter = sys.argv[2] if len(sys.argv) > 2 else None
        list_results(exp_filter)
    else:
        summarize()
