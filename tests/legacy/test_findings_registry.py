from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from sixbirds_event.findings.models import (
    ClaimEvidenceMap,
    FindingEntry,
    FindingsRegistry,
)
from sixbirds_event.findings.registry import build_findings_registry
from sixbirds_event.schemas.common import SchemaKind
from sixbirds_event.schemas.result_note import ResultNote
from sixbirds_event.schemas.run_manifest import RunManifest
from sixbirds_event.validation import load_model


CONFIG = Path("experiments/configs/findings/final-findings-registry.json")


def test_finding_entry_format_validates() -> None:
    entry = FindingEntry(
        finding_format_version="finding-entry.v1",
        finding_id="demo_finding",
        category="claim_support",
        title="Demo finding",
        status="completed",
        key_claim_tags=["C1"],
        primary_artifact_refs={"summary": "results/findings/demo/summary.json"},
        supporting_artifact_refs={"note": "results/findings/demo/note.md"},
        key_metrics={"count": 1},
        best_evidence_flag=True,
        best_evidence_score=1.0,
        notes=["demo_note"],
        flags=["demo_flag"],
    )
    assert entry.finding_id == "demo_finding"


def test_claim_evidence_map_format_validates() -> None:
    claim_map = ClaimEvidenceMap(
        claim_map_format_version="claim-evidence-map.v1",
        claim_count=1,
        claims=[
            {
                "claim_id": "C1",
                "claim_label": "Demo claim",
                "evidence_entry_ids": ["demo_finding"],
                "best_evidence_entry_id": "demo_finding",
                "theorem_linkage_ids": ["T_demo"],
                "caveat_flags": ["demo_caveat"],
            }
        ],
        metadata={"scope": "demo"},
    )
    assert claim_map.claim_count == 1


def test_committed_findings_registry_runs_end_to_end(tmp_path: Path) -> None:
    artifacts = build_findings_registry(
        config_path=CONFIG.as_posix(),
        category="findings",
        label="final-findings",
        seed=0,
        timestamp="2026-03-26T10:00:00Z",
        root=tmp_path,
    )

    registry = load_model(
        tmp_path / artifacts.registry_path,
        kind=SchemaKind.FINDINGS_REGISTRY,
    )
    claim_map = load_model(
        tmp_path / artifacts.claim_evidence_map_path,
        kind=SchemaKind.CLAIM_EVIDENCE_MAP,
    )
    result_note = load_model(
        tmp_path / artifacts.result_note_path,
        kind=SchemaKind.RESULT_NOTE,
    )
    manifest = load_model(
        tmp_path / artifacts.manifest_path,
        kind=SchemaKind.RUN_MANIFEST,
    )

    assert isinstance(registry, FindingsRegistry)
    assert isinstance(claim_map, ClaimEvidenceMap)
    assert isinstance(result_note, ResultNote)
    assert isinstance(manifest, RunManifest)

    finding_ids = {entry.finding_id for entry in registry.entries}
    categories = {entry.category for entry in registry.entries}
    assert {
        "benchmark",
        "discovered_package",
        "intervention",
        "robustness",
        "redteam",
        "lean",
        "suite",
        "claim_support",
    }.issubset(categories)
    assert "no_strong_discovered_obstruction_found" in registry.status_flags
    assert "no_baseline_obstruction" in registry.status_flags
    assert (
        "hidden_label_smuggling_not_flagged_without_provenance_audit"
        in registry.status_flags
    )
    assert "hidden_label_smuggling_not_flagged_without_provenance_audit" in finding_ids
    assert "no_baseline_obstruction" in finding_ids
    assert "atlas_upgrade_negative_result" in finding_ids

    for output_path in [
        artifacts.registry_csv_path,
        artifacts.claim_evidence_map_path,
        artifacts.flagship_examples_path,
        artifacts.figure_candidates_path,
        artifacts.table_candidates_path,
        artifacts.theorem_experiment_links_path,
        artifacts.best_evidence_paths_path,
        artifacts.summary_path,
        artifacts.note_path,
    ]:
        assert (tmp_path / output_path).exists()

    theorem_links = json.loads(
        (tmp_path / artifacts.theorem_experiment_links_path).read_text(encoding="utf-8")
    )
    best_evidence = json.loads(
        (tmp_path / artifacts.best_evidence_paths_path).read_text(encoding="utf-8")
    )
    assert theorem_links
    assert best_evidence
    assert "C2" in best_evidence

    claim_entry_ids = {entry.finding_id for entry in registry.entries}
    for claim in claim_map.claims:
        assert set(claim.evidence_entry_ids) <= claim_entry_ids
        assert claim.best_evidence_entry_id in claim_entry_ids

    note = (tmp_path / artifacts.note_path).read_text(encoding="utf-8")
    assert "Notable negative results / limitations" in note
    assert "no_strong_discovered_obstruction_found" in note
    assert "hidden_label_smuggling_not_flagged_without_provenance_audit" in note

    assert manifest.metadata["analysis_kind"] == "findings_registry"
    assert "registry" in manifest.output_artifacts
    assert "claim_evidence_map" in manifest.output_artifacts
    assert "theorem_experiment_links" in manifest.output_artifacts
    assert "best_evidence_paths" in manifest.output_artifacts


def test_cli_smoke_works_on_committed_findings_config(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "sixbirds_event",
            "findings",
            "build-registry",
            CONFIG.as_posix(),
            "--category",
            "findings",
            "--label",
            "final-findings",
            "--timestamp",
            "2026-03-26T10:01:00Z",
            "--root",
            str(tmp_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "run_id=" in result.stdout
    assert "registry=" in result.stdout
    assert "claim_evidence_map=" in result.stdout
    assert "flagship_examples=" in result.stdout
    assert "claim_count=8" in result.stdout
