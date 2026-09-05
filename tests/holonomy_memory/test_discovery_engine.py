from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest

from holonomy_memory import (
    enumerate_discovery_candidates,
    load_search_space,
    run_discovery_search,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
ALLOWED_DISCOVERY_LABELS = {"flat", "dissipative", "coherent_candidate"}


def test_run_discovery_search_fixed_space_writes_atlas_artifacts(tmp_path: Path) -> None:
    artifacts = run_discovery_search(
        search_id="fixed_support_core_small",
        seed=0,
        output_root=tmp_path,
    )
    atlas = artifacts.atlas

    assert artifacts.json_atlas_path.is_file()
    assert artifacts.csv_summary_path.is_file()
    assert artifacts.summary_note_path.is_file()
    assert atlas.evaluated_candidate_count > 0
    assert atlas.evaluated_candidate_count <= atlas.capped_candidate_count
    assert sum(count for _, count in atlas.class_counts) == atlas.evaluated_candidate_count
    assert dict(atlas.class_counts)["flat"] > 0

    payload = json.loads(artifacts.json_atlas_path.read_text(encoding="utf-8"))
    assert payload["evaluated_candidate_count"] == atlas.evaluated_candidate_count
    assert set(payload["class_counts"]) <= ALLOWED_DISCOVERY_LABELS
    assert all(
        candidate["candidate_label"] in ALLOWED_DISCOVERY_LABELS
        for candidate in payload["candidates"]
    )

    with artifacts.csv_summary_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == atlas.evaluated_candidate_count
    assert {row["class_label"] for row in rows} <= ALLOWED_DISCOVERY_LABELS


def test_run_discovery_search_cyclic_space_finds_nonflat_candidates(tmp_path: Path) -> None:
    artifacts = run_discovery_search(
        search_id="cyclic_memory_small",
        seed=0,
        output_root=tmp_path,
    )
    atlas = artifacts.atlas

    assert atlas.evaluated_candidate_count > 0
    assert any(
        record.candidate_label != "flat" for record in atlas.candidate_records
    )
    assert any(
        record.candidate_label == "coherent_candidate"
        and record.loop_action_evidence is not None
        for record in atlas.candidate_records
    )


def test_discovery_candidate_enumeration_fails_fast_on_empty_family_dimension() -> None:
    search_space = load_search_space(
        REPO_ROOT / "configs" / "search" / "fixed_support_core_small.search.json"
    ).model_copy(update={"carrier_family_candidates": []})
    with pytest.raises(
        ValueError,
        match="discovery search space requires non-empty candidate lists",
    ):
        enumerate_discovery_candidates(search_space=search_space)


def test_cli_run_discovery_smoke_writes_expected_paths(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "holonomy_memory",
            "run-discovery",
            "--search-id",
            "fixed_support_core_small",
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
        / "fixed_support_core_small.atlas.json"
    ).is_file()
    assert (
        tmp_path / "artifacts" / "tables" / "discovery_fixed_support_core_small.csv"
    ).is_file()
    assert (
        tmp_path / "docs" / "results" / "fixed_support_core_small.atlas.md"
    ).is_file()
