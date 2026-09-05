from __future__ import annotations

from pathlib import Path
import subprocess
import sys

from sixbirds_event.schemas.common import SchemaKind
from sixbirds_event.schemas.result_note import ResultNote
from sixbirds_event.schemas.run_manifest import RunManifest
from sixbirds_event.search.models import (
    PackagingAxisSearch,
    PackagingAxisTable,
    PackagingFamilyAdmissibility,
)
from sixbirds_event.validation import load_model, validate_file


COMMITTED_CONFIG = Path("experiments/configs/pica/packaging-axis-campaign.json")


def test_packaging_axis_config_validates() -> None:
    result = validate_file(COMMITTED_CONFIG, kind=SchemaKind.PACKAGING_AXIS_SEARCH)
    assert result.ok
    assert isinstance(result.model, PackagingAxisSearch)
    assert result.model.claim_ceiling == "provenance_admissible_packaging_obstruction"


def test_committed_packaging_axis_campaign_runs_end_to_end(tmp_path: Path) -> None:
    from sixbirds_event.search.packaging_axis import run_packaging_axis_search

    artifacts = run_packaging_axis_search(
        search_path=COMMITTED_CONFIG,
        category="search",
        label="packaging-axis-test",
        timestamp="2026-03-30T19:20:00Z",
        root=tmp_path,
    )

    table = load_model(
        tmp_path / artifacts.table_json_path,
        kind=SchemaKind.PACKAGING_AXIS_RESULTS,
    )
    assert isinstance(table, PackagingAxisTable)
    assert table.row_count == 3
    assert any(
        row.same_support_packaging_divergent_pair_count > 0 for row in table.rows
    )
    assert any(
        row.quotient_witness_status == "accepted_proposal_obstruction"
        for row in table.rows
    )
    best_rows = [
        row
        for row in table.rows
        if row.candidate_classification == "strongly_nonextendable_candidate"
    ]
    assert len(best_rows) == 1
    best_row = best_rows[0]
    assert best_row.point_id == "packaging_cross_res_k4_k20"
    assert best_row.quotient_accepted_only_survivor_count == 3
    assert best_row.quotient_natural_pairing_survivor_count == 11
    assert best_row.provenance_classification == "admissible"

    admissibility = load_model(
        tmp_path / artifacts.packaging_family_admissibility_path,
        kind=SchemaKind.PACKAGING_FAMILY_ADMISSIBILITY,
    )
    assert isinstance(admissibility, PackagingFamilyAdmissibility)
    assert any(row.allowed_role == "primary_context_pair" for row in admissibility.rows)

    note = load_model(
        tmp_path / artifacts.result_note_path,
        kind=SchemaKind.RESULT_NOTE,
    )
    assert isinstance(note, ResultNote)
    manifest = load_model(
        tmp_path / artifacts.manifest_path,
        kind=SchemaKind.RUN_MANIFEST,
    )
    assert isinstance(manifest, RunManifest)

    output_dir = tmp_path / artifacts.run_dir
    assert (output_dir / "packaging-axis.csv").exists()
    assert (output_dir / "packaging-axis-summary.json").exists()
    assert (output_dir / "packaging-axis-note.md").exists()
    assert (output_dir / "package-conflict-diagnostics.json").exists()
    assert (output_dir / "quotient-feasibility-diagnostics.json").exists()
    outcome_files = [
        output_dir / "best-candidate.json",
        output_dir / "negative-result.json",
        output_dir / "design-inadequate-result.json",
    ]
    assert sum(path.exists() for path in outcome_files) == 1


def test_cli_smoke_run_packaging_axis(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "sixbirds_event",
            "search",
            "run-packaging-axis",
            COMMITTED_CONFIG.as_posix(),
            "--category",
            "search",
            "--label",
            "packaging-axis-cli",
            "--timestamp",
            "2026-03-30T19:25:00Z",
            "--root",
            str(tmp_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "run_id=" in result.stdout
    assert "packaging_axis_csv=" in result.stdout
    assert "packaging_axis_json=" in result.stdout
    assert "package_conflict_diagnostics=" in result.stdout
    assert "quotient_" in result.stdout
