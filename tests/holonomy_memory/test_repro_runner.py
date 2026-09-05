from __future__ import annotations

import json
from pathlib import Path

from holonomy_memory import BENCHMARK_SUITE_IDS, run_benchmark_suite, run_discovery_smoke


def test_run_benchmark_suite_writes_stable_summary_artifacts(tmp_path: Path) -> None:
    artifacts = run_benchmark_suite(seed=0, output_root=tmp_path)

    assert artifacts.summary_json_path.exists()
    assert artifacts.summary_csv_path.exists()
    assert artifacts.summary_note_path.exists()

    payload = json.loads(artifacts.summary_json_path.read_text(encoding="utf-8"))
    assert tuple(payload["benchmark_ids"]) == BENCHMARK_SUITE_IDS
    assert [entry["benchmark_id"] for entry in payload["entries"]] == list(BENCHMARK_SUITE_IDS)
    for entry in payload["entries"]:
        assert entry["json_artifact_path"]
        assert entry["csv_artifact_path"]
        assert entry["ops_note_path"]


def test_run_discovery_smoke_writes_stable_summary_artifacts(tmp_path: Path) -> None:
    artifacts = run_discovery_smoke(seed=0, output_root=tmp_path)

    assert artifacts.summary_json_path.exists()
    assert artifacts.summary_note_path.exists()

    payload = json.loads(artifacts.summary_json_path.read_text(encoding="utf-8"))
    for key in (
        "atlas_json_path",
        "shortlist_json_path",
        "shortlist_robustness_json_path",
        "multispace_json_path",
        "dedup_json_path",
        "promoted_exemplars_json_path",
    ):
        assert payload[key]
        assert (tmp_path / payload[key]).exists()

    assert payload["primary_search_id"] == "cyclic_memory_small"
    assert isinstance(payload["combined_shortlist_ids"], list)
    assert isinstance(payload["promoted_exemplar_qualified_ids"], list)
