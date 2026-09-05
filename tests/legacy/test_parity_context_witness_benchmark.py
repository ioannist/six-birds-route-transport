from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from sixbirds_event.benchmarks.parity_context_witness import (
    BENCHMARK_ID,
    run_parity_context_witness_benchmark,
)
from sixbirds_event.reporting.structural_report import load_event_package_instance
from sixbirds_event.schemas.common import SchemaKind
from sixbirds_event.schemas.result_note import ResultNote
from sixbirds_event.schemas.run_manifest import RunManifest
from sixbirds_event.validation import load_model


BENCHMARK_DIR = Path("experiments/instances/benchmarks/parity-context-witness")


def test_benchmark_instance_validates() -> None:
    instance = load_event_package_instance(BENCHMARK_DIR / "instance.json")
    assert instance.instance_id == "inst_parity_context_witness"


def test_benchmark_bundle_runner_completes_end_to_end(tmp_path: Path) -> None:
    bundle = run_parity_context_witness_benchmark(
        category="benchmarks",
        label="parity-context-witness",
        seed=123,
        timestamp="2026-03-25T00:00:00Z",
        root=tmp_path,
    )
    assert (tmp_path / bundle.index_path).exists()
    assert (tmp_path / bundle.note_path).exists()
    assert (tmp_path / bundle.result_note_path).exists()
    assert (tmp_path / bundle.manifest_path).exists()

    assert bundle.metrics_summary["exact_structural_feasible_hard_only"] is False
    assert bundle.metrics_summary["exact_respecting_tuple_count"] == 0
    assert bundle.metrics_summary["gpd_str"] is not None
    assert bundle.metrics_summary["gpd_str"] > 0

    index = json.loads((tmp_path / bundle.index_path).read_text(encoding="utf-8"))
    assert index["benchmark_id"] == BENCHMARK_ID
    assert (
        index["nonextendable_under_current_hard_only_admissibility_semantics"] is True
    )
    assert index["relaxed_proposal_ids"]
    assert index["structural_deficit_config"]["allow_relax_hard"] is True
    assert index["statistical_status"]["solved"] is False
    assert index["statistical_status"]["reason"] == "no_respecting_tuples"
    assert Path(index["instance_path"]).exists()
    assert Path(index["trace_paths"]["stat_clean"]).exists()

    note_text = (tmp_path / bundle.note_path).read_text(encoding="utf-8")
    assert "not exactly extendable" in note_text
    assert "Relaxed blocking proposal IDs" in note_text

    manifest = load_model(tmp_path / bundle.manifest_path, kind=SchemaKind.RUN_MANIFEST)
    assert isinstance(manifest, RunManifest)
    assert set(manifest.output_artifacts) == {
        "benchmark_index",
        "benchmark_note",
        "result_note",
    }

    result_note = load_model(
        tmp_path / bundle.result_note_path, kind=SchemaKind.RESULT_NOTE
    )
    assert isinstance(result_note, ResultNote)
    assert "not exactly extendable" in result_note.interpretation
    assert "no_respecting_tuples" in result_note.interpretation


def test_cli_benchmark_runner_works(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "sixbirds_event",
            "benchmarks",
            "parity-context-witness",
            "run",
            "--category",
            "benchmarks",
            "--label",
            "parity-context-witness",
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
    assert "index=" in result.stdout
    assert "exact_structural_feasible_hard_only=False" in result.stdout
    assert "gpd_str=" in result.stdout
