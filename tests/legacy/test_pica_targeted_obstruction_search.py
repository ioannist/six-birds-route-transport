from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import sys

from sixbirds_event.schemas.common import SchemaKind
from sixbirds_event.schemas.result_note import ResultNote
from sixbirds_event.schemas.run_manifest import RunManifest
from sixbirds_event.search.models import (
    PicaTargetedObstructionSearch,
    PicaTargetedSearchRow,
    PicaTargetedSearchTable,
    TargetedSearchEvaluation,
)
from sixbirds_event.search.pica_targeted_obstruction import (
    run_pica_targeted_obstruction_search,
)
from sixbirds_event.validation import load_model, validate_payload


CONFIG = Path("experiments/configs/pica/targeted-obstruction-campaign.json")


def _fresh_timestamp(offset_seconds: int = 0) -> str:
    return (
        (
            datetime.now(timezone.utc).replace(microsecond=0)
            + timedelta(seconds=offset_seconds)
        )
        .isoformat()
        .replace("+00:00", "Z")
    )


def test_pica_targeted_obstruction_search_config_validates() -> None:
    payload = json.loads(CONFIG.read_text(encoding="utf-8"))
    result = validate_payload(payload, kind=SchemaKind.PICA_TARGETED_OBSTRUCTION_SEARCH)
    assert result.ok
    assert result.kind == SchemaKind.PICA_TARGETED_OBSTRUCTION_SEARCH


def test_pica_targeted_search_row_format_validates() -> None:
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
    row = PicaTargetedSearchRow(
        row_format_version="pica-targeted-search-row.v1",
        search_id="search_demo",
        point_id="point_demo",
        source_pica_campaign_config_path="experiments/configs/pica/pilot-campaign.json",
        discovery_config_path="experiments/configs/pica/context-discovery-exp100-multiseed.json",
        preparation_id="prep_demo",
        protocol_id="protocol_demo",
        trajectories=3,
        seed_list=[0, 1, 2],
        produced_export_bundle_path="results/search/demo/pica-export-bundle.json",
        discovered_context_family_path="results/search/demo/discovered-context-family.json",
        event_package_path="results/search/demo/event-package.json",
        provenance_classification="unsupported",
        accepted_context_count=0,
        accepted_singleton_event_count=0,
        accepted_proper_coarse_event_count=0,
        accepted_shared_event_proposal_count=0,
        accepted_proper_coarse_structural_proposal_count=0,
        baseline_hard_only=evaluation,
        all_accepted_proposals=evaluation,
        ccd_status="not_applicable",
        ccd_overall=None,
        sec_status="not_applicable",
        sec_mean=None,
        rm_status="not_applicable",
        rm_overall=None,
        candidate_classification="trivial_or_nonrecording",
        run_ids={"context_discovery": "run_demo"},
        artifact_paths={"event_package": "results/search/demo/event-package.json"},
        notes=["demo_row"],
    )
    assert row.point_id == "point_demo"


def test_committed_pica_targeted_campaign_runs_end_to_end(tmp_path: Path) -> None:
    timestamp = _fresh_timestamp()
    artifacts = run_pica_targeted_obstruction_search(
        search_path=CONFIG.as_posix(),
        category="search",
        label="pica-targeted-obstruction-test",
        seed=0,
        timestamp=timestamp,
        root=Path.cwd(),
    )

    config_model = load_model(CONFIG, kind=SchemaKind.PICA_TARGETED_OBSTRUCTION_SEARCH)
    table = load_model(
        Path(artifacts.table_json_path),
        kind=SchemaKind.PICA_TARGETED_SEARCH_RESULTS,
    )
    result_note = load_model(
        Path(artifacts.result_note_path),
        kind=SchemaKind.RESULT_NOTE,
    )
    manifest = load_model(
        Path(artifacts.manifest_path),
        kind=SchemaKind.RUN_MANIFEST,
    )

    assert isinstance(config_model, PicaTargetedObstructionSearch)
    assert isinstance(table, PicaTargetedSearchTable)
    assert isinstance(result_note, ResultNote)
    assert isinstance(manifest, RunManifest)
    assert table.search_id == config_model.search_id
    assert table.row_count == len(config_model.points)
    assert table.row_count == 4

    with Path(artifacts.table_csv_path).open(
        "r", encoding="utf-8", newline=""
    ) as handle:
        csv_rows = list(csv.DictReader(handle))
    assert len(csv_rows) == table.row_count

    summary_payload = json.loads(
        Path(artifacts.summary_path).read_text(encoding="utf-8")
    )
    note = Path(artifacts.note_path).read_text(encoding="utf-8")

    assert "adequacy_floor_result" in summary_payload
    assert "counts_by_candidate_class" in summary_payload
    assert summary_payload["outcome_kind"] in {
        "best_candidate",
        "negative_result",
        "search_inadequate",
    }
    assert "Baseline hard-only mode" in note
    assert "All-accepted-proposals mode" in note
    assert "Adequacy floor result" in note
    assert "RM is diagnostic-only" in note

    assert all(row.provenance_classification is not None for row in table.rows)
    assert all(
        row.baseline_hard_only.model_dump(mode="json") != {}
        and row.all_accepted_proposals.model_dump(mode="json") != {}
        for row in table.rows
    )

    outcome_paths = [
        Path(artifacts.outcome_path),
        Path(artifacts.run_dir) / "best-candidate.json",
        Path(artifacts.run_dir) / "negative-result.json",
        Path(artifacts.run_dir) / "inadequate-search-result.json",
    ]
    existing_outcomes = {path.name for path in outcome_paths if path.exists()}
    assert len(existing_outcomes) == 1

    adequacy = summary_payload["adequacy_floor_result"]
    assert "adequate" in adequacy
    assert "checks" in adequacy
    assert "counts" in adequacy

    if summary_payload["outcome_kind"] == "best_candidate":
        payload = json.loads(Path(artifacts.outcome_path).read_text())
        assert payload["accepted_proper_coarse_structural_proposal_count"] >= 1
        assert payload["provenance_classification"] == "admissible"
    elif summary_payload["outcome_kind"] == "negative_result":
        payload = json.loads(Path(artifacts.outcome_path).read_text())
        assert payload["adequacy_floor_met"] is True
        assert payload["negative_result"] is True
    else:
        payload = json.loads(Path(artifacts.outcome_path).read_text())
        assert payload["adequacy_floor_met"] is False
        assert payload["outcome"] == "search_inadequate"

    assert manifest.metadata["analysis_kind"] == "pica_targeted_obstruction_search"
    assert "table_csv" in manifest.output_artifacts
    assert "table_json" in manifest.output_artifacts
    assert "summary" in manifest.output_artifacts
    assert "note" in manifest.output_artifacts


def test_cli_smoke_runs_committed_pica_targeted_campaign(tmp_path: Path) -> None:
    timestamp = _fresh_timestamp(offset_seconds=5)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "sixbirds_event",
            "search",
            "run-pica-targeted-obstruction",
            CONFIG.as_posix(),
            "--category",
            "search",
            "--label",
            "pica-targeted-obstruction-cli-test",
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
    assert "targeted_search_csv=" in result.stdout
    assert "targeted_search_json=" in result.stdout
    assert "summary=" in result.stdout
    assert "outcome_kind=" in result.stdout
    assert "outcome=" in result.stdout
