#!/usr/bin/env python3
"""Analyze n=256 data from the PICA characterization campaign.

Run when n=256 logs appear in the campaign directory:
  python3 analysis/analyze_n256.py

Collects KEY_AUDIT_JSON from n=256 logs, compares to n=128 baselines,
and produces a structured report.
"""
import json, re, glob, sys, os
from collections import defaultdict
import statistics

CAMPAIGN_DIR = "lab/runs/pica_rerun_20260221_1ffaab6"

def parse_log_file(filepath):
    """Parse a single log file for all data: audits, macro lines, and config names.

    Returns (audits, macros, hash_to_name) where:
      - audits: list of KEY_AUDIT_JSON records (with _log_file, _stage)
      - macros: list of KEY_100_MACRO records (normalized to audit field names)
      - hash_to_name: dict mapping pica_config_hash to cell name
    """
    audits = []
    macros = []
    hash_to_name = {}

    # Track current cell name for matching with audit JSON
    current_cell = None

    seed_m = re.search(r'_s(\d+)_', os.path.basename(filepath))
    seed = int(seed_m.group(1)) if seed_m else -1
    stage = "unknown"
    if "stage_03" in filepath:
        stage = "stage_03_producers_consumers"
    elif "stage_05" in filepath:
        stage = "stage_05_scale_phase"

    try:
        with open(filepath) as f:
            for line in f:
                line = line.strip()

                # Parse KEY_100_DYN for cell name
                if "KEY_100_DYN" in line and "scale=256" in line:
                    m = re.search(r'cell=(\S+)', line)
                    if m:
                        current_cell = m.group(1)

                # Parse KEY_AUDIT_JSON
                if "KEY_AUDIT_JSON" in line:
                    idx = line.find('{')
                    if idx >= 0:
                        try:
                            rec = json.loads(line[idx:])
                            rec["_log_file"] = filepath
                            rec["_stage"] = stage
                            if current_cell:
                                rec["pica_config_name"] = current_cell
                                h = rec.get("pica_config_hash")
                                if h:
                                    hash_to_name[h] = current_cell
                            audits.append(rec)
                        except json.JSONDecodeError:
                            pass

                # Parse KEY_100_MACRO
                if "KEY_100_MACRO" in line and "level=L0" in line:
                    data = {"seed": seed, "n": 256, "_log_file": filepath, "_stage": stage}
                    for key in ["cell", "frob", "gap", "sigma_pi", "sigma_u",
                                "max_asym", "cyc_mean", "cyc_max", "n_chiral", "trans_ep",
                                "macro_n"]:
                        m2 = re.search(rf'{key}=(\S+)', line)
                        if m2:
                            try:
                                data[key] = float(m2.group(1))
                            except ValueError:
                                data[key] = m2.group(1)
                    # Normalize field names
                    if "cell" in data:
                        data["pica_config_name"] = data.pop("cell")
                    if "frob" in data:
                        data["frob_from_rank1"] = data.pop("frob")
                    if "gap" in data:
                        data["macro_gap"] = data.pop("gap")
                    if "sigma_pi" in data:
                        data["sigma"] = data.pop("sigma_pi")
                    macros.append(data)
    except (FileNotFoundError, PermissionError):
        pass

    return audits, macros, hash_to_name

def collect_n256_data():
    """Collect all n=256 data from campaign logs (audits + macro fallback).

    Returns (records, hash_to_name) where records have unified field names.
    Prefers KEY_AUDIT_JSON; falls back to KEY_100_MACRO.
    """
    all_audits = []
    all_macros = []
    hash_to_name = {}

    for stage in ["stage_03_producers_consumers", "stage_05_scale_phase"]:
        pattern = os.path.join(CAMPAIGN_DIR, stage, "*n256*.log")
        for f in sorted(glob.glob(pattern)):
            audits, macros, h2n = parse_log_file(f)
            all_audits.extend(audits)
            all_macros.extend(macros)
            hash_to_name.update(h2n)

    # Prefer audits; if we have both, use audits and add config names from macros
    if all_audits:
        # Fill in config names for any audits missing them
        for rec in all_audits:
            if "pica_config_name" not in rec:
                h = rec.get("pica_config_hash")
                if h and h in hash_to_name:
                    rec["pica_config_name"] = hash_to_name[h]
        return all_audits, hash_to_name
    else:
        return all_macros, hash_to_name

def collect_key100_macro(logfile):
    """Fallback: collect KEY_100_MACRO lines if no KEY_AUDIT_JSON."""
    records = []
    seed_m = re.search(r'_s(\d+)_', logfile)
    seed = int(seed_m.group(1)) if seed_m else -1
    with open(logfile) as f:
        for line in f:
            if "KEY_100_MACRO" in line and "level=L0" in line:
                data = {"seed": seed, "n": 256, "_log_file": logfile}
                for key in ["cell", "frob", "gap", "sigma_pi", "sigma_u",
                            "max_asym", "n_chiral", "trans_ep"]:
                    m = re.search(rf'{key}=(\S+)', line)
                    if m:
                        try:
                            data[key] = float(m.group(1))
                        except ValueError:
                            data[key] = m.group(1)
                # Map to audit field names
                if "cell" in data:
                    data["pica_config_name"] = data.pop("cell")
                if "frob" in data:
                    data["frob_from_rank1"] = data.pop("frob")
                if "gap" in data:
                    data["macro_gap"] = data.pop("gap")
                if "sigma_pi" in data:
                    data["sigma"] = data.pop("sigma_pi")
                records.append(data)
    return records

def load_config_map():
    """Load config hash→name mapping from pre-built map."""
    map_file = os.path.join(CAMPAIGN_DIR, "config_hash_map.json")
    if os.path.exists(map_file):
        with open(map_file) as f:
            return {int(k): v for k, v in json.load(f).items()}
    return {}

def load_n128_baselines():
    """Load n=128 data from merged audits for comparison."""
    records = []
    merged = os.path.join(CAMPAIGN_DIR, "audits_merged_v6.jsonl")
    if not os.path.exists(merged):
        return records
    config_map = load_config_map()
    with open(merged) as f:
        for line in f:
            line = line.strip()
            if line:
                rec = json.loads(line)
                if rec.get("n") == 128:
                    h = rec.get("pica_config_hash")
                    if h and h in config_map and "pica_config_name" not in rec:
                        rec["pica_config_name"] = config_map[h]
                    records.append(rec)
    return records

def median(vals):
    return statistics.median(vals) if vals else 0

def iqr(vals):
    if len(vals) < 4:
        return (min(vals), max(vals)) if vals else (0, 0)
    s = sorted(vals)
    q1 = s[len(s)//4]
    q3 = s[3*len(s)//4]
    return (q1, q3)

def analyze(records, n128_records):
    """Produce analysis report."""
    # Group by config name (prefer name, fall back to hash)
    by_config = defaultdict(list)
    for r in records:
        name = r.get("pica_config_name")
        if not name:
            h = r.get("pica_config_hash", "unknown")
            name = f"hash_{h}"
        by_config[name].append(r)

    # Group n128 by config for comparison
    n128_by_config = defaultdict(list)
    for r in n128_records:
        name = r.get("pica_config_name")
        if not name:
            h = r.get("pica_config_hash", "unknown")
            name = f"hash_{h}"
        n128_by_config[name].append(r)

    print("=" * 80)
    print("PICA n=256 Analysis Report")
    print("=" * 80)
    print(f"\nTotal n=256 records: {len(records)}")
    print(f"Configs: {len(by_config)}")
    print(f"n=128 baseline records: {len(n128_records)}")

    # Get baseline frob at n=256
    bl_frobs = [r.get("frob_from_rank1", 0) for r in by_config.get("baseline", [])]
    bl_sigmas = [r.get("sigma", 0) for r in by_config.get("baseline", [])]
    bl_med_frob = median(bl_frobs) if bl_frobs else 0.52
    bl_med_sigma = median(bl_sigmas) if bl_sigmas else 0.19

    print(f"\nBaseline n=256: frob={bl_med_frob:.4f}, sigma={bl_med_sigma:.4f}")

    # Table header
    print(f"\n{'Config':<20} {'N':>3} {'frob':>8} {'gap':>8} {'sigma':>8} {'d_frob':>8} "
          f"{'%>1.0':>6} {'n128_frob':>10}")
    print("-" * 85)

    for cfg in sorted(by_config.keys()):
        runs = by_config[cfg]
        n = len(runs)
        frobs = [r.get("frob_from_rank1", 0) for r in runs]
        gaps = [r.get("macro_gap", 0) for r in runs]
        sigmas = [r.get("sigma", 0) for r in runs]

        med_f = median(frobs)
        med_g = median(gaps)
        med_s = median(sigmas)
        d_frob = med_f - bl_med_frob
        pct_above_1 = 100 * sum(1 for f in frobs if f > 1.0) / n if n > 0 else 0

        # n=128 comparison
        n128_frobs = [r.get("frob_from_rank1", 0) for r in n128_by_config.get(cfg, [])]
        n128_med = median(n128_frobs) if n128_frobs else None
        n128_str = f"{n128_med:.4f}" if n128_med is not None else "N/A"

        print(f"{cfg:<20} {n:>3} {med_f:>8.4f} {med_g:>8.4f} {med_s:>8.4f} "
              f"{d_frob:>+8.4f} {pct_above_1:>5.0f}% {n128_str:>10}")

    # Key comparisons
    print("\n" + "=" * 80)
    print("KEY COMPARISONS")
    print("=" * 80)

    # 1. Partition competition at n=256
    a14_frobs = [r.get("frob_from_rank1", 0) for r in by_config.get("A14_only", [])]
    if a14_frobs:
        print(f"\n1. Partition competition: A14_only frob={median(a14_frobs):.4f} "
              f"(n=128: 1.327)")
        pct = sum(1 for f in a14_frobs if f > 1.0) / len(a14_frobs) * 100
        print(f"   {pct:.0f}% of seeds >1.0 (was 70% at n=128)")

    # 2. A13_A14_A19 triplet
    triplet_frobs = [r.get("frob_from_rank1", 0) for r in by_config.get("A13_A14_A19", [])]
    if triplet_frobs:
        print(f"\n2. A13_A14_A19 triplet: frob={median(triplet_frobs):.4f} "
              f"(n=128: 1.376)")

    # 3. Boost sweep
    boost_configs = [c for c in by_config.keys() if c.startswith("boost_")]
    if boost_configs:
        print(f"\n3. Boost sweep:")
        for bc in sorted(boost_configs):
            frobs = [r.get("frob_from_rank1", 0) for r in by_config[bc]]
            sigmas = [r.get("sigma", 0) for r in by_config[bc]]
            print(f"   {bc}: frob={median(frobs):.4f}, sigma={median(sigmas):.4f}")

    # 4. REV detection
    print(f"\n4. REV detection (sigma=0 seeds):")
    for cfg in sorted(by_config.keys()):
        runs = by_config[cfg]
        rev_count = sum(1 for r in runs if r.get("sigma", 1) < 0.001)
        if rev_count > 0:
            print(f"   {cfg}: {rev_count}/{len(runs)} REV seeds")

    # 5. Scale comparison
    print(f"\n5. Scale comparison (n=128 → n=256):")
    for cfg in sorted(by_config.keys()):
        n256_frobs = [r.get("frob_from_rank1", 0) for r in by_config[cfg]]
        n128_frobs = [r.get("frob_from_rank1", 0) for r in n128_by_config.get(cfg, [])]
        if n256_frobs and n128_frobs:
            ratio = median(n256_frobs) / median(n128_frobs) if median(n128_frobs) > 0 else 0
            print(f"   {cfg}: {median(n128_frobs):.4f} → {median(n256_frobs):.4f} "
                  f"(ratio={ratio:.3f})")

def main():
    # Collect n=256 data (unified: audits preferred, macro fallback)
    records, hash_to_name = collect_n256_data()

    if not records:
        print("No n=256 data found yet. Logs available:")
        for stage in ["stage_03_producers_consumers", "stage_05_scale_phase"]:
            pattern = os.path.join(CAMPAIGN_DIR, stage, "*.log")
            for f in sorted(glob.glob(pattern)):
                size = os.path.getsize(f)
                print(f"  {os.path.basename(f)} ({size} bytes)")
        sys.exit(0)

    # Merge with pre-built config map
    prebuilt = load_config_map()
    hash_to_name.update(prebuilt)

    # Apply config names to records
    for rec in records:
        if "pica_config_name" not in rec:
            h = rec.get("pica_config_hash")
            if h and h in hash_to_name:
                rec["pica_config_name"] = hash_to_name[h]

    print(f"Config map: {len(hash_to_name)} entries (from logs + prebuilt)")

    # Load n=128 baselines (already has config names from load_n128_baselines)
    n128_records = load_n128_baselines()

    # Analyze
    analyze(records, n128_records)

if __name__ == "__main__":
    main()
