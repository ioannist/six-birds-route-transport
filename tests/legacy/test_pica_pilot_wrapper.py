from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from sixbirds_event.pica_bridge.ingest import load_pica_export_bundle
from sixbirds_event.pica_bridge.pilot import run_pica_pilot_campaign
from sixbirds_event.schemas.common import SchemaKind
from sixbirds_event.schemas.result_note import ResultNote
from sixbirds_event.schemas.run_manifest import RunManifest
from sixbirds_event.validation import load_model, validate_file


PILOT_CONFIG = Path("experiments/configs/pica/pilot-campaign.json")
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


def test_pica_pilot_campaign_and_result_formats_validate(tmp_path: Path) -> None:
    assert validate_file(PILOT_CONFIG, kind=SchemaKind.PICA_PILOT_CAMPAIGN).ok

    artifacts = run_pica_pilot_campaign(
        config_path=PILOT_CONFIG,
        category="results",
        label="pica-pilot-test-validate",
        timestamp="2026-03-26T14:00:00Z",
        root=tmp_path,
    )
    assert validate_file(
        tmp_path / artifacts.summary_path,
        kind=SchemaKind.PICA_PILOT_RESULT,
    ).ok


def test_committed_pica_pilot_runs_end_to_end_and_bundle_resolves(
    tmp_path: Path,
) -> None:
    before_status = _vendor_status_snapshot()
    artifacts = run_pica_pilot_campaign(
        config_path=PILOT_CONFIG,
        category="results",
        label="pica-pilot-test",
        timestamp="2026-03-26T14:05:00Z",
        root=tmp_path,
    )
    after_status = _vendor_status_snapshot()

    assert before_status == after_status

    summary = json.loads(
        (tmp_path / artifacts.summary_path).read_text(encoding="utf-8")
    )
    assert summary["success"] is True
    assert summary["bridge_validation_status"] == "validated"

    for relative_path in [
        artifacts.export_bundle_path,
        artifacts.campaign_export_path,
        artifacts.run_ledger_path,
        artifacts.closure_catalog_path,
        artifacts.observable_ledger_path,
    ]:
        assert not Path(relative_path).is_absolute()
        assert (tmp_path / relative_path).exists()

    resolved = load_pica_export_bundle(
        tmp_path / artifacts.export_bundle_path, repo_root=tmp_path
    )
    assert len(resolved.campaigns) >= 1
    assert len(resolved.runs) >= 1
    assert len(resolved.observable_ledgers) >= 1

    result_note = load_model(
        tmp_path / artifacts.result_note_path,
        kind=SchemaKind.RESULT_NOTE,
    )
    assert isinstance(result_note, ResultNote)
    manifest = load_model(
        tmp_path / artifacts.manifest_path,
        kind=SchemaKind.RUN_MANIFEST,
    )
    assert isinstance(manifest, RunManifest)
    assert manifest.metadata["analysis_kind"] == "pica_pilot_wrapper"
    assert "export_bundle" in manifest.output_artifacts


def test_cli_smoke_runs_pica_pilot(tmp_path: Path) -> None:
    before_status = _vendor_status_snapshot()
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "sixbirds_event",
            "pica",
            "run-pilot",
            PILOT_CONFIG.as_posix(),
            "--category",
            "results",
            "--label",
            "pica-pilot-cli",
            "--timestamp",
            "2026-03-26T14:10:00Z",
            "--root",
            str(tmp_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    after_status = _vendor_status_snapshot()

    assert result.returncode == 0
    assert before_status == after_status
    assert "run_id=" in result.stdout
    assert "summary=" in result.stdout
    assert "export_bundle=" in result.stdout
    assert "campaign_count=" in result.stdout
    assert "observable_ledger_count=" in result.stdout
