#!/usr/bin/env python3
"""
Statistical testing for HYP-202..205 falsification criteria.

Reads audit JSONL, extracts Lagrange/spectral probe values, and runs the
exact tests specified in hypotheses.jsonl:
  - Mann-Whitney U (nonparametric two-sample) with Bonferroni correction
  - Spearman rank correlation
  - Effect-size thresholds

Usage:
    python analysis/test_hypotheses.py --input audits.jsonl --exp EXP-109 [--k 4]

Requires: scipy (for scipy.stats.mannwhitneyu and scipy.stats.spearmanr).
"""

import json
import statistics
import sys
from argparse import ArgumentParser
from collections import defaultdict
from pathlib import Path

from scipy.stats import mannwhitneyu, spearmanr

# Bonferroni: 4 hypotheses (HYP-202..205), family alpha=0.05
N_HYPOTHESES = 4
FAMILY_ALPHA = 0.05
BONFERRONI_ALPHA = FAMILY_ALPHA / N_HYPOTHESES  # 0.0125


def load_audits(path: Path, exp_filter: str = None) -> list:
    """Load and deduplicate audit records from JSONL.

    Dedup key: (experiment, config_identity, n, seed).
    Config identity uses the full serialized pica_config (collision-free), falling
    back to pica_config_hash, then _cfg_label.
    """
    seen = set()
    records = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            exp = rec.get("exp_id", "")
            if exp_filter and exp != exp_filter:
                continue
            # Full pica_config is collision-free; hash and label are fallbacks
            pica_config = rec.get("pica_config")
            if pica_config is not None:
                cfg_id = json.dumps(pica_config, sort_keys=True)
            else:
                cfg_id = str(rec.get("pica_config_hash", rec.get("_cfg_label", "")))
            key = (
                exp,
                cfg_id,
                rec.get("n", 0),
                rec.get("seed", -1),
            )
            if key in seen:
                continue
            seen.add(key)
            records.append(rec)
    return records


def extract_scan_values(records: list, config: str, n: int, k: int, metric: str) -> list:
    """Extract metric values from multi_scale_scan for a given config/n/k.

    Returns one value per (seed) — deduplicates within a single scan by k.
    """
    values = []
    for rec in records:
        if rec.get("_cfg_label") != config:
            continue
        if rec.get("n") != n:
            continue
        scan = rec.get("multi_scale_scan")
        if not scan:
            continue
        # Take first entry matching k (scans should be deduped by k post-fix,
        # but guard against old data with duplicates)
        for entry in scan:
            if entry.get("k") == k:
                v = entry.get(metric)
                if v is not None:
                    values.append(v)
                break  # one value per scan (= per seed)
    return values


def extract_scan_values_pooled(records: list, config: str, n_values: list, k: int, metric: str) -> list:
    """Extract metric values pooled across multiple n values."""
    values = []
    for n in n_values:
        values.extend(extract_scan_values(records, config, n, k, metric))
    return values


def extract_scan_triples(records: list, n: int, metric_x: str, metric_y: str) -> list:
    """Extract (config, x, y) triples across all configs/seeds/k for correlation."""
    triples = []
    for rec in records:
        cfg = rec.get("_cfg_label", "")
        if rec.get("n") != n:
            continue
        scan = rec.get("multi_scale_scan")
        if not scan:
            continue
        for entry in scan:
            vx = entry.get(metric_x)
            vy = entry.get(metric_y)
            if vx is not None and vy is not None:
                triples.append((cfg, vx, vy))
    return triples


def median_diff_mad(a: list, b: list) -> tuple:
    """Compute median difference and effect size (median diff / pooled MAD)."""
    if not a or not b:
        return (float("nan"), float("nan"))
    med_a = statistics.median(a)
    med_b = statistics.median(b)
    diff = med_a - med_b

    # Pooled MAD (median absolute deviation)
    mad_a = statistics.median([abs(x - med_a) for x in a]) if len(a) > 1 else 0
    mad_b = statistics.median([abs(x - med_b) for x in b]) if len(b) > 1 else 0
    pooled_mad = (mad_a + mad_b) / 2
    effect = abs(diff) / pooled_mad if pooled_mad > 1e-15 else float("inf")
    return (diff, effect)


def _med(values):
    """Safe median, rounded."""
    return round(statistics.median(values), 4) if values else None


def test_hyp_202(records: list, k: int):
    """HYP-202: full_action has smaller PLA2 gap than baseline at k=4.

    Spec: "pooled across n=64,128 (10 seeds each)".
    """
    print("\n=== HYP-202: PLA2 gap (full_action < baseline) ===")
    print(f"  Pooled across n=64,128 at k={k}")
    a = extract_scan_values_pooled(records, "full_action", [64, 128], k, "pla2_gap")
    b = extract_scan_values_pooled(records, "baseline", [64, 128], k, "pla2_gap")
    print(f"  full_action: {len(a)} values, median={_med(a)}")
    print(f"  baseline:    {len(b)} values, median={_med(b)}")

    # Also report per-scale breakdown
    for n in [64, 128]:
        an = extract_scan_values(records, "full_action", n, k, "pla2_gap")
        bn = extract_scan_values(records, "baseline", n, k, "pla2_gap")
        print(f"    n={n}: full_action={len(an)} vals (med={_med(an)}), baseline={len(bn)} vals (med={_med(bn)})")

    if len(a) < 3 or len(b) < 3:
        print("  INSUFFICIENT DATA (need >=3 per group)")
        return

    stat, p = mannwhitneyu(a, b, alternative="less")
    diff, effect = median_diff_mad(a, b)
    print(f"  Mann-Whitney U={stat:.1f}, p={p:.6f} (threshold: {BONFERRONI_ALPHA})")
    print(f"  Median diff={diff:.4f}, effect size={effect:.2f} (threshold: 0.5)")

    supported = p < BONFERRONI_ALPHA and effect >= 0.5
    print(f"  VERDICT: {'SUPPORTED' if supported else 'NOT SUPPORTED'}")
    if p >= BONFERRONI_ALPHA:
        print(f"    (p={p:.4f} >= {BONFERRONI_ALPHA})")
    if effect < 0.5:
        print(f"    (effect={effect:.2f} < 0.5)")


def test_hyp_203(records: list, n: int):
    """HYP-203: lagr_geo_r2 correlates positively with frob across all (config,seed,k)."""
    print(f"\n=== HYP-203: geo_r2 ~ frob correlation (n={n}) ===")
    triples = extract_scan_triples(records, n, "frob", "lagr_geo_r2")
    if len(triples) < 10:
        print(f"  INSUFFICIENT DATA ({len(triples)} triples, need >=10)")
        return

    x = [t[1] for t in triples]
    y = [t[2] for t in triples]
    rho, p = spearmanr(x, y)
    print(f"  {len(triples)} (config, seed, k) triples at n={n}")
    print(f"  Spearman rho={rho:.4f}, p={p:.6f} (threshold: {BONFERRONI_ALPHA})")
    print(f"  rho threshold: 0.3")

    supported = p < BONFERRONI_ALPHA and rho >= 0.3
    print(f"  VERDICT: {'SUPPORTED' if supported else 'NOT SUPPORTED'}")
    if p >= BONFERRONI_ALPHA:
        print(f"    (p={p:.4f} >= {BONFERRONI_ALPHA})")
    if rho < 0.3:
        print(f"    (rho={rho:.4f} < 0.3)")


def test_hyp_204(records: list, n: int, k: int):
    """HYP-204: full_action has lower gap_ratio (higher t_rel) than baseline."""
    print(f"\n=== HYP-204: gap_ratio (full_action < baseline, n={n}, k={k}) ===")
    a = extract_scan_values(records, "full_action", n, k, "gap_ratio")
    b = extract_scan_values(records, "baseline", n, k, "gap_ratio")
    print(f"  full_action: {len(a)} values, median={_med(a)}")
    print(f"  baseline:    {len(b)} values, median={_med(b)}")

    if len(a) < 3 or len(b) < 3:
        print("  INSUFFICIENT DATA (need >=3 per group)")
        return

    stat, p = mannwhitneyu(a, b, alternative="less")
    diff, _ = median_diff_mad(a, b)
    print(f"  Mann-Whitney U={stat:.1f}, p={p:.6f} (threshold: {BONFERRONI_ALPHA})")
    print(f"  Median diff={diff:.4f} (threshold: |diff| >= 0.1)")

    supported = p < BONFERRONI_ALPHA and abs(diff) >= 0.1
    print(f"  VERDICT: {'SUPPORTED' if supported else 'NOT SUPPORTED'}")
    if p >= BONFERRONI_ALPHA:
        print(f"    (p={p:.4f} >= {BONFERRONI_ALPHA})")
    if abs(diff) < 0.1:
        print(f"    (|diff|={abs(diff):.4f} < 0.1)")

    # Secondary: spectral_participation and eigen_entropy (reviewer note)
    for probe in ["spectral_participation", "eigen_entropy"]:
        pa = extract_scan_values(records, "full_action", n, k, probe)
        pb = extract_scan_values(records, "baseline", n, k, probe)
        if pa and pb:
            print(f"  Secondary ({probe}): full_action med={_med(pa)}, baseline med={_med(pb)}")


def test_hyp_205(records: list, n: int, k: int):
    """HYP-205: A14_only has lower diff_kl than baseline.

    The claim is directional: partition competition REDUCES diff_kl (makes macro
    kernels closer to diffusion). The criterion requires:
      (a) Mann-Whitney p < 0.0125 for A14 < baseline (one-sided less)
      (b) median KL reduction >= 20% relative to baseline
    Reduction is signed: diff = med(A14) - med(baseline) must be NEGATIVE,
    and |diff| / med(baseline) >= 0.2.
    """
    print(f"\n=== HYP-205: diff_kl (A14_only < baseline, n={n}, k={k}) ===")
    a = extract_scan_values(records, "A14_only", n, k, "lagr_diff_kl")
    b = extract_scan_values(records, "baseline", n, k, "lagr_diff_kl")
    print(f"  A14_only: {len(a)} values, median={_med(a)}")
    print(f"  baseline: {len(b)} values, median={_med(b)}")

    if len(a) < 3 or len(b) < 3:
        print("  INSUFFICIENT DATA (need >=3 per group)")
        return

    stat, p = mannwhitneyu(a, b, alternative="less")
    diff, _ = median_diff_mad(a, b)
    med_a = statistics.median(a)
    med_b = statistics.median(b)

    # Signed reduction: treatment should be LOWER than control
    if med_b > 1e-15:
        rel_reduction = (med_b - med_a) / med_b  # positive if A14 < baseline
    else:
        rel_reduction = 0.0

    print(f"  Mann-Whitney U={stat:.1f}, p={p:.6f} (threshold: {BONFERRONI_ALPHA})")
    print(f"  Median diff (A14 - baseline)={diff:.4f}")
    print(f"  Relative reduction={(rel_reduction):.1%} (threshold: >=20%, positive means A14 lower)")

    # Both conditions: p significant AND genuine reduction of >=20%
    supported = p < BONFERRONI_ALPHA and rel_reduction >= 0.2
    print(f"  VERDICT: {'SUPPORTED' if supported else 'NOT SUPPORTED'}")
    if p >= BONFERRONI_ALPHA:
        print(f"    (p={p:.4f} >= {BONFERRONI_ALPHA})")
    if rel_reduction < 0.2:
        print(f"    (relative reduction={rel_reduction:.1%} < 20%)")
    if rel_reduction < 0:
        print(f"    WARNING: A14_only has HIGHER diff_kl than baseline (opposite of claim)")

    # Secondary replication: A16_only and A17_only
    for cfg in ["A16_only", "A17_only"]:
        c = extract_scan_values(records, cfg, n, k, "lagr_diff_kl")
        if len(c) >= 3 and len(b) >= 3:
            stat2, p2 = mannwhitneyu(c, b, alternative="less")
            med_c = statistics.median(c)
            rr = (med_b - med_c) / med_b if med_b > 1e-15 else 0
            print(f"  Replication ({cfg}): {len(c)} vals, p={p2:.6f}, reduction={rr:.1%}")
        else:
            print(f"  Replication ({cfg}): insufficient data ({len(c)} values)")


def main():
    parser = ArgumentParser(description="Test HYP-202..205 falsification criteria")
    parser.add_argument("--input", type=Path, required=True, help="audits JSONL file")
    parser.add_argument("--exp", type=str, default=None,
                        help="filter to a single experiment ID (e.g., EXP-109)")
    parser.add_argument("--n", type=int, default=128,
                        help="micro kernel size for HYP-203/204/205 (default: 128)")
    parser.add_argument("--k", type=int, default=4,
                        help="coarse-graining scale (default: 4)")
    args = parser.parse_args()

    records = load_audits(args.input, args.exp)
    print(f"Loaded {len(records)} unique audit records from {args.input}")
    if args.exp:
        print(f"Filtered to experiment: {args.exp}")
    print(f"Testing at n={args.n} (HYP-202 pools n=64,128), k={args.k}")
    print(f"Bonferroni alpha = {BONFERRONI_ALPHA} (family={FAMILY_ALPHA}, {N_HYPOTHESES} hypotheses)")

    # Check for required fields (only warn if records exist but lack gap_ratio)
    has_scan = any(rec.get("multi_scale_scan") for rec in records)
    has_gap_ratio = any(
        entry.get("gap_ratio") is not None
        for rec in records
        for entry in (rec.get("multi_scale_scan") or [])
    )
    if has_scan and not has_gap_ratio:
        print("\nWARNING: Records have multi_scale_scan but no gap_ratio values.")
        print("This data may be from the pre-spectral-probe binary.")
        print("HYP-204 requires the corrected binary with SLEM-based spectral probes.")

    test_hyp_202(records, args.k)
    test_hyp_203(records, args.n)
    test_hyp_204(records, args.n, args.k)
    test_hyp_205(records, args.n, args.k)

    print("\n=== Summary ===")
    print("Verdicts use Bonferroni-corrected alpha and effect-size thresholds")
    print("as specified in hypotheses.jsonl HYP-202..205.")
    print("HYP-202: pooled across n=64,128 per spec.")
    print("HYP-204: gap_ratio requires SLEM-corrected binary (post 2026-02-24).")


if __name__ == "__main__":
    main()
