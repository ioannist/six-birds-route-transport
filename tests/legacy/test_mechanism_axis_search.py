from __future__ import annotations

from pathlib import Path
import subprocess
import sys

from sixbirds_event.schemas.common import SchemaKind
from sixbirds_event.schemas.result_note import ResultNote
from sixbirds_event.schemas.run_manifest import RunManifest
from sixbirds_event.search.models import MechanismAxisSearch, MechanismAxisTable
from sixbirds_event.validation import load_model, validate_file


COMMITTED_CONFIG = Path("experiments/configs/pica/mechanism-axis-campaign.json")


def test_mechanism_axis_config_validates() -> None:
    result = validate_file(COMMITTED_CONFIG, kind=SchemaKind.MECHANISM_AXIS_SEARCH)
    assert result.ok
    assert isinstance(result.model, MechanismAxisSearch)
    assert result.model.claim_ceiling == "package_conflict_tension"


def test_committed_mechanism_axis_campaign_runs_end_to_end(tmp_path: Path) -> None:
    from sixbirds_event.search.mechanism_axis import run_mechanism_axis_search

    artifacts = run_mechanism_axis_search(
        search_path=COMMITTED_CONFIG,
        category="search",
        label="mechanism-axis-test",
        timestamp="2026-03-29T00:30:00Z",
        root=tmp_path,
    )

    table = load_model(
        tmp_path / artifacts.table_json_path,
        kind=SchemaKind.MECHANISM_AXIS_RESULTS,
    )
    assert isinstance(table, MechanismAxisTable)
    assert table.row_count == 5
    assert any(row.changed_packaging_surface_relative_to_control for row in table.rows)
    assert any(
        row.claim_level_supported
        in {
            "nontrivial_multicontext_structure",
            "package_conflict_tension",
        }
        for row in table.rows
    )
    quotient_rows = [
        row for row in table.rows if row.quotient_witness_classification is not None
    ]
    assert len(quotient_rows) == 1
    assert quotient_rows[0].quotient_class_count == 13
    assert quotient_rows[0].quotient_accepted_only_survivor_count == 10
    assert quotient_rows[0].quotient_natural_pairing_survivor_count == 13
    assert quotient_rows[0].quotient_candidate_subset_witness_found is True

    summary = load_model(
        tmp_path / artifacts.result_note_path,
        kind=SchemaKind.RESULT_NOTE,
    )
    assert isinstance(summary, ResultNote)
    manifest = load_model(
        tmp_path / artifacts.manifest_path,
        kind=SchemaKind.RUN_MANIFEST,
    )
    assert isinstance(manifest, RunManifest)

    output_dir = tmp_path / artifacts.run_dir
    assert (output_dir / "mechanism-axis.csv").exists()
    assert (output_dir / "mechanism-axis-summary.json").exists()
    assert (output_dir / "mechanism-axis-note.md").exists()
    outcome_files = [
        output_dir / "best-candidate.json",
        output_dir / "negative-result.json",
        output_dir / "design-inadequate-result.json",
    ]
    assert sum(path.exists() for path in outcome_files) == 1


def test_cli_smoke_run_mechanism_axis(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "sixbirds_event",
            "search",
            "run-mechanism-axis",
            COMMITTED_CONFIG.as_posix(),
            "--category",
            "search",
            "--label",
            "mechanism-axis-cli",
            "--timestamp",
            "2026-03-29T00:45:00Z",
            "--root",
            str(tmp_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "run_id=" in result.stdout
    assert "mechanism_axis_csv=" in result.stdout
    assert "mechanism_axis_json=" in result.stdout
    assert "summary=" in result.stdout
    assert "claim_" in result.stdout
