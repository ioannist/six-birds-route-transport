from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sys

from ..audits.route_mismatch import RouteMismatchResult, compute_route_mismatch
from ..run_registry import (
    build_run_manifest,
    create_run_directory,
    detect_git_commit,
    repo_relative_path,
    write_run_manifest,
)
from ..schemas.event_package import EventPackageInstance
from ..schemas.observation_trace import ObservationTrace
from ..schemas.result_note import ResultNote
from ..validation import load_model


@dataclass(slots=True)
class RMReportArtifacts:
    run_id: str
    run_dir: str
    manifest_path: str
    summary_path: str
    note_path: str
    result_note_path: str
    result: RouteMismatchResult


def load_observation_trace_files(paths: list[str | Path]) -> list[ObservationTrace]:
    traces: list[ObservationTrace] = []
    for path in paths:
        model = load_model(path, kind="observation-trace")
        assert isinstance(model, ObservationTrace)
        traces.append(model)
    return traces


def _render_rm_note(
    *,
    result: RouteMismatchResult,
    trace_paths: list[str],
    instance_path: str | None,
    output_paths: dict[str, str],
) -> str:
    lines = [
        "# Route Mismatch Report",
        "",
        "## Trace / instance",
        f"- Trace IDs: `{result.trace_ids}`",
        f"- Trace paths: `{trace_paths}`",
        f"- Instance ID: `{result.instance_id}`",
        f"- Instance path: `{instance_path}`",
        "",
        "## Preparation-endpoint groups analyzed",
    ]
    for group in result.preparation_endpoint_results:
        lines.append(
            f"- `{group.preparation_kind}:{group.preparation_id}` / `{group.endpoint_id}`: route_count=`{group.route_count}`, mean_pairwise_tv=`{group.mean_pairwise_tv}`, exact_pass_fraction=`{group.exact_pass_fraction}`, insufficient_data=`{group.insufficient_data}`"
        )
    lines.extend(["", "## Route-pair mismatch results"])
    for pair in result.route_pair_results:
        lines.append(
            f"- `{pair.preparation_kind}:{pair.preparation_id}` / `{pair.endpoint_id}`: {pair.left_route_id} vs {pair.right_route_id}, tv_distance=`{pair.tv_distance}`, exact_agreement=`{pair.exact_agreement}`"
        )
    lines.extend(
        [
            "",
            "## Overall RM",
            f"- Overall RM: `{result.overall_rm}`",
            "",
            "## Explicit interpretation",
            "- RM is diagnostic-only. It reports route dependence or protocol sensitivity in the observed route-conditioned endpoint distributions and is not treated as proof of non-extendability.",
            "",
            "## Caveats / insufficient-data flags",
            f"- Insufficient-data groups: `{result.insufficient_data_groups}`",
            "",
            "## Artifact references",
            f"- Summary JSON: `{output_paths['summary']}`",
            f"- Result note JSON: `{output_paths['result_note']}`",
            f"- Run manifest: `{output_paths['manifest']}`",
        ]
    )
    return "\n".join(lines) + "\n"


def _build_result_note(
    *,
    run_id: str,
    result: RouteMismatchResult,
    output_paths: dict[str, str],
) -> ResultNote:
    scored_groups = [
        group
        for group in result.preparation_endpoint_results
        if not group.insufficient_data and group.mean_pairwise_tv is not None
    ]
    max_group_mean = max(
        (group.mean_pairwise_tv for group in scored_groups), default=0.0
    )
    return ResultNote(
        note_format_version="result-note.v1",
        note_id=f"note_{run_id}",
        run_id=run_id,
        instance_ids=[result.instance_id or "unlinked_trace"],
        metrics={
            "overall_rm": result.overall_rm if result.overall_rm is not None else -1.0,
            "route_pair_count": len(result.route_pair_results),
            "scored_group_count": len(scored_groups),
            "insufficient_data_group_count": len(result.insufficient_data_groups),
            "max_group_mean_pairwise_tv": max_group_mean,
            "exact_tolerance": result.exact_tolerance,
        },
        interpretation=(
            "RM is diagnostic-only: it summarizes route-conditioned mismatch in endpoint distributions and does not constitute proof of non-extendability."
        ),
        caveats=[
            "RM is diagnostic-only and should not be treated as a structural impossibility certificate.",
            "Groups with fewer than two routes are reported as insufficient-data and excluded from scored aggregates.",
        ],
        artifact_refs={
            "summary": output_paths["summary"],
            "note": output_paths["note"],
            "manifest": output_paths["manifest"],
        },
        metadata={"trace_count": len(result.trace_ids)},
    )


def write_rm_report(
    traces: list[ObservationTrace],
    *,
    trace_paths: list[str | Path],
    category: str,
    label: str | None = None,
    instance: EventPackageInstance | None = None,
    instance_path: str | Path | None = None,
    seed: int = 0,
    timestamp: str | None = None,
    root: str | Path | None = None,
    command: list[str] | None = None,
    exact_tolerance: float = 1e-6,
) -> RMReportArtifacts:
    repo_root = Path(root).resolve() if root is not None else None
    run_dir, run_id, manifest_timestamp = create_run_directory(
        category=category,
        label=label,
        timestamp=timestamp,
        root=repo_root,
    )
    effective_root = run_dir.parents[2]
    trace_relpaths = [
        repo_relative_path(path, root=effective_root) for path in trace_paths
    ]
    instance_relpath = (
        repo_relative_path(instance_path, root=effective_root)
        if instance_path is not None
        else None
    )
    result = compute_route_mismatch(
        traces,
        instance=instance,
        exact_tolerance=exact_tolerance,
    )

    summary_path = run_dir / "rm-summary.json"
    note_path = run_dir / "rm-note.md"
    result_note_path = run_dir / "result-note.json"
    manifest_path = run_dir / "run-manifest.json"
    output_paths = {
        "summary": repo_relative_path(summary_path, root=effective_root),
        "note": repo_relative_path(note_path, root=effective_root),
        "result_note": repo_relative_path(result_note_path, root=effective_root),
        "manifest": repo_relative_path(manifest_path, root=effective_root),
    }

    summary_payload = {
        "run_id": run_id,
        "trace_ids": result.trace_ids,
        "trace_paths": trace_relpaths,
        "instance_id": result.instance_id,
        "instance_path": instance_relpath,
        "overall_rm": result.overall_rm,
        "exact_tolerance": result.exact_tolerance,
        "route_pair_results": [asdict(item) for item in result.route_pair_results],
        "preparation_endpoint_results": [
            asdict(item) for item in result.preparation_endpoint_results
        ],
        "insufficient_data_groups": result.insufficient_data_groups,
        "aggregation_policy": result.aggregation_policy,
        "output_paths": output_paths,
    }
    summary_path.write_text(
        json.dumps(summary_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    note_path.write_text(
        _render_rm_note(
            result=result,
            trace_paths=trace_relpaths,
            instance_path=instance_relpath,
            output_paths=output_paths,
        ),
        encoding="utf-8",
    )
    result_note = _build_result_note(
        run_id=run_id,
        result=result,
        output_paths=output_paths,
    )
    result_note_path.write_text(
        json.dumps(result_note.model_dump(mode="json"), indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    input_artifacts = {
        f"trace_{index}": path for index, path in enumerate(trace_relpaths, start=1)
    }
    if instance_relpath is not None:
        input_artifacts["instance"] = instance_relpath
    manifest = build_run_manifest(
        run_id=run_id,
        timestamp=manifest_timestamp,
        command=command
        or [
            sys.executable,
            "-m",
            "sixbirds_event",
            "audits",
            "rm",
            *trace_relpaths,
        ],
        seed=seed,
        input_artifacts=input_artifacts,
        output_artifacts={
            "summary": output_paths["summary"],
            "note": output_paths["note"],
            "result_note": output_paths["result_note"],
        },
        status="succeeded",
        git_commit=detect_git_commit(root=effective_root),
        metadata={
            "analysis_kind": "route_mismatch",
            "diagnostic_only": True,
            "trace_count": len(trace_relpaths),
        },
    )
    write_run_manifest(manifest, run_dir=run_dir)
    return RMReportArtifacts(
        run_id=run_id,
        run_dir=repo_relative_path(run_dir, root=effective_root),
        manifest_path=output_paths["manifest"],
        summary_path=output_paths["summary"],
        note_path=output_paths["note"],
        result_note_path=output_paths["result_note"],
        result=result,
    )
