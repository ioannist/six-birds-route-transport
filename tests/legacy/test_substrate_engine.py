from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from sixbirds_event.schemas.common import SchemaKind
from sixbirds_event.schemas.run_manifest import RunManifest
from sixbirds_event.substrates.engine import (
    load_substrate_config,
    simulate_substrate_run,
    write_substrate_run,
)
from sixbirds_event.substrates.run_trace import SubstrateRun
from sixbirds_event.validation import load_model, validate_payload


CONFIG_DIR = Path("experiments/configs/substrates")


def test_valid_config_loads() -> None:
    config = load_substrate_config(CONFIG_DIR / "deterministic-cycle.json")
    assert config.config_id == "cfg_deterministic_cycle"


def test_invalid_config_with_bad_probability_normalization_is_rejected() -> None:
    payload = {
        "config_format_version": "substrate-config.v1",
        "config_id": "cfg_invalid",
        "states": [{"state_id": "s0"}, {"state_id": "s1"}],
        "preparations": [
            {
                "preparation_id": "prep0",
                "distribution": {"s0": 0.8, "s1": 0.3},
            }
        ],
        "actions": [
            {
                "action_id": "flip",
                "transition_kernel": {
                    "s0": {"s1": 1.0},
                    "s1": {"s0": 1.0},
                },
            }
        ],
        "lenses": [
            {
                "lens_id": "binary",
                "readout_map": {"s0": "zero", "s1": "one"},
            }
        ],
        "protocols": [{"protocol_id": "flip1", "action_ids": ["flip"]}],
        "metadata": {},
    }
    result = validate_payload(payload, kind=SchemaKind.SUBSTRATE_CONFIG)
    assert not result.ok
    assert any("sum to 1" in issue.message for issue in result.issues)


def test_deterministic_run_is_reproducible() -> None:
    config = load_substrate_config(CONFIG_DIR / "deterministic-cycle.json")
    first = simulate_substrate_run(
        config,
        run_id="run_demo",
        config_artifact=(CONFIG_DIR / "deterministic-cycle.json").as_posix(),
        preparation_id="prep0",
        protocol_id="cycle5",
        trajectory_count=4,
        seed=17,
    )
    second = simulate_substrate_run(
        config,
        run_id="run_demo",
        config_artifact=(CONFIG_DIR / "deterministic-cycle.json").as_posix(),
        preparation_id="prep0",
        protocol_id="cycle5",
        trajectory_count=4,
        seed=17,
    )
    assert first.model_dump(mode="json") == second.model_dump(mode="json")


def test_stochastic_run_is_reproducible_with_same_seed() -> None:
    config = load_substrate_config(CONFIG_DIR / "stochastic-two-state.json")
    first = simulate_substrate_run(
        config,
        run_id="run_demo",
        config_artifact=(CONFIG_DIR / "stochastic-two-state.json").as_posix(),
        preparation_id="prep0",
        protocol_id="flip6",
        trajectory_count=20,
        seed=123,
    )
    second = simulate_substrate_run(
        config,
        run_id="run_demo",
        config_artifact=(CONFIG_DIR / "stochastic-two-state.json").as_posix(),
        preparation_id="prep0",
        protocol_id="flip6",
        trajectory_count=20,
        seed=123,
    )
    assert first.model_dump(mode="json") == second.model_dump(mode="json")


def test_stochastic_run_changes_with_different_seed() -> None:
    config = load_substrate_config(CONFIG_DIR / "stochastic-two-state.json")
    first = simulate_substrate_run(
        config,
        run_id="run_demo",
        config_artifact=(CONFIG_DIR / "stochastic-two-state.json").as_posix(),
        preparation_id="prep0",
        protocol_id="flip6",
        trajectory_count=20,
        seed=123,
    )
    second = simulate_substrate_run(
        config,
        run_id="run_demo",
        config_artifact=(CONFIG_DIR / "stochastic-two-state.json").as_posix(),
        preparation_id="prep0",
        protocol_id="flip6",
        trajectory_count=20,
        seed=124,
    )
    assert first.model_dump(mode="json") != second.model_dump(mode="json")


def test_raw_run_files_are_written_and_parseable(tmp_path: Path) -> None:
    config_path = CONFIG_DIR / "deterministic-cycle.json"
    config = load_substrate_config(config_path)
    artifacts = write_substrate_run(
        config,
        config_path=config_path,
        preparation_id="prep0",
        protocol_id="cycle5",
        trajectories=4,
        seed=17,
        category="search",
        label="deterministic-cycle",
        timestamp="2026-03-25T00:00:00Z",
        root=tmp_path,
    )

    run_trace = load_model(
        tmp_path / artifacts.run_trace_path, kind=SchemaKind.SUBSTRATE_RUN
    )
    assert isinstance(run_trace, SubstrateRun)
    manifest = load_model(
        tmp_path / artifacts.manifest_path, kind=SchemaKind.RUN_MANIFEST
    )
    assert isinstance(manifest, RunManifest)
    assert set(manifest.output_artifacts) == {"substrate_run", "summary"}

    summary = json.loads(
        (tmp_path / artifacts.summary_path).read_text(encoding="utf-8")
    )
    assert summary["config_id"] == config.config_id
    assert summary["trajectory_count"] == 4
    assert summary["total_steps"] == 20
    assert "phase" in summary["lens_outcome_counts"]


def test_cli_smoke_works_for_deterministic_and_stochastic_configs(
    tmp_path: Path,
) -> None:
    deterministic = subprocess.run(
        [
            sys.executable,
            "-m",
            "sixbirds_event",
            "substrates",
            "run",
            "experiments/configs/substrates/deterministic-cycle.json",
            "--preparation",
            "prep0",
            "--protocol",
            "cycle5",
            "--trajectories",
            "4",
            "--category",
            "search",
            "--label",
            "deterministic-cycle",
            "--timestamp",
            "2026-03-25T00:00:00Z",
            "--root",
            str(tmp_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    stochastic = subprocess.run(
        [
            sys.executable,
            "-m",
            "sixbirds_event",
            "substrates",
            "run",
            "experiments/configs/substrates/stochastic-two-state.json",
            "--preparation",
            "prep0",
            "--protocol",
            "flip6",
            "--trajectories",
            "20",
            "--seed",
            "123",
            "--category",
            "search",
            "--label",
            "stochastic-two-state",
            "--timestamp",
            "2026-03-25T00:00:01Z",
            "--root",
            str(tmp_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert deterministic.returncode == 0
    assert stochastic.returncode == 0
    assert "run_id=" in deterministic.stdout
    assert "substrate_run=" in deterministic.stdout
    assert "summary=" in stochastic.stdout
    assert "manifest=" in stochastic.stdout
