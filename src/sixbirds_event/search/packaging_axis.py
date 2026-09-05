from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import json
from itertools import combinations
from pathlib import Path
import sys

from ..audits.models import QuotientFeasibilityAudit, QuotientSameSliceSelection
from ..audits.quotient_feasibility import run_quotient_feasibility_audit
from ..discovery.context_discovery import build_event_package_skeleton
from ..discovery.models import (
    AcceptedContext,
    DiscoverySummary,
    DiscoveredContextFamily,
    PicaContextDiscoveryConfig,
    PicaContextDiscoveryThresholds,
    RejectedCandidate,
)
from ..discovery.pica_context_discovery import discover_pica_context_family
from ..pica_bridge.ingest import PicaBundleResolved, load_pica_export_bundle
from ..pica_bridge.packaging_surface import resolve_pica_packaging_surface
from ..pica_bridge.pilot import run_pica_pilot_campaign
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
from .lens_axis import (
    _accepted_support_relation_counts,
    _annotation_projection_id,
    _natural_pairing_candidate_ids,
    _not_applicable_evaluation,
    _pair_side,
    _projection_context_id,
    _source_pair_filter,
    _write_csv,
    _write_json,
)
from .models import (
    ContextPairStructureRow,
    FrozenSliceProjectionFamily,
    PackagingAxisClaimLevel,
    PackagingAxisRow,
    PackagingAxisSearch,
    PackagingAxisSearchPoint,
    PackagingAxisTable,
    PackagingFamilyAdmissibility,
    PackagingFamilyAdmissibilityRow,
    TargetedCandidateLabel,
    TargetedSearchEvaluation,
)
from .pica_closure_diverse_search import (
    _blocks_for_shared_rows,
    _context_assignment_map,
    _refines,
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


PACKAGING_AXIS_CLASSIFIER_VERSION = "packaging-axis-classifier.v1"
PACKAGING_AXIS_ADEQUACY_VERSION = "packaging-axis-adequacy-floor.v1"
PACKAGING_AXIS_STAT_EVENT_BUDGET = 200
PACKAGING_AXIS_STAT_PROPOSAL_BUDGET = 150


@dataclass(slots=True)
class PackagingAxisArtifacts:
    run_id: str
    run_dir: str
    table_csv_path: str
    table_json_path: str
    summary_path: str
    note_path: str
    packaging_family_admissibility_path: str
    package_conflict_diagnostics_path: str
    quotient_feasibility_diagnostics_path: str
    result_note_path: str
    manifest_path: str
    table: PackagingAxisTable
    classification_counts: dict[str, int]
    quotient_witness_counts: dict[str, int]
    claim_level_counts: dict[str, int]
    adequacy: dict[str, object]
    outcome_path: str
    outcome_kind: str
    best_point_id: str | None


@dataclass(slots=True)
class _PreparedRun:
    merged_bundle_relpath: str
    resolved: PicaBundleResolved
    packaging_surface_summary_path: str
    packaging_source_index_path: str
    selected_operator_ids: set[str]
    selected_family_ids: set[str]
    selected_sources: set[str]
    support_slice_count: int
    run_ids: dict[str, str]
    exact_selected_branch_by_context: dict[tuple[str, ...], "_PackagingBranch"]
    default_selected_branch_by_slice: dict[tuple[str, ...], "_PackagingBranch"]


@dataclass(frozen=True, slots=True)
class _PackagingBranch:
    selector_branch_outcome: str
    packaging_operator_id: str
    packaging_family_id: str
    packaging_source: str


@dataclass(slots=True)
class _MergePoint:
    point_id: str
    seed_list: list[int]


def load_packaging_axis_search(path: str | Path) -> PackagingAxisSearch:
    model = load_model(path, kind="packaging-axis-search")
    assert isinstance(model, PackagingAxisSearch)
    return model


def _projection_family_map(
    search: PackagingAxisSearch,
) -> dict[str, FrozenSliceProjectionFamily]:
    return {family.projection_id: family for family in search.projection_families}


def _base_discovery_config(
    *,
    bundle_artifact: str,
    projection_family: FrozenSliceProjectionFamily,
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


def _prepare_seed_config(
    *,
    base_config_path: str,
    point_id: str,
    seed: int,
) -> Path:
    base_config = _load_pilot_config(base_config_path)
    payload = _pilot_config_for_seed(
        base_config=base_config,
        base_config_path=base_config_path,
        seed=seed,
    )
    config_dir = get_repo_root() / ".cache" / "packaging-axis-search"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / f"{point_id}_seed_{seed}.json"
    _write_json(config_path, payload)
    return config_path


def _prepare_fixed_run(
    *,
    search: PackagingAxisSearch,
    category: str,
    timestamp: str | None,
    root: Path,
    derived_dir: Path,
) -> _PreparedRun:
    pilot_outputs = []
    run_ids: dict[str, str] = {}
    for seed in search.seed_list:
        config_path = _prepare_seed_config(
            base_config_path=search.fixed_pilot_config_artifact,
            point_id=search.search_id,
            seed=seed,
        )
        artifacts = run_pica_pilot_campaign(
            config_path=config_path,
            category=category,
            label=f"{search.search_id}_seed_{seed}",
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
        run_ids[f"pilot_seed_{seed}"] = artifacts.run_id
    merged_bundle_relpath = _merge_pilot_outputs(
        point=_MergePoint(point_id=search.search_id, seed_list=list(search.seed_list)),
        preparation_id=search.preparation_id,
        protocol_id=search.protocol_id,
        pilot_outputs=pilot_outputs,
        output_dir=derived_dir / "merged_bundle",
        root=root,
    )
    resolved = load_pica_export_bundle(merged_bundle_relpath, repo_root=root)
    resolved_surface = resolve_pica_packaging_surface(
        merged_bundle_relpath, repo_root=root
    )
    packaging_summary_path = derived_dir / "packaging-surface-summary.json"
    packaging_source_index_path = derived_dir / "packaging-source-index.json"
    _write_json(
        packaging_summary_path, resolved_surface.surface.model_dump(mode="json")
    )
    _write_json(packaging_source_index_path, resolved_surface.source_index)

    exact_selected_branch_by_context: dict[tuple[str, ...], _PackagingBranch] = {}
    default_selected_branch_by_slice: dict[tuple[str, ...], _PackagingBranch] = {}
    for ledger in resolved.packaging_selection_ledgers.values():
        for row in ledger.rows:
            if row.selection_status != "selected":
                continue
            branch = _PackagingBranch(
                selector_branch_outcome="selected_packaging_branch",
                packaging_operator_id=row.packaging_operator_id,
                packaging_family_id=row.packaging_family_id,
                packaging_source=row.packaging_source,
            )
            exact_key = (
                row.run_id,
                row.preparation_id,
                row.protocol_id,
                row.protocol_step_id,
                str(row.step_index),
                row.resolution_id,
                row.closure_id,
                row.lens_id or "",
            )
            exact_selected_branch_by_context[exact_key] = branch
            slice_key = exact_key[:6]
            default_selected_branch_by_slice.setdefault(slice_key, branch)

    return _PreparedRun(
        merged_bundle_relpath=merged_bundle_relpath,
        resolved=resolved,
        packaging_surface_summary_path=repo_relative_path(
            packaging_summary_path, root=root
        ),
        packaging_source_index_path=repo_relative_path(
            packaging_source_index_path, root=root
        ),
        selected_operator_ids=set(
            resolved_surface.source_index["selected_operator_counts"]
        ),
        selected_family_ids=set(
            resolved_surface.source_index["selected_family_counts"]
        ),
        selected_sources=set(resolved_surface.source_index["source_counts"]),
        support_slice_count=resolved_surface.surface.support_slice_count,
        run_ids=run_ids,
        exact_selected_branch_by_context=exact_selected_branch_by_context,
        default_selected_branch_by_slice=default_selected_branch_by_slice,
    )


def _is_selected_slice(
    *,
    point: PackagingAxisSearchPoint,
    protocol_step_id: str,
    step_index: int,
    resolution_id: str,
) -> bool:
    return (
        protocol_step_id in point.selected_protocol_step_ids
        and step_index in point.selected_step_indices
        and resolution_id in point.selected_resolution_ids
    )


def _discover_family(
    *,
    search: PackagingAxisSearch,
    point: PackagingAxisSearchPoint,
    resolved: PicaBundleResolved,
    bundle_artifact: str,
    projection_families: list[FrozenSliceProjectionFamily],
    output_dir: Path,
    root: Path,
) -> tuple[str, str | None, DiscoveredContextFamily]:
    accepted_contexts: list[AcceptedContext] = []
    rejected_candidates: list[RejectedCandidate] = []
    rejection_reason_counts: Counter[str] = Counter()
    projection_fields: list[str] = []

    for projection_family in projection_families:
        projection_fields.append(projection_family.source_field)
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
            resolution_id = context.candidate_key.resolution_id or ""
            if not _is_selected_slice(
                point=point,
                protocol_step_id=context.candidate_key.protocol_step_id or "",
                step_index=context.candidate_key.step_index,
                resolution_id=resolution_id,
            ):
                continue
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
            resolution_id = candidate.candidate_key.resolution_id or ""
            if not _is_selected_slice(
                point=point,
                protocol_step_id=candidate.candidate_key.protocol_step_id or "",
                step_index=candidate.candidate_key.step_index,
                resolution_id=resolution_id,
            ):
                continue
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
        family_id=f"{point.point_id}_packaging_axis_contexts",
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
            "axis": "packaging",
            "fixed_mechanism_label": search.fixed_mechanism_label,
            "fixed_lens_label": search.fixed_lens_label,
            "projection_family_ids": [
                family.projection_id for family in projection_families
            ],
            "projection_fields": sorted(set(projection_fields)),
            "selected_protocol_step_ids": point.selected_protocol_step_ids,
            "selected_step_indices": [
                str(value) for value in point.selected_step_indices
            ],
            "selected_resolution_ids": point.selected_resolution_ids,
            "allow_cross_resolution_pairs": point.allow_cross_resolution_pairs,
        },
    )
    skeleton = build_event_package_skeleton(family, created_at="2026-03-30T00:00:00Z")

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


def _context_packaging_branch(
    context: AcceptedContext, *, prepared_run: _PreparedRun
) -> _PackagingBranch:
    source = context.source_metadata
    if source is None:
        return _PackagingBranch(
            selector_branch_outcome="untracked_support_branch",
            packaging_operator_id="untracked_support_branch",
            packaging_family_id="untracked_support_branch",
            packaging_source="untracked_support_branch",
        )
    exact_key = (
        source.run_ids[0],
        source.preparation_id,
        source.protocol_id,
        source.protocol_step_id,
        str(source.step_index),
        source.resolution_id,
        source.closure_id,
        source.lens_id,
    )
    exact = prepared_run.exact_selected_branch_by_context.get(exact_key)
    if exact is not None:
        return exact
    slice_key = exact_key[:6]
    default = prepared_run.default_selected_branch_by_slice.get(slice_key)
    if default is not None:
        return _PackagingBranch(
            selector_branch_outcome="pre_selector_branch",
            packaging_operator_id=default.packaging_operator_id,
            packaging_family_id=default.packaging_family_id,
            packaging_source=default.packaging_source,
        )
    return _PackagingBranch(
        selector_branch_outcome="untracked_support_branch",
        packaging_operator_id="untracked_support_branch",
        packaging_family_id="untracked_support_branch",
        packaging_source="untracked_support_branch",
    )


def _build_packaging_family_admissibility(
    *,
    search: PackagingAxisSearch,
    prepared_run: _PreparedRun,
) -> PackagingFamilyAdmissibility:
    operator_id = (
        sorted(prepared_run.selected_operator_ids)[0]
        if prepared_run.selected_operator_ids
        else "untracked_support_branch"
    )
    family_id = (
        sorted(prepared_run.selected_family_ids)[0]
        if prepared_run.selected_family_ids
        else "untracked_support_branch"
    )
    source_id = (
        sorted(prepared_run.selected_sources)[0]
        if prepared_run.selected_sources
        else "untracked_support_branch"
    )
    rows = [
        PackagingFamilyAdmissibilityRow(
            packaging_operator_id=operator_id,
            packaging_family_id=family_id,
            packaging_source=source_id,
            selector_branch_outcome="selected_packaging_branch",
            same_support_eligible=True,
            allowed_roles=["primary_context_pair", "probe_only"],
            allowed_role="primary_context_pair",
            notes=["selected_branch_observed_in_packaging_selection_ledger"],
            flags=["same_support_eligible", "selector_branch_observed"],
        ),
        PackagingFamilyAdmissibilityRow(
            packaging_operator_id=operator_id,
            packaging_family_id=family_id,
            packaging_source=source_id,
            selector_branch_outcome="pre_selector_branch",
            same_support_eligible=True,
            allowed_roles=["primary_context_pair", "probe_only"],
            allowed_role="primary_context_pair",
            notes=[
                "pre_selector_branch_inferred_from_same_support_contexts_without_selected_packaging_surface_match"
            ],
            flags=["same_support_eligible", "selector_branch_inferred"],
        ),
    ]
    return PackagingFamilyAdmissibility(
        catalog_format_version="packaging-family-admissibility.v1",
        search_id=search.search_id,
        fixed_mechanism_label=search.fixed_mechanism_label,
        fixed_lens_label=search.fixed_lens_label,
        row_count=len(rows),
        rows=rows,
        metadata={"axis": "packaging"},
    )


def _context_pair_rows(
    *,
    point: PackagingAxisSearchPoint,
    resolved: PicaBundleResolved,
    family: DiscoveredContextFamily,
    projection_family_map: dict[str, FrozenSliceProjectionFamily],
    prepared_run: _PreparedRun,
) -> list[ContextPairStructureRow]:
    assignments = {
        context.context_id: _context_assignment_map(resolved=resolved, context=context)
        for context in family.accepted_contexts
    }
    branch_by_context = {
        context.context_id: _context_packaging_branch(
            context, prepared_run=prepared_run
        )
        for context in family.accepted_contexts
    }
    rows: list[ContextPairStructureRow] = []
    for left, right in combinations(family.accepted_contexts, 2):
        if (
            left.candidate_key.preparation_id != right.candidate_key.preparation_id
            or left.candidate_key.protocol_id != right.candidate_key.protocol_id
        ):
            continue
        left_source = left.source_metadata
        right_source = right.source_metadata
        if left_source is None or right_source is None:
            continue
        left_family = projection_family_map[left_source.projection_id]
        right_family = projection_family_map[right_source.projection_id]
        left_assignment = assignments[left.context_id]
        right_assignment = assignments[right.context_id]
        shared_rows = set(left_assignment) & set(right_assignment)
        same_step = (
            left.candidate_key.protocol_step_id == right.candidate_key.protocol_step_id
            and left.candidate_key.step_index == right.candidate_key.step_index
            and left.candidate_key.resolution_id == right.candidate_key.resolution_id
        )
        same_support = (
            left.candidate_key.preparation_id == right.candidate_key.preparation_id
            and left.candidate_key.protocol_id == right.candidate_key.protocol_id
            and bool(shared_rows)
        )
        both_primary = (
            "primary_context" in left_family.allowed_roles
            and "primary_context" in right_family.allowed_roles
        )
        left_branch = branch_by_context[left.context_id]
        right_branch = branch_by_context[right.context_id]
        packaging_divergent = (
            left_branch.selector_branch_outcome != right_branch.selector_branch_outcome
            or left_branch.packaging_operator_id != right_branch.packaging_operator_id
            or left_branch.packaging_family_id != right_branch.packaging_family_id
            or left_branch.packaging_source != right_branch.packaging_source
        )
        allow_primary = same_step or point.allow_cross_resolution_pairs
        primary_packaging_conflict_admissible = (
            same_support and both_primary and packaging_divergent and allow_primary
        )
        primary_identity_admissible = same_support and both_primary and allow_primary
        if not shared_rows:
            relation_type = "disjoint_or_unaligned"
            notes = ["no_shared_rows"]
            flags: list[str] = []
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
        if not same_step:
            flags.append("cross_resolution")
        if packaging_divergent:
            flags.append("packaging_divergent")
        if left_branch.selector_branch_outcome != right_branch.selector_branch_outcome:
            flags.append("selector_branch_change")
        if primary_packaging_conflict_admissible:
            admissibility_reason = (
                "same_support_packaging_divergent_pair"
                if same_step
                else "same_support_cross_resolution_packaging_strict_extension"
            )
            admissibility_class = "primary_packaging_conflict"
        elif not same_support:
            admissibility_reason = "not_same_support"
            admissibility_class = "diagnostic_only"
        elif not both_primary:
            admissibility_reason = "projection_family_not_primary_context"
            admissibility_class = "diagnostic_only"
        elif not packaging_divergent:
            admissibility_reason = "not_packaging_divergent"
            admissibility_class = "probe_only"
        else:
            admissibility_reason = "cross_resolution_pairs_disabled"
            admissibility_class = "probe_only"
        notes.extend(
            [
                f"left_selector_branch={left_branch.selector_branch_outcome}",
                f"right_selector_branch={right_branch.selector_branch_outcome}",
                f"left_packaging_family={left_branch.packaging_family_id}",
                f"right_packaging_family={right_branch.packaging_family_id}",
            ]
        )
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
                same_frozen_slice=same_step and same_support,
                primary_identity_admissible=primary_identity_admissible,
                packaging_conflict_supported=packaging_divergent,
                primary_packaging_conflict_admissible=primary_packaging_conflict_admissible,
                packaging_conflict_admissibility_class=admissibility_class,
                admissibility_reason=admissibility_reason,
                notes=notes,
                flags=flags,
            )
        )
    return rows


def _accepted_packaging_divergent_counts(
    *,
    candidates_model,
    primary_pairs: set[tuple[str, str]],
) -> tuple[int, int]:
    accepted_count = 0
    accepted_coarse_count = 0
    for candidate in candidates_model.candidate_rows:
        pair_key = tuple(
            sorted((candidate.left_context_id, candidate.right_context_id))
        )
        if not candidate.accepted or pair_key not in primary_pairs:
            continue
        accepted_count += 1
        if candidate.left_is_proper_coarse or candidate.right_is_proper_coarse:
            accepted_coarse_count += 1
    return accepted_count, accepted_coarse_count


def _candidate_classification(
    *,
    row: PackagingAxisRow,
    search: PackagingAxisSearch,
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

    if (
        provenance_ok
        and row.accepted_packaging_divergent_proper_coarse_proposal_count
        >= search.candidate_classification_thresholds.min_accepted_coarse_proposal_count
        and row.accepted_packaging_divergent_proposal_count >= 1
        and row.same_support_packaging_divergent_pair_count >= 1
        and row.quotient_witness_status == "accepted_proposal_obstruction"
        and (
            positive_candidate_deficit
            or row.all_accepted_proposals.exact_feasible is False
        )
    ):
        return "strongly_nonextendable_candidate"

    if (
        provenance_ok
        and row.all_accepted_proposals.exact_feasible is True
        and row.all_accepted_proposals.gpd_str == 0
        and row.quotient_witness_status == "no_quotient_obstruction"
    ):
        return "extendable_candidate"

    if some_provenance and (
        row.quotient_witness_status
        in {
            "accepted_proposal_obstruction",
            "candidate_subset_quotient_witness",
        }
        or row.all_accepted_proposals.exact_feasible is False
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


_CLAIM_ORDER: dict[PackagingAxisClaimLevel, int] = {
    "nontrivial_multicontext_structure": 0,
    "same_support_packaging_change": 1,
    "packaging_conflict_tension": 2,
    "provenance_admissible_packaging_obstruction": 3,
}


def _bounded_claim_level(
    claim: PackagingAxisClaimLevel,
    *,
    ceiling: PackagingAxisClaimLevel,
) -> PackagingAxisClaimLevel:
    max_rank = _CLAIM_ORDER[ceiling]
    allowed = [name for name, rank in _CLAIM_ORDER.items() if rank <= max_rank]
    return (
        sorted(allowed, key=lambda name: _CLAIM_ORDER[name])[-1]
        if _CLAIM_ORDER[claim] > max_rank
        else claim
    )


def _claim_level(
    *, row: PackagingAxisRow, search: PackagingAxisSearch
) -> PackagingAxisClaimLevel:
    if row.candidate_classification == "strongly_nonextendable_candidate":
        claim = "provenance_admissible_packaging_obstruction"
    elif (
        row.quotient_witness_status
        in {
            "accepted_proposal_obstruction",
            "candidate_subset_quotient_witness",
        }
        or row.candidate_classification == "weakly_frustrated_candidate"
    ):
        claim = "packaging_conflict_tension"
    elif row.same_support_packaging_divergent_pair_count > 0:
        claim = "same_support_packaging_change"
    else:
        claim = "nontrivial_multicontext_structure"
    return _bounded_claim_level(claim, ceiling=search.claim_ceiling)


def _row_to_csv_record(row: PackagingAxisRow) -> dict[str, object]:
    return {
        "point_id": row.point_id,
        "candidate_classification": row.candidate_classification,
        "claim_level_supported": row.claim_level_supported,
        "provenance_classification": row.provenance_classification,
        "accepted_context_count": row.accepted_context_count,
        "accepted_proper_coarse_event_count": row.accepted_proper_coarse_event_count,
        "accepted_packaging_divergent_proposal_count": row.accepted_packaging_divergent_proposal_count,
        "accepted_packaging_divergent_proper_coarse_proposal_count": row.accepted_packaging_divergent_proper_coarse_proposal_count,
        "same_support_packaging_divergent_pair_count": row.same_support_packaging_divergent_pair_count,
        "same_step_packaging_divergent_pair_count": row.same_step_packaging_divergent_pair_count,
        "cross_resolution_packaging_divergent_pair_count": row.cross_resolution_packaging_divergent_pair_count,
        "baseline_exact_feasible": row.baseline_hard_only.exact_feasible,
        "candidate_exact_feasible": row.all_accepted_proposals.exact_feasible,
        "baseline_gpd_str": row.baseline_hard_only.gpd_str,
        "candidate_gpd_str": row.all_accepted_proposals.gpd_str,
        "quotient_class_count": row.quotient_class_count,
        "quotient_accepted_only_survivor_count": row.quotient_accepted_only_survivor_count,
        "quotient_natural_pairing_survivor_count": row.quotient_natural_pairing_survivor_count,
        "quotient_witness_status": row.quotient_witness_status,
        "selected_packaging_sources": json.dumps(row.selected_packaging_sources),
        "selected_packaging_operator_count": row.selected_packaging_operator_count,
        "selected_packaging_family_count": row.selected_packaging_family_count,
        "selector_branch_outcome_counts": json.dumps(
            row.selector_branch_outcome_counts, sort_keys=True
        ),
        "support_relation_kind_counts": json.dumps(
            row.support_relation_kind_counts, sort_keys=True
        ),
    }


def _evaluate_adequacy(
    rows: list[PackagingAxisRow], search: PackagingAxisSearch
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
        "points_with_accepted_proper_coarse_structural_proposals": sum(
            1
            for row in rows
            if row.accepted_packaging_divergent_proper_coarse_proposal_count > 0
        ),
        "points_with_same_support_packaging_divergent_pairs": sum(
            1 for row in rows if row.same_support_packaging_divergent_pair_count > 0
        ),
        "points_with_dual_mode_difference": sum(
            1 for row in rows if _point_has_dual_mode_difference(row)
        ),
        "points_with_nontrivial_quotient_result_recorded": sum(
            1 for row in rows if row.quotient_witness_status is not None
        ),
    }
    floor = search.adequacy_floor
    checks = {
        "total_point_count": counts["total_point_count"] >= floor.min_total_point_count,
        "admissible_built_package_count": counts["admissible_built_package_count"]
        >= floor.min_admissible_built_package_count,
        "points_with_proper_coarse_events": counts["points_with_proper_coarse_events"]
        >= floor.min_points_with_proper_coarse_events,
        "points_with_accepted_proper_coarse_structural_proposals": counts[
            "points_with_accepted_proper_coarse_structural_proposals"
        ]
        >= floor.min_points_with_accepted_proper_coarse_structural_proposals,
        "points_with_same_support_packaging_divergent_pairs": counts[
            "points_with_same_support_packaging_divergent_pairs"
        ]
        >= floor.min_points_with_same_support_packaging_divergent_pairs,
        "points_with_dual_mode_difference": counts["points_with_dual_mode_difference"]
        >= floor.min_points_with_dual_mode_difference,
        "points_with_nontrivial_quotient_result_recorded": counts[
            "points_with_nontrivial_quotient_result_recorded"
        ]
        >= floor.min_points_with_nontrivial_quotient_result_recorded,
    }
    thresholds = {
        "min_total_point_count": floor.min_total_point_count,
        "min_admissible_built_package_count": floor.min_admissible_built_package_count,
        "min_points_with_proper_coarse_events": floor.min_points_with_proper_coarse_events,
        "min_points_with_accepted_proper_coarse_structural_proposals": floor.min_points_with_accepted_proper_coarse_structural_proposals,
        "min_points_with_same_support_packaging_divergent_pairs": floor.min_points_with_same_support_packaging_divergent_pairs,
        "min_points_with_dual_mode_difference": floor.min_points_with_dual_mode_difference,
        "min_points_with_nontrivial_quotient_result_recorded": floor.min_points_with_nontrivial_quotient_result_recorded,
    }
    return {
        "adequate": all(checks.values()),
        "checks": checks,
        "counts": counts,
        "thresholds": thresholds,
    }


def _best_point(rows: list[PackagingAxisRow]) -> PackagingAxisRow | None:
    candidates = [
        row
        for row in rows
        if row.candidate_classification == "strongly_nonextendable_candidate"
    ]
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda row: (
            row.all_accepted_proposals.gpd_str or 0.0,
            row.accepted_packaging_divergent_proper_coarse_proposal_count,
            row.same_support_packaging_divergent_pair_count,
        ),
    )


def _build_summary(
    *,
    search: PackagingAxisSearch,
    rows: list[PackagingAxisRow],
    adequacy: dict[str, object],
    classification_counts: dict[str, int],
    quotient_witness_counts: dict[str, int],
    claim_level_counts: dict[str, int],
    best_point: PackagingAxisRow | None,
    output_paths: dict[str, str],
    outcome_kind: str,
) -> dict[str, object]:
    return {
        "search_id": search.search_id,
        "fixed_mechanism_configuration_refs": {
            "pilot_config_artifact": search.fixed_pilot_config_artifact,
            "fixed_mechanism_label": search.fixed_mechanism_label,
            "preparation_id": search.preparation_id,
            "protocol_id": search.protocol_id,
        },
        "fixed_lens_projection_refs": {
            "fixed_lens_label": search.fixed_lens_label,
            "fixed_projection_family_ids": list(search.fixed_projection_family_ids),
        },
        "packaging_surface_summary": {
            "selected_packaging_sources": sorted(
                {source for row in rows for source in row.selected_packaging_sources}
            ),
            "selected_packaging_operator_count": max(
                (row.selected_packaging_operator_count for row in rows), default=0
            ),
            "selected_packaging_family_count": max(
                (row.selected_packaging_family_count for row in rows), default=0
            ),
            "selector_branch_outcome_counts": dict(
                sorted(
                    Counter(
                        key
                        for row in rows
                        for key, value in row.selector_branch_outcome_counts.items()
                        for _ in range(value)
                    ).items()
                )
            ),
            "points_with_cross_resolution_packaging_pairs": [
                row.point_id
                for row in rows
                if row.cross_resolution_packaging_divergent_pair_count > 0
            ],
        },
        "adequacy_floor_thresholds": adequacy["thresholds"],
        "adequacy_floor_result": {
            "adequate": adequacy["adequate"],
            "checks": adequacy["checks"],
            "counts": adequacy["counts"],
        },
        "counts_by_candidate_class": classification_counts,
        "counts_by_quotient_witness_status": quotient_witness_counts,
        "counts_by_claim_level": claim_level_counts,
        "best_point_id": None if best_point is None else best_point.point_id,
        "negative_result": outcome_kind == "negative_result",
        "design_inadequate": outcome_kind == "design_inadequate",
        "claim_level_note": "Packaging-axis findings hold mechanism and primary lens fixed while varying packaging branch/operator/family identity on the same support object, then evaluate quotient-backed global realization under the current admissibility rules.",
        "output_paths": output_paths,
    }


def _render_note(
    *,
    search: PackagingAxisSearch,
    rows: list[PackagingAxisRow],
    adequacy: dict[str, object],
    classification_counts: dict[str, int],
    quotient_witness_counts: dict[str, int],
    claim_level_counts: dict[str, int],
    best_point: PackagingAxisRow | None,
    output_paths: dict[str, str],
    outcome_kind: str,
) -> str:
    lines = [
        "# Packaging-Axis Search",
        "",
        f"- Search ID: `{search.search_id}`",
        f"- Fixed mechanism/configuration: `{search.fixed_mechanism_label}` via `{search.fixed_pilot_config_artifact}`",
        f"- Fixed lens/projection family: `{search.fixed_lens_label}` using `{', '.join(search.fixed_projection_family_ids)}`",
        f"- Same-support rule: preparation=`{search.preparation_id}`, protocol=`{search.protocol_id}`",
        "- Varied at the packaging level:",
    ]
    for point in search.points:
        lines.append(
            f"  - `{point.point_id}`: step_ids=`{','.join(point.selected_protocol_step_ids)}`, step_indices=`{','.join(str(v) for v in point.selected_step_indices)}`, resolution_ids=`{','.join(point.selected_resolution_ids)}`, allow_cross_resolution_pairs=`{point.allow_cross_resolution_pairs}`"
        )
    lines.extend(["", "## Baseline vs all-accepted-proposals"])
    for row in rows:
        lines.append(
            f"- `{row.point_id}`: baseline_exact=`{row.baseline_hard_only.exact_feasible}`, candidate_exact=`{row.all_accepted_proposals.exact_feasible}`, baseline_gpd_str=`{row.baseline_hard_only.gpd_str}`, candidate_gpd_str=`{row.all_accepted_proposals.gpd_str}`"
        )
    lines.extend(["", "## Quotient-feasibility comparison"])
    for row in rows:
        lines.append(
            f"- `{row.point_id}`: witness_status=`{row.quotient_witness_status}`, quotient_class_count=`{row.quotient_class_count}`, accepted_only_survivors=`{row.quotient_accepted_only_survivor_count}`, natural_pairing_survivors=`{row.quotient_natural_pairing_survivor_count}`, candidate_subset_witness_found=`{row.quotient_candidate_subset_witness_found}`"
        )
    lines.extend(["", "## Packaging-divergent pair diagnostics"])
    for row in rows:
        lines.append(
            f"- `{row.point_id}`: same_support_pairs=`{row.same_support_packaging_divergent_pair_count}`, same_step_pairs=`{row.same_step_packaging_divergent_pair_count}`, cross_resolution_pairs=`{row.cross_resolution_packaging_divergent_pair_count}`, accepted_packaging_divergent_proposals=`{row.accepted_packaging_divergent_proposal_count}`, accepted_packaging_divergent_proper_coarse_proposals=`{row.accepted_packaging_divergent_proper_coarse_proposal_count}`"
        )
    lines.extend(["", "## Counts by candidate class"])
    for label, count in sorted(classification_counts.items()):
        lines.append(f"- `{label}`: `{count}`")
    lines.extend(["", "## Counts by quotient witness status"])
    for label, count in sorted(quotient_witness_counts.items()):
        lines.append(f"- `{label}`: `{count}`")
    lines.extend(["", "## Counts by claim level"])
    for label, count in sorted(claim_level_counts.items()):
        lines.append(f"- `{label}`: `{count}`")
    lines.extend(
        [
            "",
            "## Adequacy floor",
            f"- Adequate: `{adequacy['adequate']}`",
        ]
    )
    for key, value in sorted(adequacy["checks"].items()):
        lines.append(f"- `{key}`: `{value}` (count=`{adequacy['counts'][key]}`)")
    lines.extend(
        [
            "",
            "## Outcome",
            f"- Outcome kind: `{outcome_kind}`",
            f"- Best point: `{None if best_point is None else best_point.point_id}`",
            "- RM is diagnostic-only.",
            "- Status fields such as `unsolved`, `insufficient_data`, and `not_applicable` are preserved where relevant.",
            "- Quotient-backed feasibility is the default theorem-facing exact backend for this axis; raw tuple exactness remains diagnostic only.",
            "",
            "## Artifacts",
        ]
    )
    for key, value in sorted(output_paths.items()):
        lines.append(f"- `{key}`: `{value}`")
    return "\n".join(lines) + "\n"


def _build_result_note(
    *,
    run_id: str,
    table: PackagingAxisTable,
    adequacy: dict[str, object],
    classification_counts: dict[str, int],
    quotient_witness_counts: dict[str, int],
    claim_level_counts: dict[str, int],
    output_paths: dict[str, str],
    outcome_kind: str,
    best_point: PackagingAxisRow | None,
) -> ResultNote:
    metrics: dict[str, object] = {
        "point_count": table.row_count,
        "adequacy_met": adequacy["adequate"],
        "outcome_kind": outcome_kind,
        **adequacy["counts"],
    }
    for label, count in sorted(classification_counts.items()):
        metrics[f"classification_count_{label}"] = count
    for label, count in sorted(quotient_witness_counts.items()):
        metrics[f"quotient_witness_count_{label}"] = count
    for label, count in sorted(claim_level_counts.items()):
        metrics[f"claim_level_count_{label}"] = count
    return ResultNote(
        note_format_version="result-note.v1",
        note_id=f"note_{run_id}",
        run_id=run_id,
        instance_ids=[table.search_id],
        metrics=metrics,
        interpretation=(
            "The packaging-axis search holds mechanism and primary lens fixed, varies selector-branch / packaging identity on the same support object, and evaluates global realization with the quotient-backed feasibility backend under the current admissibility rules."
        ),
        caveats=[
            "RM is diagnostic-only in this runner.",
            "Quotient witness status is theorem-facing; raw tuple exactness is retained only as a diagnostic baseline.",
        ],
        artifact_refs=output_paths,
        metadata={
            "classifier_version": PACKAGING_AXIS_CLASSIFIER_VERSION,
            "adequacy_version": PACKAGING_AXIS_ADEQUACY_VERSION,
            "best_point_id": None if best_point is None else best_point.point_id,
        },
    )


def _skip_statistical_stage(*, accepted_event_count: int, proposal_count: int) -> bool:
    return (
        accepted_event_count > PACKAGING_AXIS_STAT_EVENT_BUDGET
        or proposal_count > PACKAGING_AXIS_STAT_PROPOSAL_BUDGET
    )


def _run_point(
    *,
    search: PackagingAxisSearch,
    point: PackagingAxisSearchPoint,
    prepared_run: _PreparedRun,
    packaging_family_admissibility_path: str,
    category: str,
    timestamp: str | None,
    root: Path,
    derived_dir: Path,
) -> tuple[PackagingAxisRow, list[ContextPairStructureRow], dict[str, object]]:
    projection_family_map = _projection_family_map(search)
    projection_families = [
        projection_family_map[projection_id]
        for projection_id in search.fixed_projection_family_ids
    ]
    family_path, skeleton_path, family = _discover_family(
        search=search,
        point=point,
        resolved=prepared_run.resolved,
        bundle_artifact=prepared_run.merged_bundle_relpath,
        projection_families=projection_families,
        output_dir=derived_dir / "families",
        root=root,
    )
    artifact_paths = {
        "export_bundle": prepared_run.merged_bundle_relpath,
        "packaging_surface_summary": prepared_run.packaging_surface_summary_path,
        "packaging_source_index": prepared_run.packaging_source_index_path,
        "packaging_family_admissibility": packaging_family_admissibility_path,
        "discovered_context_family": family_path,
    }
    run_ids = dict(prepared_run.run_ids)
    if family.diagnostics_summary.accepted_context_count < 2:
        row = PackagingAxisRow(
            row_format_version="packaging-axis-row.v1",
            search_id=search.search_id,
            point_id=point.point_id,
            source_pica_campaign_config_path=search.fixed_pilot_config_artifact,
            produced_export_bundle_path=prepared_run.merged_bundle_relpath,
            packaging_surface_summary_path=prepared_run.packaging_surface_summary_path,
            discovered_context_family_path=family_path,
            event_package_path=None,
            provenance_classification=None,
            fixed_mechanism_label=search.fixed_mechanism_label,
            fixed_lens_label=search.fixed_lens_label,
            fixed_projection_family_ids=list(search.fixed_projection_family_ids),
            selected_protocol_step_ids=list(point.selected_protocol_step_ids),
            selected_step_indices=list(point.selected_step_indices),
            selected_resolution_ids=list(point.selected_resolution_ids),
            accepted_context_count=family.diagnostics_summary.accepted_context_count,
            accepted_singleton_event_count=0,
            accepted_proper_coarse_event_count=0,
            accepted_shared_event_proposal_count=0,
            accepted_proper_coarse_proposal_count=0,
            accepted_packaging_divergent_proposal_count=0,
            accepted_packaging_divergent_proper_coarse_proposal_count=0,
            same_support_packaging_divergent_pair_count=0,
            same_step_packaging_divergent_pair_count=0,
            cross_resolution_packaging_divergent_pair_count=0,
            same_support_non_nested_packaging_divergent_pair_count=0,
            baseline_hard_only=_not_applicable_evaluation(),
            all_accepted_proposals=_not_applicable_evaluation(),
            quotient_class_count=None,
            quotient_accepted_only_survivor_count=None,
            quotient_accepted_only_exact_feasible=None,
            quotient_accepted_only_failure_reason=None,
            quotient_natural_pairing_survivor_count=None,
            quotient_natural_pairing_exact_feasible=None,
            quotient_candidate_subset_witness_found=None,
            quotient_candidate_subset_minimal_witness_size=None,
            quotient_witness_status=None,
            quotient_witness_candidate_ids=[],
            quotient_feasibility_summary_path=None,
            selected_packaging_sources=sorted(prepared_run.selected_sources),
            selected_packaging_operator_count=len(prepared_run.selected_operator_ids),
            selected_packaging_family_count=len(prepared_run.selected_family_ids),
            packaging_support_slice_count=prepared_run.support_slice_count,
            selector_branch_outcome_counts={},
            support_relation_kind_counts={},
            candidate_classification="trivial_or_nonrecording",
            claim_level_supported="nontrivial_multicontext_structure",
            run_ids=run_ids,
            artifact_paths=artifact_paths,
            notes=list(point.notes)
            + ["insufficient_accepted_contexts_for_package_build"],
            flags=["packaging_axis"],
        )
        return row, [], {"point_id": point.point_id, "quotient_witness_status": None}

    context_pair_rows = _context_pair_rows(
        point=point,
        resolved=prepared_run.resolved,
        family=family,
        projection_family_map=projection_family_map,
        prepared_run=prepared_run,
    )
    context_pair_path = derived_dir / f"{point.point_id}_package_conflict_pairs.json"
    _write_json(
        context_pair_path, [row.model_dump(mode="json") for row in context_pair_rows]
    )
    artifact_paths["package_conflict_pairs"] = repo_relative_path(
        context_pair_path, root=root
    )
    primary_pairs = {
        tuple(sorted((row.left.context_id, row.right.context_id)))
        for row in context_pair_rows
        if row.primary_packaging_conflict_admissible
    }
    selector_branch_outcome_counts = Counter()
    for pair in context_pair_rows:
        for note in pair.notes:
            if note.startswith("left_selector_branch="):
                selector_branch_outcome_counts[note.split("=", 1)[1]] += 1
            if note.startswith("right_selector_branch="):
                selector_branch_outcome_counts[note.split("=", 1)[1]] += 1
    same_support_packaging_divergent_pair_count = sum(
        1 for row in context_pair_rows if row.primary_packaging_conflict_admissible
    )
    same_step_packaging_divergent_pair_count = sum(
        1
        for row in context_pair_rows
        if row.primary_packaging_conflict_admissible and row.same_step
    )
    cross_resolution_packaging_divergent_pair_count = sum(
        1
        for row in context_pair_rows
        if row.primary_packaging_conflict_admissible and not row.same_step
    )
    same_support_non_nested_packaging_divergent_pair_count = sum(
        1
        for row in context_pair_rows
        if row.primary_packaging_conflict_admissible
        and row.relation_type == "incomparable"
    )
    package_artifacts = write_package_build_report(
        family_path=root / family_path,
        pica_bundle_path=root / prepared_run.merged_bundle_relpath,
        skeleton_path=root / skeleton_path if skeleton_path is not None else None,
        category=category,
        label=f"{point.point_id}_package_build",
        seed=search.seed_list[0],
        timestamp=timestamp,
        root=root,
        thresholds=search.shared_event_inference_thresholds,
        event_thresholds=search.event_generation_thresholds,
        source_pair_filter=_source_pair_filter(primary_pairs),
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
        seed=search.seed_list[0],
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
        resolved=prepared_run.resolved,
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
    skip_statistical = _skip_statistical_stage(
        accepted_event_count=len(package_artifacts.event_package.events),
        proposal_count=len(package_artifacts.event_package.equality_proposals),
    )
    baseline_statistical = None
    candidate_statistical = None
    if not skip_statistical:
        baseline_statistical = write_statistical_summary(
            package_artifacts.event_package,
            [stat_trace],
            instance_path=root / package_artifacts.event_package_path,
            trace_paths=[stat_trace_path],
            category=category,
            label=f"{point.point_id}_baseline_statistical",
            seed=search.seed_list[0],
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
            seed=search.seed_list[0],
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
        gpd_stat_status="unsolved"
        if baseline_statistical is None
        else "solved"
        if baseline_statistical.result.solved
        else "unsolved",
        gpd_stat=None
        if baseline_statistical is None
        else baseline_statistical.result.gpd_stat,
        gpd_stat_reason="packaging_axis_statistical_budget_exceeded"
        if baseline_statistical is None
        else baseline_statistical.result.reason,
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
        gpd_stat_status="unsolved"
        if candidate_statistical is None
        else "solved"
        if candidate_statistical.result.solved
        else "unsolved",
        gpd_stat=None
        if candidate_statistical is None
        else candidate_statistical.result.gpd_stat,
        gpd_stat_reason="packaging_axis_statistical_budget_exceeded"
        if candidate_statistical is None
        else candidate_statistical.result.reason,
    )
    sec_status, sec_mean = _sec_summary(package_artifacts.candidates)
    (
        accepted_packaging_divergent_proposal_count,
        (accepted_packaging_divergent_proper_coarse_proposal_count),
    ) = _accepted_packaging_divergent_counts(
        candidates_model=package_artifacts.candidates,
        primary_pairs=primary_pairs,
    )
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
            "stat_trace": stat_trace_relpath,
        }
    )
    if baseline_statistical is not None and candidate_statistical is not None:
        artifact_paths["baseline_statistical_summary"] = (
            baseline_statistical.summary_path
        )
        artifact_paths["candidate_statistical_summary"] = (
            candidate_statistical.summary_path
        )

    point_dir = derived_dir / "quotient_audits" / point.point_id
    point_dir.mkdir(parents=True, exist_ok=True)
    audit_path = point_dir / "quotient-feasibility-audit.json"
    natural_pairing_ids = (
        _natural_pairing_candidate_ids(package_artifacts.candidates)
        if search.include_natural_pairing_control
        else []
    )
    audit = QuotientFeasibilityAudit(
        audit_format_version="quotient-feasibility-audit.v1",
        audit_id=f"{search.search_id}_{point.point_id}_quotient",
        source_event_package_artifact=package_artifacts.event_package_path,
        source_discovered_context_family_artifact=family_path,
        source_shared_event_candidates_artifact=package_artifacts.candidates_path,
        source_package_provenance_artifact=package_artifacts.provenance_path,
        same_slice_selection=QuotientSameSliceSelection(
            preparation_id=search.preparation_id,
            protocol_id=search.protocol_id,
            protocol_step_id=point.selected_protocol_step_ids[0],
            step_index=point.selected_step_indices[0],
            resolution_id=point.selected_resolution_ids[0],
            candidate_event_scope="singleton_only",
        ),
        candidate_pool_mode="same_slice_candidate_pool",
        subset_search={
            "enabled": search.quotient_subset_search_enabled,
            "max_subset_size": search.quotient_max_subset_size,
            "stop_at_first_witness": search.quotient_stop_at_first_witness,
        },
        natural_pairing_candidate_ids=natural_pairing_ids,
        output_category="results",
        output_label=f"{point.point_id}_quotient_feasibility",
        metadata={"axis": "packaging"},
    )
    _write_json(audit_path, audit.model_dump(mode="json"))
    quotient_artifacts = run_quotient_feasibility_audit(
        audit_path=audit_path,
        category="results",
        label=f"{point.point_id}_quotient_feasibility",
        seed=search.seed_list[0],
        timestamp=timestamp,
        root=root,
        command=[
            sys.executable,
            "-m",
            "sixbirds_event",
            "audits",
            "quotient-feasibility",
            repo_relative_path(audit_path, root=root),
        ],
    )
    run_ids["quotient_feasibility_audit"] = quotient_artifacts.run_id
    artifact_paths["quotient_feasibility_summary"] = quotient_artifacts.summary_path
    artifact_paths["quotient_class_ledger"] = (
        quotient_artifacts.quotient_class_ledger_path
    )
    row = PackagingAxisRow(
        row_format_version="packaging-axis-row.v1",
        search_id=search.search_id,
        point_id=point.point_id,
        source_pica_campaign_config_path=search.fixed_pilot_config_artifact,
        produced_export_bundle_path=prepared_run.merged_bundle_relpath,
        packaging_surface_summary_path=prepared_run.packaging_surface_summary_path,
        discovered_context_family_path=family_path,
        event_package_path=package_artifacts.event_package_path,
        provenance_classification=provenance_artifacts.result.admissibility_classification,
        fixed_mechanism_label=search.fixed_mechanism_label,
        fixed_lens_label=search.fixed_lens_label,
        fixed_projection_family_ids=list(search.fixed_projection_family_ids),
        selected_protocol_step_ids=list(point.selected_protocol_step_ids),
        selected_step_indices=list(point.selected_step_indices),
        selected_resolution_ids=list(point.selected_resolution_ids),
        accepted_context_count=family.diagnostics_summary.accepted_context_count,
        accepted_singleton_event_count=package_artifacts.discovered_event_family.diagnostics_summary.accepted_singleton_event_count,
        accepted_proper_coarse_event_count=package_artifacts.discovered_event_family.diagnostics_summary.accepted_coarse_event_count,
        accepted_shared_event_proposal_count=len(
            package_artifacts.event_package.equality_proposals
        ),
        accepted_proper_coarse_proposal_count=accepted_proper_coarse_proposal_count,
        accepted_packaging_divergent_proposal_count=accepted_packaging_divergent_proposal_count,
        accepted_packaging_divergent_proper_coarse_proposal_count=accepted_packaging_divergent_proper_coarse_proposal_count,
        same_support_packaging_divergent_pair_count=same_support_packaging_divergent_pair_count,
        same_step_packaging_divergent_pair_count=same_step_packaging_divergent_pair_count,
        cross_resolution_packaging_divergent_pair_count=cross_resolution_packaging_divergent_pair_count,
        same_support_non_nested_packaging_divergent_pair_count=same_support_non_nested_packaging_divergent_pair_count,
        baseline_hard_only=baseline_hard_only,
        all_accepted_proposals=all_accepted_proposals,
        quotient_class_count=quotient_artifacts.result.quotient_summary.quotient_class_count,
        quotient_accepted_only_survivor_count=quotient_artifacts.result.accepted_proposal_set_result.survivor_count,
        quotient_accepted_only_exact_feasible=quotient_artifacts.result.accepted_proposal_set_result.exact_feasible,
        quotient_accepted_only_failure_reason=quotient_artifacts.result.accepted_proposal_set_result.exact_failure_reason,
        quotient_natural_pairing_survivor_count=None
        if quotient_artifacts.result.natural_pairing_result is None
        else quotient_artifacts.result.natural_pairing_result.survivor_count,
        quotient_natural_pairing_exact_feasible=None
        if quotient_artifacts.result.natural_pairing_result is None
        else quotient_artifacts.result.natural_pairing_result.exact_feasible,
        quotient_candidate_subset_witness_found=quotient_artifacts.result.candidate_subset_witness_result.witness_found,
        quotient_candidate_subset_minimal_witness_size=quotient_artifacts.result.candidate_subset_witness_result.minimal_witness_size,
        quotient_witness_status=quotient_artifacts.result.witness_classification,
        quotient_witness_candidate_ids=quotient_artifacts.result.candidate_subset_witness_result.witness_candidate_ids,
        quotient_feasibility_summary_path=quotient_artifacts.summary_path,
        selected_packaging_sources=sorted(prepared_run.selected_sources),
        selected_packaging_operator_count=len(prepared_run.selected_operator_ids),
        selected_packaging_family_count=len(prepared_run.selected_family_ids),
        packaging_support_slice_count=prepared_run.support_slice_count,
        selector_branch_outcome_counts=dict(
            sorted(selector_branch_outcome_counts.items())
        ),
        support_relation_kind_counts=_accepted_support_relation_counts(
            package_artifacts.candidates
        ),
        candidate_classification="inconclusive",
        claim_level_supported="nontrivial_multicontext_structure",
        run_ids=run_ids,
        artifact_paths=artifact_paths,
        notes=list(point.notes)
        + [
            "rm_is_diagnostic_only",
            f"sec_status={sec_status}",
            f"sec_mean={sec_mean}",
            "statistical_budget_exceeded_for_large_package"
            if skip_statistical
            else "statistical_stage_completed",
        ],
        flags=["packaging_axis", "same_support_package_change"],
    )
    quotient_diag = {
        "point_id": point.point_id,
        "quotient_witness_status": row.quotient_witness_status,
        "quotient_class_count": row.quotient_class_count,
        "accepted_only_survivor_count": row.quotient_accepted_only_survivor_count,
        "natural_pairing_survivor_count": row.quotient_natural_pairing_survivor_count,
        "candidate_subset_witness_found": row.quotient_candidate_subset_witness_found,
        "quotient_feasibility_summary_path": row.quotient_feasibility_summary_path,
    }
    return row, context_pair_rows, quotient_diag


def run_packaging_axis_search(
    *,
    search_path: str | Path,
    category: str,
    label: str | None = None,
    seed: int = 0,
    timestamp: str | None = None,
    root: str | Path | None = None,
    command: list[str] | None = None,
) -> PackagingAxisArtifacts:
    del seed
    repo_root = Path(root).resolve() if root is not None else None
    search = load_packaging_axis_search(search_path)
    run_dir, run_id, manifest_timestamp = create_run_directory(
        category=category,
        label=label or search.output_label or search.search_id,
        timestamp=timestamp,
        root=repo_root,
    )
    effective_root = run_dir.parents[2]
    derived_dir = run_dir / "derived"
    derived_dir.mkdir()

    prepared_run = _prepare_fixed_run(
        search=search,
        category=category,
        timestamp=timestamp,
        root=effective_root,
        derived_dir=derived_dir,
    )
    packaging_family_admissibility = _build_packaging_family_admissibility(
        search=search,
        prepared_run=prepared_run,
    )
    packaging_family_admissibility_path = (
        derived_dir / "packaging-family-admissibility.json"
    )
    _write_json(
        packaging_family_admissibility_path,
        packaging_family_admissibility.model_dump(mode="json"),
    )
    packaging_family_admissibility_relpath = repo_relative_path(
        packaging_family_admissibility_path, root=effective_root
    )

    point_results = [
        _run_point(
            search=search,
            point=point,
            prepared_run=prepared_run,
            packaging_family_admissibility_path=packaging_family_admissibility_relpath,
            category=category,
            timestamp=timestamp,
            root=effective_root,
            derived_dir=derived_dir,
        )
        for point in search.points
    ]
    rows: list[PackagingAxisRow] = []
    context_pair_rows: list[dict[str, object]] = []
    quotient_diagnostics_rows: list[dict[str, object]] = []
    for row, pair_rows, quotient_diag in point_results:
        row = row.model_copy(
            update={
                "candidate_classification": _candidate_classification(
                    row=row, search=search
                )
            }
        )
        row = row.model_copy(
            update={"claim_level_supported": _claim_level(row=row, search=search)}
        )
        rows.append(row)
        context_pair_rows.extend([pair.model_dump(mode="json") for pair in pair_rows])
        quotient_diagnostics_rows.append(quotient_diag)

    table = PackagingAxisTable(
        table_format_version="packaging-axis-results.v1",
        search_id=search.search_id,
        row_count=len(rows),
        rows=rows,
        metadata={"axis": "packaging"},
    )
    classification_counts = dict(Counter(row.candidate_classification for row in rows))
    quotient_witness_counts = dict(
        Counter(
            row.quotient_witness_status
            for row in rows
            if row.quotient_witness_status is not None
        )
    )
    claim_level_counts = dict(Counter(row.claim_level_supported for row in rows))
    adequacy = _evaluate_adequacy(rows, search)
    best_point = _best_point(rows)
    if not adequacy["adequate"]:
        outcome_kind = "design_inadequate"
    elif best_point is not None:
        outcome_kind = "best_candidate"
    else:
        outcome_kind = "negative_result"

    table_csv_path = run_dir / "packaging-axis.csv"
    table_json_path = run_dir / "packaging-axis.json"
    summary_path = run_dir / "packaging-axis-summary.json"
    note_path = run_dir / "packaging-axis-note.md"
    conflict_diag_path = run_dir / "package-conflict-diagnostics.json"
    quotient_diag_path = run_dir / "quotient-feasibility-diagnostics.json"
    result_note_path = run_dir / "result-note.json"
    manifest_path = run_dir / "run-manifest.json"
    outcome_path = run_dir / (
        "best-candidate.json"
        if outcome_kind == "best_candidate"
        else "negative-result.json"
        if outcome_kind == "negative_result"
        else "design-inadequate-result.json"
    )

    _write_csv(table_csv_path, [_row_to_csv_record(row) for row in rows])
    _write_json(table_json_path, table.model_dump(mode="json"))
    _write_json(
        conflict_diag_path,
        {
            "search_id": search.search_id,
            "rows": [
                {
                    "point_id": row.point_id,
                    "same_support_packaging_divergent_pair_count": row.same_support_packaging_divergent_pair_count,
                    "same_step_packaging_divergent_pair_count": row.same_step_packaging_divergent_pair_count,
                    "cross_resolution_packaging_divergent_pair_count": row.cross_resolution_packaging_divergent_pair_count,
                    "same_support_non_nested_packaging_divergent_pair_count": row.same_support_non_nested_packaging_divergent_pair_count,
                    "selector_branch_outcome_counts": row.selector_branch_outcome_counts,
                    "support_relation_kind_counts": row.support_relation_kind_counts,
                }
                for row in rows
            ],
            "context_pair_structure_rows": context_pair_rows,
        },
    )
    _write_json(
        quotient_diag_path,
        {
            "search_id": search.search_id,
            "rows": quotient_diagnostics_rows,
        },
    )
    output_paths = {
        "table_csv": repo_relative_path(table_csv_path, root=effective_root),
        "table_json": repo_relative_path(table_json_path, root=effective_root),
        "summary": repo_relative_path(summary_path, root=effective_root),
        "note": repo_relative_path(note_path, root=effective_root),
        "packaging_family_admissibility": packaging_family_admissibility_relpath,
        "package_conflict_diagnostics": repo_relative_path(
            conflict_diag_path, root=effective_root
        ),
        "quotient_feasibility_diagnostics": repo_relative_path(
            quotient_diag_path, root=effective_root
        ),
        "result_note": repo_relative_path(result_note_path, root=effective_root),
        "manifest": repo_relative_path(manifest_path, root=effective_root),
        "outcome": repo_relative_path(outcome_path, root=effective_root),
    }
    summary = _build_summary(
        search=search,
        rows=rows,
        adequacy=adequacy,
        classification_counts=classification_counts,
        quotient_witness_counts=quotient_witness_counts,
        claim_level_counts=claim_level_counts,
        best_point=best_point,
        output_paths=output_paths,
        outcome_kind=outcome_kind,
    )
    _write_json(summary_path, summary)
    note_path.write_text(
        _render_note(
            search=search,
            rows=rows,
            adequacy=adequacy,
            classification_counts=classification_counts,
            quotient_witness_counts=quotient_witness_counts,
            claim_level_counts=claim_level_counts,
            best_point=best_point,
            output_paths=output_paths,
            outcome_kind=outcome_kind,
        ),
        encoding="utf-8",
    )
    _write_json(
        outcome_path,
        {
            "search_id": search.search_id,
            "outcome_kind": outcome_kind,
            "best_point_id": None if best_point is None else best_point.point_id,
            "adequacy_floor_result": adequacy,
            "counts_by_quotient_witness_status": quotient_witness_counts,
            "counts_by_claim_level": claim_level_counts,
        },
    )
    result_note = _build_result_note(
        run_id=run_id,
        table=table,
        adequacy=adequacy,
        classification_counts=classification_counts,
        quotient_witness_counts=quotient_witness_counts,
        claim_level_counts=claim_level_counts,
        output_paths=output_paths,
        outcome_kind=outcome_kind,
        best_point=best_point,
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
            "run-packaging-axis",
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
            "analysis_kind": "packaging_axis_search",
            "classifier_version": PACKAGING_AXIS_CLASSIFIER_VERSION,
            "adequacy_version": PACKAGING_AXIS_ADEQUACY_VERSION,
        },
    )
    write_run_manifest(manifest, run_dir=run_dir)
    return PackagingAxisArtifacts(
        run_id=run_id,
        run_dir=repo_relative_path(run_dir, root=effective_root),
        table_csv_path=output_paths["table_csv"],
        table_json_path=output_paths["table_json"],
        summary_path=output_paths["summary"],
        note_path=output_paths["note"],
        packaging_family_admissibility_path=output_paths[
            "packaging_family_admissibility"
        ],
        package_conflict_diagnostics_path=output_paths["package_conflict_diagnostics"],
        quotient_feasibility_diagnostics_path=output_paths[
            "quotient_feasibility_diagnostics"
        ],
        result_note_path=output_paths["result_note"],
        manifest_path=output_paths["manifest"],
        table=table,
        classification_counts=classification_counts,
        quotient_witness_counts=quotient_witness_counts,
        claim_level_counts=claim_level_counts,
        adequacy=adequacy,
        outcome_path=output_paths["outcome"],
        outcome_kind=outcome_kind,
        best_point_id=None if best_point is None else best_point.point_id,
    )
