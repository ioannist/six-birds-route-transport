from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from sixbirds_event.schemas.common import SchemaKind
from sixbirds_event.schemas.event_package import EventPackageInstance
from sixbirds_event.schemas.observation_trace import ObservationTrace
from sixbirds_event.provenance.models import PackageProvenance
from sixbirds_event.schemas.result_note import ResultNote
from sixbirds_event.schemas.run_manifest import RunManifest
from sixbirds_event.validation import load_model, validate_payload
from sixbirds_event.reporting.hidden_record_report import (
    write_hidden_record_intervention_report,
)


INTERVENTION_DIR = Path("experiments/instances/interventions/hidden-record-route-split")
INTERVENTION = INTERVENTION_DIR / "intervention.json"
BEFORE_INSTANCE = INTERVENTION_DIR / "before-instance.json"
ROUTE_SOURCE = INTERVENTION_DIR / "route-source.json"


def test_hidden_record_intervention_format_validates() -> None:
    payload = json.loads(INTERVENTION.read_text(encoding="utf-8"))
    result = validate_payload(payload, kind=SchemaKind.HIDDEN_RECORD_INTERVENTION)
    assert result.ok
    assert result.kind == SchemaKind.HIDDEN_RECORD_INTERVENTION


def test_committed_intervention_assets_are_reproducible_repo_files() -> None:
    intervention = load_model(INTERVENTION, kind=SchemaKind.HIDDEN_RECORD_INTERVENTION)
    before_instance = load_model(
        BEFORE_INSTANCE, kind=SchemaKind.EVENT_PACKAGE_INSTANCE
    )
    route_source = load_model(ROUTE_SOURCE, kind=SchemaKind.OBSERVATION_TRACE)

    assert intervention.intervention_id == "hidden_record_route_split"
    assert isinstance(before_instance, EventPackageInstance)
    assert before_instance.instance_id == "inst_hidden_record_route_split_before"
    assert isinstance(route_source, ObservationTrace)
    assert route_source.trace_id == "trace_hidden_record_route_split_source"


def test_hidden_record_intervention_runner_writes_bundle_and_comparison(
    tmp_path: Path,
) -> None:
    artifacts = write_hidden_record_intervention_report(
        intervention_path=INTERVENTION.as_posix(),
        category="interventions",
        label="hidden-record-route-split",
        seed=0,
        timestamp="2026-03-25T00:00:00Z",
        root=tmp_path,
    )

    augmented = load_model(
        tmp_path / artifacts.augmented_instance_path,
        kind=SchemaKind.EVENT_PACKAGE_INSTANCE,
    )
    before_stat = load_model(
        tmp_path / artifacts.before_stat_path,
        kind=SchemaKind.OBSERVATION_TRACE,
    )
    after_stat = load_model(
        tmp_path / artifacts.after_stat_path,
        kind=SchemaKind.OBSERVATION_TRACE,
    )
    provenance = load_model(
        tmp_path / artifacts.provenance_path,
        kind=SchemaKind.PACKAGE_PROVENANCE,
    )
    result_note = load_model(
        tmp_path / artifacts.result_note_path,
        kind=SchemaKind.RESULT_NOTE,
    )
    manifest = load_model(
        tmp_path / artifacts.manifest_path,
        kind=SchemaKind.RUN_MANIFEST,
    )

    assert isinstance(augmented, EventPackageInstance)
    assert isinstance(before_stat, ObservationTrace)
    assert isinstance(after_stat, ObservationTrace)
    assert isinstance(provenance, PackageProvenance)
    assert isinstance(result_note, ResultNote)
    assert isinstance(manifest, RunManifest)

    summary_payload = json.loads(
        (tmp_path / artifacts.summary_path).read_text(encoding="utf-8")
    )
    assert summary_payload["before"]["exact_structural_feasible_hard_only"] is False
    assert summary_payload["before"]["gpd_str"] > 0
    assert summary_payload["before"]["statistical_solved"] is False
    assert summary_payload["before"]["statistical_reason"] == "no_respecting_tuples"
    assert summary_payload["after"]["exact_structural_feasible_hard_only"] is True
    assert summary_payload["after"]["gpd_str"] == 0
    assert summary_payload["after"]["gpd_stat"] == 0.0
    assert summary_payload["before"]["rm"]["overall_rm"] == 0.5
    assert summary_payload["after"]["rm"]["overall_rm"] is None
    assert summary_payload["obstruction_status_after_intervention"] == "disappeared"

    assert manifest.output_artifacts == {
        "after_route": "results/interventions/20260325T000000Z--hidden_record_route_split/after-route.json",
        "after_stat": "results/interventions/20260325T000000Z--hidden_record_route_split/after-stat.json",
        "augmented_instance": "results/interventions/20260325T000000Z--hidden_record_route_split/augmented-instance.json",
        "before_stat": "results/interventions/20260325T000000Z--hidden_record_route_split/before-stat.json",
        "note": "results/interventions/20260325T000000Z--hidden_record_route_split/comparison-note.md",
        "package_provenance": "results/interventions/20260325T000000Z--hidden_record_route_split/package-provenance.json",
        "result_note": "results/interventions/20260325T000000Z--hidden_record_route_split/result-note.json",
        "summary": "results/interventions/20260325T000000Z--hidden_record_route_split/comparison-summary.json",
    }
    assert manifest.metadata["analysis_kind"] == "hidden_record_intervention"
    assert manifest.metadata["obstruction_status_after_intervention"] == "disappeared"

    note = (tmp_path / artifacts.note_path).read_text(encoding="utf-8")
    assert "Obstruction status after intervention" in note
    assert "`disappeared`" in note
    assert "RM is diagnostic-only" in note
    assert "Package provenance" in note


def test_cli_smoke_works_on_committed_intervention_asset(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "sixbirds_event",
            "interventions",
            "hidden-record",
            INTERVENTION.as_posix(),
            "--category",
            "interventions",
            "--label",
            "hidden-record-route-split",
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
    assert "package_provenance=" in result.stdout
    assert "before_gpd_str=2.0" in result.stdout
    assert "after_gpd_str=0" in result.stdout
    assert "conclusion=disappeared" in result.stdout
