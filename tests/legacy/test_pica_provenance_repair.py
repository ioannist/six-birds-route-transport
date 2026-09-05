from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from sixbirds_event.provenance.audit import audit_package_provenance
from sixbirds_event.provenance.models import (
    PICA_OBSERVABLE_ROW_FILTER_FIELDS,
    PackageProvenance,
    PicaSourceRef,
)
from sixbirds_event.reporting.pica_provenance_refresh_report import (
    write_pica_provenance_refresh_report,
)
from sixbirds_event.schemas.common import SchemaKind
from sixbirds_event.schemas.result_note import ResultNote
from sixbirds_event.schemas.run_manifest import RunManifest
from sixbirds_event.validation import load_model, validate_payload


PICA_PACKAGE_DIR = Path(
    "experiments/instances/discovered/pica-exp100-multiseed-package"
)
PICA_PACKAGE = PICA_PACKAGE_DIR / "event-package.json"
PICA_PROVENANCE = PICA_PACKAGE_DIR / "package-provenance.json"
PAIRMATCH_PACKAGE_DIR = Path(
    "experiments/instances/discovered/pica-exp110-pairmatch-package"
)
PAIRMATCH_PACKAGE = PAIRMATCH_PACKAGE_DIR / "event-package.json"
PAIRMATCH_PROVENANCE = PAIRMATCH_PACKAGE_DIR / "package-provenance.json"


# --- Case A: unknown row-filter fields are rejected ---


def test_pica_source_ref_detects_unknown_row_filter_fields() -> None:
    ref = PicaSourceRef(
        export_bundle_id="bundle1",
        campaign_id="campaign1",
        run_id="run1",
        observable_ledger_id="ledger1",
        closure_id="closure1",
        lens_id="lens1",
        level_id="level1",
        resolution_id="res1",
        preparation_id="prep1",
        protocol_id="proto1",
        step_index=0,
        source_row_filters={"context_id": "ctx_bad", "observation_label": "ok"},
    )
    unknown = ref.unknown_row_filter_fields
    assert unknown == ["context_id"]
    assert "observation_label" not in unknown


def test_pica_source_ref_empty_filters_yields_no_unknowns() -> None:
    ref = PicaSourceRef(
        export_bundle_id="bundle1",
        campaign_id="campaign1",
        run_id="run1",
        observable_ledger_id="ledger1",
        closure_id="closure1",
        lens_id="lens1",
        level_id="level1",
        resolution_id="res1",
        preparation_id="prep1",
        protocol_id="proto1",
        step_index=0,
        source_row_filters={},
    )
    assert ref.unknown_row_filter_fields == []


def test_unknown_row_filter_fields_counted_by_audit(tmp_path: Path) -> None:
    # Create a minimal event-package instance
    package_payload = {
        "instance_format_version": "event-package-instance.v1",
        "instance_id": "test_pkg",
        "contexts": [
            {
                "context_id": "ctx1",
                "atoms": [{"atom_id": "a1"}],
            }
        ],
        "events": [
            {
                "event_id": "evt1",
                "context_id": "ctx1",
                "atom_ids": ["a1"],
            }
        ],
        "equality_proposals": [],
        "audit": {"created_at": "2026-03-27T00:00:00Z"},
    }
    package_path = tmp_path / "event-package.json"
    package_path.write_text(json.dumps(package_payload), encoding="utf-8")

    # Create provenance with an invalid context_id row filter
    provenance_payload = {
        "provenance_format_version": "package-provenance.v1",
        "package_artifact": "event-package.json",
        "package_id": "test_pkg",
        "provenance_mode": "derived",
        "source_artifacts": {"test": "event-package.json"},
        "context_entries": [
            {
                "context_id": "ctx1",
                "origin_kind": "derived_context",
                "source_refs": [
                    {
                        "artifact": "event-package.json",
                        "source_kind": "derived_context",
                        "source_item_id": "ctx1",
                    }
                ],
            }
        ],
        "event_entries": [
            {
                "event_id": "evt1",
                "origin_kind": "derived_event",
                "source_refs": [
                    {
                        "artifact": "event-package.json",
                        "source_kind": "derived_event_basis",
                        "source_item_id": "evt1",
                    },
                    {
                        "artifact": "nonexistent-bundle.json",
                        "source_kind": "pica_export_bundle",
                        "pica_ref": {
                            "export_bundle_id": "bundle_x",
                            "campaign_id": "camp_x",
                            "run_id": "run_x",
                            "observable_ledger_id": "ledger_x",
                            "closure_id": "closure_x",
                            "lens_id": "lens_x",
                            "level_id": "level_x",
                            "resolution_id": "res_x",
                            "preparation_id": "prep_x",
                            "protocol_id": "proto_x",
                            "step_index": 0,
                            "source_row_filters": {"context_id": "ctx_bad_synthetic"},
                        },
                    },
                ],
            }
        ],
        "proposal_entries": [],
    }
    provenance_path = tmp_path / "package-provenance.json"
    provenance_path.write_text(json.dumps(provenance_payload), encoding="utf-8")

    result = audit_package_provenance(
        package_path=package_path,
        provenance_path=provenance_path,
        root=tmp_path,
    )

    assert result.unknown_row_filter_field_count == 1
    assert result.admissibility_classification != "admissible"


# --- Case B: repaired PICA-derived package audits as admissible ---


def test_committed_pica_exp100_package_audits_as_admissible() -> None:
    result = audit_package_provenance(
        package_path=PICA_PACKAGE,
        provenance_path=PICA_PROVENANCE,
    )
    assert result.admissibility_classification == "admissible", (
        f"Expected admissible, got {result.admissibility_classification}; "
        f"unsupported_events={result.unsupported_event_count}, "
        f"unresolved={result.unresolved_source_ref_count}, "
        f"unknown_filters={result.unknown_row_filter_field_count}"
    )
    assert result.unknown_row_filter_field_count == 0
    assert result.unsupported_event_count == 0
    assert result.unresolved_source_ref_count == 0


def test_committed_pica_exp110_pairmatch_package_audits_as_admissible() -> None:
    result = audit_package_provenance(
        package_path=PAIRMATCH_PACKAGE,
        provenance_path=PAIRMATCH_PROVENANCE,
    )
    assert result.admissibility_classification == "admissible", (
        f"Expected admissible, got {result.admissibility_classification}; "
        f"unsupported_events={result.unsupported_event_count}, "
        f"unresolved={result.unresolved_source_ref_count}, "
        f"unknown_filters={result.unknown_row_filter_field_count}"
    )
    assert result.unknown_row_filter_field_count == 0
    assert result.unsupported_event_count == 0
    assert result.unresolved_source_ref_count == 0


# --- Case C: no invalid filter keys remain in emitted package provenance ---


def test_committed_pica_provenance_has_no_invalid_filter_keys() -> None:
    provenance = load_model(PICA_PROVENANCE, kind=SchemaKind.PACKAGE_PROVENANCE)
    assert isinstance(provenance, PackageProvenance)
    for entry in provenance.event_entries:
        for ref in entry.source_refs:
            if ref.pica_ref is not None:
                unknown = ref.pica_ref.unknown_row_filter_fields
                assert unknown == [], (
                    f"Event {entry.event_id} has unknown row-filter fields: {unknown}"
                )


def test_repaired_emission_code_does_not_emit_context_id_filter() -> None:
    provenance = load_model(PICA_PROVENANCE, kind=SchemaKind.PACKAGE_PROVENANCE)
    assert isinstance(provenance, PackageProvenance)
    for entry in provenance.event_entries:
        for ref in entry.source_refs:
            if ref.pica_ref is not None:
                assert "context_id" not in ref.pica_ref.source_row_filters, (
                    f"context_id still in source_row_filters for event {entry.event_id}"
                )


def test_pairmatch_committed_provenance_has_no_invalid_filter_keys() -> None:
    provenance = load_model(PAIRMATCH_PROVENANCE, kind=SchemaKind.PACKAGE_PROVENANCE)
    assert isinstance(provenance, PackageProvenance)
    for entry in provenance.event_entries:
        for ref in entry.source_refs:
            if ref.pica_ref is not None:
                assert ref.pica_ref.unknown_row_filter_fields == []
                assert "context_id" not in ref.pica_ref.source_row_filters


# --- Case D: Refresh reporting helper works ---


def test_refresh_report_writes_required_artifacts(tmp_path: Path) -> None:
    report = write_pica_provenance_refresh_report(
        package_provenance_pairs=[
            (PICA_PACKAGE, PICA_PROVENANCE),
            (PAIRMATCH_PACKAGE, PAIRMATCH_PROVENANCE),
        ],
        category="results",
        label="pica-provenance-refresh-test",
        seed=0,
        timestamp="2026-03-27T14:00:00Z",
        root=tmp_path,
    )

    # Check all required files exist
    summary_path = tmp_path / report.summary_path
    note_path = tmp_path / report.note_path
    result_note_path = tmp_path / report.result_note_path
    manifest_path = tmp_path / report.manifest_path

    assert summary_path.exists()
    assert note_path.exists()
    assert result_note_path.exists()
    assert manifest_path.exists()

    # Validate summary
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["audited_package_count"] == 2
    assert summary["admissible_count"] == 2
    assert summary["total_unknown_row_filter_field_count"] == 0
    assert summary["systematic_failure_mode_present"] is False
    package_ids = {entry["package_id"] for entry in summary["audited_packages"]}
    assert package_ids == {
        "inst_pica_exp100_multiseed",
        "inst_pica_exp110_pairmatch",
    }

    # Validate result-note
    result_note_data = json.loads(result_note_path.read_text(encoding="utf-8"))
    rn_result = validate_payload(result_note_data, kind=SchemaKind.RESULT_NOTE)
    assert rn_result.ok
    assert isinstance(rn_result.model, ResultNote)

    # Validate manifest
    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    mn_result = validate_payload(manifest_data, kind=SchemaKind.RUN_MANIFEST)
    assert mn_result.ok
    assert isinstance(mn_result.model, RunManifest)

    # Check note content
    note_text = note_path.read_text(encoding="utf-8")
    assert "PICA Provenance Refresh Report" in note_text
    assert "admissible" in note_text


# --- Canonical whitelist sanity ---


def test_canonical_whitelist_covers_all_pica_observable_row_fields() -> None:
    from sixbirds_event.pica_bridge.models import PicaObservableRow

    row_fields = set(PicaObservableRow.model_fields.keys()) - {"observation_payload"}
    assert row_fields == PICA_OBSERVABLE_ROW_FILTER_FIELDS, (
        f"Whitelist mismatch: "
        f"in row but not whitelist: {row_fields - PICA_OBSERVABLE_ROW_FILTER_FIELDS}, "
        f"in whitelist but not row: {PICA_OBSERVABLE_ROW_FILTER_FIELDS - row_fields}"
    )


# --- CLI smoke ---


def test_cli_smoke_pica_provenance_refresh(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "sixbirds_event",
            "audits",
            "pica-provenance-refresh",
            f"{PICA_PACKAGE}:{PICA_PROVENANCE}",
            f"{PAIRMATCH_PACKAGE}:{PAIRMATCH_PROVENANCE}",
            "--category",
            "results",
            "--label",
            "pica-provenance-refresh-smoke",
            "--timestamp",
            "2026-03-27T14:00:00Z",
            "--root",
            str(tmp_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"CLI failed: {result.stderr}"
    assert "run_id=" in result.stdout
    assert "summary=" in result.stdout
    assert (
        "package=inst_pica_exp100_multiseed classification=admissible" in result.stdout
    )
    assert (
        "package=inst_pica_exp110_pairmatch classification=admissible" in result.stdout
    )
    assert "unknown_row_filter_fields=0" in result.stdout
