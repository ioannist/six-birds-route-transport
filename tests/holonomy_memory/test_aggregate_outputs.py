from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

import matplotlib

from holonomy_memory import aggregate_outputs


matplotlib.use("Agg")
from matplotlib import image as mpimg  # noqa: E402


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_aggregate_outputs_writes_combined_outputs_and_figures(tmp_path: Path) -> None:
    artifacts = aggregate_outputs(output_root=tmp_path)

    assert artifacts.combined_json_path.is_file()
    assert artifacts.combined_csv_path.is_file()
    assert artifacts.figure_manifest_path.is_file()
    assert artifacts.tracked_note_path.is_file()
    assert len(artifacts.ordered_figure_paths) >= 3
    for figure_path in artifacts.ordered_figure_paths:
        assert figure_path.is_file()
        assert figure_path.stat().st_size > 0
        image = mpimg.imread(figure_path)
        assert image.size > 0

    summary_payload = json.loads(artifacts.combined_json_path.read_text(encoding="utf-8"))
    figure_payload = json.loads(artifacts.figure_manifest_path.read_text(encoding="utf-8"))
    with artifacts.combined_csv_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    assert any(row["record_type"].startswith("benchmark") for row in rows)
    assert any(row["record_type"].startswith("discovery") for row in rows)
    if (REPO_ROOT / "artifacts" / "results" / "discovery" / "promoted_exemplars.json").is_file():
        assert any(row["record_type"] == "discovery_promoted_exemplar" for row in rows)

    counts_from_csv: dict[str, int] = {}
    for row in rows:
        counts_from_csv[row["record_type"]] = counts_from_csv.get(row["record_type"], 0) + 1
    assert summary_payload["row_counts_by_record_type"] == counts_from_csv

    assert len(figure_payload["figures"]) >= 3
    for figure in figure_payload["figures"]:
        figure_path = Path(figure["figure_path"])
        assert figure_path.is_file()
        assert figure["source_artifact_paths"]


def test_cli_aggregate_outputs_smoke_writes_expected_paths(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "holonomy_memory",
            "aggregate-outputs",
            "--output-root",
            str(tmp_path),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "artifacts" / "results" / "aggregate_outputs.json").is_file()
    assert (tmp_path / "artifacts" / "tables" / "aggregate_outputs.csv").is_file()
    assert (tmp_path / "artifacts" / "results" / "aggregate_figures.json").is_file()
    assert (tmp_path / "docs" / "results" / "aggregate_outputs.md").is_file()
