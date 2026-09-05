from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import csv
import json
from pathlib import Path
import sys

from ..audits.quotient_feasibility import (
    run_quotient_feasibility_audit,
)
from ..pica_bridge.ingest import load_pica_export_bundle
from ..pica_bridge.packaging_surface import resolve_pica_packaging_surface
from ..pica_bridge.pilot import PicaPilotArtifacts, run_pica_pilot_campaign
from ..provenance.audit import write_provenance_audit_report
from ..reporting.package_build_report import write_package_build_report
from ..reporting.statistical_report import write_statistical_summary
from ..run_registry import (
    build_run_manifest,
    create_run_directory,
    detect_git_commit,
    get_repo_root,
    repo_relative_path,
    write_run_manifest,
)
from ..schemas.result_note import ResultNote
from ..solvers.structural_exact import solve_exact_structural_feasibility
from ..validation import load_model
from .models import (
    FrozenSliceProjectionFamily,
    MechanismAxisClaimLevel,
    MechanismAxisRow,
    MechanismAxisSearch,
    MechanismAxisSearchPoint,
    MechanismAxisTable,
    MechanismSignalKind,
    TargetedCandidateLabel,
    TargetedSearchEvaluation,
)
from .pica_frozen_slice_obstruction import _discover_family
from .pica_targeted_obstruction import (
    _baseline_deficit_evaluation,
    _candidate_deficit_evaluation,
    _derive_pica_stat_trace,
    _load_pilot_config,
    _merge_pilot_outputs,
    _pilot_config_for_seed,
    _point_has_dual_mode_difference,
    _sec_summary,
)


MECHANISM_AXIS_CLASSIFIER_VERSION = "mechanism-axis-classifier.v1"
MECHANISM_AXIS_ADEQUACY_VERSION = "mechanism-axis-adequacy-floor.v1"


@dataclass(slots=True)
class MechanismAxisArtifacts:
    run_id: str
    run_dir: str
    table_csv_path: str
    table_json_path: str
    summary_path: str
    note_path: str
    result_note_path: str
    manifest_path: str
    table: MechanismAxisTable
    classification_counts: dict[str, int]
    claim_level_counts: dict[str, int]
    adequacy: dict[str, object]
    outcome_path: str
    outcome_kind: str
    best_point_id: str | None


@dataclass(slots=True)
class _DiscoveryPoint:
    point_id: str
    preparation_id: str
    protocol_id: str
    selected_protocol_step_ids: list[str]
    selected_step_indices: list[int]


@dataclass(slots=True)
class _PointArtifacts:
    row: MechanismAxisRow
    catalog_operator_ids: set[str]
    catalog_family_ids: set[str]
    selected_operator_ids: set[str]
    selected_family_ids: set[str]
    selected_sources: set[str]


def load_mechanism_axis_search(path: str | Path) -> MechanismAxisSearch:
    model = load_model(path, kind="mechanism-axis-search")
    assert isinstance(model, MechanismAxisSearch)
    return model


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    fieldnames = list(rows[0]) if rows else []
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        if rows:
            writer.writerows(rows)


def _projection_family_map(
    search: MechanismAxisSearch,
) -> dict[str, FrozenSliceProjectionFamily]:
    return {family.projection_id: family for family in search.projection_families}


def _active_projection_families(
    search: MechanismAxisSearch,
) -> list[FrozenSliceProjectionFamily]:
    family_map = _projection_family_map(search)
    return [
        family_map[projection_id]
        for projection_id in search.active_projection_family_ids
    ]


def _not_applicable_evaluation() -> TargetedSearchEvaluation:
    return TargetedSearchEvaluation(
        exact_structural_status="not_applicable",
        gpd_str_status="not_applicable",
        gpd_stat_status="not_applicable",
    )


def _candidate_classification(
    *,
    row: MechanismAxisRow,
    search: MechanismAxisSearch,
) -> TargetedCandidateLabel:
    if row.event_package_path is None or row.accepted_context_count < 2:
        return "trivial_or_nonrecording"
    if row.all_accepted_proposals.gpd_str_status != "solved":
        return "inconclusive"

    provenance_ok = row.provenance_classification == "admissible"
    some_provenance = row.provenance_classification in {
        "admissible",
        "partially_supported",
    }
    positive_candidate_deficit = (
        row.all_accepted_proposals.gpd_str is not None
        and row.all_accepted_proposals.gpd_str
        >= search.candidate_classification_thresholds.strong_nonextendable_min_gpd_str
    )
    candidate_exact_fails = row.all_accepted_proposals.exact_feasible is False
    strong_reason = row.all_accepted_proposals.exact_failure_reason in {
        "no_respecting_tuples",
        "coverage_failure",
    }

    if (
        provenance_ok
        and row.accepted_proper_coarse_proposal_count
        >= search.candidate_classification_thresholds.min_accepted_coarse_proposal_count
        and candidate_exact_fails
        and positive_candidate_deficit
        and strong_reason
    ):
        return "strongly_nonextendable_candidate"

    if (
        provenance_ok
        and row.all_accepted_proposals.exact_feasible is True
        and row.all_accepted_proposals.gpd_str == 0
    ):
        return "extendable_candidate"

    if some_provenance and (
        candidate_exact_fails
        or (
            row.all_accepted_proposals.gpd_str is not None
            and row.all_accepted_proposals.gpd_str > 0
        )
        or (
            row.all_accepted_proposals.gpd_stat_status == "solved"
            and row.all_accepted_proposals.gpd_stat is not None
            and row.all_accepted_proposals.gpd_stat
            > search.candidate_classification_thresholds.near_zero_gpd_stat
        )
        or _point_has_dual_mode_difference(row)
    ):
        return "weakly_frustrated_candidate"

    return "inconclusive"


_CLAIM_ORDER: dict[MechanismAxisClaimLevel, int] = {
    "mechanism_dependence": 0,
    "nontrivial_multicontext_structure": 1,
    "package_conflict_tension": 2,
}


def _bounded_claim_level(
    claim: MechanismAxisClaimLevel,
    *,
    ceiling: MechanismAxisClaimLevel,
) -> MechanismAxisClaimLevel:
    max_rank = _CLAIM_ORDER[ceiling]
    allowed = [name for name, rank in _CLAIM_ORDER.items() if rank <= max_rank]
    return (
        sorted(allowed, key=lambda name: _CLAIM_ORDER[name])[-1]
        if _CLAIM_ORDER[claim] > max_rank
        else claim
    )


def _claim_level(
    *,
    row: MechanismAxisRow,
    search: MechanismAxisSearch,
) -> MechanismAxisClaimLevel:
    if row.candidate_classification in {
        "strongly_nonextendable_candidate",
        "weakly_frustrated_candidate",
    }:
        claim = "package_conflict_tension"
    elif row.accepted_context_count >= 2 and row.accepted_proper_coarse_event_count > 0:
        claim = "nontrivial_multicontext_structure"
    else:
        claim = "mechanism_dependence"
    return _bounded_claim_level(claim, ceiling=search.claim_ceiling)


def _signal_kind(
    *,
    row: MechanismAxisRow,
    control_row: MechanismAxisRow,
) -> MechanismSignalKind:
    if row.candidate_classification == "strongly_nonextendable_candidate":
        return "strong_mechanism_side_tension"
    if row.candidate_classification == "weakly_frustrated_candidate":
        return "weak_frustration"
    if row.changed_packaging_surface_relative_to_control and (
        row.accepted_context_count == control_row.accepted_context_count
        and row.accepted_proper_coarse_event_count
        == control_row.accepted_proper_coarse_event_count
        and row.accepted_proper_coarse_proposal_count
        == control_row.accepted_proper_coarse_proposal_count
    ):
        return "packaging_surface_change_only"
    if (
        row.accepted_context_count > control_row.accepted_context_count
        or row.accepted_proper_coarse_event_count
        > control_row.accepted_proper_coarse_event_count
        or row.accepted_proper_coarse_proposal_count
        > control_row.accepted_proper_coarse_proposal_count
    ):
        return "package_structure_richer"
    if not row.changed_packaging_surface_relative_to_control:
        return "control_like"
    return "inconclusive"


def _evaluate_adequacy(
    *,
    rows: list[MechanismAxisRow],
    search: MechanismAxisSearch,
) -> dict[str, object]:
    counts = {
        "total_point_count": len(rows),
        "admissible_built_package_count": sum(
            1
            for row in rows
            if row.event_package_path is not None
            and row.provenance_classification == "admissible"
        ),
        "points_with_proper_coarse_events": sum(
            1 for row in rows if row.accepted_proper_coarse_event_count > 0
        ),
        "points_with_changed_packaging_surface_relative_to_control": sum(
            1 for row in rows if row.changed_packaging_surface_relative_to_control
        ),
        "points_with_dual_mode_difference": sum(
            1 for row in rows if _point_has_dual_mode_difference(row)
        ),
    }
    floor = search.adequacy_floor
    checks = {
        "total_point_count": counts["total_point_count"] >= floor.min_total_point_count,
        "admissible_built_package_count": counts["admissible_built_package_count"]
        >= floor.min_admissible_built_package_count,
        "points_with_proper_coarse_events": counts["points_with_proper_coarse_events"]
        >= floor.min_points_with_proper_coarse_events,
        "points_with_changed_packaging_surface_relative_to_control": counts[
            "points_with_changed_packaging_surface_relative_to_control"
        ]
        >= floor.min_points_with_changed_packaging_surface_relative_to_control,
        "points_with_dual_mode_difference": counts["points_with_dual_mode_difference"]
        >= floor.min_points_with_dual_mode_difference,
    }
    return {
        "adequate": all(checks.values()),
        "counts": counts,
        "checks": checks,
        "thresholds": floor.model_dump(mode="json"),
    }


def _best_point(rows: list[MechanismAxisRow]) -> MechanismAxisRow | None:
    strong = [
        row
        for row in rows
        if row.candidate_classification == "strongly_nonextendable_candidate"
    ]
    if strong:
        return sorted(
            strong,
            key=lambda row: (
                -(row.all_accepted_proposals.gpd_str or 0.0),
                row.all_accepted_proposals.exact_respecting_tuple_count
                if row.all_accepted_proposals.exact_respecting_tuple_count is not None
                else 10**9,
                row.point_id,
            ),
        )[0]
    weak = [
        row
        for row in rows
        if row.candidate_classification == "weakly_frustrated_candidate"
    ]
    if weak:
        return sorted(
            weak,
            key=lambda row: (
                -(row.all_accepted_proposals.gpd_str or 0.0),
                -row.accepted_proper_coarse_proposal_count,
                row.point_id,
            ),
        )[0]
    return None


def _row_to_csv_record(row: MechanismAxisRow) -> dict[str, object]:
    return {
        "point_id": row.point_id,
        "axis": row.axis,
        "source_pica_campaign_config_path": row.source_pica_campaign_config_path,
        "produced_export_bundle_path": row.produced_export_bundle_path,
        "packaging_surface_summary_path": row.packaging_surface_summary_path,
        "discovered_context_family_path": row.discovered_context_family_path,
        "event_package_path": row.event_package_path,
        "provenance_classification": row.provenance_classification,
        "accepted_context_count": row.accepted_context_count,
        "accepted_singleton_event_count": row.accepted_singleton_event_count,
        "accepted_proper_coarse_event_count": row.accepted_proper_coarse_event_count,
        "accepted_shared_event_proposal_count": row.accepted_shared_event_proposal_count,
        "accepted_proper_coarse_proposal_count": row.accepted_proper_coarse_proposal_count,
        "baseline_exact_feasible": row.baseline_hard_only.exact_feasible,
        "baseline_exact_respecting_tuple_count": row.baseline_hard_only.exact_respecting_tuple_count,
        "baseline_gpd_str": row.baseline_hard_only.gpd_str,
        "baseline_gpd_stat": row.baseline_hard_only.gpd_stat,
        "candidate_exact_feasible": row.all_accepted_proposals.exact_feasible,
        "candidate_exact_respecting_tuple_count": row.all_accepted_proposals.exact_respecting_tuple_count,
        "candidate_exact_failure_reason": row.all_accepted_proposals.exact_failure_reason,
        "candidate_gpd_str": row.all_accepted_proposals.gpd_str,
        "candidate_gpd_stat": row.all_accepted_proposals.gpd_stat,
        "selected_packaging_sources": "|".join(row.selected_packaging_sources),
        "selected_packaging_operator_count": row.selected_packaging_operator_count,
        "selected_packaging_family_count": row.selected_packaging_family_count,
        "packaging_support_slice_count": row.packaging_support_slice_count,
        "changed_packaging_surface_relative_to_control": row.changed_packaging_surface_relative_to_control,
        "quotient_class_count": row.quotient_class_count,
        "quotient_accepted_only_survivor_count": row.quotient_accepted_only_survivor_count,
        "quotient_natural_pairing_survivor_count": row.quotient_natural_pairing_survivor_count,
        "quotient_candidate_subset_witness_found": row.quotient_candidate_subset_witness_found,
        "quotient_witness_classification": row.quotient_witness_classification,
        "quotient_witness_candidate_ids": "|".join(row.quotient_witness_candidate_ids),
        "candidate_classification": row.candidate_classification,
        "claim_level_supported": row.claim_level_supported,
        "mechanism_signal_kind": row.mechanism_signal_kind,
    }


def _build_summary(
    *,
    search: MechanismAxisSearch,
    rows: list[MechanismAxisRow],
    adequacy: dict[str, object],
    classification_counts: dict[str, int],
    claim_level_counts: dict[str, int],
    best_point: MechanismAxisRow | None,
    outcome_kind: str,
    output_paths: dict[str, str],
) -> dict[str, object]:
    packaging_surface_diversity = {
        "points_with_changed_packaging_surface_relative_to_control": adequacy["counts"][
            "points_with_changed_packaging_surface_relative_to_control"
        ],
        "selected_packaging_sources_by_point": {
            row.point_id: row.selected_packaging_sources for row in rows
        },
        "selected_packaging_operator_count_by_point": {
            row.point_id: row.selected_packaging_operator_count for row in rows
        },
        "selected_packaging_family_count_by_point": {
            row.point_id: row.selected_packaging_family_count for row in rows
        },
    }
    quotient_counts = dict(
        Counter(
            row.quotient_witness_classification
            for row in rows
            if row.quotient_witness_classification is not None
        )
    )
    return {
        "search_id": search.search_id,
        "config_family_covered": [
            point.pilot_config_artifact for point in search.points
        ],
        "fixed_search_settings": {
            "axis": "mechanism",
            "fixed_lens_family_label": search.fixed_lens_family_label,
            "fixed_packaging_policy_label": search.fixed_packaging_policy_label,
            "active_projection_family_ids": list(search.active_projection_family_ids),
            "selected_protocol_step_ids": list(search.selected_protocol_step_ids),
            "selected_step_indices": list(search.selected_step_indices),
            "event_generation_thresholds": search.event_generation_thresholds.model_dump(
                mode="json"
            ),
            "shared_event_inference_thresholds": (
                search.shared_event_inference_thresholds.model_dump(mode="json")
            ),
            "claim_ceiling": search.claim_ceiling,
        },
        "packaging_surface_diversity_summary": packaging_surface_diversity,
        "quotient_feasibility_summary": {
            "points_with_quotient_audit": sum(
                1 for row in rows if row.quotient_witness_classification is not None
            ),
            "counts_by_witness_classification": quotient_counts,
            "accepted_only_survivor_count_by_point": {
                row.point_id: row.quotient_accepted_only_survivor_count
                for row in rows
                if row.quotient_accepted_only_survivor_count is not None
            },
            "natural_pairing_survivor_count_by_point": {
                row.point_id: row.quotient_natural_pairing_survivor_count
                for row in rows
                if row.quotient_natural_pairing_survivor_count is not None
            },
            "witness_candidate_ids_by_point": {
                row.point_id: row.quotient_witness_candidate_ids
                for row in rows
                if row.quotient_witness_candidate_ids
            },
            "contains_accepted_proposal_obstruction": quotient_counts.get(
                "accepted_proposal_obstruction", 0
            )
            > 0,
            "contains_candidate_subset_witness": quotient_counts.get(
                "candidate_subset_quotient_witness", 0
            )
            > 0,
        },
        "adequacy_floor_thresholds": adequacy["thresholds"],
        "adequacy_floor_result": {
            "adequate": adequacy["adequate"],
            "checks": adequacy["checks"],
            "counts": adequacy["counts"],
        },
        "counts_by_candidate_class": classification_counts,
        "counts_by_claim_level": claim_level_counts,
        "best_point_id": None if best_point is None else best_point.point_id,
        "negative_result": outcome_kind == "negative_result",
        "design_inadequate": outcome_kind == "design_inadequate",
        "claim_ceiling_note": "Mechanism-axis findings are regime-selection evidence only and do not justify same-system contextuality or theorem-level obstruction claims.",
        "output_paths": output_paths,
    }


def _render_note(
    *,
    search: MechanismAxisSearch,
    rows: list[MechanismAxisRow],
    adequacy: dict[str, object],
    classification_counts: dict[str, int],
    claim_level_counts: dict[str, int],
    best_point: MechanismAxisRow | None,
    outcome_kind: str,
    output_paths: dict[str, str],
) -> str:
    lines = [
        "# Mechanism-Axis Search",
        "",
        f"- Search ID: `{search.search_id}`",
        f"- Campaign family covered: `{', '.join(point.point_id for point in search.points)}`",
        "- Held fixed:",
        f"  - lens family: `{search.fixed_lens_family_label}`",
        f"  - packaging policy: `{search.fixed_packaging_policy_label}`",
        f"  - projection families: `{', '.join(search.active_projection_family_ids)}`",
        f"  - selected protocol steps: `{', '.join(search.selected_protocol_step_ids)}`",
        f"  - selected step indices: `{', '.join(str(index) for index in search.selected_step_indices)}`",
        "- Varied mechanically:",
        "  - enable matrix / mechanism family / control-space point through the committed pilot config family",
        "",
        "## Packaging-surface changes observed",
    ]
    for row in rows:
        lines.append(
            f"- `{row.point_id}`: sources=`{','.join(row.selected_packaging_sources) or 'none'}`, selected_operator_count=`{row.selected_packaging_operator_count}`, selected_family_count=`{row.selected_packaging_family_count}`, changed_relative_to_control=`{row.changed_packaging_surface_relative_to_control}`, signal=`{row.mechanism_signal_kind}`"
        )
    lines.extend(["", "## Quotient feasibility"])
    for row in rows:
        lines.append(
            f"- `{row.point_id}`: quotient_class_count=`{row.quotient_class_count}`, accepted_only_survivors=`{row.quotient_accepted_only_survivor_count}`, natural_pairing_survivors=`{row.quotient_natural_pairing_survivor_count}`, candidate_subset_witness_found=`{row.quotient_candidate_subset_witness_found}`, witness_classification=`{row.quotient_witness_classification}`, witness_candidate_ids=`{','.join(row.quotient_witness_candidate_ids) or 'none'}`"
        )
    quotient_counts = Counter(
        row.quotient_witness_classification
        for row in rows
        if row.quotient_witness_classification is not None
    )
    if quotient_counts:
        lines.append("- Quotient witness counts:")
        for label, count in sorted(quotient_counts.items()):
            lines.append(f"  - `{label}`: `{count}`")
    lines.extend(
        [
            "",
            "## Evaluation modes",
            "- `baseline_hard_only` uses hard proposals only.",
            "- `all_accepted_proposals` uses all accepted proposals from the built package.",
            "- Dual-mode divergence is diagnostic of mechanism-side tension but does not override the mechanism-axis claim ceiling.",
            "",
            "## Candidate classes",
        ]
    )
    for label, count in sorted(classification_counts.items()):
        lines.append(f"- `{label}`: `{count}`")
    lines.extend(
        [
            "",
            "## Claim levels",
        ]
    )
    for label, count in sorted(claim_level_counts.items()):
        lines.append(f"- `{label}`: `{count}`")
    lines.extend(
        [
            "",
            "## Adequacy floor",
            f"- adequate: `{adequacy['adequate']}`",
        ]
    )
    for key, value in sorted(adequacy["checks"].items()):
        lines.append(
            f"- `{key}`: check=`{value}`, count=`{adequacy['counts'][key]}`, threshold=`{adequacy['thresholds'][f'min_{key}']}`"
            if f"min_{key}" in adequacy["thresholds"]
            else f"- `{key}`: check=`{value}`, count=`{adequacy['counts'][key]}`"
        )
    lines.extend(
        [
            "",
            "## Outcome",
            f"- outcome_kind: `{outcome_kind}`",
            f"- best_point: `{best_point.point_id if best_point is not None else 'null'}`",
            "- claim ceiling: `mechanism` axis results stop at mechanism-side regime/tension claims and do not support same-system contextuality or theorem-level packaging obstruction.",
            "- RM is diagnostic-only.",
            "- Status values such as `unsolved`, `insufficient_data`, and `not_applicable` are preserved explicitly rather than coerced into numeric values.",
            "",
            "## Artifact refs",
        ]
    )
    for key, value in sorted(output_paths.items()):
        lines.append(f"- `{key}`: `{value}`")
    return "\n".join(lines) + "\n"


def _build_result_note(
    *,
    run_id: str,
    table: MechanismAxisTable,
    adequacy: dict[str, object],
    classification_counts: dict[str, int],
    claim_level_counts: dict[str, int],
    outcome_kind: str,
    best_point: MechanismAxisRow | None,
    output_paths: dict[str, str],
) -> ResultNote:
    metrics: dict[str, object] = {
        "point_count": table.row_count,
        "adequacy_met": adequacy["adequate"],
        "outcome_kind": outcome_kind,
        **adequacy["counts"],
    }
    for label, count in sorted(classification_counts.items()):
        metrics[f"classification_count_{label}"] = count
    for label, count in sorted(claim_level_counts.items()):
        metrics[f"claim_level_count_{label}"] = count
    quotient_witness_counts = Counter(
        row.quotient_witness_classification
        for row in table.rows
        if row.quotient_witness_classification is not None
    )
    for label, count in sorted(quotient_witness_counts.items()):
        metrics[f"quotient_witness_count_{label}"] = count
    return ResultNote(
        note_format_version="result-note.v1",
        note_id=f"note_{run_id}",
        run_id=run_id,
        instance_ids=[table.search_id],
        metrics=metrics,
        interpretation=(
            "The mechanism-axis search compares theory-points while holding lens, projection, and packaging-policy settings fixed as much as practical, then records packaging-surface changes and mechanism-side tension without claiming same-system obstruction."
        ),
        caveats=[
            "Mechanism-axis candidates remain subject to the TH1 claim ceiling and do not justify theorem-level packaging obstruction claims by themselves.",
            "RM is diagnostic-only in this runner.",
        ],
        artifact_refs=output_paths,
        metadata={
            "classifier_version": MECHANISM_AXIS_CLASSIFIER_VERSION,
            "adequacy_version": MECHANISM_AXIS_ADEQUACY_VERSION,
            "best_point_id": None if best_point is None else best_point.point_id,
        },
    )


def _prepare_seed_config(
    *,
    base_config_path: str,
    point: MechanismAxisSearchPoint,
    seed: int,
) -> Path:
    base_config = _load_pilot_config(base_config_path)
    payload = _pilot_config_for_seed(
        base_config=base_config,
        base_config_path=base_config_path,
        seed=seed,
    )
    config_dir = get_repo_root() / ".cache" / "mechanism-axis-search"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / f"{point.point_id}_seed_{seed}.json"
    _write_json(config_path, payload)
    return config_path


def _run_point(
    *,
    point: MechanismAxisSearchPoint,
    search: MechanismAxisSearch,
    category: str,
    timestamp: str | None,
    root: Path,
    derived_dir: Path,
) -> _PointArtifacts:
    base_config = _load_pilot_config(point.pilot_config_artifact)
    pilot_outputs: list[PicaPilotArtifacts] = []
    run_ids: dict[str, str] = {}
    notes = list(point.notes)
    for seed in point.seed_list:
        config_path = _prepare_seed_config(
            base_config_path=point.pilot_config_artifact,
            point=point,
            seed=seed,
        )
        artifacts = run_pica_pilot_campaign(
            config_path=config_path,
            category=category,
            label=f"{point.point_id}_seed_{seed}",
            seed=seed,
            timestamp=timestamp,
            root=root,
            command=[
                sys.executable,
                "-m",
                "sixbirds_event",
                "pica",
                "run-pilot",
                config_path.as_posix(),
            ],
        )
        pilot_outputs.append(artifacts)
        run_ids[f"pica_wrapper_seed_{seed}"] = artifacts.run_id

    merged_bundle_relpath = _merge_pilot_outputs(
        point=point,
        preparation_id=point.preparation_id,
        protocol_id=point.protocol_id,
        pilot_outputs=pilot_outputs,
        output_dir=derived_dir,
        root=root,
    )
    resolved = load_pica_export_bundle(merged_bundle_relpath, repo_root=root)
    resolved_surface = resolve_pica_packaging_surface(
        merged_bundle_relpath, repo_root=root
    )
    packaging_summary_path = (
        derived_dir / f"{point.point_id}_packaging_surface_summary.json"
    )
    packaging_source_index_path = (
        derived_dir / f"{point.point_id}_packaging_source_index.json"
    )
    _write_json(
        packaging_summary_path, resolved_surface.surface.model_dump(mode="json")
    )
    _write_json(packaging_source_index_path, resolved_surface.source_index)

    discovery_point = _DiscoveryPoint(
        point_id=point.point_id,
        preparation_id=point.preparation_id,
        protocol_id=point.protocol_id,
        selected_protocol_step_ids=list(search.selected_protocol_step_ids),
        selected_step_indices=list(search.selected_step_indices),
    )
    family_path, skeleton_path, family = _discover_family(
        point=discovery_point,
        resolved=resolved,
        bundle_artifact=merged_bundle_relpath,
        projection_families=_active_projection_families(search),
        output_dir=derived_dir,
        root=root,
    )

    artifact_paths = {
        "export_bundle": merged_bundle_relpath,
        "packaging_surface_summary": repo_relative_path(
            packaging_summary_path, root=root
        ),
        "packaging_source_index": repo_relative_path(
            packaging_source_index_path, root=root
        ),
        "discovered_context_family": family_path,
    }
    selected_operator_ids = set(
        resolved_surface.source_index["selected_operator_counts"]
    )
    selected_family_ids = set(resolved_surface.source_index["selected_family_counts"])
    selected_sources = set(resolved_surface.source_index["source_counts"])
    catalog_operator_ids = set(
        resolved_surface.source_index["distinct_packaging_operator_ids"]
    )
    catalog_family_ids = set(
        resolved_surface.source_index["distinct_packaging_family_ids"]
    )

    if family.diagnostics_summary.accepted_context_count < 2:
        row = MechanismAxisRow(
            row_format_version="mechanism-axis-row.v1",
            search_id=search.search_id,
            point_id=point.point_id,
            source_pica_campaign_config_path=point.pilot_config_artifact,
            produced_export_bundle_path=merged_bundle_relpath,
            packaging_surface_summary_path=artifact_paths["packaging_surface_summary"],
            discovered_context_family_path=family_path,
            event_package_path=None,
            provenance_classification=None,
            accepted_context_count=family.diagnostics_summary.accepted_context_count,
            accepted_singleton_event_count=0,
            accepted_proper_coarse_event_count=0,
            accepted_shared_event_proposal_count=0,
            accepted_proper_coarse_proposal_count=0,
            baseline_hard_only=_not_applicable_evaluation(),
            all_accepted_proposals=_not_applicable_evaluation(),
            selected_packaging_sources=sorted(selected_sources),
            selected_packaging_operator_count=len(selected_operator_ids),
            selected_packaging_family_count=len(selected_family_ids),
            packaging_support_slice_count=resolved_surface.surface.support_slice_count,
            changed_packaging_surface_relative_to_control=False,
            quotient_class_count=None,
            quotient_accepted_only_survivor_count=None,
            quotient_natural_pairing_survivor_count=None,
            quotient_candidate_subset_witness_found=None,
            quotient_witness_classification=None,
            quotient_witness_candidate_ids=[],
            quotient_feasibility_summary_path=None,
            candidate_classification="trivial_or_nonrecording",
            claim_level_supported="mechanism_dependence",
            mechanism_signal_kind="inconclusive",
            run_ids=run_ids,
            artifact_paths=artifact_paths,
            notes=notes + ["insufficient_accepted_contexts_for_package_build"],
            flags=["mechanism_axis", "claim_ceiling_mechanism_only"],
        )
        return _PointArtifacts(
            row=row,
            catalog_operator_ids=catalog_operator_ids,
            catalog_family_ids=catalog_family_ids,
            selected_operator_ids=selected_operator_ids,
            selected_family_ids=selected_family_ids,
            selected_sources=selected_sources,
        )

    package_artifacts = write_package_build_report(
        family_path=root / family_path,
        pica_bundle_path=root / merged_bundle_relpath,
        skeleton_path=root / skeleton_path if skeleton_path is not None else None,
        category=category,
        label=f"{point.point_id}_package_build",
        seed=point.seed_list[0],
        timestamp=timestamp,
        root=root,
        thresholds=search.shared_event_inference_thresholds,
        event_thresholds=search.event_generation_thresholds,
        command=[
            sys.executable,
            "-m",
            "sixbirds_event",
            "substrates",
            "build-event-package",
            family_path,
        ],
    )
    run_ids["package_build"] = package_artifacts.run_id
    provenance_artifacts = write_provenance_audit_report(
        package_path=root / package_artifacts.event_package_path,
        provenance_path=root / package_artifacts.provenance_path,
        category=category,
        label=f"{point.point_id}_provenance",
        seed=point.seed_list[0],
        timestamp=timestamp,
        root=root,
        command=[
            sys.executable,
            "-m",
            "sixbirds_event",
            "audits",
            "provenance",
            package_artifacts.event_package_path,
        ],
    )
    run_ids["provenance_audit"] = provenance_artifacts.run_id

    stat_trace = _derive_pica_stat_trace(
        family=family,
        resolved=resolved,
        instance_id=package_artifacts.event_package.instance_id,
        instance_artifact=package_artifacts.event_package_path,
        trace_id=f"{point.point_id}_stat_trace",
    )
    stat_trace_path = derived_dir / f"{point.point_id}_stat_trace.json"
    _write_json(stat_trace_path, stat_trace.model_dump(mode="json"))
    stat_trace_relpath = repo_relative_path(stat_trace_path, root=root)

    hard_only_exact = solve_exact_structural_feasibility(
        package_artifacts.event_package,
        include_soft=False,
    )
    all_proposals_exact = solve_exact_structural_feasibility(
        package_artifacts.event_package,
        include_soft=True,
    )
    baseline_statistical = write_statistical_summary(
        package_artifacts.event_package,
        [stat_trace],
        instance_path=root / package_artifacts.event_package_path,
        trace_paths=[stat_trace_path],
        category=category,
        label=f"{point.point_id}_baseline_statistical",
        seed=point.seed_list[0],
        timestamp=timestamp,
        root=root,
        include_soft=False,
        command=[
            sys.executable,
            "-m",
            "sixbirds_event",
            "statistical",
            "report",
            package_artifacts.event_package_path,
        ],
    )
    candidate_statistical = write_statistical_summary(
        package_artifacts.event_package,
        [stat_trace],
        instance_path=root / package_artifacts.event_package_path,
        trace_paths=[stat_trace_path],
        category=category,
        label=f"{point.point_id}_candidate_statistical",
        seed=point.seed_list[0],
        timestamp=timestamp,
        root=root,
        include_soft=True,
        command=[
            sys.executable,
            "-m",
            "sixbirds_event",
            "statistical",
            "report",
            package_artifacts.event_package_path,
        ],
    )
    run_ids["baseline_statistical"] = baseline_statistical.run_id
    run_ids["candidate_statistical"] = candidate_statistical.run_id

    baseline_gpd_str_status, baseline_gpd_str, baseline_gpd_str_reason = (
        _baseline_deficit_evaluation(package_artifacts.event_package)
    )
    candidate_gpd_str_status, candidate_gpd_str, candidate_gpd_str_reason = (
        _candidate_deficit_evaluation(package_artifacts.event_package)
    )
    baseline_hard_only = TargetedSearchEvaluation(
        exact_structural_status="feasible"
        if hard_only_exact.feasible
        else "infeasible",
        exact_feasible=hard_only_exact.feasible,
        exact_respecting_tuple_count=hard_only_exact.respecting_tuple_count,
        exact_failure_reason=hard_only_exact.reason,
        gpd_str_status=baseline_gpd_str_status,
        gpd_str=baseline_gpd_str,
        gpd_str_reason=baseline_gpd_str_reason,
        gpd_stat_status="solved" if baseline_statistical.result.solved else "unsolved",
        gpd_stat=baseline_statistical.result.gpd_stat,
        gpd_stat_reason=baseline_statistical.result.reason,
    )
    all_accepted_proposals = TargetedSearchEvaluation(
        exact_structural_status="feasible"
        if all_proposals_exact.feasible
        else "infeasible",
        exact_feasible=all_proposals_exact.feasible,
        exact_respecting_tuple_count=all_proposals_exact.respecting_tuple_count,
        exact_failure_reason=all_proposals_exact.reason,
        gpd_str_status=candidate_gpd_str_status,
        gpd_str=candidate_gpd_str,
        gpd_str_reason=candidate_gpd_str_reason,
        gpd_stat_status="solved" if candidate_statistical.result.solved else "unsolved",
        gpd_stat=candidate_statistical.result.gpd_stat,
        gpd_stat_reason=candidate_statistical.result.reason,
    )
    sec_status, sec_mean = _sec_summary(package_artifacts.candidates)
    accepted_proper_coarse_proposal_count = sum(
        1
        for candidate in package_artifacts.candidates.candidate_rows
        if candidate.accepted
        and (candidate.left_is_proper_coarse or candidate.right_is_proper_coarse)
    )
    artifact_paths.update(
        {
            "event_package": package_artifacts.event_package_path,
            "package_provenance": package_artifacts.provenance_path,
            "shared_event_candidates": package_artifacts.candidates_path,
            "package_build_summary": package_artifacts.summary_path,
            "provenance_summary": provenance_artifacts.summary_path,
            "baseline_statistical_summary": baseline_statistical.summary_path,
            "candidate_statistical_summary": candidate_statistical.summary_path,
            "stat_trace": stat_trace_relpath,
        }
    )
    quotient_class_count: int | None = None
    quotient_accepted_only_survivor_count: int | None = None
    quotient_natural_pairing_survivor_count: int | None = None
    quotient_candidate_subset_witness_found: bool | None = None
    quotient_witness_classification: str | None = None
    quotient_witness_candidate_ids: list[str] = []
    quotient_feasibility_summary_path: str | None = None
    if point.quotient_feasibility_audit_artifact is not None:
        template_path = root / point.quotient_feasibility_audit_artifact
        if not template_path.exists():
            template_path = get_repo_root() / point.quotient_feasibility_audit_artifact
        quotient_artifacts = run_quotient_feasibility_audit(
            audit_path=template_path,
            category=category,
            label=f"{point.point_id}_quotient_feasibility",
            seed=point.seed_list[0],
            timestamp=timestamp,
            root=root,
            command=[
                sys.executable,
                "-m",
                "sixbirds_event",
                "audits",
                "quotient-feasibility",
                repo_relative_path(template_path, root=get_repo_root()),
            ],
        )
        run_ids["quotient_feasibility_audit"] = quotient_artifacts.run_id
        quotient_class_count = (
            quotient_artifacts.result.quotient_summary.quotient_class_count
        )
        quotient_accepted_only_survivor_count = (
            quotient_artifacts.result.accepted_proposal_set_result.survivor_count
        )
        quotient_natural_pairing_survivor_count = (
            None
            if quotient_artifacts.result.natural_pairing_result is None
            else quotient_artifacts.result.natural_pairing_result.survivor_count
        )
        quotient_candidate_subset_witness_found = (
            quotient_artifacts.result.candidate_subset_witness_result.witness_found
        )
        quotient_witness_classification = (
            quotient_artifacts.result.witness_classification
        )
        quotient_witness_candidate_ids = quotient_artifacts.result.candidate_subset_witness_result.witness_candidate_ids
        quotient_feasibility_summary_path = quotient_artifacts.summary_path
        artifact_paths["quotient_feasibility_summary"] = quotient_artifacts.summary_path
        artifact_paths["quotient_class_ledger"] = (
            quotient_artifacts.quotient_class_ledger_path
        )
    row = MechanismAxisRow(
        row_format_version="mechanism-axis-row.v1",
        search_id=search.search_id,
        point_id=point.point_id,
        source_pica_campaign_config_path=point.pilot_config_artifact,
        produced_export_bundle_path=merged_bundle_relpath,
        packaging_surface_summary_path=artifact_paths["packaging_surface_summary"],
        discovered_context_family_path=family_path,
        event_package_path=package_artifacts.event_package_path,
        provenance_classification=provenance_artifacts.result.admissibility_classification,
        accepted_context_count=family.diagnostics_summary.accepted_context_count,
        accepted_singleton_event_count=package_artifacts.discovered_event_family.diagnostics_summary.accepted_singleton_event_count,
        accepted_proper_coarse_event_count=package_artifacts.discovered_event_family.diagnostics_summary.accepted_coarse_event_count,
        accepted_shared_event_proposal_count=len(
            package_artifacts.event_package.equality_proposals
        ),
        accepted_proper_coarse_proposal_count=accepted_proper_coarse_proposal_count,
        baseline_hard_only=baseline_hard_only,
        all_accepted_proposals=all_accepted_proposals,
        selected_packaging_sources=sorted(selected_sources),
        selected_packaging_operator_count=len(selected_operator_ids),
        selected_packaging_family_count=len(selected_family_ids),
        packaging_support_slice_count=resolved_surface.surface.support_slice_count,
        changed_packaging_surface_relative_to_control=False,
        quotient_class_count=quotient_class_count,
        quotient_accepted_only_survivor_count=quotient_accepted_only_survivor_count,
        quotient_natural_pairing_survivor_count=quotient_natural_pairing_survivor_count,
        quotient_candidate_subset_witness_found=quotient_candidate_subset_witness_found,
        quotient_witness_classification=quotient_witness_classification,
        quotient_witness_candidate_ids=quotient_witness_candidate_ids,
        quotient_feasibility_summary_path=quotient_feasibility_summary_path,
        candidate_classification="inconclusive",
        claim_level_supported="mechanism_dependence",
        mechanism_signal_kind="inconclusive",
        run_ids=run_ids,
        artifact_paths=artifact_paths,
        notes=notes
        + [
            f"mechanism_family_id={base_config.mechanism_family_id}",
            f"enable_matrix_id={base_config.enable_matrix_id}",
            "ccd_not_applicable_without_repeated_read_trace",
            "rm_is_diagnostic_only",
            f"sec_status={sec_status}",
            f"sec_mean={sec_mean}",
        ],
        flags=["mechanism_axis", "claim_ceiling_mechanism_only"],
    )
    return _PointArtifacts(
        row=row,
        catalog_operator_ids=catalog_operator_ids,
        catalog_family_ids=catalog_family_ids,
        selected_operator_ids=selected_operator_ids,
        selected_family_ids=selected_family_ids,
        selected_sources=selected_sources,
    )


def run_mechanism_axis_search(
    *,
    search_path: str | Path,
    category: str,
    label: str | None = None,
    seed: int = 0,
    timestamp: str | None = None,
    root: str | Path | None = None,
    command: list[str] | None = None,
) -> MechanismAxisArtifacts:
    del seed
    repo_root = Path(root).resolve() if root is not None else None
    search = load_mechanism_axis_search(search_path)
    run_dir, run_id, manifest_timestamp = create_run_directory(
        category=category,
        label=label or search.output_label or search.search_id,
        timestamp=timestamp,
        root=repo_root,
    )
    effective_root = run_dir.parents[2]
    derived_dir = run_dir / "derived"
    derived_dir.mkdir()

    point_artifacts = [
        _run_point(
            point=point,
            search=search,
            category=category,
            timestamp=timestamp,
            root=effective_root,
            derived_dir=derived_dir,
        )
        for point in search.points
    ]
    control = point_artifacts[0]
    updated_rows: list[MechanismAxisRow] = []
    for artifacts in point_artifacts:
        changed_surface = (
            artifacts.selected_sources != control.selected_sources
            or artifacts.catalog_operator_ids != control.catalog_operator_ids
            or artifacts.catalog_family_ids != control.catalog_family_ids
            or artifacts.selected_operator_ids != control.selected_operator_ids
            or artifacts.selected_family_ids != control.selected_family_ids
        )
        row = artifacts.row.model_copy(
            update={
                "changed_packaging_surface_relative_to_control": changed_surface,
            }
        )
        row = row.model_copy(
            update={
                "candidate_classification": _candidate_classification(
                    row=row,
                    search=search,
                )
            }
        )
        row = row.model_copy(
            update={
                "claim_level_supported": _claim_level(
                    row=row,
                    search=search,
                )
            }
        )
        updated_rows.append(row)

    control_row = updated_rows[0]
    final_rows = [
        row.model_copy(
            update={
                "mechanism_signal_kind": _signal_kind(row=row, control_row=control_row)
            }
        )
        for row in updated_rows
    ]

    table = MechanismAxisTable(
        table_format_version="mechanism-axis-results.v1",
        search_id=search.search_id,
        row_count=len(final_rows),
        rows=final_rows,
        metadata={"axis": "mechanism"},
    )
    classification_counts = dict(
        Counter(row.candidate_classification for row in final_rows)
    )
    claim_level_counts = dict(Counter(row.claim_level_supported for row in final_rows))
    adequacy = _evaluate_adequacy(rows=final_rows, search=search)
    best_point = _best_point(final_rows)
    if not adequacy["adequate"]:
        outcome_kind = "design_inadequate"
    elif (
        best_point is not None
        and best_point.candidate_classification == "strongly_nonextendable_candidate"
    ):
        outcome_kind = "best_candidate"
    else:
        outcome_kind = "negative_result"

    table_csv_path = run_dir / "mechanism-axis.csv"
    table_json_path = run_dir / "mechanism-axis.json"
    summary_path = run_dir / "mechanism-axis-summary.json"
    note_path = run_dir / "mechanism-axis-note.md"
    result_note_path = run_dir / "result-note.json"
    manifest_path = run_dir / "run-manifest.json"
    outcome_path = run_dir / (
        "best-candidate.json"
        if outcome_kind == "best_candidate"
        else "negative-result.json"
        if outcome_kind == "negative_result"
        else "design-inadequate-result.json"
    )

    _write_csv(table_csv_path, [_row_to_csv_record(row) for row in final_rows])
    _write_json(table_json_path, table.model_dump(mode="json"))
    output_paths = {
        "table_csv": repo_relative_path(table_csv_path, root=effective_root),
        "table_json": repo_relative_path(table_json_path, root=effective_root),
        "summary": repo_relative_path(summary_path, root=effective_root),
        "note": repo_relative_path(note_path, root=effective_root),
        "result_note": repo_relative_path(result_note_path, root=effective_root),
        "manifest": repo_relative_path(manifest_path, root=effective_root),
        "outcome": repo_relative_path(outcome_path, root=effective_root),
    }
    summary = _build_summary(
        search=search,
        rows=final_rows,
        adequacy=adequacy,
        classification_counts=classification_counts,
        claim_level_counts=claim_level_counts,
        best_point=best_point,
        outcome_kind=outcome_kind,
        output_paths=output_paths,
    )
    _write_json(summary_path, summary)
    note_path.write_text(
        _render_note(
            search=search,
            rows=final_rows,
            adequacy=adequacy,
            classification_counts=classification_counts,
            claim_level_counts=claim_level_counts,
            best_point=best_point,
            outcome_kind=outcome_kind,
            output_paths=output_paths,
        ),
        encoding="utf-8",
    )
    _write_json(
        outcome_path,
        {
            "search_id": search.search_id,
            "outcome_kind": outcome_kind,
            "claim_ceiling": search.claim_ceiling,
            "best_point_id": None if best_point is None else best_point.point_id,
            "adequacy_floor_result": adequacy,
        },
    )
    result_note = _build_result_note(
        run_id=run_id,
        table=table,
        adequacy=adequacy,
        classification_counts=classification_counts,
        claim_level_counts=claim_level_counts,
        outcome_kind=outcome_kind,
        best_point=best_point,
        output_paths=output_paths,
    )
    _write_json(result_note_path, result_note.model_dump(mode="json"))
    manifest = build_run_manifest(
        run_id=run_id,
        timestamp=manifest_timestamp,
        command=command
        or [
            sys.executable,
            "-m",
            "sixbirds_event",
            "search",
            "run-mechanism-axis",
            repo_relative_path(search_path, root=effective_root),
        ],
        seed=0,
        input_artifacts={
            "search_config": repo_relative_path(search_path, root=effective_root)
        },
        output_artifacts=output_paths,
        status="succeeded",
        git_commit=detect_git_commit(root=effective_root),
        metadata={
            "analysis_kind": "mechanism_axis_search",
            "classifier_version": MECHANISM_AXIS_CLASSIFIER_VERSION,
            "adequacy_version": MECHANISM_AXIS_ADEQUACY_VERSION,
        },
    )
    write_run_manifest(manifest, run_dir=run_dir)
    return MechanismAxisArtifacts(
        run_id=run_id,
        run_dir=repo_relative_path(run_dir, root=effective_root),
        table_csv_path=output_paths["table_csv"],
        table_json_path=output_paths["table_json"],
        summary_path=output_paths["summary"],
        note_path=output_paths["note"],
        result_note_path=output_paths["result_note"],
        manifest_path=output_paths["manifest"],
        table=table,
        classification_counts=classification_counts,
        claim_level_counts=claim_level_counts,
        adequacy=adequacy,
        outcome_path=output_paths["outcome"],
        outcome_kind=outcome_kind,
        best_point_id=None if best_point is None else best_point.point_id,
    )
