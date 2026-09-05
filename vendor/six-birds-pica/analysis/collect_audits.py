#!/usr/bin/env python3
"""
Collect KEY_AUDIT_JSON records from experiment log files.

Parses log files for KEY_AUDIT_JSON lines, annotates with config names
from KEY_100_CFG lines, and writes audits.jsonl.

Usage:
    python analysis/collect_audits.py --input-dir lab/runs/stage_01 --output audits.jsonl
    python analysis/collect_audits.py --merge dir1/audits.jsonl dir2/audits.jsonl --output merged.jsonl
"""

import hashlib
import json
import sys
from pathlib import Path
from argparse import ArgumentParser

# Known label aliases: map variant labels to their canonical name.
# This prevents label→hash collisions when the same config appears
# under different names in different experiments.
LABEL_ALIASES = {
    "A15_only": "baseline",        # EXP-103 mislabels baseline() as A15_only
    "baseline_ref": "baseline",    # some stages use baseline_ref
}


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
        # Deterministic hash of the full config JSON (sorted keys)
        canonical = json.dumps(pica_config, sort_keys=True, separators=(",", ":"))
        return "full:" + hashlib.sha256(canonical.encode()).hexdigest()[:16]
    pch = record.get("pica_config_hash")
    if pch is not None:
        return f"hash:{pch}"
    label = record.get("_cfg_label") or record.get("config_name") or "?"
    return f"label:{normalize_label(label)}"


def normalize_label(label: str) -> str:
    """Apply alias normalization to a config label."""
    return LABEL_ALIASES.get(label, label)


def extract_cfg_labels(log_path: Path) -> dict:
    """Extract pica_config_hash -> label mappings from KEY_100_DYN lines.

    KEY_100_DYN lines contain 'cell=<label>' and can be paired with
    the audit record by (seed, scale, cell) matching.
    We look for KEY_100_MACRO lines which have 'cell=<label>' to build
    a mapping from the log file.
    """
    labels = {}
    try:
        with open(log_path) as f:
            for line in f:
                if line.startswith("KEY_100_MACRO ") or line.startswith("KEY_100_DYN "):
                    parts = line.strip().split()
                    cell = None
                    seed = None
                    scale = None
                    for p in parts:
                        if p.startswith("cell="):
                            cell = p.split("=", 1)[1]
                        elif p.startswith("seed="):
                            seed = p.split("=", 1)[1]
                        elif p.startswith("scale="):
                            scale = p.split("=", 1)[1]
                    if cell and seed and scale:
                        labels[(seed, scale, cell)] = cell
    except Exception:
        pass
    return labels


def extract_audits_from_log(log_path: Path) -> list:
    """Parse KEY_AUDIT_JSON payloads from a single log and keep one canonical record."""

    def _to_num(v):
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str):
            try:
                return float(v)
            except ValueError:
                return None
        return None

    def _parse_json_blocks(blob: str) -> list[dict]:
        """Extract JSON objects following KEY_AUDIT_JSON using brace-count parsing."""
        out = []
        token = "KEY_AUDIT_JSON"
        start = 0
        while True:
            i = blob.find(token, start)
            if i == -1:
                break

            j = i + len(token)
            while j < len(blob) and blob[j].isspace():
                j += 1
            if j >= len(blob):
                start = i + len(token)
                continue

            if blob[j] != "{":
                # Fallback: tolerate prefix text after token, find first '{' on same line.
                line_end = blob.find("\n", j)
                if line_end == -1:
                    line_end = len(blob)
                k = blob.find("{", j, line_end)
                if k == -1:
                    start = line_end
                    continue
                j = k

            depth = 0
            k = j
            in_str = False
            esc = False
            while k < len(blob):
                ch = blob[k]
                if in_str:
                    if esc:
                        esc = False
                    elif ch == "\\":
                        esc = True
                    elif ch == '"':
                        in_str = False
                else:
                    if ch == '"':
                        in_str = True
                    elif ch == "{":
                        depth += 1
                    elif ch == "}":
                        depth -= 1
                        if depth == 0:
                            k += 1
                            break
                k += 1

            if depth != 0:
                print(f"WARN: unterminated KEY_AUDIT_JSON block in {log_path}", file=sys.stderr)
                start = j + 1
                continue

            payload = blob[j:k]
            try:
                out.append(json.loads(payload))
            except json.JSONDecodeError as e:
                print(f"WARN: bad JSON in {log_path}: {e}", file=sys.stderr)
            start = k
        return out

    def _record_rank(rec: dict, idx: int):
        """Canonical selection key: max(step), fallback max(t), then latest index."""
        step = _to_num(rec.get("step"))
        tval = _to_num(rec.get("t"))
        has_step = 1 if step is not None else 0
        has_t = 1 if tval is not None else 0
        step_key = step if step is not None else float("-inf")
        t_key = tval if tval is not None else float("-inf")
        return (has_step, step_key, has_t, t_key, idx)

    # First pass: collect config labels from KEY_100_DYN lines
    cfg_labels = []
    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if line.startswith("KEY_100_DYN "):
                    parts = line.strip().split()
                    cell = None
                    for p in parts:
                        if p.startswith("cell="):
                            cell = p.split("=", 1)[1]
                        elif p.startswith("cfg_label="):
                            cell = p.split("=", 1)[1]
                    if cell:
                        cfg_labels.append(cell)
    except Exception:
        pass

    try:
        blob = Path(log_path).read_text(encoding="utf-8", errors="replace")
        parsed = _parse_json_blocks(blob)
    except Exception as e:
        print(f"WARN: error reading {log_path}: {e}", file=sys.stderr)
        return []

    if not parsed:
        return []

    # Keep one canonical audit record per log file.
    best_idx, best_record = max(enumerate(parsed), key=lambda x: _record_rank(x[1], x[0]))
    best_record["_log_file"] = str(log_path)
    if "config_name" in best_record and best_record["config_name"]:
        best_record["_cfg_label"] = best_record["config_name"]
    elif best_idx < len(cfg_labels):
        best_record["_cfg_label"] = cfg_labels[best_idx]
    elif cfg_labels:
        best_record["_cfg_label"] = cfg_labels[-1]

    return [best_record]


def collect_from_directory(input_dir: Path, output: Path):
    """Collect all audits from log files in a directory tree."""
    all_audits = []
    log_files = sorted(input_dir.rglob("*.log"))
    print(f"Scanning {len(log_files)} log files in {input_dir}...")
    for log_file in log_files:
        audits = extract_audits_from_log(log_file)
        all_audits.extend(audits)

    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w") as f:
        for audit in all_audits:
            f.write(json.dumps(audit, default=str) + "\n")

    print(f"Collected {len(all_audits)} audit records -> {output}")


def _exp_sort_key(exp_id: str) -> tuple:
    """Extract numeric suffix from exp_id for sorting (e.g. 'EXP-107' → 107)."""
    if not exp_id:
        return (0,)
    import re
    m = re.search(r"(\d+)", exp_id)
    return (int(m.group(1)),) if m else (0,)


def merge_audits(input_files: list, output: Path, dedup_cross_exp: bool = True):
    """Merge multiple audits.jsonl files, deduplicating.

    Primary dedup key: (config_identity, seed, n, exp_id).
    config_identity uses the full pica_config JSON when available (captures all
    parameters), falling back to pica_config_hash (covers 24/36 params) or label.
    Labels are normalized through LABEL_ALIASES to fix known misnamings.

    Cross-experiment dedup is on by default: when the same (config, seed, n) appears
    in multiple experiments, only the record from the highest-numbered experiment is
    kept. Pass dedup_cross_exp=False to disable.
    """
    seen = set()
    merged = []
    cross_exp_dupes = 0
    total_input = 0
    for path in input_files:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                total_input += 1
                record = json.loads(line)
                # Normalize labels through alias table
                if "_cfg_label" in record:
                    record["_cfg_label"] = normalize_label(record["_cfg_label"])
                if "config_name" in record and record["config_name"]:
                    record["config_name"] = normalize_label(record["config_name"])
                if dedup_cross_exp:
                    # Primary key: config_identity captures full config when available.
                    # Under default behavior we still collapse exact same-experiment identities.
                    cfg_id = config_identity(record)
                    key = (
                        cfg_id,
                        record.get("seed"),
                        record.get("n"),
                        record.get("exp_id"),
                    )
                    if key not in seen:
                        seen.add(key)
                        merged.append(record)
                else:
                    # Provenance-preserving mode: keep all records as-is.
                    merged.append(record)

    # Detect cross-experiment duplicates (same seed/n/config, different exp_id)
    cross_exp_keys = {}
    for r in merged:
        cfg_id = config_identity(r)
        cross_key = (cfg_id, r.get("seed"), r.get("n"))
        cross_exp_keys.setdefault(cross_key, []).append(r)

    # Cross-experiment duplicate means same (config, seed, n) appears under >1 exp_id.
    cross_dupes = {
        k: v for k, v in cross_exp_keys.items()
        if len({r.get("exp_id") for r in v}) > 1
    }
    if cross_dupes:
        print(f"WARNING: {len(cross_dupes)} cross-experiment duplicates detected "
              f"(same seed/n/config in multiple experiments):", file=sys.stderr)
        for k, recs in list(cross_dupes.items())[:5]:
            exps = [r.get("exp_id", "?") for r in recs]
            labels = set(r.get("_cfg_label", "?") for r in recs)
            print(f"  cfg={k[0][:30]} s={k[1]} n={k[2]}: {exps} labels={labels}",
                  file=sys.stderr)
        if len(cross_dupes) > 5:
            print(f"  ... and {len(cross_dupes)-5} more", file=sys.stderr)

        if dedup_cross_exp:
            # Keep only the record from the highest-numbered experiment
            best = {}  # cross_key → record with highest exp_id
            for r in merged:
                cfg_id = config_identity(r)
                cross_key = (cfg_id, r.get("seed"), r.get("n"))
                if cross_key not in best:
                    best[cross_key] = r
                else:
                    prev_exp = best[cross_key].get("exp_id", "")
                    curr_exp = r.get("exp_id", "")
                    if _exp_sort_key(curr_exp) > _exp_sort_key(prev_exp):
                        best[cross_key] = r
            cross_exp_dupes = len(merged) - len(best)
            merged = list(best.values())

    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w") as f:
        for r in merged:
            f.write(json.dumps(r, default=str) + "\n")

    dropped = total_input - len(merged)
    print(f"Merged {len(merged)} unique records from {total_input} input records "
          f"({dropped} duplicates dropped, {cross_exp_dupes} cross-exp deduped) "
          f"-> {output}")


if __name__ == "__main__":
    parser = ArgumentParser(description="Collect KEY_AUDIT_JSON from experiment logs")
    parser.add_argument("--input-dir", type=Path, help="Directory to scan for .log files")
    parser.add_argument("--merge", nargs="+", type=Path, help="JSONL files to merge")
    parser.add_argument("--output", type=Path, required=True, help="Output audits.jsonl")
    parser.add_argument("--no-dedup-cross-exp", action="store_true", default=False,
                        help="Disable cross-experiment deduplication. By default, when the "
                             "same (config, seed, n) appears in multiple experiments, only "
                             "the record from the highest-numbered experiment is kept.")

    args = parser.parse_args()

    if args.merge:
        merge_audits(args.merge, args.output, dedup_cross_exp=not args.no_dedup_cross_exp)
    elif args.input_dir:
        collect_from_directory(args.input_dir, args.output)
    else:
        parser.print_help()
