from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from sixbirds_event.provenance.audit import write_provenance_audit_report
from sixbirds_event.provenance.models import PackageProvenance, ProvenanceAuditResult
from sixbirds_event.schemas.common import SchemaKind
from sixbirds_event.schemas.result_note import ResultNote
from sixbirds_event.schemas.run_manifest import RunManifest
from sixbirds_event.validation import load_model, validate_payload


CLASSICAL_INSTANCE = Path(
    "experiments/instances/benchmarks/classical-master-test/instance.json"
)
CLASSICAL_PROVENANCE = Path(
    "experiments/instances/benchmarks/classical-master-test/provenance.json"
)
PARITY_INSTANCE = Path(
    "experiments/instances/benchmarks/parity-context-witness/instance.json"
)
PARITY_PROVENANCE = Path(
    "experiments/instances/benchmarks/parity-context-witness/provenance.json"
)
DISCOVERED_DIR = Path("experiments/instances/discovered/stochastic-two-state-package")
DISCOVERED_INSTANCE = DISCOVERED_DIR / "event-package.json"
DISCOVERED_PROVENANCE = DISCOVERED_DIR / "provenance.json"
SMUGGLED_INSTANCE = Path(
    "experiments/instances/redteam/hidden-label-smuggling/smuggled-instance.json"
)


def test_package_provenance_format_validates() -> None:
    payload = json.loads(CLASSICAL_PROVENANCE.read_text(encoding="utf-8"))
    result = validate_payload(payload, kind=SchemaKind.PACKAGE_PROVENANCE)
    assert result.ok
    assert result.kind == SchemaKind.PACKAGE_PROVENANCE
    assert isinstance(result.model, PackageProvenance)


def test_provenance_audit_result_format_validates(tmp_path: Path) -> None:
    report = write_provenance_audit_report(
        package_path=CLASSICAL_INSTANCE,
        provenance_path=CLASSICAL_PROVENANCE,
        category="results",
        label="provenance-classical",
        seed=0,
        timestamp="2026-03-26T00:00:00Z",
        root=tmp_path,
    )
    payload = json.loads((tmp_path / report.summary_path).read_text(encoding="utf-8"))
    result = validate_payload(payload, kind=SchemaKind.PROVENANCE_AUDIT_RESULT)
    assert result.ok
    assert result.kind == SchemaKind.PROVENANCE_AUDIT_RESULT
    assert isinstance(result.model, ProvenanceAuditResult)


def test_provenance_audit_classifies_committed_cases(tmp_path: Path) -> None:
    classical = write_provenance_audit_report(
        package_path=CLASSICAL_INSTANCE,
        provenance_path=CLASSICAL_PROVENANCE,
        category="results",
        label="provenance-classical",
        seed=0,
        timestamp="2026-03-26T00:00:00Z",
        root=tmp_path,
    )
    parity = write_provenance_audit_report(
        package_path=PARITY_INSTANCE,
        provenance_path=PARITY_PROVENANCE,
        category="results",
        label="provenance-parity",
        seed=0,
        timestamp="2026-03-26T00:05:00Z",
        root=tmp_path,
    )
    discovered = write_provenance_audit_report(
        package_path=DISCOVERED_INSTANCE,
        provenance_path=DISCOVERED_PROVENANCE,
        category="results",
        label="provenance-discovered",
        seed=0,
        timestamp="2026-03-26T00:10:00Z",
        root=tmp_path,
    )
    smuggled = write_provenance_audit_report(
        package_path=SMUGGLED_INSTANCE,
        provenance_path=None,
        category="results",
        label="provenance-smuggled",
        seed=0,
        timestamp="2026-03-26T00:15:00Z",
        root=tmp_path,
    )

    assert classical.result.admissibility_classification == "admissible"
    assert parity.result.admissibility_classification == "admissible"
    assert discovered.result.admissibility_classification == "admissible"
    assert smuggled.result.admissibility_classification == "unsupported"
    assert smuggled.result.notes == ["no_provenance_manifest_supplied"]
    assert smuggled.result.suspicious_refinement_flags

    summary = load_model(
        tmp_path / classical.summary_path,
        kind=SchemaKind.PROVENANCE_AUDIT_RESULT,
    )
    assert isinstance(summary, ProvenanceAuditResult)
    result_note = load_model(
        tmp_path / classical.result_note_path,
        kind=SchemaKind.RESULT_NOTE,
    )
    assert isinstance(result_note, ResultNote)
    manifest = load_model(
        tmp_path / classical.manifest_path,
        kind=SchemaKind.RUN_MANIFEST,
    )
    assert isinstance(manifest, RunManifest)
    assert manifest.metadata["analysis_kind"] == "provenance_audit"
    assert manifest.output_artifacts == {
        "note": "results/results/20260326T000000Z--provenance_classical/provenance-audit-note.md",
        "result_note": "results/results/20260326T000000Z--provenance_classical/result-note.json",
        "summary": "results/results/20260326T000000Z--provenance_classical/provenance-audit-summary.json",
    }

    note = (tmp_path / classical.note_path).read_text(encoding="utf-8")
    assert "Coverage summary" in note
    assert "Final admissibility classification" in note
    assert "`admissible`" in note


def test_cli_smoke_provenance_audit_handles_admissible_and_unsupported(
    tmp_path: Path,
) -> None:
    admissible = subprocess.run(
        [
            sys.executable,
            "-m",
            "sixbirds_event",
            "audits",
            "provenance",
            CLASSICAL_INSTANCE.as_posix(),
            "--provenance",
            CLASSICAL_PROVENANCE.as_posix(),
            "--category",
            "results",
            "--label",
            "provenance-classical",
            "--timestamp",
            "2026-03-26T00:00:00Z",
            "--root",
            str(tmp_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    unsupported = subprocess.run(
        [
            sys.executable,
            "-m",
            "sixbirds_event",
            "audits",
            "provenance",
            SMUGGLED_INSTANCE.as_posix(),
            "--category",
            "results",
            "--label",
            "provenance-smuggled",
            "--timestamp",
            "2026-03-26T00:05:00Z",
            "--root",
            str(tmp_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert admissible.returncode == 0
    assert "run_id=" in admissible.stdout
    assert "summary=" in admissible.stdout
    assert "manifest=" in admissible.stdout
    assert "admissibility_classification=admissible" in admissible.stdout

    assert unsupported.returncode == 0
    assert "run_id=" in unsupported.stdout
    assert "summary=" in unsupported.stdout
    assert "manifest=" in unsupported.stdout
    assert "admissibility_classification=unsupported" in unsupported.stdout
