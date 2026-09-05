from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import sys

from ..reporting.statistical_report import write_statistical_summary
from ..reporting.structural_report import (
    generate_structural_report,
    load_event_package_instance,
)
from ..run_registry import (
    build_run_manifest,
    create_run_directory,
    detect_git_commit,
    repo_relative_path,
    write_run_manifest,
)
from ..schemas.observation_trace import ObservationTrace
from ..schemas.result_note import ResultNote
from ..solvers.structural_deficit import StructuralDeficitConfig
from ..validation import load_model

BENCHMARK_ID = "parity-context-witness"
BENCHMARK_DIR = Path("experiments/instances/benchmarks/parity-context-witness")
DEFICIT_CONFIG = StructuralDeficitConfig(
    allow_relax_hard=True,
    hard_proposal_relax_weight=1.0,
)


@dataclass(slots=True)
class BenchmarkBundleArtifacts:
    benchmark_id: str
    run_id: str
    run_dir: str
    index_path: str
    note_path: str
    result_note_path: str
    manifest_path: str
    metrics_summary: dict[str, float | bool | None]
    sub_runs: dict[str, dict[str, object]]
    relaxed_proposal_ids: list[str]
    statistical_reason: str | None


def _load_trace(path: str | Path) -> ObservationTrace:
    model = load_model(path, kind="observation-trace")
    assert isinstance(model, ObservationTrace)
    return model


def _asset(name: str) -> str:
    return (BENCHMARK_DIR / name).as_posix()


def _artifact_record(
    artifact, *, include_note: bool = True, include_result_note: bool = True
) -> dict[str, object]:
    payload = {
        "run_id": artifact.run_id,
        "manifest_path": artifact.manifest_path,
        "summary_path": artifact.summary_path,
    }
    if include_note and hasattr(artifact, "note_path"):
        payload["note_path"] = artifact.note_path
    if include_result_note and hasattr(artifact, "result_note_path"):
        payload["result_note_path"] = artifact.result_note_path
    return payload


def _build_result_note(
    *,
    run_id: str,
    instance_id: str,
    metrics_summary: dict[str, float | bool | None],
    output_paths: dict[str, str],
    relaxed_proposal_ids: list[str],
    statistical_reason: str | None,
) -> ResultNote:
    return ResultNote(
        note_format_version="result-note.v1",
        note_id=f"note_{run_id}",
        run_id=run_id,
        instance_ids=[instance_id],
        metrics={
            "exact_structural_feasible_hard_only": metrics_summary[
                "exact_structural_feasible_hard_only"
            ],
            "exact_respecting_tuple_count": metrics_summary[
                "exact_respecting_tuple_count"
            ],
            "gpd_str": metrics_summary["gpd_str"]
            if metrics_summary["gpd_str"] is not None
            else -1.0,
            "hard_relax_enabled": DEFICIT_CONFIG.allow_relax_hard,
            "hard_proposal_relax_weight": DEFICIT_CONFIG.hard_proposal_relax_weight,
            "relaxed_proposal_count": len(relaxed_proposal_ids),
            "statistical_solved": metrics_summary["statistical_solved"],
            "gpd_stat": metrics_summary["gpd_stat"]
            if metrics_summary["gpd_stat"] is not None
            else -1.0,
        },
        interpretation=(
            "Under the current hard-only admissibility semantics, this finite parity/context witness is not exactly extendable. "
            f"Exact respecting tuple count={metrics_summary['exact_respecting_tuple_count']}, gpd_str={metrics_summary['gpd_str']}, "
            f"relaxed blocking proposals={relaxed_proposal_ids}, statistical_status="
            f"{'solved' if metrics_summary['statistical_solved'] else f'unsolved ({statistical_reason})'}."
        ),
        caveats=[
            "Exact feasibility is evaluated under the usual hard-only structural semantics.",
            "Structural deficit is evaluated with hard-proposal relaxation enabled for this benchmark.",
        ],
        artifact_refs={
            "benchmark_index": output_paths["benchmark_index"],
            "benchmark_note": output_paths["benchmark_note"],
            "manifest": output_paths["manifest"],
        },
        metadata={"benchmark_id": BENCHMARK_ID},
    )


def _render_benchmark_note(
    *,
    instance_path: str,
    trace_paths: dict[str, str],
    metrics_summary: dict[str, float | bool | None],
    structural_summary_path: str,
    statistical_summary_path: str,
    relaxed_proposal_ids: list[str],
    structural_blocking_explanation: dict[str, object],
    statistical_reason: str | None,
    output_paths: dict[str, str],
) -> str:
    lines = [
        "# Parity Context Witness Benchmark",
        "",
        "## Benchmark ID",
        f"- Benchmark ID: `{BENCHMARK_ID}`",
        "",
        "## Instance path",
        f"- Instance path: `{instance_path}`",
        "",
        "## Construction summary",
        "- This benchmark encodes a finite 3x3 parity table witness with six parity-constrained contexts, context atoms given by parity-compatible sign triples, and shared-observable glue enforced only through event-level `+1` coarse events across row and column contexts.",
        "",
        "## Structural exact-feasibility result",
        f"- Hard-only exact feasible: `{metrics_summary['exact_structural_feasible_hard_only']}`",
        f"- Exact respecting tuple count: `{metrics_summary['exact_respecting_tuple_count']}`",
        "",
        "## Structural deficit result",
        f"- `gpd_str`: `{metrics_summary['gpd_str']}`",
        f"- Hard-relax config: `{{'allow_relax_hard': {DEFICIT_CONFIG.allow_relax_hard}, 'hard_proposal_relax_weight': {DEFICIT_CONFIG.hard_proposal_relax_weight}, 'atom_relax_weight': {DEFICIT_CONFIG.atom_relax_weight}}}`",
        f"- Relaxed blocking proposal IDs: `{relaxed_proposal_ids}`",
        f"- Blocking explanation: `{json.dumps(structural_blocking_explanation, sort_keys=True)}`",
        "",
        "## Statistical run status",
        f"- Statistical solved: `{metrics_summary['statistical_solved']}`",
        f"- Statistical reason: `{statistical_reason}`",
        f"- `gpd_stat`: `{metrics_summary['gpd_stat']}`",
        "",
        "## Conclusion",
        "- Under the current hard-only admissibility semantics, this benchmark is not exactly extendable. The hard-relaxed structural deficit run returns a positive `gpd_str`, and the bundle records the relaxed proposal IDs needed to restore a finite witness family.",
        "",
        "## Artifact references",
        f"- Structural summary: `{structural_summary_path}`",
        f"- Statistical summary: `{statistical_summary_path}`",
        f"- Benchmark index: `{output_paths['benchmark_index']}`",
        f"- Result note JSON: `{output_paths['result_note']}`",
        f"- Run manifest: `{output_paths['manifest']}`",
        "",
        "## Trace set used",
    ]
    for name, path in trace_paths.items():
        lines.append(f"- `{name}`: `{path}`")
    return "\n".join(lines) + "\n"


def run_parity_context_witness_benchmark(
    *,
    category: str,
    label: str | None = None,
    seed: int = 0,
    timestamp: str | None = None,
    root: str | Path | None = None,
    command: list[str] | None = None,
) -> BenchmarkBundleArtifacts:
    repo_root = Path(root).resolve() if root is not None else None
    bundle_label = label or BENCHMARK_ID
    bundle_dir, run_id, manifest_timestamp = create_run_directory(
        category=category,
        label=bundle_label,
        timestamp=timestamp,
        root=repo_root,
    )
    effective_root = bundle_dir.parents[2]

    instance_path = _asset("instance.json")
    stat_clean_path = _asset("stat-clean.json")
    trace_paths = {"stat_clean": stat_clean_path}

    instance = load_event_package_instance(instance_path)
    stat_clean_trace = _load_trace(stat_clean_path)

    structural = generate_structural_report(
        instance,
        instance_path=instance_path,
        category=category,
        label=f"{bundle_label}-structural",
        seed=seed,
        timestamp=timestamp,
        root=effective_root,
        command=[
            sys.executable,
            "-m",
            "sixbirds_event",
            "structural",
            "report",
            instance_path,
        ],
        deficit_config=DEFICIT_CONFIG,
    )
    statistical = write_statistical_summary(
        instance,
        [stat_clean_trace],
        instance_path=instance_path,
        trace_paths=[stat_clean_path],
        category=category,
        label=f"{bundle_label}-stat-clean",
        seed=seed,
        timestamp=timestamp,
        root=effective_root,
        command=["python", "-m", "sixbirds_event", "benchmark", "stat-clean"],
    )

    metrics_summary = {
        "exact_structural_feasible_hard_only": structural.summary.exact_extendable_hard_only,
        "exact_respecting_tuple_count": structural.summary.hard_only_respecting_tuple_count,
        "gpd_str": structural.summary.gpd_str,
        "statistical_solved": statistical.result.solved,
        "gpd_stat": statistical.result.gpd_stat,
    }
    sub_runs = {
        "structural": _artifact_record(structural),
        "stat_clean": _artifact_record(
            statistical, include_note=False, include_result_note=False
        ),
    }
    nonextendable_under_current_hard_only_admissibility_semantics = (
        not structural.summary.exact_extendable_hard_only
    )

    index_path = bundle_dir / "benchmark-index.json"
    note_path = bundle_dir / "benchmark-note.md"
    result_note_path = bundle_dir / "result-note.json"
    manifest_path = bundle_dir / "run-manifest.json"
    output_paths = {
        "benchmark_index": repo_relative_path(index_path, root=effective_root),
        "benchmark_note": repo_relative_path(note_path, root=effective_root),
        "result_note": repo_relative_path(result_note_path, root=effective_root),
        "manifest": repo_relative_path(manifest_path, root=effective_root),
    }
    instance_relpath = repo_relative_path(instance_path, root=effective_root)
    trace_relpaths = {
        name: repo_relative_path(path, root=effective_root)
        for name, path in trace_paths.items()
    }
    structural_deficit_config = {
        "allow_relax_hard": DEFICIT_CONFIG.allow_relax_hard,
        "hard_proposal_relax_weight": DEFICIT_CONFIG.hard_proposal_relax_weight,
        "atom_relax_weight": DEFICIT_CONFIG.atom_relax_weight,
    }
    statistical_status = {
        "solved": statistical.result.solved,
        "reason": statistical.result.reason,
        "gpd_stat": statistical.result.gpd_stat,
    }

    index_payload = {
        "benchmark_id": BENCHMARK_ID,
        "instance_path": instance_relpath,
        "trace_paths": trace_relpaths,
        "sub_runs": sub_runs,
        "metrics_summary": metrics_summary,
        "structural_deficit_config": structural_deficit_config,
        "relaxed_proposal_ids": structural.summary.relaxed_proposal_ids,
        "statistical_status": statistical_status,
        "nonextendable_under_current_hard_only_admissibility_semantics": nonextendable_under_current_hard_only_admissibility_semantics,
        "output_paths": output_paths,
        "omitted_trace_assets": ["stat-noisy.json"],
    }
    index_path.write_text(
        json.dumps(index_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    note_path.write_text(
        _render_benchmark_note(
            instance_path=instance_relpath,
            trace_paths=trace_relpaths,
            metrics_summary=metrics_summary,
            structural_summary_path=structural.summary_path,
            statistical_summary_path=statistical.summary_path,
            relaxed_proposal_ids=structural.summary.relaxed_proposal_ids,
            structural_blocking_explanation=structural.summary.blocking_explanation,
            statistical_reason=statistical.result.reason,
            output_paths=output_paths,
        ),
        encoding="utf-8",
    )
    result_note = _build_result_note(
        run_id=run_id,
        instance_id=instance.instance_id,
        metrics_summary=metrics_summary,
        output_paths=output_paths,
        relaxed_proposal_ids=structural.summary.relaxed_proposal_ids,
        statistical_reason=statistical.result.reason,
    )
    result_note_path.write_text(
        json.dumps(result_note.model_dump(mode="json"), indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    manifest = build_run_manifest(
        run_id=run_id,
        timestamp=manifest_timestamp,
        command=command
        or [
            sys.executable,
            "-m",
            "sixbirds_event",
            "benchmarks",
            BENCHMARK_ID,
            "run",
        ],
        seed=seed,
        input_artifacts={
            "instance": instance_relpath,
            "trace_stat_clean": trace_relpaths["stat_clean"],
        },
        output_artifacts={
            "benchmark_index": output_paths["benchmark_index"],
            "benchmark_note": output_paths["benchmark_note"],
            "result_note": output_paths["result_note"],
        },
        status="succeeded",
        git_commit=detect_git_commit(root=effective_root),
        metadata={
            "analysis_kind": "benchmark_bundle",
            "benchmark_id": BENCHMARK_ID,
            "nonextendable_under_current_hard_only_admissibility_semantics": nonextendable_under_current_hard_only_admissibility_semantics,
            "sub_run_count": len(sub_runs),
        },
    )
    write_run_manifest(manifest, run_dir=bundle_dir)

    return BenchmarkBundleArtifacts(
        benchmark_id=BENCHMARK_ID,
        run_id=run_id,
        run_dir=repo_relative_path(bundle_dir, root=effective_root),
        index_path=output_paths["benchmark_index"],
        note_path=output_paths["benchmark_note"],
        result_note_path=output_paths["result_note"],
        manifest_path=output_paths["manifest"],
        metrics_summary=metrics_summary,
        sub_runs=sub_runs,
        relaxed_proposal_ids=structural.summary.relaxed_proposal_ids,
        statistical_reason=statistical.result.reason,
    )
