from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
import sys
import time

from ..benchmarks.classical_master_test import run_classical_master_test_benchmark
from ..benchmarks.epistemic_six_state import run_epistemic_six_state_benchmark
from ..benchmarks.parity_context_witness import run_parity_context_witness_benchmark
from ..reporting.flattening_report import write_flattening_intervention_report
from ..reporting.hidden_record_report import write_hidden_record_intervention_report
from ..run_registry import (
    build_run_manifest,
    create_run_directory,
    detect_git_commit,
    get_repo_root,
    repo_relative_path,
    write_run_manifest,
)
from ..schemas.result_note import ResultNote
from ..search.sweep import run_search_sweep

BENCHMARK_SUITE_ID = "benchmark_suite"
INTERVENTION_SUITE_ID = "intervention_suite"
SEARCH_SUITE_ID = "search_suite"
LEAN_BUILD_SUITE_ID = "lean_build"

SEARCH_SWEEP_PATH = "experiments/configs/search/small-sweep.json"
HIDDEN_RECORD_INTERVENTION_PATH = (
    "experiments/instances/interventions/hidden-record-route-split/intervention.json"
)
FLATTENING_INTERVENTION_PATH = (
    "experiments/instances/interventions/flattening-completion-branch/intervention.json"
)


@dataclass(slots=True)
class SuiteRunArtifacts:
    run_id: str
    run_dir: str
    summary_path: str
    note_path: str
    result_note_path: str
    manifest_path: str
    summary: dict[str, object]


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_result_note(path: Path, note: ResultNote) -> None:
    path.write_text(
        json.dumps(note.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _load_json(root: Path, relpath: str) -> dict[str, object]:
    return json.loads((root / relpath).read_text(encoding="utf-8"))


def _suite_artifacts(
    *,
    suite_label: str,
    summary_name: str,
    note_name: str,
    category: str,
    timestamp: str | None,
    root: str | Path | None,
) -> tuple[Path, str, str, Path, Path, Path, Path]:
    repo_root = Path(root).resolve() if root is not None else None
    run_dir, run_id, manifest_timestamp = create_run_directory(
        category=category,
        label=suite_label,
        timestamp=timestamp,
        root=repo_root,
    )
    summary_path = run_dir / summary_name
    note_path = run_dir / note_name
    result_note_path = run_dir / "result-note.json"
    manifest_path = run_dir / "run-manifest.json"
    return (
        run_dir,
        run_id,
        manifest_timestamp,
        summary_path,
        note_path,
        result_note_path,
        manifest_path,
    )


def run_benchmark_suite(
    *,
    category: str,
    label: str | None = None,
    seed: int = 0,
    timestamp: str | None = None,
    root: str | Path | None = None,
    command: list[str] | None = None,
) -> SuiteRunArtifacts:
    suite_label = label or "benchmark-suite"
    (
        run_dir,
        run_id,
        manifest_timestamp,
        summary_path,
        note_path,
        result_note_path,
        manifest_path,
    ) = _suite_artifacts(
        suite_label=suite_label,
        summary_name="benchmark-suite-summary.json",
        note_name="benchmark-suite-note.md",
        category=category,
        timestamp=timestamp,
        root=root,
    )
    effective_root = run_dir.parents[2]

    classical = run_classical_master_test_benchmark(
        category="benchmarks",
        label=f"{suite_label}-classical-master-test",
        seed=seed,
        timestamp=timestamp,
        root=effective_root,
        command=[
            sys.executable,
            "-m",
            "sixbirds_event",
            "benchmarks",
            "classical-master-test",
            "run",
        ],
    )
    epistemic = run_epistemic_six_state_benchmark(
        category="benchmarks",
        label=f"{suite_label}-epistemic-six-state",
        seed=seed,
        timestamp=timestamp,
        root=effective_root,
        command=[
            sys.executable,
            "-m",
            "sixbirds_event",
            "benchmarks",
            "epistemic-six-state",
            "run",
        ],
    )
    parity = run_parity_context_witness_benchmark(
        category="benchmarks",
        label=f"{suite_label}-parity-context-witness",
        seed=seed,
        timestamp=timestamp,
        root=effective_root,
        command=[
            sys.executable,
            "-m",
            "sixbirds_event",
            "benchmarks",
            "parity-context-witness",
            "run",
        ],
    )

    benchmark_entries = []
    for bundle in [classical, epistemic, parity]:
        index_payload = _load_json(effective_root, bundle.index_path)
        benchmark_entries.append(
            {
                "benchmark_id": bundle.benchmark_id,
                "status": "succeeded",
                "run_id": bundle.run_id,
                "run_dir": bundle.run_dir,
                "index_path": bundle.index_path,
                "note_path": bundle.note_path,
                "result_note_path": bundle.result_note_path,
                "manifest_path": bundle.manifest_path,
                "key_artifacts": index_payload.get("output_paths", {}),
                "metrics": index_payload.get("metrics_summary", bundle.metrics_summary),
            }
        )

    summary = {
        "suite_id": BENCHMARK_SUITE_ID,
        "suite_run_id": run_id,
        "benchmarks": benchmark_entries,
        "benchmark_ids": [entry["benchmark_id"] for entry in benchmark_entries],
        "benchmark_completion_statuses": {
            entry["benchmark_id"]: entry["status"] for entry in benchmark_entries
        },
    }
    _write_json(summary_path, summary)

    output_paths = {
        "summary": repo_relative_path(summary_path, root=effective_root),
        "note": repo_relative_path(note_path, root=effective_root),
        "result_note": repo_relative_path(result_note_path, root=effective_root),
        "manifest": repo_relative_path(manifest_path, root=effective_root),
    }
    note_lines = [
        "# Benchmark Suite",
        "",
        "## Suite ID",
        f"- Suite ID: `{BENCHMARK_SUITE_ID}`",
        "",
        "## Benchmarks run",
    ]
    for entry in benchmark_entries:
        note_lines.extend(
            [
                f"- `{entry['benchmark_id']}`: run_id=`{entry['run_id']}`, index=`{entry['index_path']}`",
                f"  metrics=`{entry['metrics']}`",
            ]
        )
    note_lines.extend(
        [
            "",
            "## Artifact references",
            f"- Summary: `{output_paths['summary']}`",
            f"- Result note: `{output_paths['result_note']}`",
            f"- Manifest: `{output_paths['manifest']}`",
        ]
    )
    note_path.write_text("\n".join(note_lines) + "\n", encoding="utf-8")

    result_note = ResultNote(
        note_format_version="result-note.v1",
        note_id=f"note_{run_id}",
        run_id=run_id,
        instance_ids=[entry["benchmark_id"] for entry in benchmark_entries],
        metrics={
            "benchmark_count": len(benchmark_entries),
            "successful_benchmark_count": len(benchmark_entries),
            "parity_gpd_str": parity.metrics_summary["gpd_str"]
            if parity.metrics_summary["gpd_str"] is not None
            else -1.0,
        },
        interpretation=(
            "Benchmark suite orchestrated the existing T12/T13/T14 runners and recorded their bundle-level metrics and artifact references."
        ),
        caveats=[
            "Suite summaries aggregate existing benchmark outputs and do not recompute sub-run metrics.",
            "Explicit sub-run statuses and artifact references are preserved from the underlying benchmark bundles.",
        ],
        artifact_refs=output_paths,
        metadata={
            "suite_id": BENCHMARK_SUITE_ID,
            "benchmark_ids": [entry["benchmark_id"] for entry in benchmark_entries],
        },
    )
    _write_result_note(result_note_path, result_note)

    manifest = build_run_manifest(
        run_id=run_id,
        timestamp=manifest_timestamp,
        command=command
        or [
            sys.executable,
            "-m",
            "sixbirds_event",
            "pipeline",
            "run-benchmarks",
        ],
        seed=seed,
        input_artifacts={},
        output_artifacts={
            "summary": output_paths["summary"],
            "note": output_paths["note"],
            "result_note": output_paths["result_note"],
        },
        status="succeeded",
        git_commit=detect_git_commit(root=effective_root),
        metadata={
            "analysis_kind": "benchmark_suite",
            "suite_id": BENCHMARK_SUITE_ID,
            "sub_run_count": len(benchmark_entries),
        },
    )
    write_run_manifest(manifest, run_dir=run_dir)

    return SuiteRunArtifacts(
        run_id=run_id,
        run_dir=repo_relative_path(run_dir, root=effective_root),
        summary_path=output_paths["summary"],
        note_path=output_paths["note"],
        result_note_path=output_paths["result_note"],
        manifest_path=output_paths["manifest"],
        summary=summary,
    )


def run_intervention_suite(
    *,
    category: str,
    label: str | None = None,
    seed: int = 0,
    timestamp: str | None = None,
    root: str | Path | None = None,
    command: list[str] | None = None,
) -> SuiteRunArtifacts:
    suite_label = label or "intervention-suite"
    (
        run_dir,
        run_id,
        manifest_timestamp,
        summary_path,
        note_path,
        result_note_path,
        manifest_path,
    ) = _suite_artifacts(
        suite_label=suite_label,
        summary_name="intervention-suite-summary.json",
        note_name="intervention-suite-note.md",
        category=category,
        timestamp=timestamp,
        root=root,
    )
    effective_root = run_dir.parents[2]

    hidden = write_hidden_record_intervention_report(
        intervention_path=HIDDEN_RECORD_INTERVENTION_PATH,
        category="interventions",
        label=f"{suite_label}-hidden-record",
        seed=seed,
        timestamp=timestamp,
        root=effective_root,
        command=[
            sys.executable,
            "-m",
            "sixbirds_event",
            "interventions",
            "hidden-record",
            HIDDEN_RECORD_INTERVENTION_PATH,
        ],
    )
    flattening = write_flattening_intervention_report(
        intervention_path=FLATTENING_INTERVENTION_PATH,
        category="interventions",
        label=f"{suite_label}-flattening",
        seed=seed,
        timestamp=timestamp,
        root=effective_root,
        command=[
            sys.executable,
            "-m",
            "sixbirds_event",
            "interventions",
            "flattening",
            FLATTENING_INTERVENTION_PATH,
        ],
    )

    intervention_entries = [
        {
            "intervention_id": hidden.summary["intervention_id"],
            "status": "succeeded",
            "run_id": hidden.run_id,
            "summary_path": hidden.summary_path,
            "note_path": hidden.note_path,
            "result_note_path": hidden.result_note_path,
            "manifest_path": hidden.manifest_path,
            "before": hidden.summary["before"],
            "after": hidden.summary["after"],
            "conclusion": hidden.conclusion,
        },
        {
            "intervention_id": flattening.summary["intervention_id"],
            "status": "succeeded",
            "run_id": flattening.run_id,
            "summary_path": flattening.summary_path,
            "note_path": flattening.note_path,
            "result_note_path": flattening.result_note_path,
            "manifest_path": flattening.manifest_path,
            "before": flattening.summary["before"],
            "after": flattening.summary["after"],
            "conclusion": flattening.conclusion,
        },
    ]

    summary = {
        "suite_id": INTERVENTION_SUITE_ID,
        "suite_run_id": run_id,
        "intervention_ids": [
            entry["intervention_id"] for entry in intervention_entries
        ],
        "interventions": intervention_entries,
        "intervention_completion_statuses": {
            entry["intervention_id"]: entry["status"] for entry in intervention_entries
        },
    }
    _write_json(summary_path, summary)

    output_paths = {
        "summary": repo_relative_path(summary_path, root=effective_root),
        "note": repo_relative_path(note_path, root=effective_root),
        "result_note": repo_relative_path(result_note_path, root=effective_root),
        "manifest": repo_relative_path(manifest_path, root=effective_root),
    }
    note_lines = [
        "# Intervention Suite",
        "",
        "## Suite ID",
        f"- Suite ID: `{INTERVENTION_SUITE_ID}`",
        "",
        "## Interventions run",
    ]
    for entry in intervention_entries:
        note_lines.extend(
            [
                f"- `{entry['intervention_id']}`: run_id=`{entry['run_id']}`, conclusion=`{entry['conclusion']}`",
                f"  before=`{entry['before']}`",
                f"  after=`{entry['after']}`",
            ]
        )
    note_lines.extend(
        [
            "",
            "## Artifact references",
            f"- Summary: `{output_paths['summary']}`",
            f"- Result note: `{output_paths['result_note']}`",
            f"- Manifest: `{output_paths['manifest']}`",
        ]
    )
    note_path.write_text("\n".join(note_lines) + "\n", encoding="utf-8")

    result_note = ResultNote(
        note_format_version="result-note.v1",
        note_id=f"note_{run_id}",
        run_id=run_id,
        instance_ids=[entry["intervention_id"] for entry in intervention_entries],
        metrics={
            "intervention_count": len(intervention_entries),
            "hidden_record_disappeared": hidden.conclusion == "disappeared",
            "flattening_repairable": flattening.conclusion == "repairable",
        },
        interpretation=(
            "Intervention suite orchestrated the existing hidden-record and flattening/completion intervention runners and preserved their before/after conclusions."
        ),
        caveats=[
            "Suite summaries reuse the underlying intervention comparison outputs without recomputing sub-run metrics.",
            "Statuses such as solved, unsolved, insufficient_data, and not_applicable are preserved from sub-runs.",
        ],
        artifact_refs=output_paths,
        metadata={
            "suite_id": INTERVENTION_SUITE_ID,
            "intervention_ids": [
                entry["intervention_id"] for entry in intervention_entries
            ],
        },
    )
    _write_result_note(result_note_path, result_note)

    manifest = build_run_manifest(
        run_id=run_id,
        timestamp=manifest_timestamp,
        command=command
        or [
            sys.executable,
            "-m",
            "sixbirds_event",
            "pipeline",
            "run-interventions",
        ],
        seed=seed,
        input_artifacts={
            "hidden_record_intervention": HIDDEN_RECORD_INTERVENTION_PATH,
            "flattening_intervention": FLATTENING_INTERVENTION_PATH,
        },
        output_artifacts={
            "summary": output_paths["summary"],
            "note": output_paths["note"],
            "result_note": output_paths["result_note"],
        },
        status="succeeded",
        git_commit=detect_git_commit(root=effective_root),
        metadata={
            "analysis_kind": "intervention_suite",
            "suite_id": INTERVENTION_SUITE_ID,
            "sub_run_count": len(intervention_entries),
        },
    )
    write_run_manifest(manifest, run_dir=run_dir)

    return SuiteRunArtifacts(
        run_id=run_id,
        run_dir=repo_relative_path(run_dir, root=effective_root),
        summary_path=output_paths["summary"],
        note_path=output_paths["note"],
        result_note_path=output_paths["result_note"],
        manifest_path=output_paths["manifest"],
        summary=summary,
    )


def run_search_suite(
    *,
    category: str,
    label: str | None = None,
    seed: int = 0,
    timestamp: str | None = None,
    root: str | Path | None = None,
    command: list[str] | None = None,
) -> SuiteRunArtifacts:
    suite_label = label or "search-suite"
    (
        run_dir,
        run_id,
        manifest_timestamp,
        summary_path,
        note_path,
        result_note_path,
        manifest_path,
    ) = _suite_artifacts(
        suite_label=suite_label,
        summary_name="search-suite-summary.json",
        note_name="search-suite-note.md",
        category=category,
        timestamp=timestamp,
        root=root,
    )
    effective_root = run_dir.parents[2]

    sweep = run_search_sweep(
        sweep_path=SEARCH_SWEEP_PATH,
        category="search",
        label=f"{suite_label}-small-sweep",
        seed=seed,
        timestamp=timestamp,
        root=effective_root,
        command=[
            sys.executable,
            "-m",
            "sixbirds_event",
            "search",
            "run-sweep",
            SEARCH_SWEEP_PATH,
        ],
    )
    sweep_summary = _load_json(effective_root, sweep.summary_path)

    summary = {
        "suite_id": SEARCH_SUITE_ID,
        "suite_run_id": run_id,
        "sweep_config_path": SEARCH_SWEEP_PATH,
        "sub_run_id": sweep.run_id,
        "key_artifact_refs": {
            "atlas_csv": sweep.atlas_csv_path,
            "atlas_json": sweep.atlas_json_path,
            "regime_counts": sweep.regime_counts_path,
            "summary": sweep.summary_path,
            "note": sweep.note_path,
            "result_note": sweep.result_note_path,
            "manifest": sweep.manifest_path,
        },
        "regime_counts": sweep.regime_counts,
        "notable_unsolved_or_insufficient_data_counts": sweep_summary.get(
            "notable_unsolved_or_insufficient_data_counts", {}
        ),
    }
    _write_json(summary_path, summary)

    output_paths = {
        "summary": repo_relative_path(summary_path, root=effective_root),
        "note": repo_relative_path(note_path, root=effective_root),
        "result_note": repo_relative_path(result_note_path, root=effective_root),
        "manifest": repo_relative_path(manifest_path, root=effective_root),
    }
    note_lines = [
        "# Search Suite",
        "",
        "## Suite ID",
        f"- Suite ID: `{SEARCH_SUITE_ID}`",
        "",
        "## Sweep run",
        f"- Sweep config: `{SEARCH_SWEEP_PATH}`",
        f"- Sub-run ID: `{sweep.run_id}`",
        f"- Regime counts: `{sweep.regime_counts}`",
        f"- Notable unsolved / insufficient-data counts: `{summary['notable_unsolved_or_insufficient_data_counts']}`",
        "",
        "## Artifact references",
        f"- Summary: `{output_paths['summary']}`",
        f"- Result note: `{output_paths['result_note']}`",
        f"- Manifest: `{output_paths['manifest']}`",
    ]
    note_path.write_text("\n".join(note_lines) + "\n", encoding="utf-8")

    result_note = ResultNote(
        note_format_version="result-note.v1",
        note_id=f"note_{run_id}",
        run_id=run_id,
        instance_ids=[SEARCH_SUITE_ID],
        metrics={
            "point_count": int(sum(sweep.regime_counts.values())),
            "globally_packageable_count": sweep.regime_counts.get(
                "globally_packageable", 0
            ),
            "multi_context_but_extendable_count": sweep.regime_counts.get(
                "multi_context_but_extendable", 0
            ),
        },
        interpretation=(
            "Search suite orchestrated the committed compact sweep and recorded the suite-level regime counts and atlas artifact references."
        ),
        caveats=[
            "Suite summaries preserve unsolved, insufficient_data, and not_applicable statuses from the sweep outputs.",
            "RM remains diagnostic-only where present in the underlying sweep outputs.",
        ],
        artifact_refs=output_paths,
        metadata={
            "suite_id": SEARCH_SUITE_ID,
            "sweep_config_path": SEARCH_SWEEP_PATH,
        },
    )
    _write_result_note(result_note_path, result_note)

    manifest = build_run_manifest(
        run_id=run_id,
        timestamp=manifest_timestamp,
        command=command
        or [
            sys.executable,
            "-m",
            "sixbirds_event",
            "pipeline",
            "run-search",
        ],
        seed=seed,
        input_artifacts={"sweep": SEARCH_SWEEP_PATH},
        output_artifacts={
            "summary": output_paths["summary"],
            "note": output_paths["note"],
            "result_note": output_paths["result_note"],
        },
        status="succeeded",
        git_commit=detect_git_commit(root=effective_root),
        metadata={
            "analysis_kind": "search_suite",
            "suite_id": SEARCH_SUITE_ID,
            "sub_run_count": 1,
        },
    )
    write_run_manifest(manifest, run_dir=run_dir)

    return SuiteRunArtifacts(
        run_id=run_id,
        run_dir=repo_relative_path(run_dir, root=effective_root),
        summary_path=output_paths["summary"],
        note_path=output_paths["note"],
        result_note_path=output_paths["result_note"],
        manifest_path=output_paths["manifest"],
        summary=summary,
    )


def run_lean_build(
    *,
    category: str,
    label: str | None = None,
    seed: int = 0,
    timestamp: str | None = None,
    root: str | Path | None = None,
    command: list[str] | None = None,
) -> SuiteRunArtifacts:
    suite_label = label or "lean-build"
    (
        run_dir,
        run_id,
        manifest_timestamp,
        summary_path,
        note_path,
        result_note_path,
        manifest_path,
    ) = _suite_artifacts(
        suite_label=suite_label,
        summary_name="lean-build-summary.json",
        note_name="lean-build-note.md",
        category=category,
        timestamp=timestamp,
        root=root,
    )
    effective_root = run_dir.parents[2]
    source_repo_root = get_repo_root()
    lean_root = source_repo_root / "lean"
    if not lean_root.exists():
        summary = {
            "suite_id": LEAN_BUILD_SUITE_ID,
            "suite_run_id": run_id,
            "lean_build_command": "cd lean && lake build",
            "modules_checked": [],
            "success": False,
            "skipped": True,
            "skip_reason": "lean directory is absent in this repository setup",
            "return_code": None,
            "duration_seconds": 0.0,
            "stdout_tail": [],
            "stderr_tail": [],
        }
        _write_json(summary_path, summary)

        output_paths = {
            "summary": repo_relative_path(summary_path, root=effective_root),
            "note": repo_relative_path(note_path, root=effective_root),
            "result_note": repo_relative_path(result_note_path, root=effective_root),
            "manifest": repo_relative_path(manifest_path, root=effective_root),
        }
        note_lines = [
            "# Lean Build",
            "",
            "## Suite ID",
            f"- Suite ID: `{LEAN_BUILD_SUITE_ID}`",
            "",
            "## Build command",
            "- `cd lean && lake build`",
            "",
            "## Build result",
            "- Success: `False`",
            "- Skipped: `True`",
            f"- Skip reason: `{summary['skip_reason']}`",
            "",
            "## Artifact references",
            f"- Summary: `{output_paths['summary']}`",
            f"- Result note: `{output_paths['result_note']}`",
            f"- Manifest: `{output_paths['manifest']}`",
        ]
        note_path.write_text("\n".join(note_lines) + "\n", encoding="utf-8")

        result_note = ResultNote(
            note_format_version="result-note.v1",
            note_id=f"note_{run_id}",
            run_id=run_id,
            instance_ids=[LEAN_BUILD_SUITE_ID],
            metrics={
                "success": summary["success"],
                "skipped": summary["skipped"],
                "skip_reason": summary["skip_reason"],
                "return_code": summary["return_code"],
                "duration_seconds": summary["duration_seconds"],
            },
            interpretation=(
                "Lean build suite was skipped because the repository no longer carries the Lean source tree."
            ),
            caveats=[
                "This repository setup intentionally omits the Lean project and records the omission as a skipped suite run.",
            ],
            artifact_refs=output_paths,
            metadata={"suite_id": LEAN_BUILD_SUITE_ID, "skipped": True},
        )
        _write_result_note(result_note_path, result_note)

        manifest = build_run_manifest(
            run_id=run_id,
            timestamp=manifest_timestamp,
            command=command
            or [
                sys.executable,
                "-m",
                "sixbirds_event",
                "pipeline",
                "run-lean",
            ],
            seed=seed,
            input_artifacts={},
            output_artifacts={
                "summary": output_paths["summary"],
                "note": output_paths["note"],
                "result_note": output_paths["result_note"],
            },
            status="skipped",
            git_commit=detect_git_commit(root=effective_root),
            metadata={
                "analysis_kind": "lean_build_suite",
                "suite_id": LEAN_BUILD_SUITE_ID,
                "skipped": True,
                "skip_reason": summary["skip_reason"],
            },
        )
        write_run_manifest(manifest, run_dir=run_dir)
        return SuiteRunArtifacts(
            run_id=run_id,
            run_dir=repo_relative_path(run_dir, root=effective_root),
            summary_path=output_paths["summary"],
            note_path=output_paths["note"],
            result_note_path=output_paths["result_note"],
            manifest_path=output_paths["manifest"],
            summary=summary,
        )

    build_command = ["lake", "build"]
    started = time.monotonic()
    result = subprocess.run(
        build_command,
        cwd=lean_root,
        capture_output=True,
        text=True,
        check=False,
    )
    duration_seconds = round(time.monotonic() - started, 6)
    summary = {
        "suite_id": LEAN_BUILD_SUITE_ID,
        "suite_run_id": run_id,
        "lean_build_command": "cd lean && lake build",
        "modules_checked": ["lake build"],
        "success": result.returncode == 0,
        "skipped": False,
        "return_code": result.returncode,
        "duration_seconds": duration_seconds,
        "stdout_tail": result.stdout.strip().splitlines()[-10:],
        "stderr_tail": result.stderr.strip().splitlines()[-10:],
    }
    _write_json(summary_path, summary)

    output_paths = {
        "summary": repo_relative_path(summary_path, root=effective_root),
        "note": repo_relative_path(note_path, root=effective_root),
        "result_note": repo_relative_path(result_note_path, root=effective_root),
        "manifest": repo_relative_path(manifest_path, root=effective_root),
    }
    note_lines = [
        "# Lean Build",
        "",
        "## Suite ID",
        f"- Suite ID: `{LEAN_BUILD_SUITE_ID}`",
        "",
        "## Build command",
        "- `cd lean && lake build`",
        "",
        "## Build result",
        f"- Success: `{summary['success']}`",
        f"- Return code: `{summary['return_code']}`",
        f"- Duration seconds: `{summary['duration_seconds']}`",
        "",
        "## Artifact references",
        f"- Summary: `{output_paths['summary']}`",
        f"- Result note: `{output_paths['result_note']}`",
        f"- Manifest: `{output_paths['manifest']}`",
    ]
    note_path.write_text("\n".join(note_lines) + "\n", encoding="utf-8")

    result_note = ResultNote(
        note_format_version="result-note.v1",
        note_id=f"note_{run_id}",
        run_id=run_id,
        instance_ids=[LEAN_BUILD_SUITE_ID],
        metrics={
            "success": summary["success"],
            "return_code": summary["return_code"],
            "duration_seconds": summary["duration_seconds"],
        },
        interpretation=(
            "Lean build suite ran the repository Lean project build command and recorded the build status and timing."
        ),
        caveats=[
            "This suite wraps the existing Lean project build and does not formalize or re-run individual theorem scripts separately.",
        ],
        artifact_refs=output_paths,
        metadata={"suite_id": LEAN_BUILD_SUITE_ID},
    )
    _write_result_note(result_note_path, result_note)

    manifest = build_run_manifest(
        run_id=run_id,
        timestamp=manifest_timestamp,
        command=command
        or [
            sys.executable,
            "-m",
            "sixbirds_event",
            "pipeline",
            "run-lean",
        ],
        seed=seed,
        input_artifacts={},
        output_artifacts={
            "summary": output_paths["summary"],
            "note": output_paths["note"],
            "result_note": output_paths["result_note"],
        },
        status="succeeded" if result.returncode == 0 else "failed",
        git_commit=detect_git_commit(root=effective_root),
        metadata={
            "analysis_kind": "lean_build_suite",
            "suite_id": LEAN_BUILD_SUITE_ID,
            "return_code": result.returncode,
            "skipped": False,
        },
    )
    write_run_manifest(manifest, run_dir=run_dir)

    return SuiteRunArtifacts(
        run_id=run_id,
        run_dir=repo_relative_path(run_dir, root=effective_root),
        summary_path=output_paths["summary"],
        note_path=output_paths["note"],
        result_note_path=output_paths["result_note"],
        manifest_path=output_paths["manifest"],
        summary=summary,
    )
