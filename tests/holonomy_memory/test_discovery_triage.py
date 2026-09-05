from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

from holonomy_memory import triage_discovery_candidates


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_triage_discovery_candidates_writes_shortlist_and_keeps_order(tmp_path: Path) -> None:
    artifacts = triage_discovery_candidates(
        search_id="cyclic_memory_small",
        seed=0,
        output_root=tmp_path,
    )
    shortlist = artifacts.shortlist

    assert artifacts.atlas_json_path.is_file()
    assert artifacts.atlas_csv_path.is_file()
    assert artifacts.atlas_note_path.is_file()
    assert artifacts.shortlist_json_path.is_file()
    assert artifacts.shortlist_csv_path.is_file()
    assert artifacts.shortlist_note_path.is_file()

    class_counts = dict(shortlist.class_counts)
    evaluated_candidate_count = sum(class_counts.values())
    assert shortlist.class_counts[0][0] == "flat"
    assert shortlist.class_counts[1][0] == "dissipative"
    assert shortlist.class_counts[2][0] == "coherent_candidate"
    assert evaluated_candidate_count > 0

    combined = shortlist.combined_shortlist
    assert combined
    assert len({entry.candidate_id for entry in combined}) == len(combined)
    assert any(entry.class_label == "coherent_candidate" for entry in combined)
    assert all(
        0.0 <= float(entry.robustness_proxy_fraction) <= 1.0 for entry in combined
    )
    assert any(entry.primary_witness_count > 0 for entry in combined)
    assert any(entry.primary_predictive_loop_score > 0 for entry in combined)

    discrepancy_ids = [entry.candidate_id for entry in shortlist.top_by_discrepancy]
    predictive_loop_ids = [entry.candidate_id for entry in shortlist.top_by_predictive_loop]
    robustness_entries = list(shortlist.top_by_robustness_proxy)
    assert discrepancy_ids == sorted(discrepancy_ids)
    assert predictive_loop_ids == sorted(predictive_loop_ids)
    assert robustness_entries == sorted(
        robustness_entries,
        key=lambda entry: (
            -float(entry.robustness_proxy_fraction),
            entry.candidate_id,
        ),
    )

    with artifacts.shortlist_csv_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == len(combined)
    assert [row["candidate_id"] for row in rows] == [entry.candidate_id for entry in combined]


def test_cli_triage_discovery_smoke_writes_expected_paths(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "holonomy_memory",
            "triage-discovery",
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
        / "cyclic_memory_small.atlas.json"
    ).is_file()
    assert (
        tmp_path
        / "artifacts"
        / "results"
        / "discovery"
        / "cyclic_memory_small.shortlist.json"
    ).is_file()
    assert (
        tmp_path / "artifacts" / "tables" / "discovery_cyclic_memory_small_shortlist.csv"
    ).is_file()
    assert (
        tmp_path / "docs" / "results" / "cyclic_memory_small.shortlist.md"
    ).is_file()
