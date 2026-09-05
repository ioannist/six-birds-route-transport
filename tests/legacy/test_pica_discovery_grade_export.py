from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from sixbirds_event.pica_bridge.discovery_readiness import (
    analyze_pica_discovery_readiness,
)
from sixbirds_event.pica_bridge.ingest import load_pica_export_bundle
from sixbirds_event.pica_bridge.pilot import run_pica_pilot_campaign
from sixbirds_event.schemas.common import SchemaKind
from sixbirds_event.schemas.result_note import ResultNote
from sixbirds_event.schemas.run_manifest import RunManifest
from sixbirds_event.validation import load_model, validate_file


DISCOVERY_GRADE_CONFIG = Path("experiments/configs/pica/pilot-discovery-grade.json")
COMMITTED_DISCOVERY_BUNDLE = Path(
    "experiments/contracts/pica/pilot/exp120_discovery_grade/pica-export-bundle.json"
)
COMMITTED_AGGREGATE_BUNDLE = Path(
    "experiments/contracts/pica/pilot/exp100_multiseed/pica-export-bundle.json"
)
VENDOR_PATH = Path("vendor/six-birds-pica")


def _vendor_status_snapshot() -> str:
    result = subprocess.run(
        [
            "git",
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
            "--",
            VENDOR_PATH.as_posix(),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout


def test_committed_discovery_grade_assets_validate() -> None:
    assert validate_file(DISCOVERY_GRADE_CONFIG, kind=SchemaKind.PICA_PILOT_CAMPAIGN).ok
    assert validate_file(
        COMMITTED_DISCOVERY_BUNDLE, kind=SchemaKind.PICA_EXPORT_BUNDLE
    ).ok
    observable_ledger = Path(
        "experiments/contracts/pica/pilot/exp120_discovery_grade/pica-observable-ledger.json"
    )
    assert validate_file(observable_ledger, kind=SchemaKind.PICA_OBSERVABLE_LEDGER).ok
    payload = json.loads(observable_ledger.read_text(encoding="utf-8"))
    assert payload["observation_granularity"] == "per_trajectory"
    assert payload["cooccurrence_scope"] == "within_run_and_trajectory"
    assert payload["supports_structural_probe_conditioning"] is True


def test_discovery_grade_pilot_runs_and_bundle_resolves(tmp_path: Path) -> None:
    before_status = _vendor_status_snapshot()
    artifacts = run_pica_pilot_campaign(
        config_path=DISCOVERY_GRADE_CONFIG,
        category="results",
        label="pica-discovery-grade-test",
        timestamp="2026-03-28T02:00:00Z",
        root=tmp_path,
    )
    after_status = _vendor_status_snapshot()

    assert before_status == after_status
    assert validate_file(
        tmp_path / artifacts.summary_path,
        kind=SchemaKind.PICA_PILOT_RESULT,
    ).ok

    summary = json.loads(
        (tmp_path / artifacts.summary_path).read_text(encoding="utf-8")
    )
    assert summary["pica_export_mode"] == "discovery_grade_per_trajectory"
    assert summary["observation_granularity"] == "per_trajectory"
    assert summary["cooccurrence_scope"] == "within_run_and_trajectory"
    assert summary["supports_structural_probe_conditioning"] is True

    resolved = load_pica_export_bundle(
        tmp_path / artifacts.export_bundle_path,
        repo_root=tmp_path,
    )
    ledger = next(iter(resolved.observable_ledgers.values()))
    assert ledger.observation_granularity == "per_trajectory"
    assert ledger.supports_structural_probe_conditioning is True
    assert ledger.trajectory_count >= 1


def test_readiness_analyzer_marks_discovery_grade_ready_and_aggregate_inadequate(
    tmp_path: Path,
) -> None:
    ready = analyze_pica_discovery_readiness(
        bundle_path=COMMITTED_DISCOVERY_BUNDLE,
        category="results",
        label="pica-discovery-grade-ready",
        timestamp="2026-03-28T02:05:00Z",
        root=tmp_path,
    )
    assert validate_file(
        tmp_path / ready.summary_path,
        kind=SchemaKind.PICA_DISCOVERY_READINESS,
    ).ok
    assert ready.summary.readiness_classification == "discovery_grade_ready"
    assert ready.summary.context_pairs_with_shared_trajectory_support > 0
    assert ready.summary.context_pairs_with_probe_conditioning_potential > 0

    inadequate = analyze_pica_discovery_readiness(
        bundle_path=COMMITTED_AGGREGATE_BUNDLE,
        category="results",
        label="pica-discovery-grade-inadequate",
        timestamp="2026-03-28T02:06:00Z",
        root=tmp_path,
    )
    assert inadequate.summary.readiness_classification == "discovery_grade_inadequate"
    assert inadequate.summary.pica_export_mode == "aggregate_summary"

    result_note = load_model(
        tmp_path / ready.result_note_path,
        kind=SchemaKind.RESULT_NOTE,
    )
    assert isinstance(result_note, ResultNote)
    manifest = load_model(
        tmp_path / ready.manifest_path,
        kind=SchemaKind.RUN_MANIFEST,
    )
    assert isinstance(manifest, RunManifest)
    assert manifest.metadata["analysis_kind"] == "pica_discovery_readiness"


def test_cli_smoke_runs_discovery_grade_pilot_and_readiness(tmp_path: Path) -> None:
    before_status = _vendor_status_snapshot()
    pilot = subprocess.run(
        [
            sys.executable,
            "-m",
            "sixbirds_event",
            "pica",
            "run-pilot",
            DISCOVERY_GRADE_CONFIG.as_posix(),
            "--category",
            "results",
            "--label",
            "pica-discovery-grade-cli",
            "--timestamp",
            "2026-03-28T02:10:00Z",
            "--root",
            str(tmp_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    after_status = _vendor_status_snapshot()
    assert pilot.returncode == 0
    assert before_status == after_status
    assert "pica_export_mode=discovery_grade_per_trajectory" in pilot.stdout
    assert "observation_granularity=per_trajectory" in pilot.stdout

    readiness = subprocess.run(
        [
            sys.executable,
            "-m",
            "sixbirds_event",
            "pica",
            "analyze-discovery-readiness",
            COMMITTED_DISCOVERY_BUNDLE.as_posix(),
            "--category",
            "results",
            "--label",
            "pica-discovery-readiness-cli",
            "--timestamp",
            "2026-03-28T02:11:00Z",
            "--root",
            str(tmp_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert readiness.returncode == 0
    assert "readiness_classification=discovery_grade_ready" in readiness.stdout
    assert "trajectory_count=" in readiness.stdout
