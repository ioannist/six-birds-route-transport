from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import sys

from ..interventions.flattening import (
    build_completed_config,
    derive_route_trace_from_run,
    derive_stat_trace_from_family,
    load_flattening_intervention,
)
from ..reporting.context_discovery_report import write_context_discovery_report
from ..reporting.package_build_report import write_package_build_report
from ..reporting.rm_report import write_rm_report
from ..reporting.statistical_report import write_statistical_summary
from ..reporting.structural_report import generate_structural_report
from ..run_registry import (
    build_run_manifest,
    create_run_directory,
    detect_git_commit,
    repo_relative_path,
    write_run_manifest,
)
from ..schemas.result_note import ResultNote
from ..solvers.structural_deficit import StructuralDeficitConfig
from ..substrates.engine import load_substrate_config, write_substrate_run
from ..validation import load_model


@dataclass(slots=True)
class FlatteningInterventionArtifacts:
    run_id: str
    run_dir: str
    manifest_path: str
    before_route_trace_path: str
    after_route_trace_path: str
    summary_path: str
    note_path: str
    result_note_path: str
    conclusion: str
    summary: dict[str, object]


@dataclass(slots=True)
class _SideArtifacts:
    raw_run_path: str
    route_trace_path: str
    family_path: str
    event_package_instance_id: str | None
    package_path: str | None
    stat_trace_path: str | None
    raw_run_id: str
    discovery_run_id: str
    package_run_id: str | None
    structural_run_id: str | None
    statistical_run_id: str | None
    rm_run_id: str | None
    accepted_context_count: int
    accepted_proposal_count: int
    exact_structural_status: str
    exact_structural_feasible_hard_only: bool | None
    exact_respecting_tuple_count: int | None
    gpd_str: float | None
    gpd_stat_status: str
    gpd_stat: float | None
    gpd_stat_reason: str | None
    rm_status: str
    overall_rm: float | None
    rm_insufficient_data_group_count: int | None
    structural_summary_path: str | None
    statistical_summary_path: str | None
    rm_summary_path: str | None


def _artifact_record(
    artifact,
    *,
    include_summary: bool = True,
    include_note: bool = True,
    include_result_note: bool = True,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "run_id": artifact.run_id,
        "manifest_path": artifact.manifest_path,
    }
    if include_summary and hasattr(artifact, "summary_path"):
        payload["summary_path"] = artifact.summary_path
    if include_note and hasattr(artifact, "note_path"):
        payload["note_path"] = artifact.note_path
    if include_result_note and hasattr(artifact, "result_note_path"):
        payload["result_note_path"] = artifact.result_note_path
    return payload


def _classify_outcome(
    *,
    before: _SideArtifacts,
    after: _SideArtifacts,
    rm_material_decrease_min: float,
) -> str:
    rm_decreased_materially = (
        before.rm_status == "scored"
        and after.rm_status == "scored"
        and before.overall_rm is not None
        and after.overall_rm is not None
        and before.overall_rm - after.overall_rm >= rm_material_decrease_min
    )
    if (
        after.package_path is not None
        and after.exact_structural_feasible_hard_only is True
        and after.gpd_str is not None
        and abs(after.gpd_str) <= 1e-9
        and (
            (before.exact_structural_feasible_hard_only is False)
            or (before.gpd_str is not None and before.gpd_str > 0)
            or rm_decreased_materially
        )
    ):
        return "repairable"
    if (
        before.gpd_str is not None
        and after.gpd_str is not None
        and after.gpd_str < before.gpd_str
    ) or rm_decreased_materially:
        return "weakened"
    return "robust"


def _side_summary(side: _SideArtifacts) -> dict[str, object]:
    return {
        "raw_run_path": side.raw_run_path,
        "route_trace_path": side.route_trace_path,
        "discovered_context_family_path": side.family_path,
        "event_package_instance_id": side.event_package_instance_id,
        "event_package_path": side.package_path,
        "stat_trace_path": side.stat_trace_path,
        "accepted_context_count": side.accepted_context_count,
        "accepted_shared_event_proposal_count": side.accepted_proposal_count,
        "exact_structural_status": side.exact_structural_status,
        "exact_structural_feasible_hard_only": side.exact_structural_feasible_hard_only,
        "exact_respecting_tuple_count": side.exact_respecting_tuple_count,
        "gpd_str": side.gpd_str,
        "gpd_stat_status": side.gpd_stat_status,
        "gpd_stat": side.gpd_stat,
        "gpd_stat_reason": side.gpd_stat_reason,
        "rm_status": side.rm_status,
        "overall_rm": side.overall_rm,
        "rm_insufficient_data_group_count": side.rm_insufficient_data_group_count,
    }


def _render_note(
    *,
    spec,
    summary: dict[str, object],
    output_paths: dict[str, str],
) -> str:
    lines = [
        "# Flattening Intervention Comparison",
        "",
        "## Intervention ID",
        f"- Intervention ID: `{spec.intervention_id}`",
        "",
        "## Source substrate config",
        f"- Source config: `{spec.source_config_artifact}`",
        "",
        "## Before / after protocols",
        f"- Before protocol: `{spec.before_protocol_id}`",
        f"- After protocol: `{summary['after_protocol_id']}`",
        "",
        "## Completion policy used",
        f"- Completion policy: `{summary['completion_policy']}`",
        "",
        "## Route-extraction settings",
        f"- Route extraction: `{summary['route_extraction']}`",
        "",
        "## Before metrics",
        f"- Metrics: `{summary['before']}`",
        "",
        "## After metrics",
        f"- Metrics: `{summary['after']}`",
        "",
        "## Before / after comparison",
        f"- Deltas: `{summary['deltas']}`",
        f"- Flattening outcome: `{summary['flattening_outcome']}`",
        "",
        "## Caveats",
        "- RM is diagnostic-only.",
        "- unsolved / insufficient-data / not_applicable statuses are preserved explicitly rather than coerced to numeric zero.",
        "",
        "## Artifact references",
        f"- Before route trace: `{output_paths['before_route_trace']}`",
        f"- After route trace: `{output_paths['after_route_trace']}`",
        f"- Comparison summary: `{output_paths['summary']}`",
        f"- Result note: `{output_paths['result_note']}`",
        f"- Run manifest: `{output_paths['manifest']}`",
    ]
    return "\n".join(lines) + "\n"


def _build_result_note(
    *,
    run_id: str,
    summary: dict[str, object],
    output_paths: dict[str, str],
) -> ResultNote:
    before = summary["before"]
    after = summary["after"]
    instance_ids = [
        summary["intervention_id"],
        *(
            [before["event_package_instance_id"]]
            if before["event_package_instance_id"] is not None
            else []
        ),
        *(
            [after["event_package_instance_id"]]
            if after["event_package_instance_id"] is not None
            else []
        ),
    ]
    return ResultNote(
        note_format_version="result-note.v1",
        note_id=f"note_{run_id}",
        run_id=run_id,
        instance_ids=instance_ids,
        metrics={
            "before_exact_structural_status": before["exact_structural_status"],
            "before_gpd_str": before["gpd_str"],
            "before_gpd_stat_status": before["gpd_stat_status"],
            "before_gpd_stat": before["gpd_stat"],
            "before_rm_status": before["rm_status"],
            "before_overall_rm": before["overall_rm"],
            "after_exact_structural_status": after["exact_structural_status"],
            "after_gpd_str": after["gpd_str"],
            "after_gpd_stat_status": after["gpd_stat_status"],
            "after_gpd_stat": after["gpd_stat"],
            "after_rm_status": after["rm_status"],
            "after_overall_rm": after["overall_rm"],
        },
        interpretation=(
            "Flattening/completion intervention reran the discovery and package pipeline before and after explicit completion. "
            f"Flattening outcome: {summary['flattening_outcome']}."
        ),
        caveats=[
            "RM is diagnostic-only when present.",
            "unsolved / insufficient-data / not_applicable statuses are preserved explicitly in the comparison bundle.",
        ],
        artifact_refs={
            "before_route_trace": output_paths["before_route_trace"],
            "after_route_trace": output_paths["after_route_trace"],
            "summary": output_paths["summary"],
            "note": output_paths["note"],
            "manifest": output_paths["manifest"],
        },
        metadata={"flattening_outcome": summary["flattening_outcome"]},
    )


def _run_side(
    *,
    side: str,
    config,
    config_path: str,
    protocol_id: str,
    endpoint_step_index: int,
    spec,
    category: str,
    label: str,
    timestamp: str | None,
    root: Path,
    bundle_dir: Path,
    deficit_config: StructuralDeficitConfig,
) -> _SideArtifacts:
    raw = write_substrate_run(
        config,
        config_path=config_path,
        preparation_id=spec.preparation_id,
        protocol_id=protocol_id,
        trajectories=spec.trajectory_count,
        seed=spec.seed,
        category=category,
        label=f"{label}-{side}-substrate",
        timestamp=timestamp,
        root=root,
        command=[
            sys.executable,
            "-m",
            "sixbirds_event",
            "substrates",
            "run",
            config_path,
            "--preparation",
            spec.preparation_id,
            "--protocol",
            protocol_id,
            "--trajectories",
            str(spec.trajectory_count),
            "--seed",
            str(spec.seed),
        ],
    )
    route_trace = derive_route_trace_from_run(
        raw.run_trace,
        spec,
        trace_id=f"{spec.intervention_id}__{side}_route",
        endpoint_step_index=endpoint_step_index,
    )
    route_trace_path = bundle_dir / f"{side}-route-trace.json"
    route_trace_path.write_text(
        json.dumps(route_trace.model_dump(mode="json"), indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    route_trace_relpath = repo_relative_path(route_trace_path, root=root)
    rm_report = (
        write_rm_report(
            [route_trace],
            trace_paths=[route_trace_relpath],
            category=category,
            label=f"{label}-{side}-rm",
            instance=None,
            instance_path=None,
            seed=spec.seed,
            timestamp=timestamp,
            root=root,
            command=[
                sys.executable,
                "-m",
                "sixbirds_event",
                "audits",
                "rm",
                route_trace_relpath,
            ],
        )
        if spec.comparison_config.include_rm
        else None
    )
    rm_status = "not_applicable"
    overall_rm = None
    rm_insufficient = None
    rm_summary_path = None
    rm_run_id = None
    if rm_report is not None:
        rm_run_id = rm_report.run_id
        rm_summary_path = rm_report.summary_path
        if rm_report.result.overall_rm is not None:
            rm_status = "scored"
            overall_rm = rm_report.result.overall_rm
        else:
            rm_status = "insufficient_data"
        rm_insufficient = len(rm_report.result.insufficient_data_groups)

    discovery = write_context_discovery_report(
        run_paths=[root / raw.run_trace_path],
        category=category,
        label=f"{label}-{side}-discover",
        seed=spec.seed,
        timestamp=timestamp,
        root=root,
        command=[
            sys.executable,
            "-m",
            "sixbirds_event",
            "substrates",
            "discover-contexts",
            raw.run_trace_path,
        ],
        thresholds=spec.discovery_thresholds,
    )
    family = load_model(root / discovery.family_path, kind="discovered-context-family")
    assert family is not None
    accepted_context_count = family.diagnostics_summary.accepted_context_count

    event_package_instance_id = None
    package_path = None
    stat_trace_path = None
    package_run_id = None
    structural_run_id = None
    statistical_run_id = None
    structural_summary_path = None
    statistical_summary_path = None
    accepted_proposal_count = 0
    exact_status = "not_applicable"
    exact_feasible = None
    exact_tuple_count = None
    gpd_str = None
    gpd_stat_status = "not_applicable"
    gpd_stat = None
    gpd_stat_reason = None

    if family.diagnostics_summary.accepted_context_count > 0:
        package = write_package_build_report(
            family_path=root / discovery.family_path,
            run_paths=[root / raw.run_trace_path],
            skeleton_path=(
                None
                if discovery.skeleton_path is None
                else root / discovery.skeleton_path
            ),
            category=category,
            label=f"{label}-{side}-package",
            seed=spec.seed,
            timestamp=timestamp,
            root=root,
            command=[
                sys.executable,
                "-m",
                "sixbirds_event",
                "substrates",
                "build-event-package",
                discovery.family_path,
                "--raw-run",
                raw.run_trace_path,
            ],
            thresholds=spec.shared_event_inference_thresholds,
        )
        package_path = package.event_package_path
        event_package_instance_id = package.event_package.instance_id
        package_run_id = package.run_id
        accepted_proposal_count = len(package.event_package.equality_proposals)
        stat_trace = derive_stat_trace_from_family(
            raw.run_trace,
            family,
            instance_id=package.event_package.instance_id,
            instance_artifact=package.event_package_path,
            trace_id=f"{spec.intervention_id}__{side}_stat",
        )
        stat_trace_path_obj = bundle_dir / f"{side}-stat-trace.json"
        stat_trace_path_obj.write_text(
            json.dumps(stat_trace.model_dump(mode="json"), indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        stat_trace_path = repo_relative_path(stat_trace_path_obj, root=root)
        structural = generate_structural_report(
            package.event_package,
            instance_path=package.event_package_path,
            category=category,
            label=f"{label}-{side}-structural",
            seed=spec.seed,
            timestamp=timestamp,
            root=root,
            command=[
                sys.executable,
                "-m",
                "sixbirds_event",
                "structural",
                "report",
                package.event_package_path,
            ],
            deficit_config=deficit_config,
        )
        structural_run_id = structural.run_id
        structural_summary_path = structural.summary_path
        exact_status = (
            "feasible"
            if structural.summary.exact_extendable_hard_only
            else "infeasible"
        )
        exact_feasible = structural.summary.exact_extendable_hard_only
        exact_tuple_count = structural.summary.hard_only_respecting_tuple_count
        gpd_str = (
            float(structural.summary.gpd_str)
            if structural.summary.gpd_str is not None
            else None
        )
        statistical = write_statistical_summary(
            package.event_package,
            [stat_trace],
            instance_path=package.event_package_path,
            trace_paths=[stat_trace_path],
            category=category,
            label=f"{label}-{side}-statistical",
            seed=spec.seed,
            timestamp=timestamp,
            root=root,
            command=[
                sys.executable,
                "-m",
                "sixbirds_event",
                "interventions",
                "flattening",
                "derived-stat",
            ],
        )
        statistical_run_id = statistical.run_id
        statistical_summary_path = statistical.summary_path
        if statistical.result.solved:
            gpd_stat_status = "solved"
            gpd_stat = statistical.result.gpd_stat
        else:
            gpd_stat_status = "unsolved"
            gpd_stat_reason = statistical.result.reason

    return _SideArtifacts(
        raw_run_path=raw.run_trace_path,
        route_trace_path=route_trace_relpath,
        family_path=discovery.family_path,
        event_package_instance_id=event_package_instance_id,
        package_path=package_path,
        stat_trace_path=stat_trace_path,
        raw_run_id=raw.run_id,
        discovery_run_id=discovery.run_id,
        package_run_id=package_run_id,
        structural_run_id=structural_run_id,
        statistical_run_id=statistical_run_id,
        rm_run_id=rm_run_id,
        accepted_context_count=accepted_context_count,
        accepted_proposal_count=accepted_proposal_count,
        exact_structural_status=exact_status,
        exact_structural_feasible_hard_only=exact_feasible,
        exact_respecting_tuple_count=exact_tuple_count,
        gpd_str=gpd_str,
        gpd_stat_status=gpd_stat_status,
        gpd_stat=gpd_stat,
        gpd_stat_reason=gpd_stat_reason,
        rm_status=rm_status,
        overall_rm=overall_rm,
        rm_insufficient_data_group_count=rm_insufficient,
        structural_summary_path=structural_summary_path,
        statistical_summary_path=statistical_summary_path,
        rm_summary_path=rm_summary_path,
    )


def write_flattening_intervention_report(
    *,
    intervention_path: str | Path,
    category: str,
    label: str | None = None,
    seed: int = 0,
    timestamp: str | None = None,
    root: str | Path | None = None,
    command: list[str] | None = None,
) -> FlatteningInterventionArtifacts:
    repo_root = Path(root).resolve() if root is not None else None
    run_dir, run_id, manifest_timestamp = create_run_directory(
        category=category,
        label=label,
        timestamp=timestamp,
        root=repo_root,
    )
    effective_root = run_dir.parents[2]
    intervention_relpath = repo_relative_path(intervention_path, root=effective_root)
    spec = load_flattening_intervention(intervention_path)
    source_config = load_substrate_config(spec.source_config_artifact)

    derived_config_path = run_dir / "flattened-config.json"
    derived_config_relpath = repo_relative_path(
        derived_config_path, root=effective_root
    )
    derived_config, after_protocol_id = build_completed_config(
        source_config,
        spec,
        derived_config_artifact=derived_config_relpath,
    )
    derived_config_path.write_text(
        json.dumps(derived_config.model_dump(mode="json"), indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )

    deficit_config = StructuralDeficitConfig(
        allow_relax_hard=spec.comparison_config.allow_relax_hard,
        hard_proposal_relax_weight=spec.comparison_config.hard_proposal_relax_weight,
    )
    bundle_label = label or spec.intervention_id
    before = _run_side(
        side="before",
        config=source_config,
        config_path=spec.source_config_artifact,
        protocol_id=spec.before_protocol_id,
        endpoint_step_index=spec.route_extraction.before_endpoint_step_index,
        spec=spec,
        category=category,
        label=bundle_label,
        timestamp=timestamp,
        root=effective_root,
        bundle_dir=run_dir,
        deficit_config=deficit_config,
    )
    after = _run_side(
        side="after",
        config=derived_config,
        config_path=derived_config_relpath,
        protocol_id=after_protocol_id,
        endpoint_step_index=spec.route_extraction.after_endpoint_step_index,
        spec=spec,
        category=category,
        label=bundle_label,
        timestamp=timestamp,
        root=effective_root,
        bundle_dir=run_dir,
        deficit_config=deficit_config,
    )
    conclusion = _classify_outcome(
        before=before,
        after=after,
        rm_material_decrease_min=spec.comparison_config.rm_material_decrease_min,
    )

    summary_path = run_dir / "comparison-summary.json"
    note_path = run_dir / "comparison-note.md"
    result_note_path = run_dir / "result-note.json"
    manifest_path = run_dir / "run-manifest.json"
    output_paths = {
        "before_route_trace": before.route_trace_path,
        "after_route_trace": after.route_trace_path,
        "summary": repo_relative_path(summary_path, root=effective_root),
        "note": repo_relative_path(note_path, root=effective_root),
        "result_note": repo_relative_path(result_note_path, root=effective_root),
        "manifest": repo_relative_path(manifest_path, root=effective_root),
        "flattened_config": derived_config_relpath,
    }
    summary = {
        "intervention_id": spec.intervention_id,
        "source_config_path": spec.source_config_artifact,
        "before_protocol_id": spec.before_protocol_id,
        "completion_policy": spec.completion_policy.model_dump(mode="json"),
        "after_protocol_id": after_protocol_id,
        "route_extraction": spec.route_extraction.model_dump(mode="json"),
        "before": _side_summary(before),
        "after": _side_summary(after),
        "before_run_refs": {
            "raw_run_id": before.raw_run_id,
            "discovery_run_id": before.discovery_run_id,
            "package_run_id": before.package_run_id,
            "structural_run_id": before.structural_run_id,
            "statistical_run_id": before.statistical_run_id,
            "rm_run_id": before.rm_run_id,
        },
        "after_run_refs": {
            "raw_run_id": after.raw_run_id,
            "discovery_run_id": after.discovery_run_id,
            "package_run_id": after.package_run_id,
            "structural_run_id": after.structural_run_id,
            "statistical_run_id": after.statistical_run_id,
            "rm_run_id": after.rm_run_id,
        },
        "deltas": {
            "gpd_str_delta": None
            if before.gpd_str is None or after.gpd_str is None
            else after.gpd_str - before.gpd_str,
            "gpd_stat_delta": None
            if before.gpd_stat is None or after.gpd_stat is None
            else after.gpd_stat - before.gpd_stat,
            "overall_rm_delta": None
            if before.overall_rm is None or after.overall_rm is None
            else after.overall_rm - before.overall_rm,
        },
        "flattening_outcome": conclusion,
        "status_counts": {
            "before_gpd_stat_status": before.gpd_stat_status,
            "after_gpd_stat_status": after.gpd_stat_status,
            "before_rm_status": before.rm_status,
            "after_rm_status": after.rm_status,
        },
    }
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    note_path.write_text(
        _render_note(spec=spec, summary=summary, output_paths=output_paths),
        encoding="utf-8",
    )
    result_note = _build_result_note(
        run_id=run_id,
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
            "interventions",
            "flattening",
            intervention_relpath,
        ],
        seed=seed,
        input_artifacts={
            "intervention": intervention_relpath,
            "source_config": spec.source_config_artifact,
        },
        output_artifacts={
            "before_route_trace": output_paths["before_route_trace"],
            "after_route_trace": output_paths["after_route_trace"],
            "flattened_config": output_paths["flattened_config"],
            "summary": output_paths["summary"],
            "note": output_paths["note"],
            "result_note": output_paths["result_note"],
        },
        status="succeeded",
        git_commit=detect_git_commit(root=effective_root),
        metadata={
            "analysis_kind": "flattening_intervention",
            "intervention_id": spec.intervention_id,
            "flattening_outcome": conclusion,
        },
    )
    write_run_manifest(manifest, run_dir=run_dir)
    return FlatteningInterventionArtifacts(
        run_id=run_id,
        run_dir=repo_relative_path(run_dir, root=effective_root),
        manifest_path=output_paths["manifest"],
        before_route_trace_path=output_paths["before_route_trace"],
        after_route_trace_path=output_paths["after_route_trace"],
        summary_path=output_paths["summary"],
        note_path=output_paths["note"],
        result_note_path=output_paths["result_note"],
        conclusion=conclusion,
        summary=summary,
    )
