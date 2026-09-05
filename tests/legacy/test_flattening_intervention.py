from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from sixbirds_event.reporting.flattening_report import (
    write_flattening_intervention_report,
)
from sixbirds_event.schemas.common import SchemaKind
from sixbirds_event.schemas.result_note import ResultNote
from sixbirds_event.schemas.run_manifest import RunManifest
from sixbirds_event.validation import load_model, validate_payload


INTERVENTION_DIR = Path(
    "experiments/instances/interventions/flattening-completion-branch"
)
INTERVENTION = INTERVENTION_DIR / "intervention.json"
SOURCE_CONFIG = Path("experiments/configs/substrates/flattenable-branch.json")
RUNBOOK = Path("docs/runbooks/flattening-intervention.md")


def test_flattening_intervention_format_validates() -> None:
    payload = json.loads(INTERVENTION.read_text(encoding="utf-8"))
    result = validate_payload(payload, kind=SchemaKind.FLATTENING_INTERVENTION)
    assert result.ok
    assert result.kind == SchemaKind.FLATTENING_INTERVENTION


def test_committed_flattening_assets_are_reproducible_repo_files() -> None:
    intervention = load_model(INTERVENTION, kind=SchemaKind.FLATTENING_INTERVENTION)
    config = load_model(SOURCE_CONFIG, kind=SchemaKind.SUBSTRATE_CONFIG)

    assert intervention.intervention_id == "flattening_completion_branch"
    assert intervention.before_protocol_id == "branch_only"
    assert config.config_id == "cfg_flattenable_branch"
    assert RUNBOOK.exists()


def test_flattening_intervention_runner_writes_bundle_and_comparison(
    tmp_path: Path,
) -> None:
    artifacts = write_flattening_intervention_report(
        intervention_path=INTERVENTION.as_posix(),
        category="interventions",
        label="flattening-completion-branch",
        seed=0,
        timestamp="2026-03-25T00:00:00Z",
        root=tmp_path,
    )

    result_note = load_model(
        tmp_path / artifacts.result_note_path,
        kind=SchemaKind.RESULT_NOTE,
    )
    manifest = load_model(
        tmp_path / artifacts.manifest_path,
        kind=SchemaKind.RUN_MANIFEST,
    )

    assert isinstance(result_note, ResultNote)
    assert isinstance(manifest, RunManifest)

    summary_payload = json.loads(
        (tmp_path / artifacts.summary_path).read_text(encoding="utf-8")
    )
    assert summary_payload["before"]["exact_structural_feasible_hard_only"] is True
    assert summary_payload["before"]["gpd_str"] == 0.0
    assert summary_payload["before"]["gpd_stat_status"] == "solved"
    assert summary_payload["before"]["gpd_stat"] == 0.0
    assert summary_payload["before"]["rm_status"] == "scored"
    assert summary_payload["before"]["overall_rm"] == 1.0

    assert summary_payload["after"]["exact_structural_feasible_hard_only"] is True
    assert summary_payload["after"]["gpd_str"] == 0.0
    assert summary_payload["after"]["gpd_stat_status"] == "solved"
    assert summary_payload["after"]["gpd_stat"] is not None
    assert summary_payload["after"]["rm_status"] == "scored"
    assert summary_payload["after"]["overall_rm"] == 0.0

    assert summary_payload["deltas"]["gpd_str_delta"] == 0.0
    assert summary_payload["deltas"]["overall_rm_delta"] == -1.0
    assert summary_payload["flattening_outcome"] == "repairable"
    assert summary_payload["status_counts"] == {
        "after_gpd_stat_status": "solved",
        "after_rm_status": "scored",
        "before_gpd_stat_status": "solved",
        "before_rm_status": "scored",
    }

    assert manifest.output_artifacts == {
        "after_route_trace": "results/interventions/20260325T000000Z--flattening_completion_branch/after-route-trace.json",
        "before_route_trace": "results/interventions/20260325T000000Z--flattening_completion_branch/before-route-trace.json",
        "flattened_config": "results/interventions/20260325T000000Z--flattening_completion_branch/flattened-config.json",
        "note": "results/interventions/20260325T000000Z--flattening_completion_branch/comparison-note.md",
        "result_note": "results/interventions/20260325T000000Z--flattening_completion_branch/result-note.json",
        "summary": "results/interventions/20260325T000000Z--flattening_completion_branch/comparison-summary.json",
    }
    assert manifest.metadata["analysis_kind"] == "flattening_intervention"
    assert manifest.metadata["flattening_outcome"] == "repairable"

    note = (tmp_path / artifacts.note_path).read_text(encoding="utf-8")
    assert "Flattening outcome" in note
    assert "`repairable`" in note
    assert "RM is diagnostic-only" in note
    assert (
        "unsolved / insufficient-data / not_applicable statuses are preserved explicitly"
        in note
    )


def test_cli_smoke_works_on_committed_flattening_asset(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "sixbirds_event",
            "interventions",
            "flattening",
            INTERVENTION.as_posix(),
            "--category",
            "interventions",
            "--label",
            "flattening-completion-branch",
            "--timestamp",
            "2026-03-25T00:00:00Z",
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
    assert "note=" in result.stdout
    assert "result_note=" in result.stdout
    assert "manifest=" in result.stdout
    assert "before_gpd_str=0.0" in result.stdout
    assert "after_gpd_str=0.0" in result.stdout
    assert "before_gpd_stat_status=solved" in result.stdout
    assert "after_gpd_stat_status=solved" in result.stdout
    assert "before_rm_status=scored" in result.stdout
    assert "after_rm_status=scored" in result.stdout
    assert "before_overall_rm=1.0" in result.stdout
    assert "after_overall_rm=0.0" in result.stdout
    assert "conclusion=repairable" in result.stdout
