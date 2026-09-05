from __future__ import annotations

from pathlib import Path
import subprocess
import sys

from sixbirds_event.schemas.common import SchemaKind
from sixbirds_event.schemas.result_note import ResultNote
from sixbirds_event.schemas.run_manifest import RunManifest
from sixbirds_event.search.models import (
    LensAxisFinalOutcome,
    LensAxisFinalizationConfig,
)
from sixbirds_event.validation import load_model, validate_file


COMMITTED_CONFIG = Path("experiments/configs/pica/lens-axis-final.json")


def test_lens_axis_finalization_config_validates() -> None:
    result = validate_file(COMMITTED_CONFIG, kind=SchemaKind.LENS_AXIS_FINALIZATION)
    assert result.ok
    assert isinstance(result.model, LensAxisFinalizationConfig)
    assert result.model.canonical_flagship_case_id == "cross_res_all_steps"


def test_lens_axis_finalization_runs_end_to_end(tmp_path: Path) -> None:
    from sixbirds_event.search.lens_axis_finalization import run_lens_axis_finalization

    artifacts = run_lens_axis_finalization(
        config_path=COMMITTED_CONFIG,
        category="results",
        label="lens-axis-final-test",
        timestamp="2026-03-30T02:00:00Z",
        root=tmp_path,
    )

    outcome = load_model(
        tmp_path / artifacts.summary_path,
        kind=SchemaKind.LENS_AXIS_FINAL_OUTCOME,
    )
    assert isinstance(outcome, LensAxisFinalOutcome)
    assert outcome.canonical_flagship_case_id == "cross_res_all_steps"
    assert outcome.accepted_proposal_obstruction is True
    assert outcome.accepted_only_survivor_count == 10
    assert outcome.natural_pairing_survivor_count == 13
    assert outcome.final_claim_level == "provenance_admissible_strong_obstruction"
    assert {regime.regime_label for regime in outcome.regimes} == {
        "same_step_bounded_negative",
        "cross_resolution_strict_extension",
    }

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
    assert (output_dir / "lens-axis-final-summary.json").exists()
    assert (output_dir / "lens-axis-final-note.md").exists()
    assert (output_dir / "lens-axis-regime-table.json").exists()
    assert (output_dir / "th4-finalized.json").exists()


def test_cli_smoke_finalize_lens_axis(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "sixbirds_event",
            "search",
            "finalize-lens-axis",
            COMMITTED_CONFIG.as_posix(),
            "--category",
            "results",
            "--label",
            "lens-axis-final-cli",
            "--timestamp",
            "2026-03-30T02:05:00Z",
            "--root",
            str(tmp_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "run_id=" in result.stdout
    assert "summary=" in result.stdout
    assert "regime_table=" in result.stdout
    assert "canonical_flagship_case_id=cross_res_all_steps" in result.stdout
    assert "accepted_proposal_obstruction=True" in result.stdout
    assert "accepted_only_survivor_count=10" in result.stdout
    assert "natural_pairing_survivor_count=13" in result.stdout
    assert "final_claim_level=provenance_admissible_strong_obstruction" in result.stdout
