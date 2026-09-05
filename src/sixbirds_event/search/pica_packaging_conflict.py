from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from itertools import combinations
import json
from pathlib import Path
import statistics
import sys

from ..discovery.models import (
    DiscoveredContextFamily,
    SharedEventCandidates,
)
from ..pica_bridge.ingest import PicaBundleResolved, load_pica_export_bundle
from ..pica_bridge.models import PicaCommutatorCatalog
from ..pica_bridge.pilot import PicaPilotArtifacts, run_pica_pilot_campaign
from ..provenance.audit import write_provenance_audit_report
from ..reporting.package_build_report import write_package_build_report
from ..reporting.statistical_report import write_statistical_summary
from ..run_registry import (
    build_run_manifest,
    create_run_directory,
    detect_git_commit,
    repo_relative_path,
    write_run_manifest,
)
from ..schemas.result_note import ResultNote
from ..solvers.structural_exact import solve_exact_structural_feasibility
from ..validation import load_model
from .models import (
    CommutatorAdmissibilityMode,
    ContextPairStructureRow,
    ContextPairStructureTable,
    FrozenSliceProjectionFamily,
    PackagingConflictComparisonRow,
    PackagingConflictComparisonTable,
    PackagingConflictModeResult,
    PackagingConflictSearchPoint,
    PackagingConflictSearchRow,
    PicaPackagingConflictSearch,
    ProjectionFamilyAdmissibilityRow,
    ProjectionFamilyAdmissibilityTable,
    TargetedCandidateLabel,
    TargetedSearchEvaluation,
)
from .pica_closure_diverse_search import _context_assignment_map, _proposal_support
from .pica_frozen_slice_obstruction import (
    _blocks_for_shared_rows,
    _build_projection_admissibility_rows,
    _discover_family,
    _pair_side,
    _projection_family_map,
    _refines,
    _relation_counts,
    _source_pair_filter,
    _write_csv,
    _write_json,
)
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


PICA_PACKAGING_CONFLICT_CLASSIFIER_VERSION = "pica-packaging-conflict-classifier.v1"
PICA_PACKAGING_CONFLICT_ADEQUACY_VERSION = "pica-packaging-conflict-adequacy.v1"
P5_P6_COMBINED_PAIRS = ["[P1,P6]", "[P2,P6]", "[P4,P6]"]


@dataclass(slots=True)
class PicaPackagingConflictArtifacts:
    run_id: str
    run_dir: str
    table_csv_path: str
    table_json_path: str
    context_pair_structure_path: str
    projection_family_admissibility_path: str
    commutator_summary_path: str
    summary_path: str
    note_path: str
    result_note_path: str
    manifest_path: str
    table: PackagingConflictComparisonTable
    context_pair_structure: ContextPairStructureTable
    projection_family_admissibility: ProjectionFamilyAdmissibilityTable
    classification_counts: dict[str, dict[str, int]]
    outcome_path: str
    outcome_kind: str


@dataclass(slots=True)
class _PreparedPointArtifacts:
    merged_bundle_relpath: str
    family_path: str
    skeleton_path: str | None
    family: DiscoveredContextFamily
    resolved_bundle: PicaBundleResolved
    admissibility_rows: list[ProjectionFamilyAdmissibilityRow]
    run_ids: dict[str, str]


@dataclass(slots=True)
class _PointModeArtifacts:
    row: PackagingConflictSearchRow
    context_pair_rows: list[ContextPairStructureRow]
    commutator_summary: dict[str, object]
    primary_pair_ids: set[tuple[str, str]]


def load_pica_packaging_conflict_search(
    path: str | Path,
) -> PicaPackagingConflictSearch:
    model = load_model(path, kind="pica-packaging-conflict-search")
    assert isinstance(model, PicaPackagingConflictSearch)
    return model


def _relevant_pairs_for_mode(
    search: PicaPackagingConflictSearch,
    mode: CommutatorAdmissibilityMode,
) -> list[str]:
    if mode == "p5_only":
        return list(search.relevant_commutator_pairs)
    return sorted(set(search.relevant_commutator_pairs) | set(P5_P6_COMBINED_PAIRS))


def _nonzero_relevant_commutators(
    *,
    relevant_commutator_pairs: list[str],
    min_relevant_commutator_value: float,
    catalogs_by_run: dict[str, PicaCommutatorCatalog],
    run_ids: set[str],
) -> list[str]:
    supported: set[str] = set()
    for run_id in run_ids:
        catalog = catalogs_by_run.get(run_id)
        if catalog is None:
            continue
        for row in catalog.rows:
            if (
                row.pair_id in relevant_commutator_pairs
                and row.metric_value >= min_relevant_commutator_value
            ):
                supported.add(row.pair_id)
    return sorted(supported)


def _context_pair_rows(
    *,
    point: PackagingConflictSearchPoint,
    search: PicaPackagingConflictSearch,
    commutator_admissibility_mode: CommutatorAdmissibilityMode,
    relevant_commutator_pairs: list[str],
    resolved: PicaBundleResolved,
    family: DiscoveredContextFamily,
    projection_family_map: dict[str, FrozenSliceProjectionFamily],
) -> tuple[list[ContextPairStructureRow], dict[str, object]]:
    assignments = {
        context.context_id: _context_assignment_map(resolved=resolved, context=context)
        for context in family.accepted_contexts
    }
    catalogs_by_run = resolved.commutator_catalogs_by_run()
    rows: list[ContextPairStructureRow] = []
    point_support_pairs: set[str] = set()

    for left, right in combinations(family.accepted_contexts, 2):
        if (
            left.candidate_key.preparation_id != right.candidate_key.preparation_id
            or left.candidate_key.protocol_id != right.candidate_key.protocol_id
        ):
            continue
        left_family = projection_family_map[left.source_metadata.projection_id]  # type: ignore[index]
        right_family = projection_family_map[right.source_metadata.projection_id]  # type: ignore[index]
        left_assignment = assignments[left.context_id]
        right_assignment = assignments[right.context_id]
        shared_rows = set(left_assignment) & set(right_assignment)
        same_protocol_step = (
            left.candidate_key.protocol_step_id == right.candidate_key.protocol_step_id
        )
        same_step_index = (
            left.candidate_key.step_index == right.candidate_key.step_index
        )
        same_step = same_protocol_step and same_step_index
        policy = search.source_pair_policy
        same_frozen_slice = (
            (
                (not policy.require_same_preparation_id)
                or left.candidate_key.preparation_id
                == right.candidate_key.preparation_id
            )
            and (
                (not policy.require_same_protocol_id)
                or left.candidate_key.protocol_id == right.candidate_key.protocol_id
            )
            and ((not policy.require_same_protocol_step_id) or same_protocol_step)
            and ((not policy.require_same_step_index) or same_step_index)
            and ((not policy.require_shared_support_scope) or bool(shared_rows))
        )
        primary_identity_admissible = (
            same_frozen_slice
            and "primary_context" in left_family.allowed_roles
            and "primary_context" in right_family.allowed_roles
        )
        differs_by_closure = (
            left.source_metadata is not None
            and right.source_metadata is not None
            and left.source_metadata.closure_id != right.source_metadata.closure_id
        )
        differs_by_lens = (
            left.source_metadata is not None
            and right.source_metadata is not None
            and left.source_metadata.lens_id != right.source_metadata.lens_id
        )
        differs_by_packaging_operation = differs_by_closure or differs_by_lens
        left_run_ids = (
            set(left.source_metadata.run_ids)
            if left.source_metadata is not None and left.source_metadata.run_ids
            else set()
        )
        right_run_ids = (
            set(right.source_metadata.run_ids)
            if right.source_metadata is not None and right.source_metadata.run_ids
            else set()
        )
        shared_run_ids = left_run_ids & right_run_ids
        commutator_support_pairs = _nonzero_relevant_commutators(
            relevant_commutator_pairs=relevant_commutator_pairs,
            min_relevant_commutator_value=search.min_relevant_commutator_value,
            catalogs_by_run=catalogs_by_run,
            run_ids=shared_run_ids,
        )
        point_support_pairs.update(commutator_support_pairs)
        packaging_conflict_supported = bool(commutator_support_pairs)
        primary_packaging_conflict_admissible = (
            primary_identity_admissible
            and differs_by_packaging_operation
            and packaging_conflict_supported
        )

        if not same_step:
            relation_type = "disjoint_or_unaligned"
            notes = ["cross_step_pair"]
            flags: list[str] = []
        elif not shared_rows:
            relation_type = "disjoint_or_unaligned"
            notes = ["no_shared_rows"]
            flags = []
        else:
            left_blocks = _blocks_for_shared_rows(left_assignment, shared_rows)
            right_blocks = _blocks_for_shared_rows(right_assignment, shared_rows)
            left_refines = _refines(left_blocks, right_blocks)
            right_refines = _refines(right_blocks, left_blocks)
            notes = []
            flags = []
            if left_refines and right_refines:
                relation_type = "equal"
            elif left_refines:
                relation_type = "left_refines_right"
            elif right_refines:
                relation_type = "right_refines_left"
            else:
                relation_type = "incomparable"
                flags.append("non_nested")

        if primary_packaging_conflict_admissible:
            admissibility_reason = (
                "same_slice_closure_or_lens_difference_with_relevant_commutator_support"
            )
            admissibility_class = "primary_packaging_conflict"
        elif not primary_identity_admissible:
            if not same_frozen_slice:
                admissibility_reason = "not_same_frozen_slice"
            else:
                admissibility_reason = "projection_family_not_primary_context"
            admissibility_class = "diagnostic_only"
        elif not differs_by_packaging_operation:
            admissibility_reason = (
                "projection_only_difference_not_primary_packaging_conflict"
            )
            admissibility_class = "probe_only"
        elif not packaging_conflict_supported:
            admissibility_reason = "no_relevant_nonzero_commutator_support"
            admissibility_class = "probe_only"
        else:
            admissibility_reason = "diagnostic_only"
            admissibility_class = "diagnostic_only"

        rows.append(
            ContextPairStructureRow(
                point_id=point.point_id,
                preparation_id=left.candidate_key.preparation_id,
                protocol_id=left.candidate_key.protocol_id,
                left=_pair_side(left),
                right=_pair_side(right),
                relation_type=relation_type,
                shared_row_count=len(shared_rows),
                left_assignment_count=len(left_assignment),
                right_assignment_count=len(right_assignment),
                left_block_count=len(set(left_assignment.values())),
                right_block_count=len(set(right_assignment.values())),
                same_step=same_step,
                same_frozen_slice=same_frozen_slice,
                primary_identity_admissible=primary_identity_admissible,
                commutator_admissibility_mode=commutator_admissibility_mode,
                packaging_conflict_supported=packaging_conflict_supported,
                commutator_support_pairs=commutator_support_pairs,
                primary_packaging_conflict_admissible=primary_packaging_conflict_admissible,
                packaging_conflict_admissibility_class=admissibility_class,
                admissibility_reason=admissibility_reason,
                notes=notes,
                flags=flags,
            )
        )

    return rows, {
        "point_id": point.point_id,
        "commutator_admissibility_mode": commutator_admissibility_mode,
        "row_count": len(rows),
        "nonzero_relevant_commutator_support_count": len(point_support_pairs),
        "nonzero_relevant_commutator_support_pairs": sorted(point_support_pairs),
        "rows_with_packaging_conflict_support": sum(
            1 for row in rows if row.packaging_conflict_supported
        ),
        "rows_with_primary_packaging_conflict_admissibility": sum(
            1 for row in rows if row.primary_packaging_conflict_admissible
        ),
    }


def _candidate_classification(
    *,
    row: PackagingConflictSearchRow,
    search: PicaPackagingConflictSearch,
    blocking_classification: str | None,
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
    candidate_exact_fails = row.all_accepted_proposals.exact_feasible is False
    positive_candidate_deficit = (
        row.all_accepted_proposals.gpd_str is not None
        and row.all_accepted_proposals.gpd_str
        > search.candidate_classification_thresholds.strong_nonextendable_min_gpd_str
    )
    strong_block = blocking_classification in {
        "no_respecting_tuples",
        "coverage_failure",
    }

    if (
        provenance_ok
        and row.accepted_package_conflict_same_slice_proper_coarse_proposal_count
        >= search.candidate_classification_thresholds.min_accepted_coarse_proposal_count
        and row.accepted_non_nested_package_conflict_proposal_count >= 1
        and candidate_exact_fails
        and positive_candidate_deficit
        and strong_block
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
    ):
        return "weakly_frustrated_candidate"

    return "inconclusive"


def _evaluate_adequacy(
    *,
    rows: list[PackagingConflictComparisonRow],
    search: PicaPackagingConflictSearch,
    changed_pair_point_ids: set[str],
) -> dict[str, object]:
    all_supports = [
        row.p5_p6_combined.median_accepted_proposal_support
        for row in rows
        if row.p5_p6_combined.median_accepted_proposal_support is not None
    ]
    median_support = float(statistics.median(all_supports)) if all_supports else None
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
        "points_with_package_conflict_same_slice_proper_coarse_structural_proposals": sum(
            1
            for row in rows
            if row.p5_p6_combined.accepted_package_conflict_same_slice_proper_coarse_proposal_count
            > 0
        ),
        "points_with_non_nested_same_slice_package_conflict_pairs": sum(
            1
            for row in rows
            if row.p5_p6_combined.same_slice_non_nested_packaging_conflict_pair_count
            > 0
        ),
        "points_with_dual_mode_difference": sum(
            1 for row in rows if _point_has_dual_mode_difference(row.p5_p6_combined)
        ),
        "points_with_nonzero_relevant_p5_commutator_support": sum(
            1
            for row in rows
            if row.p5_only.nonzero_relevant_commutator_support_count > 0
        ),
        "points_with_changed_packaging_conflict_pair_set": len(changed_pair_point_ids),
        "median_accepted_proposal_support": median_support,
    }
    floor = search.adequacy_floor
    checks = {
        "total_point_count": counts["total_point_count"] >= floor.min_total_point_count,
        "admissible_built_package_count": counts["admissible_built_package_count"]
        >= floor.min_admissible_built_package_count,
        "points_with_proper_coarse_events": counts["points_with_proper_coarse_events"]
        >= floor.min_points_with_proper_coarse_events,
        "points_with_package_conflict_same_slice_proper_coarse_structural_proposals": counts[
            "points_with_package_conflict_same_slice_proper_coarse_structural_proposals"
        ]
        >= floor.min_points_with_package_conflict_same_slice_proper_coarse_structural_proposals,
        "points_with_non_nested_same_slice_package_conflict_pairs": counts[
            "points_with_non_nested_same_slice_package_conflict_pairs"
        ]
        >= floor.min_points_with_non_nested_same_slice_package_conflict_pairs,
        "points_with_dual_mode_difference": counts["points_with_dual_mode_difference"]
        >= floor.min_points_with_dual_mode_difference,
        "points_with_nonzero_relevant_p5_commutator_support": counts[
            "points_with_nonzero_relevant_p5_commutator_support"
        ]
        >= floor.min_points_with_nonzero_relevant_p5_commutator_support,
        "points_with_changed_packaging_conflict_pair_set": counts[
            "points_with_changed_packaging_conflict_pair_set"
        ]
        >= 1,
        "median_accepted_proposal_support": (
            median_support is not None
            and median_support >= floor.min_median_accepted_proposal_support
        ),
    }
    return {
        "adequate": all(checks.values()),
        "counts": counts,
        "checks": checks,
        "thresholds": floor.model_dump(mode="json"),
    }


def _select_best_candidate(
    rows: list[PackagingConflictComparisonRow],
) -> tuple[PackagingConflictComparisonRow, CommutatorAdmissibilityMode] | None:
    candidates: list[
        tuple[PackagingConflictComparisonRow, CommutatorAdmissibilityMode]
    ] = []
    for row in rows:
        for mode_name, mode_result in [
            ("p5_only", row.p5_only),
            ("p5_p6_combined", row.p5_p6_combined),
        ]:
            if (
                mode_result.candidate_classification
                == "strongly_nonextendable_candidate"
            ):
                candidates.append((row, mode_name))
    if not candidates:
        return None

    def _mode_result(
        item: tuple[PackagingConflictComparisonRow, CommutatorAdmissibilityMode],
    ) -> PackagingConflictModeResult:
        row, mode_name = item
        return row.p5_only if mode_name == "p5_only" else row.p5_p6_combined

    return sorted(
        candidates,
        key=lambda item: (
            -(_mode_result(item).all_accepted_proposals.gpd_str or 0.0),
            -_mode_result(item).accepted_non_nested_package_conflict_proposal_count,
            _mode_result(item).all_accepted_proposals.exact_respecting_tuple_count
            if _mode_result(item).all_accepted_proposals.exact_respecting_tuple_count
            is not None
            else 10**9,
            item[0].point_id,
            item[1],
        ),
    )[0]


def _classification_counts_by_mode(
    rows: list[PackagingConflictComparisonRow],
) -> dict[str, dict[str, int]]:
    counts: dict[str, Counter[str]] = {
        "p5_only": Counter(),
        "p5_p6_combined": Counter(),
    }
    for row in rows:
        counts["p5_only"][row.p5_only.candidate_classification] += 1
        counts["p5_p6_combined"][row.p5_p6_combined.candidate_classification] += 1
    return {mode: dict(sorted(counter.items())) for mode, counter in counts.items()}


def _comparative_conclusion(
    rows: list[PackagingConflictComparisonRow],
    *,
    changed_pair_point_ids: set[str],
    best_candidate: tuple[PackagingConflictComparisonRow, CommutatorAdmissibilityMode]
    | None,
) -> str:
    if best_candidate is not None and best_candidate[1] == "p5_p6_combined":
        return "p6_surface_unlocked_stronger_candidate"
    if not changed_pair_point_ids:
        return "p6_surface_changed_nothing"
    changed_signal = any(
        row.p5_only.accepted_package_conflict_same_slice_proper_coarse_proposal_count
        != row.p5_p6_combined.accepted_package_conflict_same_slice_proper_coarse_proposal_count
        or row.p5_only.candidate_classification
        != row.p5_p6_combined.candidate_classification
        or row.p5_only.support_relation_kind_counts
        != row.p5_p6_combined.support_relation_kind_counts
        for row in rows
    )
    if changed_signal:
        return "p6_surface_increased_signal_but_not_obstruction"
    return "p6_surface_changed_nothing"


def _row_to_csv_record(row: PackagingConflictComparisonRow) -> dict[str, object]:
    return {
        "point_id": row.point_id,
        "source_pica_campaign_config_path": row.source_pica_campaign_config_path,
        "projection_family_ids": "|".join(row.projection_family_ids),
        "selected_protocol_step_ids": "|".join(row.selected_protocol_step_ids),
        "selected_step_indices": "|".join(
            str(value) for value in row.selected_step_indices
        ),
        "preparation_id": row.preparation_id,
        "protocol_id": row.protocol_id,
        "trajectories": row.trajectories,
        "seed_list": "|".join(str(seed) for seed in row.seed_list),
        "produced_export_bundle_path": row.produced_export_bundle_path,
        "discovered_context_family_path": row.discovered_context_family_path,
        "event_package_path": row.event_package_path,
        "provenance_classification": row.provenance_classification,
        "accepted_context_count": row.accepted_context_count,
        "accepted_proper_coarse_event_count": row.accepted_proper_coarse_event_count,
        "p5_only_accepted_proper_coarse_structural_proposal_count": row.p5_only.accepted_proper_coarse_structural_proposal_count,
        "p5_p6_combined_accepted_proper_coarse_structural_proposal_count": row.p5_p6_combined.accepted_proper_coarse_structural_proposal_count,
        "p5_only_candidate_exact_feasible": row.p5_only.all_accepted_proposals.exact_feasible,
        "p5_p6_combined_candidate_exact_feasible": row.p5_p6_combined.all_accepted_proposals.exact_feasible,
        "p5_only_candidate_gpd_str": row.p5_only.all_accepted_proposals.gpd_str,
        "p5_p6_combined_candidate_gpd_str": row.p5_p6_combined.all_accepted_proposals.gpd_str,
        "p5_only_candidate_classification": row.p5_only.candidate_classification,
        "p5_p6_combined_candidate_classification": row.p5_p6_combined.candidate_classification,
        "p5_only_support_relation_kind_counts": json.dumps(
            row.p5_only.support_relation_kind_counts,
            sort_keys=True,
        ),
        "p5_p6_combined_support_relation_kind_counts": json.dumps(
            row.p5_p6_combined.support_relation_kind_counts,
            sort_keys=True,
        ),
    }


def _prepare_point(
    *,
    point: PackagingConflictSearchPoint,
    search: PicaPackagingConflictSearch,
    projection_family_map: dict[str, FrozenSliceProjectionFamily],
    category: str,
    timestamp: str | None,
    root: Path,
    derived_dir: Path,
) -> _PreparedPointArtifacts:
    pilot_config = _load_pilot_config(root / point.pilot_config_artifact)
    pilot_outputs: list[PicaPilotArtifacts] = []
    run_ids: dict[str, str] = {}
    point_config_dir = derived_dir / point.point_id / "configs"
    point_config_dir.mkdir(parents=True, exist_ok=True)

    for index, seed in enumerate(point.seed_list):
        seeded_payload = _pilot_config_for_seed(
            base_config=pilot_config,
            base_config_path=point.pilot_config_artifact,
            seed=seed,
        )
        seeded_payload["preparation_id"] = point.preparation_id
        seeded_payload["protocol_id"] = point.protocol_id
        config_path = point_config_dir / f"pilot-seed{index}.json"
        _write_json(config_path, seeded_payload)
        artifacts = run_pica_pilot_campaign(
            config_path=config_path,
            category=category,
            label=f"{search.search_id}-{point.point_id}-seed{seed}",
            seed=seed,
            timestamp=timestamp,
            root=root,
            command=[
                sys.executable,
                "-m",
                "sixbirds_event",
                "pica",
                "run-pilot",
                repo_relative_path(config_path, root=root),
            ],
        )
        pilot_outputs.append(artifacts)
        run_ids[f"pica_wrapper_seed_{seed}"] = artifacts.run_id

    merged_bundle_relpath = _merge_pilot_outputs(
        point=point,  # type: ignore[arg-type]
        preparation_id=point.preparation_id,
        protocol_id=point.protocol_id,
        pilot_outputs=pilot_outputs,
        output_dir=derived_dir / "bundles",
        root=root,
    )
    resolved_bundle = load_pica_export_bundle(
        root / merged_bundle_relpath, repo_root=root
    )
    selected_projection_families = [
        projection_family_map[projection_id]
        for projection_id in point.projection_family_ids
    ]
    admissibility_rows = _build_projection_admissibility_rows(
        point=point,  # type: ignore[arg-type]
        resolved=resolved_bundle,
        projection_families=selected_projection_families,
    )
    family_path, skeleton_path, family = _discover_family(
        point=point,  # type: ignore[arg-type]
        resolved=resolved_bundle,
        bundle_artifact=merged_bundle_relpath,
        projection_families=selected_projection_families,
        output_dir=derived_dir / "families",
        root=root,
    )
    return _PreparedPointArtifacts(
        merged_bundle_relpath=merged_bundle_relpath,
        family_path=family_path,
        skeleton_path=skeleton_path,
        family=family,
        resolved_bundle=resolved_bundle,
        admissibility_rows=admissibility_rows,
        run_ids=run_ids,
    )


def _accepted_support_relation_counts(
    candidates_model: SharedEventCandidates,
) -> dict[str, int]:
    return dict(
        sorted(
            Counter(
                row.support_relation_kind
                for row in candidates_model.candidate_rows
                if row.accepted
            ).items()
        )
    )


def _run_point_mode(
    *,
    point: PackagingConflictSearchPoint,
    search: PicaPackagingConflictSearch,
    prepared: _PreparedPointArtifacts,
    commutator_admissibility_mode: CommutatorAdmissibilityMode,
    projection_family_map: dict[str, FrozenSliceProjectionFamily],
    category: str,
    timestamp: str | None,
    root: Path,
    derived_dir: Path,
) -> _PointModeArtifacts:
    relevant_commutator_pairs = _relevant_pairs_for_mode(
        search,
        commutator_admissibility_mode,
    )
    context_pair_rows, commutator_summary = _context_pair_rows(
        point=point,
        search=search,
        commutator_admissibility_mode=commutator_admissibility_mode,
        relevant_commutator_pairs=relevant_commutator_pairs,
        resolved=prepared.resolved_bundle,
        family=prepared.family,
        projection_family_map=projection_family_map,
    )
    point_pair_path = (
        derived_dir
        / f"{point.point_id}-{commutator_admissibility_mode}-context-pairs.json"
    )
    _write_json(
        point_pair_path,
        [row.model_dump(mode="json") for row in context_pair_rows],
    )
    primary_pairs = {
        tuple(sorted((row.left.context_id, row.right.context_id)))
        for row in context_pair_rows
        if row.primary_packaging_conflict_admissible
    }
    run_ids = dict(prepared.run_ids)
    counts = _relation_counts(context_pair_rows)
    same_slice_non_nested_context_pair_count = sum(
        1
        for pair in context_pair_rows
        if pair.same_frozen_slice and pair.relation_type == "incomparable"
    )
    if len(prepared.family.accepted_contexts) < 2 or not primary_pairs:
        row = PackagingConflictSearchRow(
            row_format_version="packaging-conflict-search-row.v1",
            search_id=search.search_id,
            point_id=point.point_id,
            source_pica_campaign_config_path=point.pilot_config_artifact,
            projection_family_ids=list(point.projection_family_ids),
            preparation_id=point.preparation_id,
            protocol_id=point.protocol_id,
            selected_protocol_step_ids=list(point.selected_protocol_step_ids),
            selected_step_indices=list(point.selected_step_indices),
            trajectories=point.trajectories,
            seed_list=list(point.seed_list),
            produced_export_bundle_path=prepared.merged_bundle_relpath,
            discovered_context_family_path=prepared.family_path,
            accepted_context_count=prepared.family.diagnostics_summary.accepted_context_count,
            accepted_proper_coarse_event_count=0,
            accepted_shared_event_proposal_count=0,
            accepted_proper_coarse_structural_proposal_count=0,
            accepted_package_conflict_same_slice_proper_coarse_proposal_count=0,
            accepted_non_nested_package_conflict_proposal_count=0,
            equal_context_pair_count=counts["equal"],
            left_refines_right_count=counts["left_refines_right"],
            right_refines_left_count=counts["right_refines_left"],
            incomparable_context_pair_count=counts["incomparable"],
            disjoint_or_unaligned_context_pair_count=counts["disjoint_or_unaligned"],
            same_slice_non_nested_context_pair_count=same_slice_non_nested_context_pair_count,
            primary_identity_admissible_pair_count=sum(
                1 for pair in context_pair_rows if pair.primary_identity_admissible
            ),
            packaging_conflict_admissible_pair_count=0,
            same_slice_non_nested_packaging_conflict_pair_count=0,
            nonzero_relevant_p5_commutator_support_count=int(
                commutator_summary["nonzero_relevant_commutator_support_count"]
            ),
            baseline_hard_only=TargetedSearchEvaluation(
                exact_structural_status="not_applicable",
                gpd_str_status="not_applicable",
                gpd_stat_status="not_applicable",
            ),
            all_accepted_proposals=TargetedSearchEvaluation(
                exact_structural_status="not_applicable",
                gpd_str_status="not_applicable",
                gpd_stat_status="not_applicable",
            ),
            ccd_status="not_applicable",
            sec_status="not_applicable",
            rm_status="not_applicable",
            candidate_classification="trivial_or_nonrecording",
            run_ids=run_ids,
            artifact_paths={
                "export_bundle": prepared.merged_bundle_relpath,
                "discovered_context_family": prepared.family_path,
                "context_pair_structure": repo_relative_path(
                    point_pair_path, root=root
                ),
            },
            notes=list(point.notes)
            + [f"mode={commutator_admissibility_mode}"]
            + ["no_packaging_conflict_admissible_multi_context_structure"],
        )
        return _PointModeArtifacts(
            row=row,
            context_pair_rows=context_pair_rows,
            commutator_summary=commutator_summary,
            primary_pair_ids=primary_pairs,
        )

    package_artifacts = write_package_build_report(
        family_path=root / prepared.family_path,
        run_paths=[],
        pica_bundle_path=prepared.merged_bundle_relpath,
        skeleton_path=(
            None if prepared.skeleton_path is None else root / prepared.skeleton_path
        ),
        category=category,
        label=(
            f"{search.search_id}-{point.point_id}-{commutator_admissibility_mode}-package"
        ),
        seed=point.seed_list[0],
        timestamp=timestamp,
        root=root,
        command=[
            sys.executable,
            "-m",
            "sixbirds_event",
            "search",
            "run-packaging-conflict",
            "package-build",
        ],
        thresholds=search.shared_event_inference_thresholds,
        event_thresholds=search.event_generation_thresholds,
        source_pair_filter=_source_pair_filter(primary_pairs),
    )
    candidates_model = load_model(
        root / package_artifacts.candidates_path, kind="shared-event-candidates"
    )
    assert isinstance(candidates_model, SharedEventCandidates)
    run_ids[f"{commutator_admissibility_mode}_package_build"] = package_artifacts.run_id

    provenance_artifacts = write_provenance_audit_report(
        package_path=root / package_artifacts.event_package_path,
        provenance_path=root / package_artifacts.provenance_path,
        category=category,
        label=(
            f"{search.search_id}-{point.point_id}-{commutator_admissibility_mode}-provenance"
        ),
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
            "--provenance",
            package_artifacts.provenance_path,
        ],
    )
    run_ids[f"{commutator_admissibility_mode}_provenance_audit"] = (
        provenance_artifacts.run_id
    )

    stat_trace = _derive_pica_stat_trace(
        family=prepared.family,
        resolved=prepared.resolved_bundle,
        instance_id=package_artifacts.event_package.instance_id,
        instance_artifact=package_artifacts.event_package_path,
        trace_id=(
            f"trace_{search.search_id}_{point.point_id}_{commutator_admissibility_mode}_stat"
        ),
    )
    stat_trace_path = (
        derived_dir / f"{point.point_id}-{commutator_admissibility_mode}-stat.json"
    )
    _write_json(stat_trace_path, stat_trace.model_dump(mode="json"))
    stat_trace_relpath = repo_relative_path(stat_trace_path, root=root)

    hard_only_exact = solve_exact_structural_feasibility(
        package_artifacts.event_package
    )
    all_proposals_exact = solve_exact_structural_feasibility(
        package_artifacts.event_package,
        include_soft=True,
    )
    baseline_statistical = write_statistical_summary(
        package_artifacts.event_package,
        [stat_trace],
        instance_path=package_artifacts.event_package_path,
        trace_paths=[stat_trace_relpath],
        category=category,
        label=(
            f"{search.search_id}-{point.point_id}-{commutator_admissibility_mode}-baseline-statistical"
        ),
        seed=point.seed_list[0],
        timestamp=timestamp,
        root=root,
        include_soft=False,
        command=[
            sys.executable,
            "-m",
            "sixbirds_event",
            "search",
            "packaging-conflict-baseline-statistical",
        ],
    )
    candidate_statistical = write_statistical_summary(
        package_artifacts.event_package,
        [stat_trace],
        instance_path=package_artifacts.event_package_path,
        trace_paths=[stat_trace_relpath],
        category=category,
        label=(
            f"{search.search_id}-{point.point_id}-{commutator_admissibility_mode}-candidate-statistical"
        ),
        seed=point.seed_list[0],
        timestamp=timestamp,
        root=root,
        include_soft=True,
        command=[
            sys.executable,
            "-m",
            "sixbirds_event",
            "search",
            "packaging-conflict-candidate-statistical",
        ],
    )
    run_ids[f"{commutator_admissibility_mode}_baseline_statistical"] = (
        baseline_statistical.run_id
    )
    run_ids[f"{commutator_admissibility_mode}_candidate_statistical"] = (
        candidate_statistical.run_id
    )

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
    sec_status, sec_mean = _sec_summary(candidates_model)
    relation_lookup = {
        tuple(sorted((row.left.context_id, row.right.context_id))): row
        for row in context_pair_rows
    }
    accepted_proper_coarse_structural_proposal_count = sum(
        1
        for row in candidates_model.candidate_rows
        if row.accepted and (row.left_is_proper_coarse or row.right_is_proper_coarse)
    )
    accepted_package_conflict_same_slice_proper_coarse_proposal_count = sum(
        1
        for row in candidates_model.candidate_rows
        if row.accepted
        and (row.left_is_proper_coarse or row.right_is_proper_coarse)
        and (
            pair := relation_lookup.get(
                tuple(sorted((row.left_context_id, row.right_context_id)))
            )
        )
        is not None
        and pair.primary_packaging_conflict_admissible
    )
    accepted_non_nested_package_conflict_proposal_count = sum(
        1
        for row in candidates_model.candidate_rows
        if row.accepted
        and (row.left_is_proper_coarse or row.right_is_proper_coarse)
        and (
            pair := relation_lookup.get(
                tuple(sorted((row.left_context_id, row.right_context_id)))
            )
        )
        is not None
        and pair.primary_packaging_conflict_admissible
        and pair.relation_type == "incomparable"
    )
    support_values = _proposal_support(candidates_model)
    row = PackagingConflictSearchRow(
        row_format_version="packaging-conflict-search-row.v1",
        search_id=search.search_id,
        point_id=point.point_id,
        source_pica_campaign_config_path=point.pilot_config_artifact,
        projection_family_ids=list(point.projection_family_ids),
        preparation_id=point.preparation_id,
        protocol_id=point.protocol_id,
        selected_protocol_step_ids=list(point.selected_protocol_step_ids),
        selected_step_indices=list(point.selected_step_indices),
        trajectories=point.trajectories,
        seed_list=list(point.seed_list),
        produced_export_bundle_path=prepared.merged_bundle_relpath,
        discovered_context_family_path=prepared.family_path,
        event_package_path=package_artifacts.event_package_path,
        provenance_classification=provenance_artifacts.result.admissibility_classification,
        accepted_context_count=prepared.family.diagnostics_summary.accepted_context_count,
        accepted_proper_coarse_event_count=sum(
            1
            for context in package_artifacts.discovered_event_family.contexts
            for event in context.events
            if event.event_kind == "proper_coarse"
        ),
        accepted_shared_event_proposal_count=len(
            package_artifacts.event_package.equality_proposals
        ),
        accepted_proper_coarse_structural_proposal_count=accepted_proper_coarse_structural_proposal_count,
        accepted_package_conflict_same_slice_proper_coarse_proposal_count=accepted_package_conflict_same_slice_proper_coarse_proposal_count,
        accepted_non_nested_package_conflict_proposal_count=accepted_non_nested_package_conflict_proposal_count,
        equal_context_pair_count=counts["equal"],
        left_refines_right_count=counts["left_refines_right"],
        right_refines_left_count=counts["right_refines_left"],
        incomparable_context_pair_count=counts["incomparable"],
        disjoint_or_unaligned_context_pair_count=counts["disjoint_or_unaligned"],
        same_slice_non_nested_context_pair_count=same_slice_non_nested_context_pair_count,
        primary_identity_admissible_pair_count=sum(
            1 for pair in context_pair_rows if pair.primary_identity_admissible
        ),
        packaging_conflict_admissible_pair_count=sum(
            1
            for pair in context_pair_rows
            if pair.primary_packaging_conflict_admissible
        ),
        same_slice_non_nested_packaging_conflict_pair_count=sum(
            1
            for pair in context_pair_rows
            if pair.primary_packaging_conflict_admissible
            and pair.relation_type == "incomparable"
        ),
        nonzero_relevant_p5_commutator_support_count=int(
            commutator_summary["nonzero_relevant_commutator_support_count"]
        ),
        median_accepted_proposal_support=(
            float(statistics.median(support_values)) if support_values else None
        ),
        baseline_hard_only=baseline_hard_only,
        all_accepted_proposals=all_accepted_proposals,
        ccd_status="not_applicable",
        sec_status=sec_status,
        sec_mean=sec_mean,
        rm_status="not_applicable",
        candidate_classification="inconclusive",
        run_ids=run_ids,
        artifact_paths={
            "export_bundle": prepared.merged_bundle_relpath,
            "discovered_context_family": prepared.family_path,
            "event_package": package_artifacts.event_package_path,
            "package_provenance": package_artifacts.provenance_path,
            "shared_event_candidates": package_artifacts.candidates_path,
            "package_build_summary": package_artifacts.summary_path,
            "context_pair_structure": repo_relative_path(point_pair_path, root=root),
        },
        notes=list(point.notes) + [f"mode={commutator_admissibility_mode}"],
    )
    row = row.model_copy(
        update={
            "candidate_classification": _candidate_classification(
                row=row,
                search=search,
                blocking_classification=all_proposals_exact.reason,
            )
        }
    )
    return _PointModeArtifacts(
        row=row,
        context_pair_rows=context_pair_rows,
        commutator_summary={
            **commutator_summary,
            "support_relation_kind_counts": _accepted_support_relation_counts(
                candidates_model
            ),
        },
        primary_pair_ids=primary_pairs,
    )


def _render_note(
    *,
    search: PicaPackagingConflictSearch,
    table: PackagingConflictComparisonTable,
    structure: ContextPairStructureTable,
    admissibility: ProjectionFamilyAdmissibilityTable,
    commutator_summary: dict[str, object],
    classification_counts: dict[str, dict[str, int]],
    adequacy: dict[str, object],
    best_candidate: tuple[PackagingConflictComparisonRow, CommutatorAdmissibilityMode]
    | None,
    outcome_kind: str,
    comparative_conclusion: str,
    output_paths: dict[str, str],
) -> str:
    lines = [
        "# Packaging-Conflict PICA Search",
        "",
        f"- Search ID: `{search.search_id}`",
        "",
        "## Campaign family covered",
    ]
    for row in table.rows:
        lines.append(
            f"- `{row.point_id}`: p5_only_pairs=`{row.p5_only.packaging_conflict_admissible_pair_count}`, p5_p6_pairs=`{row.p5_p6_combined.packaging_conflict_admissible_pair_count}`, p5_only_class=`{row.p5_only.candidate_classification}`, p5_p6_class=`{row.p5_p6_combined.candidate_classification}`, provenance=`{row.provenance_classification}`"
        )
    lines.extend(["", "## Primary projection families"])
    for family in search.projection_families:
        lines.append(
            f"- `{family.projection_id}`: source_field=`{family.source_field}`, kind=`{family.projection_kind}`, allowed_roles=`{','.join(family.allowed_roles)}`"
        )
    lines.extend(
        [
            "",
            "## Package-conflict admissibility rule",
            "- Primary source-pair identity requires matching preparation, protocol, protocol_step_id, and step_index on shared trajectory support.",
            "- Pairs differing only by projection field are probe-only or diagnostic-only.",
            "- Primary package-conflict evidence also requires a closure or lens difference plus nonzero relevant commutator support under the active mode.",
            "",
            "## Relevant commutator diagnostics used",
            f"- P5-only relevant pairs: `{_relevant_pairs_for_mode(search, 'p5_only')}`",
            f"- P5/P6-combined relevant pairs: `{_relevant_pairs_for_mode(search, 'p5_p6_combined')}`",
            f"- Commutator summary rows: `{commutator_summary['row_count']}`",
            f"- Points with changed admissible pair sets after adding P6: `{commutator_summary['points_with_changed_packaging_conflict_pair_set']}`",
            "",
            "## Evaluation modes",
            "- Each point is evaluated in `p5_only` and `p5_p6_combined` admissibility modes.",
            "- Baseline hard-only mode evaluates exact feasibility and deficits using only hard constraints.",
            "- All-accepted-proposals mode evaluates exact feasibility and deficits using accepted same-slice package-conflict structural proposals.",
            "- coverage_failure is treated as genuine nonextendability when the other strong-candidate conditions hold.",
            "",
            "## Candidate classification counts",
        ]
    )
    for mode_name, counts in sorted(classification_counts.items()):
        lines.append(f"- `{mode_name}`: `{counts}`")
    lines.extend(
        [
            "",
            "## Adequacy floor result",
            f"- Adequate: `{adequacy['adequate']}`",
            f"- Counts: `{adequacy['counts']}`",
            f"- Checks: `{adequacy['checks']}`",
            "",
            "## Context-pair structure summary",
            f"- Context-pair rows: `{structure.row_count}`",
            f"- Package-conflict admissible rows: `{sum(1 for row in structure.rows if row.primary_packaging_conflict_admissible)}`",
            f"- Non-nested package-conflict rows: `{sum(1 for row in structure.rows if row.primary_packaging_conflict_admissible and row.relation_type == 'incomparable')}`",
            "",
            "## Projection-family admissibility summary",
            f"- Admissibility rows: `{admissibility.row_count}`",
            f"- Primary-context eligible rows: `{sum(1 for row in admissibility.rows if 'primary_context' in row.allowed_roles)}`",
            "",
            "## Outcome",
            f"- Outcome kind: `{outcome_kind}`",
            f"- Best candidate: `{None if best_candidate is None else {'point_id': best_candidate[0].point_id, 'mode': best_candidate[1]}}`",
            f"- Comparative conclusion: `{comparative_conclusion}`",
            "",
            "## Notes",
            "- RM is diagnostic-only.",
            "- unsolved / insufficient_data / not_applicable statuses are preserved explicitly.",
            "",
            "## Artifact references",
            f"- Comparison CSV: `{output_paths['table_csv']}`",
            f"- Comparison JSON: `{output_paths['table_json']}`",
            f"- Context-pair structure: `{output_paths['context_pair_structure']}`",
            f"- Projection-family admissibility: `{output_paths['projection_family_admissibility']}`",
            f"- Commutator summary: `{output_paths['commutator_summary']}`",
            f"- Summary: `{output_paths['summary']}`",
            f"- Result note: `{output_paths['result_note']}`",
            f"- Run manifest: `{output_paths['manifest']}`",
            f"- Outcome artifact: `{output_paths['outcome']}`",
        ]
    )
    return "\n".join(lines) + "\n"


def _build_result_note(
    *,
    run_id: str,
    table: PackagingConflictComparisonTable,
    structure: ContextPairStructureTable,
    commutator_summary: dict[str, object],
    classification_counts: dict[str, dict[str, int]],
    adequacy: dict[str, object],
    outcome_kind: str,
    best_candidate: tuple[PackagingConflictComparisonRow, CommutatorAdmissibilityMode]
    | None,
    comparative_conclusion: str,
    output_paths: dict[str, str],
) -> ResultNote:
    metrics: dict[str, object] = {
        "point_count": table.row_count,
        "context_pair_row_count": structure.row_count,
        "adequacy_met": adequacy["adequate"],
        "outcome_kind": outcome_kind,
        "comparative_conclusion": comparative_conclusion,
        **adequacy["counts"],
    }
    for mode_name, counts in sorted(classification_counts.items()):
        for label, count in sorted(counts.items()):
            metrics[f"{mode_name}_classification_count_{label}"] = count
    return ResultNote(
        note_format_version="result-note.v1",
        note_id=f"note_{run_id}",
        run_id=run_id,
        instance_ids=[table.search_id],
        metrics=metrics,
        interpretation=(
            "The comparative packaging-conflict PICA search evaluates the same bounded family in p5_only and p5_p6_combined admissibility modes and records whether widening the commutator surface changes package-conflict signal or proposal support relation kinds."
        ),
        caveats=[
            "Projection-only differences do not count as primary package-conflict evidence.",
            "coverage_failure is treated as genuine nonextendability when the package-conflict strong-candidate conditions hold.",
        ],
        artifact_refs=output_paths,
        metadata={
            "classifier_version": PICA_PACKAGING_CONFLICT_CLASSIFIER_VERSION,
            "adequacy_version": PICA_PACKAGING_CONFLICT_ADEQUACY_VERSION,
            "best_candidate_id": None
            if best_candidate is None
            else best_candidate[0].point_id,
            "best_candidate_mode": None
            if best_candidate is None
            else best_candidate[1],
        },
    )


def run_pica_packaging_conflict_search(
    *,
    search_path: str | Path,
    category: str,
    label: str | None = None,
    seed: int = 0,
    timestamp: str | None = None,
    root: str | Path | None = None,
    commutator_admissibility_mode: str | None = None,
    command: list[str] | None = None,
) -> PicaPackagingConflictArtifacts:
    del seed
    repo_root = Path(root).resolve() if root is not None else None
    search = load_pica_packaging_conflict_search(search_path)
    run_dir, run_id, manifest_timestamp = create_run_directory(
        category=category,
        label=label or search.search_id,
        timestamp=timestamp,
        root=repo_root,
    )
    effective_root = run_dir.parents[2]
    derived_dir = run_dir / "derived"
    derived_dir.mkdir()
    projection_family_map = _projection_family_map(search)
    effective_mode = commutator_admissibility_mode or "both"
    mode_names: list[CommutatorAdmissibilityMode]
    if effective_mode == "both":
        mode_names = ["p5_only", "p5_p6_combined"]
    else:
        mode_names = [effective_mode]  # type: ignore[list-item]
    prepared_points = {
        point.point_id: _prepare_point(
            point=point,
            search=search,
            projection_family_map=projection_family_map,
            category=category,
            timestamp=timestamp,
            root=effective_root,
            derived_dir=derived_dir,
        )
        for point in search.points
    }
    mode_artifacts_by_point: dict[str, dict[str, _PointModeArtifacts]] = {
        point.point_id: {} for point in search.points
    }
    for point in search.points:
        prepared = prepared_points[point.point_id]
        for mode_name in mode_names:
            mode_artifacts_by_point[point.point_id][mode_name] = _run_point_mode(
                point=point,
                search=search,
                prepared=prepared,
                commutator_admissibility_mode=mode_name,
                projection_family_map=projection_family_map,
                category=category,
                timestamp=timestamp,
                root=effective_root,
                derived_dir=derived_dir,
            )
        if "p5_only" not in mode_artifacts_by_point[point.point_id]:
            mode_artifacts_by_point[point.point_id]["p5_only"] = (
                mode_artifacts_by_point[point.point_id]["p5_p6_combined"]
            )
        if "p5_p6_combined" not in mode_artifacts_by_point[point.point_id]:
            mode_artifacts_by_point[point.point_id]["p5_p6_combined"] = (
                mode_artifacts_by_point[point.point_id]["p5_only"]
            )

    comparison_rows: list[PackagingConflictComparisonRow] = []
    changed_pair_point_ids: set[str] = set()
    all_context_pair_rows: list[ContextPairStructureRow] = []
    for point in search.points:
        p5_artifacts = mode_artifacts_by_point[point.point_id]["p5_only"]
        combined_artifacts = mode_artifacts_by_point[point.point_id]["p5_p6_combined"]
        if p5_artifacts.primary_pair_ids != combined_artifacts.primary_pair_ids:
            changed_pair_point_ids.add(point.point_id)
        all_context_pair_rows.extend(p5_artifacts.context_pair_rows)
        if "both" == effective_mode:
            all_context_pair_rows.extend(combined_artifacts.context_pair_rows)
        common_provenance = (
            p5_artifacts.row.provenance_classification
            if p5_artifacts.row.provenance_classification
            == combined_artifacts.row.provenance_classification
            else combined_artifacts.row.provenance_classification
        )
        comparison_rows.append(
            PackagingConflictComparisonRow(
                row_format_version="packaging-conflict-comparison-row.v1",
                search_id=search.search_id,
                point_id=point.point_id,
                source_pica_campaign_config_path=point.pilot_config_artifact,
                projection_family_ids=list(point.projection_family_ids),
                preparation_id=point.preparation_id,
                protocol_id=point.protocol_id,
                selected_protocol_step_ids=list(point.selected_protocol_step_ids),
                selected_step_indices=list(point.selected_step_indices),
                trajectories=point.trajectories,
                seed_list=list(point.seed_list),
                produced_export_bundle_path=prepared_points[
                    point.point_id
                ].merged_bundle_relpath,
                discovered_context_family_path=prepared_points[
                    point.point_id
                ].family_path,
                event_package_path=combined_artifacts.row.event_package_path,
                provenance_classification=common_provenance,
                accepted_context_count=prepared_points[
                    point.point_id
                ].family.diagnostics_summary.accepted_context_count,
                accepted_proper_coarse_event_count=combined_artifacts.row.accepted_proper_coarse_event_count,
                equal_context_pair_count=combined_artifacts.row.equal_context_pair_count,
                left_refines_right_count=combined_artifacts.row.left_refines_right_count,
                right_refines_left_count=combined_artifacts.row.right_refines_left_count,
                incomparable_context_pair_count=combined_artifacts.row.incomparable_context_pair_count,
                disjoint_or_unaligned_context_pair_count=combined_artifacts.row.disjoint_or_unaligned_context_pair_count,
                same_slice_non_nested_context_pair_count=combined_artifacts.row.same_slice_non_nested_context_pair_count,
                primary_identity_admissible_pair_count=combined_artifacts.row.primary_identity_admissible_pair_count,
                p5_only=PackagingConflictModeResult(
                    commutator_admissibility_mode="p5_only",
                    relevant_commutator_pairs=_relevant_pairs_for_mode(
                        search, "p5_only"
                    ),
                    accepted_shared_event_proposal_count=p5_artifacts.row.accepted_shared_event_proposal_count,
                    accepted_proper_coarse_structural_proposal_count=p5_artifacts.row.accepted_proper_coarse_structural_proposal_count,
                    accepted_package_conflict_same_slice_proper_coarse_proposal_count=p5_artifacts.row.accepted_package_conflict_same_slice_proper_coarse_proposal_count,
                    accepted_non_nested_package_conflict_proposal_count=p5_artifacts.row.accepted_non_nested_package_conflict_proposal_count,
                    packaging_conflict_admissible_pair_count=p5_artifacts.row.packaging_conflict_admissible_pair_count,
                    same_slice_non_nested_packaging_conflict_pair_count=p5_artifacts.row.same_slice_non_nested_packaging_conflict_pair_count,
                    nonzero_relevant_commutator_support_count=p5_artifacts.row.nonzero_relevant_p5_commutator_support_count,
                    median_accepted_proposal_support=p5_artifacts.row.median_accepted_proposal_support,
                    support_relation_kind_counts=p5_artifacts.commutator_summary.get(
                        "support_relation_kind_counts", {}
                    ),
                    baseline_hard_only=p5_artifacts.row.baseline_hard_only,
                    all_accepted_proposals=p5_artifacts.row.all_accepted_proposals,
                    candidate_classification=p5_artifacts.row.candidate_classification,
                    artifact_paths={
                        f"p5_only_{key}": value
                        for key, value in p5_artifacts.row.artifact_paths.items()
                    },
                ),
                p5_p6_combined=PackagingConflictModeResult(
                    commutator_admissibility_mode="p5_p6_combined",
                    relevant_commutator_pairs=_relevant_pairs_for_mode(
                        search, "p5_p6_combined"
                    ),
                    accepted_shared_event_proposal_count=combined_artifacts.row.accepted_shared_event_proposal_count,
                    accepted_proper_coarse_structural_proposal_count=combined_artifacts.row.accepted_proper_coarse_structural_proposal_count,
                    accepted_package_conflict_same_slice_proper_coarse_proposal_count=combined_artifacts.row.accepted_package_conflict_same_slice_proper_coarse_proposal_count,
                    accepted_non_nested_package_conflict_proposal_count=combined_artifacts.row.accepted_non_nested_package_conflict_proposal_count,
                    packaging_conflict_admissible_pair_count=combined_artifacts.row.packaging_conflict_admissible_pair_count,
                    same_slice_non_nested_packaging_conflict_pair_count=combined_artifacts.row.same_slice_non_nested_packaging_conflict_pair_count,
                    nonzero_relevant_commutator_support_count=combined_artifacts.row.nonzero_relevant_p5_commutator_support_count,
                    median_accepted_proposal_support=combined_artifacts.row.median_accepted_proposal_support,
                    support_relation_kind_counts=combined_artifacts.commutator_summary.get(
                        "support_relation_kind_counts", {}
                    ),
                    baseline_hard_only=combined_artifacts.row.baseline_hard_only,
                    all_accepted_proposals=combined_artifacts.row.all_accepted_proposals,
                    candidate_classification=combined_artifacts.row.candidate_classification,
                    artifact_paths={
                        f"p5_p6_combined_{key}": value
                        for key, value in combined_artifacts.row.artifact_paths.items()
                    },
                ),
                run_ids={
                    **prepared_points[point.point_id].run_ids,
                    **p5_artifacts.row.run_ids,
                    **combined_artifacts.row.run_ids,
                },
                artifact_paths={
                    "export_bundle": prepared_points[
                        point.point_id
                    ].merged_bundle_relpath,
                    "discovered_context_family": prepared_points[
                        point.point_id
                    ].family_path,
                    **{
                        f"p5_only_{key}": value
                        for key, value in p5_artifacts.row.artifact_paths.items()
                    },
                    **{
                        f"p5_p6_combined_{key}": value
                        for key, value in combined_artifacts.row.artifact_paths.items()
                    },
                },
                notes=list(point.notes),
            )
        )

    table = PackagingConflictComparisonTable(
        table_format_version="packaging-conflict-comparison-results.v1",
        search_id=search.search_id,
        row_count=len(comparison_rows),
        rows=comparison_rows,
        metadata={"search_path": repo_relative_path(search_path, root=effective_root)},
    )
    structure = ContextPairStructureTable(
        structure_format_version="context-pair-structure.v1",
        search_id=search.search_id,
        row_count=len(all_context_pair_rows),
        rows=all_context_pair_rows,
        metadata={"search_path": repo_relative_path(search_path, root=effective_root)},
    )
    admissibility = ProjectionFamilyAdmissibilityTable(
        table_format_version="projection-family-admissibility.v1",
        search_id=search.search_id,
        row_count=sum(
            len(prepared.admissibility_rows) for prepared in prepared_points.values()
        ),
        rows=[
            row
            for prepared in prepared_points.values()
            for row in prepared.admissibility_rows
        ],
        metadata={"search_path": repo_relative_path(search_path, root=effective_root)},
    )
    classification_counts = _classification_counts_by_mode(table.rows)
    adequacy = _evaluate_adequacy(
        rows=table.rows,
        search=search,
        changed_pair_point_ids=changed_pair_point_ids,
    )
    best_candidate = _select_best_candidate(table.rows)
    comparative_conclusion = _comparative_conclusion(
        table.rows,
        changed_pair_point_ids=changed_pair_point_ids,
        best_candidate=best_candidate,
    )
    outcome_kind = (
        "best_candidate"
        if best_candidate is not None
        else ("negative_result" if adequacy["adequate"] else "design_inadequate")
    )
    commutator_summary = {
        "row_count": len(comparison_rows),
        "points_with_changed_packaging_conflict_pair_set": len(changed_pair_point_ids),
        "rows": [
            {
                "point_id": point_id,
                "p5_only": mode_artifacts_by_point[point_id][
                    "p5_only"
                ].commutator_summary,
                "p5_p6_combined": mode_artifacts_by_point[point_id][
                    "p5_p6_combined"
                ].commutator_summary,
            }
            for point_id in sorted(mode_artifacts_by_point)
        ],
    }

    table_csv_path = run_dir / "packaging-conflict-comparison.csv"
    table_json_path = run_dir / "packaging-conflict-comparison.json"
    context_pair_structure_path = run_dir / "context-pair-structure.json"
    projection_family_admissibility_path = (
        run_dir / "projection-family-admissibility.json"
    )
    commutator_summary_path = run_dir / "pica-commutator-catalog-summary.json"
    summary_path = run_dir / "packaging-conflict-comparison-summary.json"
    note_path = run_dir / "packaging-conflict-comparison-note.md"
    result_note_path = run_dir / "result-note.json"
    manifest_path = run_dir / "run-manifest.json"
    outcome_filename = (
        "best-candidate.json"
        if outcome_kind == "best_candidate"
        else (
            "negative-result.json"
            if outcome_kind == "negative_result"
            else "design-inadequate-result.json"
        )
    )
    outcome_path = run_dir / outcome_filename

    _write_csv(table_csv_path, [_row_to_csv_record(row) for row in table.rows])
    _write_json(table_json_path, table.model_dump(mode="json"))
    _write_json(context_pair_structure_path, structure.model_dump(mode="json"))
    _write_json(
        projection_family_admissibility_path,
        admissibility.model_dump(mode="json"),
    )
    _write_json(commutator_summary_path, commutator_summary)
    summary_payload = {
        "search_id": search.search_id,
        "campaign_family": [row.source_pica_campaign_config_path for row in table.rows],
        "commutator_admissibility_modes": mode_names,
        "projection_family_admissibility_summary": {
            "row_count": admissibility.row_count,
            "primary_context_rows": sum(
                1
                for row in admissibility.rows
                if "primary_context" in row.allowed_roles
            ),
        },
        "package_conflict_admissibility_summary": {
            "same_slice_non_nested_packaging_conflict_pair_count": sum(
                row.p5_p6_combined.same_slice_non_nested_packaging_conflict_pair_count
                for row in table.rows
            ),
            "packaging_conflict_admissible_pair_count": sum(
                row.p5_p6_combined.packaging_conflict_admissible_pair_count
                for row in table.rows
            ),
        },
        "relevant_commutator_support_summary": commutator_summary,
        "adequacy_floor_thresholds": search.adequacy_floor.model_dump(mode="json"),
        "adequacy_floor_result": adequacy,
        "counts_by_candidate_class": classification_counts,
        "best_candidate": None
        if best_candidate is None
        else {"point_id": best_candidate[0].point_id, "mode": best_candidate[1]},
        "comparative_surface_changed_pair_set": len(changed_pair_point_ids) > 0,
        "accepted_proposals_by_support_relation_kind": {
            mode_name: dict(
                sorted(
                    Counter(
                        kind
                        for row in table.rows
                        for kind, count in getattr(
                            row, mode_name
                        ).support_relation_kind_counts.items()
                        for _ in range(count)
                    ).items()
                )
            )
            for mode_name in ["p5_only", "p5_p6_combined"]
        },
        "comparative_conclusion": comparative_conclusion,
        "negative_result": outcome_kind == "negative_result",
        "design_inadequate": outcome_kind == "design_inadequate",
        "outcome_kind": outcome_kind,
        "paths": {
            "table_csv": repo_relative_path(table_csv_path, root=effective_root),
            "table_json": repo_relative_path(table_json_path, root=effective_root),
            "context_pair_structure": repo_relative_path(
                context_pair_structure_path,
                root=effective_root,
            ),
            "projection_family_admissibility": repo_relative_path(
                projection_family_admissibility_path,
                root=effective_root,
            ),
            "commutator_summary": repo_relative_path(
                commutator_summary_path,
                root=effective_root,
            ),
            "summary": repo_relative_path(summary_path, root=effective_root),
            "note": repo_relative_path(note_path, root=effective_root),
            "result_note": repo_relative_path(result_note_path, root=effective_root),
            "manifest": repo_relative_path(manifest_path, root=effective_root),
            "outcome": repo_relative_path(outcome_path, root=effective_root),
        },
    }
    _write_json(summary_path, summary_payload)
    outcome_payload = (
        {
            "point_id": best_candidate[0].point_id,
            "mode": best_candidate[1],
            "row": best_candidate[0].model_dump(mode="json"),
        }
        if best_candidate is not None
        else {
            "outcome": "negative_result"
            if outcome_kind == "negative_result"
            else "design_inadequate",
            "adequacy_floor_met": adequacy["adequate"],
            "negative_result": outcome_kind == "negative_result",
            "counts_by_candidate_class": classification_counts,
            "adequacy_floor_result": adequacy,
            "comparative_conclusion": comparative_conclusion,
        }
    )
    _write_json(outcome_path, outcome_payload)

    output_paths = summary_payload["paths"]
    note_path.write_text(
        _render_note(
            search=search,
            table=table,
            structure=structure,
            admissibility=admissibility,
            commutator_summary=commutator_summary,
            classification_counts=classification_counts,
            adequacy=adequacy,
            best_candidate=best_candidate,
            outcome_kind=outcome_kind,
            comparative_conclusion=comparative_conclusion,
            output_paths=output_paths,
        ),
        encoding="utf-8",
    )
    result_note = _build_result_note(
        run_id=run_id,
        table=table,
        structure=structure,
        commutator_summary=commutator_summary,
        classification_counts=classification_counts,
        adequacy=adequacy,
        outcome_kind=outcome_kind,
        best_candidate=best_candidate,
        comparative_conclusion=comparative_conclusion,
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
            "run-packaging-conflict",
            repo_relative_path(search_path, root=effective_root),
            "--commutator-admissibility-mode",
            effective_mode,
        ],
        seed=0,
        input_artifacts={
            "search_config": repo_relative_path(search_path, root=effective_root)
        },
        output_artifacts={
            "table_csv": output_paths["table_csv"],
            "table_json": output_paths["table_json"],
            "context_pair_structure": output_paths["context_pair_structure"],
            "projection_family_admissibility": output_paths[
                "projection_family_admissibility"
            ],
            "commutator_summary": output_paths["commutator_summary"],
            "summary": output_paths["summary"],
            "note": output_paths["note"],
            "result_note": output_paths["result_note"],
            "outcome": output_paths["outcome"],
        },
        status="succeeded",
        git_commit=detect_git_commit(root=effective_root),
        metadata={
            "analysis_kind": "pica_packaging_conflict_search",
            "classifier_version": PICA_PACKAGING_CONFLICT_CLASSIFIER_VERSION,
            "adequacy_version": PICA_PACKAGING_CONFLICT_ADEQUACY_VERSION,
            "commutator_admissibility_mode": effective_mode,
        },
    )
    write_run_manifest(manifest, run_dir=run_dir)
    return PicaPackagingConflictArtifacts(
        run_id=run_id,
        run_dir=repo_relative_path(run_dir, root=effective_root),
        table_csv_path=output_paths["table_csv"],
        table_json_path=output_paths["table_json"],
        context_pair_structure_path=output_paths["context_pair_structure"],
        projection_family_admissibility_path=output_paths[
            "projection_family_admissibility"
        ],
        commutator_summary_path=output_paths["commutator_summary"],
        summary_path=output_paths["summary"],
        note_path=output_paths["note"],
        result_note_path=output_paths["result_note"],
        manifest_path=repo_relative_path(manifest_path, root=effective_root),
        table=table,
        context_pair_structure=structure,
        projection_family_admissibility=admissibility,
        classification_counts=classification_counts,
        outcome_path=output_paths["outcome"],
        outcome_kind=outcome_kind,
    )
