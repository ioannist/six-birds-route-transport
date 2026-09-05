#!/usr/bin/env python3
"""Plot a metric from experiment results across seeds and scales.

Usage:
    python analysis/plot_metric.py EXP-000 sigma_t
    python analysis/plot_metric.py EXP-001 fixed_point_count --output plot.png
"""

import json
import sys
from pathlib import Path

LEDGER_DIR = Path(__file__).parent.parent / "lab" / "ledger"


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    entries = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


def plot_metric(exp_id: str, metric_name: str, output: str | None = None):
    results = read_jsonl(LEDGER_DIR / "results.jsonl")
    results = [r for r in results if r.get("experiment_id") == exp_id]

    if not results:
        print(f"No results found for {exp_id}")
        return

    # Extract data
    data = []
    for r in results:
        metrics = r.get("metrics", {})
        val = metrics.get(metric_name)
        if val is not None:
            data.append({
                "seed": r.get("seed", 0),
                "scale": r.get("scale", 0),
                "value": float(val),
            })

    if not data:
        print(f"No values found for metric '{metric_name}' in {exp_id}")
        return

    # Try matplotlib
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        scales = sorted(set(d["scale"] for d in data))
        seeds = sorted(set(d["seed"] for d in data))

        fig, ax = plt.subplots(figsize=(8, 5))
        for scale in scales:
            vals = [d["value"] for d in data if d["scale"] == scale]
            seeds_for_scale = [d["seed"] for d in data if d["scale"] == scale]
            ax.scatter(seeds_for_scale, vals, label=f"n={scale}", alpha=0.7)

        ax.set_xlabel("Seed")
        ax.set_ylabel(metric_name)
        ax.set_title(f"{exp_id}: {metric_name}")
        ax.legend()
        ax.grid(True, alpha=0.3)

        out_path = output or f"lab/artifacts/{exp_id}_{metric_name}.png"
        fig.savefig(out_path, dpi=100, bbox_inches="tight")
        print(f"Plot saved to {out_path}")
        plt.close(fig)

    except ImportError:
        # Fallback: text summary
        print(f"\n{exp_id}: {metric_name}")
        print("-" * 40)
        scales = sorted(set(d["scale"] for d in data))
        for scale in scales:
            vals = [d["value"] for d in data if d["scale"] == scale]
            mean = sum(vals) / len(vals) if vals else 0
            min_v = min(vals) if vals else 0
            max_v = max(vals) if vals else 0
            print(f"  scale={scale:4d}: mean={mean:.6f}  min={min_v:.6f}  max={max_v:.6f}  (n={len(vals)})")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python plot_metric.py <EXP-ID> <metric_name> [--output path.png]")
        sys.exit(1)

    exp_id = sys.argv[1]
    metric_name = sys.argv[2]
    output = None
    if "--output" in sys.argv:
        idx = sys.argv.index("--output")
        if idx + 1 < len(sys.argv):
            output = sys.argv[idx + 1]

    plot_metric(exp_id, metric_name, output)
