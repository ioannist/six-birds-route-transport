from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import sys

from ..reporting.ccd_report import write_ccd_report
from ..reporting.rm_report import write_rm_report
from ..reporting.sec_report import write_sec_report
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
from ..validation import load_model

BENCHMARK_ID = "epistemic-six-state"
BENCHMARK_DIR = Path("experiments/instances/benchmarks/epistemic-six-state")


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


def _load_trace(path: str | Path) -> ObservationTrace:
    model = load_model(path, kind="observation-trace")
    assert isinstance(model, ObservationTrace)
    return model


def _asset(name: str) -> str:
    return (BENCHMARK_DIR / name).as_posix()


def _mean_scored_event_pair_sec(result) -> float | None:
    scores = [
        pair.approx_score
        for pair in result.event_pair_results
        if not pair.insufficient_data and pair.approx_score is not None
    ]
    return sum(scores) / len(scores) if scores else None


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
    extendable_under_current_admissibility_semantics: bool,
) -> ResultNote:
    conclusion = (
        "extendable"
        if extendable_under_current_admissibility_semantics
        else "not extendable"
    )
    return ResultNote(
        note_format_version="result-note.v1",
        note_id=f"note_{run_id}",
        run_id=run_id,
        instance_ids=[instance_id],
        metrics={
            "extendable_under_current_admissibility_semantics": extendable_under_current_admissibility_semantics,
            "gpd_str": metrics_summary["gpd_str"]
            if metrics_summary["gpd_str"] is not None
            else -1.0,
            "gpd_stat_clean": metrics_summary["gpd_stat_clean"]
            if metrics_summary["gpd_stat_clean"] is not None
            else -1.0,
            "gpd_stat_noisy": metrics_summary["gpd_stat_noisy"]
            if metrics_summary["gpd_stat_noisy"] is not None
            else -1.0,
            "ccd_clean": metrics_summary["ccd_clean"]
            if metrics_summary["ccd_clean"] is not None
            else -1.0,
            "ccd_noisy": metrics_summary["ccd_noisy"]
            if metrics_summary["ccd_noisy"] is not None
            else -1.0,
            "sec_clean_mean_approx": metrics_summary["sec_clean_mean_approx"]
            if metrics_summary["sec_clean_mean_approx"] is not None
            else -1.0,
            "sec_noisy_mean_approx": metrics_summary["sec_noisy_mean_approx"]
            if metrics_summary["sec_noisy_mean_approx"] is not None
            else -1.0,
            "rm_clean": metrics_summary["rm_clean"]
            if metrics_summary["rm_clean"] is not None
            else -1.0,
            "rm_noisy": metrics_summary["rm_noisy"]
            if metrics_summary["rm_noisy"] is not None
            else -1.0,
        },
        interpretation=(
            f"Under the current hard-only structural admissibility semantics, this benchmark is {conclusion}; "
            f"gpd_str={metrics_summary['gpd_str']}, clean gpd_stat={metrics_summary['gpd_stat_clean']}, noisy gpd_stat={metrics_summary['gpd_stat_noisy']}. "
            "RM remains diagnostic-only."
        ),
        caveats=[
            "The benchmark is a finite restricted-knowledge calibration case evaluated under the current structural/statistical/audit stack.",
            "RM is diagnostic-only and is not treated as proof of non-extendability.",
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
    sub_runs: dict[str, dict[str, object]],
    output_paths: dict[str, str],
    extendable_under_current_admissibility_semantics: bool,
) -> str:
    conclusion = (
        "extendable"
        if extendable_under_current_admissibility_semantics
        else "not extendable"
    )
    lines = [
        "# Epistemic Six-State Benchmark",
        "",
        "## Benchmark ID",
        f"- Benchmark ID: `{BENCHMARK_ID}`",
        "",
        "## Instance path",
        f"- Instance path: `{instance_path}`",
        "",
        "## Benchmark design summary",
        "- This benchmark encodes a finite six-state restricted-knowledge toy model with three coarse contexts and explicit shared atom-level and general-event equalities, then runs the current structural, statistical, CCD, SEC, and RM stack on clean and mildly noisy synthetic traces.",
        "",
        "## Trace set used",
    ]
    for name, path in trace_paths.items():
        lines.append(f"- `{name}`: `{path}`")
    lines.extend(
        [
            "",
            "## Structural results",
            f"- Hard-only exact structural feasibility: `{metrics_summary['exact_structural_feasible_hard_only']}`",
            f"- `gpd_str`: `{metrics_summary['gpd_str']}`",
            "",
            "## Statistical clean/noisy results",
            f"- Clean `gpd_stat`: `{metrics_summary['gpd_stat_clean']}`",
            f"- Noisy `gpd_stat`: `{metrics_summary['gpd_stat_noisy']}`",
            "",
            "## CCD clean/noisy results",
            f"- Clean overall CCD: `{metrics_summary['ccd_clean']}`",
            f"- Noisy overall CCD: `{metrics_summary['ccd_noisy']}`",
            "",
            "## SEC clean/noisy results",
            f"- Clean mean approximate SEC: `{metrics_summary['sec_clean_mean_approx']}`",
            f"- Noisy mean approximate SEC: `{metrics_summary['sec_noisy_mean_approx']}`",
            "",
            "## RM clean/noisy results",
            f"- Clean overall RM: `{metrics_summary['rm_clean']}`",
            f"- Noisy overall RM: `{metrics_summary['rm_noisy']}`",
            "",
            "## Extendability conclusion",
            f"- Under the current hard-only structural admissibility semantics, this benchmark is `{conclusion}` with `gpd_str = {metrics_summary['gpd_str']}` and clean `gpd_stat = {metrics_summary['gpd_stat_clean']}`.",
            "",
            "## RM interpretation",
            "- RM is diagnostic-only. It reports route dependence in the synthetic route traces and is not treated as proof of non-extendability.",
            "",
            "## Artifact references",
            f"- Benchmark index: `{output_paths['benchmark_index']}`",
            f"- Result note JSON: `{output_paths['result_note']}`",
            f"- Run manifest: `{output_paths['manifest']}`",
        ]
    )
    for name, artifact in sub_runs.items():
        lines.append(
            f"- Sub-run `{name}`: manifest=`{artifact['manifest_path']}`, summary=`{artifact['summary_path']}`"
        )
    return "\n".join(lines) + "\n"


def run_epistemic_six_state_benchmark(
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
    instance = load_event_package_instance(instance_path)

    trace_paths = {
        "stat_clean": _asset("stat-clean.json"),
        "stat_noisy": _asset("stat-noisy.json"),
        "ccd_clean": _asset("ccd-clean.json"),
        "ccd_noisy": _asset("ccd-noisy.json"),
        "sec_clean": _asset("sec-clean.json"),
        "sec_noisy": _asset("sec-noisy.json"),
        "rm_clean": _asset("rm-clean.json"),
        "rm_noisy": _asset("rm-noisy.json"),
    }
    traces = {name: _load_trace(path) for name, path in trace_paths.items()}

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
    )
    stat_clean = write_statistical_summary(
        instance,
        [traces["stat_clean"]],
        instance_path=instance_path,
        trace_paths=[trace_paths["stat_clean"]],
        category=category,
        label=f"{bundle_label}-stat-clean",
        seed=seed,
        timestamp=timestamp,
        root=effective_root,
        command=["python", "-m", "sixbirds_event", "benchmark", "stat-clean"],
    )
    stat_noisy = write_statistical_summary(
        instance,
        [traces["stat_noisy"]],
        instance_path=instance_path,
        trace_paths=[trace_paths["stat_noisy"]],
        category=category,
        label=f"{bundle_label}-stat-noisy",
        seed=seed,
        timestamp=timestamp,
        root=effective_root,
        command=["python", "-m", "sixbirds_event", "benchmark", "stat-noisy"],
    )
    ccd_clean = write_ccd_report(
        traces["ccd_clean"],
        trace_path=trace_paths["ccd_clean"],
        category=category,
        label=f"{bundle_label}-ccd-clean",
        instance=instance,
        instance_path=instance_path,
        seed=seed,
        timestamp=timestamp,
        root=effective_root,
        command=["python", "-m", "sixbirds_event", "benchmark", "ccd-clean"],
    )
    ccd_noisy = write_ccd_report(
        traces["ccd_noisy"],
        trace_path=trace_paths["ccd_noisy"],
        category=category,
        label=f"{bundle_label}-ccd-noisy",
        instance=instance,
        instance_path=instance_path,
        seed=seed,
        timestamp=timestamp,
        root=effective_root,
        command=["python", "-m", "sixbirds_event", "benchmark", "ccd-noisy"],
    )
    sec_clean = write_sec_report(
        instance,
        [traces["sec_clean"]],
        instance_path=instance_path,
        trace_paths=[trace_paths["sec_clean"]],
        category=category,
        label=f"{bundle_label}-sec-clean",
        seed=seed,
        timestamp=timestamp,
        root=effective_root,
        command=["python", "-m", "sixbirds_event", "benchmark", "sec-clean"],
    )
    sec_noisy = write_sec_report(
        instance,
        [traces["sec_noisy"]],
        instance_path=instance_path,
        trace_paths=[trace_paths["sec_noisy"]],
        category=category,
        label=f"{bundle_label}-sec-noisy",
        seed=seed,
        timestamp=timestamp,
        root=effective_root,
        command=["python", "-m", "sixbirds_event", "benchmark", "sec-noisy"],
    )
    rm_clean = write_rm_report(
        [traces["rm_clean"]],
        trace_paths=[trace_paths["rm_clean"]],
        category=category,
        label=f"{bundle_label}-rm-clean",
        instance=instance,
        instance_path=instance_path,
        seed=seed,
        timestamp=timestamp,
        root=effective_root,
        command=["python", "-m", "sixbirds_event", "benchmark", "rm-clean"],
    )
    rm_noisy = write_rm_report(
        [traces["rm_noisy"]],
        trace_paths=[trace_paths["rm_noisy"]],
        category=category,
        label=f"{bundle_label}-rm-noisy",
        instance=instance,
        instance_path=instance_path,
        seed=seed,
        timestamp=timestamp,
        root=effective_root,
        command=["python", "-m", "sixbirds_event", "benchmark", "rm-noisy"],
    )

    extendable_under_current_admissibility_semantics = (
        structural.summary.exact_extendable_hard_only
    )
    metrics_summary = {
        "exact_structural_feasible_hard_only": structural.summary.exact_extendable_hard_only,
        "gpd_str": structural.summary.gpd_str,
        "gpd_stat_clean": stat_clean.result.gpd_stat,
        "gpd_stat_noisy": stat_noisy.result.gpd_stat,
        "ccd_clean": ccd_clean.result.overall_ccd,
        "ccd_noisy": ccd_noisy.result.overall_ccd,
        "sec_clean_mean_approx": _mean_scored_event_pair_sec(sec_clean.result),
        "sec_noisy_mean_approx": _mean_scored_event_pair_sec(sec_noisy.result),
        "rm_clean": rm_clean.result.overall_rm,
        "rm_noisy": rm_noisy.result.overall_rm,
    }

    sub_runs = {
        "structural": _artifact_record(structural),
        "stat_clean": _artifact_record(
            stat_clean, include_note=False, include_result_note=False
        ),
        "stat_noisy": _artifact_record(
            stat_noisy, include_note=False, include_result_note=False
        ),
        "ccd_clean": _artifact_record(ccd_clean),
        "ccd_noisy": _artifact_record(ccd_noisy),
        "sec_clean": _artifact_record(sec_clean),
        "sec_noisy": _artifact_record(sec_noisy),
        "rm_clean": _artifact_record(rm_clean),
        "rm_noisy": _artifact_record(rm_noisy),
    }

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

    index_payload = {
        "benchmark_id": BENCHMARK_ID,
        "instance_path": instance_relpath,
        "trace_paths": trace_relpaths,
        "sub_runs": sub_runs,
        "metrics_summary": metrics_summary,
        "extendable_under_current_admissibility_semantics": extendable_under_current_admissibility_semantics,
        "output_paths": output_paths,
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
            sub_runs=sub_runs,
            output_paths=output_paths,
            extendable_under_current_admissibility_semantics=extendable_under_current_admissibility_semantics,
        ),
        encoding="utf-8",
    )
    result_note = _build_result_note(
        run_id=run_id,
        instance_id=instance.instance_id,
        metrics_summary=metrics_summary,
        output_paths=output_paths,
        extendable_under_current_admissibility_semantics=extendable_under_current_admissibility_semantics,
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
            **{f"trace_{name}": path for name, path in trace_relpaths.items()},
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
            "extendable_under_current_admissibility_semantics": extendable_under_current_admissibility_semantics,
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
    )
