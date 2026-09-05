from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

from holonomy_memory import run_discovery_shortlist_robustness, triage_discovery_candidates


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_run_discovery_shortlist_robustness_writes_summary_and_preserves_order(
    tmp_path: Path,
) -> None:
    triage_artifacts = triage_discovery_candidates(
        search_id="cyclic_memory_small",
        seed=0,
        output_root=tmp_path,
    )
    robustness_artifacts = run_discovery_shortlist_robustness(
        search_id="cyclic_memory_small",
        seed=0,
        output_root=tmp_path,
    )
    summary = robustness_artifacts.summary

    assert robustness_artifacts.summary_json_path.is_file()
    assert robustness_artifacts.summary_csv_path.is_file()
    assert robustness_artifacts.summary_note_path.is_file()
    assert [entry.candidate_id for entry in summary.entries] == [
        entry.candidate_id for entry in triage_artifacts.shortlist.combined_shortlist
    ]
    assert tuple(summary.ordered_shortlisted_candidate_ids) == tuple(
        entry.candidate_id for entry in triage_artifacts.shortlist.combined_shortlist
    )
    assert all(entry.threshold > 0 for entry in summary.entries)
    assert all(
        0.0 <= float(entry.survival_fraction) <= 1.0 for entry in summary.entries
    )
    assert any(entry.meets_threshold for entry in summary.entries)

    with robustness_artifacts.summary_csv_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == len(summary.entries)
    assert [row["candidate_id"] for row in rows] == [
        entry.candidate_id for entry in summary.entries
    ]


def test_cli_run_discovery_shortlist_robustness_smoke_writes_expected_paths(
    tmp_path: Path,
) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "holonomy_memory",
            "run-discovery-shortlist-robustness",
            "--search-id",
            "cyclic_memory_small",
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
        / "cyclic_memory_small.shortlist_robustness.json"
    ).is_file()
    assert (
        tmp_path
        / "artifacts"
        / "tables"
        / "discovery_cyclic_memory_small_shortlist_robustness.csv"
    ).is_file()
    assert (
        tmp_path
        / "docs"
        / "results"
        / "cyclic_memory_small.shortlist_robustness.md"
    ).is_file()
