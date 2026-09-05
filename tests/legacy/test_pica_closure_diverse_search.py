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
    ContextPairStructureTable,
    PicaClosureDiverseSearch,
    PicaClosureDiverseSearchTable,
)
from sixbirds_event.search.pica_closure_diverse_search import (
    run_pica_closure_diverse_search,
)
from sixbirds_event.validation import load_model, validate_file


SEARCH_CONFIG = Path(
    "experiments/configs/pica/closure-diverse-obstruction-campaign.json"
)


def _fresh_timestamp(offset_seconds: int = 0) -> str:
    return (
        (
            datetime.now(timezone.utc).replace(microsecond=0)
            + timedelta(seconds=offset_seconds)
        )
        .isoformat()
        .replace("+00:00", "Z")
    )


def test_closure_diverse_search_config_validates() -> None:
    result = validate_file(SEARCH_CONFIG, kind=SchemaKind.PICA_CLOSURE_DIVERSE_SEARCH)
    assert result.ok
    assert result.kind == SchemaKind.PICA_CLOSURE_DIVERSE_SEARCH
    assert isinstance(result.model, PicaClosureDiverseSearch)
    assert len(result.model.points) == 4
    assert len(result.model.projection_families) >= 4


def test_context_pair_structure_fixture_validates() -> None:
    result = validate_file(
        Path("tests/legacy/fixtures/valid/context-pair-structure.json"),
        kind=SchemaKind.CONTEXT_PAIR_STRUCTURE,
    )
    assert result.ok
    assert result.kind == SchemaKind.CONTEXT_PAIR_STRUCTURE
    assert isinstance(result.model, ContextPairStructureTable)


def test_invalid_context_pair_structure_fixture_fails() -> None:
    result = validate_file(
        Path("tests/legacy/fixtures/invalid/context-pair-structure.json"),
        kind=SchemaKind.CONTEXT_PAIR_STRUCTURE,
    )
    assert not result.ok
    assert any("shared_row_count" in issue.message for issue in result.issues)


def test_invalid_search_config_fixture_fails() -> None:
    result = validate_file(
        Path("tests/legacy/fixtures/invalid/pica-closure-diverse-search.json"),
        kind=SchemaKind.PICA_CLOSURE_DIVERSE_SEARCH,
    )
    assert not result.ok
    assert any(
        "point_id values must be unique" in issue.message for issue in result.issues
    )


def test_committed_closure_diverse_campaign_runs_end_to_end() -> None:
    timestamp = _fresh_timestamp()
    artifacts = run_pica_closure_diverse_search(
        search_path=SEARCH_CONFIG.as_posix(),
        category="search",
        label="pica-closure-diverse-test",
        seed=0,
        timestamp=timestamp,
        root=Path.cwd(),
    )

    config_model = load_model(
        SEARCH_CONFIG, kind=SchemaKind.PICA_CLOSURE_DIVERSE_SEARCH
    )
    table = load_model(
        Path(artifacts.table_json_path),
        kind=SchemaKind.PICA_CLOSURE_DIVERSE_SEARCH_RESULTS,
    )
    pair_table = load_model(
        Path(artifacts.context_pair_structure_path),
        kind=SchemaKind.CONTEXT_PAIR_STRUCTURE,
    )
    result_note = load_model(
        Path(artifacts.result_note_path), kind=SchemaKind.RESULT_NOTE
    )
    manifest = load_model(Path(artifacts.manifest_path), kind=SchemaKind.RUN_MANIFEST)

    assert isinstance(config_model, PicaClosureDiverseSearch)
    assert isinstance(table, PicaClosureDiverseSearchTable)
    assert isinstance(pair_table, ContextPairStructureTable)
    assert isinstance(result_note, ResultNote)
    assert isinstance(manifest, RunManifest)
    assert table.search_id == config_model.search_id
    assert table.row_count == len(config_model.points)
    assert table.row_count == 4
    assert pair_table.search_id == config_model.search_id
    assert pair_table.row_count >= 1

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
        "design_inadequate",
    }
    assert "Projection families used" in note
    assert "Closure/lens/resolution diversity summary" in note
    assert "Baseline hard-only mode" in note
    assert "All-accepted-proposals mode" in note
    assert "RM is diagnostic-only" in note
    assert "unsolved / insufficient_data / not_applicable" in note

    assert all(row.provenance_classification == "admissible" for row in table.rows)
    assert any(row.incomparable_context_pair_count > 0 for row in table.rows)
    assert any(pair.relation_type == "incomparable" for pair in pair_table.rows)

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
        assert payload["accepted_proper_coarse_structural_proposal_count"] >= 1
        assert payload["accepted_incomparable_proper_coarse_proposal_count"] >= 1
        assert payload["provenance_classification"] == "admissible"
    elif summary_payload["outcome_kind"] == "negative_result":
        payload = json.loads(Path(artifacts.outcome_path).read_text(encoding="utf-8"))
        assert payload["adequacy_floor_met"] is True
        assert payload["negative_result"] is True
    else:
        payload = json.loads(Path(artifacts.outcome_path).read_text(encoding="utf-8"))
        assert payload["adequacy_floor_met"] is False
        assert payload["outcome"] == "design_inadequate"

    assert manifest.metadata["analysis_kind"] == "pica_closure_diverse_search"
    assert "table_csv" in manifest.output_artifacts
    assert "table_json" in manifest.output_artifacts
    assert "context_pair_structure" in manifest.output_artifacts
    assert "summary" in manifest.output_artifacts
    assert "note" in manifest.output_artifacts


def test_cli_smoke_runs_committed_closure_diverse_campaign() -> None:
    timestamp = _fresh_timestamp(offset_seconds=5)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "sixbirds_event",
            "search",
            "run-pica-closure-diverse",
            SEARCH_CONFIG.as_posix(),
            "--category",
            "search",
            "--label",
            "pica-closure-diverse-cli-test",
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
    assert "pica_closure_diverse_csv=" in result.stdout
    assert "pica_closure_diverse_json=" in result.stdout
    assert "context_pair_structure=" in result.stdout
    assert "summary=" in result.stdout
    assert "outcome_kind=" in result.stdout
    assert "outcome=" in result.stdout
