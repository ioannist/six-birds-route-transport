#!/usr/bin/env python3
"""
Generate Markdown reports from audit JSONL files.

Reads audits.jsonl, computes per-config statistics (median, IQR),
identifies outliers, and produces a structured report.

Usage:
    python analysis/report_stage.py --input audits.jsonl --output report.md [--stage "Stage 01"]
"""

import hashlib
import json
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from argparse import ArgumentParser

# Known label aliases: map variant labels to their canonical name.
# Must match the table in collect_audits.py.
LABEL_ALIASES = {
    "A15_only": "baseline",        # EXP-103 mislabels baseline() as A15_only
    "baseline_ref": "baseline",    # some stages use baseline_ref
}


def normalize_label(label: str) -> str:
    """Apply alias normalization to a config label."""
    return LABEL_ALIASES.get(label, label)


def load_audits(path: Path) -> list:
    """Load audits from JSONL file."""
    audits = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                audits.append(json.loads(line))
    return audits


def config_identity(record: dict) -> str:
    """Compute a config identity key for dedup.

    Priority order:
    1. Full pica_config JSON (captures ALL parameters including the 12 excluded from hash)
    2. pica_config_hash (covers enabled matrix + 9 core params, misses 12 others)
    3. Normalized label (last resort for legacy records)

    Returns a string suitable as a dict/set key.
    """
    pica_config = record.get("pica_config")
    if pica_config is not None:
        canonical = json.dumps(pica_config, sort_keys=True, separators=(",", ":"))
        return "full:" + hashlib.sha256(canonical.encode()).hexdigest()[:16]
    pch = record.get("pica_config_hash")
    if pch is not None:
        return f"hash:{pch}"
    label = record.get("_cfg_label") or record.get("config_name") or "?"
    return f"label:{normalize_label(label)}"


def cfg_display_label(a: dict) -> str:
    """Get the display label for an audit record (normalized through aliases)."""
    raw = a.get("_cfg_label") or a.get("config_name") or str(a.get("pica_config_hash", "?"))
    return normalize_label(raw)


def deduplicate_audits(audits: list) -> tuple:
    """Deduplicate by (config_identity, n, seed), keeping first occurrence.

    Returns (deduped_list, n_dropped).
    Uses config_identity() which prefers full pica_config JSON (captures all params),
    falls back to pica_config_hash, then label. Labels are normalized through
    LABEL_ALIASES and used only for display.
    """
    # First pass: normalize labels
    for a in audits:
        if "_cfg_label" in a:
            a["_cfg_label"] = normalize_label(a["_cfg_label"])
        if "config_name" in a and a["config_name"]:
            a["config_name"] = normalize_label(a["config_name"])

    seen = set()
    result = []
    for a in audits:
        cfg_key = config_identity(a)
        key = (cfg_key, a.get("n"), a.get("seed"))
        if key not in seen:
            seen.add(key)
            result.append(a)
    return result, len(audits) - len(result)


def safe_median(vals):
    return statistics.median(vals) if vals else None

def safe_stdev(vals):
    return statistics.stdev(vals) if len(vals) >= 2 else 0.0

def quartiles(vals):
    """Compute Q1, median, Q3 for a list of values."""
    if not vals:
        return None, None, None
    s = sorted(vals)
    n = len(s)
    q1 = s[n // 4] if n >= 4 else s[0]
    med = statistics.median(s)
    q3 = s[(3 * n) // 4] if n >= 4 else s[-1]
    return q1, med, q3


def fmt(v, decimals=4):
    """Format a value for display."""
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:.{decimals}f}"
    return str(v)


def nested_get(d, *keys):
    """Get nested value from dict, e.g. nested_get(d, 'partition_stats', 'effective_k')."""
    for k in keys:
        if d is None or not isinstance(d, dict):
            return None
        d = d.get(k)
    return d


CORE_METRICS = [
    ("frob_from_rank1", "frob"),
    ("macro_gap", "gap"),
    ("sigma", "σ_π"),
    ("sigma_ratio", "σ_ratio"),
    ("sigma_u", "σ_u"),
    ("macro_gap_ratio", "gap_ratio"),
]

STRUCTURE_METRICS = [
    ("partition_stats.effective_k", "part_k"),
    ("packaging_stats.effective_k", "pkg_k"),
    ("partition_flip_count", "part_flips"),
    ("packaging_flip_count", "pkg_flips"),
    ("tau_change_count", "τ_changes"),
]

RICH_METRICS = [
    ("max_asym", "max_asym"),
    ("n_chiral", "n_chiral"),
    ("trans_ep", "trans_ep"),
]

LAGRANGE_SCAN_METRICS = [
    ("step_entropy", "H_step"),
    ("pla2_gap", "PLA2_gap"),
    ("lagr_geo_r2", "geo_R2"),
    ("lagr_diff_kl", "diff_KL"),
    ("lagr_diff_alpha", "diff_alpha"),
    ("t_rel", "t_rel"),
    ("gap_ratio", "gap_ratio"),
    ("eigen_entropy", "H_eig"),
    ("spectral_participation", "N_eff"),
    ("slow_modes_r50", "r50"),
    ("slow_modes_r70", "r70"),
    ("slow_modes_r90", "r90"),
]


def get_metric(audit, metric_path):
    """Get a metric value from an audit record, supporting dotted paths."""
    if "." in metric_path:
        parts = metric_path.split(".")
        return nested_get(audit, *parts)
    return audit.get(metric_path)


def group_by(audits, key_fn):
    """Group audits by a key function."""
    groups = defaultdict(list)
    for a in audits:
        k = key_fn(a)
        groups[k].append(a)
    return groups


def compute_stats(audits, metric_path):
    """Compute stats for a metric across a list of audit records."""
    vals = [v for a in audits if (v := get_metric(a, metric_path)) is not None]
    if not vals:
        return None
    q1, med, q3 = quartiles(vals)
    iqr = (q3 - q1) if q1 is not None and q3 is not None else 0
    n_seeds = len(set(a.get("seed") for a in audits))
    return {
        "n": len(vals),
        "n_seeds": n_seeds,
        "median": med,
        "q1": q1,
        "q3": q3,
        "iqr": iqr,
        "min": min(vals),
        "max": max(vals),
        "std": safe_stdev(vals),
    }


def build_display_map(audits):
    """Map config_identity → display label, disambiguating collisions.

    When multiple distinct config identities share the same display label
    (e.g. "baseline" from two experiments with different interval params),
    appends a short identity suffix to distinguish them in tables.
    """
    id_to_labels = defaultdict(set)
    for a in audits:
        cid = config_identity(a)
        label = cfg_display_label(a)
        id_to_labels[cid].add(label)

    # Pick deterministic label for each identity (alphabetically first)
    id_display = {}
    for cid, labels in id_to_labels.items():
        id_display[cid] = sorted(labels)[0]

    # Disambiguate: when multiple identities map to the same label
    label_to_ids = defaultdict(list)
    for cid, label in id_display.items():
        label_to_ids[label].append(cid)

    for label, cids in label_to_ids.items():
        if len(cids) > 1:
            for cid in sorted(cids):
                suffix = cid.split(":")[-1][:8]
                id_display[cid] = f"{label} [{suffix}]"

    return id_display


def generate_report(audits, output, stage_name=""):
    """Generate Markdown report."""
    lines = []
    lines.append(f"# Stage Report: {stage_name}")
    lines.append("")

    # Deduplicate: one record per (config, scale, seed)
    raw_count = len(audits)
    audits, n_dropped = deduplicate_audits(audits)
    lines.append(f"**Total audit records:** {len(audits)} (unique) from {raw_count} raw "
                 f"({n_dropped} cross-stage duplicates removed)")
    lines.append("")

    # Build identity → display label mapping (disambiguates collisions)
    id_display = build_display_map(audits)

    # Group by config identity (NOT display label — prevents merging
    # distinct configs that happen to share the same human label)
    by_cfg = group_by(audits, config_identity)

    # Group by (config identity, scale)
    by_cfg_scale = group_by(
        audits,
        lambda a: (config_identity(a), a.get("n"))
    )

    # ── Run status summary ──
    lines.append("## Run Summary")
    lines.append("")
    exp_ids = sorted(set(a.get("exp_id", "?") for a in audits))
    scales = sorted(set(a.get("n", 0) for a in audits))
    n_seeds = len(set(a.get("seed", 0) for a in audits))
    n_cfgs = len(by_cfg)
    lines.append(f"- Experiments: {', '.join(exp_ids)}")
    lines.append(f"- Scales: {scales}")
    lines.append(f"- Seeds: {n_seeds}")
    lines.append(f"- Configs: {n_cfgs} (by identity, {len(set(id_display.values()))} distinct labels)")
    lines.append(f"- Dedup: removed {n_dropped} duplicate (cfg, n, seed) records")
    lines.append("")

    # Stable sort order: config identities sorted by display label
    cfg_ids_sorted = sorted(by_cfg.keys(), key=lambda cid: id_display.get(cid, cid))

    # ── Core metrics table ──
    lines.append("## Core Metrics (median ± IQR across seeds)")
    lines.append("")

    all_metrics = CORE_METRICS + STRUCTURE_METRICS + RICH_METRICS
    for metric_path, short_name in all_metrics:
        # Check if any audit has this metric
        has_metric = any(get_metric(a, metric_path) is not None for a in audits)
        if not has_metric:
            continue

        lines.append(f"### {short_name} (`{metric_path}`)")
        lines.append("")
        header = "| config | " + " | ".join(f"n={s}" for s in scales) + " |"
        sep = "|--------|" + "|".join("--------" for _ in scales) + "|"
        lines.append(header)
        lines.append(sep)

        for cfg_id in cfg_ids_sorted:
            display = id_display.get(cfg_id, cfg_id)
            cells = []
            for s in scales:
                key = (cfg_id, s)
                if key in by_cfg_scale:
                    st = compute_stats(by_cfg_scale[key], metric_path)
                    if st:
                        cells.append(f"{fmt(st['median'])} ±{fmt(st['iqr'])} ({st['n_seeds']}s)")
                    else:
                        cells.append("—")
                else:
                    cells.append("—")
            lines.append(f"| {display} | " + " | ".join(cells) + " |")
        lines.append("")

    # ── Baseline deltas ──
    lines.append("## Baseline Deltas (median difference from baseline)")
    lines.append("")

    # Find baseline identity. If multiple identities map to "baseline" (or contain
    # "baseline"), the display map will have disambiguated them with suffixes.
    # We need exactly one unambiguous baseline to compute deltas.
    baseline_candidates = [cid for cid, label in id_display.items() if label == "baseline"]
    if not baseline_candidates:
        baseline_candidates = [cid for cid, label in id_display.items()
                               if "baseline" in label.lower()]
    baseline_id = None
    if len(baseline_candidates) == 1:
        baseline_id = baseline_candidates[0]
    elif len(baseline_candidates) > 1:
        lines.append(f"**WARNING:** {len(baseline_candidates)} distinct baseline identities "
                     f"found (disambiguated as {[id_display[c] for c in baseline_candidates]}). "
                     f"Baseline deltas skipped — cannot determine which baseline to compare against.")
        lines.append("")

    if baseline_id is not None:
        delta_metrics = [("frob_from_rank1", "frob"), ("sigma", "σ_π"),
                         ("sigma_ratio", "σ_ratio")]
        for metric_path, short_name in delta_metrics:
            has_metric = any(get_metric(a, metric_path) is not None for a in audits)
            if not has_metric:
                continue

            lines.append(f"### Δ{short_name}")
            lines.append("")
            header = "| config | " + " | ".join(f"n={s}" for s in scales) + " |"
            sep = "|--------|" + "|".join("--------" for _ in scales) + "|"
            lines.append(header)
            lines.append(sep)

            for cfg_id in cfg_ids_sorted:
                if cfg_id == baseline_id:
                    continue
                display = id_display.get(cfg_id, cfg_id)
                cells = []
                for s in scales:
                    cfg_st = compute_stats(by_cfg_scale.get((cfg_id, s), []), metric_path)
                    base_st = compute_stats(by_cfg_scale.get((baseline_id, s), []), metric_path)
                    if cfg_st and base_st and cfg_st["median"] is not None and base_st["median"] is not None:
                        delta = cfg_st["median"] - base_st["median"]
                        cells.append(f"{delta:+.4f}")
                    else:
                        cells.append("—")
                lines.append(f"| {display} | " + " | ".join(cells) + " |")
            lines.append("")

    # ── Multi-scale scan profiles ──
    has_scan = any(a.get("multi_scale_scan") for a in audits)
    if has_scan:
        lines.append("## Multi-Scale Scan Profiles")
        lines.append("")
        lines.append("Median sigma_pi across k for each config (aggregated over seeds/scales).")
        lines.append("")

        for cfg_id in sorted(by_cfg.keys(), key=lambda c: id_display.get(c, c)):
            display = id_display.get(cfg_id, cfg_id)
            cfg_audits = by_cfg[cfg_id]
            scans = [a["multi_scale_scan"] for a in cfg_audits if a.get("multi_scale_scan")]
            if not scans:
                continue
            # Collect by k
            by_k = defaultdict(list)
            for scan in scans:
                for entry in scan:
                    k = entry.get("k")
                    sp = entry.get("sigma_pi")
                    if k and sp is not None:
                        by_k[k].append(sp)

            if by_k:
                lines.append(f"**{display}:** " + ", ".join(
                    f"k={k}: σ={fmt(safe_median(vs))}"
                    for k, vs in sorted(by_k.items())
                ))
        lines.append("")

    # ── Lagrange probe profiles (from multi_scale_scan entries) ──
    has_lagrange = any(
        entry.get("step_entropy") is not None
        for a in audits if a.get("multi_scale_scan")
        for entry in a["multi_scale_scan"]
    )
    if has_lagrange:
        lines.append("## Lagrange Probe Profiles")
        lines.append("")
        lines.append("Median across seeds per config per k. Extracted from `multi_scale_scan` entries.")
        lines.append("")

        for metric_key, short_name in LAGRANGE_SCAN_METRICS:
            # Check if any scan entry has this metric
            has_this = any(
                entry.get(metric_key) is not None
                for a in audits if a.get("multi_scale_scan")
                for entry in a["multi_scale_scan"]
            )
            if not has_this:
                continue

            lines.append(f"### {short_name} (`{metric_key}`)")
            lines.append("")

            # Collect all k values present
            all_k = sorted(set(
                entry.get("k")
                for a in audits if a.get("multi_scale_scan")
                for entry in a["multi_scale_scan"]
                if entry.get("k") is not None
            ))
            if not all_k:
                continue

            header = "| config | " + " | ".join(f"k={k}" for k in all_k) + " |"
            sep = "|--------|" + "|".join("--------" for _ in all_k) + "|"
            lines.append(header)
            lines.append(sep)

            for cfg_id in cfg_ids_sorted:
                display = id_display.get(cfg_id, cfg_id)
                cfg_audits = by_cfg[cfg_id]
                scans = [a["multi_scale_scan"] for a in cfg_audits if a.get("multi_scale_scan")]
                if not scans:
                    continue
                # Collect values by k
                by_k = defaultdict(list)
                for scan in scans:
                    for entry in scan:
                        k = entry.get("k")
                        v = entry.get(metric_key)
                        if k is not None and v is not None:
                            by_k[k].append(v)

                cells = []
                for k in all_k:
                    vs = by_k.get(k, [])
                    if vs:
                        med = safe_median(vs)
                        cells.append(fmt(med))
                    else:
                        cells.append("—")
                lines.append(f"| {display} | " + " | ".join(cells) + " |")
            lines.append("")

    # ── Outlier detection ──
    lines.append("## Flagged Runs (Outliers)")
    lines.append("")

    flag_metrics = [
        ("sigma", "highest σ_π"),
        ("n_chiral", "highest chirality"),
        ("partition_stats.effective_k", "highest partition effective_k"),
        ("partition_flip_count", "highest partition flips"),
    ]

    for metric_path, desc in flag_metrics:
        vals_with_id = []
        for a in audits:
            v = get_metric(a, metric_path)
            if v is not None:
                vals_with_id.append((v, a))
        if not vals_with_id:
            continue

        vals_with_id.sort(key=lambda x: x[0], reverse=True)
        lines.append(f"### Top 5 by {desc}")
        for v, a in vals_with_id[:5]:
            cfg = cfg_display_label(a)
            lines.append(f"- {cfg} (s={a.get('seed')}, n={a.get('n')}): {fmt(v)}")
        lines.append("")

    # Write report
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w") as f:
        f.write("\n".join(lines))
    print(f"Report written to {output} ({len(lines)} lines)")


if __name__ == "__main__":
    parser = ArgumentParser(description="Generate stage report from audit JSONL")
    parser.add_argument("--input", type=Path, required=True, help="audits.jsonl file")
    parser.add_argument("--output", type=Path, required=True, help="Output report.md")
    parser.add_argument("--stage", default="", help="Stage name for report title")
    args = parser.parse_args()

    audits = load_audits(args.input)
    print(f"Loaded {len(audits)} audit records")
    generate_report(audits, args.output, args.stage)
