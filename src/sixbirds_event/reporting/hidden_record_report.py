from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import sys

from ..interventions.hidden_record import (
    build_augmented_instance,
    derive_after_route_trace,
    derive_after_stat_trace,
    derive_before_stat_trace,
    load_hidden_record_intervention,
    load_route_source_trace,
)
from ..provenance.models import (
    ContextProvenanceEntry,
    EventProvenanceEntry,
    PackageProvenance,
    ProposalProvenanceEntry,
    ProvenanceSourceRef,
    RefinementProvenance,
)
from ..reporting.rm_report import write_rm_report
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
from ..schemas.result_note import ResultNote
from ..solvers.structural_deficit import StructuralDeficitConfig


@dataclass(slots=True)
class HiddenRecordInterventionArtifacts:
    run_id: str
    run_dir: str
    manifest_path: str
    augmented_instance_path: str
    provenance_path: str
    before_stat_path: str
    after_stat_path: str
    summary_path: str
    note_path: str
    result_note_path: str
    conclusion: str
    summary: dict[str, object]


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


def _classify_conclusion(
    *,
    before_exact_feasible: bool,
    before_gpd_str: float | None,
    after_exact_feasible: bool,
    after_gpd_str: float | None,
) -> str:
    if (
        not before_exact_feasible
        and after_exact_feasible
        and after_gpd_str is not None
        and abs(after_gpd_str) <= 1e-9
    ):
        return "disappeared"
    if (
        before_gpd_str is not None
        and after_gpd_str is not None
        and after_gpd_str < before_gpd_str
    ):
        return "weakened"
    return "survived"


def _rm_metrics(report) -> dict[str, object]:
    return {
        "overall_rm": report.result.overall_rm,
        "insufficient_data_group_count": len(report.result.insufficient_data_groups),
        "preparation_endpoint_group_count": len(
            report.result.preparation_endpoint_results
        ),
    }


def _build_summary(
    *,
    spec,
    output_paths: dict[str, str],
    before_structural,
    after_structural,
    before_statistical,
    after_statistical,
    before_rm,
    after_rm,
    conclusion: str,
    after_route_trace_path: str,
) -> dict[str, object]:
    return {
        "intervention_id": spec.intervention_id,
        "before_instance_path": spec.before_instance_artifact,
        "route_source_path": spec.route_source_artifact,
        "augmented_instance_path": output_paths["augmented_instance"],
        "package_provenance_path": output_paths["provenance"],
        "before_stat_path": output_paths["before_stat"],
        "after_stat_path": output_paths["after_stat"],
        "after_route_trace_path": after_route_trace_path,
        "residue_field_name": spec.residue_field_name,
        "residue_values": spec.residue_values,
        "comparison_config": spec.comparison_config.model_dump(mode="json"),
        "before": {
            "exact_structural_feasible_hard_only": before_structural.summary.exact_extendable_hard_only,
            "gpd_str": before_structural.summary.gpd_str,
            "structural_reason": before_structural.summary.blocking_explanation.get(
                "hard_only_reason"
            ),
            "gpd_stat": before_statistical.result.gpd_stat,
            "statistical_solved": before_statistical.result.solved,
            "statistical_reason": before_statistical.result.reason,
            "rm": _rm_metrics(before_rm) if before_rm is not None else None,
        },
        "after": {
            "exact_structural_feasible_hard_only": after_structural.summary.exact_extendable_hard_only,
            "gpd_str": after_structural.summary.gpd_str,
            "structural_reason": after_structural.summary.blocking_explanation.get(
                "hard_only_reason"
            ),
            "gpd_stat": after_statistical.result.gpd_stat,
            "statistical_solved": after_statistical.result.solved,
            "statistical_reason": after_statistical.result.reason,
            "rm": _rm_metrics(after_rm) if after_rm is not None else None,
        },
        "deltas": {
            "gpd_str_delta": (
                None
                if before_structural.summary.gpd_str is None
                or after_structural.summary.gpd_str is None
                else after_structural.summary.gpd_str
                - before_structural.summary.gpd_str
            ),
            "gpd_stat_delta": (
                None
                if before_statistical.result.gpd_stat is None
                or after_statistical.result.gpd_stat is None
                else after_statistical.result.gpd_stat
                - before_statistical.result.gpd_stat
            ),
        },
        "sub_runs": {
            "before_structural": _artifact_record(before_structural),
            "after_structural": _artifact_record(after_structural),
            "before_statistical": _artifact_record(
                before_statistical, include_note=False, include_result_note=False
            ),
            "after_statistical": _artifact_record(
                after_statistical, include_note=False, include_result_note=False
            ),
            **(
                {"before_rm": _artifact_record(before_rm)}
                if before_rm is not None
                else {}
            ),
            **(
                {"after_rm": _artifact_record(after_rm)} if after_rm is not None else {}
            ),
        },
        "obstruction_status_after_intervention": conclusion,
    }


def _render_note(
    *,
    spec,
    summary: dict[str, object],
    output_paths: dict[str, str],
) -> str:
    before = summary["before"]
    after = summary["after"]
    lines = [
        "# Hidden Record Intervention Comparison",
        "",
        "## Intervention ID",
        f"- Intervention ID: `{spec.intervention_id}`",
        "",
        "## Before package/source description",
        f"- Before instance: `{spec.before_instance_artifact}`",
        f"- Route source: `{spec.route_source_artifact}`",
        "",
        "## Hidden record exposed",
        f"- Residue field name: `{spec.residue_field_name}`",
        f"- Residue values: `{spec.residue_values}`",
        "",
        "## Augmentation rule used",
        f"- Augmentation policy: `{spec.augmentation_policy}`",
        "- Contexts are duplicated once per residue value, atoms/events are namespaced by residue, and proposals are rewritten only for the residue assignments explicitly listed in the intervention input.",
        "",
        "## Before metrics",
        f"- Exact hard-only feasible: `{before['exact_structural_feasible_hard_only']}`",
        f"- `gpd_str`: `{before['gpd_str']}`",
        f"- `gpd_stat`: `{before['gpd_stat']}`",
        f"- Statistical solved: `{before['statistical_solved']}`",
        f"- Statistical reason: `{before['statistical_reason']}`",
        f"- RM summary: `{before['rm']}`",
        "",
        "## After metrics",
        f"- Exact hard-only feasible: `{after['exact_structural_feasible_hard_only']}`",
        f"- `gpd_str`: `{after['gpd_str']}`",
        f"- `gpd_stat`: `{after['gpd_stat']}`",
        f"- Statistical solved: `{after['statistical_solved']}`",
        f"- Statistical reason: `{after['statistical_reason']}`",
        f"- RM summary: `{after['rm']}`",
        "",
        "## Before / after comparison",
        f"- `gpd_str` delta: `{summary['deltas']['gpd_str_delta']}`",
        f"- `gpd_stat` delta: `{summary['deltas']['gpd_stat_delta']}`",
        f"- Obstruction status after intervention: `{summary['obstruction_status_after_intervention']}`",
        "",
        "## Technical interpretation",
        "- This intervention exposes route residue as an explicit record-admissible field and reruns the structural/statistical stack on the augmented package to test whether the original obstruction disappears, weakens, or survives.",
        "",
        "## RM caveat",
        "- RM is diagnostic-only and is reported here only as a route-sensitivity comparison, not as proof of extendability or non-extendability.",
        "",
        "## Artifact references",
        f"- Augmented instance: `{output_paths['augmented_instance']}`",
        f"- Package provenance: `{output_paths['provenance']}`",
        f"- Before statistical trace: `{output_paths['before_stat']}`",
        f"- After statistical trace: `{output_paths['after_stat']}`",
        f"- Comparison summary: `{output_paths['summary']}`",
        f"- Result note: `{output_paths['result_note']}`",
        f"- Run manifest: `{output_paths['manifest']}`",
    ]
    return "\n".join(lines) + "\n"


def _build_result_note(
    *,
    run_id: str,
    before_instance_id: str,
    augmented_instance_id: str,
    summary: dict[str, object],
    output_paths: dict[str, str],
) -> ResultNote:
    before = summary["before"]
    after = summary["after"]
    return ResultNote(
        note_format_version="result-note.v1",
        note_id=f"note_{run_id}",
        run_id=run_id,
        instance_ids=[before_instance_id, augmented_instance_id],
        metrics={
            "before_exact_structural_feasible_hard_only": before[
                "exact_structural_feasible_hard_only"
            ],
            "before_gpd_str": before["gpd_str"]
            if before["gpd_str"] is not None
            else -1.0,
            "before_gpd_stat": before["gpd_stat"]
            if before["gpd_stat"] is not None
            else -1.0,
            "after_exact_structural_feasible_hard_only": after[
                "exact_structural_feasible_hard_only"
            ],
            "after_gpd_str": after["gpd_str"] if after["gpd_str"] is not None else -1.0,
            "after_gpd_stat": after["gpd_stat"]
            if after["gpd_stat"] is not None
            else -1.0,
        },
        interpretation=(
            "Hidden-record intervention reran the structural/statistical comparison after exposing route residue as an explicit record. "
            f"Obstruction status after intervention: {summary['obstruction_status_after_intervention']}."
        ),
        caveats=[
            "RM is diagnostic-only when present.",
            "The augmentation follows the explicit proposal-to-residue assignment metadata from the intervention input.",
        ],
        artifact_refs={
            "augmented_instance": output_paths["augmented_instance"],
            "package_provenance": output_paths["provenance"],
            "before_stat": output_paths["before_stat"],
            "after_stat": output_paths["after_stat"],
            "summary": output_paths["summary"],
            "note": output_paths["note"],
            "manifest": output_paths["manifest"],
        },
        metadata={
            "obstruction_status_after_intervention": summary[
                "obstruction_status_after_intervention"
            ]
        },
    )


def _base_id_from_suffix(
    *, value: str, residue_field_name: str
) -> tuple[str, str] | None:
    marker = f"__{residue_field_name}_"
    if marker not in value:
        return None
    base, residue_value = value.rsplit(marker, maxsplit=1)
    if not base or not residue_value:
        return None
    return base, residue_value


def _build_augmented_package_provenance(
    *,
    spec,
    before_instance,
    augmented_instance,
    intervention_artifact: str,
    augmented_instance_artifact: str,
) -> PackageProvenance:
    before_context_ids = {context.context_id for context in before_instance.contexts}
    before_event_ids = {event.event_id for event in before_instance.events}
    before_proposal_ids = {
        proposal.proposal_id for proposal in before_instance.equality_proposals
    }
    selected_context_ids = set(spec.selected_context_ids)
    proposal_assignment_ids = {
        assignment.proposal_id for assignment in spec.proposal_residue_assignments
    }
    source_artifacts = {
        "before_instance": spec.before_instance_artifact,
        "route_source": spec.route_source_artifact,
        "intervention": intervention_artifact,
    }
    context_entries: list[ContextProvenanceEntry] = []
    for context in augmented_instance.contexts:
        split = _base_id_from_suffix(
            value=context.context_id,
            residue_field_name=spec.residue_field_name,
        )
        if split is None:
            context_entries.append(
                ContextProvenanceEntry(
                    context_id=context.context_id,
                    origin_kind="designed_context",
                    source_refs=[
                        ProvenanceSourceRef(
                            artifact=spec.before_instance_artifact,
                            source_kind="ancestor_context",
                            source_item_id=context.context_id,
                        )
                    ],
                )
            )
            continue
        ancestor_context_id, residue_value = split
        if (
            ancestor_context_id not in before_context_ids
            or ancestor_context_id not in selected_context_ids
        ):
            continue
        context_entries.append(
            ContextProvenanceEntry(
                context_id=context.context_id,
                origin_kind="intervention_split_context",
                ancestor_context_id=ancestor_context_id,
                source_refs=[
                    ProvenanceSourceRef(
                        artifact=spec.before_instance_artifact,
                        source_kind="ancestor_context",
                        source_item_id=ancestor_context_id,
                    ),
                    ProvenanceSourceRef(
                        artifact=intervention_artifact,
                        source_kind="intervention_selected_context",
                        source_item_id=ancestor_context_id,
                    ),
                    ProvenanceSourceRef(
                        artifact=spec.route_source_artifact,
                        source_kind="route_residue_source",
                    ),
                ],
                refinement=RefinementProvenance(
                    ancestor_id=ancestor_context_id,
                    residue_field_name=spec.residue_field_name,
                    residue_value=residue_value,
                    source_artifact=spec.route_source_artifact,
                ),
            )
        )
    event_entries: list[EventProvenanceEntry] = []
    for event in augmented_instance.events:
        split = _base_id_from_suffix(
            value=event.event_id,
            residue_field_name=spec.residue_field_name,
        )
        if split is None:
            event_entries.append(
                EventProvenanceEntry(
                    event_id=event.event_id,
                    origin_kind="designed_event",
                    source_refs=[
                        ProvenanceSourceRef(
                            artifact=spec.before_instance_artifact,
                            source_kind="ancestor_event",
                            source_item_id=event.event_id,
                        )
                    ],
                )
            )
            continue
        ancestor_event_id, residue_value = split
        if ancestor_event_id not in before_event_ids:
            continue
        event_entries.append(
            EventProvenanceEntry(
                event_id=event.event_id,
                origin_kind="intervention_split_event",
                ancestor_event_id=ancestor_event_id,
                source_refs=[
                    ProvenanceSourceRef(
                        artifact=spec.before_instance_artifact,
                        source_kind="ancestor_event",
                        source_item_id=ancestor_event_id,
                    ),
                    ProvenanceSourceRef(
                        artifact=spec.route_source_artifact,
                        source_kind="route_residue_source",
                    ),
                ],
                refinement=RefinementProvenance(
                    ancestor_id=ancestor_event_id,
                    residue_field_name=spec.residue_field_name,
                    residue_value=residue_value,
                    source_artifact=spec.route_source_artifact,
                ),
            )
        )
    proposal_entries: list[ProposalProvenanceEntry] = []
    for proposal in augmented_instance.equality_proposals:
        split = _base_id_from_suffix(
            value=proposal.proposal_id,
            residue_field_name=spec.residue_field_name,
        )
        if split is None:
            proposal_entries.append(
                ProposalProvenanceEntry(
                    proposal_id=proposal.proposal_id,
                    origin_kind="designed_proposal",
                    source_refs=[
                        ProvenanceSourceRef(
                            artifact=spec.before_instance_artifact,
                            source_kind="ancestor_proposal",
                            source_item_id=proposal.proposal_id,
                        )
                    ],
                )
            )
            continue
        ancestor_proposal_id, residue_value = split
        if (
            ancestor_proposal_id not in before_proposal_ids
            or ancestor_proposal_id not in proposal_assignment_ids
        ):
            continue
        proposal_entries.append(
            ProposalProvenanceEntry(
                proposal_id=proposal.proposal_id,
                origin_kind="intervention_split_proposal",
                ancestor_proposal_id=ancestor_proposal_id,
                source_refs=[
                    ProvenanceSourceRef(
                        artifact=spec.before_instance_artifact,
                        source_kind="ancestor_proposal",
                        source_item_id=ancestor_proposal_id,
                    ),
                    ProvenanceSourceRef(
                        artifact=intervention_artifact,
                        source_kind="intervention_proposal_assignment",
                        source_item_id=ancestor_proposal_id,
                    ),
                    ProvenanceSourceRef(
                        artifact=spec.route_source_artifact,
                        source_kind="route_residue_source",
                    ),
                ],
                refinement=RefinementProvenance(
                    ancestor_id=ancestor_proposal_id,
                    residue_field_name=spec.residue_field_name,
                    residue_value=residue_value,
                    source_artifact=spec.route_source_artifact,
                ),
            )
        )
    return PackageProvenance(
        provenance_format_version="package-provenance.v1",
        package_artifact=augmented_instance_artifact,
        package_id=augmented_instance.instance_id,
        provenance_mode="intervention_derived",
        source_artifacts=source_artifacts,
        context_entries=context_entries,
        event_entries=event_entries,
        proposal_entries=proposal_entries,
        metadata={"intervention_id": spec.intervention_id},
    )


def write_hidden_record_intervention_report(
    *,
    intervention_path: str | Path,
    category: str,
    label: str | None = None,
    seed: int = 0,
    timestamp: str | None = None,
    root: str | Path | None = None,
    command: list[str] | None = None,
) -> HiddenRecordInterventionArtifacts:
    repo_root = Path(root).resolve() if root is not None else None
    run_dir, run_id, manifest_timestamp = create_run_directory(
        category=category,
        label=label,
        timestamp=timestamp,
        root=repo_root,
    )
    effective_root = run_dir.parents[2]
    intervention_relpath = repo_relative_path(intervention_path, root=effective_root)

    spec = load_hidden_record_intervention(intervention_path)
    before_instance = load_event_package_instance(spec.before_instance_artifact)
    route_source = load_route_source_trace(spec.route_source_artifact)

    augmented_instance_path = run_dir / "augmented-instance.json"
    provenance_path = run_dir / "package-provenance.json"
    before_stat_path = run_dir / "before-stat.json"
    after_stat_path = run_dir / "after-stat.json"
    after_route_path = run_dir / "after-route.json"
    summary_path = run_dir / "comparison-summary.json"
    note_path = run_dir / "comparison-note.md"
    result_note_path = run_dir / "result-note.json"
    manifest_path = run_dir / "run-manifest.json"
    output_paths = {
        "augmented_instance": repo_relative_path(
            augmented_instance_path, root=effective_root
        ),
        "provenance": repo_relative_path(provenance_path, root=effective_root),
        "before_stat": repo_relative_path(before_stat_path, root=effective_root),
        "after_stat": repo_relative_path(after_stat_path, root=effective_root),
        "after_route": repo_relative_path(after_route_path, root=effective_root),
        "summary": repo_relative_path(summary_path, root=effective_root),
        "note": repo_relative_path(note_path, root=effective_root),
        "result_note": repo_relative_path(result_note_path, root=effective_root),
        "manifest": repo_relative_path(manifest_path, root=effective_root),
    }

    augmented_instance = build_augmented_instance(
        spec,
        before_instance,
        created_at=manifest_timestamp,
        augmented_instance_artifact=output_paths["augmented_instance"],
    )
    before_stat = derive_before_stat_trace(spec, before_instance, route_source)
    after_stat = derive_after_stat_trace(
        spec,
        augmented_instance,
        route_source,
        augmented_instance_artifact=output_paths["augmented_instance"],
    )
    after_route = derive_after_route_trace(
        spec,
        augmented_instance,
        route_source,
        augmented_instance_artifact=output_paths["augmented_instance"],
    )
    provenance = _build_augmented_package_provenance(
        spec=spec,
        before_instance=before_instance,
        augmented_instance=augmented_instance,
        intervention_artifact=intervention_relpath,
        augmented_instance_artifact=output_paths["augmented_instance"],
    )

    augmented_instance_path.write_text(
        json.dumps(augmented_instance.model_dump(mode="json"), indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    provenance_path.write_text(
        json.dumps(provenance.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    before_stat_path.write_text(
        json.dumps(before_stat.model_dump(mode="json"), indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    after_stat_path.write_text(
        json.dumps(after_stat.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    after_route_path.write_text(
        json.dumps(after_route.model_dump(mode="json"), indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )

    deficit_config = StructuralDeficitConfig(
        allow_relax_hard=spec.comparison_config.allow_relax_hard,
        hard_proposal_relax_weight=spec.comparison_config.hard_proposal_relax_weight,
    )
    before_structural = generate_structural_report(
        before_instance,
        instance_path=spec.before_instance_artifact,
        category=category,
        label=f"{label or spec.intervention_id}-before-structural",
        seed=seed,
        timestamp=timestamp,
        root=effective_root,
        command=["python", "-m", "sixbirds_event", "intervention", "before-structural"],
        deficit_config=deficit_config,
    )
    after_structural = generate_structural_report(
        augmented_instance,
        instance_path=output_paths["augmented_instance"],
        category=category,
        label=f"{label or spec.intervention_id}-after-structural",
        seed=seed,
        timestamp=timestamp,
        root=effective_root,
        command=["python", "-m", "sixbirds_event", "intervention", "after-structural"],
        deficit_config=deficit_config,
    )
    before_statistical = write_statistical_summary(
        before_instance,
        [before_stat],
        instance_path=spec.before_instance_artifact,
        trace_paths=[output_paths["before_stat"]],
        category=category,
        label=f"{label or spec.intervention_id}-before-stat",
        seed=seed,
        timestamp=timestamp,
        root=effective_root,
        command=["python", "-m", "sixbirds_event", "intervention", "before-stat"],
    )
    after_statistical = write_statistical_summary(
        augmented_instance,
        [after_stat],
        instance_path=output_paths["augmented_instance"],
        trace_paths=[output_paths["after_stat"]],
        category=category,
        label=f"{label or spec.intervention_id}-after-stat",
        seed=seed,
        timestamp=timestamp,
        root=effective_root,
        command=["python", "-m", "sixbirds_event", "intervention", "after-stat"],
    )
    before_rm = (
        write_rm_report(
            [route_source],
            trace_paths=[spec.route_source_artifact],
            category=category,
            label=f"{label or spec.intervention_id}-before-rm",
            instance=before_instance,
            instance_path=spec.before_instance_artifact,
            seed=seed,
            timestamp=timestamp,
            root=effective_root,
            command=["python", "-m", "sixbirds_event", "intervention", "before-rm"],
        )
        if spec.comparison_config.include_rm
        else None
    )
    after_rm = (
        write_rm_report(
            [after_route],
            trace_paths=[output_paths["after_route"]],
            category=category,
            label=f"{label or spec.intervention_id}-after-rm",
            instance=augmented_instance,
            instance_path=output_paths["augmented_instance"],
            seed=seed,
            timestamp=timestamp,
            root=effective_root,
            command=["python", "-m", "sixbirds_event", "intervention", "after-rm"],
        )
        if spec.comparison_config.include_rm
        else None
    )

    conclusion = _classify_conclusion(
        before_exact_feasible=before_structural.summary.exact_extendable_hard_only,
        before_gpd_str=before_structural.summary.gpd_str,
        after_exact_feasible=after_structural.summary.exact_extendable_hard_only,
        after_gpd_str=after_structural.summary.gpd_str,
    )
    summary = _build_summary(
        spec=spec,
        output_paths=output_paths,
        before_structural=before_structural,
        after_structural=after_structural,
        before_statistical=before_statistical,
        after_statistical=after_statistical,
        before_rm=before_rm,
        after_rm=after_rm,
        conclusion=conclusion,
        after_route_trace_path=output_paths["after_route"],
    )
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    note_path.write_text(
        _render_note(spec=spec, summary=summary, output_paths=output_paths),
        encoding="utf-8",
    )
    result_note = _build_result_note(
        run_id=run_id,
        before_instance_id=before_instance.instance_id,
        augmented_instance_id=augmented_instance.instance_id,
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
            "hidden-record",
            intervention_relpath,
        ],
        seed=seed,
        input_artifacts={
            "intervention": intervention_relpath,
            "before_instance": spec.before_instance_artifact,
            "route_source": spec.route_source_artifact,
        },
        output_artifacts={
            "augmented_instance": output_paths["augmented_instance"],
            "package_provenance": output_paths["provenance"],
            "before_stat": output_paths["before_stat"],
            "after_stat": output_paths["after_stat"],
            "after_route": output_paths["after_route"],
            "summary": output_paths["summary"],
            "note": output_paths["note"],
            "result_note": output_paths["result_note"],
        },
        status="succeeded",
        git_commit=detect_git_commit(root=effective_root),
        metadata={
            "analysis_kind": "hidden_record_intervention",
            "intervention_id": spec.intervention_id,
            "obstruction_status_after_intervention": conclusion,
        },
    )
    write_run_manifest(manifest, run_dir=run_dir)
    return HiddenRecordInterventionArtifacts(
        run_id=run_id,
        run_dir=repo_relative_path(run_dir, root=effective_root),
        manifest_path=output_paths["manifest"],
        augmented_instance_path=output_paths["augmented_instance"],
        provenance_path=output_paths["provenance"],
        before_stat_path=output_paths["before_stat"],
        after_stat_path=output_paths["after_stat"],
        summary_path=output_paths["summary"],
        note_path=output_paths["note"],
        result_note_path=output_paths["result_note"],
        conclusion=conclusion,
        summary=summary,
    )
