#!/usr/bin/env python3
"""
Batch job launcher for PICA experiments.

Reads a jobs.json file, launches Rust runner processes in parallel,
monitors for completion/failure/timeout, and writes stage_status.json.

Usage:
    python analysis/run_batch.py run --jobs jobs.json [--parallelism 44] [--timeout 172800]
    python analysis/run_batch.py generate stage_01 --output jobs.json
"""

import json
import os
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from argparse import ArgumentParser


def load_jobs(path: Path) -> list:
    """Load jobs from a JSON file. Format: list of {exp, seed, scale, stage, config?, env?}."""
    with open(path) as f:
        return json.load(f)


def run_one_job(job: dict, output_dir: Path, binary: str, timeout: int) -> dict:
    """Execute one job via subprocess. Returns a status dict."""
    stage = job["stage"]
    exp = job["exp"]
    seed = job["seed"]
    scale = job["scale"]
    config = job.get("config")

    # Per-config log files when config is specified
    if config:
        log_path = output_dir / stage / f"{exp}_s{seed}_n{scale}_{config}.log"
    else:
        log_path = output_dir / stage / f"{exp}_s{seed}_n{scale}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["RAYON_NUM_THREADS"] = "1"
    env["OPENBLAS_NUM_THREADS"] = "1"
    env["MKL_NUM_THREADS"] = "1"
    if "env" in job:
        env.update(job["env"])

    cmd = ["stdbuf", "-oL", binary, "--exp", exp, "--seed", str(seed), "--scale", str(scale)]
    if config:
        cmd.extend(["--config", config])
    t0 = time.time()

    # Write stdout directly to file (not captured in memory). stdbuf -oL
    # forces line-buffered output so logs are visible in real-time.
    stderr_path = log_path.with_suffix(".stderr")
    with open(log_path, "w") as stdout_f, open(stderr_path, "w") as stderr_f:
        try:
            result = subprocess.run(
                cmd, stdout=stdout_f, stderr=stderr_f, timeout=timeout, env=env
            )
            wall = round(time.time() - t0, 1)
            # Append stderr to log if any
            stderr_content = stderr_path.read_text() if stderr_path.exists() else ""
            if stderr_content.strip():
                with open(log_path, "a") as f:
                    f.write("\n--- STDERR ---\n")
                    f.write(stderr_content)
            stderr_path.unlink(missing_ok=True)
            status_dict = {
                "exp": exp, "seed": seed, "scale": scale, "stage": stage,
                "status": "ok" if result.returncode == 0 else "failed",
                "wall_secs": wall,
                "log_path": str(log_path),
                "returncode": result.returncode,
            }
            if config:
                status_dict["config"] = config
            return status_dict
        except subprocess.TimeoutExpired:
            wall = round(time.time() - t0, 1)
            # stdout already written to file — partial output is preserved
            stderr_content = stderr_path.read_text() if stderr_path.exists() else ""
            if stderr_content.strip():
                with open(log_path, "a") as f:
                    f.write("\n--- STDERR (partial, timed out) ---\n")
                    f.write(stderr_content)
            stderr_path.unlink(missing_ok=True)
            status_dict = {
                "exp": exp, "seed": seed, "scale": scale, "stage": stage,
                "status": "timeout",
                "wall_secs": wall,
                "log_path": str(log_path),
                "returncode": -1,
            }
            if config:
                status_dict["config"] = config
            return status_dict


def run_batch(jobs: list, output_dir: Path, binary: str,
              parallelism: int = 44, timeout: int = 172800) -> list:
    """Run all jobs in parallel, write stage_status.json per stage."""
    results = []
    total = len(jobs)
    print(f"Launching {total} jobs with parallelism={parallelism}, timeout={timeout}s",
          flush=True)

    with ProcessPoolExecutor(max_workers=parallelism) as pool:
        futures = {
            pool.submit(run_one_job, job, output_dir, binary, timeout): job
            for job in jobs
        }
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            ok = sum(1 for r in results if r["status"] == "ok")
            fail = sum(1 for r in results if r["status"] != "ok")
            cfg_str = f" cfg={result['config']}" if "config" in result else ""
            print(f"  [{ok + fail}/{total}] {result['exp']} s={result['seed']} "
                  f"n={result['scale']}{cfg_str} -> {result['status']} ({result['wall_secs']}s)",
                  flush=True)

    # Write stage_status.json per stage
    stages = {}
    for r in results:
        stages.setdefault(r["stage"], []).append(r)
    for stage, stage_results in stages.items():
        status_path = output_dir / stage / "stage_status.json"
        with open(status_path, "w") as f:
            json.dump({
                "stage": stage,
                "n_jobs": len(stage_results),
                "n_ok": sum(1 for r in stage_results if r["status"] == "ok"),
                "n_failed": sum(1 for r in stage_results if r["status"] == "failed"),
                "n_timeout": sum(1 for r in stage_results if r["status"] == "timeout"),
                "total_wall_secs": round(sum(r["wall_secs"] for r in stage_results), 1),
                "jobs": stage_results,
            }, f, indent=2)
    print(f"\nDone: {sum(1 for r in results if r['status'] == 'ok')}/{total} ok")
    return results


# ── Stage job generators ────────────────────────────────────────────

STAGE_DEFS = {
    "stage_01_core_baselines": {
        "experiments": ["EXP-104"],
        "scales": [32, 64, 128, 256],
        "seeds": [0, 1, 2],
    },
    "stage_02_single_cell": {
        "experiments": ["EXP-100"],
        "scales": [32, 64, 128, 256],
        "seeds": [0, 1, 2],
    },
    "stage_03_producers_consumers": {
        "experiments": ["EXP-102", "EXP-103"],
        "scales": [64, 128],
        "seeds": [0, 1, 2],
    },
    "stage_04_full_system": {
        "experiments": ["EXP-105"],
        "scales": [64, 128, 256],
        "seeds": [0, 1, 2],
    },
    "stage_05_scale_phase": {
        "experiments": ["EXP-107", "EXP-106"],
        "scales": [128, 256],
        "seeds": list(range(10)),
    },
}


def generate_stage_jobs(stage_name: str) -> list:
    """Generate job list for a named stage."""
    if stage_name not in STAGE_DEFS:
        print(f"Unknown stage: {stage_name}. Available: {list(STAGE_DEFS.keys())}")
        sys.exit(1)

    defn = STAGE_DEFS[stage_name]
    jobs = []
    for exp in defn["experiments"]:
        for seed in defn["seeds"]:
            for scale in defn["scales"]:
                job = {
                    "exp": exp, "seed": seed, "scale": scale,
                    "stage": stage_name,
                }
                # Always enable rich scan (multi_scale_scan with Lagrange/spectral probes).
                # The runner now always runs rich scans, but set env var for backward compat.
                job["env"] = {"SIX_BIRDS_AUDIT_RICH": "1"}
                jobs.append(job)
    return jobs


if __name__ == "__main__":
    parser = ArgumentParser(description="Batch job launcher for PICA experiments")
    sub = parser.add_subparsers(dest="command")

    run_p = sub.add_parser("run", help="Run jobs from a file")
    run_p.add_argument("--jobs", type=Path, required=True)
    run_p.add_argument("--parallelism", type=int, default=44)
    run_p.add_argument("--timeout", type=int, default=172800)
    run_p.add_argument("--output-dir", type=Path, default=Path("lab/runs"))
    run_p.add_argument("--binary", default="target/release/runner")

    gen_p = sub.add_parser("generate", help="Generate jobs.json for a stage")
    gen_p.add_argument("stage", choices=list(STAGE_DEFS.keys()))
    gen_p.add_argument("--output", type=Path, required=True)

    args = parser.parse_args()

    if args.command == "run":
        jobs = load_jobs(args.jobs)
        print(f"Loaded {len(jobs)} jobs from {args.jobs}")
        run_batch(jobs, args.output_dir, args.binary, args.parallelism, args.timeout)
    elif args.command == "generate":
        jobs = generate_stage_jobs(args.stage)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w") as f:
            json.dump(jobs, f, indent=2)
        print(f"Generated {len(jobs)} jobs -> {args.output}")
    else:
        parser.print_help()
