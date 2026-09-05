from __future__ import annotations

import math
from typing import Literal

from pydantic import Field, model_validator

from ..schemas.common import (
    MetadataValue,
    MetricValue,
    SixBirdsModel,
    collect_list_duplicates,
    ensure_metadata_shape,
    ensure_metric_shape,
    ensure_repo_relative_mapping,
    is_repo_relative_path,
)


FrameworkResponse = Literal[
    "flagged",
    "corrected",
    "partially_flagged",
    "partially_corrected",
    "not_flagged",
]
AdversarialType = Literal[
    "hidden_label_smuggling",
    "schedule_protocol_residue_artifact",
    "flattenable_route_mismatch",
    "bad_shared_event_proposals",
]
RunnerMode = Literal[
    "structural_only",
    "hidden_record_intervention",
    "flattening_intervention",
    "sec_audit",
]
MetricStatus = Literal[
    "solved",
    "unsolved",
    "scored",
    "insufficient_data",
    "not_applicable",
]
StructuralStatus = Literal["feasible", "infeasible", "not_applicable"]


class RedteamCaseConfig(SixBirdsModel):
    case_id: str
    adversarial_type: AdversarialType
    runner_mode: RunnerMode
    asset_refs: dict[str, str]
    expected_issue_type: str
    expected_framework_response: FrameworkResponse | None = None
    classification_thresholds: dict[str, MetricValue] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_case(self) -> "RedteamCaseConfig":
        if not self.case_id:
            raise ValueError("case_id must be a non-empty string")
        ensure_repo_relative_mapping(self.asset_refs, field_name="asset_refs")
        if not self.expected_issue_type:
            raise ValueError("expected_issue_type must be a non-empty string")
        ensure_metric_shape(self.classification_thresholds)
        if any(not note for note in self.notes):
            raise ValueError("notes must contain only non-empty strings")

        required_assets = {
            "structural_only": {"instance"},
            "hidden_record_intervention": {"intervention"},
            "flattening_intervention": {"intervention"},
            "sec_audit": {"instance", "trace"},
        }[self.runner_mode]
        missing_assets = sorted(required_assets - set(self.asset_refs))
        if missing_assets:
            raise ValueError(
                f"runner_mode '{self.runner_mode}' requires asset_refs for: {', '.join(missing_assets)}"
            )
        return self


class RedteamSuite(SixBirdsModel):
    suite_format_version: str
    suite_id: str
    cases: list[RedteamCaseConfig]
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_suite(self) -> "RedteamSuite":
        if self.suite_format_version != "redteam-suite.v1":
            raise ValueError("suite_format_version must equal 'redteam-suite.v1'")
        if not self.suite_id:
            raise ValueError("suite_id must be a non-empty string")
        if len(self.cases) < 3:
            raise ValueError("cases must contain at least three entries")
        duplicates = collect_list_duplicates([case.case_id for case in self.cases])
        if duplicates:
            raise ValueError(f"case_id values must be unique: {', '.join(duplicates)}")
        ensure_metadata_shape(self.metadata)
        return self


class RedteamCaseResult(SixBirdsModel):
    row_format_version: str
    suite_id: str
    case_id: str
    adversarial_type: AdversarialType
    input_asset_refs: dict[str, str]
    attempted_metrics: list[str]
    exact_structural_status: StructuralStatus
    exact_structural_feasible_hard_only: bool | None = None
    gpd_str: float | None = None
    gpd_stat_status: MetricStatus
    gpd_stat: float | None = None
    gpd_stat_reason: str | None = None
    ccd_status: MetricStatus
    ccd_overall: float | None = None
    sec_status: MetricStatus
    sec_mean: float | None = None
    rm_status: MetricStatus
    rm_overall: float | None = None
    intervention_conclusion: str | None = None
    framework_response: FrameworkResponse
    explanatory_flags: list[str] = Field(default_factory=list)
    run_ids: dict[str, str]
    artifact_paths: dict[str, str]
    note_path: str

    @model_validator(mode="after")
    def validate_result(self) -> "RedteamCaseResult":
        if self.row_format_version != "redteam-case-result.v1":
            raise ValueError("row_format_version must equal 'redteam-case-result.v1'")
        for name in ["suite_id", "case_id", "note_path"]:
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise ValueError(f"{name} must be a non-empty string")
        ensure_repo_relative_mapping(
            self.input_asset_refs, field_name="input_asset_refs"
        )
        ensure_repo_relative_mapping(self.artifact_paths, field_name="artifact_paths")
        if not is_repo_relative_path(self.note_path):
            raise ValueError("note_path must be a normalized repo-relative path")
        if not self.attempted_metrics:
            raise ValueError("attempted_metrics must not be empty")
        if any(not metric for metric in self.attempted_metrics):
            raise ValueError("attempted_metrics must contain only non-empty strings")
        if self.exact_structural_status == "not_applicable":
            if self.exact_structural_feasible_hard_only is not None:
                raise ValueError(
                    "exact_structural_feasible_hard_only must be null when exact_structural_status is not_applicable"
                )
            if self.gpd_str is not None:
                raise ValueError(
                    "gpd_str must be null when exact_structural_status is not_applicable"
                )
        for status_name, value_name in [
            ("gpd_stat_status", "gpd_stat"),
            ("ccd_status", "ccd_overall"),
            ("sec_status", "sec_mean"),
            ("rm_status", "rm_overall"),
        ]:
            status = getattr(self, status_name)
            value = getattr(self, value_name)
            if status in {"solved", "scored"}:
                if value is None:
                    raise ValueError(
                        f"{value_name} must be present when {status_name} is {status}"
                    )
            elif value is not None:
                raise ValueError(
                    f"{value_name} must be null unless {status_name} is solved/scored"
                )
        for name in ["gpd_str", "gpd_stat", "ccd_overall", "sec_mean", "rm_overall"]:
            value = getattr(self, name)
            if value is not None and (
                isinstance(value, bool) or not math.isfinite(value) or value < 0
            ):
                raise ValueError(f"{name} must be a finite non-negative value")
        if (
            self.intervention_conclusion is not None
            and not self.intervention_conclusion
        ):
            raise ValueError("intervention_conclusion must be non-empty when present")
        if not self.run_ids:
            raise ValueError("run_ids must not be empty")
        for key, value in self.run_ids.items():
            if not isinstance(key, str) or not key:
                raise ValueError("run_ids keys must be non-empty strings")
            if not isinstance(value, str) or not value:
                raise ValueError("run_ids values must be non-empty strings")
        if any(not flag for flag in self.explanatory_flags):
            raise ValueError("explanatory_flags must contain only non-empty strings")
        return self


class RedteamResultsTable(SixBirdsModel):
    table_format_version: str
    suite_id: str
    row_count: int
    rows: list[RedteamCaseResult]
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_table(self) -> "RedteamResultsTable":
        if self.table_format_version != "redteam-results.v1":
            raise ValueError("table_format_version must equal 'redteam-results.v1'")
        if not self.suite_id:
            raise ValueError("suite_id must be a non-empty string")
        if self.row_count != len(self.rows):
            raise ValueError("row_count must equal len(rows)")
        duplicates = collect_list_duplicates([row.case_id for row in self.rows])
        if duplicates:
            raise ValueError(
                f"results rows must be unique by case_id: {', '.join(duplicates)}"
            )
        if any(row.suite_id != self.suite_id for row in self.rows):
            raise ValueError("all case results must share the table suite_id")
        ensure_metadata_shape(self.metadata)
        return self
