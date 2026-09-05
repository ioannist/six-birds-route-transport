#!/usr/bin/env python3
"""Generate Wave 1 job manifest for campaign_v3.

FULL REGENERATION: all old data was deleted (pre-SLEM-fix binary).
Every experiment × every scale × every config × every seed. No shortcuts.

Step count: n * 2000 (5x reduction from old n * 10000).
Timing estimates with new step count:
  n=32:  ~1-2s per config
  n=64:  ~3-5s per config
  n=128: ~4-6min per config
  n=256: ~30-40min per config
"""

import json
from collections import Counter
from pathlib import Path

STAGE = "wave_1"
MANIFEST_PATH = Path("lab/runs/campaign_v3/wave_1/manifest.json")
jobs = []

SEEDS = list(range(10))
ALL_SCALES = [32, 64, 128]


def add(exp, seed, scale, config=None):
    job = {"exp": exp, "seed": seed, "scale": scale, "stage": STAGE}
    if config:
        job["config"] = config
    job["env"] = {"SIX_BIRDS_AUDIT_RICH": "1"}
    jobs.append(job)


# ── Config lists (must match runner exactly) ──

EXP100_CONFIGS = [
    "baseline",
    "A1_P1-P1", "A2_P1-P2", "A3_P1-P3", "A4_P1-P4",
    "A5_P1-P5", "A6_P1-P6", "A7_P2-P1", "A8_P2-P2",
    "A9_P2-P3", "A11_P2-P5", "A12_P2-P6", "A13_P3-P6",
]  # 13 configs (baseline + 12 individual cells; A10 = baseline)

EXP101_CONFIGS = [
    "baseline", "sbrc", "mixer", "full_action",
    "combo_rm", "combo_structure", "full_action_safe",
]  # 7 configs

EXP106_CONFIGS = [
    "baseline",
    "A13_A18_A19", "boost_0.1", "boost_0.5", "boost_1.0",
    "boost_3.0", "boost_4.0",
    "A13_A3_A19", "A13_A14_A19", "A13_A21_A19",
    "chain_SBRC", "chain_A24", "chain_pkg",
]  # 13 configs

EXP107_CONFIGS = [
    "baseline", "chain", "A13_only", "A24_only", "A25_only",
    "sbrc", "full_action", "full_all", "A11_A22",
    "chain_A24", "chain_SBRC", "A19_only", "P1_row_A13",
]  # 13 configs


# ── Generate ALL jobs ──

# EXP-F1: empty baseline (1 config, no filter needed)
for seed in SEEDS:
    for scale in ALL_SCALES:
        add("EXP-F1", seed, scale)

# EXP-100: single-cell sweep, all 13 configs × all scales
for seed in SEEDS:
    for scale in ALL_SCALES:
        for cfg in EXP100_CONFIGS:
            add("EXP-100", seed, scale, cfg)

# EXP-101: multi-level dynamics, all 7 configs × all scales
for seed in SEEDS:
    for scale in ALL_SCALES:
        for cfg in EXP101_CONFIGS:
            add("EXP-101", seed, scale, cfg)

# EXP-106: phase transition, all 13 configs × all scales
for seed in SEEDS:
    for scale in ALL_SCALES:
        for cfg in EXP106_CONFIGS:
            add("EXP-106", seed, scale, cfg)

# EXP-107: scale dependence, all 13 configs × all scales
for seed in SEEDS:
    for scale in ALL_SCALES:
        for cfg in EXP107_CONFIGS:
            add("EXP-107", seed, scale, cfg)

# EXP-109: Lagrange baseline survey (13 configs internal, no filter — run all)
for seed in SEEDS:
    for scale in ALL_SCALES:
        add("EXP-109", seed, scale)

# EXP-110: Lagrange scale dependence (3 configs internal, no filter)
for seed in SEEDS:
    for scale in ALL_SCALES:
        add("EXP-110", seed, scale)


# ── Summary ──
n32 = sum(1 for j in jobs if j["scale"] == 32)
n64 = sum(1 for j in jobs if j["scale"] == 64)
n128 = sum(1 for j in jobs if j["scale"] == 128)
n256 = sum(1 for j in jobs if j["scale"] == 256)
print(f"Total jobs: {len(jobs)}  (n=32: {n32}, n=64: {n64}, n=128: {n128}, n=256: {n256})")

# Per-experiment breakdown
exp_counts = Counter(j["exp"] for j in jobs)
for exp in sorted(exp_counts):
    scales = Counter(j["scale"] for j in jobs if j["exp"] == exp)
    scale_str = ", ".join(f"n={s}: {c}" for s, c in sorted(scales.items()))
    print(f"  {exp}: {exp_counts[exp]} jobs  ({scale_str})")

# Guard against accidental duplicate jobs.
seen = set()
dupes = []
for j in jobs:
    key = (j["exp"], j["seed"], j["scale"], j.get("config"))
    if key in seen:
        dupes.append(key)
    seen.add(key)
if dupes:
    raise RuntimeError(f"Duplicate jobs in manifest: {dupes[:5]}")

MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
with open(MANIFEST_PATH, "w") as f:
    json.dump(jobs, f, indent=2)
print(f"Written to {MANIFEST_PATH}")

# Timing estimate
cpu_32 = n32 * 2       # ~2s
cpu_64 = n64 * 5       # ~5s
cpu_128 = n128 * 300   # ~5min
cpu_256 = n256 * 2100  # ~35min
total_cpu_h = (cpu_32 + cpu_64 + cpu_128 + cpu_256) / 3600
wall_44 = total_cpu_h / 44
print(f"\nEstimated CPU time: {total_cpu_h:.0f}h")
print(f"Estimated wall time (44 slots): {wall_44:.1f}h")
