from __future__ import annotations

from pathlib import Path
import subprocess
import sys

from sixbirds_event.audits.models import (
    QuotientClassLedger,
    QuotientFeasibilityAudit,
    QuotientFeasibilityResult,
)
from sixbirds_event.schemas.common import SchemaKind
from sixbirds_event.schemas.result_note import ResultNote
from sixbirds_event.schemas.run_manifest import RunManifest
from sixbirds_event.validation import load_model, validate_file


COMMITTED_AUDIT = Path(
    "experiments/instances/mechanism-axis/exp104_p6_row_all_n64_seed0/quotient-feasibility-audit.json"
)
COMMITTED_CANDIDATES = Path(
    "experiments/instances/mechanism-axis/exp104_p6_row_all_n64_seed0/shared-event-candidates.json"
)


def test_quotient_feasibility_audit_config_validates() -> None:
    result = validate_file(COMMITTED_AUDIT, kind=SchemaKind.QUOTIENT_FEASIBILITY_AUDIT)
    assert result.ok
    assert isinstance(result.model, QuotientFeasibilityAudit)
    assert result.model.same_slice_selection.protocol_step_id.endswith("step_1")


def test_committed_quotient_feasibility_case_runs_end_to_end(tmp_path: Path) -> None:
    from sixbirds_event.audits.quotient_feasibility import (
        run_quotient_feasibility_audit,
    )

    artifacts = run_quotient_feasibility_audit(
        audit_path=COMMITTED_AUDIT,
        category="results",
        label="quotient-feasibility-test",
        timestamp="2026-03-29T06:00:00Z",
        root=tmp_path,
    )

    ledger = load_model(
        tmp_path / artifacts.quotient_class_ledger_path,
        kind=SchemaKind.QUOTIENT_CLASS_LEDGER,
    )
    assert isinstance(ledger, QuotientClassLedger)
    assert ledger.quotient_class_count == 13

    result = load_model(
        tmp_path / artifacts.summary_path,
        kind=SchemaKind.QUOTIENT_FEASIBILITY_RESULT,
    )
    assert isinstance(result, QuotientFeasibilityResult)
    assert result.witness_classification in {
        "accepted_proposal_obstruction",
        "candidate_subset_quotient_witness",
        "no_quotient_obstruction",
    }
    assert result.accepted_proposal_set_result.survivor_count == 10
    assert result.natural_pairing_result is not None
    assert result.natural_pairing_result.survivor_count == 13
    assert result.forced_candidate_subset_result is not None
    assert result.forced_candidate_subset_result.survivor_count == 0
    assert result.candidate_subset_witness_result.witness_found is True

    note = load_model(
        tmp_path / artifacts.result_note_path, kind=SchemaKind.RESULT_NOTE
    )
    assert isinstance(note, ResultNote)
    manifest = load_model(
        tmp_path / artifacts.manifest_path, kind=SchemaKind.RUN_MANIFEST
    )
    assert isinstance(manifest, RunManifest)

    output_dir = tmp_path / artifacts.run_dir
    assert (output_dir / "quotient-class-ledger.json").exists()
    assert (output_dir / "quotient-feasibility-summary.json").exists()
    assert (output_dir / "quotient-feasibility-note.md").exists()
    assert (output_dir / "witness-search-table.json").exists()


def test_committed_forced_witness_candidates_remain_rejected() -> None:
    candidates = load_model(
        COMMITTED_CANDIDATES, kind=SchemaKind.SHARED_EVENT_CANDIDATES
    )
    forced_ids = set(
        load_model(
            COMMITTED_AUDIT, kind=SchemaKind.QUOTIENT_FEASIBILITY_AUDIT
        ).forced_candidate_ids
    )
    rows = [row for row in candidates.candidate_rows if row.candidate_id in forced_ids]
    assert len(rows) == 2
    assert all(not row.accepted for row in rows)


def test_cli_smoke_quotient_feasibility(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "sixbirds_event",
            "audits",
            "quotient-feasibility",
            COMMITTED_AUDIT.as_posix(),
            "--category",
            "results",
            "--label",
            "quotient-feasibility-cli",
            "--timestamp",
            "2026-03-29T06:05:00Z",
            "--root",
            str(tmp_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "run_id=" in result.stdout
    assert "quotient_class_count=13" in result.stdout
    assert "accepted_only_survivor_count=10" in result.stdout
    assert "natural_pairing_survivor_count=13" in result.stdout
    assert "candidate_subset_witness_found=True" in result.stdout
    assert "witness_classification=" in result.stdout
