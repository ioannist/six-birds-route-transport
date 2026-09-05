from __future__ import annotations

from dataclasses import dataclass
import csv
import json
from pathlib import Path
import statistics
import sys

from ..audits import (
    compute_context_closure_defect,
    compute_route_mismatch,
    compute_shared_event_consistency,
)
from ..run_registry import (
    build_run_manifest,
    create_run_directory,
    detect_git_commit,
    repo_relative_path,
    write_run_manifest,
)
from ..schemas.event_package import EventPackageInstance
from ..schemas.result_note import ResultNote
from ..solvers.statistical_deficit import solve_statistical_deficit_from_trace
from ..solvers.structural_deficit import (
    StructuralDeficitConfig,
    solve_structural_deficit,
)
from ..solvers.structural_exact import solve_exact_structural_feasibility
from ..validation import load_model
from .models import (
    NoiseMetricThresholds,
    NoiseRobustnessRow,
    NoiseRobustnessSweep,
    NoiseRobustnessTable,
    NoiseRobustnessTarget,
)
from .noise_models import (
    make_noisy_ccd_trace,
    make_noisy_rm_trace,
    make_noisy_sec_trace,
    make_noisy_stat_trace,
)


@dataclass(slots=True)
class NoiseRobustnessArtifacts:
    run_id: str
    run_dir: str
    manifest_path: str
    csv_path: str
    json_path: str
    threshold_crossings_path: str
    summary_path: str
    note_path: str
    result_note_path: str
    table: NoiseRobustnessTable
    threshold_crossings: dict[str, object]
    summary: dict[str, object]


def load_noise_robustness_sweep(path: str | Path) -> NoiseRobustnessSweep:
    model = load_model(path, kind="noise-robustness-sweep")
    assert isinstance(model, NoiseRobustnessSweep)
    return model


def _load_trace(path: str | Path):
    model = load_model(path, kind="observation-trace")
    assert model is not None
    return model


def _load_instance(path: str | Path) -> EventPackageInstance:
    model = load_model(path, kind="event-package-instance")
    assert isinstance(model, EventPackageInstance)
    return model


def _resolve_input_path(path: str | Path, *, effective_root: Path) -> Path:
    candidate = Path(path)
    if candidate.exists():
        return candidate
    rooted = effective_root / candidate
    if rooted.exists():
        return rooted
    return candidate


def _baseline_structural_metadata(instance: EventPackageInstance) -> dict[str, object]:
    exact = solve_exact_structural_feasibility(instance, include_soft=False)
    baseline_gpd_str: float | None
    if exact.feasible:
        baseline_gpd_str = 0.0
    else:
        deficit = solve_structural_deficit(instance, config=StructuralDeficitConfig())
        baseline_gpd_str = deficit.gpd_str
    return {
        "baseline_exact_structural_feasible_hard_only": exact.feasible,
        "baseline_gpd_str": baseline_gpd_str,
        "baseline_exact_respecting_tuple_count": exact.respecting_tuple_count,
    }


def _threshold_flag(
    value: float | None, threshold: float, *, status: str
) -> bool | None:
    if status not in {"solved", "scored"} or value is None:
        return None
    return value >= threshold


def _write_trace(path: Path, trace) -> str:
    path.write_text(
        json.dumps(trace.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path.as_posix()


def _sec_mean(result) -> float | None:
    scores = [
        row.approx_score
        for row in result.event_pair_results
        if row.approx_score is not None and not row.insufficient_data
    ]
    return statistics.mean(scores) if scores else None


def _metric_thresholds_for_target(
    target: NoiseRobustnessTarget,
    sweep_thresholds: NoiseMetricThresholds,
) -> NoiseMetricThresholds:
    return target.metric_threshold_overrides or sweep_thresholds


def _compute_row(
    *,
    sweep_id: str,
    target: NoiseRobustnessTarget,
    instance: EventPackageInstance,
    noise_level: float,
    noised_paths: dict[str, str],
    noised_traces: dict[str, object],
    thresholds: NoiseMetricThresholds,
    baseline_structural: dict[str, object],
) -> NoiseRobustnessRow:
    gpd_stat_status = "not_applicable"
    gpd_stat = None
    gpd_stat_reason = None
    if "stat" in noised_traces:
        stat_result = solve_statistical_deficit_from_trace(
            instance,
            noised_traces["stat"],
        )
        if stat_result.solved:
            gpd_stat_status = "solved"
            gpd_stat = stat_result.gpd_stat
        else:
            gpd_stat_status = "unsolved"
            gpd_stat_reason = stat_result.reason

    ccd_status = "not_applicable"
    ccd_overall = None
    if "ccd" in noised_traces:
        ccd_result = compute_context_closure_defect(
            noised_traces["ccd"],
            instance=instance,
        )
        if ccd_result.overall_ccd is not None:
            ccd_status = "scored"
            ccd_overall = ccd_result.overall_ccd
        else:
            ccd_status = "insufficient_data"

    sec_status = "not_applicable"
    sec_mean = None
    if "sec" in noised_traces:
        sec_result = compute_shared_event_consistency(
            instance,
            [noised_traces["sec"]],
        )
        sec_mean = _sec_mean(sec_result)
        sec_status = "scored" if sec_mean is not None else "insufficient_data"

    rm_status = "not_applicable"
    rm_overall = None
    if "rm" in noised_traces:
        rm_result = compute_route_mismatch(
            [noised_traces["rm"]],
            instance=instance,
        )
        if rm_result.overall_rm is not None:
            rm_status = "scored"
            rm_overall = rm_result.overall_rm
        else:
            rm_status = "insufficient_data"

    return NoiseRobustnessRow(
        row_format_version="noise-robustness-row.v1",
        sweep_id=sweep_id,
        target_id=target.target_id,
        target_type=target.target_type,
        noise_level=noise_level,
        event_package_path=target.event_package_artifact,
        noisy_trace_artifacts={
            "stat": noised_paths.get("stat"),
            "ccd": noised_paths.get("ccd"),
            "sec": noised_paths.get("sec"),
            "rm": noised_paths.get("rm"),
        },
        gpd_stat_status=gpd_stat_status,
        gpd_stat=gpd_stat,
        gpd_stat_reason=gpd_stat_reason,
        ccd_status=ccd_status,
        ccd_overall=ccd_overall,
        sec_status=sec_status,
        sec_mean=sec_mean,
        rm_status=rm_status,
        rm_overall=rm_overall,
        gpd_stat_threshold_crossed=_threshold_flag(
            gpd_stat,
            thresholds.gpd_stat_failure_threshold,
            status=gpd_stat_status,
        ),
        ccd_threshold_crossed=_threshold_flag(
            ccd_overall,
            thresholds.ccd_failure_threshold,
            status=ccd_status,
        ),
        sec_threshold_crossed=_threshold_flag(
            sec_mean,
            thresholds.sec_failure_threshold,
            status=sec_status,
        ),
        rm_threshold_crossed=_threshold_flag(
            rm_overall,
            thresholds.rm_failure_threshold,
            status=rm_status,
        ),
        baseline_exact_structural_feasible_hard_only=baseline_structural[
            "baseline_exact_structural_feasible_hard_only"
        ],
        baseline_gpd_str=baseline_structural["baseline_gpd_str"],
        notes=list(target.notes),
    )


def _first_crossing(
    rows: list[NoiseRobustnessRow],
    *,
    metric: str,
    threshold: float,
) -> dict[str, object]:
    status_field = f"{metric}_status"
    value_field = {
        "gpd_stat": "gpd_stat",
        "ccd": "ccd_overall",
        "sec": "sec_mean",
        "rm": "rm_overall",
    }[metric]
    applicable_rows = [
        row
        for row in sorted(rows, key=lambda item: item.noise_level)
        if getattr(row, status_field) in {"solved", "scored"}
        and getattr(row, value_field) is not None
    ]
    first_crossing = next(
        (
            row.noise_level
            for row in applicable_rows
            if getattr(row, value_field) >= threshold
        ),
        None,
    )
    observed_statuses = sorted({getattr(row, status_field) for row in rows})
    return {
        "threshold": threshold,
        "first_crossing_noise_level": first_crossing,
        "observed_statuses": observed_statuses,
    }


def _render_note(
    *,
    sweep: NoiseRobustnessSweep,
    summary: dict[str, object],
    output_paths: dict[str, str],
) -> str:
    lines = [
        "# Noise Robustness Sweep",
        "",
        "## Sweep ID",
        f"- `{sweep.sweep_id}`",
        "",
        "## Targets covered",
    ]
    for target in sweep.targets:
        lines.append(f"- `{target.target_id}` ({target.target_type})")
    lines.extend(
        [
            "",
            "## Noise model and noise grid",
            f"- Distribution model: `{sweep.noise_model.distribution_model}`",
            f"- CCD model: `{sweep.noise_model.ccd_model}`",
            f"- Noise grid: `{summary['noise_grid']}`",
            "",
            "## Threshold config",
            f"- `{summary['thresholds']}`",
            "",
            "## Robustness trends",
            f"- Availability counts: `{summary['availability_counts']}`",
            f"- Notable status counts: `{summary['status_counts']}`",
            "",
            "## First-crossing summary",
            f"- `{summary['first_crossings']}`",
            "",
            "## Caveats",
            "- RM is diagnostic-only.",
            "- unsolved / insufficient_data / not_applicable statuses are preserved explicitly rather than coerced to numeric zero.",
            "- Baseline structural metadata is fixed-package context, not a noise-varying metric.",
            "",
            "## Artifact references",
            f"- Robustness CSV: `{output_paths['csv']}`",
            f"- Robustness JSON: `{output_paths['json']}`",
            f"- Threshold crossings: `{output_paths['threshold_crossings']}`",
            f"- Summary: `{output_paths['summary']}`",
            f"- Result note: `{output_paths['result_note']}`",
            f"- Run manifest: `{output_paths['manifest']}`",
        ]
    )
    return "\n".join(lines) + "\n"


def _build_result_note(
    *,
    run_id: str,
    sweep: NoiseRobustnessSweep,
    summary: dict[str, object],
    output_paths: dict[str, str],
) -> ResultNote:
    return ResultNote(
        note_format_version="result-note.v1",
        note_id=f"note_{run_id}",
        run_id=run_id,
        instance_ids=[target.target_id for target in sweep.targets],
        metrics={
            "target_count": len(sweep.targets),
            "row_count": summary["row_count"],
            "noise_grid_size": len(summary["noise_grid"]),
        },
        interpretation=(
            "Noise robustness was evaluated by injecting deterministic seeded noise into fixed baseline traces. "
            "Only trace-sensitive metrics were swept; structural metadata remained fixed-package context."
        ),
        caveats=[
            "RM is diagnostic-only when present.",
            "unsolved / insufficient_data / not_applicable statuses are preserved explicitly in robustness rows and summaries.",
        ],
        artifact_refs={
            "robustness_csv": output_paths["csv"],
            "robustness_json": output_paths["json"],
            "threshold_crossings": output_paths["threshold_crossings"],
            "summary": output_paths["summary"],
            "note": output_paths["note"],
            "manifest": output_paths["manifest"],
        },
        metadata={
            "committed_target_types": sorted(
                {target.target_type for target in sweep.targets}
            )
        },
    )


def run_noise_robustness_sweep(
    *,
    sweep_path: str | Path,
    category: str,
    label: str | None = None,
    seed: int = 0,
    timestamp: str | None = None,
    root: str | Path | None = None,
    command: list[str] | None = None,
) -> NoiseRobustnessArtifacts:
    repo_root = Path(root).resolve() if root is not None else None
    run_dir, run_id, manifest_timestamp = create_run_directory(
        category=category,
        label=label,
        timestamp=timestamp,
        root=repo_root,
    )
    effective_root = run_dir.parents[2]
    sweep = load_noise_robustness_sweep(sweep_path)
    sweep_relpath = repo_relative_path(sweep_path, root=effective_root)

    rows: list[NoiseRobustnessRow] = []
    noisy_root = run_dir / "noisy-traces"
    noisy_root.mkdir(parents=True, exist_ok=True)

    for target in sweep.targets:
        instance = _load_instance(
            _resolve_input_path(
                target.event_package_artifact,
                effective_root=effective_root,
            )
        )
        baseline_structural = _baseline_structural_metadata(instance)
        thresholds = _metric_thresholds_for_target(target, sweep.metric_thresholds)
        baseline_traces = {
            family: _load_trace(
                _resolve_input_path(path, effective_root=effective_root)
            )
            for family, path in {
                "stat": target.trace_artifacts.stat,
                "ccd": target.trace_artifacts.ccd,
                "sec": target.trace_artifacts.sec,
                "rm": target.trace_artifacts.rm,
            }.items()
            if path is not None
        }
        noise_grid = target.noise_grid_override or sweep.noise_grid
        for noise_level in noise_grid:
            point_dir = noisy_root / target.target_id / f"noise-{noise_level:.2f}"
            point_dir.mkdir(parents=True, exist_ok=True)
            noised_traces: dict[str, object] = {}
            noised_paths: dict[str, str] = {}

            if "stat" in baseline_traces:
                trace = make_noisy_stat_trace(
                    baseline_traces["stat"],
                    noise_level=noise_level,
                    base_seed=sweep.noise_model.base_seed,
                    target_id=target.target_id,
                )
                path = point_dir / "stat-trace.json"
                _write_trace(path, trace)
                noised_traces["stat"] = trace
                noised_paths["stat"] = repo_relative_path(path, root=effective_root)
            if "ccd" in baseline_traces:
                trace = make_noisy_ccd_trace(
                    baseline_traces["ccd"],
                    instance=instance,
                    noise_level=noise_level,
                    base_seed=sweep.noise_model.base_seed,
                    target_id=target.target_id,
                )
                path = point_dir / "ccd-trace.json"
                _write_trace(path, trace)
                noised_traces["ccd"] = trace
                noised_paths["ccd"] = repo_relative_path(path, root=effective_root)
            if "sec" in baseline_traces:
                trace = make_noisy_sec_trace(
                    baseline_traces["sec"],
                    noise_level=noise_level,
                    base_seed=sweep.noise_model.base_seed,
                    target_id=target.target_id,
                )
                path = point_dir / "sec-trace.json"
                _write_trace(path, trace)
                noised_traces["sec"] = trace
                noised_paths["sec"] = repo_relative_path(path, root=effective_root)
            if "rm" in baseline_traces:
                trace = make_noisy_rm_trace(
                    baseline_traces["rm"],
                    noise_level=noise_level,
                    base_seed=sweep.noise_model.base_seed,
                    target_id=target.target_id,
                )
                path = point_dir / "rm-trace.json"
                _write_trace(path, trace)
                noised_traces["rm"] = trace
                noised_paths["rm"] = repo_relative_path(path, root=effective_root)

            rows.append(
                _compute_row(
                    sweep_id=sweep.sweep_id,
                    target=target,
                    instance=instance,
                    noise_level=noise_level,
                    noised_paths=noised_paths,
                    noised_traces=noised_traces,
                    thresholds=thresholds,
                    baseline_structural=baseline_structural,
                )
            )

    rows = sorted(rows, key=lambda row: (row.target_id, row.noise_level))
    table = NoiseRobustnessTable(
        table_format_version="noise-robustness-table.v1",
        sweep_id=sweep.sweep_id,
        row_count=len(rows),
        rows=rows,
        metadata={
            "committed_target_types": sorted(
                {target.target_type for target in sweep.targets}
            )
        },
    )

    threshold_crossings = {
        "sweep_id": sweep.sweep_id,
        "targets": {
            target.target_id: {
                "gpd_stat": _first_crossing(
                    [row for row in rows if row.target_id == target.target_id],
                    metric="gpd_stat",
                    threshold=_metric_thresholds_for_target(
                        target, sweep.metric_thresholds
                    ).gpd_stat_failure_threshold,
                ),
                "ccd": _first_crossing(
                    [row for row in rows if row.target_id == target.target_id],
                    metric="ccd",
                    threshold=_metric_thresholds_for_target(
                        target, sweep.metric_thresholds
                    ).ccd_failure_threshold,
                ),
                "sec": _first_crossing(
                    [row for row in rows if row.target_id == target.target_id],
                    metric="sec",
                    threshold=_metric_thresholds_for_target(
                        target, sweep.metric_thresholds
                    ).sec_failure_threshold,
                ),
                "rm": _first_crossing(
                    [row for row in rows if row.target_id == target.target_id],
                    metric="rm",
                    threshold=_metric_thresholds_for_target(
                        target, sweep.metric_thresholds
                    ).rm_failure_threshold,
                ),
            }
            for target in sweep.targets
        },
    }

    status_counts: dict[str, int] = {}
    for row in rows:
        for field_name in [
            "gpd_stat_status",
            "ccd_status",
            "sec_status",
            "rm_status",
        ]:
            key = f"{field_name}:{getattr(row, field_name)}"
            status_counts[key] = status_counts.get(key, 0) + 1

    availability_counts = {
        "gpd_stat_applicable_rows": sum(
            1 for row in rows if row.gpd_stat_status != "not_applicable"
        ),
        "ccd_applicable_rows": sum(
            1 for row in rows if row.ccd_status != "not_applicable"
        ),
        "sec_applicable_rows": sum(
            1 for row in rows if row.sec_status != "not_applicable"
        ),
        "rm_applicable_rows": sum(
            1 for row in rows if row.rm_status != "not_applicable"
        ),
    }

    csv_path = run_dir / "robustness.csv"
    json_path = run_dir / "robustness.json"
    threshold_path = run_dir / "threshold-crossings.json"
    summary_path = run_dir / "robustness-summary.json"
    note_path = run_dir / "robustness-note.md"
    result_note_path = run_dir / "result-note.json"
    manifest_path = run_dir / "run-manifest.json"
    output_paths = {
        "csv": repo_relative_path(csv_path, root=effective_root),
        "json": repo_relative_path(json_path, root=effective_root),
        "threshold_crossings": repo_relative_path(threshold_path, root=effective_root),
        "summary": repo_relative_path(summary_path, root=effective_root),
        "note": repo_relative_path(note_path, root=effective_root),
        "result_note": repo_relative_path(result_note_path, root=effective_root),
        "manifest": repo_relative_path(manifest_path, root=effective_root),
    }

    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "target_id",
                "target_type",
                "noise_level",
                "event_package_path",
                "stat_trace_path",
                "ccd_trace_path",
                "sec_trace_path",
                "rm_trace_path",
                "gpd_stat_status",
                "gpd_stat",
                "gpd_stat_reason",
                "ccd_status",
                "ccd_overall",
                "sec_status",
                "sec_mean",
                "rm_status",
                "rm_overall",
                "gpd_stat_threshold_crossed",
                "ccd_threshold_crossed",
                "sec_threshold_crossed",
                "rm_threshold_crossed",
                "baseline_exact_structural_feasible_hard_only",
                "baseline_gpd_str",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "target_id": row.target_id,
                    "target_type": row.target_type,
                    "noise_level": row.noise_level,
                    "event_package_path": row.event_package_path,
                    "stat_trace_path": row.noisy_trace_artifacts.stat,
                    "ccd_trace_path": row.noisy_trace_artifacts.ccd,
                    "sec_trace_path": row.noisy_trace_artifacts.sec,
                    "rm_trace_path": row.noisy_trace_artifacts.rm,
                    "gpd_stat_status": row.gpd_stat_status,
                    "gpd_stat": row.gpd_stat,
                    "gpd_stat_reason": row.gpd_stat_reason,
                    "ccd_status": row.ccd_status,
                    "ccd_overall": row.ccd_overall,
                    "sec_status": row.sec_status,
                    "sec_mean": row.sec_mean,
                    "rm_status": row.rm_status,
                    "rm_overall": row.rm_overall,
                    "gpd_stat_threshold_crossed": row.gpd_stat_threshold_crossed,
                    "ccd_threshold_crossed": row.ccd_threshold_crossed,
                    "sec_threshold_crossed": row.sec_threshold_crossed,
                    "rm_threshold_crossed": row.rm_threshold_crossed,
                    "baseline_exact_structural_feasible_hard_only": row.baseline_exact_structural_feasible_hard_only,
                    "baseline_gpd_str": row.baseline_gpd_str,
                }
            )

    json_path.write_text(
        json.dumps(table.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    threshold_path.write_text(
        json.dumps(threshold_crossings, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    summary = {
        "sweep_id": sweep.sweep_id,
        "target_count": len(sweep.targets),
        "row_count": len(rows),
        "noise_grid": sweep.noise_grid,
        "thresholds": sweep.metric_thresholds.model_dump(mode="json"),
        "availability_counts": availability_counts,
        "status_counts": status_counts,
        "first_crossings": threshold_crossings["targets"],
        "table_paths": {
            "csv": output_paths["csv"],
            "json": output_paths["json"],
            "threshold_crossings": output_paths["threshold_crossings"],
        },
        "committed_target_types": sorted(
            {target.target_type for target in sweep.targets}
        ),
    }
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    note_path.write_text(
        _render_note(sweep=sweep, summary=summary, output_paths=output_paths),
        encoding="utf-8",
    )
    result_note = _build_result_note(
        run_id=run_id,
        sweep=sweep,
        summary=summary,
        output_paths=output_paths,
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
            "robustness",
            "run-sweep",
            sweep_relpath,
        ],
        seed=seed,
        input_artifacts={"sweep": sweep_relpath},
        output_artifacts={
            "robustness_csv": output_paths["csv"],
            "robustness_json": output_paths["json"],
            "threshold_crossings": output_paths["threshold_crossings"],
            "summary": output_paths["summary"],
            "note": output_paths["note"],
            "result_note": output_paths["result_note"],
        },
        status="succeeded",
        git_commit=detect_git_commit(root=effective_root),
        metadata={
            "analysis_kind": "noise_robustness",
            "sweep_id": sweep.sweep_id,
            "target_count": len(sweep.targets),
        },
    )
    write_run_manifest(manifest, run_dir=run_dir)
    return NoiseRobustnessArtifacts(
        run_id=run_id,
        run_dir=repo_relative_path(run_dir, root=effective_root),
        manifest_path=output_paths["manifest"],
        csv_path=output_paths["csv"],
        json_path=output_paths["json"],
        threshold_crossings_path=output_paths["threshold_crossings"],
        summary_path=output_paths["summary"],
        note_path=output_paths["note"],
        result_note_path=output_paths["result_note"],
        table=table,
        threshold_crossings=threshold_crossings,
        summary=summary,
    )
