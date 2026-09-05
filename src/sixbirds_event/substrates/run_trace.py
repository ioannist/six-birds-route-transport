from __future__ import annotations

from pydantic import Field, field_validator, model_validator

from ..schemas.common import (
    MetadataValue,
    SixBirdsModel,
    collect_list_duplicates,
    ensure_metadata_shape,
    is_repo_relative_path,
)


class TrajectoryStep(SixBirdsModel):
    step_index: int
    action_id: str
    state_before: str
    state_after: str
    observations: dict[str, str]

    @model_validator(mode="after")
    def validate_step(self) -> "TrajectoryStep":
        if isinstance(self.step_index, bool) or self.step_index < 0:
            raise ValueError("step_index must be a non-negative integer")
        if not self.action_id:
            raise ValueError("action_id must be a non-empty string")
        if not self.state_before:
            raise ValueError("state_before must be a non-empty string")
        if not self.state_after:
            raise ValueError("state_after must be a non-empty string")
        if not self.observations:
            raise ValueError("observations must not be empty")
        for lens_id, observation_label in self.observations.items():
            if not lens_id:
                raise ValueError("observations keys must be non-empty strings")
            if not observation_label:
                raise ValueError("observations values must be non-empty strings")
        return self


class TrajectoryRecord(SixBirdsModel):
    trajectory_id: str
    preparation_id: str
    protocol_id: str
    initial_state_id: str
    steps: list[TrajectoryStep]

    @field_validator("steps")
    @classmethod
    def validate_steps(cls, steps: list[TrajectoryStep]) -> list[TrajectoryStep]:
        if not steps:
            raise ValueError("steps must not be empty")
        expected = list(range(len(steps)))
        actual = [step.step_index for step in steps]
        if actual != expected:
            raise ValueError(
                "step_index values must form a contiguous zero-based range"
            )
        return steps


class SubstrateRun(SixBirdsModel):
    run_format_version: str
    run_id: str
    config_id: str
    config_artifact: str
    seed: int
    preparation_id: str
    protocol_id: str
    trajectory_count: int
    trajectories: list[TrajectoryRecord]
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_run(self) -> "SubstrateRun":
        if self.run_format_version != "substrate-run.v1":
            raise ValueError("run_format_version must equal 'substrate-run.v1'")
        if not is_repo_relative_path(self.config_artifact):
            raise ValueError("config_artifact must be a normalized repo-relative path")
        if isinstance(self.seed, bool):
            raise ValueError("seed must be an integer")
        if isinstance(self.trajectory_count, bool) or self.trajectory_count <= 0:
            raise ValueError("trajectory_count must be a positive integer")
        if not self.trajectories:
            raise ValueError("trajectories must not be empty")
        if self.trajectory_count != len(self.trajectories):
            raise ValueError("trajectory_count must equal len(trajectories)")

        ensure_metadata_shape(self.metadata)

        trajectory_ids = [trajectory.trajectory_id for trajectory in self.trajectories]
        duplicates = collect_list_duplicates(trajectory_ids)
        if duplicates:
            raise ValueError(
                f"trajectory_id values must be unique: {', '.join(duplicates)}"
            )
        for trajectory in self.trajectories:
            if trajectory.preparation_id != self.preparation_id:
                raise ValueError(
                    "trajectory preparation_id values must match the top-level preparation_id"
                )
            if trajectory.protocol_id != self.protocol_id:
                raise ValueError(
                    "trajectory protocol_id values must match the top-level protocol_id"
                )
        return self
