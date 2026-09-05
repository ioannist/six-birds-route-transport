from __future__ import annotations

import math
from typing import Literal

from pydantic import Field, model_validator

from ..schemas.common import (
    MetadataValue,
    SixBirdsModel,
    collect_list_duplicates,
    ensure_metadata_shape,
    ensure_repo_relative_mapping,
    is_repo_relative_path,
)


RobustnessStatus = Literal[
    "solved", "unsolved", "scored", "insufficient_data", "not_applicable"
]
TargetType = Literal["benchmark", "discovered_package"]


class RobustnessTraceArtifacts(SixBirdsModel):
    stat: str | None = None
    ccd: str | None = None
    sec: str | None = None
    rm: str | None = None

    @model_validator(mode="after")
    def validate_artifacts(self) -> "RobustnessTraceArtifacts":
        for field_name in ["stat", "ccd", "sec", "rm"]:
            value = getattr(self, field_name)
            if value is not None and not is_repo_relative_path(value):
                raise ValueError(
                    f"{field_name} must be a normalized repo-relative path when present"
                )
        return self


class NoiseMetricThresholds(SixBirdsModel):
    gpd_stat_failure_threshold: float
    ccd_failure_threshold: float
    sec_failure_threshold: float
    rm_failure_threshold: float

    @model_validator(mode="after")
    def validate_thresholds(self) -> "NoiseMetricThresholds":
        for name in [
            "gpd_stat_failure_threshold",
            "ccd_failure_threshold",
            "sec_failure_threshold",
            "rm_failure_threshold",
        ]:
            value = getattr(self, name)
            if isinstance(value, bool) or not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be a finite non-negative value")
        return self


class NoiseModelConfig(SixBirdsModel):
    base_seed: int
    distribution_model: str = "independent_jitter_mix_v1"
    ccd_model: str = "singleton_corruption_v1"

    @model_validator(mode="after")
    def validate_config(self) -> "NoiseModelConfig":
        if isinstance(self.base_seed, bool):
            raise ValueError("base_seed must be an integer")
        if not self.distribution_model:
            raise ValueError("distribution_model must be a non-empty string")
        if not self.ccd_model:
            raise ValueError("ccd_model must be a non-empty string")
        return self


class NoiseRobustnessTarget(SixBirdsModel):
    target_id: str
    target_type: TargetType
    event_package_artifact: str
    trace_artifacts: RobustnessTraceArtifacts
    noise_grid_override: list[float] | None = None
    metric_threshold_overrides: NoiseMetricThresholds | None = None
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_target(self) -> "NoiseRobustnessTarget":
        if not self.target_id:
            raise ValueError("target_id must be a non-empty string")
        ensure_repo_relative_mapping(
            {"event_package_artifact": self.event_package_artifact},
            field_name="event_package_artifact",
        )
        if self.noise_grid_override is not None:
            if not self.noise_grid_override:
                raise ValueError("noise_grid_override must not be empty when present")
            for noise_level in self.noise_grid_override:
                if (
                    isinstance(noise_level, bool)
                    or not math.isfinite(noise_level)
                    or noise_level < 0
                    or noise_level > 1
                ):
                    raise ValueError(
                        "noise_grid_override values must be finite values in [0, 1]"
                    )
        if any(not note for note in self.notes):
            raise ValueError("notes must contain only non-empty strings")
        return self


class NoiseRobustnessSweep(SixBirdsModel):
    sweep_format_version: str
    sweep_id: str
    targets: list[NoiseRobustnessTarget]
    noise_grid: list[float]
    noise_model: NoiseModelConfig
    metric_thresholds: NoiseMetricThresholds
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_sweep(self) -> "NoiseRobustnessSweep":
        if self.sweep_format_version != "noise-robustness-sweep.v1":
            raise ValueError(
                "sweep_format_version must equal 'noise-robustness-sweep.v1'"
            )
        if not self.sweep_id:
            raise ValueError("sweep_id must be a non-empty string")
        if not self.targets:
            raise ValueError("targets must not be empty")
        duplicates = collect_list_duplicates(
            [target.target_id for target in self.targets]
        )
        if duplicates:
            raise ValueError(
                f"target_id values must be unique: {', '.join(duplicates)}"
            )
        if not self.noise_grid:
            raise ValueError("noise_grid must not be empty")
        for noise_level in self.noise_grid:
            if (
                isinstance(noise_level, bool)
                or not math.isfinite(noise_level)
                or noise_level < 0
                or noise_level > 1
            ):
                raise ValueError("noise_grid values must be finite values in [0, 1]")
        ensure_metadata_shape(self.metadata)
        return self


class NoiseRobustnessRow(SixBirdsModel):
    row_format_version: str
    sweep_id: str
    target_id: str
    target_type: TargetType
    noise_level: float
    event_package_path: str
    noisy_trace_artifacts: RobustnessTraceArtifacts
    gpd_stat_status: RobustnessStatus
    gpd_stat: float | None = None
    gpd_stat_reason: str | None = None
    ccd_status: RobustnessStatus
    ccd_overall: float | None = None
    sec_status: RobustnessStatus
    sec_mean: float | None = None
    rm_status: RobustnessStatus
    rm_overall: float | None = None
    gpd_stat_threshold_crossed: bool | None = None
    ccd_threshold_crossed: bool | None = None
    sec_threshold_crossed: bool | None = None
    rm_threshold_crossed: bool | None = None
    baseline_exact_structural_feasible_hard_only: bool | None = None
    baseline_gpd_str: float | None = None
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_row(self) -> "NoiseRobustnessRow":
        if self.row_format_version != "noise-robustness-row.v1":
            raise ValueError("row_format_version must equal 'noise-robustness-row.v1'")
        if not self.sweep_id:
            raise ValueError("sweep_id must be a non-empty string")
        if not self.target_id:
            raise ValueError("target_id must be a non-empty string")
        if not is_repo_relative_path(self.event_package_path):
            raise ValueError(
                "event_package_path must be a normalized repo-relative path"
            )
        if (
            isinstance(self.noise_level, bool)
            or not math.isfinite(self.noise_level)
            or self.noise_level < 0
            or self.noise_level > 1
        ):
            raise ValueError("noise_level must be a finite value in [0, 1]")
        if self.gpd_stat_status == "solved":
            if self.gpd_stat is None:
                raise ValueError(
                    "gpd_stat must be present when gpd_stat_status is solved"
                )
        elif self.gpd_stat is not None:
            raise ValueError("gpd_stat must be null unless gpd_stat_status is solved")
        for status_name, value_name in [
            ("ccd_status", "ccd_overall"),
            ("sec_status", "sec_mean"),
            ("rm_status", "rm_overall"),
        ]:
            status = getattr(self, status_name)
            value = getattr(self, value_name)
            if status == "scored":
                if value is None:
                    raise ValueError(
                        f"{value_name} must be present when {status_name} is scored"
                    )
            elif value is not None:
                raise ValueError(
                    f"{value_name} must be null unless {status_name} is scored"
                )
        for flag_name in [
            "gpd_stat_threshold_crossed",
            "ccd_threshold_crossed",
            "sec_threshold_crossed",
            "rm_threshold_crossed",
        ]:
            flag = getattr(self, flag_name)
            if flag is not None and not isinstance(flag, bool):
                raise ValueError(f"{flag_name} must be a boolean or null")
        for value_name in [
            "gpd_stat",
            "ccd_overall",
            "sec_mean",
            "rm_overall",
            "baseline_gpd_str",
        ]:
            value = getattr(self, value_name)
            if value is not None and (
                isinstance(value, bool) or not math.isfinite(value) or value < 0
            ):
                raise ValueError(f"{value_name} must be a finite non-negative value")
        if any(not note for note in self.notes):
            raise ValueError("notes must contain only non-empty strings")
        return self


class NoiseRobustnessTable(SixBirdsModel):
    table_format_version: str
    sweep_id: str
    row_count: int
    rows: list[NoiseRobustnessRow]
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_table(self) -> "NoiseRobustnessTable":
        if self.table_format_version != "noise-robustness-table.v1":
            raise ValueError(
                "table_format_version must equal 'noise-robustness-table.v1'"
            )
        if not self.sweep_id:
            raise ValueError("sweep_id must be a non-empty string")
        if self.row_count != len(self.rows):
            raise ValueError("row_count must equal len(rows)")
        duplicates = collect_list_duplicates(
            [f"{row.target_id}:{row.noise_level}" for row in self.rows]
        )
        if duplicates:
            raise ValueError("rows must be unique by (target_id, noise_level)")
        if any(row.sweep_id != self.sweep_id for row in self.rows):
            raise ValueError("all rows must share the table sweep_id")
        ensure_metadata_shape(self.metadata)
        return self
