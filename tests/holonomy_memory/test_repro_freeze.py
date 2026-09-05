from __future__ import annotations

import json
from pathlib import Path

from holonomy_memory import (
    FROZEN_REPRO_COMMANDS,
    ReproCommandStatus,
    ReproFreezeSummary,
    run_benchmark_suite,
    run_discovery_smoke,
    write_repro_freeze_summary,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_reproducibility_ops_note_mentions_frozen_commands_and_outputs() -> None:
    note_path = REPO_ROOT / "docs" / "ops" / "reproducibility.md"
    note_text = note_path.read_text(encoding="utf-8")

    for command in FROZEN_REPRO_COMMANDS:
        assert command in note_text
    for output_path in (
        "artifacts/results/benchmark_suite.json",
        "artifacts/tables/benchmark_suite.csv",
        "docs/results/benchmark_suite.md",
        "artifacts/results/discovery/discovery_smoke.json",
        "docs/results/discovery_smoke.md",
        "artifacts/results/repro_freeze.json",
        "lean/",
        "seed = 0",
        "temporary clean checkout",
    ):
        assert output_path in note_text


def test_write_repro_freeze_summary_writes_expected_schema(tmp_path: Path) -> None:
    benchmark_artifacts = run_benchmark_suite(seed=0, output_root=tmp_path)
    discovery_artifacts = run_discovery_smoke(seed=0, output_root=tmp_path)

    summary = ReproFreezeSummary(
        seed=0,
        commands=FROZEN_REPRO_COMMANDS,
        verified_from_temporary_clean_copy=True,
        command_statuses=tuple(
            ReproCommandStatus(command=command, passed=True) for command in FROZEN_REPRO_COMMANDS
        ),
        benchmark_suite_semantics_match=True,
        discovery_smoke_semantics_match=True,
        benchmark_suite_artifact_paths=(
            "artifacts/results/benchmark_suite.json",
            "artifacts/tables/benchmark_suite.csv",
            "docs/results/benchmark_suite.md",
        ),
        discovery_smoke_artifact_paths=(
            "artifacts/results/discovery/discovery_smoke.json",
            "docs/results/discovery_smoke.md",
        ),
    )

    artifacts = write_repro_freeze_summary(summary=summary, output_root=tmp_path)
    assert benchmark_artifacts.summary_json_path.exists()
    assert discovery_artifacts.summary_json_path.exists()
    assert artifacts.summary_json_path.exists()

    payload = json.loads(artifacts.summary_json_path.read_text(encoding="utf-8"))
    assert tuple(payload["commands"]) == FROZEN_REPRO_COMMANDS
    assert payload["seed"] == 0
    assert payload["verified_from_temporary_clean_copy"] is True
    assert payload["benchmark_suite_semantics_match"] is True
    assert payload["discovery_smoke_semantics_match"] is True
    assert len(payload["command_statuses"]) == len(FROZEN_REPRO_COMMANDS)
    assert tuple(payload["benchmark_suite_artifact_paths"]) == (
        "artifacts/results/benchmark_suite.json",
        "artifacts/tables/benchmark_suite.csv",
        "docs/results/benchmark_suite.md",
    )
    assert tuple(payload["discovery_smoke_artifact_paths"]) == (
        "artifacts/results/discovery/discovery_smoke.json",
        "docs/results/discovery_smoke.md",
    )
