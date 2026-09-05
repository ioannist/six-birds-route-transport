from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import csv
import json
from itertools import combinations
from pathlib import Path
import statistics
import sys

from ..discovery.context_discovery import build_event_package_skeleton
from ..discovery.models import (
    AcceptedContext,
    DiscoverySummary,
    DiscoveredContextFamily,
    PicaContextDiscoveryConfig,
    PicaContextDiscoveryThresholds,
    RejectedCandidate,
    SharedEventCandidates,
)
from ..discovery.pica_context_discovery import discover_pica_context_family
from ..discovery.shared_event_inference import _project_pica_row_label
from ..pica_bridge.ingest import PicaBundleResolved, load_pica_export_bundle
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
    ClosureDiverseProjectionFamily,
    ContextPairSide,
    ContextPairStructureRow,
    ContextPairStructureTable,
    ContextRelationType,
    PicaClosureDiverseSearch,
    PicaClosureDiverseSearchPoint,
    PicaClosureDiverseSearchRow,
    PicaClosureDiverseSearchTable,
    TargetedCandidateLabel,
    TargetedSearchEvaluation,
)
from .pica_targeted_obstruction import (
    _baseline_deficit_evaluation,
    _candidate_deficit_evaluation,
    _derive_pica_stat_trace,
    _merge_pilot_outputs,
    _pilot_config_for_seed,
    _point_has_dual_mode_difference,
    _sec_summary,
    _load_pilot_config,
)


PICA_CLOSURE_DIVERSE_CLASSIFIER_VERSION = "pica-closure-diverse-classifier.v1"
PICA_CLOSURE_DIVERSE_ADEQUACY_VERSION = "pica-closure-diverse-adequacy-floor.v1"


@dataclass(slots=True)
class PicaClosureDiverseArtifacts:
    run_id: str
    run_dir: str
    table_csv_path: str
    table_json_path: str
    context_pair_structure_path: str
    summary_path: str
    note_path: str
    result_note_path: str
    manifest_path: str
    table: PicaClosureDiverseSearchTable
    context_pair_structure: ContextPairStructureTable
    classification_counts: dict[str, int]
    outcome_path: str
    outcome_kind: str


@dataclass(slots=True)
class _PointArtifacts:
    row: PicaClosureDiverseSearchRow
    context_pair_rows: list[ContextPairStructureRow]


def load_pica_closure_diverse_search(
    path: str | Path,
) -> PicaClosureDiverseSearch:
    model = load_model(path, kind="pica-closure-diverse-search")
    assert isinstance(model, PicaClosureDiverseSearch)
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


def _slug(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in value).strip("_")


def _projection_family_map(
    search: PicaClosureDiverseSearch,
) -> dict[str, ClosureDiverseProjectionFamily]:
    return {family.projection_id: family for family in search.projection_families}


def _projection_context_id(context_id: str, projection_id: str) -> str:
    return f"{context_id}__proj_{_slug(projection_id)}"


def _base_discovery_config(
    *,
    bundle_artifact: str,
    projection_family: ClosureDiverseProjectionFamily,
) -> PicaContextDiscoveryConfig:
    return PicaContextDiscoveryConfig(
        schema_version="pica-context-discovery.v1",
        bundle_artifact=bundle_artifact,
        selected_run_ids=[],
        selected_point_ids=[],
        projection=projection_family.projection,
        grouping_key_fields=[
            "preparation_id",
            "protocol_id",
            "level_id",
            "resolution_id",
            "closure_id",
            "lens_id",
            "protocol_step_id",
        ],
        thresholds=PicaContextDiscoveryThresholds(
            min_row_count=2,
            min_atom_count=2,
            min_atom_support_count=1,
            min_atom_support_fraction=0.0,
            min_coverage=1.0,
            max_batch_tv=1.0,
            batch_count=2,
        ),
        notes=[
            f"Projection family {projection_family.projection_id}: {projection_family.label}"
        ],
        flags=list(projection_family.notes),
    )


def _annotation_projection_id(
    context: AcceptedContext | RejectedCandidate,
    projection_id: str,
) -> AcceptedContext | RejectedCandidate:
    source_metadata = context.source_metadata
    if source_metadata is None:
        return context
    new_metadata = source_metadata.model_copy(update={"projection_id": projection_id})
    if isinstance(context, AcceptedContext):
        return context.model_copy(update={"source_metadata": new_metadata})
    return context.model_copy(update={"source_metadata": new_metadata})


def _discover_multi_projection_family(
    *,
    point: PicaClosureDiverseSearchPoint,
    search: PicaClosureDiverseSearch,
    resolved: PicaBundleResolved,
    bundle_artifact: str,
    projection_families: list[ClosureDiverseProjectionFamily],
    output_dir: Path,
    root: Path,
) -> tuple[str, str | None, DiscoveredContextFamily]:
    accepted_contexts: list[AcceptedContext] = []
    rejected_candidates: list[RejectedCandidate] = []
    rejection_reason_counts: Counter[str] = Counter()
    projection_fields: list[str] = []

    for projection_family in projection_families:
        projection_fields.append(
            projection_family.projection.payload_key
            or projection_family.projection.projection_mode
        )
        discovery = discover_pica_context_family(
            resolved,
            config=_base_discovery_config(
                bundle_artifact=bundle_artifact,
                projection_family=projection_family,
            ),
            family_id=f"{point.point_id}_{projection_family.projection_id}",
            bundle_artifact=bundle_artifact,
        )
        for context in discovery.family.accepted_contexts:
            annotated = _annotation_projection_id(
                context, projection_family.projection_id
            )
            assert isinstance(annotated, AcceptedContext)
            accepted_contexts.append(
                annotated.model_copy(
                    update={
                        "context_id": _projection_context_id(
                            annotated.context_id, projection_family.projection_id
                        )
                    }
                )
            )
        for candidate in discovery.family.rejected_candidates:
            annotated = _annotation_projection_id(
                candidate, projection_family.projection_id
            )
            assert isinstance(annotated, RejectedCandidate)
            rejected_candidates.append(annotated)
            rejection_reason_counts.update(annotated.rejection_reasons)

    accepted_contexts = sorted(
        accepted_contexts, key=lambda context: context.context_id
    )
    family = DiscoveredContextFamily(
        family_format_version="discovered-context-family.v1",
        family_id=f"{point.point_id}_closure_diverse_contexts",
        source_run_artifacts=[bundle_artifact],
        thresholds={
            "min_trajectory_count": 2,
            "min_atom_count": 2,
            "min_atom_support_count": 1,
            "min_atom_support_fraction": 0.0,
            "min_coverage": 1.0,
            "max_batch_tv": 1.0,
            "max_persistence_flip_rate": None,
            "batch_count": 2,
        },
        accepted_contexts=accepted_contexts,
        rejected_candidates=rejected_candidates,
        diagnostics_summary=DiscoverySummary(
            candidate_count=len(accepted_contexts) + len(rejected_candidates),
            accepted_context_count=len(accepted_contexts),
            rejected_candidate_count=len(rejected_candidates),
            rejection_reason_counts=dict(sorted(rejection_reason_counts.items())),
            accepted_context_ids=[context.context_id for context in accepted_contexts],
        ),
        event_package_skeleton_artifact=None,
        source_mode="pica_export_bundle",
        source_bundle_artifact=bundle_artifact,
        metadata={
            "observable_only": True,
            "projection_family_ids": [
                family.projection_id for family in projection_families
            ],
            "projection_fields": sorted(set(projection_fields)),
            "distinct_projection_count": len(projection_families),
            "distinct_level_count": len(
                {
                    context.candidate_key.level_id
                    for context in accepted_contexts
                    if context.candidate_key.level_id is not None
                }
            ),
            "distinct_resolution_count": len(
                {
                    context.candidate_key.resolution_id
                    for context in accepted_contexts
                    if context.candidate_key.resolution_id is not None
                }
            ),
            "distinct_closure_count": len(
                {
                    context.candidate_key.closure_id
                    for context in accepted_contexts
                    if context.candidate_key.closure_id is not None
                }
            ),
            "distinct_projection_field_count": len(set(projection_fields)),
        },
    )
    skeleton = build_event_package_skeleton(
        family,
        created_at="2026-03-27T00:00:00Z",
    )

    point_dir = output_dir / point.point_id
    point_dir.mkdir(parents=True, exist_ok=True)
    family_path = point_dir / "discovered-context-family.json"
    skeleton_path = point_dir / "event-package-skeleton.json"
    _write_json(family_path, family.model_dump(mode="json"))
    if skeleton is not None:
        _write_json(skeleton_path, skeleton.model_dump(mode="json"))
    return (
        repo_relative_path(family_path, root=root),
        repo_relative_path(skeleton_path, root=root) if skeleton is not None else None,
        family,
    )


def _context_assignment_map(
    *,
    resolved: PicaBundleResolved,
    context: AcceptedContext,
) -> dict[tuple[str, str], str]:
    source_metadata = context.source_metadata
    if source_metadata is None:
        return {}
    label_to_outcome = {
        outcome.observation_label: outcome.outcome_id
        for outcome in context.atomic_outcomes
    }
    assignment: dict[tuple[str, str], str] = {}
    ledgers_by_run = resolved.observable_ledgers_by_run()
    for run_id in source_metadata.run_ids:
        ledger = ledgers_by_run.get(run_id)
        if ledger is None:
            continue
        for row in ledger.rows:
            if row.preparation_id != source_metadata.preparation_id:
                continue
            if row.protocol_id != source_metadata.protocol_id:
                continue
            if row.level_id != source_metadata.level_id:
                continue
            if row.resolution_id != source_metadata.resolution_id:
                continue
            if row.closure_id != source_metadata.closure_id:
                continue
            if row.lens_id != source_metadata.lens_id:
                continue
            if row.protocol_step_id != source_metadata.protocol_step_id:
                continue
            if row.step_index != source_metadata.step_index:
                continue
            projected = _project_pica_row_label(row, source_metadata)
            if projected is None:
                continue
            atom_id = label_to_outcome.get(projected)
            if atom_id is None:
                continue
            assignment[(run_id, row.trajectory_id)] = atom_id
    return assignment


def _blocks_for_shared_rows(
    assignment: dict[tuple[str, str], str], shared_rows: set[tuple[str, str]]
) -> list[set[tuple[str, str]]]:
    blocks: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for row_id in shared_rows:
        blocks[assignment[row_id]].add(row_id)
    return [block for _, block in sorted(blocks.items())]


def _refines(
    left_blocks: list[set[tuple[str, str]]], right_blocks: list[set[tuple[str, str]]]
) -> bool:
    if not left_blocks:
        return False
    return all(any(left <= right for right in right_blocks) for left in left_blocks)


def _pair_side(context: AcceptedContext) -> ContextPairSide:
    assert context.source_metadata is not None
    source_metadata = context.source_metadata
    return ContextPairSide(
        context_id=context.context_id,
        level_id=source_metadata.level_id,
        resolution_id=source_metadata.resolution_id,
        closure_id=source_metadata.closure_id,
        lens_id=source_metadata.lens_id,
        protocol_step_id=source_metadata.protocol_step_id,
        step_index=source_metadata.step_index,
        projection_id=source_metadata.projection_id,
        projection_field=source_metadata.projection_field,
    )


def _context_pair_rows(
    *,
    point: PicaClosureDiverseSearchPoint,
    resolved: PicaBundleResolved,
    family: DiscoveredContextFamily,
) -> list[ContextPairStructureRow]:
    assignments = {
        context.context_id: _context_assignment_map(resolved=resolved, context=context)
        for context in family.accepted_contexts
    }
    rows: list[ContextPairStructureRow] = []
    for left, right in combinations(family.accepted_contexts, 2):
        if (
            left.candidate_key.preparation_id != right.candidate_key.preparation_id
            or left.candidate_key.protocol_id != right.candidate_key.protocol_id
        ):
            continue
        left_assignment = assignments[left.context_id]
        right_assignment = assignments[right.context_id]
        same_step = (
            left.candidate_key.step_index == right.candidate_key.step_index
            and left.candidate_key.protocol_step_id
            == right.candidate_key.protocol_step_id
        )
        shared_rows = set(left_assignment) & set(right_assignment)
        notes: list[str] = []
        flags: list[str] = []
        if not same_step:
            relation: ContextRelationType = "disjoint_or_unaligned"
            notes.append("unaligned_step_family")
        elif not shared_rows:
            relation = "disjoint_or_unaligned"
            notes.append("no_shared_rows")
        else:
            left_blocks = _blocks_for_shared_rows(left_assignment, shared_rows)
            right_blocks = _blocks_for_shared_rows(right_assignment, shared_rows)
            left_refines = _refines(left_blocks, right_blocks)
            right_refines = _refines(right_blocks, left_blocks)
            if left_refines and right_refines:
                relation = "equal"
            elif left_refines:
                relation = "left_refines_right"
            elif right_refines:
                relation = "right_refines_left"
            else:
                relation = "incomparable"
                flags.append("non_nested")
        rows.append(
            ContextPairStructureRow(
                point_id=point.point_id,
                preparation_id=left.candidate_key.preparation_id,
                protocol_id=left.candidate_key.protocol_id,
                left=_pair_side(left),
                right=_pair_side(right),
                relation_type=relation,
                shared_row_count=len(shared_rows),
                left_assignment_count=len(left_assignment),
                right_assignment_count=len(right_assignment),
                left_block_count=len(set(left_assignment.values())),
                right_block_count=len(set(right_assignment.values())),
                same_step=same_step,
                notes=notes,
                flags=flags,
            )
        )
    return rows


def _row_to_csv_record(row: PicaClosureDiverseSearchRow) -> dict[str, object]:
    return {
        "point_id": row.point_id,
        "source_pica_campaign_config_path": row.source_pica_campaign_config_path,
        "projection_family_ids": "|".join(row.projection_family_ids),
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
        "accepted_shared_event_proposal_count": row.accepted_shared_event_proposal_count,
        "accepted_proper_coarse_structural_proposal_count": row.accepted_proper_coarse_structural_proposal_count,
        "accepted_incomparable_proper_coarse_proposal_count": row.accepted_incomparable_proper_coarse_proposal_count,
        "equal_context_pair_count": row.equal_context_pair_count,
        "left_refines_right_count": row.left_refines_right_count,
        "right_refines_left_count": row.right_refines_left_count,
        "incomparable_context_pair_count": row.incomparable_context_pair_count,
        "disjoint_or_unaligned_context_pair_count": row.disjoint_or_unaligned_context_pair_count,
        "median_accepted_proposal_support": row.median_accepted_proposal_support,
        "baseline_exact_structural_status": row.baseline_hard_only.exact_structural_status,
        "baseline_exact_feasible": row.baseline_hard_only.exact_feasible,
        "baseline_exact_respecting_tuple_count": row.baseline_hard_only.exact_respecting_tuple_count,
        "baseline_gpd_str_status": row.baseline_hard_only.gpd_str_status,
        "baseline_gpd_str": row.baseline_hard_only.gpd_str,
        "baseline_gpd_stat_status": row.baseline_hard_only.gpd_stat_status,
        "baseline_gpd_stat": row.baseline_hard_only.gpd_stat,
        "candidate_exact_structural_status": row.all_accepted_proposals.exact_structural_status,
        "candidate_exact_feasible": row.all_accepted_proposals.exact_feasible,
        "candidate_exact_respecting_tuple_count": row.all_accepted_proposals.exact_respecting_tuple_count,
        "candidate_gpd_str_status": row.all_accepted_proposals.gpd_str_status,
        "candidate_gpd_str": row.all_accepted_proposals.gpd_str,
        "candidate_gpd_stat_status": row.all_accepted_proposals.gpd_stat_status,
        "candidate_gpd_stat": row.all_accepted_proposals.gpd_stat,
        "sec_status": row.sec_status,
        "sec_mean": row.sec_mean,
        "rm_status": row.rm_status,
        "rm_overall": row.rm_overall,
        "ccd_status": row.ccd_status,
        "ccd_overall": row.ccd_overall,
        "candidate_classification": row.candidate_classification,
    }


def _relation_counts(
    rows: list[ContextPairStructureRow],
) -> dict[ContextRelationType, int]:
    counts: Counter[ContextRelationType] = Counter(row.relation_type for row in rows)
    return {
        "equal": counts.get("equal", 0),
        "left_refines_right": counts.get("left_refines_right", 0),
        "right_refines_left": counts.get("right_refines_left", 0),
        "incomparable": counts.get("incomparable", 0),
        "disjoint_or_unaligned": counts.get("disjoint_or_unaligned", 0),
    }


def _proposal_support(candidate: SharedEventCandidates) -> list[float]:
    supports: list[float] = []
    for row in candidate.candidate_rows:
        if not row.accepted:
            continue
        per_probe = [
            min(comparison.left_conditioning_count, comparison.right_conditioning_count)
            for comparison in row.probe_comparisons
        ]
        if per_probe:
            supports.append(float(statistics.median(per_probe)))
    return supports


def _candidate_classification(
    *,
    row: PicaClosureDiverseSearchRow,
    search: PicaClosureDiverseSearch,
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
    strong_block = (
        row.all_accepted_proposals.exact_respecting_tuple_count == 0
        or blocking_classification == "no_respecting_tuples"
    )

    if (
        provenance_ok
        and row.accepted_proper_coarse_structural_proposal_count
        >= search.candidate_classification_thresholds.min_accepted_coarse_proposal_count
        and row.accepted_incomparable_proper_coarse_proposal_count >= 1
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
    rows: list[PicaClosureDiverseSearchRow],
    search: PicaClosureDiverseSearch,
) -> dict[str, object]:
    all_supports = [
        row.median_accepted_proposal_support
        for row in rows
        if row.median_accepted_proposal_support is not None
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
        "points_with_proper_coarse_structural_proposals": sum(
            1
            for row in rows
            if row.accepted_proper_coarse_structural_proposal_count > 0
        ),
        "points_with_incomparable_context_pairs": sum(
            1 for row in rows if row.incomparable_context_pair_count > 0
        ),
        "points_with_dual_mode_difference": sum(
            1 for row in rows if _point_has_dual_mode_difference(row)
        ),
        "median_accepted_proposal_support": median_support,
    }
    floor = search.adequacy_floor
    checks = {
        "total_point_count": counts["total_point_count"] >= floor.min_total_point_count,
        "admissible_built_package_count": counts["admissible_built_package_count"]
        >= floor.min_admissible_built_package_count,
        "points_with_proper_coarse_events": counts["points_with_proper_coarse_events"]
        >= floor.min_points_with_proper_coarse_events,
        "points_with_proper_coarse_structural_proposals": counts[
            "points_with_proper_coarse_structural_proposals"
        ]
        >= floor.min_points_with_proper_coarse_structural_proposals,
        "points_with_incomparable_context_pairs": counts[
            "points_with_incomparable_context_pairs"
        ]
        >= floor.min_points_with_incomparable_context_pairs,
        "points_with_dual_mode_difference": counts["points_with_dual_mode_difference"]
        >= floor.min_points_with_dual_mode_difference,
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
    rows: list[PicaClosureDiverseSearchRow],
) -> PicaClosureDiverseSearchRow | None:
    candidates = [
        row
        for row in rows
        if row.candidate_classification == "strongly_nonextendable_candidate"
    ]
    if not candidates:
        return None
    return sorted(
        candidates,
        key=lambda row: (
            -(row.all_accepted_proposals.gpd_str or 0.0),
            -row.accepted_incomparable_proper_coarse_proposal_count,
            row.all_accepted_proposals.exact_respecting_tuple_count
            if row.all_accepted_proposals.exact_respecting_tuple_count is not None
            else 10**9,
            row.point_id,
        ),
    )[0]


def _run_point(
    *,
    point: PicaClosureDiverseSearchPoint,
    search: PicaClosureDiverseSearch,
    projection_family_map: dict[str, ClosureDiverseProjectionFamily],
    category: str,
    timestamp: str | None,
    root: Path,
    derived_dir: Path,
) -> _PointArtifacts:
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
        seeded_config_path = point_config_dir / f"pilot-seed-{seed}.json"
        _write_json(seeded_config_path, seeded_payload)
        pilot_artifacts = run_pica_pilot_campaign(
            config_path=seeded_config_path,
            category=category,
            label=f"{search.search_id}-{point.point_id}-pica-seed{seed}",
            timestamp=timestamp,
            root=root,
            command=[
                sys.executable,
                "-m",
                "sixbirds_event",
                "pica",
                "run-pilot",
                point.pilot_config_artifact,
            ],
        )
        pilot_outputs.append(pilot_artifacts)
        run_ids[f"pica_wrapper_{index}"] = pilot_artifacts.run_id

    merged_bundle_relpath = _merge_pilot_outputs(
        point=point,
        preparation_id=point.preparation_id,
        protocol_id=point.protocol_id,
        pilot_outputs=pilot_outputs,
        output_dir=derived_dir / "bundles",
        root=root,
    )
    merged_bundle_path = root / merged_bundle_relpath
    resolved_bundle = load_pica_export_bundle(merged_bundle_path, repo_root=root)
    projection_families = [
        projection_family_map[projection_id]
        for projection_id in point.projection_family_ids
    ]

    family_path, skeleton_path, family = _discover_multi_projection_family(
        point=point,
        search=search,
        resolved=resolved_bundle,
        bundle_artifact=merged_bundle_relpath,
        projection_families=projection_families,
        output_dir=derived_dir / "contexts",
        root=root,
    )
    context_pair_rows = _context_pair_rows(
        point=point,
        resolved=resolved_bundle,
        family=family,
    )
    relation_counts = _relation_counts(context_pair_rows)
    point_pair_path = (
        derived_dir / "context-pairs" / point.point_id / "context-pair-structure.json"
    )
    point_pair_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(
        point_pair_path,
        ContextPairStructureTable(
            structure_format_version="context-pair-structure.v1",
            search_id=search.search_id,
            row_count=len(context_pair_rows),
            rows=context_pair_rows,
            metadata={"point_id": point.point_id},
        ).model_dump(mode="json"),
    )
    notes = list(point.notes)
    if relation_counts["incomparable"] > 0:
        notes.append("non_nested_context_pairs_present")

    if family.diagnostics_summary.accepted_context_count < 2:
        row = PicaClosureDiverseSearchRow(
            row_format_version="pica-closure-diverse-search-row.v1",
            search_id=search.search_id,
            point_id=point.point_id,
            source_pica_campaign_config_path=point.pilot_config_artifact,
            projection_family_ids=list(point.projection_family_ids),
            preparation_id=point.preparation_id,
            protocol_id=point.protocol_id,
            trajectories=point.trajectories,
            seed_list=point.seed_list,
            produced_export_bundle_path=merged_bundle_relpath,
            discovered_context_family_path=family_path,
            event_package_path=None,
            provenance_classification=None,
            accepted_context_count=family.diagnostics_summary.accepted_context_count,
            accepted_proper_coarse_event_count=0,
            accepted_shared_event_proposal_count=0,
            accepted_proper_coarse_structural_proposal_count=0,
            accepted_incomparable_proper_coarse_proposal_count=0,
            equal_context_pair_count=relation_counts["equal"],
            left_refines_right_count=relation_counts["left_refines_right"],
            right_refines_left_count=relation_counts["right_refines_left"],
            incomparable_context_pair_count=relation_counts["incomparable"],
            disjoint_or_unaligned_context_pair_count=relation_counts[
                "disjoint_or_unaligned"
            ],
            median_accepted_proposal_support=None,
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
                "export_bundle": merged_bundle_relpath,
                "discovered_context_family": family_path,
                "context_pair_structure": repo_relative_path(
                    point_pair_path, root=root
                ),
            },
            notes=notes + ["no_nontrivial_multi_context_structure"],
        )
        return _PointArtifacts(row=row, context_pair_rows=context_pair_rows)

    package_artifacts = write_package_build_report(
        family_path=root / family_path,
        run_paths=[],
        pica_bundle_path=merged_bundle_relpath,
        skeleton_path=None if skeleton_path is None else root / skeleton_path,
        category=category,
        label=f"{search.search_id}-{point.point_id}-package",
        seed=point.seed_list[0],
        timestamp=timestamp,
        root=root,
        command=[
            sys.executable,
            "-m",
            "sixbirds_event",
            "substrates",
            "build-event-package",
            family_path,
            "--pica-bundle",
            merged_bundle_relpath,
            "--event-algebra-mode",
            search.event_generation_thresholds.event_algebra_mode or "auto",
            "--inference-mode",
            search.shared_event_inference_thresholds.inference_mode,
        ],
        thresholds=search.shared_event_inference_thresholds,
        event_thresholds=search.event_generation_thresholds,
    )
    candidates_model = load_model(
        root / package_artifacts.candidates_path, kind="shared-event-candidates"
    )
    assert isinstance(candidates_model, SharedEventCandidates)
    run_ids["package_build"] = package_artifacts.run_id

    provenance_artifacts = write_provenance_audit_report(
        package_path=root / package_artifacts.event_package_path,
        provenance_path=root / package_artifacts.provenance_path,
        category=category,
        label=f"{search.search_id}-{point.point_id}-provenance",
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
    run_ids["provenance_audit"] = provenance_artifacts.run_id

    stat_trace = _derive_pica_stat_trace(
        family=family,
        resolved=resolved_bundle,
        instance_id=package_artifacts.event_package.instance_id,
        instance_artifact=package_artifacts.event_package_path,
        trace_id=f"trace_{search.search_id}_{point.point_id}_stat",
    )
    stat_trace_path = derived_dir / f"{point.point_id}-stat.json"
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
        label=f"{search.search_id}-{point.point_id}-baseline-statistical",
        seed=point.seed_list[0],
        timestamp=timestamp,
        root=root,
        include_soft=False,
        command=[
            sys.executable,
            "-m",
            "sixbirds_event",
            "search",
            "pica-closure-diverse-baseline-statistical",
            stat_trace_relpath,
        ],
    )
    candidate_statistical = write_statistical_summary(
        package_artifacts.event_package,
        [stat_trace],
        instance_path=package_artifacts.event_package_path,
        trace_paths=[stat_trace_relpath],
        category=category,
        label=f"{search.search_id}-{point.point_id}-candidate-statistical",
        seed=point.seed_list[0],
        timestamp=timestamp,
        root=root,
        include_soft=True,
        command=[
            sys.executable,
            "-m",
            "sixbirds_event",
            "search",
            "pica-closure-diverse-candidate-statistical",
            stat_trace_relpath,
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
        gpd_str_status=baseline_gpd_str_status,
        gpd_str=baseline_gpd_str,
        gpd_str_reason=baseline_gpd_str_reason,
        gpd_stat_status="solved" if baseline_statistical.result.solved else "unsolved",
        gpd_stat=baseline_statistical.result.gpd_stat,
        gpd_stat_reason=baseline_statistical.result.reason,
    )
    all_accepted_proposals = TargetedSearchEvaluation(
        exact_structural_status=(
            "feasible" if all_proposals_exact.feasible else "infeasible"
        ),
        exact_feasible=all_proposals_exact.feasible,
        exact_respecting_tuple_count=all_proposals_exact.respecting_tuple_count,
        gpd_str_status=candidate_gpd_str_status,
        gpd_str=candidate_gpd_str,
        gpd_str_reason=candidate_gpd_str_reason,
        gpd_stat_status="solved" if candidate_statistical.result.solved else "unsolved",
        gpd_stat=candidate_statistical.result.gpd_stat,
        gpd_stat_reason=candidate_statistical.result.reason,
    )
    sec_status, sec_mean = _sec_summary(candidates_model)
    relation_lookup = {
        tuple(sorted((row.left.context_id, row.right.context_id))): row.relation_type
        for row in context_pair_rows
    }
    accepted_proper_coarse_structural_proposal_count = sum(
        1
        for row in candidates_model.candidate_rows
        if row.accepted and (row.left_is_proper_coarse or row.right_is_proper_coarse)
    )
    accepted_incomparable_proper_coarse_proposal_count = sum(
        1
        for row in candidates_model.candidate_rows
        if row.accepted
        and (row.left_is_proper_coarse or row.right_is_proper_coarse)
        and relation_lookup.get(
            tuple(sorted((row.left_context_id, row.right_context_id)))
        )
        == "incomparable"
    )
    support_values = _proposal_support(candidates_model)
    row = PicaClosureDiverseSearchRow(
        row_format_version="pica-closure-diverse-search-row.v1",
        search_id=search.search_id,
        point_id=point.point_id,
        source_pica_campaign_config_path=point.pilot_config_artifact,
        projection_family_ids=list(point.projection_family_ids),
        preparation_id=point.preparation_id,
        protocol_id=point.protocol_id,
        trajectories=point.trajectories,
        seed_list=point.seed_list,
        produced_export_bundle_path=merged_bundle_relpath,
        discovered_context_family_path=family_path,
        event_package_path=package_artifacts.event_package_path,
        provenance_classification=provenance_artifacts.result.admissibility_classification,
        accepted_context_count=family.diagnostics_summary.accepted_context_count,
        accepted_proper_coarse_event_count=package_artifacts.discovered_event_family.diagnostics_summary.accepted_coarse_event_count,
        accepted_shared_event_proposal_count=len(
            package_artifacts.event_package.equality_proposals
        ),
        accepted_proper_coarse_structural_proposal_count=accepted_proper_coarse_structural_proposal_count,
        accepted_incomparable_proper_coarse_proposal_count=accepted_incomparable_proper_coarse_proposal_count,
        equal_context_pair_count=relation_counts["equal"],
        left_refines_right_count=relation_counts["left_refines_right"],
        right_refines_left_count=relation_counts["right_refines_left"],
        incomparable_context_pair_count=relation_counts["incomparable"],
        disjoint_or_unaligned_context_pair_count=relation_counts[
            "disjoint_or_unaligned"
        ],
        median_accepted_proposal_support=(
            float(statistics.median(support_values)) if support_values else None
        ),
        baseline_hard_only=baseline_hard_only,
        all_accepted_proposals=all_accepted_proposals,
        ccd_status="not_applicable",
        ccd_overall=None,
        sec_status=sec_status,
        sec_mean=sec_mean,
        rm_status="not_applicable",
        rm_overall=None,
        candidate_classification="inconclusive",
        run_ids=run_ids,
        artifact_paths={
            "export_bundle": merged_bundle_relpath,
            "discovered_context_family": family_path,
            "context_pair_structure": repo_relative_path(point_pair_path, root=root),
            "event_package": package_artifacts.event_package_path,
            "package_provenance": package_artifacts.provenance_path,
            "shared_event_candidates": package_artifacts.candidates_path,
            "package_build_summary": package_artifacts.summary_path,
            "provenance_summary": provenance_artifacts.summary_path,
            "baseline_statistical_summary": baseline_statistical.summary_path,
            "candidate_statistical_summary": candidate_statistical.summary_path,
            "stat_trace": stat_trace_relpath,
        },
        notes=notes
        + [
            "ccd_not_applicable_without_repeated_read_trace",
            "rm_not_applicable_without_route_observations",
        ],
    )
    classified = row.model_copy(
        update={
            "candidate_classification": _candidate_classification(
                row=row,
                search=search,
                blocking_classification=(
                    "no_respecting_tuples"
                    if all_proposals_exact.reason == "no_respecting_tuples"
                    else all_proposals_exact.reason
                ),
            )
        }
    )
    return _PointArtifacts(row=classified, context_pair_rows=context_pair_rows)


def _render_note(
    *,
    search: PicaClosureDiverseSearch,
    table: PicaClosureDiverseSearchTable,
    structure: ContextPairStructureTable,
    classification_counts: dict[str, int],
    adequacy: dict[str, object],
    best_candidate_id: str | None,
    outcome_kind: str,
    output_paths: dict[str, str],
) -> str:
    lines = [
        "# PICA Closure-Diverse Search",
        "",
        f"- Search ID: `{search.search_id}`",
        "",
        "## Campaign family covered",
    ]
    for row in table.rows:
        lines.append(
            f"- `{row.point_id}`: pilot_config=`{row.source_pica_campaign_config_path}`, projections=`{','.join(row.projection_family_ids)}`, bundle=`{row.produced_export_bundle_path}`, provenance=`{row.provenance_classification}`, coarse_events=`{row.accepted_proper_coarse_event_count}`, coarse_proposals=`{row.accepted_proper_coarse_structural_proposal_count}`, incomparable_pairs=`{row.incomparable_context_pair_count}`, class=`{row.candidate_classification}`"
        )
    lines.extend(
        [
            "",
            "## Projection families used",
        ]
    )
    for family in search.projection_families:
        field = family.projection.payload_key or family.projection.projection_mode
        lines.append(
            f"- `{family.projection_id}`: field=`{field}`, mode=`{family.projection.projection_mode}`"
        )
    lines.extend(
        [
            "",
            "## Closure/lens/resolution diversity summary",
            f"- Context-pair rows: `{structure.row_count}`",
            f"- Incomparable rows: `{sum(1 for row in structure.rows if row.relation_type == 'incomparable')}`",
            f"- Equal rows: `{sum(1 for row in structure.rows if row.relation_type == 'equal')}`",
            f"- Refinement rows: `{sum(1 for row in structure.rows if row.relation_type in {'left_refines_right', 'right_refines_left'})}`",
            "",
            "## Evaluation modes",
            "- Baseline hard-only mode evaluates exact feasibility and deficits using only hard constraints.",
            "- All-accepted-proposals mode evaluates exact feasibility and deficits using all accepted structural proposals.",
            "- Strong endogenous obstruction classification is allowed only in the all-accepted-proposals mode and only when an accepted proper-coarse proposal comes from an incomparable context pair.",
            "",
            "## Candidate classification counts",
        ]
    )
    for label, count in sorted(classification_counts.items()):
        lines.append(f"- `{label}`: `{count}`")
    lines.extend(
        [
            "",
            "## Adequacy floor result",
            f"- Adequate: `{adequacy['adequate']}`",
            f"- Counts: `{adequacy['counts']}`",
            f"- Checks: `{adequacy['checks']}`",
            "",
            "## Outcome",
            f"- Outcome kind: `{outcome_kind}`",
            f"- Best candidate ID: `{best_candidate_id}`",
            "",
            "## Notes",
            "- RM is diagnostic-only.",
            "- unsolved / insufficient_data / not_applicable statuses are preserved explicitly.",
            "- A bounded negative result is emitted only when the stronger closure-diverse adequacy floor is satisfied.",
            "",
            "## Artifact references",
            f"- Search CSV: `{output_paths['table_csv']}`",
            f"- Search JSON: `{output_paths['table_json']}`",
            f"- Context-pair structure: `{output_paths['context_pair_structure']}`",
            f"- Search summary: `{output_paths['summary']}`",
            f"- Result note: `{output_paths['result_note']}`",
            f"- Run manifest: `{output_paths['manifest']}`",
            f"- Outcome artifact: `{output_paths['outcome']}`",
        ]
    )
    return "\n".join(lines) + "\n"


def _build_result_note(
    *,
    run_id: str,
    table: PicaClosureDiverseSearchTable,
    structure: ContextPairStructureTable,
    classification_counts: dict[str, int],
    adequacy: dict[str, object],
    outcome_kind: str,
    best_candidate_id: str | None,
    output_paths: dict[str, str],
) -> ResultNote:
    metrics: dict[str, object] = {
        "point_count": table.row_count,
        "context_pair_row_count": structure.row_count,
        "adequacy_met": adequacy["adequate"],
        "outcome_kind": outcome_kind,
        **adequacy["counts"],
    }
    for label, count in sorted(classification_counts.items()):
        metrics[f"classification_count_{label}"] = count
    return ResultNote(
        note_format_version="result-note.v1",
        note_id=f"note_{run_id}",
        run_id=run_id,
        instance_ids=[table.search_id],
        metrics=metrics,
        interpretation=(
            "The bounded closure-diverse PICA campaign searches across multiple observable projection families and records explicit context-pair non-nestedness before classifying any endogenous obstruction candidate."
        ),
        caveats=[
            "A strong discovered candidate must include at least one accepted proper-coarse structural proposal from an incomparable context pair.",
            "If the stronger adequacy floor fails, the honest outcome is design-inadequate rather than a bounded negative obstruction result.",
        ],
        artifact_refs=output_paths,
        metadata={
            "classifier_version": PICA_CLOSURE_DIVERSE_CLASSIFIER_VERSION,
            "adequacy_version": PICA_CLOSURE_DIVERSE_ADEQUACY_VERSION,
            "best_candidate_id": best_candidate_id,
        },
    )


def run_pica_closure_diverse_search(
    *,
    search_path: str | Path,
    category: str,
    label: str | None = None,
    seed: int = 0,
    timestamp: str | None = None,
    root: str | Path | None = None,
    command: list[str] | None = None,
) -> PicaClosureDiverseArtifacts:
    repo_root = Path(root).resolve() if root is not None else None
    search = load_pica_closure_diverse_search(search_path)
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
    point_artifacts = [
        _run_point(
            point=point,
            search=search,
            projection_family_map=projection_family_map,
            category=category,
            timestamp=timestamp,
            root=effective_root,
            derived_dir=derived_dir,
        )
        for point in search.points
    ]
    rows = [artifact.row for artifact in point_artifacts]
    context_pair_rows = [
        row for artifact in point_artifacts for row in artifact.context_pair_rows
    ]
    table = PicaClosureDiverseSearchTable(
        table_format_version="pica-closure-diverse-search-results.v1",
        search_id=search.search_id,
        row_count=len(rows),
        rows=rows,
        metadata={
            "classifier_version": PICA_CLOSURE_DIVERSE_CLASSIFIER_VERSION,
            "adequacy_version": PICA_CLOSURE_DIVERSE_ADEQUACY_VERSION,
            "search_artifact": repo_relative_path(search_path, root=effective_root),
        },
    )
    structure = ContextPairStructureTable(
        structure_format_version="context-pair-structure.v1",
        search_id=search.search_id,
        row_count=len(context_pair_rows),
        rows=context_pair_rows,
        metadata={
            "search_artifact": repo_relative_path(search_path, root=effective_root),
        },
    )
    classification_counts = dict(Counter(row.candidate_classification for row in rows))
    adequacy = _evaluate_adequacy(rows=rows, search=search)
    best_candidate = _select_best_candidate(rows)

    table_csv_path = run_dir / "pica-closure-diverse-search.csv"
    table_json_path = run_dir / "pica-closure-diverse-search.json"
    structure_path = run_dir / "context-pair-structure.json"
    summary_path = run_dir / "pica-closure-diverse-summary.json"
    note_path = run_dir / "pica-closure-diverse-note.md"
    result_note_path = run_dir / "result-note.json"
    manifest_path = run_dir / "run-manifest.json"

    _write_csv(table_csv_path, [_row_to_csv_record(row) for row in rows])
    _write_json(table_json_path, table.model_dump(mode="json"))
    _write_json(structure_path, structure.model_dump(mode="json"))

    if best_candidate is not None:
        outcome_kind = "best_candidate"
        outcome_path = run_dir / "best-candidate.json"
        outcome_payload = {
            "search_id": search.search_id,
            "best_candidate_id": best_candidate.point_id,
            "candidate_classification": best_candidate.candidate_classification,
            "event_package_path": best_candidate.event_package_path,
            "produced_export_bundle_path": best_candidate.produced_export_bundle_path,
            "accepted_proper_coarse_structural_proposal_count": best_candidate.accepted_proper_coarse_structural_proposal_count,
            "accepted_incomparable_proper_coarse_proposal_count": best_candidate.accepted_incomparable_proper_coarse_proposal_count,
            "all_accepted_proposals": best_candidate.all_accepted_proposals.model_dump(
                mode="json"
            ),
            "provenance_classification": best_candidate.provenance_classification,
        }
    elif adequacy["adequate"]:
        outcome_kind = "negative_result"
        outcome_path = run_dir / "negative-result.json"
        outcome_payload = {
            "search_id": search.search_id,
            "adequacy_floor_met": True,
            "negative_result": True,
            "best_candidate_id": None,
            "statement": "No provenance-admissible strong endogenous discovered obstruction was found in this committed bounded closure-diverse PICA family.",
            "adequacy": adequacy,
        }
    else:
        outcome_kind = "design_inadequate"
        outcome_path = run_dir / "design-inadequate-result.json"
        outcome_payload = {
            "search_id": search.search_id,
            "adequacy_floor_met": False,
            "outcome": "design_inadequate",
            "best_candidate_id": None,
            "adequacy": adequacy,
            "statement": "The committed closure-diverse PICA campaign did not satisfy the stronger adequacy floor required for a scientifically meaningful negative result.",
        }
    _write_json(outcome_path, outcome_payload)

    output_paths = {
        "table_csv": repo_relative_path(table_csv_path, root=effective_root),
        "table_json": repo_relative_path(table_json_path, root=effective_root),
        "context_pair_structure": repo_relative_path(
            structure_path, root=effective_root
        ),
        "summary": repo_relative_path(summary_path, root=effective_root),
        "note": repo_relative_path(note_path, root=effective_root),
        "result_note": repo_relative_path(result_note_path, root=effective_root),
        "manifest": repo_relative_path(manifest_path, root=effective_root),
        "outcome": repo_relative_path(outcome_path, root=effective_root),
    }
    summary = {
        "search_id": search.search_id,
        "config_family": [point.pilot_config_artifact for point in search.points],
        "projection_families": [
            family.model_dump(mode="json") for family in search.projection_families
        ],
        "event_generation_thresholds": search.event_generation_thresholds.model_dump(
            mode="json"
        ),
        "shared_event_inference_thresholds": search.shared_event_inference_thresholds.model_dump(
            mode="json"
        ),
        "candidate_classification_thresholds": search.candidate_classification_thresholds.model_dump(
            mode="json"
        ),
        "adequacy_floor_thresholds": search.adequacy_floor.model_dump(mode="json"),
        "adequacy_floor_result": adequacy,
        "counts_by_candidate_class": classification_counts,
        "incomparable_context_pair_count": sum(
            1 for row in structure.rows if row.relation_type == "incomparable"
        ),
        "best_candidate_id": None
        if best_candidate is None
        else best_candidate.point_id,
        "negative_result": outcome_kind == "negative_result",
        "design_inadequate": outcome_kind == "design_inadequate",
        "outcome_kind": outcome_kind,
        "paths": output_paths,
    }
    _write_json(summary_path, summary)
    note_path.write_text(
        _render_note(
            search=search,
            table=table,
            structure=structure,
            classification_counts=classification_counts,
            adequacy=adequacy,
            best_candidate_id=None
            if best_candidate is None
            else best_candidate.point_id,
            outcome_kind=outcome_kind,
            output_paths=output_paths,
        ),
        encoding="utf-8",
    )
    result_note = _build_result_note(
        run_id=run_id,
        table=table,
        structure=structure,
        classification_counts=classification_counts,
        adequacy=adequacy,
        outcome_kind=outcome_kind,
        best_candidate_id=None if best_candidate is None else best_candidate.point_id,
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
            "run-pica-closure-diverse",
            repo_relative_path(search_path, root=effective_root),
        ],
        seed=seed,
        input_artifacts={
            "search_config": repo_relative_path(search_path, root=effective_root)
        },
        output_artifacts={
            "table_csv": output_paths["table_csv"],
            "table_json": output_paths["table_json"],
            "context_pair_structure": output_paths["context_pair_structure"],
            "summary": output_paths["summary"],
            "note": output_paths["note"],
            "result_note": output_paths["result_note"],
            outcome_kind: output_paths["outcome"],
        },
        status="succeeded",
        git_commit=detect_git_commit(root=effective_root),
        metadata={
            "analysis_kind": "pica_closure_diverse_search",
            "outcome_kind": outcome_kind,
            "adequacy_met": adequacy["adequate"],
        },
    )
    write_run_manifest(manifest, run_dir=run_dir)

    return PicaClosureDiverseArtifacts(
        run_id=run_id,
        run_dir=repo_relative_path(run_dir, root=effective_root),
        table_csv_path=output_paths["table_csv"],
        table_json_path=output_paths["table_json"],
        context_pair_structure_path=output_paths["context_pair_structure"],
        summary_path=output_paths["summary"],
        note_path=output_paths["note"],
        result_note_path=output_paths["result_note"],
        manifest_path=output_paths["manifest"],
        table=table,
        context_pair_structure=structure,
        classification_counts=classification_counts,
        outcome_path=output_paths["outcome"],
        outcome_kind=outcome_kind,
    )
