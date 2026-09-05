from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import sys

from sixbirds_event.discovery.models import (
    DiscoveredEventGenerationThresholds,
    PicaObservableProjection,
    SharedEventInferenceThresholds,
)
from sixbirds_event.pica_bridge.pilot import run_pica_pilot_campaign
from sixbirds_event.schemas.common import SchemaKind
from sixbirds_event.schemas.result_note import ResultNote
from sixbirds_event.schemas.run_manifest import RunManifest
from sixbirds_event.search.models import (
    FrozenSliceProjectionFamily,
    PackagingConflictComparisonTable,
    PackagingConflictSearchPoint,
    PackagingConflictSearchRow,
    PicaPackagingConflictAdequacyFloor,
    PicaPackagingConflictSearch,
    ProjectionFamilyAdmissibilityTable,
    TargetedCandidateClassificationThresholds,
    TargetedSearchEvaluation,
    ContextPairStructureTable,
)
from sixbirds_event.search.pica_packaging_conflict import (
    _candidate_classification,
    run_pica_packaging_conflict_search,
)
from sixbirds_event.validation import load_model, validate_file


SEARCH_CONFIG = Path("experiments/configs/pica/packaging-conflict-campaign.json")
PILOT_CONFIG = Path("experiments/configs/pica/pilot-exp121-packaging-p1p5.json")


def _fresh_timestamp(offset_seconds: int = 0) -> str:
    return (
        (
            datetime.now(timezone.utc).replace(microsecond=0)
            + timedelta(seconds=offset_seconds)
        )
        .isoformat()
        .replace("+00:00", "Z")
    )


def test_packaging_conflict_search_config_validates() -> None:
    result = validate_file(
        SEARCH_CONFIG, kind=SchemaKind.PICA_PACKAGING_CONFLICT_SEARCH
    )
    assert result.ok
    assert result.kind == SchemaKind.PICA_PACKAGING_CONFLICT_SEARCH
    assert isinstance(result.model, PicaPackagingConflictSearch)
    assert len(result.model.points) == 3
    assert len(result.model.projection_families) >= 5
    assert result.model.commutator_admissibility_mode == "p5_only"
    assert result.model.relevant_commutator_pairs == ["[P1,P5]", "[P2,P5]", "[P4,P5]"]


def test_pica_commutator_catalog_validates() -> None:
    timestamp = _fresh_timestamp()
    artifacts = run_pica_pilot_campaign(
        config_path=PILOT_CONFIG.as_posix(),
        category="results",
        label="pica-packaging-commutator-test",
        seed=0,
        timestamp=timestamp,
        root=Path.cwd(),
    )

    assert artifacts.commutator_catalog_path is not None
    catalog = load_model(
        Path(artifacts.commutator_catalog_path),
        kind=SchemaKind.PICA_COMMUTATOR_CATALOG,
    )
    assert catalog.row_count >= 6
    pair_ids = {row.pair_id for row in catalog.rows}
    assert {"[P1,P5]", "[P2,P5]", "[P4,P5]"} <= pair_ids
    assert {"[P1,P6]", "[P2,P6]", "[P4,P6]"} <= pair_ids


def test_coverage_failure_counts_as_strong_nonextendability() -> None:
    search = PicaPackagingConflictSearch(
        search_format_version="pica-packaging-conflict-search.v1",
        search_id="demo_search",
        points=[
            PackagingConflictSearchPoint(
                point_id="demo_point",
                pilot_config_artifact=PILOT_CONFIG.as_posix(),
                preparation_id="prep",
                protocol_id="protocol",
                trajectories=8,
                seed_list=[0],
                projection_family_ids=["obs_primary"],
                selected_protocol_step_ids=["step_1"],
                selected_step_indices=[1],
            )
        ],
        projection_families=[
            FrozenSliceProjectionFamily(
                projection_id="obs_primary",
                label="observation label",
                source_field="observation_label",
                projection_kind="packaging_outcome",
                allowed_roles=["primary_context"],
                projection=PicaObservableProjection(
                    projection_mode="observation_label"
                ),
            )
        ],
        relevant_commutator_pairs=["[P1,P5]"],
        min_relevant_commutator_value=1e-12,
        event_generation_thresholds=DiscoveredEventGenerationThresholds(
            event_basis_mode="singleton_plus_small_unions",
            event_algebra_mode="full_powerset",
            max_full_powerset_atom_count=6,
            max_union_size=3,
            min_event_support_count=1,
            min_event_support_fraction=0.0,
            include_empty_and_full_in_truncation=True,
            match_empty_for_inference=False,
            match_full_for_inference=False,
        ),
        shared_event_inference_thresholds=SharedEventInferenceThresholds(
            inference_mode="structural_primary",
            min_common_probes=1,
            min_conditioning_count=3,
            min_probe_atom_support_count=1,
            max_mean_tv=1.0,
            exact_tolerance=1e-9,
            proposal_constraint_kind="soft",
        ),
        provenance_required=True,
        candidate_classification_thresholds=TargetedCandidateClassificationThresholds(
            strong_nonextendable_min_gpd_str=1.0,
            near_zero_gpd_stat=1e-6,
            min_accepted_coarse_proposal_count=1,
        ),
        adequacy_floor=PicaPackagingConflictAdequacyFloor(),
    )
    row = PackagingConflictSearchRow(
        row_format_version="packaging-conflict-search-row.v1",
        search_id="demo_search",
        point_id="demo_point",
        source_pica_campaign_config_path=PILOT_CONFIG.as_posix(),
        projection_family_ids=["obs_primary"],
        preparation_id="prep",
        protocol_id="protocol",
        selected_protocol_step_ids=["step_1"],
        selected_step_indices=[1],
        trajectories=8,
        seed_list=[0],
        produced_export_bundle_path="experiments/contracts/pica/pilot/exp120_discovery_grade/pica-export-bundle.json",
        discovered_context_family_path="experiments/instances/discovered/pica-exp110-pairmatch-contexts/discovered-context-family.json",
        event_package_path="experiments/instances/discovered/pica-exp110-pairmatch-package/event-package.json",
        provenance_classification="admissible",
        accepted_context_count=3,
        accepted_proper_coarse_event_count=2,
        accepted_shared_event_proposal_count=2,
        accepted_proper_coarse_structural_proposal_count=1,
        accepted_package_conflict_same_slice_proper_coarse_proposal_count=1,
        accepted_non_nested_package_conflict_proposal_count=1,
        equal_context_pair_count=0,
        left_refines_right_count=0,
        right_refines_left_count=0,
        incomparable_context_pair_count=1,
        disjoint_or_unaligned_context_pair_count=0,
        same_slice_non_nested_context_pair_count=1,
        primary_identity_admissible_pair_count=1,
        packaging_conflict_admissible_pair_count=1,
        same_slice_non_nested_packaging_conflict_pair_count=1,
        nonzero_relevant_p5_commutator_support_count=1,
        median_accepted_proposal_support=4.0,
        baseline_hard_only=TargetedSearchEvaluation(
            exact_structural_status="feasible",
            exact_feasible=True,
            exact_respecting_tuple_count=4,
            gpd_str_status="solved",
            gpd_str=0.0,
            gpd_str_reason="baseline",
            gpd_stat_status="solved",
            gpd_stat=0.0,
            gpd_stat_reason="baseline",
        ),
        all_accepted_proposals=TargetedSearchEvaluation(
            exact_structural_status="infeasible",
            exact_feasible=False,
            exact_respecting_tuple_count=2,
            exact_failure_reason="coverage_failure",
            gpd_str_status="solved",
            gpd_str=2.0,
            gpd_str_reason="candidate",
            gpd_stat_status="solved",
            gpd_stat=0.2,
            gpd_stat_reason="candidate",
        ),
        ccd_status="not_applicable",
        sec_status="not_applicable",
        rm_status="not_applicable",
        candidate_classification="inconclusive",
        run_ids={"pilot": "run_demo"},
        artifact_paths={
            "export_bundle": "experiments/contracts/pica/pilot/exp120_discovery_grade/pica-export-bundle.json",
            "discovered_context_family": "experiments/instances/discovered/pica-exp110-pairmatch-contexts/discovered-context-family.json",
        },
    )

    assert (
        _candidate_classification(
            row=row,
            search=search,
            blocking_classification="coverage_failure",
        )
        == "strongly_nonextendable_candidate"
    )


def test_committed_packaging_conflict_campaign_runs_end_to_end() -> None:
    timestamp = _fresh_timestamp(offset_seconds=5)
    artifacts = run_pica_packaging_conflict_search(
        search_path=SEARCH_CONFIG.as_posix(),
        category="search",
        label="pica-packaging-conflict-test",
        seed=0,
        timestamp=timestamp,
        root=Path.cwd(),
        commutator_admissibility_mode="both",
    )

    config_model = load_model(
        SEARCH_CONFIG, kind=SchemaKind.PICA_PACKAGING_CONFLICT_SEARCH
    )
    table = load_model(
        Path(artifacts.table_json_path),
        kind=SchemaKind.PICA_PACKAGING_CONFLICT_SEARCH_RESULTS,
    )
    pair_table = load_model(
        Path(artifacts.context_pair_structure_path),
        kind=SchemaKind.CONTEXT_PAIR_STRUCTURE,
    )
    admissibility_table = load_model(
        Path(artifacts.projection_family_admissibility_path),
        kind=SchemaKind.PROJECTION_FAMILY_ADMISSIBILITY,
    )
    result_note = load_model(
        Path(artifacts.result_note_path), kind=SchemaKind.RESULT_NOTE
    )
    manifest = load_model(Path(artifacts.manifest_path), kind=SchemaKind.RUN_MANIFEST)

    assert isinstance(config_model, PicaPackagingConflictSearch)
    assert isinstance(table, PackagingConflictComparisonTable)
    assert isinstance(pair_table, ContextPairStructureTable)
    assert isinstance(admissibility_table, ProjectionFamilyAdmissibilityTable)
    assert isinstance(result_note, ResultNote)
    assert isinstance(manifest, RunManifest)
    assert table.search_id == config_model.search_id
    assert table.row_count == len(config_model.points) == 3
    assert pair_table.row_count >= 1
    assert admissibility_table.row_count >= table.row_count

    with Path(artifacts.table_csv_path).open(
        "r", encoding="utf-8", newline=""
    ) as handle:
        csv_rows = list(csv.DictReader(handle))
    assert len(csv_rows) == table.row_count

    summary_payload = json.loads(
        Path(artifacts.summary_path).read_text(encoding="utf-8")
    )
    commutator_summary = json.loads(
        Path(artifacts.commutator_summary_path).read_text(encoding="utf-8")
    )
    note = Path(artifacts.note_path).read_text(encoding="utf-8")

    assert summary_payload["outcome_kind"] in {
        "best_candidate",
        "negative_result",
        "design_inadequate",
    }
    assert summary_payload["comparative_conclusion"] in {
        "p6_surface_changed_nothing",
        "p6_surface_increased_signal_but_not_obstruction",
        "p6_surface_unlocked_stronger_candidate",
    }
    assert "package_conflict_admissibility_summary" in summary_payload
    assert "relevant_commutator_support_summary" in summary_payload
    assert "adequacy_floor_result" in summary_payload
    assert "accepted_proposals_by_support_relation_kind" in summary_payload
    assert (
        "Primary package-conflict evidence also requires a closure or lens difference plus nonzero relevant commutator support under the active mode."
        in note
    )
    assert "coverage_failure is treated as genuine nonextendability" in note
    assert "points_with_changed_packaging_conflict_pair_set" in commutator_summary

    assert all(row.provenance_classification == "admissible" for row in table.rows)
    assert any(
        row.p5_only.packaging_conflict_admissible_pair_count > 0 for row in table.rows
    )
    assert any(
        row.p5_p6_combined.packaging_conflict_admissible_pair_count
        >= row.p5_only.packaging_conflict_admissible_pair_count
        for row in table.rows
    )
    assert any(
        row.p5_only.support_relation_kind_counts
        or row.p5_p6_combined.support_relation_kind_counts
        for row in table.rows
    )
    assert any(
        pair.commutator_admissibility_mode == "p5_p6_combined"
        for pair in pair_table.rows
    )

    outcome_paths = [
        Path(artifacts.outcome_path),
        Path(artifacts.run_dir) / "best-candidate.json",
        Path(artifacts.run_dir) / "negative-result.json",
        Path(artifacts.run_dir) / "design-inadequate-result.json",
    ]
    existing_outcomes = {path.name for path in outcome_paths if path.exists()}
    assert len(existing_outcomes) == 1

    adequacy = summary_payload["adequacy_floor_result"]
    assert "adequate" in adequacy
    assert "checks" in adequacy
    assert "counts" in adequacy

    if summary_payload["outcome_kind"] == "best_candidate":
        payload = json.loads(Path(artifacts.outcome_path).read_text(encoding="utf-8"))
        assert payload["mode"] in {"p5_only", "p5_p6_combined"}
        assert payload["row"]["provenance_classification"] == "admissible"
    elif summary_payload["outcome_kind"] == "negative_result":
        payload = json.loads(Path(artifacts.outcome_path).read_text(encoding="utf-8"))
        assert payload["adequacy_floor_met"] is True
        assert payload["negative_result"] is True
    else:
        payload = json.loads(Path(artifacts.outcome_path).read_text(encoding="utf-8"))
        assert payload["adequacy_floor_met"] is False
        assert payload["outcome"] == "design_inadequate"

    assert manifest.metadata["analysis_kind"] == "pica_packaging_conflict_search"
    assert "table_csv" in manifest.output_artifacts
    assert "table_json" in manifest.output_artifacts
    assert "context_pair_structure" in manifest.output_artifacts
    assert "projection_family_admissibility" in manifest.output_artifacts
    assert "commutator_summary" in manifest.output_artifacts
    assert "summary" in manifest.output_artifacts
    assert "note" in manifest.output_artifacts


def test_cli_smoke_runs_committed_packaging_conflict_campaign() -> None:
    timestamp = _fresh_timestamp(offset_seconds=10)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "sixbirds_event",
            "search",
            "run-packaging-conflict",
            SEARCH_CONFIG.as_posix(),
            "--category",
            "search",
            "--label",
            "pica-packaging-conflict-cli-test",
            "--commutator-admissibility-mode",
            "both",
            "--timestamp",
            timestamp,
            "--root",
            str(Path.cwd()),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "run_id=" in result.stdout
    assert "packaging_conflict_comparison_csv=" in result.stdout
    assert "packaging_conflict_comparison_json=" in result.stdout
    assert "context_pair_structure=" in result.stdout
    assert "projection_family_admissibility=" in result.stdout
    assert "commutator_summary=" in result.stdout
    assert "summary=" in result.stdout
    assert "outcome_kind=" in result.stdout
    assert "outcome=" in result.stdout
