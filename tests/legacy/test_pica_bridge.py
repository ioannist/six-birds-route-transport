from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from sixbirds_event.pica_bridge.ingest import load_pica_export_bundle
from sixbirds_event.provenance.audit import audit_package_provenance
from sixbirds_event.reporting.pica_bridge_report import write_pica_bridge_report
from sixbirds_event.schemas.common import SchemaKind
from sixbirds_event.schemas.result_note import ResultNote
from sixbirds_event.schemas.run_manifest import RunManifest
from sixbirds_event.validation import load_model, validate_file


EXAMPLES_DIR = Path("experiments/contracts/pica/examples")
BUNDLE = EXAMPLES_DIR / "pica-export-bundle.json"
CAMPAIGN = EXAMPLES_DIR / "pica-campaign-export.json"
RUN_LEDGER = EXAMPLES_DIR / "pica-run-ledger.json"
CLOSURE_CATALOG = EXAMPLES_DIR / "pica-closure-catalog.json"
OBSERVABLE_LEDGER = EXAMPLES_DIR / "pica-observable-ledger.json"
PICA_BACKED_PACKAGE = EXAMPLES_DIR / "pica-backed-event-package.json"
PICA_BACKED_PROVENANCE = EXAMPLES_DIR / "pica-backed-provenance.json"


def test_all_pica_export_formats_validate() -> None:
    assert validate_file(BUNDLE, kind=SchemaKind.PICA_EXPORT_BUNDLE).ok
    assert validate_file(CAMPAIGN, kind=SchemaKind.PICA_CAMPAIGN_EXPORT).ok
    assert validate_file(RUN_LEDGER, kind=SchemaKind.PICA_RUN_LEDGER).ok
    assert validate_file(CLOSURE_CATALOG, kind=SchemaKind.PICA_CLOSURE_CATALOG).ok
    assert validate_file(OBSERVABLE_LEDGER, kind=SchemaKind.PICA_OBSERVABLE_LEDGER).ok


def test_bundle_import_builds_source_index() -> None:
    resolved = load_pica_export_bundle(BUNDLE)
    assert resolved.export_bundle.export_bundle_id == "pica_export_bundle_example_v1"
    assert set(resolved.campaigns) == {"campaign_example_v1"}
    assert set(resolved.runs) == {"run_triadic_branch_seed123"}
    assert set(resolved.observable_ledgers) == {
        "observable_ledger_run_triadic_branch_seed123"
    }
    rows = resolved.filter_rows(
        run_id="run_triadic_branch_seed123",
        protocol_step_id="protocol_branch_hold_hold_step_0",
        observation_label="obs_left_A",
    )
    assert len(rows) == 1
    assert rows[0].route_label == "route_left"
    source_index = resolved.to_source_index_payload()
    assert source_index["closure_ids"] == ["closure_branch_record"]
    assert source_index["lens_ids"] == ["lens_record_main"]
    assert source_index["protocol_step_ids"] == [
        "protocol_branch_hold_hold_step_0",
        "protocol_branch_hold_hold_step_1",
    ]


def test_pica_backed_example_validates_and_audits_as_admissible() -> None:
    assert validate_file(PICA_BACKED_PACKAGE, kind=SchemaKind.EVENT_PACKAGE_INSTANCE).ok
    provenance_result = validate_file(
        PICA_BACKED_PROVENANCE, kind=SchemaKind.PACKAGE_PROVENANCE
    )
    assert provenance_result.ok

    audit = audit_package_provenance(
        package_path=PICA_BACKED_PACKAGE,
        provenance_path=PICA_BACKED_PROVENANCE,
    )
    assert audit.admissibility_classification == "admissible"
    assert audit.unresolved_source_ref_count == 0


def test_unresolved_pica_reference_is_flagged_honestly(tmp_path: Path) -> None:
    payload = json.loads(PICA_BACKED_PROVENANCE.read_text(encoding="utf-8"))
    payload["context_entries"][0]["source_refs"][0]["pica_ref"]["closure_id"] = (
        "missing_closure"
    )
    bad_path = tmp_path / "bad-provenance.json"
    bad_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    audit = audit_package_provenance(
        package_path=PICA_BACKED_PACKAGE,
        provenance_path=bad_path,
        root=tmp_path,
    )
    assert audit.admissibility_classification != "admissible"
    assert audit.unresolved_source_ref_count > 0


def test_pica_bridge_report_writes_required_outputs(tmp_path: Path) -> None:
    report = write_pica_bridge_report(
        bundle_path=BUNDLE,
        package_path=PICA_BACKED_PACKAGE,
        provenance_path=PICA_BACKED_PROVENANCE,
        category="results",
        label="pica-bundle-audit",
        seed=0,
        timestamp="2026-03-26T11:00:00Z",
        root=tmp_path,
    )

    summary = json.loads((tmp_path / report.summary_path).read_text(encoding="utf-8"))
    assert summary["campaign_count"] == 1
    assert summary["run_count"] == 1
    assert summary["closure_count"] == 1
    assert summary["lens_count"] == 1
    assert summary["observable_ledger_count"] == 1
    assert summary["admissibility_classification"] == "admissible"

    source_index = json.loads(
        (tmp_path / report.source_index_path).read_text(encoding="utf-8")
    )
    assert source_index["run_ids"] == ["run_triadic_branch_seed123"]
    assert source_index["observable_ledger_ids"] == [
        "observable_ledger_run_triadic_branch_seed123"
    ]

    audit_summary = load_model(
        tmp_path / report.provenance_audit_summary_path,
        kind=SchemaKind.PROVENANCE_AUDIT_RESULT,
    )
    assert audit_summary.admissibility_classification == "admissible"
    result_note = load_model(
        tmp_path / report.result_note_path,
        kind=SchemaKind.RESULT_NOTE,
    )
    assert isinstance(result_note, ResultNote)
    manifest = load_model(
        tmp_path / report.manifest_path,
        kind=SchemaKind.RUN_MANIFEST,
    )
    assert isinstance(manifest, RunManifest)
    assert manifest.metadata["analysis_kind"] == "pica_bridge_inspect"


def test_cli_smoke_bundle_only_and_bundle_with_audit(tmp_path: Path) -> None:
    bundle_only = subprocess.run(
        [
            sys.executable,
            "-m",
            "sixbirds_event",
            "pica",
            "inspect-bundle",
            BUNDLE.as_posix(),
            "--category",
            "results",
            "--label",
            "pica-bundle-inspect",
            "--timestamp",
            "2026-03-26T12:00:00Z",
            "--root",
            str(tmp_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    bundle_with_audit = subprocess.run(
        [
            sys.executable,
            "-m",
            "sixbirds_event",
            "pica",
            "inspect-bundle",
            BUNDLE.as_posix(),
            "--package",
            PICA_BACKED_PACKAGE.as_posix(),
            "--provenance",
            PICA_BACKED_PROVENANCE.as_posix(),
            "--category",
            "results",
            "--label",
            "pica-bundle-audit",
            "--timestamp",
            "2026-03-26T12:05:00Z",
            "--root",
            str(tmp_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert bundle_only.returncode == 0
    assert "run_id=" in bundle_only.stdout
    assert "summary=" in bundle_only.stdout
    assert "source_index=" in bundle_only.stdout
    assert "campaign_count=1" in bundle_only.stdout
    assert "observable_ledger_count=1" in bundle_only.stdout

    assert bundle_with_audit.returncode == 0
    assert "run_id=" in bundle_with_audit.stdout
    assert "provenance_audit_summary=" in bundle_with_audit.stdout
    assert "admissibility_classification=admissible" in bundle_with_audit.stdout
