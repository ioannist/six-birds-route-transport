from __future__ import annotations

import math
from typing import Literal

from pydantic import Field, model_validator

from ..provenance.models import AdmissibilityClassification
from ..robustness.models import NoiseMetricThresholds, NoiseModelConfig
from ..schemas.common import (
    MetadataValue,
    SixBirdsModel,
    ensure_metadata_shape,
    ensure_repo_relative_mapping,
    is_repo_relative_path,
)
from ..search.models import AtlasStatus, TargetedSearchEvaluation


ApplicabilityStatus = Literal["completed", "not_applicable"]
DiscoveredCaseVerdict = Literal[
    "survived",
    "weakened",
    "disappeared",
    "no_baseline_obstruction",
    "inconclusive",
]
FlagshipCaseType = Literal[
    "mechanism_witness",
    "lens_flagship",
    "packaging_flagship",
]
FlagshipControlVerdict = Literal[
    "survived",
    "weakened",
    "disappeared",
    "not_applicable",
    "inconclusive",
]
FlagshipOverallVerdict = Literal[
    "all_applicable_flagships_survived",
    "mixed_outcomes",
    "some_disappeared",
    "mostly_not_applicable",
]


class SelectedDiscoveredCaseRefs(SixBirdsModel):
    case_id: str
    event_package_artifact: str
    package_provenance_artifact: str
    raw_run_artifact: str
    discovered_context_family_artifact: str
    shared_event_candidates_artifact: str
    source_config_artifact: str
    selection_artifact: str

    @model_validator(mode="after")
    def validate_refs(self) -> "SelectedDiscoveredCaseRefs":
        if not self.case_id:
            raise ValueError("case_id must be a non-empty string")
        ensure_repo_relative_mapping(
            {
                "event_package_artifact": self.event_package_artifact,
                "package_provenance_artifact": self.package_provenance_artifact,
                "raw_run_artifact": self.raw_run_artifact,
                "discovered_context_family_artifact": self.discovered_context_family_artifact,
                "shared_event_candidates_artifact": self.shared_event_candidates_artifact,
                "source_config_artifact": self.source_config_artifact,
                "selection_artifact": self.selection_artifact,
            },
            field_name="selected_case_artifacts",
        )
        return self


class BaselineEvaluationMetadata(SixBirdsModel):
    preparation_id: str
    protocol_id: str
    trajectories: int
    seed: int
    event_basis_mode: str
    max_union_size: int

    @model_validator(mode="after")
    def validate_metadata(self) -> "BaselineEvaluationMetadata":
        if not self.preparation_id:
            raise ValueError("preparation_id must be a non-empty string")
        if not self.protocol_id:
            raise ValueError("protocol_id must be a non-empty string")
        if isinstance(self.trajectories, bool) or self.trajectories <= 0:
            raise ValueError("trajectories must be a positive integer")
        if isinstance(self.seed, bool):
            raise ValueError("seed must be an integer")
        if not self.event_basis_mode:
            raise ValueError("event_basis_mode must be a non-empty string")
        if isinstance(self.max_union_size, bool) or self.max_union_size <= 0:
            raise ValueError("max_union_size must be a positive integer")
        return self


class InterventionApplicabilityConfig(SixBirdsModel):
    applicable: bool = False
    intervention_artifact: str | None = None
    reason: str | None = None

    @model_validator(mode="after")
    def validate_config(self) -> "InterventionApplicabilityConfig":
        if self.applicable:
            if self.intervention_artifact is None:
                raise ValueError(
                    "intervention_artifact must be provided when applicable is true"
                )
            if not is_repo_relative_path(self.intervention_artifact):
                raise ValueError(
                    "intervention_artifact must be a normalized repo-relative path"
                )
        elif self.intervention_artifact is not None and not is_repo_relative_path(
            self.intervention_artifact
        ):
            raise ValueError(
                "intervention_artifact must be a normalized repo-relative path when present"
            )
        if self.reason is not None and not self.reason:
            raise ValueError("reason must be non-empty when present")
        return self


class RobustnessSweepSettings(SixBirdsModel):
    noise_grid: list[float]
    noise_model: NoiseModelConfig
    metric_thresholds: NoiseMetricThresholds

    @model_validator(mode="after")
    def validate_settings(self) -> "RobustnessSweepSettings":
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
        return self


class DiscoveredCaseFalsification(SixBirdsModel):
    falsification_format_version: str
    falsification_id: str
    selected_case: SelectedDiscoveredCaseRefs
    baseline_evaluation: BaselineEvaluationMetadata
    hidden_record: InterventionApplicabilityConfig
    flattening: InterventionApplicabilityConfig
    robustness: RobustnessSweepSettings
    verdict_rule_version: str
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_config(self) -> "DiscoveredCaseFalsification":
        if self.falsification_format_version != "discovered-case-falsification.v1":
            raise ValueError(
                "falsification_format_version must equal 'discovered-case-falsification.v1'"
            )
        if not self.falsification_id:
            raise ValueError("falsification_id must be a non-empty string")
        if not self.verdict_rule_version:
            raise ValueError("verdict_rule_version must be a non-empty string")
        ensure_metadata_shape(self.metadata)
        return self


class FalsificationInterventionResult(SixBirdsModel):
    applicability_status: ApplicabilityStatus
    outcome: str | None = None
    reason: str | None = None
    run_id: str | None = None
    summary_artifact: str | None = None
    note_artifact: str | None = None
    result_note_artifact: str | None = None
    manifest_artifact: str | None = None

    @model_validator(mode="after")
    def validate_result(self) -> "FalsificationInterventionResult":
        for name in [
            "summary_artifact",
            "note_artifact",
            "result_note_artifact",
            "manifest_artifact",
        ]:
            value = getattr(self, name)
            if value is not None and not is_repo_relative_path(value):
                raise ValueError(f"{name} must be a normalized repo-relative path")
        if self.applicability_status == "completed" and self.run_id is None:
            raise ValueError(
                "run_id must be present when applicability_status is completed"
            )
        if self.applicability_status == "not_applicable" and self.run_id is not None:
            raise ValueError(
                "run_id must be null when applicability_status is not_applicable"
            )
        if self.outcome is not None and not self.outcome:
            raise ValueError("outcome must be non-empty when present")
        if self.reason is not None and not self.reason:
            raise ValueError("reason must be non-empty when present")
        return self


class RobustnessSubrunResult(SixBirdsModel):
    applicability_status: ApplicabilityStatus
    run_id: str | None = None
    summary_artifact: str | None = None
    note_artifact: str | None = None
    threshold_crossings_artifact: str | None = None
    result_note_artifact: str | None = None
    manifest_artifact: str | None = None
    first_crossings: dict[str, object] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_result(self) -> "RobustnessSubrunResult":
        for name in [
            "summary_artifact",
            "note_artifact",
            "threshold_crossings_artifact",
            "result_note_artifact",
            "manifest_artifact",
        ]:
            value = getattr(self, name)
            if value is not None and not is_repo_relative_path(value):
                raise ValueError(f"{name} must be a normalized repo-relative path")
        if self.applicability_status == "completed" and self.run_id is None:
            raise ValueError(
                "run_id must be present when applicability_status is completed"
            )
        if self.applicability_status == "not_applicable" and self.run_id is not None:
            raise ValueError(
                "run_id must be null when applicability_status is not_applicable"
            )
        if any(not note for note in self.notes):
            raise ValueError("notes must contain only non-empty strings")
        ensure_metadata_shape(self.first_crossings)
        return self


class DiscoveredCaseFalsificationResult(SixBirdsModel):
    result_format_version: str
    falsification_id: str
    selected_case_id: str
    selected_source_refs: dict[str, str]
    provenance_classification: AdmissibilityClassification
    baseline_hard_only: TargetedSearchEvaluation
    baseline_all_accepted_proposals: TargetedSearchEvaluation
    sec_status: AtlasStatus
    sec_mean: float | None = None
    ccd_status: AtlasStatus
    ccd_overall: float | None = None
    rm_status: AtlasStatus
    rm_overall: float | None = None
    hidden_record: FalsificationInterventionResult
    flattening: FalsificationInterventionResult
    robustness: RobustnessSubrunResult
    final_verdict: DiscoveredCaseVerdict
    artifact_refs: dict[str, str]
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_result(self) -> "DiscoveredCaseFalsificationResult":
        if self.result_format_version != "discovered-case-falsification-result.v1":
            raise ValueError(
                "result_format_version must equal 'discovered-case-falsification-result.v1'"
            )
        if not self.falsification_id:
            raise ValueError("falsification_id must be a non-empty string")
        if not self.selected_case_id:
            raise ValueError("selected_case_id must be a non-empty string")
        ensure_repo_relative_mapping(
            self.selected_source_refs,
            field_name="selected_source_refs",
        )
        for status_name, value_name in [
            ("sec_status", "sec_mean"),
            ("ccd_status", "ccd_overall"),
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
        for name in ["sec_mean", "ccd_overall", "rm_overall"]:
            value = getattr(self, name)
            if value is not None and (
                isinstance(value, bool) or not math.isfinite(value) or value < 0
            ):
                raise ValueError(f"{name} must be a finite non-negative value")
        ensure_repo_relative_mapping(self.artifact_refs, field_name="artifact_refs")
        if any(not note for note in self.notes):
            raise ValueError("notes must contain only non-empty strings")
        return self


class FlagshipSourceRefs(SixBirdsModel):
    discovered_context_family_artifact: str
    event_package_artifact: str
    package_provenance_artifact: str
    shared_event_candidates_artifact: str
    quotient_feasibility_summary_artifact: str
    source_pica_bundle_artifact: str | None = None

    @model_validator(mode="after")
    def validate_refs(self) -> "FlagshipSourceRefs":
        mapping = {
            "discovered_context_family_artifact": self.discovered_context_family_artifact,
            "event_package_artifact": self.event_package_artifact,
            "package_provenance_artifact": self.package_provenance_artifact,
            "shared_event_candidates_artifact": self.shared_event_candidates_artifact,
            "quotient_feasibility_summary_artifact": self.quotient_feasibility_summary_artifact,
        }
        if self.source_pica_bundle_artifact is not None:
            if not self.source_pica_bundle_artifact:
                raise ValueError(
                    "source_pica_bundle_artifact must be non-empty when present"
                )
            mapping["source_pica_bundle_artifact"] = self.source_pica_bundle_artifact
        ensure_repo_relative_mapping(mapping, field_name="flagship_source_refs")
        return self


class FlagshipMetricValue(SixBirdsModel):
    status: AtlasStatus
    value: float | None = None
    reason: str | None = None

    @model_validator(mode="after")
    def validate_metric(self) -> "FlagshipMetricValue":
        if self.status == "solved":
            if self.value is None:
                raise ValueError("value must be present when status is solved")
        elif self.value is not None:
            raise ValueError("value must be null unless status is solved")
        if self.value is not None and (
            isinstance(self.value, bool)
            or not math.isfinite(self.value)
            or self.value < 0
        ):
            raise ValueError("value must be a finite non-negative number when present")
        if self.reason is not None and not self.reason:
            raise ValueError("reason must be non-empty when present")
        return self


class FlagshipMetricOverrides(SixBirdsModel):
    gpd_str: FlagshipMetricValue | None = None
    gpd_stat: FlagshipMetricValue | None = None


class FlagshipRobustnessConfig(SixBirdsModel):
    applicable: bool = False
    noise_grid: list[float] = Field(default_factory=list)
    noise_model: NoiseModelConfig | None = None
    metric_thresholds: NoiseMetricThresholds | None = None
    trace_families: list[Literal["stat", "ccd", "sec", "rm"]] = Field(
        default_factory=lambda: ["stat", "sec"]
    )
    reason: str | None = None

    @model_validator(mode="after")
    def validate_config(self) -> "FlagshipRobustnessConfig":
        if self.applicable:
            if not self.noise_grid:
                raise ValueError("noise_grid must not be empty when applicable is true")
            for noise_level in self.noise_grid:
                if (
                    isinstance(noise_level, bool)
                    or not math.isfinite(noise_level)
                    or noise_level < 0
                    or noise_level > 1
                ):
                    raise ValueError(
                        "noise_grid values must be finite values in [0, 1]"
                    )
            if self.noise_model is None:
                raise ValueError("noise_model must be present when applicable is true")
            if self.metric_thresholds is None:
                raise ValueError(
                    "metric_thresholds must be present when applicable is true"
                )
        else:
            if self.noise_grid:
                raise ValueError("noise_grid must be empty when applicable is false")
            if self.noise_model is not None or self.metric_thresholds is not None:
                raise ValueError(
                    "noise_model and metric_thresholds must be null when applicable is false"
                )
        if not self.trace_families:
            raise ValueError("trace_families must not be empty")
        duplicates = set()
        seen: set[str] = set()
        for trace_family in self.trace_families:
            if trace_family in seen:
                duplicates.add(trace_family)
            seen.add(trace_family)
        if duplicates:
            raise ValueError(
                f"trace_families must be unique: {', '.join(sorted(duplicates))}"
            )
        if self.reason is not None and not self.reason:
            raise ValueError("reason must be non-empty when present")
        return self


class FlagshipControlCaseConfig(SixBirdsModel):
    case_id: str
    case_type: FlagshipCaseType
    source_refs: FlagshipSourceRefs
    hidden_record: InterventionApplicabilityConfig = Field(
        default_factory=InterventionApplicabilityConfig
    )
    flattening: InterventionApplicabilityConfig = Field(
        default_factory=InterventionApplicabilityConfig
    )
    robustness: FlagshipRobustnessConfig = Field(
        default_factory=FlagshipRobustnessConfig
    )
    baseline_metric_overrides: FlagshipMetricOverrides | None = None
    notes: list[str] = Field(default_factory=list)
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_case(self) -> "FlagshipControlCaseConfig":
        if not self.case_id:
            raise ValueError("case_id must be a non-empty string")
        if (
            self.robustness.applicable
            and self.source_refs.source_pica_bundle_artifact is None
        ):
            raise ValueError(
                "source_pica_bundle_artifact must be present when robustness is applicable"
            )
        if any(not note for note in self.notes):
            raise ValueError("notes must contain only non-empty strings")
        ensure_metadata_shape(self.metadata)
        return self


class FlagshipControlBundle(SixBirdsModel):
    bundle_format_version: str
    bundle_id: str
    flagship_cases: list[FlagshipControlCaseConfig]
    verdict_rule_version: str
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_bundle(self) -> "FlagshipControlBundle":
        if self.bundle_format_version != "flagship-control-bundle.v1":
            raise ValueError(
                "bundle_format_version must equal 'flagship-control-bundle.v1'"
            )
        if not self.bundle_id:
            raise ValueError("bundle_id must be a non-empty string")
        if not self.flagship_cases:
            raise ValueError("flagship_cases must not be empty")
        duplicates = {
            case_id
            for case_id in [case.case_id for case in self.flagship_cases]
            if [case.case_id for case in self.flagship_cases].count(case_id) > 1
        }
        if duplicates:
            raise ValueError(
                f"case_id values must be unique: {', '.join(sorted(duplicates))}"
            )
        if not self.verdict_rule_version:
            raise ValueError("verdict_rule_version must be a non-empty string")
        ensure_metadata_shape(self.metadata)
        return self


class FlagshipMetricSnapshot(SixBirdsModel):
    witness_classification: str
    exact_feasible: bool | None = None
    survivor_count: int | None = None
    failure_reason: str | None = None
    quotient_class_count: int | None = None
    uncovered_atom_count: int | None = None
    gpd_str: FlagshipMetricValue
    gpd_stat: FlagshipMetricValue

    @model_validator(mode="after")
    def validate_snapshot(self) -> "FlagshipMetricSnapshot":
        if not self.witness_classification:
            raise ValueError("witness_classification must be a non-empty string")
        for name in ["survivor_count", "quotient_class_count", "uncovered_atom_count"]:
            value = getattr(self, name)
            if value is not None and (isinstance(value, bool) or value < 0):
                raise ValueError(f"{name} must be a non-negative integer when present")
        if self.failure_reason is not None and not self.failure_reason:
            raise ValueError("failure_reason must be non-empty when present")
        return self


class FlagshipControlSummary(SixBirdsModel):
    applicability_status: ApplicabilityStatus
    verdict: FlagshipControlVerdict
    reason: str | None = None
    pre_control: FlagshipMetricSnapshot
    post_control: FlagshipMetricSnapshot | None = None
    run_id: str | None = None
    artifact_refs: dict[str, str] = Field(default_factory=dict)
    first_crossings: dict[str, object] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_summary(self) -> "FlagshipControlSummary":
        if self.applicability_status == "completed":
            if self.post_control is None:
                raise ValueError(
                    "post_control must be present when applicability_status is completed"
                )
            if self.run_id is None and self.verdict != "inconclusive":
                raise ValueError(
                    "run_id must be present for completed controls unless verdict is inconclusive"
                )
        else:
            if self.post_control is not None or self.run_id is not None:
                raise ValueError(
                    "post_control and run_id must be null when applicability_status is not_applicable"
                )
            if self.verdict != "not_applicable":
                raise ValueError(
                    "verdict must equal not_applicable when applicability_status is not_applicable"
                )
        if self.reason is not None and not self.reason:
            raise ValueError("reason must be non-empty when present")
        ensure_repo_relative_mapping(self.artifact_refs, field_name="artifact_refs")
        if any(not isinstance(key, str) or not key for key in self.first_crossings):
            raise ValueError("first_crossings must contain only non-empty string keys")
        if any(not note for note in self.notes):
            raise ValueError("notes must contain only non-empty strings")
        return self


class FlagshipControlCaseResult(SixBirdsModel):
    case_id: str
    case_type: FlagshipCaseType
    source_refs: FlagshipSourceRefs
    hidden_record: FlagshipControlSummary
    flattening: FlagshipControlSummary
    robustness: FlagshipControlSummary
    final_verdict: FlagshipControlVerdict
    artifact_refs: dict[str, str] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_case(self) -> "FlagshipControlCaseResult":
        if not self.case_id:
            raise ValueError("case_id must be a non-empty string")
        ensure_repo_relative_mapping(self.artifact_refs, field_name="artifact_refs")
        if any(not note for note in self.notes):
            raise ValueError("notes must contain only non-empty strings")
        return self


class FlagshipControlResult(SixBirdsModel):
    result_format_version: str
    bundle_id: str
    cases: list[FlagshipControlCaseResult]
    overall_bundle_verdict: FlagshipOverallVerdict
    artifact_refs: dict[str, str]
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_result(self) -> "FlagshipControlResult":
        if self.result_format_version != "flagship-control-result.v1":
            raise ValueError(
                "result_format_version must equal 'flagship-control-result.v1'"
            )
        if not self.bundle_id:
            raise ValueError("bundle_id must be a non-empty string")
        if not self.cases:
            raise ValueError("cases must not be empty")
        duplicates = {
            case_id
            for case_id in [case.case_id for case in self.cases]
            if [case.case_id for case in self.cases].count(case_id) > 1
        }
        if duplicates:
            raise ValueError(
                f"case_id values must be unique: {', '.join(sorted(duplicates))}"
            )
        ensure_repo_relative_mapping(self.artifact_refs, field_name="artifact_refs")
        if any(not note for note in self.notes):
            raise ValueError("notes must contain only non-empty strings")
        return self
