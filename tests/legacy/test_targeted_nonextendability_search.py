from __future__ import annotations

import csv
import json
from pathlib import Path
import subprocess
import sys

from sixbirds_event.schemas.common import SchemaKind
from sixbirds_event.schemas.result_note import ResultNote
from sixbirds_event.schemas.run_manifest import RunManifest
from sixbirds_event.search.models import (
    TargetedNonextendabilitySearch,
    TargetedSearchEvaluation,
    TargetedSearchRow,
    TargetedSearchTable,
)
from sixbirds_event.search.targeted_nonextendability import (
    run_targeted_nonextendability_search,
)
from sixbirds_event.validation import load_model, validate_payload


SEARCH = Path("experiments/configs/search/targeted-nonextendability.json")


def test_targeted_search_format_validates() -> None:
    payload = json.loads(SEARCH.read_text(encoding="utf-8"))
    result = validate_payload(payload, kind=SchemaKind.TARGETED_NONEXTENDABILITY_SEARCH)
    assert result.ok
    assert result.kind == SchemaKind.TARGETED_NONEXTENDABILITY_SEARCH


def test_targeted_search_row_format_validates() -> None:
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
    row = TargetedSearchRow(
        row_format_version="targeted-search-row.v1",
        search_id="targeted_demo",
        point_id="point_demo",
        config_path="experiments/configs/substrates/triadic-stable-single-lens.json",
        preparation_id="prep0",
        protocol_id="branch_hold_hold",
        trajectories=12,
        seed=123,
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
        candidate_classification="trivial_or_nonrecording",
        run_ids={"substrate_run": "run_search_demo_point"},
        artifact_paths={
            "raw_run": "results/search/demo/raw.json",
            "family": "results/search/demo/family.json",
        },
        notes=["demo_row"],
    )
    assert row.point_id == "point_demo"


def test_committed_targeted_search_runs_end_to_end(tmp_path: Path) -> None:
    artifacts = run_targeted_nonextendability_search(
        search_path=SEARCH.as_posix(),
        category="search",
        label="targeted-nonextendability",
        seed=0,
        timestamp="2026-03-26T05:00:00Z",
        root=tmp_path,
    )

    search_model = load_model(
        SEARCH,
        kind=SchemaKind.TARGETED_NONEXTENDABILITY_SEARCH,
    )
    table = load_model(
        tmp_path / artifacts.table_json_path,
        kind=SchemaKind.TARGETED_SEARCH_RESULTS,
    )
    result_note = load_model(
        tmp_path / artifacts.result_note_path,
        kind=SchemaKind.RESULT_NOTE,
    )
    manifest = load_model(
        tmp_path / artifacts.manifest_path,
        kind=SchemaKind.RUN_MANIFEST,
    )

    assert isinstance(search_model, TargetedNonextendabilitySearch)
    assert isinstance(table, TargetedSearchTable)
    assert isinstance(result_note, ResultNote)
    assert isinstance(manifest, RunManifest)
    assert table.search_id == search_model.search_id
    assert table.row_count == len(search_model.points)
    assert table.row_count == 3

    csv_path = tmp_path / artifacts.table_csv_path
    assert csv_path.exists()
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        csv_rows = list(csv.DictReader(handle))
    assert len(csv_rows) == table.row_count

    summary_payload = json.loads(
        (tmp_path / artifacts.summary_path).read_text(encoding="utf-8")
    )
    note = (tmp_path / artifacts.note_path).read_text(encoding="utf-8")

    assert summary_payload["search_id"] == "targeted_nonextendability"
    assert summary_payload["negative_result"] is True
    assert summary_payload["best_candidate_id"] is None
    assert "Baseline hard-only mode" in note
    assert "All-accepted-proposals mode" in note
    assert "RM is diagnostic-only" in note
    assert "unsolved / insufficient-data / not_applicable" in note

    negative_result = json.loads(
        (tmp_path / artifacts.negative_result_path).read_text(encoding="utf-8")
    )
    assert negative_result["negative_result"] is True

    assert manifest.metadata["analysis_kind"] == "targeted_nonextendability_search"
    assert set(manifest.output_artifacts) == {
        "table_csv",
        "table_json",
        "summary",
        "note",
        "result_note",
        "negative_result",
    }

    assert any(
        row.accepted_coarse_event_count >= 1 and row.accepted_coarse_proposal_count >= 1
        for row in table.rows
    )
    assert any(
        row.baseline_hard_only.exact_respecting_tuple_count
        != row.all_accepted_proposals.exact_respecting_tuple_count
        for row in table.rows
        if row.baseline_hard_only.exact_respecting_tuple_count is not None
        and row.all_accepted_proposals.exact_respecting_tuple_count is not None
    )

    for row in table.rows:
        assert row.provenance_classification is not None
        assert row.baseline_hard_only.exact_structural_status in {
            "feasible",
            "infeasible",
            "not_applicable",
        }
        assert row.all_accepted_proposals.exact_structural_status in {
            "feasible",
            "infeasible",
            "not_applicable",
        }
        assert row.baseline_hard_only.gpd_str_status in {
            "solved",
            "unsolved",
            "insufficient_data",
            "not_applicable",
        }
        assert row.all_accepted_proposals.gpd_str_status in {
            "solved",
            "unsolved",
            "insufficient_data",
            "not_applicable",
        }
        assert (tmp_path / row.raw_run_path).exists()
        assert (tmp_path / row.discovered_context_family_path).exists()
        if row.event_package_path is not None:
            assert (tmp_path / row.event_package_path).exists()
        assert row.run_ids
        assert row.artifact_paths


def test_cli_smoke_works_on_committed_targeted_search(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "sixbirds_event",
            "search",
            "run-targeted-nonextendability",
            SEARCH.as_posix(),
            "--category",
            "search",
            "--label",
            "targeted-nonextendability",
            "--timestamp",
            "2026-03-26T05:00:00Z",
            "--root",
            str(tmp_path),
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
    assert "note=" in result.stdout
    assert "result_note=" in result.stdout
    assert "manifest=" in result.stdout
    assert "extendable_candidate=" in result.stdout
    assert "negative_result=true" in result.stdout
    assert "negative_result_json=" in result.stdout

    stdout_lines = {
        line.split("=", 1)[0]: line.split("=", 1)[1]
        for line in result.stdout.strip().splitlines()
        if "=" in line
    }
    table_path = tmp_path / stdout_lines["targeted_search_json"]
    table = load_model(table_path, kind=SchemaKind.TARGETED_SEARCH_RESULTS)
    assert isinstance(table, TargetedSearchTable)
    assert table.row_count == 3
