from __future__ import annotations

from pathlib import Path
import subprocess
import sys

from sixbirds_event.audits.models import QuotientFeasibilityAudit
from sixbirds_event.schemas.common import SchemaKind
from sixbirds_event.schemas.event_package import EventPackageInstance
from sixbirds_event.schemas.result_note import ResultNote
from sixbirds_event.schemas.run_manifest import RunManifest
from sixbirds_event.search.models import (
    LensAxisCrossResolutionAdjudication,
    LensFamilyAdmissibility,
)
from sixbirds_event.validation import load_model, validate_file


CASE_DIR = Path(
    "experiments/instances/lens-axis/exp104_p6_row_all_n64_cross_res_k4_k20"
)
COMMITTED_AUDIT = CASE_DIR / "quotient-feasibility-audit.json"


def test_cross_resolution_assets_validate() -> None:
    audit = validate_file(COMMITTED_AUDIT, kind=SchemaKind.QUOTIENT_FEASIBILITY_AUDIT)
    assert audit.ok
    assert isinstance(audit.model, QuotientFeasibilityAudit)

    admissibility = validate_file(
        CASE_DIR / "lens-family-admissibility.json",
        kind=SchemaKind.LENS_FAMILY_ADMISSIBILITY,
    )
    assert admissibility.ok
    assert isinstance(admissibility.model, LensFamilyAdmissibility)

    package = validate_file(
        CASE_DIR / "event-package.json", kind=SchemaKind.EVENT_PACKAGE_INSTANCE
    )
    assert package.ok
    assert isinstance(package.model, EventPackageInstance)

    assert validate_file(
        CASE_DIR / "discovered-context-family.json",
        kind=SchemaKind.DISCOVERED_CONTEXT_FAMILY,
    ).ok
    assert validate_file(
        CASE_DIR / "shared-event-candidates.json",
        kind=SchemaKind.SHARED_EVENT_CANDIDATES,
    ).ok
    assert validate_file(
        CASE_DIR / "package-provenance.json",
        kind=SchemaKind.PACKAGE_PROVENANCE,
    ).ok


def test_cross_resolution_closure_runs_end_to_end(tmp_path: Path) -> None:
    from sixbirds_event.search.lens_axis_cross_resolution import (
        run_lens_axis_cross_resolution_closure,
    )

    artifacts = run_lens_axis_cross_resolution_closure(
        audit_path=COMMITTED_AUDIT,
        category="search",
        label="lens-cross-resolution-test",
        timestamp="2026-03-29T22:10:00Z",
        root=tmp_path,
    )

    adjudication = load_model(
        tmp_path / artifacts.adjudication_path,
        kind=SchemaKind.LENS_AXIS_CROSS_RESOLUTION_ADJUDICATION,
    )
    assert isinstance(adjudication, LensAxisCrossResolutionAdjudication)
    assert adjudication.final_adjudication == "accepted_as_lens_axis_strict_extension"
    assert adjudication.same_support_status is True
    assert adjudication.same_run_status is True
    assert adjudication.same_evaluation_regime_status is True
    assert adjudication.same_step_status is False
    assert adjudication.cross_resolution_status is True

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
    assert (output_dir / "cross-resolution-adjudication.json").exists()
    assert (output_dir / "cross-resolution-summary.json").exists()
    assert (output_dir / "cross-resolution-note.md").exists()
    outcome_files = [
        output_dir / "th4-accepted-obstruction.json",
        output_dir / "th4-rejected-out-of-contract.json",
    ]
    assert sum(path.exists() for path in outcome_files) == 1
    assert (output_dir / "th4-accepted-obstruction.json").exists()


def test_cli_smoke_cross_resolution_closure(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "sixbirds_event",
            "search",
            "close-lens-cross-resolution",
            COMMITTED_AUDIT.as_posix(),
            "--category",
            "search",
            "--label",
            "lens-cross-resolution-cli",
            "--timestamp",
            "2026-03-29T22:15:00Z",
            "--root",
            str(tmp_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "run_id=" in result.stdout
    assert "adjudication=" in result.stdout
    assert "summary=" in result.stdout
    assert "accepted_only_survivor_count=" in result.stdout
    assert "witness_classification=accepted_proposal_obstruction" in result.stdout
    assert "final_adjudication=accepted_as_lens_axis_strict_extension" in result.stdout
