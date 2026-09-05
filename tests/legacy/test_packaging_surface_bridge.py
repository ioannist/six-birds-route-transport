from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from sixbirds_event.pica_bridge.ingest import load_pica_export_bundle
from sixbirds_event.pica_bridge.packaging_surface import resolve_pica_packaging_surface
from sixbirds_event.provenance.audit import audit_package_provenance
from sixbirds_event.reporting.pica_packaging_surface_report import (
    write_pica_packaging_surface_report,
)
from sixbirds_event.schemas.common import SchemaKind
from sixbirds_event.schemas.result_note import ResultNote
from sixbirds_event.schemas.run_manifest import RunManifest
from sixbirds_event.validation import load_model, validate_file


EXAMPLES_DIR = Path("experiments/contracts/pica/examples")
COMMITTED_DIR = Path("experiments/contracts/pica/pilot/exp130_packaging_surface")

OPERATOR_CATALOG = EXAMPLES_DIR / "pica-packaging-operator-catalog.json"
SELECTION_LEDGER = EXAMPLES_DIR / "pica-packaging-selection-ledger.json"
PACKAGING_SURFACE = EXAMPLES_DIR / "pica-packaging-surface.json"

COMMITTED_BUNDLE = COMMITTED_DIR / "pica-export-bundle.json"
COMMITTED_PACKAGE = COMMITTED_DIR / "packaging-backed-event-package.json"
COMMITTED_PROVENANCE = COMMITTED_DIR / "packaging-backed-provenance.json"


def test_packaging_surface_formats_validate() -> None:
    assert validate_file(
        OPERATOR_CATALOG, kind=SchemaKind.PICA_PACKAGING_OPERATOR_CATALOG
    ).ok
    assert validate_file(
        SELECTION_LEDGER, kind=SchemaKind.PICA_PACKAGING_SELECTION_LEDGER
    ).ok
    assert validate_file(PACKAGING_SURFACE, kind=SchemaKind.PICA_PACKAGING_SURFACE).ok


def test_committed_packaging_surface_bundle_imports_and_indexes() -> None:
    resolved = load_pica_export_bundle(COMMITTED_BUNDLE)
    assert len(resolved.packaging_operator_catalogs) == 1
    assert len(resolved.packaging_selection_ledgers) == 1

    source_index = resolved.to_source_index_payload()
    assert source_index["packaging_sources"] == ["p5_from_p4"]
    assert source_index["packaging_operator_ids"] == ["packaging_operator_p5_from_p4"]
    assert source_index["packaging_family_ids"] == ["packaging_family_p5"]

    packaging_surface = resolve_pica_packaging_surface(COMMITTED_BUNDLE)
    assert packaging_surface.surface.distinct_packaging_operator_count >= 1
    assert packaging_surface.surface.distinct_packaging_family_count >= 1
    assert packaging_surface.surface.source_counts["p5_from_p4"] > 0
    assert (
        packaging_surface.surface.selected_operator_counts[
            "packaging_operator_p5_from_p4"
        ]
        > 0
    )


def test_packaging_surface_report_and_packaging_provenance_audit_succeed(
    tmp_path: Path,
) -> None:
    report = write_pica_packaging_surface_report(
        bundle_path=COMMITTED_BUNDLE,
        package_path=COMMITTED_PACKAGE,
        provenance_path=COMMITTED_PROVENANCE,
        category="results",
        label="packaging-surface-report",
        seed=0,
        timestamp="2026-03-28T23:40:00Z",
        root=tmp_path,
    )

    summary = load_model(
        tmp_path / report.summary_path,
        kind=SchemaKind.PICA_PACKAGING_SURFACE,
    )
    assert summary.distinct_packaging_operator_count == 1
    assert summary.distinct_packaging_family_count == 1

    source_index = json.loads(
        (tmp_path / report.source_index_path).read_text(encoding="utf-8")
    )
    assert source_index["packaging_sources"] == ["p5_from_p4"]

    audit_summary = load_model(
        tmp_path / report.provenance_audit_summary_path,
        kind=SchemaKind.PROVENANCE_AUDIT_RESULT,
    )
    assert audit_summary.admissibility_classification == "admissible"

    direct_audit = audit_package_provenance(
        package_path=COMMITTED_PACKAGE,
        provenance_path=COMMITTED_PROVENANCE,
    )
    assert direct_audit.admissibility_classification == "admissible"

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
    assert manifest.metadata["analysis_kind"] == "pica_packaging_surface_inspect"


def test_cli_smoke_inspect_packaging_surface(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "sixbirds_event",
            "pica",
            "inspect-packaging-surface",
            COMMITTED_BUNDLE.as_posix(),
            "--package",
            COMMITTED_PACKAGE.as_posix(),
            "--provenance",
            COMMITTED_PROVENANCE.as_posix(),
            "--category",
            "results",
            "--label",
            "packaging-surface-cli",
            "--timestamp",
            "2026-03-28T23:45:00Z",
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
    assert "source_index=" in result.stdout
    assert "admissibility_classification=admissible" in result.stdout
    assert "distinct_packaging_operator_count=1" in result.stdout
    assert "distinct_packaging_family_count=1" in result.stdout
