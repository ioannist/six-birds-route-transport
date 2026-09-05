from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sys

from ..run_registry import (
    build_run_manifest,
    create_run_directory,
    detect_git_commit,
    repo_relative_path,
    write_run_manifest,
)
from ..schemas.event_package import EventPackageInstance
from ..schemas.observation_trace import ObservationTrace
from ..solvers.statistical_deficit import (
    StatisticalDeficitResult,
    solve_statistical_global_packaging,
)


@dataclass(slots=True)
class StatisticalReportArtifacts:
    run_id: str
    run_dir: str
    manifest_path: str
    summary_path: str
    result: StatisticalDeficitResult


def write_statistical_summary(
    instance: EventPackageInstance,
    traces: list[ObservationTrace],
    *,
    instance_path: str | Path | None = None,
    trace_paths: list[str | Path],
    category: str,
    label: str | None = None,
    seed: int = 0,
    timestamp: str | None = None,
    root: str | Path | None = None,
    include_soft: bool = False,
    command: list[str] | None = None,
) -> StatisticalReportArtifacts:
    repo_root = Path(root).resolve() if root is not None else None
    run_dir, run_id, manifest_timestamp = create_run_directory(
        category=category,
        label=label,
        timestamp=timestamp,
        root=repo_root,
    )
    effective_root = run_dir.parents[2]
    result = solve_statistical_global_packaging(
        instance,
        traces,
        include_soft=include_soft,
    )
    summary_path = run_dir / "statistical-summary.json"
    manifest_path = run_dir / "run-manifest.json"
    summary_relpath = repo_relative_path(summary_path, root=effective_root)
    manifest_relpath = repo_relative_path(manifest_path, root=effective_root)
    summary_payload = {
        "run_id": run_id,
        "instance_id": instance.instance_id,
        "trace_ids": result.trace_ids,
        "mode": result.mode,
        "solved": result.solved,
        "reason": result.reason,
        "gpd_stat": result.gpd_stat,
        "candidate_tuple_count": result.candidate_tuple_count,
        "allowed_tuple_count": result.allowed_tuple_count,
        "total_residual": result.total_residual,
        "context_residuals": {
            context_id: asdict(residual)
            for context_id, residual in result.context_residuals.items()
        },
        "fitted_tuple_distribution": [
            asdict(item) for item in result.fitted_tuple_distribution
        ],
        "fitted_context_marginals": result.fitted_context_marginals,
        "observed_context_marginals": result.observed_context_marginals,
        "trace_paths": [
            repo_relative_path(path, root=effective_root) for path in trace_paths
        ],
    }
    summary_path.write_text(
        json.dumps(summary_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest = build_run_manifest(
        run_id=run_id,
        timestamp=manifest_timestamp,
        command=command
        or [sys.executable, "-m", "sixbirds_event", "statistical", "report"],
        seed=seed,
        input_artifacts=(
            {"instance": repo_relative_path(instance_path, root=effective_root)}
            if instance_path is not None
            else {}
        ),
        output_artifacts={"summary": summary_relpath},
        status="succeeded",
        git_commit=detect_git_commit(root=effective_root),
        metadata={"analysis_kind": "statistical_report", "mode": result.mode},
    )
    write_run_manifest(manifest, run_dir=run_dir)
    return StatisticalReportArtifacts(
        run_id=run_id,
        run_dir=repo_relative_path(run_dir, root=effective_root),
        manifest_path=manifest_relpath,
        summary_path=summary_relpath,
        result=result,
    )
