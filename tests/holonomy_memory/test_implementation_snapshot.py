from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_implementation_snapshot_lists_existing_paths() -> None:
    index_path = REPO_ROOT / "docs" / "ops" / "implementation_snapshot_v0.md"
    snapshot_path = REPO_ROOT / "artifacts" / "results" / "implementation_snapshot_v0.json"

    assert index_path.is_file()
    assert snapshot_path.is_file()

    payload = json.loads(snapshot_path.read_text(encoding="utf-8"))

    path_groups = [
        payload["benchmark_artifacts"]["suite_summary_paths"],
        payload["benchmark_artifacts"]["per_benchmark_result_paths"],
        payload["benchmark_artifacts"]["key_benchmark_note_paths"],
        payload["discovery_artifacts"]["atlas_paths"],
        payload["discovery_artifacts"]["shortlist_paths"],
        payload["discovery_artifacts"]["shortlist_robustness_paths"],
        payload["discovery_artifacts"]["multi_space_summary_paths"],
        payload["discovery_artifacts"]["dedup_summary_paths"],
        payload["discovery_artifacts"]["promoted_exemplar_paths"],
        payload["discovery_artifacts"]["optional_promotion_robustness_paths"],
        payload["robustness_artifacts"]["core_suite_paths"],
        payload["robustness_artifacts"]["per_benchmark_note_paths"],
        payload["aggregation_artifacts"]["paths"],
        [
            payload["reproducibility_status"]["note_path"],
            payload["reproducibility_status"]["freeze_summary_path"],
            payload["lean_status"]["toolchain_path"],
            "lean/lakefile.toml",
            payload["lean_status"]["root_module_path"],
        ],
        payload["lean_status"]["theorem_module_paths"],
    ]

    listed_paths = [Path(path) for group in path_groups for path in group]
    assert payload["verification"]["all_paths_checked"] is True
    assert payload["verification"]["regenerated_paths"] == []
    assert payload["verification"]["listed_path_count"] == len(listed_paths)
    for path in listed_paths:
        assert (REPO_ROOT / path).is_file()

    index_text = index_path.read_text(encoding="utf-8")
    for section in (
        "## Snapshot scope",
        "## Benchmark artifacts",
        "## Discovery artifacts",
        "## Robustness artifacts",
        "## Aggregation artifacts",
        "## Lean status",
        "## Reproducibility status",
        "## Open issues",
        "## Verification",
    ):
        assert section in index_text
