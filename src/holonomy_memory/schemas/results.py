from __future__ import annotations

from pydantic import Field, model_validator

from .common import HolonomyMemoryModel, ensure_finite_nonnegative_number, ensure_nonempty_string, ensure_unique_strings
from .enums import (
    AuditStatus,
    BenchmarkResultManifestVersion,
    ClassLabel,
    DiscrepancyMetricName,
)


class InterfaceResultRecord(HolonomyMemoryModel):
    benchmark_id: str
    interface_id: str
    history_count: int = Field(ge=0)
    current_quotient_size: int = Field(ge=0)
    predictive_quotient_size: int = Field(ge=0)
    witness_count: int = Field(ge=0)
    max_fiber_size: int = Field(ge=0)
    discrepancy_metric_name: DiscrepancyMetricName
    discrepancy_metric_value: float
    loop_action_score_current_quotient: float
    loop_action_score_predictive_quotient: float
    support_fixation_status: AuditStatus
    currentization_status: AuditStatus
    flattening_status: AuditStatus
    robustness_fraction: float = Field(ge=0, le=1)
    class_label: ClassLabel
    runtime: float = Field(ge=0)
    seed: int

    @model_validator(mode="after")
    def validate_record(self) -> "InterfaceResultRecord":
        ensure_nonempty_string(self.benchmark_id, "benchmark_id")
        ensure_nonempty_string(self.interface_id, "interface_id")
        ensure_finite_nonnegative_number(
            self.discrepancy_metric_value, "discrepancy_metric_value"
        )
        ensure_finite_nonnegative_number(
            self.loop_action_score_current_quotient,
            "loop_action_score_current_quotient",
        )
        ensure_finite_nonnegative_number(
            self.loop_action_score_predictive_quotient,
            "loop_action_score_predictive_quotient",
        )
        ensure_finite_nonnegative_number(self.runtime, "runtime")
        return self


class BenchmarkResultManifest(HolonomyMemoryModel):
    schema_version: BenchmarkResultManifestVersion = BenchmarkResultManifestVersion.V1
    manifest_id: str
    benchmark_id: str
    records: list[InterfaceResultRecord] = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_manifest(self) -> "BenchmarkResultManifest":
        ensure_nonempty_string(self.manifest_id, "manifest_id")
        ensure_nonempty_string(self.benchmark_id, "benchmark_id")
        ensure_unique_strings([record.interface_id for record in self.records], "interface_ids")
        for record in self.records:
            if record.benchmark_id != self.benchmark_id:
                raise ValueError("all records must match benchmark_id")
        for tag in self.tags:
            ensure_nonempty_string(tag, "tags")
        return self
