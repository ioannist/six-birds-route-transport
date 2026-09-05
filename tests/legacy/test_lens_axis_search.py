from __future__ import annotations

from pathlib import Path
import subprocess
import sys

from sixbirds_event.schemas.common import SchemaKind
from sixbirds_event.schemas.result_note import ResultNote
from sixbirds_event.schemas.run_manifest import RunManifest
from sixbirds_event.search.models import (
    LensAxisSearch,
    LensAxisTable,
    LensFamilyAdmissibility,
)
from sixbirds_event.validation import load_model, validate_file


COMMITTED_CONFIG = Path("experiments/configs/pica/lens-axis-campaign.json")


def test_lens_axis_config_and_admissibility_validate() -> None:
    result = validate_file(COMMITTED_CONFIG, kind=SchemaKind.LENS_AXIS_SEARCH)
    assert result.ok
    assert isinstance(result.model, LensAxisSearch)
    assert result.model.claim_ceiling == "provenance_admissible_strong_obstruction"


def test_committed_lens_axis_campaign_runs_end_to_end(tmp_path: Path) -> None:
    from sixbirds_event.search.lens_axis import run_lens_axis_search

    artifacts = run_lens_axis_search(
        search_path=COMMITTED_CONFIG,
        category="search",
        label="lens-axis-test",
        timestamp="2026-03-29T12:30:00Z",
        root=tmp_path,
    )

    table = load_model(
        tmp_path / artifacts.table_json_path,
        kind=SchemaKind.LENS_AXIS_RESULTS,
    )
    assert isinstance(table, LensAxisTable)
    assert table.row_count == 3
    assert any(row.same_slice_non_nested_lens_pair_count > 0 for row in table.rows)
    assert all(
        row.quotient_witness_status == "candidate_subset_quotient_witness"
        for row in table.rows
    )
    assert all(
        row.quotient_candidate_subset_witness_found is True for row in table.rows
    )
    assert all(
        row.candidate_classification == "weakly_frustrated_candidate"
        for row in table.rows
    )

    admissibility = load_model(
        tmp_path / artifacts.run_dir / "derived" / "lens-family-admissibility.json",
        kind=SchemaKind.LENS_FAMILY_ADMISSIBILITY,
    )
    assert isinstance(admissibility, LensFamilyAdmissibility)
    assert any(row.allowed_role == "primary_context" for row in admissibility.rows)

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
    assert (output_dir / "lens-axis.csv").exists()
    assert (output_dir / "lens-axis-summary.json").exists()
    assert (output_dir / "lens-axis-note.md").exists()
    assert (output_dir / "support-relation-diagnostics.json").exists()
    assert (output_dir / "quotient-feasibility-diagnostics.json").exists()
    outcome_files = [
        output_dir / "best-candidate.json",
        output_dir / "negative-result.json",
        output_dir / "design-inadequate-result.json",
    ]
    assert sum(path.exists() for path in outcome_files) == 1


def test_cli_smoke_run_lens_axis(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "sixbirds_event",
            "search",
            "run-lens-axis",
            COMMITTED_CONFIG.as_posix(),
            "--category",
            "search",
            "--label",
            "lens-axis-cli",
            "--timestamp",
            "2026-03-29T12:45:00Z",
            "--root",
            str(tmp_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "run_id=" in result.stdout
    assert "lens_axis_csv=" in result.stdout
    assert "lens_axis_json=" in result.stdout
    assert "support_relation_diagnostics=" in result.stdout
    assert "quotient_" in result.stdout
