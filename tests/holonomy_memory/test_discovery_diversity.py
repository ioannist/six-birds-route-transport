from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

from holonomy_memory import (
    DEFAULT_MULTISPACE_SEARCH_IDS,
    run_discovery_diversity_audit,
    run_multispace_discovery,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_run_discovery_diversity_audit_writes_expected_artifacts_and_clusters(
    tmp_path: Path,
) -> None:
    multispace_artifacts = run_multispace_discovery(seed=0, output_root=tmp_path)
    artifacts = run_discovery_diversity_audit(seed=0, output_root=tmp_path)
    summary = artifacts.summary

    assert artifacts.summary_json_path.is_file()
    assert artifacts.summary_csv_path.is_file()
    assert artifacts.summary_note_path.is_file()
    assert summary.source_search_ids == DEFAULT_MULTISPACE_SEARCH_IDS
    assert summary.unique_exemplar_count == len(summary.clusters)
    assert len(summary.clusters) <= summary.total_shortlisted_candidate_count

    expected_qualified_ids: list[str] = []
    productive_spaces_with_shortlists: set[str] = set()
    for entry in multispace_artifacts.summary.entries:
        if entry.shortlist_count > 0:
            productive_spaces_with_shortlists.add(entry.search_id)
        if entry.shortlist_json_path is None:
            continue
        shortlist_payload = json.loads(entry.shortlist_json_path.read_text(encoding="utf-8"))
        expected_qualified_ids.extend(
            f"{entry.search_id}:{item['candidate_id']}"
            for item in shortlist_payload["combined_shortlist"]
        )
    assert list(summary.ordered_shortlisted_candidate_ids_audited) == expected_qualified_ids

    with artifacts.summary_csv_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    observed_qualified_ids = [f"{row['search_id']}:{row['candidate_id']}" for row in rows]
    assert observed_qualified_ids == expected_qualified_ids
    assert len(observed_qualified_ids) == len(set(observed_qualified_ids))

    cluster_ids = [cluster.cluster_id for cluster in summary.clusters]
    assert cluster_ids == [f"cluster_{index:03d}" for index in range(len(cluster_ids))]

    row_cluster_counts: dict[str, int] = {}
    row_exemplar_counts: dict[str, int] = {}
    row_search_ids: set[str] = set()
    for row in rows:
        row_cluster_counts[row["cluster_id"]] = row_cluster_counts.get(row["cluster_id"], 0) + 1
        row_exemplar_counts[row["cluster_id"]] = row_exemplar_counts.get(row["cluster_id"], 0) + (
            1 if row["is_exemplar"] == "true" else 0
        )
        row_search_ids.add(row["search_id"])
    assert set(row_cluster_counts) == set(cluster_ids)
    assert all(count == 1 for count in row_exemplar_counts.values())
    assert row_search_ids == productive_spaces_with_shortlists

    if any(cluster.cluster_size > 1 for cluster in summary.clusters):
        assert any(cluster.match_kind != "singleton" for cluster in summary.clusters)
    else:
        assert summary.singleton_count == len(summary.clusters)
        assert summary.singleton_count == summary.total_shortlisted_candidate_count


def test_cli_audit_discovery_diversity_smoke_writes_expected_paths(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "holonomy_memory",
            "audit-discovery-diversity",
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
        tmp_path / "artifacts" / "results" / "discovery" / "multi_space.dedup.json"
    ).is_file()
    assert (
        tmp_path / "artifacts" / "tables" / "discovery_multi_space_dedup.csv"
    ).is_file()
    assert (
        tmp_path / "docs" / "results" / "multi_space.dedup.md"
    ).is_file()
