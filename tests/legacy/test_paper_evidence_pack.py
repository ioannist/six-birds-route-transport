from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from sixbirds_event.evidence.models import (
    CaveatRegistry,
    PaperEvidencePack,
    TheoremExperimentMap,
)
from sixbirds_event.schemas.common import SchemaKind
from sixbirds_event.schemas.result_note import ResultNote
from sixbirds_event.schemas.run_manifest import RunManifest
from sixbirds_event.validation import load_model, validate_file


PACK_INDEX = Path("experiments/instances/paper/evidence-pack-index.json")
THEOREM_MAP = Path("experiments/instances/paper/theorem-experiment-map.json")
CAVEAT_REGISTRY = Path("experiments/instances/paper/caveat-registry.json")


def test_paper_evidence_pack_format_validates() -> None:
    result = validate_file(PACK_INDEX, kind=SchemaKind.PAPER_EVIDENCE_PACK)
    assert result.ok
    assert isinstance(result.model, PaperEvidencePack)
    assert result.model.evidence_pack_id == "paper_evidence_pack_t51"


def test_theorem_experiment_map_format_validates() -> None:
    result = validate_file(THEOREM_MAP, kind=SchemaKind.THEOREM_EXPERIMENT_MAP)
    assert result.ok
    assert isinstance(result.model, TheoremExperimentMap)
    assert result.model.theorem_object_label == "event_package"


def test_caveat_registry_format_validates() -> None:
    result = validate_file(CAVEAT_REGISTRY, kind=SchemaKind.CAVEAT_REGISTRY)
    assert result.ok
    assert isinstance(result.model, CaveatRegistry)
    assert len(result.model.entries) >= 5


def test_paper_evidence_pack_build_runs_end_to_end(tmp_path: Path) -> None:
    from sixbirds_event.evidence.pack import build_paper_evidence_pack

    artifacts = build_paper_evidence_pack(
        index_path=PACK_INDEX,
        category="results",
        label="paper-evidence-pack-test",
        timestamp="2026-03-31T08:00:00Z",
        root=tmp_path,
    )

    summary_path = tmp_path / artifacts.summary_path
    note_path = tmp_path / artifacts.note_path
    result_note = load_model(
        tmp_path / artifacts.result_note_path,
        kind=SchemaKind.RESULT_NOTE,
    )
    manifest = load_model(
        tmp_path / artifacts.manifest_path,
        kind=SchemaKind.RUN_MANIFEST,
    )

    assert summary_path.exists()
    assert note_path.exists()
    assert isinstance(result_note, ResultNote)
    assert isinstance(manifest, RunManifest)

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["evidence_pack_id"] == "paper_evidence_pack_t51"
    assert (
        summary["transient_gap_resolution"]["t50_runtime_outputs"]
        == "committed_summary_substitution"
    )
    assert (
        summary["transient_gap_resolution"]["th6_runtime_outputs"]
        == "committed_summary_substitution"
    )
    assert summary["summary_metrics"]["overall_control_bundle_verdict"] == (
        "all_applicable_flagships_survived"
    )

    note_text = note_path.read_text(encoding="utf-8")
    assert "Flagship numerical evidence" in note_text
    assert "Missing transient-output handling" in note_text
    assert "all_applicable_flagships_survived" in note_text

    assert manifest.metadata["analysis_kind"] == "paper_evidence_pack"
    assert "summary" in manifest.output_artifacts
    assert "note" in manifest.output_artifacts
    assert "result_note" in manifest.output_artifacts
    assert "manifest" in manifest.output_artifacts


def test_cli_smoke_build_paper_evidence_pack(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "sixbirds_event",
            "evidence",
            "build-pack",
            PACK_INDEX.as_posix(),
            "--category",
            "results",
            "--label",
            "paper-evidence-pack-cli",
            "--timestamp",
            "2026-03-31T08:05:00Z",
            "--root",
            str(tmp_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "run_id=" in result.stdout
    assert (
        "theorem_experiment_map=experiments/instances/paper/theorem-experiment-map.json"
        in result.stdout
    )
    assert (
        "flagship_witnesses=experiments/instances/paper/flagship-witnesses.json"
        in result.stdout
    )
    assert (
        "best_evidence_by_axis=experiments/instances/paper/best-evidence-by-axis.json"
        in result.stdout
    )
    assert (
        "caveat_registry=experiments/instances/paper/caveat-registry.json"
        in result.stdout
    )
    assert "summary=" in result.stdout
