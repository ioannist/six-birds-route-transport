from __future__ import annotations

import csv
import json
from pathlib import Path
import subprocess
import sys

from sixbirds_event.schemas.common import SchemaKind
from sixbirds_event.schemas.result_note import ResultNote
from sixbirds_event.schemas.run_manifest import RunManifest
from sixbirds_event.search.models import SearchAtlas, SearchAtlasRow
from sixbirds_event.search.sweep import run_search_sweep
from sixbirds_event.validation import load_model, validate_payload


SWEEP = Path("experiments/configs/search/small-sweep.json")


def test_search_sweep_format_validates() -> None:
    payload = json.loads(SWEEP.read_text(encoding="utf-8"))
    result = validate_payload(payload, kind=SchemaKind.SEARCH_SWEEP)
    assert result.ok
    assert result.kind == SchemaKind.SEARCH_SWEEP


def test_search_atlas_row_format_validates() -> None:
    row = SearchAtlasRow(
        row_format_version="search-atlas-row.v1",
        sweep_id="sweep_demo",
        point_id="point_demo",
        config_path="experiments/configs/substrates/deterministic-cycle.json",
        preparation_id="prep0",
        protocol_id="cycle5",
        trajectories=4,
        seed=0,
        raw_run_path="results/search/demo/raw.json",
        discovered_context_family_path="results/search/demo/family.json",
        event_package_path=None,
        accepted_context_count=0,
        accepted_shared_event_proposal_count=0,
        exact_structural_status="not_applicable",
        exact_structural_feasible_hard_only=None,
        exact_respecting_tuple_count=None,
        gpd_str=None,
        gpd_stat_status="not_applicable",
        gpd_stat=None,
        gpd_stat_reason=None,
        ccd_status="not_applicable",
        ccd_overall=None,
        sec_status="not_applicable",
        sec_mean=None,
        rm_status="not_applicable",
        rm_overall=None,
        regime_classification="trivial_or_nonrecording",
        run_ids={"substrate_run": "run_search_demo_point"},
        artifact_paths={
            "raw_run": "results/search/demo/raw.json",
            "family": "results/search/demo/family.json",
        },
        notes=["demo_row"],
    )
    assert row.point_id == "point_demo"


def test_committed_sweep_runs_end_to_end(tmp_path: Path) -> None:
    artifacts = run_search_sweep(
        sweep_path=SWEEP.as_posix(),
        category="search",
        label="small-sweep",
        seed=0,
        timestamp="2026-03-25T00:00:00Z",
        root=tmp_path,
    )

    atlas = load_model(
        tmp_path / artifacts.atlas_json_path, kind=SchemaKind.SEARCH_ATLAS
    )
    assert isinstance(atlas, SearchAtlas)
    assert atlas.row_count == 3

    csv_path = tmp_path / artifacts.atlas_csv_path
    assert csv_path.exists()
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == atlas.row_count

    regime_counts = json.loads(
        (tmp_path / artifacts.regime_counts_path).read_text(encoding="utf-8")
    )
    assert regime_counts["trivial_or_nonrecording"] >= 1
    assert sum(regime_counts.values()) == atlas.row_count

    assert any(row.accepted_context_count >= 2 for row in atlas.rows)
    for row in atlas.rows:
        assert (tmp_path / row.raw_run_path).exists()
        assert (tmp_path / row.discovered_context_family_path).exists()
        if row.event_package_path is not None:
            assert (tmp_path / row.event_package_path).exists()
        assert row.run_ids
        assert row.artifact_paths
        assert row.gpd_stat_status in {"solved", "unsolved", "not_applicable"}
        assert row.rm_status in {"scored", "insufficient_data", "not_applicable"}

    note = (tmp_path / artifacts.note_path).read_text(encoding="utf-8")
    assert "Regime counts" in note
    assert "RM is diagnostic-only" in note
    assert "unsolved / insufficient-data" in note

    result_note = load_model(
        tmp_path / artifacts.result_note_path, kind=SchemaKind.RESULT_NOTE
    )
    assert isinstance(result_note, ResultNote)
    manifest = load_model(
        tmp_path / artifacts.manifest_path, kind=SchemaKind.RUN_MANIFEST
    )
    assert isinstance(manifest, RunManifest)
    assert set(manifest.output_artifacts) == {
        "atlas_csv",
        "atlas_json",
        "regime_counts",
        "summary",
        "note",
        "result_note",
    }


def test_cli_smoke_works_on_committed_sweep(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "sixbirds_event",
            "search",
            "run-sweep",
            SWEEP.as_posix(),
            "--category",
            "search",
            "--label",
            "small-sweep",
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
    assert "atlas_csv=" in result.stdout
    assert "atlas_json=" in result.stdout
    assert "regime_counts=" in result.stdout
    assert "trivial_or_nonrecording=" in result.stdout
    assert "multi_context_but_extendable=" in result.stdout

    stdout_lines = {
        line.split("=", 1)[0]: line.split("=", 1)[1]
        for line in result.stdout.strip().splitlines()
        if "=" in line
    }
    atlas_path = tmp_path / stdout_lines["atlas_json"]
    atlas = load_model(atlas_path, kind=SchemaKind.SEARCH_ATLAS)
    assert isinstance(atlas, SearchAtlas)
    assert atlas.row_count == 3
