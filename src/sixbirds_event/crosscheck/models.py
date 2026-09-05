from __future__ import annotations

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


CrosscheckTargetType = Literal["benchmark", "discovered_candidate"]
EvaluationMode = Literal["hard_only", "all_proposals"]
CrosscheckStatus = Literal["solved", "unsolved", "not_applicable"]
FeasibilityStatus = Literal["feasible", "infeasible"]


class BlockingAnalysisSettings(SixBirdsModel):
    single_proposal_leave_one_out: bool = True


class ExactCrosscheckTarget(SixBirdsModel):
    target_id: str
    target_type: CrosscheckTargetType
    package_artifact: str | None = None
    evaluation_mode: EvaluationMode
    applicability_override_status: Literal["not_applicable"] | None = None
    applicability_reason: str | None = None
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_target(self) -> "ExactCrosscheckTarget":
        if not self.target_id:
            raise ValueError("target_id must be a non-empty string")
        if self.applicability_override_status == "not_applicable":
            if self.applicability_reason is None:
                raise ValueError(
                    "applicability_reason must be provided when applicability_override_status is not_applicable"
                )
            if self.package_artifact is not None and not is_repo_relative_path(
                self.package_artifact
            ):
                raise ValueError(
                    "package_artifact must be a normalized repo-relative path when present"
                )
        else:
            if self.package_artifact is None:
                raise ValueError(
                    "package_artifact must be provided when the target is applicable"
                )
            ensure_repo_relative_mapping(
                {"package_artifact": self.package_artifact},
                field_name="package_artifact",
            )
        if self.applicability_reason is not None and not self.applicability_reason:
            raise ValueError("applicability_reason must be non-empty when present")
        if any(not note for note in self.notes):
            raise ValueError("notes must contain only non-empty strings")
        return self


class ExactCrosscheck(SixBirdsModel):
    crosscheck_format_version: str
    crosscheck_id: str
    targets: list[ExactCrosscheckTarget]
    backend_label: str
    blocking_analysis: BlockingAnalysisSettings
    output_category: str | None = None
    output_label: str | None = None
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_config(self) -> "ExactCrosscheck":
        if self.crosscheck_format_version != "exact-crosscheck.v1":
            raise ValueError(
                "crosscheck_format_version must equal 'exact-crosscheck.v1'"
            )
        if not self.crosscheck_id:
            raise ValueError("crosscheck_id must be a non-empty string")
        if not self.targets:
            raise ValueError("targets must not be empty")
        duplicates = collect_list_duplicates(
            [target.target_id for target in self.targets]
        )
        if duplicates:
            raise ValueError(
                f"target_id values must be unique: {', '.join(duplicates)}"
            )
        if not self.backend_label:
            raise ValueError("backend_label must be a non-empty string")
        if self.output_category is not None and not self.output_category:
            raise ValueError("output_category must be non-empty when present")
        if self.output_label is not None and not self.output_label:
            raise ValueError("output_label must be non-empty when present")
        ensure_metadata_shape(self.metadata)
        return self


class SingleProposalBlockingResult(SixBirdsModel):
    proposal_id: str
    feasibility_status: Literal["feasible", "infeasible", "unsolved"]
    exact_respecting_tuple_count: int | None = None
    exact_selected_tuple_count: int | None = None
    reason: str | None = None

    @model_validator(mode="after")
    def validate_result(self) -> "SingleProposalBlockingResult":
        if not self.proposal_id:
            raise ValueError("proposal_id must be a non-empty string")
        for name in ["exact_respecting_tuple_count", "exact_selected_tuple_count"]:
            value = getattr(self, name)
            if value is not None and (isinstance(value, bool) or value < 0):
                raise ValueError(f"{name} must be a non-negative integer when present")
        if self.reason is not None and not self.reason:
            raise ValueError("reason must be non-empty when present")
        return self


class BlockingProxyResult(SixBirdsModel):
    status: CrosscheckStatus
    blocking_proposal_ids: list[str] = Field(default_factory=list)
    single_proposal_results: list[SingleProposalBlockingResult] = Field(
        default_factory=list
    )
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_result(self) -> "BlockingProxyResult":
        duplicates = collect_list_duplicates(self.blocking_proposal_ids)
        if duplicates:
            raise ValueError(
                f"blocking_proposal_ids must be unique: {', '.join(duplicates)}"
            )
        duplicates = collect_list_duplicates(
            [row.proposal_id for row in self.single_proposal_results]
        )
        if duplicates:
            raise ValueError(
                "single_proposal_results must be unique by proposal_id: "
                + ", ".join(duplicates)
            )
        if any(not note for note in self.notes):
            raise ValueError("notes must contain only non-empty strings")
        return self


class ExactCrosscheckRow(SixBirdsModel):
    row_format_version: str
    crosscheck_id: str
    target_id: str
    target_type: CrosscheckTargetType
    package_path: str | None = None
    evaluation_mode: EvaluationMode
    backend_label: str
    crosscheck_status: CrosscheckStatus
    feasibility_status: FeasibilityStatus | None = None
    exact_respecting_tuple_count: int | None = None
    exact_selected_tuple_count: int | None = None
    model_artifact_path: str | None = None
    summary_artifact_path: str | None = None
    note_artifact_path: str | None = None
    solution_artifact_path: str | None = None
    blocking_proxy: BlockingProxyResult
    applicability_reason: str | None = None
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_row(self) -> "ExactCrosscheckRow":
        if self.row_format_version != "exact-crosscheck-row.v1":
            raise ValueError("row_format_version must equal 'exact-crosscheck-row.v1'")
        if not self.crosscheck_id:
            raise ValueError("crosscheck_id must be a non-empty string")
        if not self.target_id:
            raise ValueError("target_id must be a non-empty string")
        if not self.backend_label:
            raise ValueError("backend_label must be a non-empty string")
        if self.package_path is not None and not is_repo_relative_path(
            self.package_path
        ):
            raise ValueError("package_path must be a normalized repo-relative path")
        for name in [
            "model_artifact_path",
            "summary_artifact_path",
            "note_artifact_path",
            "solution_artifact_path",
        ]:
            value = getattr(self, name)
            if value is not None and not is_repo_relative_path(value):
                raise ValueError(f"{name} must be a normalized repo-relative path")
        if self.crosscheck_status == "solved":
            if self.feasibility_status is None:
                raise ValueError(
                    "feasibility_status must be present when crosscheck_status is solved"
                )
            if self.package_path is None:
                raise ValueError(
                    "package_path must be present when crosscheck_status is solved"
                )
            for name in [
                "model_artifact_path",
                "summary_artifact_path",
                "note_artifact_path",
            ]:
                if getattr(self, name) is None:
                    raise ValueError(
                        f"{name} must be present when crosscheck_status is solved"
                    )
        else:
            if self.feasibility_status is not None:
                raise ValueError(
                    "feasibility_status must be null unless crosscheck_status is solved"
                )
            if self.solution_artifact_path is not None:
                raise ValueError(
                    "solution_artifact_path must be null unless crosscheck_status is solved"
                )
        for name in ["exact_respecting_tuple_count", "exact_selected_tuple_count"]:
            value = getattr(self, name)
            if value is not None and (isinstance(value, bool) or value < 0):
                raise ValueError(f"{name} must be a non-negative integer when present")
        if self.applicability_reason is not None and not self.applicability_reason:
            raise ValueError("applicability_reason must be non-empty when present")
        if any(not note for note in self.notes):
            raise ValueError("notes must contain only non-empty strings")
        return self


class ExactCrosscheckResults(SixBirdsModel):
    result_format_version: str
    crosscheck_id: str
    row_count: int
    rows: list[ExactCrosscheckRow]
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_results(self) -> "ExactCrosscheckResults":
        if self.result_format_version != "exact-crosscheck-result.v1":
            raise ValueError(
                "result_format_version must equal 'exact-crosscheck-result.v1'"
            )
        if not self.crosscheck_id:
            raise ValueError("crosscheck_id must be a non-empty string")
        if self.row_count != len(self.rows):
            raise ValueError("row_count must equal len(rows)")
        duplicates = collect_list_duplicates([row.target_id for row in self.rows])
        if duplicates:
            raise ValueError(
                f"rows must be unique by target_id: {', '.join(duplicates)}"
            )
        if any(row.crosscheck_id != self.crosscheck_id for row in self.rows):
            raise ValueError("all rows must share the table crosscheck_id")
        ensure_metadata_shape(self.metadata)
        return self
