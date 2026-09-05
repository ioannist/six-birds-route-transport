from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

from holonomy_memory import DEFAULT_MULTISPACE_SEARCH_IDS, run_multispace_discovery


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_run_multispace_discovery_writes_combined_summary_and_counts(tmp_path: Path) -> None:
    artifacts = run_multispace_discovery(seed=0, output_root=tmp_path)
    summary = artifacts.summary

    assert artifacts.summary_json_path.is_file()
    assert artifacts.summary_csv_path.is_file()
    assert artifacts.summary_note_path.is_file()
    assert summary.search_ids == DEFAULT_MULTISPACE_SEARCH_IDS
    assert [entry.search_id for entry in summary.entries] == list(DEFAULT_MULTISPACE_SEARCH_IDS)

    aggregate_flat = sum(entry.flat_count for entry in summary.entries)
    aggregate_dissipative = sum(entry.dissipative_count for entry in summary.entries)
    aggregate_coherent = sum(entry.coherent_candidate_count for entry in summary.entries)
    aggregate_shortlist = sum(entry.shortlist_count for entry in summary.entries)
    assert dict(summary.aggregate_class_counts) == {
        "flat": aggregate_flat,
        "dissipative": aggregate_dissipative,
        "coherent_candidate": aggregate_coherent,
    }
    assert summary.aggregate_shortlist_count == aggregate_shortlist
    assert any(
        entry.search_id != "cyclic_memory_small" and (entry.all_flat or entry.productive)
        for entry in summary.entries
    )

    fixed_entry = next(entry for entry in summary.entries if entry.search_id == "fixed_support_core_small")
    cyclic_entry = next(entry for entry in summary.entries if entry.search_id == "cyclic_memory_small")
    assert fixed_entry.all_flat is True
    assert cyclic_entry.productive is True

    with artifacts.summary_csv_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert [row["search_id"] for row in rows] == list(DEFAULT_MULTISPACE_SEARCH_IDS)


def test_cli_run_discovery_multispace_smoke_writes_expected_paths(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "holonomy_memory",
            "run-discovery-multispace",
            "--seed",
            "0",
            "--output-root",
            str(tmp_path),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert (
        tmp_path
        / "artifacts"
        / "results"
        / "discovery"
        / "multi_space.discovery.json"
    ).is_file()
    assert (
        tmp_path / "artifacts" / "tables" / "discovery_multi_space_summary.csv"
    ).is_file()
    assert (
        tmp_path / "docs" / "results" / "multi_space.discovery.md"
    ).is_file()
