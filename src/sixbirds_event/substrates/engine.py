from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import random
import sys

from ..run_registry import (
    build_run_manifest,
    create_run_directory,
    detect_git_commit,
    repo_relative_path,
    write_run_manifest,
)
from ..validation import load_model
from .config import SubstrateConfig
from .run_trace import SubstrateRun, TrajectoryRecord, TrajectoryStep


@dataclass(slots=True)
class SubstrateRunArtifacts:
    run_id: str
    run_dir: str
    manifest_path: str
    run_trace_path: str
    summary_path: str
    run_trace: SubstrateRun
    summary: dict[str, object]


def load_substrate_config(path: str | Path) -> SubstrateConfig:
    model = load_model(path, kind="substrate-config")
    assert isinstance(model, SubstrateConfig)
    return model


def load_substrate_run(path: str | Path) -> SubstrateRun:
    model = load_model(path, kind="substrate-run")
    assert isinstance(model, SubstrateRun)
    return model


def _sorted_distribution_items(
    distribution: dict[str, float],
) -> list[tuple[str, float]]:
    return sorted(distribution.items())


def _sample_distribution(
    distribution: dict[str, float],
    *,
    rng: random.Random,
) -> str:
    threshold = rng.random()
    cumulative = 0.0
    items = _sorted_distribution_items(distribution)
    for state_id, probability in items:
        cumulative += probability
        if threshold <= cumulative:
            return state_id
    return items[-1][0]


def _lookup_distribution_by_id(values: list[object], *, key: str) -> dict[str, object]:
    return {
        getattr(value, key): value  # type: ignore[misc]
        for value in values
    }


def simulate_substrate_run(
    config: SubstrateConfig,
    *,
    run_id: str,
    config_artifact: str,
    preparation_id: str,
    protocol_id: str,
    trajectory_count: int,
    seed: int,
) -> SubstrateRun:
    preparation_by_id = _lookup_distribution_by_id(
        config.preparations, key="preparation_id"
    )
    protocol_by_id = _lookup_distribution_by_id(config.protocols, key="protocol_id")
    action_by_id = _lookup_distribution_by_id(config.actions, key="action_id")
    lenses = config.lenses

    try:
        preparation = preparation_by_id[preparation_id]
    except KeyError as exc:
        raise ValueError(f"unknown preparation_id '{preparation_id}'") from exc
    try:
        protocol = protocol_by_id[protocol_id]
    except KeyError as exc:
        raise ValueError(f"unknown protocol_id '{protocol_id}'") from exc

    rng = random.Random(seed)
    trajectories: list[TrajectoryRecord] = []
    for trajectory_index in range(trajectory_count):
        initial_state_id = _sample_distribution(preparation.distribution, rng=rng)
        current_state_id = initial_state_id
        steps: list[TrajectoryStep] = []
        for step_index, action_id in enumerate(protocol.action_ids):
            action = action_by_id[action_id]
            transition_distribution = action.transition_kernel[current_state_id]
            next_state_id = _sample_distribution(transition_distribution, rng=rng)
            observations = {
                lens.lens_id: lens.readout_map[next_state_id] for lens in lenses
            }
            steps.append(
                TrajectoryStep(
                    step_index=step_index,
                    action_id=action_id,
                    state_before=current_state_id,
                    state_after=next_state_id,
                    observations=observations,
                )
            )
            current_state_id = next_state_id
        trajectories.append(
            TrajectoryRecord(
                trajectory_id=f"traj_{trajectory_index + 1:04d}",
                preparation_id=preparation_id,
                protocol_id=protocol_id,
                initial_state_id=initial_state_id,
                steps=steps,
            )
        )

    return SubstrateRun(
        run_format_version="substrate-run.v1",
        run_id=run_id,
        config_id=config.config_id,
        config_artifact=config_artifact,
        seed=seed,
        preparation_id=preparation_id,
        protocol_id=protocol_id,
        trajectory_count=trajectory_count,
        trajectories=trajectories,
        metadata={
            "lens_ids": [lens.lens_id for lens in lenses],
            "protocol_length": len(protocol.action_ids),
        },
    )


def summarize_substrate_run(run_trace: SubstrateRun) -> dict[str, object]:
    state_visit_counts: dict[str, int] = {}
    lens_outcome_counts: dict[str, dict[str, int]] = {}
    total_steps = 0

    for trajectory in run_trace.trajectories:
        state_visit_counts[trajectory.initial_state_id] = (
            state_visit_counts.get(trajectory.initial_state_id, 0) + 1
        )
        for step in trajectory.steps:
            total_steps += 1
            state_visit_counts[step.state_after] = (
                state_visit_counts.get(step.state_after, 0) + 1
            )
            for lens_id, observation_label in step.observations.items():
                lens_counts = lens_outcome_counts.setdefault(lens_id, {})
                lens_counts[observation_label] = (
                    lens_counts.get(observation_label, 0) + 1
                )

    return {
        "config_id": run_trace.config_id,
        "config_artifact": run_trace.config_artifact,
        "run_id": run_trace.run_id,
        "seed": run_trace.seed,
        "preparation_id": run_trace.preparation_id,
        "protocol_id": run_trace.protocol_id,
        "trajectory_count": run_trace.trajectory_count,
        "total_steps": total_steps,
        "state_visit_counts": dict(sorted(state_visit_counts.items())),
        "lens_outcome_counts": {
            lens_id: dict(sorted(outcomes.items()))
            for lens_id, outcomes in sorted(lens_outcome_counts.items())
        },
        "state_visit_policy": "counts initial_state_id plus every per-step state_after value",
        "observation_policy": "per-step observations are emitted from all lenses on state_after",
    }


def write_substrate_run(
    config: SubstrateConfig,
    *,
    config_path: str | Path,
    preparation_id: str,
    protocol_id: str,
    trajectories: int | None = None,
    seed: int | None = None,
    category: str,
    label: str | None = None,
    timestamp: str | None = None,
    root: str | Path | None = None,
    command: list[str] | None = None,
) -> SubstrateRunArtifacts:
    repo_root = Path(root).resolve() if root is not None else None
    run_dir, run_id, manifest_timestamp = create_run_directory(
        category=category,
        label=label,
        timestamp=timestamp,
        root=repo_root,
    )
    effective_root = run_dir.parents[2]
    config_relpath = repo_relative_path(config_path, root=effective_root)

    trajectory_count = (
        trajectories
        if trajectories is not None
        else (
            config.defaults.trajectory_count
            if config.defaults is not None
            and config.defaults.trajectory_count is not None
            else 1
        )
    )
    seed_value = (
        seed
        if seed is not None
        else (
            config.defaults.seed
            if config.defaults is not None and config.defaults.seed is not None
            else 0
        )
    )
    run_trace = simulate_substrate_run(
        config,
        run_id=run_id,
        config_artifact=config_relpath,
        preparation_id=preparation_id,
        protocol_id=protocol_id,
        trajectory_count=trajectory_count,
        seed=seed_value,
    )

    run_trace_path = run_dir / "substrate-run.json"
    summary_path = run_dir / "substrate-summary.json"
    manifest_path = run_dir / "run-manifest.json"
    output_paths = {
        "substrate_run": repo_relative_path(run_trace_path, root=effective_root),
        "summary": repo_relative_path(summary_path, root=effective_root),
        "manifest": repo_relative_path(manifest_path, root=effective_root),
    }

    run_trace_path.write_text(
        json.dumps(run_trace.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    summary = summarize_substrate_run(run_trace)
    summary_payload = {
        **summary,
        "artifact_refs": output_paths,
    }
    summary_path.write_text(
        json.dumps(summary_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    manifest = build_run_manifest(
        run_id=run_id,
        timestamp=manifest_timestamp,
        command=command
        or [
            sys.executable,
            "-m",
            "sixbirds_event",
            "substrates",
            "run",
            config_relpath,
        ],
        seed=seed_value,
        input_artifacts={"config": config_relpath},
        output_artifacts={
            "substrate_run": output_paths["substrate_run"],
            "summary": output_paths["summary"],
        },
        status="succeeded",
        git_commit=detect_git_commit(root=effective_root),
        metadata={
            "analysis_kind": "substrate_run",
            "config_id": config.config_id,
            "preparation_id": preparation_id,
            "protocol_id": protocol_id,
            "trajectory_count": trajectory_count,
        },
    )
    write_run_manifest(manifest, run_dir=run_dir)

    return SubstrateRunArtifacts(
        run_id=run_id,
        run_dir=repo_relative_path(run_dir, root=effective_root),
        manifest_path=output_paths["manifest"],
        run_trace_path=output_paths["substrate_run"],
        summary_path=output_paths["summary"],
        run_trace=run_trace,
        summary=summary_payload,
    )
