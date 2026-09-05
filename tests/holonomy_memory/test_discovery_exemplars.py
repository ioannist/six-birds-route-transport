from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

from holonomy_memory import promote_discovery_exemplars


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_promote_discovery_exemplars_writes_tracked_artifacts_and_is_stable(
    tmp_path: Path,
) -> None:
    first = promote_discovery_exemplars(seed=0, output_root=tmp_path)
    second = promote_discovery_exemplars(seed=0, output_root=tmp_path)

    first_summary = first.summary
    second_summary = second.summary
    assert first.summary_json_path.is_file()
    assert first.summary_csv_path.is_file()
    assert first.index_note_path.is_file()
    assert len(first.individual_exemplar_note_paths) >= 1
    assert all(path.is_file() for path in first.individual_exemplar_note_paths)
    assert first_summary.ordered_promoted_qualified_ids == second_summary.ordered_promoted_qualified_ids

    promoted = list(first_summary.promoted_exemplars)
    assert 1 <= len(promoted) <= 2
    assert len({entry.qualified_id for entry in promoted}) == len(promoted)
    assert all(":" in entry.qualified_id for entry in promoted)
    assert any(entry.meets_threshold for entry in promoted)

    for entry in promoted:
        assert entry.qualified_id == f"{entry.search_id}:{entry.candidate_id}"
        assert entry.selection_reasons
        assert entry.threshold > 0
        assert 0 <= float(entry.survival_fraction) <= 1
        assert entry.atlas_json_path.is_file()
        assert entry.atlas_csv_path.is_file()
        assert entry.atlas_note_path.is_file()
        assert entry.shortlist_json_path.is_file()
        assert entry.shortlist_csv_path.is_file()
        assert entry.shortlist_note_path.is_file()
        assert entry.robustness_json_path.is_file()
        assert entry.robustness_csv_path.is_file()
        assert entry.robustness_note_path.is_file()
        assert entry.dedup_json_path.is_file()
        assert entry.dedup_csv_path.is_file()
        assert entry.dedup_note_path.is_file()
        assert entry.distinctness_kind in {"singleton", "near_duplicate", "exact_duplicate"}

    with first.summary_csv_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert [row["qualified_id"] for row in rows] == list(first_summary.ordered_promoted_qualified_ids)

    if len(promoted) == 2:
        first_entry, second_entry = promoted
        assert first_entry.qualified_id != second_entry.qualified_id
        if first_entry.search_id != second_entry.search_id:
            pass
        else:
            first_signature = _structural_signature_for_promoted(first_entry)
            second_signature = _structural_signature_for_promoted(second_entry)
            assert first_signature != second_signature


def test_cli_promote_discovery_exemplars_smoke_writes_expected_paths(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "holonomy_memory",
            "promote-discovery-exemplars",
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
        tmp_path / "artifacts" / "results" / "discovery" / "promoted_exemplars.json"
    ).is_file()
    assert (
        tmp_path / "artifacts" / "tables" / "discovery_promoted_exemplars.csv"
    ).is_file()
    assert (
        tmp_path / "docs" / "results" / "discovery_exemplars.md"
    ).is_file()


def _structural_signature_for_promoted(entry: object) -> tuple[object, ...]:
    promoted = entry
    payload = json.loads(promoted.atlas_json_path.read_text(encoding="utf-8"))
    candidate = next(
        item
        for item in payload["candidates"]
        if item["candidate_id"] == promoted.candidate_id
    )
    spec = candidate["candidate_spec"]
    return (
        spec["support_size"],
        spec["interface_count"],
        spec["carrier_family"],
        spec["route_update_family"],
        spec["observable_family"],
        spec["continuation_catalog_family"],
    )
