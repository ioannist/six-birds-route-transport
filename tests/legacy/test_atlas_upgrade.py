from __future__ import annotations

import csv
import json
from pathlib import Path
import subprocess
import sys

from sixbirds_event.schemas.common import SchemaKind
from sixbirds_event.schemas.result_note import ResultNote
from sixbirds_event.schemas.run_manifest import RunManifest
from sixbirds_event.search.atlas_upgrade import run_atlas_upgrade
from sixbirds_event.search.models import (
    AtlasUpgradeConfig,
    AtlasUpgradeRow,
    AtlasUpgradeTable,
    TargetedSearchEvaluation,
)
from sixbirds_event.validation import load_model, validate_payload


CONFIG = Path("experiments/configs/search/atlas-upgrade.json")


def test_atlas_upgrade_config_format_validates() -> None:
    payload = json.loads(CONFIG.read_text(encoding="utf-8"))
    result = validate_payload(payload, kind=SchemaKind.ATLAS_UPGRADE_CONFIG)
    assert result.ok
    assert result.kind == SchemaKind.ATLAS_UPGRADE_CONFIG


def test_atlas_upgrade_row_format_validates() -> None:
    evaluation = TargetedSearchEvaluation(
        exact_structural_status="not_applicable",
        exact_feasible=None,
        exact_respecting_tuple_count=None,
        gpd_str_status="not_applicable",
        gpd_str=None,
        gpd_str_reason=None,
        gpd_stat_status="not_applicable",
        gpd_stat=None,
        gpd_stat_reason=None,
    )
    row = AtlasUpgradeRow(
        row_format_version="atlas-upgrade-row.v1",
        atlas_id="atlas_demo",
        point_id="point_demo",
        config_path="experiments/configs/substrates/deterministic-cycle.json",
        preparation_id="prep0",
        protocol_id="cycle5",
        trajectories=4,
        seed=0,
        raw_run_path="results/search/demo/raw.json",
        discovered_context_family_path="results/search/demo/family.json",
        event_package_path=None,
        provenance_classification=None,
        accepted_context_count=0,
        accepted_singleton_event_count=0,
        accepted_coarse_event_count=0,
        accepted_shared_event_proposal_count=0,
        accepted_coarse_proposal_count=0,
        baseline_hard_only=evaluation,
        all_accepted_proposals=evaluation,
        ccd_status="not_applicable",
        ccd_overall=None,
        sec_status="not_applicable",
        sec_mean=None,
        rm_status="not_applicable",
        rm_overall=None,
        regime_classification="trivial_or_nonrecording",
        figure_group_labels=["demo_group", "trivial_or_nonrecording"],
        run_ids={"substrate_run": "run_search_demo"},
        artifact_paths={
            "raw_run": "results/search/demo/raw.json",
            "family": "results/search/demo/family.json",
        },
        notes=["demo_row"],
    )
    assert row.point_id == "point_demo"


def test_committed_atlas_upgrade_runs_end_to_end(tmp_path: Path) -> None:
    artifacts = run_atlas_upgrade(
        config_path=CONFIG.as_posix(),
        category="search",
        label="atlas-upgrade",
        seed=0,
        timestamp="2026-03-26T09:00:00Z",
        root=tmp_path,
    )

    config_model = load_model(CONFIG, kind=SchemaKind.ATLAS_UPGRADE_CONFIG)
    table = load_model(
        tmp_path / artifacts.table_json_path,
        kind=SchemaKind.ATLAS_UPGRADE_RESULTS,
    )
    result_note = load_model(
        tmp_path / artifacts.result_note_path,
        kind=SchemaKind.RESULT_NOTE,
    )
    manifest = load_model(
        tmp_path / artifacts.manifest_path,
        kind=SchemaKind.RUN_MANIFEST,
    )

    assert isinstance(config_model, AtlasUpgradeConfig)
    assert isinstance(table, AtlasUpgradeTable)
    assert isinstance(result_note, ResultNote)
    assert isinstance(manifest, RunManifest)
    assert table.atlas_id == config_model.atlas_id
    assert table.row_count == len(config_model.points)
    assert table.row_count == 6

    summary_payload = json.loads(
        (tmp_path / artifacts.summary_path).read_text(encoding="utf-8")
    )
    threshold_payload = json.loads(
        (tmp_path / artifacts.threshold_summary_path).read_text(encoding="utf-8")
    )
    note = (tmp_path / artifacts.note_path).read_text(encoding="utf-8")

    assert (tmp_path / artifacts.table_csv_path).exists()
    assert (tmp_path / artifacts.regime_counts_path).exists()
    assert (tmp_path / artifacts.figure_regime_counts_csv_path).exists()
    assert (tmp_path / artifacts.figure_atlas_points_csv_path).exists()
    assert (tmp_path / artifacts.figure_threshold_summary_csv_path).exists()

    with (tmp_path / artifacts.table_csv_path).open(
        "r", encoding="utf-8", newline=""
    ) as handle:
        csv_rows = list(csv.DictReader(handle))
    assert len(csv_rows) == table.row_count

    assert summary_payload["atlas_id"] == "atlas_upgrade"
    assert "counts_by_regime" in summary_payload
    assert "threshold_configs" in summary_payload
    assert "Baseline hard-only mode" in note
    assert "All-accepted-proposals mode" in note
    assert "RM is diagnostic-only" in note
    assert "unsolved / insufficient_data / not_applicable" in note

    assert "stage_counts" in threshold_payload
    assert threshold_payload["stage_counts"]["package_build_success_count"] >= 1
    assert (
        threshold_payload["stage_counts"]["accepted_coarse_event_positive_count"] >= 1
    )

    assert any(
        row.regime_classification
        in {"globally_packageable", "multi_context_but_extendable"}
        and row.accepted_context_count >= 2
        for row in table.rows
    )
    assert any(
        row.accepted_coarse_event_count > 0 and row.accepted_coarse_proposal_count > 0
        for row in table.rows
    )
    assert any(
        row.baseline_hard_only.exact_respecting_tuple_count
        != row.all_accepted_proposals.exact_respecting_tuple_count
        for row in table.rows
        if row.baseline_hard_only.exact_respecting_tuple_count is not None
        and row.all_accepted_proposals.exact_respecting_tuple_count is not None
    )

    if summary_payload["strong_nonextendable_count"] == 0:
        assert summary_payload["no_strong_discovered_obstruction_found"] is True
        assert artifacts.negative_result_path is not None
        negative_payload = json.loads(
            (tmp_path / artifacts.negative_result_path).read_text(encoding="utf-8")
        )
        assert negative_payload["reason"] == "no_strong_discovered_obstruction_found"
    else:
        assert artifacts.best_candidate_path is not None

    assert manifest.metadata["analysis_kind"] == "atlas_upgrade"
    assert "table_csv" in manifest.output_artifacts
    assert "table_json" in manifest.output_artifacts
    assert "regime_counts" in manifest.output_artifacts
    assert "threshold_summary" in manifest.output_artifacts


def test_cli_smoke_works_on_committed_atlas_upgrade(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "sixbirds_event",
            "search",
            "run-atlas-upgrade",
            CONFIG.as_posix(),
            "--category",
            "search",
            "--label",
            "atlas-upgrade",
            "--timestamp",
            "2026-03-26T09:00:00Z",
            "--root",
            str(tmp_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "run_id=" in result.stdout
    assert "atlas_csv=" in result.stdout
    assert "regime_counts=" in result.stdout
    assert "negative_result=true" in result.stdout or "best_candidate=" in result.stdout
