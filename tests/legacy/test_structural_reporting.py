from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from sixbirds_event.reporting.structural_report import (
    generate_structural_report,
    load_event_package_instance,
)
from sixbirds_event.schemas.event_package import EventPackageInstance
from sixbirds_event.schemas.common import SchemaKind
from sixbirds_event.schemas.result_note import ResultNote
from sixbirds_event.schemas.run_manifest import RunManifest
from sixbirds_event.validation import load_model


SMOKE_DIR = Path("experiments/instances/smoke")


def test_extendable_report_writes_artifacts_and_manifest(tmp_path: Path) -> None:
    instance_path = SMOKE_DIR / "exact-extendable.json"
    instance = load_event_package_instance(instance_path)
    report = generate_structural_report(
        instance,
        instance_path=instance_path,
        category="benchmarks",
        label="extendable",
        seed=123,
        timestamp="2026-03-25T00:00:00Z",
        root=tmp_path,
        command=["python", "-m", "sixbirds_event", "structural", "report"],
    )

    for relpath in [
        report.manifest_path,
        report.summary_path,
        report.note_path,
        report.result_note_path,
    ]:
        assert (tmp_path / relpath).exists()

    manifest = load_model(tmp_path / report.manifest_path, kind=SchemaKind.RUN_MANIFEST)
    assert isinstance(manifest, RunManifest)
    assert manifest.input_artifacts["instance"] == instance_path.as_posix()
    assert set(manifest.output_artifacts) == {"summary", "note", "result_note"}

    summary = json.loads((tmp_path / report.summary_path).read_text(encoding="utf-8"))
    assert summary["exact_extendable_hard_only"] is True
    assert summary["exact_extendable_all_proposals"] is True
    assert summary["gpd_str"] == 0.0
    assert summary["hard_only_witness_tuples"]
    assert summary["all_proposals_witness_tuples"]

    note = (tmp_path / report.note_path).read_text(encoding="utf-8")
    assert "Total candidate tuple count" in note
    assert "Technical interpretation" in note
    assert report.summary_path in note

    result_note = load_model(
        tmp_path / report.result_note_path, kind=SchemaKind.RESULT_NOTE
    )
    assert isinstance(result_note, ResultNote)
    assert result_note.run_id == report.run_id


def test_nonextendable_report_includes_best_fit_witness_and_blockers(
    tmp_path: Path,
) -> None:
    instance_path = SMOKE_DIR / "exact-nonextendable.json"
    instance = load_event_package_instance(instance_path)
    report = generate_structural_report(
        instance,
        instance_path=instance_path,
        category="benchmarks",
        label="nonextendable",
        seed=123,
        timestamp="2026-03-25T00:00:01Z",
        root=tmp_path,
    )

    summary = json.loads((tmp_path / report.summary_path).read_text(encoding="utf-8"))
    assert summary["exact_extendable_hard_only"] is False
    assert summary["exact_extendable_all_proposals"] is False
    assert summary["gpd_str"] > 0
    assert summary["blocking_explanation"]["classification"] == "coverage_failure"
    assert summary["best_fit_witness_tuples"]
    assert summary["relaxed_atoms"] == {"ctx_a": ["a1"], "ctx_b": ["b1"]}


def test_soft_conflict_reporting_is_semantically_explicit(tmp_path: Path) -> None:
    instance = EventPackageInstance.model_validate(
        {
            "instance_format_version": "event-package-instance.v1",
            "instance_id": "inst_soft_conflict_report",
            "contexts": [
                {
                    "context_id": "ctx_a",
                    "atoms": [{"atom_id": "a0"}, {"atom_id": "a1"}],
                },
                {
                    "context_id": "ctx_b",
                    "atoms": [{"atom_id": "b0"}, {"atom_id": "b1"}],
                },
            ],
            "events": [
                {"event_id": "event_a0", "context_id": "ctx_a", "atom_ids": ["a0"]},
                {"event_id": "event_a1", "context_id": "ctx_a", "atom_ids": ["a1"]},
                {"event_id": "event_b0", "context_id": "ctx_b", "atom_ids": ["b0"]},
                {"event_id": "event_b1", "context_id": "ctx_b", "atom_ids": ["b1"]},
                {"event_id": "event_empty", "context_id": "ctx_b", "atom_ids": []},
            ],
            "equality_proposals": [
                {
                    "proposal_id": "p_a0_b0",
                    "left_event_id": "event_a0",
                    "right_event_id": "event_b0",
                    "constraint_kind": "hard",
                },
                {
                    "proposal_id": "p_a1_b1",
                    "left_event_id": "event_a1",
                    "right_event_id": "event_b1",
                    "constraint_kind": "hard",
                },
                {
                    "proposal_id": "p_soft_conflict",
                    "left_event_id": "event_a1",
                    "right_event_id": "event_empty",
                    "constraint_kind": "soft",
                    "weight_key": "wk_soft",
                },
            ],
            "weights": {"wk_soft": 0.5},
            "metadata": {},
            "audit": {"created_at": "2026-03-25T00:00:00Z"},
        }
    )
    report = generate_structural_report(
        instance,
        instance_path=SMOKE_DIR / "exact-extendable.json",
        category="benchmarks",
        label="soft-conflict",
        seed=123,
        timestamp="2026-03-25T00:00:02Z",
        root=tmp_path,
    )
    summary = json.loads((tmp_path / report.summary_path).read_text(encoding="utf-8"))
    assert summary["exact_extendable_hard_only"] is True
    assert summary["exact_extendable_all_proposals"] is False
    assert summary["gpd_str"] > 0
    note = (tmp_path / report.note_path).read_text(encoding="utf-8")
    assert "Hard-only exact extendable: `True`" in note
    assert "All-proposals exact extendable: `False`" in note


def test_cli_structural_report_works_on_sample_instance(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "sixbirds_event",
            "structural",
            "report",
            "experiments/instances/smoke/exact-extendable.json",
            "--category",
            "benchmarks",
            "--label",
            "smoke",
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
