from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import sys

from sixbirds_event.schemas.common import SchemaKind
from sixbirds_event.schemas.result_note import ResultNote
from sixbirds_event.schemas.run_manifest import RunManifest
from sixbirds_event.run_registry import format_directory_timestamp, slugify
from sixbirds_event.search.models import (
    ContextPairStructureTable,
    PicaFrozenSliceSearch,
    PicaFrozenSliceSearchTable,
    ProjectionFamilyAdmissibilityTable,
)
from sixbirds_event.search.pica_frozen_slice_obstruction import (
    run_pica_frozen_slice_search,
)
from sixbirds_event.validation import load_model, validate_file


SEARCH_CONFIG = Path("experiments/configs/pica/frozen-slice-obstruction-campaign.json")


def _fresh_timestamp(
    *, label: str, category: str = "search", offset_seconds: int = 0
) -> str:
    base = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(
        seconds=offset_seconds
    )
    results_root = Path.cwd() / "results" / category
    label_token = slugify(label) or "run"
    for extra_seconds in range(120):
        candidate = base + timedelta(seconds=extra_seconds)
        directory_name = (
            f"{format_directory_timestamp(candidate.isoformat())}--{label_token}"
        )
        if not (results_root / directory_name).exists():
            return candidate.isoformat().replace("+00:00", "Z")
    raise AssertionError("unable to find unused timestamp for frozen-slice test run")


def test_frozen_slice_search_config_validates() -> None:
    result = validate_file(SEARCH_CONFIG, kind=SchemaKind.PICA_FROZEN_SLICE_SEARCH)
    assert result.ok
    assert result.kind == SchemaKind.PICA_FROZEN_SLICE_SEARCH
    assert isinstance(result.model, PicaFrozenSliceSearch)
    assert len(result.model.points) == 3
    assert len(result.model.projection_families) >= 5


def test_committed_frozen_slice_campaign_runs_end_to_end() -> None:
    timestamp = _fresh_timestamp(label="pica-frozen-slice-test")
    artifacts = run_pica_frozen_slice_search(
        search_path=SEARCH_CONFIG.as_posix(),
        category="search",
        label="pica-frozen-slice-test",
        seed=0,
        timestamp=timestamp,
        root=Path.cwd(),
    )

    config_model = load_model(SEARCH_CONFIG, kind=SchemaKind.PICA_FROZEN_SLICE_SEARCH)
    table = load_model(
        Path(artifacts.table_json_path),
        kind=SchemaKind.PICA_FROZEN_SLICE_SEARCH_RESULTS,
    )
    pair_table = load_model(
        Path(artifacts.context_pair_structure_path),
        kind=SchemaKind.CONTEXT_PAIR_STRUCTURE,
    )
    admissibility_table = load_model(
        Path(artifacts.projection_family_admissibility_path),
        kind=SchemaKind.PROJECTION_FAMILY_ADMISSIBILITY,
    )
    result_note = load_model(
        Path(artifacts.result_note_path), kind=SchemaKind.RESULT_NOTE
    )
    manifest = load_model(Path(artifacts.manifest_path), kind=SchemaKind.RUN_MANIFEST)

    assert isinstance(config_model, PicaFrozenSliceSearch)
    assert isinstance(table, PicaFrozenSliceSearchTable)
    assert isinstance(pair_table, ContextPairStructureTable)
    assert isinstance(admissibility_table, ProjectionFamilyAdmissibilityTable)
    assert isinstance(result_note, ResultNote)
    assert isinstance(manifest, RunManifest)
    assert table.search_id == config_model.search_id
    assert table.row_count == len(config_model.points)
    assert table.row_count == 3
    assert pair_table.search_id == config_model.search_id
    assert admissibility_table.search_id == config_model.search_id
    assert pair_table.row_count >= 1
    assert admissibility_table.row_count >= table.row_count

    with Path(artifacts.table_csv_path).open(
        "r", encoding="utf-8", newline=""
    ) as handle:
        csv_rows = list(csv.DictReader(handle))
    assert len(csv_rows) == table.row_count

    summary_payload = json.loads(
        Path(artifacts.summary_path).read_text(encoding="utf-8")
    )
    note = Path(artifacts.note_path).read_text(encoding="utf-8")

    assert summary_payload["outcome_kind"] in {
        "best_candidate",
        "negative_result",
        "design_inadequate",
    }
    assert "projection_family_admissibility_summary" in summary_payload
    assert "adequacy_floor_result" in summary_payload
    assert (
        "Primary source-pair identity requires matching preparation, protocol, protocol_step_id, and step_index"
        in note
    )
    assert "Cross-step contexts may act as probes or diagnostics" in note
    assert "Primary projection families" in note
    assert "Baseline hard-only mode" in note
    assert "All-accepted-proposals mode" in note
    assert "RM is diagnostic-only" in note

    assert all(row.provenance_classification == "admissible" for row in table.rows)
    assert any(row.same_slice_non_nested_context_pair_count > 0 for row in table.rows)
    assert any(
        row.accepted_primary_same_slice_proper_coarse_proposal_count > 0
        for row in table.rows
    )
    assert any(
        pair.same_frozen_slice
        and pair.primary_identity_admissible
        and pair.relation_type == "incomparable"
        for pair in pair_table.rows
    )
    assert any(
        row.projection_kind in {"packaging_outcome", "derived_row_outcome"}
        and "primary_context" in row.allowed_roles
        for row in admissibility_table.rows
    )

    outcome_paths = [
        Path(artifacts.outcome_path),
        Path(artifacts.run_dir) / "best-candidate.json",
        Path(artifacts.run_dir) / "negative-result.json",
        Path(artifacts.run_dir) / "design-inadequate-result.json",
    ]
    existing_outcomes = {path.name for path in outcome_paths if path.exists()}
    assert len(existing_outcomes) == 1

    adequacy = summary_payload["adequacy_floor_result"]
    assert "adequate" in adequacy
    assert "checks" in adequacy
    assert "counts" in adequacy

    if summary_payload["outcome_kind"] == "best_candidate":
        payload = json.loads(Path(artifacts.outcome_path).read_text(encoding="utf-8"))
        assert payload["accepted_primary_same_slice_proper_coarse_proposal_count"] >= 1
        assert payload["provenance_classification"] == "admissible"
    elif summary_payload["outcome_kind"] == "negative_result":
        payload = json.loads(Path(artifacts.outcome_path).read_text(encoding="utf-8"))
        assert payload["adequacy_floor_met"] is True
        assert payload["negative_result"] is True
    else:
        payload = json.loads(Path(artifacts.outcome_path).read_text(encoding="utf-8"))
        assert payload["adequacy_floor_met"] is False
        assert payload["outcome"] == "design_inadequate"

    assert manifest.metadata["analysis_kind"] == "pica_frozen_slice_search"
    assert "table_csv" in manifest.output_artifacts
    assert "table_json" in manifest.output_artifacts
    assert "context_pair_structure" in manifest.output_artifacts
    assert "projection_family_admissibility" in manifest.output_artifacts
    assert "summary" in manifest.output_artifacts
    assert "note" in manifest.output_artifacts


def test_cli_smoke_runs_committed_frozen_slice_campaign() -> None:
    timestamp = _fresh_timestamp(
        label="pica-frozen-slice-cli-test",
        offset_seconds=5,
    )
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "sixbirds_event",
            "search",
            "run-frozen-slice-obstruction",
            SEARCH_CONFIG.as_posix(),
            "--category",
            "search",
            "--label",
            "pica-frozen-slice-cli-test",
            "--timestamp",
            timestamp,
            "--root",
            str(Path.cwd()),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "run_id=" in result.stdout
    assert "frozen_slice_search_csv=" in result.stdout
    assert "frozen_slice_search_json=" in result.stdout
    assert "context_pair_structure=" in result.stdout
    assert "projection_family_admissibility=" in result.stdout
    assert "summary=" in result.stdout
    assert "outcome_kind=" in result.stdout
    assert "outcome=" in result.stdout
