from __future__ import annotations

import math
from typing import Literal

from pydantic import Field, model_validator

from ..discovery.models import (
    DiscoveredEventGenerationThresholds,
    ExtractionThresholds,
    PicaObservableProjection,
    SharedEventInferenceThresholds,
)
from ..provenance.models import AdmissibilityClassification
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


AtlasStatus = Literal[
    "solved", "unsolved", "scored", "insufficient_data", "not_applicable"
]
StructuralStatus = Literal["feasible", "infeasible", "not_applicable"]
RegimeLabel = Literal[
    "globally_packageable",
    "multi_context_but_extendable",
    "weakly_frustrated",
    "strongly_nonextendable",
    "trivial_or_nonrecording",
]
TargetedCandidateLabel = Literal[
    "strongly_nonextendable_candidate",
    "weakly_frustrated_candidate",
    "extendable_candidate",
    "trivial_or_nonrecording",
    "inconclusive",
]
ContextRelationType = Literal[
    "equal",
    "left_refines_right",
    "right_refines_left",
    "incomparable",
    "disjoint_or_unaligned",
]
ProjectionFamilyKind = Literal[
    "packaging_outcome",
    "derived_row_outcome",
    "closure_summary",
    "route_summary",
]
ProjectionFamilyRole = Literal[
    "primary_context",
    "probe_only",
    "diagnostic_only",
]
PackagingConflictAdmissibilityClass = Literal[
    "primary_packaging_conflict",
    "probe_only",
    "diagnostic_only",
]
CommutatorAdmissibilityMode = Literal["p5_only", "p5_p6_combined"]
MechanismAxisClaimLevel = Literal[
    "mechanism_dependence",
    "nontrivial_multicontext_structure",
    "package_conflict_tension",
]
MechanismSignalKind = Literal[
    "packaging_surface_change_only",
    "package_structure_richer",
    "weak_frustration",
    "strong_mechanism_side_tension",
    "control_like",
    "inconclusive",
]
MechanismAxisQuotientWitnessClassification = Literal[
    "accepted_proposal_obstruction",
    "candidate_subset_quotient_witness",
    "no_quotient_obstruction",
]
LensAxisClaimLevel = Literal[
    "nontrivial_multicontext_structure",
    "same_slice_non_nested_structure",
    "package_conflict_tension",
    "provenance_admissible_strong_obstruction",
]
LensAxisQuotientWitnessStatus = Literal[
    "accepted_proposal_obstruction",
    "candidate_subset_quotient_witness",
    "no_quotient_obstruction",
]
PackagingFamilyRole = Literal[
    "primary_context_pair",
    "probe_only",
    "diagnostic_only",
]
PackagingAxisClaimLevel = Literal[
    "nontrivial_multicontext_structure",
    "same_support_packaging_change",
    "packaging_conflict_tension",
    "provenance_admissible_packaging_obstruction",
]
PackagingAxisQuotientWitnessStatus = Literal[
    "accepted_proposal_obstruction",
    "candidate_subset_quotient_witness",
    "no_quotient_obstruction",
]


class SearchSweepPoint(SixBirdsModel):
    point_id: str
    config_artifact: str
    preparation_id: str
    protocol_id: str
    trajectories: int
    seed: int
    parameter_overrides: dict[str, MetricValue] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_point(self) -> "SearchSweepPoint":
        if not self.point_id:
            raise ValueError("point_id must be a non-empty string")
        ensure_repo_relative_mapping(
            {"config_artifact": self.config_artifact},
            field_name="config_artifact",
        )
        if not self.preparation_id:
            raise ValueError("preparation_id must be a non-empty string")
        if not self.protocol_id:
            raise ValueError("protocol_id must be a non-empty string")
        if isinstance(self.trajectories, bool) or self.trajectories <= 0:
            raise ValueError("trajectories must be a positive integer")
        if isinstance(self.seed, bool):
            raise ValueError("seed must be an integer")
        ensure_metric_shape(self.parameter_overrides)
        if any(not note for note in self.notes):
            raise ValueError("notes must contain only non-empty strings")
        return self


class ClassificationThresholds(SixBirdsModel):
    near_zero_gpd_stat: float = 1e-6
    strong_nonextendable_min_gpd_str: float = 1.0

    @model_validator(mode="after")
    def validate_thresholds(self) -> "ClassificationThresholds":
        for name, value in {
            "near_zero_gpd_stat": self.near_zero_gpd_stat,
            "strong_nonextendable_min_gpd_str": self.strong_nonextendable_min_gpd_str,
        }.items():
            if isinstance(value, bool) or not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be a finite non-negative value")
        return self


class SearchSweep(SixBirdsModel):
    sweep_format_version: str
    sweep_id: str
    points: list[SearchSweepPoint]
    extraction_thresholds: ExtractionThresholds
    shared_event_inference_thresholds: SharedEventInferenceThresholds
    classification_thresholds: ClassificationThresholds
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_sweep(self) -> "SearchSweep":
        if self.sweep_format_version != "search-sweep.v1":
            raise ValueError("sweep_format_version must equal 'search-sweep.v1'")
        if not self.sweep_id:
            raise ValueError("sweep_id must be a non-empty string")
        if not self.points:
            raise ValueError("points must not be empty")
        duplicates = collect_list_duplicates([point.point_id for point in self.points])
        if duplicates:
            raise ValueError(f"point_id values must be unique: {', '.join(duplicates)}")
        ensure_metadata_shape(self.metadata)
        return self


class SearchAtlasRow(SixBirdsModel):
    row_format_version: str
    sweep_id: str
    point_id: str
    config_path: str
    preparation_id: str
    protocol_id: str
    trajectories: int
    seed: int
    raw_run_path: str
    discovered_context_family_path: str
    event_package_path: str | None = None
    accepted_context_count: int
    accepted_shared_event_proposal_count: int
    exact_structural_status: StructuralStatus
    exact_structural_feasible_hard_only: bool | None = None
    exact_respecting_tuple_count: int | None = None
    gpd_str: float | None = None
    gpd_stat_status: AtlasStatus
    gpd_stat: float | None = None
    gpd_stat_reason: str | None = None
    ccd_status: AtlasStatus
    ccd_overall: float | None = None
    sec_status: AtlasStatus
    sec_mean: float | None = None
    rm_status: AtlasStatus
    rm_overall: float | None = None
    regime_classification: RegimeLabel
    run_ids: dict[str, str]
    artifact_paths: dict[str, str]
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_row(self) -> "SearchAtlasRow":
        if self.row_format_version != "search-atlas-row.v1":
            raise ValueError("row_format_version must equal 'search-atlas-row.v1'")
        for name in [
            "sweep_id",
            "point_id",
            "config_path",
            "preparation_id",
            "protocol_id",
            "raw_run_path",
            "discovered_context_family_path",
        ]:
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise ValueError(f"{name} must be a non-empty string")
        ensure_repo_relative_mapping(
            {
                "config_path": self.config_path,
                "raw_run_path": self.raw_run_path,
                "discovered_context_family_path": self.discovered_context_family_path,
            },
            field_name="row_artifacts",
        )
        if self.event_package_path is not None and not is_repo_relative_path(
            self.event_package_path
        ):
            raise ValueError(
                "event_package_path must be a normalized repo-relative path when present"
            )
        if isinstance(self.trajectories, bool) or self.trajectories <= 0:
            raise ValueError("trajectories must be a positive integer")
        if isinstance(self.seed, bool):
            raise ValueError("seed must be an integer")
        for name in [
            "accepted_context_count",
            "accepted_shared_event_proposal_count",
        ]:
            value = getattr(self, name)
            if isinstance(value, bool) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if self.exact_structural_status == "not_applicable":
            if self.exact_structural_feasible_hard_only is not None:
                raise ValueError(
                    "exact_structural_feasible_hard_only must be null when structural status is not_applicable"
                )
        if self.gpd_stat_status == "solved" and self.gpd_stat is None:
            raise ValueError("gpd_stat must be present when gpd_stat_status is solved")
        if self.gpd_stat_status != "solved" and self.gpd_stat is not None:
            raise ValueError("gpd_stat must be null unless gpd_stat_status is solved")
        for status_name, value_name in [
            ("ccd_status", "ccd_overall"),
            ("sec_status", "sec_mean"),
            ("rm_status", "rm_overall"),
        ]:
            status = getattr(self, status_name)
            value = getattr(self, value_name)
            if status in {"scored", "solved"}:
                if value is None:
                    raise ValueError(
                        f"{value_name} must be present when {status_name} is {status}"
                    )
            elif value is not None:
                raise ValueError(
                    f"{value_name} must be null unless {status_name} is scored"
                )
        for name in ["gpd_str", "gpd_stat", "ccd_overall", "sec_mean", "rm_overall"]:
            value = getattr(self, name)
            if value is not None and (
                isinstance(value, bool) or not math.isfinite(value) or value < 0
            ):
                raise ValueError(f"{name} must be a finite non-negative value")
        if not self.run_ids:
            raise ValueError("run_ids must not be empty")
        if not self.artifact_paths:
            raise ValueError("artifact_paths must not be empty")
        for key, value in self.run_ids.items():
            if not isinstance(key, str) or not key:
                raise ValueError("run_ids keys must be non-empty strings")
            if not isinstance(value, str) or not value:
                raise ValueError("run_ids values must be non-empty strings")
        ensure_repo_relative_mapping(self.artifact_paths, field_name="artifact_paths")
        if any(not note for note in self.notes):
            raise ValueError("notes must contain only non-empty strings")
        return self


class SearchAtlas(SixBirdsModel):
    atlas_format_version: str
    sweep_id: str
    row_count: int
    rows: list[SearchAtlasRow]
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_atlas(self) -> "SearchAtlas":
        if self.atlas_format_version != "search-atlas.v1":
            raise ValueError("atlas_format_version must equal 'search-atlas.v1'")
        if not self.sweep_id:
            raise ValueError("sweep_id must be a non-empty string")
        if self.row_count != len(self.rows):
            raise ValueError("row_count must equal len(rows)")
        duplicates = collect_list_duplicates([row.point_id for row in self.rows])
        if duplicates:
            raise ValueError(
                f"atlas rows must be unique by point_id: {', '.join(duplicates)}"
            )
        if any(row.sweep_id != self.sweep_id for row in self.rows):
            raise ValueError("all atlas rows must share the atlas sweep_id")
        ensure_metadata_shape(self.metadata)
        return self


class TargetedSearchPoint(SixBirdsModel):
    point_id: str
    config_artifact: str
    preparation_id: str
    protocol_id: str
    trajectories: int
    seed: int
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_point(self) -> "TargetedSearchPoint":
        if not self.point_id:
            raise ValueError("point_id must be a non-empty string")
        ensure_repo_relative_mapping(
            {"config_artifact": self.config_artifact},
            field_name="config_artifact",
        )
        if not self.preparation_id:
            raise ValueError("preparation_id must be a non-empty string")
        if not self.protocol_id:
            raise ValueError("protocol_id must be a non-empty string")
        if isinstance(self.trajectories, bool) or self.trajectories <= 0:
            raise ValueError("trajectories must be a positive integer")
        if isinstance(self.seed, bool):
            raise ValueError("seed must be an integer")
        if any(not note for note in self.notes):
            raise ValueError("notes must contain only non-empty strings")
        return self


class TargetedCandidateClassificationThresholds(SixBirdsModel):
    strong_nonextendable_min_gpd_str: float = 1.0
    near_zero_gpd_stat: float = 1e-6
    min_accepted_coarse_proposal_count: int = 1

    @model_validator(mode="after")
    def validate_thresholds(self) -> "TargetedCandidateClassificationThresholds":
        if (
            isinstance(self.strong_nonextendable_min_gpd_str, bool)
            or not math.isfinite(self.strong_nonextendable_min_gpd_str)
            or self.strong_nonextendable_min_gpd_str < 0
        ):
            raise ValueError(
                "strong_nonextendable_min_gpd_str must be a finite non-negative value"
            )
        if (
            isinstance(self.near_zero_gpd_stat, bool)
            or not math.isfinite(self.near_zero_gpd_stat)
            or self.near_zero_gpd_stat < 0
        ):
            raise ValueError("near_zero_gpd_stat must be a finite non-negative value")
        if (
            isinstance(self.min_accepted_coarse_proposal_count, bool)
            or self.min_accepted_coarse_proposal_count < 0
        ):
            raise ValueError(
                "min_accepted_coarse_proposal_count must be a non-negative integer"
            )
        return self


class TargetedSearchStopRule(SixBirdsModel):
    stop_after_family_exhausted: bool = True
    select_best_by: str = "highest_candidate_mode_gpd_str_then_lowest_all_proposals_respecting_tuple_count_then_point_id"
    emit_negative_result_if_none: bool = True

    @model_validator(mode="after")
    def validate_rule(self) -> "TargetedSearchStopRule":
        if not self.select_best_by:
            raise ValueError("select_best_by must be a non-empty string")
        return self


class TargetedNonextendabilitySearch(SixBirdsModel):
    search_format_version: str
    search_id: str
    points: list[TargetedSearchPoint]
    extraction_thresholds: ExtractionThresholds
    coarse_event_generation_thresholds: DiscoveredEventGenerationThresholds
    shared_event_inference_thresholds: SharedEventInferenceThresholds
    provenance_required: bool = True
    candidate_classification_thresholds: TargetedCandidateClassificationThresholds
    stop_rule: TargetedSearchStopRule
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_search(self) -> "TargetedNonextendabilitySearch":
        if self.search_format_version != "targeted-nonextendability-search.v1":
            raise ValueError(
                "search_format_version must equal 'targeted-nonextendability-search.v1'"
            )
        if not self.search_id:
            raise ValueError("search_id must be a non-empty string")
        if not self.points:
            raise ValueError("points must not be empty")
        duplicates = collect_list_duplicates([point.point_id for point in self.points])
        if duplicates:
            raise ValueError(f"point_id values must be unique: {', '.join(duplicates)}")
        ensure_metadata_shape(self.metadata)
        return self


class TargetedSearchEvaluation(SixBirdsModel):
    exact_structural_status: StructuralStatus
    exact_feasible: bool | None = None
    exact_respecting_tuple_count: int | None = None
    exact_failure_reason: str | None = None
    gpd_str_status: AtlasStatus
    gpd_str: float | None = None
    gpd_str_reason: str | None = None
    gpd_stat_status: AtlasStatus
    gpd_stat: float | None = None
    gpd_stat_reason: str | None = None

    @model_validator(mode="after")
    def validate_evaluation(self) -> "TargetedSearchEvaluation":
        if self.exact_structural_status == "not_applicable":
            if (
                self.exact_feasible is not None
                or self.exact_respecting_tuple_count is not None
            ):
                raise ValueError(
                    "exact_feasible and exact_respecting_tuple_count must be null when exact_structural_status is not_applicable"
                )
        if self.gpd_str_status == "solved" and self.gpd_str is None:
            raise ValueError("gpd_str must be present when gpd_str_status is solved")
        if self.gpd_str_status != "solved" and self.gpd_str is not None:
            raise ValueError("gpd_str must be null unless gpd_str_status is solved")
        if self.gpd_stat_status == "solved" and self.gpd_stat is None:
            raise ValueError("gpd_stat must be present when gpd_stat_status is solved")
        if self.gpd_stat_status != "solved" and self.gpd_stat is not None:
            raise ValueError("gpd_stat must be null unless gpd_stat_status is solved")
        for name in ["gpd_str", "gpd_stat"]:
            value = getattr(self, name)
            if value is not None and (
                isinstance(value, bool) or not math.isfinite(value) or value < 0
            ):
                raise ValueError(f"{name} must be a finite non-negative value")
        if self.exact_respecting_tuple_count is not None and (
            isinstance(self.exact_respecting_tuple_count, bool)
            or self.exact_respecting_tuple_count < 0
        ):
            raise ValueError(
                "exact_respecting_tuple_count must be a non-negative integer when present"
            )
        if self.exact_failure_reason is not None and not self.exact_failure_reason:
            raise ValueError("exact_failure_reason must be non-empty when present")
        return self


class TargetedSearchRow(SixBirdsModel):
    row_format_version: str
    search_id: str
    point_id: str
    config_path: str
    preparation_id: str
    protocol_id: str
    trajectories: int
    seed: int
    raw_run_path: str
    discovered_context_family_path: str
    event_package_path: str | None = None
    provenance_classification: AdmissibilityClassification | None = None
    accepted_context_count: int
    accepted_singleton_event_count: int
    accepted_coarse_event_count: int
    accepted_shared_event_proposal_count: int
    accepted_coarse_proposal_count: int
    baseline_hard_only: TargetedSearchEvaluation
    all_accepted_proposals: TargetedSearchEvaluation
    ccd_status: AtlasStatus
    ccd_overall: float | None = None
    sec_status: AtlasStatus
    sec_mean: float | None = None
    rm_status: AtlasStatus
    rm_overall: float | None = None
    candidate_classification: TargetedCandidateLabel
    run_ids: dict[str, str]
    artifact_paths: dict[str, str]
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_row(self) -> "TargetedSearchRow":
        if self.row_format_version != "targeted-search-row.v1":
            raise ValueError("row_format_version must equal 'targeted-search-row.v1'")
        for name in [
            "search_id",
            "point_id",
            "config_path",
            "preparation_id",
            "protocol_id",
            "raw_run_path",
            "discovered_context_family_path",
        ]:
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise ValueError(f"{name} must be a non-empty string")
        ensure_repo_relative_mapping(
            {
                "config_path": self.config_path,
                "raw_run_path": self.raw_run_path,
                "discovered_context_family_path": self.discovered_context_family_path,
            },
            field_name="row_artifacts",
        )
        if self.event_package_path is not None and not is_repo_relative_path(
            self.event_package_path
        ):
            raise ValueError(
                "event_package_path must be a normalized repo-relative path when present"
            )
        if isinstance(self.trajectories, bool) or self.trajectories <= 0:
            raise ValueError("trajectories must be a positive integer")
        if isinstance(self.seed, bool):
            raise ValueError("seed must be an integer")
        for name in [
            "accepted_context_count",
            "accepted_singleton_event_count",
            "accepted_coarse_event_count",
            "accepted_shared_event_proposal_count",
            "accepted_coarse_proposal_count",
        ]:
            value = getattr(self, name)
            if isinstance(value, bool) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        for status_name, value_name in [
            ("ccd_status", "ccd_overall"),
            ("sec_status", "sec_mean"),
            ("rm_status", "rm_overall"),
        ]:
            status = getattr(self, status_name)
            value = getattr(self, value_name)
            if status in {"scored", "solved"}:
                if value is None:
                    raise ValueError(
                        f"{value_name} must be present when {status_name} is {status}"
                    )
            elif value is not None:
                raise ValueError(
                    f"{value_name} must be null unless {status_name} is scored"
                )
        for name in ["ccd_overall", "sec_mean", "rm_overall"]:
            value = getattr(self, name)
            if value is not None and (
                isinstance(value, bool) or not math.isfinite(value) or value < 0
            ):
                raise ValueError(f"{name} must be a finite non-negative value")
        if not self.run_ids:
            raise ValueError("run_ids must not be empty")
        if not self.artifact_paths:
            raise ValueError("artifact_paths must not be empty")
        for key, value in self.run_ids.items():
            if not isinstance(key, str) or not key:
                raise ValueError("run_ids keys must be non-empty strings")
            if not isinstance(value, str) or not value:
                raise ValueError("run_ids values must be non-empty strings")
        ensure_repo_relative_mapping(self.artifact_paths, field_name="artifact_paths")
        if any(not note for note in self.notes):
            raise ValueError("notes must contain only non-empty strings")
        return self


class TargetedSearchTable(SixBirdsModel):
    table_format_version: str
    search_id: str
    row_count: int
    rows: list[TargetedSearchRow]
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_table(self) -> "TargetedSearchTable":
        if self.table_format_version != "targeted-search-results.v1":
            raise ValueError(
                "table_format_version must equal 'targeted-search-results.v1'"
            )
        if not self.search_id:
            raise ValueError("search_id must be a non-empty string")
        if self.row_count != len(self.rows):
            raise ValueError("row_count must equal len(rows)")
        duplicates = collect_list_duplicates([row.point_id for row in self.rows])
        if duplicates:
            raise ValueError(
                f"targeted search rows must be unique by point_id: {', '.join(duplicates)}"
            )
        if any(row.search_id != self.search_id for row in self.rows):
            raise ValueError("all rows must share the table search_id")
        ensure_metadata_shape(self.metadata)
        return self


class FigureOutputSettings(SixBirdsModel):
    emit_regime_counts_csv: bool = True
    emit_atlas_points_csv: bool = True
    emit_threshold_summary_csv: bool = True


class AtlasUpgradePoint(SixBirdsModel):
    point_id: str
    config_artifact: str
    preparation_id: str
    protocol_id: str
    trajectories: int
    seed: int
    figure_group: str | None = None
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_point(self) -> "AtlasUpgradePoint":
        if not self.point_id:
            raise ValueError("point_id must be a non-empty string")
        ensure_repo_relative_mapping(
            {"config_artifact": self.config_artifact},
            field_name="config_artifact",
        )
        if not self.preparation_id:
            raise ValueError("preparation_id must be a non-empty string")
        if not self.protocol_id:
            raise ValueError("protocol_id must be a non-empty string")
        if isinstance(self.trajectories, bool) or self.trajectories <= 0:
            raise ValueError("trajectories must be a positive integer")
        if isinstance(self.seed, bool):
            raise ValueError("seed must be an integer")
        if self.figure_group is not None and not self.figure_group:
            raise ValueError("figure_group must be non-empty when present")
        if any(not note for note in self.notes):
            raise ValueError("notes must contain only non-empty strings")
        return self


class AtlasUpgradeConfig(SixBirdsModel):
    atlas_format_version: str
    atlas_id: str
    points: list[AtlasUpgradePoint]
    extraction_thresholds: ExtractionThresholds
    coarse_event_generation_thresholds: DiscoveredEventGenerationThresholds
    shared_event_inference_thresholds: SharedEventInferenceThresholds
    provenance_required: bool = True
    candidate_classification_thresholds: TargetedCandidateClassificationThresholds
    figure_output_settings: FigureOutputSettings = Field(
        default_factory=FigureOutputSettings
    )
    output_category: str | None = None
    output_label: str | None = None
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_atlas(self) -> "AtlasUpgradeConfig":
        if self.atlas_format_version != "atlas-upgrade-config.v1":
            raise ValueError(
                "atlas_format_version must equal 'atlas-upgrade-config.v1'"
            )
        if not self.atlas_id:
            raise ValueError("atlas_id must be a non-empty string")
        if not self.points:
            raise ValueError("points must not be empty")
        duplicates = collect_list_duplicates([point.point_id for point in self.points])
        if duplicates:
            raise ValueError(f"point_id values must be unique: {', '.join(duplicates)}")
        if self.output_category is not None and not self.output_category:
            raise ValueError("output_category must be non-empty when present")
        if self.output_label is not None and not self.output_label:
            raise ValueError("output_label must be non-empty when present")
        ensure_metadata_shape(self.metadata)
        return self


class AtlasUpgradeRow(SixBirdsModel):
    row_format_version: str
    atlas_id: str
    point_id: str
    config_path: str
    preparation_id: str
    protocol_id: str
    trajectories: int
    seed: int
    raw_run_path: str
    discovered_context_family_path: str
    event_package_path: str | None = None
    provenance_classification: AdmissibilityClassification | None = None
    accepted_context_count: int
    accepted_singleton_event_count: int
    accepted_coarse_event_count: int
    accepted_shared_event_proposal_count: int
    accepted_coarse_proposal_count: int
    baseline_hard_only: TargetedSearchEvaluation
    all_accepted_proposals: TargetedSearchEvaluation
    ccd_status: AtlasStatus
    ccd_overall: float | None = None
    sec_status: AtlasStatus
    sec_mean: float | None = None
    rm_status: AtlasStatus
    rm_overall: float | None = None
    regime_classification: RegimeLabel
    figure_group_labels: list[str] = Field(default_factory=list)
    run_ids: dict[str, str]
    artifact_paths: dict[str, str]
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_row(self) -> "AtlasUpgradeRow":
        if self.row_format_version != "atlas-upgrade-row.v1":
            raise ValueError("row_format_version must equal 'atlas-upgrade-row.v1'")
        for name in [
            "atlas_id",
            "point_id",
            "config_path",
            "preparation_id",
            "protocol_id",
            "raw_run_path",
            "discovered_context_family_path",
        ]:
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise ValueError(f"{name} must be a non-empty string")
        ensure_repo_relative_mapping(
            {
                "config_path": self.config_path,
                "raw_run_path": self.raw_run_path,
                "discovered_context_family_path": self.discovered_context_family_path,
            },
            field_name="row_artifacts",
        )
        if self.event_package_path is not None and not is_repo_relative_path(
            self.event_package_path
        ):
            raise ValueError(
                "event_package_path must be a normalized repo-relative path when present"
            )
        if isinstance(self.trajectories, bool) or self.trajectories <= 0:
            raise ValueError("trajectories must be a positive integer")
        if isinstance(self.seed, bool):
            raise ValueError("seed must be an integer")
        for name in [
            "accepted_context_count",
            "accepted_singleton_event_count",
            "accepted_coarse_event_count",
            "accepted_shared_event_proposal_count",
            "accepted_coarse_proposal_count",
        ]:
            value = getattr(self, name)
            if isinstance(value, bool) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        for status_name, value_name in [
            ("ccd_status", "ccd_overall"),
            ("sec_status", "sec_mean"),
            ("rm_status", "rm_overall"),
        ]:
            status = getattr(self, status_name)
            value = getattr(self, value_name)
            if status in {"scored", "solved"}:
                if value is None:
                    raise ValueError(
                        f"{value_name} must be present when {status_name} is {status}"
                    )
            elif value is not None:
                raise ValueError(
                    f"{value_name} must be null unless {status_name} is scored"
                )
        for name in ["ccd_overall", "sec_mean", "rm_overall"]:
            value = getattr(self, name)
            if value is not None and (
                isinstance(value, bool) or not math.isfinite(value) or value < 0
            ):
                raise ValueError(f"{name} must be a finite non-negative value")
        if any(not label for label in self.figure_group_labels):
            raise ValueError("figure_group_labels must contain only non-empty strings")
        if not self.run_ids:
            raise ValueError("run_ids must not be empty")
        if not self.artifact_paths:
            raise ValueError("artifact_paths must not be empty")
        for key, value in self.run_ids.items():
            if not isinstance(key, str) or not key:
                raise ValueError("run_ids keys must be non-empty strings")
            if not isinstance(value, str) or not value:
                raise ValueError("run_ids values must be non-empty strings")
        ensure_repo_relative_mapping(self.artifact_paths, field_name="artifact_paths")
        if any(not note for note in self.notes):
            raise ValueError("notes must contain only non-empty strings")
        return self


class AtlasUpgradeTable(SixBirdsModel):
    table_format_version: str
    atlas_id: str
    row_count: int
    rows: list[AtlasUpgradeRow]
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_table(self) -> "AtlasUpgradeTable":
        if self.table_format_version != "atlas-upgrade-results.v1":
            raise ValueError(
                "table_format_version must equal 'atlas-upgrade-results.v1'"
            )
        if not self.atlas_id:
            raise ValueError("atlas_id must be a non-empty string")
        if self.row_count != len(self.rows):
            raise ValueError("row_count must equal len(rows)")
        duplicates = collect_list_duplicates([row.point_id for row in self.rows])
        if duplicates:
            raise ValueError(
                f"atlas-upgrade rows must be unique by point_id: {', '.join(duplicates)}"
            )
        if any(row.atlas_id != self.atlas_id for row in self.rows):
            raise ValueError("all rows must share the table atlas_id")
        ensure_metadata_shape(self.metadata)
        return self


class PicaTargetedAdequacyFloor(SixBirdsModel):
    min_total_point_count: int = 4
    min_admissible_built_package_count: int = 2
    min_points_with_proper_coarse_events: int = 2
    min_points_with_proper_coarse_structural_proposals: int = 1
    min_points_with_dual_mode_difference: int = 1

    @model_validator(mode="after")
    def validate_floor(self) -> "PicaTargetedAdequacyFloor":
        for name in [
            "min_total_point_count",
            "min_admissible_built_package_count",
            "min_points_with_proper_coarse_events",
            "min_points_with_proper_coarse_structural_proposals",
            "min_points_with_dual_mode_difference",
        ]:
            value = getattr(self, name)
            if isinstance(value, bool) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        return self


class PicaTargetedSearchPoint(SixBirdsModel):
    point_id: str
    pilot_config_artifact: str
    discovery_config_artifact: str
    trajectories: int
    seed_list: list[int]
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_point(self) -> "PicaTargetedSearchPoint":
        if not self.point_id:
            raise ValueError("point_id must be a non-empty string")
        ensure_repo_relative_mapping(
            {
                "pilot_config_artifact": self.pilot_config_artifact,
                "discovery_config_artifact": self.discovery_config_artifact,
            },
            field_name="point_artifacts",
        )
        if isinstance(self.trajectories, bool) or self.trajectories <= 0:
            raise ValueError("trajectories must be a positive integer")
        if not self.seed_list:
            raise ValueError("seed_list must not be empty")
        duplicates = collect_list_duplicates([str(seed) for seed in self.seed_list])
        if duplicates:
            raise ValueError(f"seed_list must be unique: {', '.join(duplicates)}")
        for seed in self.seed_list:
            if isinstance(seed, bool):
                raise ValueError("seed_list must contain only integers")
        if any(not note for note in self.notes):
            raise ValueError("notes must contain only non-empty strings")
        return self


class PicaTargetedObstructionSearch(SixBirdsModel):
    search_format_version: str
    search_id: str
    points: list[PicaTargetedSearchPoint]
    event_generation_thresholds: DiscoveredEventGenerationThresholds
    shared_event_inference_thresholds: SharedEventInferenceThresholds
    provenance_required: bool = True
    candidate_classification_thresholds: TargetedCandidateClassificationThresholds
    adequacy_floor: PicaTargetedAdequacyFloor
    output_category: str | None = None
    output_label: str | None = None
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_search(self) -> "PicaTargetedObstructionSearch":
        if self.search_format_version != "pica-targeted-obstruction-search.v1":
            raise ValueError(
                "search_format_version must equal 'pica-targeted-obstruction-search.v1'"
            )
        if not self.search_id:
            raise ValueError("search_id must be a non-empty string")
        if not self.points:
            raise ValueError("points must not be empty")
        duplicates = collect_list_duplicates([point.point_id for point in self.points])
        if duplicates:
            raise ValueError(f"point_id values must be unique: {', '.join(duplicates)}")
        if self.output_category is not None and not self.output_category:
            raise ValueError("output_category must be non-empty when present")
        if self.output_label is not None and not self.output_label:
            raise ValueError("output_label must be non-empty when present")
        ensure_metadata_shape(self.metadata)
        return self


class PicaTargetedSearchRow(SixBirdsModel):
    row_format_version: str
    search_id: str
    point_id: str
    source_pica_campaign_config_path: str
    discovery_config_path: str
    preparation_id: str
    protocol_id: str
    trajectories: int
    seed_list: list[int]
    produced_export_bundle_path: str
    discovered_context_family_path: str
    event_package_path: str | None = None
    provenance_classification: AdmissibilityClassification | None = None
    accepted_context_count: int
    accepted_singleton_event_count: int
    accepted_proper_coarse_event_count: int
    accepted_shared_event_proposal_count: int
    accepted_proper_coarse_structural_proposal_count: int
    baseline_hard_only: TargetedSearchEvaluation
    all_accepted_proposals: TargetedSearchEvaluation
    ccd_status: AtlasStatus
    ccd_overall: float | None = None
    sec_status: AtlasStatus
    sec_mean: float | None = None
    rm_status: AtlasStatus
    rm_overall: float | None = None
    candidate_classification: TargetedCandidateLabel
    run_ids: dict[str, str]
    artifact_paths: dict[str, str]
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_row(self) -> "PicaTargetedSearchRow":
        if self.row_format_version != "pica-targeted-search-row.v1":
            raise ValueError(
                "row_format_version must equal 'pica-targeted-search-row.v1'"
            )
        for name in [
            "search_id",
            "point_id",
            "source_pica_campaign_config_path",
            "discovery_config_path",
            "preparation_id",
            "protocol_id",
            "produced_export_bundle_path",
            "discovered_context_family_path",
        ]:
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise ValueError(f"{name} must be a non-empty string")
        ensure_repo_relative_mapping(
            {
                "source_pica_campaign_config_path": self.source_pica_campaign_config_path,
                "discovery_config_path": self.discovery_config_path,
                "produced_export_bundle_path": self.produced_export_bundle_path,
                "discovered_context_family_path": self.discovered_context_family_path,
            },
            field_name="row_artifacts",
        )
        if self.event_package_path is not None and not is_repo_relative_path(
            self.event_package_path
        ):
            raise ValueError(
                "event_package_path must be a normalized repo-relative path when present"
            )
        if isinstance(self.trajectories, bool) or self.trajectories <= 0:
            raise ValueError("trajectories must be a positive integer")
        if not self.seed_list:
            raise ValueError("seed_list must not be empty")
        duplicates = collect_list_duplicates([str(seed) for seed in self.seed_list])
        if duplicates:
            raise ValueError(f"seed_list must be unique: {', '.join(duplicates)}")
        for seed in self.seed_list:
            if isinstance(seed, bool):
                raise ValueError("seed_list must contain only integers")
        for name in [
            "accepted_context_count",
            "accepted_singleton_event_count",
            "accepted_proper_coarse_event_count",
            "accepted_shared_event_proposal_count",
            "accepted_proper_coarse_structural_proposal_count",
        ]:
            value = getattr(self, name)
            if isinstance(value, bool) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        for status_name, value_name in [
            ("ccd_status", "ccd_overall"),
            ("sec_status", "sec_mean"),
            ("rm_status", "rm_overall"),
        ]:
            status = getattr(self, status_name)
            value = getattr(self, value_name)
            if status in {"scored", "solved"}:
                if value is None:
                    raise ValueError(
                        f"{value_name} must be present when {status_name} is {status}"
                    )
            elif value is not None:
                raise ValueError(
                    f"{value_name} must be null unless {status_name} is scored"
                )
        for name in ["ccd_overall", "sec_mean", "rm_overall"]:
            value = getattr(self, name)
            if value is not None and (
                isinstance(value, bool) or not math.isfinite(value) or value < 0
            ):
                raise ValueError(f"{name} must be a finite non-negative value")
        if not self.run_ids:
            raise ValueError("run_ids must not be empty")
        if not self.artifact_paths:
            raise ValueError("artifact_paths must not be empty")
        ensure_repo_relative_mapping(self.artifact_paths, field_name="artifact_paths")
        if any(not note for note in self.notes):
            raise ValueError("notes must contain only non-empty strings")
        return self


class PicaTargetedSearchTable(SixBirdsModel):
    table_format_version: str
    search_id: str
    row_count: int
    rows: list[PicaTargetedSearchRow]
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_table(self) -> "PicaTargetedSearchTable":
        if self.table_format_version != "pica-targeted-search-results.v1":
            raise ValueError(
                "table_format_version must equal 'pica-targeted-search-results.v1'"
            )
        if not self.search_id:
            raise ValueError("search_id must be a non-empty string")
        if self.row_count != len(self.rows):
            raise ValueError("row_count must equal len(rows)")
        duplicates = collect_list_duplicates([row.point_id for row in self.rows])
        if duplicates:
            raise ValueError(
                f"pica targeted-search rows must be unique by point_id: {', '.join(duplicates)}"
            )
        if any(row.search_id != self.search_id for row in self.rows):
            raise ValueError("all rows must share the table search_id")
        ensure_metadata_shape(self.metadata)
        return self


class ClosureDiverseProjectionFamily(SixBirdsModel):
    projection_id: str
    label: str
    projection: PicaObservableProjection
    notes: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_family(self) -> "ClosureDiverseProjectionFamily":
        if not self.projection_id:
            raise ValueError("projection_id must be a non-empty string")
        if not self.label:
            raise ValueError("label must be a non-empty string")
        duplicates = collect_list_duplicates(self.notes + self.flags)
        if duplicates:
            raise ValueError(
                f"notes/flags values must be unique within a projection family: {', '.join(duplicates)}"
            )
        if any(not value for value in self.notes + self.flags):
            raise ValueError("notes and flags must contain only non-empty strings")
        return self


class FrozenSliceProjectionFamily(SixBirdsModel):
    projection_id: str
    label: str
    source_field: str
    projection_kind: ProjectionFamilyKind
    allowed_roles: list[ProjectionFamilyRole]
    projection: PicaObservableProjection
    notes: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_family(self) -> "FrozenSliceProjectionFamily":
        if not self.projection_id:
            raise ValueError("projection_id must be a non-empty string")
        if not self.label:
            raise ValueError("label must be a non-empty string")
        if not self.source_field:
            raise ValueError("source_field must be a non-empty string")
        if not self.allowed_roles:
            raise ValueError("allowed_roles must not be empty")
        role_duplicates = collect_list_duplicates(self.allowed_roles)
        if role_duplicates:
            raise ValueError(
                f"allowed_roles must be unique: {', '.join(role_duplicates)}"
            )
        duplicates = collect_list_duplicates(self.notes + self.flags)
        if duplicates:
            raise ValueError(
                f"notes/flags values must be unique within a projection family: {', '.join(duplicates)}"
            )
        if any(not value for value in self.notes + self.flags):
            raise ValueError("notes and flags must contain only non-empty strings")
        return self


class PicaFrozenSliceSearchPoint(SixBirdsModel):
    point_id: str
    pilot_config_artifact: str
    preparation_id: str
    protocol_id: str
    trajectories: int
    seed_list: list[int]
    projection_family_ids: list[str]
    selected_protocol_step_ids: list[str] = Field(default_factory=list)
    selected_step_indices: list[int] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_point(self) -> "PicaFrozenSliceSearchPoint":
        if not self.point_id:
            raise ValueError("point_id must be a non-empty string")
        if not self.preparation_id:
            raise ValueError("preparation_id must be a non-empty string")
        if not self.protocol_id:
            raise ValueError("protocol_id must be a non-empty string")
        ensure_repo_relative_mapping(
            {"pilot_config_artifact": self.pilot_config_artifact},
            field_name="point_artifacts",
        )
        if isinstance(self.trajectories, bool) or self.trajectories <= 0:
            raise ValueError("trajectories must be a positive integer")
        if not self.seed_list:
            raise ValueError("seed_list must not be empty")
        seed_duplicates = collect_list_duplicates(
            [str(seed) for seed in self.seed_list]
        )
        if seed_duplicates:
            raise ValueError(f"seed_list must be unique: {', '.join(seed_duplicates)}")
        if any(isinstance(seed, bool) for seed in self.seed_list):
            raise ValueError("seed_list must contain only integers")
        if not self.projection_family_ids:
            raise ValueError("projection_family_ids must not be empty")
        projection_duplicates = collect_list_duplicates(self.projection_family_ids)
        if projection_duplicates:
            raise ValueError(
                f"projection_family_ids must be unique: {', '.join(projection_duplicates)}"
            )
        step_duplicates = collect_list_duplicates(self.selected_protocol_step_ids)
        if step_duplicates:
            raise ValueError(
                f"selected_protocol_step_ids must be unique: {', '.join(step_duplicates)}"
            )
        if any(not value for value in self.selected_protocol_step_ids):
            raise ValueError(
                "selected_protocol_step_ids must contain only non-empty strings"
            )
        index_duplicates = collect_list_duplicates(
            [str(value) for value in self.selected_step_indices]
        )
        if index_duplicates:
            raise ValueError(
                f"selected_step_indices must be unique: {', '.join(index_duplicates)}"
            )
        if any(
            isinstance(value, bool) or value < 0 for value in self.selected_step_indices
        ):
            raise ValueError("selected_step_indices must contain non-negative integers")
        if any(not value for value in self.notes):
            raise ValueError("notes must contain only non-empty strings")
        return self


class FrozenSliceSourcePairPolicy(SixBirdsModel):
    require_same_preparation_id: bool = True
    require_same_protocol_id: bool = True
    require_same_protocol_step_id: bool = True
    require_same_step_index: bool = True
    require_shared_support_scope: bool = True


class PicaFrozenSliceAdequacyFloor(SixBirdsModel):
    min_total_point_count: int = 3
    min_admissible_built_package_count: int = 2
    min_points_with_proper_coarse_events: int = 2
    min_points_with_primary_same_slice_proper_coarse_structural_proposals: int = 1
    min_points_with_same_slice_non_nested_context_pairs: int = 1
    min_points_with_dual_mode_difference: int = 1
    min_median_accepted_proposal_support: float = 3.0

    @model_validator(mode="after")
    def validate_floor(self) -> "PicaFrozenSliceAdequacyFloor":
        for name in [
            "min_total_point_count",
            "min_admissible_built_package_count",
            "min_points_with_proper_coarse_events",
            "min_points_with_primary_same_slice_proper_coarse_structural_proposals",
            "min_points_with_same_slice_non_nested_context_pairs",
            "min_points_with_dual_mode_difference",
        ]:
            value = getattr(self, name)
            if isinstance(value, bool) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if (
            isinstance(self.min_median_accepted_proposal_support, bool)
            or not math.isfinite(self.min_median_accepted_proposal_support)
            or self.min_median_accepted_proposal_support < 0
        ):
            raise ValueError(
                "min_median_accepted_proposal_support must be a finite non-negative value"
            )
        return self


class PicaFrozenSliceSearch(SixBirdsModel):
    search_format_version: str
    search_id: str
    points: list[PicaFrozenSliceSearchPoint]
    projection_families: list[FrozenSliceProjectionFamily]
    source_pair_policy: FrozenSliceSourcePairPolicy = Field(
        default_factory=FrozenSliceSourcePairPolicy
    )
    event_generation_thresholds: DiscoveredEventGenerationThresholds
    shared_event_inference_thresholds: SharedEventInferenceThresholds
    provenance_required: bool = True
    candidate_classification_thresholds: TargetedCandidateClassificationThresholds
    adequacy_floor: PicaFrozenSliceAdequacyFloor
    output_category: str | None = None
    output_label: str | None = None
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_search(self) -> "PicaFrozenSliceSearch":
        if self.search_format_version != "pica-frozen-slice-search.v1":
            raise ValueError(
                "search_format_version must equal 'pica-frozen-slice-search.v1'"
            )
        if not self.search_id:
            raise ValueError("search_id must be a non-empty string")
        if not self.points:
            raise ValueError("points must not be empty")
        point_duplicates = collect_list_duplicates(
            [point.point_id for point in self.points]
        )
        if point_duplicates:
            raise ValueError(
                f"point_id values must be unique: {', '.join(point_duplicates)}"
            )
        if not self.projection_families:
            raise ValueError("projection_families must not be empty")
        family_duplicates = collect_list_duplicates(
            [family.projection_id for family in self.projection_families]
        )
        if family_duplicates:
            raise ValueError(
                f"projection_families must be unique by projection_id: {', '.join(family_duplicates)}"
            )
        family_ids = {family.projection_id for family in self.projection_families}
        primary_ids = {
            family.projection_id
            for family in self.projection_families
            if "primary_context" in family.allowed_roles
        }
        for point in self.points:
            unknown = sorted(set(point.projection_family_ids) - family_ids)
            if unknown:
                raise ValueError(
                    f"point {point.point_id} references unknown projection families: {', '.join(unknown)}"
                )
            if not set(point.projection_family_ids) & primary_ids:
                raise ValueError(
                    f"point {point.point_id} must reference at least one primary_context projection family"
                )
        if self.output_category is not None and not self.output_category:
            raise ValueError("output_category must be non-empty when present")
        if self.output_label is not None and not self.output_label:
            raise ValueError("output_label must be non-empty when present")
        ensure_metadata_shape(self.metadata)
        return self


class ProjectionFamilyAdmissibilityRow(SixBirdsModel):
    point_id: str
    projection_id: str
    source_field: str
    projection_kind: ProjectionFamilyKind
    allowed_roles: list[ProjectionFamilyRole]
    row_count: int
    unique_value_count: int
    varies_within_frozen_slice: bool
    notes: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_row(self) -> "ProjectionFamilyAdmissibilityRow":
        for name in ["point_id", "projection_id", "source_field"]:
            if not getattr(self, name):
                raise ValueError(f"{name} must be a non-empty string")
        if not self.allowed_roles:
            raise ValueError("allowed_roles must not be empty")
        if isinstance(self.row_count, bool) or self.row_count < 0:
            raise ValueError("row_count must be a non-negative integer")
        if isinstance(self.unique_value_count, bool) or self.unique_value_count < 0:
            raise ValueError("unique_value_count must be a non-negative integer")
        if any(not value for value in self.notes + self.flags):
            raise ValueError("notes and flags must contain only non-empty strings")
        return self


class ProjectionFamilyAdmissibilityTable(SixBirdsModel):
    table_format_version: str
    search_id: str
    row_count: int
    rows: list[ProjectionFamilyAdmissibilityRow]
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_table(self) -> "ProjectionFamilyAdmissibilityTable":
        if self.table_format_version != "projection-family-admissibility.v1":
            raise ValueError(
                "table_format_version must equal 'projection-family-admissibility.v1'"
            )
        if not self.search_id:
            raise ValueError("search_id must be a non-empty string")
        if self.row_count != len(self.rows):
            raise ValueError("row_count must equal len(rows)")
        ensure_metadata_shape(self.metadata)
        return self


class PicaClosureDiverseSearchPoint(SixBirdsModel):
    point_id: str
    pilot_config_artifact: str
    preparation_id: str
    protocol_id: str
    trajectories: int
    seed_list: list[int]
    projection_family_ids: list[str]
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_point(self) -> "PicaClosureDiverseSearchPoint":
        if not self.point_id:
            raise ValueError("point_id must be a non-empty string")
        if not self.preparation_id:
            raise ValueError("preparation_id must be a non-empty string")
        if not self.protocol_id:
            raise ValueError("protocol_id must be a non-empty string")
        ensure_repo_relative_mapping(
            {"pilot_config_artifact": self.pilot_config_artifact},
            field_name="point_artifacts",
        )
        if isinstance(self.trajectories, bool) or self.trajectories <= 0:
            raise ValueError("trajectories must be a positive integer")
        if not self.seed_list:
            raise ValueError("seed_list must not be empty")
        seed_duplicates = collect_list_duplicates(
            [str(seed) for seed in self.seed_list]
        )
        if seed_duplicates:
            raise ValueError(f"seed_list must be unique: {', '.join(seed_duplicates)}")
        if any(isinstance(seed, bool) for seed in self.seed_list):
            raise ValueError("seed_list must contain only integers")
        if not self.projection_family_ids:
            raise ValueError("projection_family_ids must not be empty")
        projection_duplicates = collect_list_duplicates(self.projection_family_ids)
        if projection_duplicates:
            raise ValueError(
                f"projection_family_ids must be unique: {', '.join(projection_duplicates)}"
            )
        if any(not value for value in self.notes):
            raise ValueError("notes must contain only non-empty strings")
        return self


class PicaClosureDiverseAdequacyFloor(SixBirdsModel):
    min_total_point_count: int = 4
    min_admissible_built_package_count: int = 2
    min_points_with_proper_coarse_events: int = 2
    min_points_with_proper_coarse_structural_proposals: int = 1
    min_points_with_incomparable_context_pairs: int = 1
    min_points_with_dual_mode_difference: int = 1
    min_median_accepted_proposal_support: float = 3.0

    @model_validator(mode="after")
    def validate_floor(self) -> "PicaClosureDiverseAdequacyFloor":
        for name in [
            "min_total_point_count",
            "min_admissible_built_package_count",
            "min_points_with_proper_coarse_events",
            "min_points_with_proper_coarse_structural_proposals",
            "min_points_with_incomparable_context_pairs",
            "min_points_with_dual_mode_difference",
        ]:
            value = getattr(self, name)
            if isinstance(value, bool) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if (
            isinstance(self.min_median_accepted_proposal_support, bool)
            or not math.isfinite(self.min_median_accepted_proposal_support)
            or self.min_median_accepted_proposal_support < 0
        ):
            raise ValueError(
                "min_median_accepted_proposal_support must be a finite non-negative value"
            )
        return self


class PicaClosureDiverseSearch(SixBirdsModel):
    search_format_version: str
    search_id: str
    points: list[PicaClosureDiverseSearchPoint]
    projection_families: list[ClosureDiverseProjectionFamily]
    event_generation_thresholds: DiscoveredEventGenerationThresholds
    shared_event_inference_thresholds: SharedEventInferenceThresholds
    provenance_required: bool = True
    candidate_classification_thresholds: TargetedCandidateClassificationThresholds
    adequacy_floor: PicaClosureDiverseAdequacyFloor
    output_category: str | None = None
    output_label: str | None = None
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_search(self) -> "PicaClosureDiverseSearch":
        if self.search_format_version != "pica-closure-diverse-search.v1":
            raise ValueError(
                "search_format_version must equal 'pica-closure-diverse-search.v1'"
            )
        if not self.search_id:
            raise ValueError("search_id must be a non-empty string")
        if not self.points:
            raise ValueError("points must not be empty")
        point_duplicates = collect_list_duplicates(
            [point.point_id for point in self.points]
        )
        if point_duplicates:
            raise ValueError(
                f"point_id values must be unique: {', '.join(point_duplicates)}"
            )
        if not self.projection_families:
            raise ValueError("projection_families must not be empty")
        family_duplicates = collect_list_duplicates(
            [family.projection_id for family in self.projection_families]
        )
        if family_duplicates:
            raise ValueError(
                f"projection_families must be unique by projection_id: {', '.join(family_duplicates)}"
            )
        family_ids = {family.projection_id for family in self.projection_families}
        for point in self.points:
            unknown = sorted(set(point.projection_family_ids) - family_ids)
            if unknown:
                raise ValueError(
                    f"point {point.point_id} references unknown projection families: {', '.join(unknown)}"
                )
        if self.output_category is not None and not self.output_category:
            raise ValueError("output_category must be non-empty when present")
        if self.output_label is not None and not self.output_label:
            raise ValueError("output_label must be non-empty when present")
        ensure_metadata_shape(self.metadata)
        return self


class ContextPairSide(SixBirdsModel):
    context_id: str
    level_id: str
    resolution_id: str
    closure_id: str
    lens_id: str
    protocol_step_id: str
    step_index: int
    projection_id: str | None = None
    projection_field: str

    @model_validator(mode="after")
    def validate_side(self) -> "ContextPairSide":
        for name in [
            "context_id",
            "level_id",
            "resolution_id",
            "closure_id",
            "lens_id",
            "protocol_step_id",
            "projection_field",
        ]:
            if not getattr(self, name):
                raise ValueError(f"{name} must be a non-empty string")
        if self.projection_id is not None and not self.projection_id:
            raise ValueError("projection_id must be non-empty when present")
        if isinstance(self.step_index, bool) or self.step_index < 0:
            raise ValueError("step_index must be a non-negative integer")
        return self


class ContextPairStructureRow(SixBirdsModel):
    point_id: str
    preparation_id: str
    protocol_id: str
    left: ContextPairSide
    right: ContextPairSide
    relation_type: ContextRelationType
    shared_row_count: int
    left_assignment_count: int
    right_assignment_count: int
    left_block_count: int
    right_block_count: int
    same_step: bool
    same_frozen_slice: bool = False
    primary_identity_admissible: bool = False
    commutator_admissibility_mode: CommutatorAdmissibilityMode | None = None
    packaging_conflict_supported: bool = False
    commutator_support_pairs: list[str] = Field(default_factory=list)
    primary_packaging_conflict_admissible: bool = False
    packaging_conflict_admissibility_class: (
        PackagingConflictAdmissibilityClass | None
    ) = None
    admissibility_reason: str | None = None
    notes: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_row(self) -> "ContextPairStructureRow":
        for name in ["point_id", "preparation_id", "protocol_id"]:
            if not getattr(self, name):
                raise ValueError(f"{name} must be a non-empty string")
        for name in [
            "shared_row_count",
            "left_assignment_count",
            "right_assignment_count",
            "left_block_count",
            "right_block_count",
        ]:
            value = getattr(self, name)
            if isinstance(value, bool) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if any(not value for value in self.commutator_support_pairs):
            raise ValueError(
                "commutator_support_pairs must contain only non-empty strings"
            )
        if (
            self.commutator_admissibility_mode is not None
            and not self.commutator_admissibility_mode
        ):
            raise ValueError(
                "commutator_admissibility_mode must be non-empty when present"
            )
        if (
            self.packaging_conflict_admissibility_class is not None
            and not self.packaging_conflict_admissibility_class
        ):
            raise ValueError(
                "packaging_conflict_admissibility_class must be non-empty when present"
            )
        if self.admissibility_reason is not None and not self.admissibility_reason:
            raise ValueError("admissibility_reason must be non-empty when present")
        if any(not value for value in self.notes + self.flags):
            raise ValueError("notes and flags must contain only non-empty strings")
        return self


class ContextPairStructureTable(SixBirdsModel):
    structure_format_version: str
    search_id: str
    row_count: int
    rows: list[ContextPairStructureRow]
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_table(self) -> "ContextPairStructureTable":
        if self.structure_format_version != "context-pair-structure.v1":
            raise ValueError(
                "structure_format_version must equal 'context-pair-structure.v1'"
            )
        if not self.search_id:
            raise ValueError("search_id must be a non-empty string")
        if self.row_count != len(self.rows):
            raise ValueError("row_count must equal len(rows)")
        ensure_metadata_shape(self.metadata)
        return self


class PicaClosureDiverseSearchRow(SixBirdsModel):
    row_format_version: str
    search_id: str
    point_id: str
    source_pica_campaign_config_path: str
    projection_family_ids: list[str]
    preparation_id: str
    protocol_id: str
    trajectories: int
    seed_list: list[int]
    produced_export_bundle_path: str
    discovered_context_family_path: str
    event_package_path: str | None = None
    provenance_classification: AdmissibilityClassification | None = None
    accepted_context_count: int
    accepted_proper_coarse_event_count: int
    accepted_shared_event_proposal_count: int
    accepted_proper_coarse_structural_proposal_count: int
    accepted_incomparable_proper_coarse_proposal_count: int
    equal_context_pair_count: int
    left_refines_right_count: int
    right_refines_left_count: int
    incomparable_context_pair_count: int
    disjoint_or_unaligned_context_pair_count: int
    median_accepted_proposal_support: float | None = None
    baseline_hard_only: TargetedSearchEvaluation
    all_accepted_proposals: TargetedSearchEvaluation
    ccd_status: AtlasStatus
    ccd_overall: float | None = None
    sec_status: AtlasStatus
    sec_mean: float | None = None
    rm_status: AtlasStatus
    rm_overall: float | None = None
    candidate_classification: TargetedCandidateLabel
    run_ids: dict[str, str]
    artifact_paths: dict[str, str]
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_row(self) -> "PicaClosureDiverseSearchRow":
        if self.row_format_version != "pica-closure-diverse-search-row.v1":
            raise ValueError(
                "row_format_version must equal 'pica-closure-diverse-search-row.v1'"
            )
        for name in [
            "search_id",
            "point_id",
            "source_pica_campaign_config_path",
            "preparation_id",
            "protocol_id",
            "produced_export_bundle_path",
            "discovered_context_family_path",
        ]:
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise ValueError(f"{name} must be a non-empty string")
        ensure_repo_relative_mapping(
            {
                "source_pica_campaign_config_path": self.source_pica_campaign_config_path,
                "produced_export_bundle_path": self.produced_export_bundle_path,
                "discovered_context_family_path": self.discovered_context_family_path,
            },
            field_name="row_artifacts",
        )
        if self.event_package_path is not None and not is_repo_relative_path(
            self.event_package_path
        ):
            raise ValueError(
                "event_package_path must be a normalized repo-relative path when present"
            )
        if not self.projection_family_ids:
            raise ValueError("projection_family_ids must not be empty")
        projection_duplicates = collect_list_duplicates(self.projection_family_ids)
        if projection_duplicates:
            raise ValueError(
                f"projection_family_ids must be unique: {', '.join(projection_duplicates)}"
            )
        if isinstance(self.trajectories, bool) or self.trajectories <= 0:
            raise ValueError("trajectories must be a positive integer")
        if not self.seed_list:
            raise ValueError("seed_list must not be empty")
        seed_duplicates = collect_list_duplicates(
            [str(seed) for seed in self.seed_list]
        )
        if seed_duplicates:
            raise ValueError(f"seed_list must be unique: {', '.join(seed_duplicates)}")
        for seed in self.seed_list:
            if isinstance(seed, bool):
                raise ValueError("seed_list must contain only integers")
        for name in [
            "accepted_context_count",
            "accepted_proper_coarse_event_count",
            "accepted_shared_event_proposal_count",
            "accepted_proper_coarse_structural_proposal_count",
            "accepted_incomparable_proper_coarse_proposal_count",
            "equal_context_pair_count",
            "left_refines_right_count",
            "right_refines_left_count",
            "incomparable_context_pair_count",
            "disjoint_or_unaligned_context_pair_count",
        ]:
            value = getattr(self, name)
            if isinstance(value, bool) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if self.median_accepted_proposal_support is not None and (
            isinstance(self.median_accepted_proposal_support, bool)
            or not math.isfinite(self.median_accepted_proposal_support)
            or self.median_accepted_proposal_support < 0
        ):
            raise ValueError(
                "median_accepted_proposal_support must be a finite non-negative value when present"
            )
        for status_name, value_name in [
            ("ccd_status", "ccd_overall"),
            ("sec_status", "sec_mean"),
            ("rm_status", "rm_overall"),
        ]:
            status = getattr(self, status_name)
            value = getattr(self, value_name)
            if status in {"scored", "solved"}:
                if value is None:
                    raise ValueError(
                        f"{value_name} must be present when {status_name} is {status}"
                    )
            elif value is not None:
                raise ValueError(
                    f"{value_name} must be null unless {status_name} is scored"
                )
        for name in ["ccd_overall", "sec_mean", "rm_overall"]:
            value = getattr(self, name)
            if value is not None and (
                isinstance(value, bool) or not math.isfinite(value) or value < 0
            ):
                raise ValueError(f"{name} must be a finite non-negative value")
        if not self.run_ids:
            raise ValueError("run_ids must not be empty")
        if not self.artifact_paths:
            raise ValueError("artifact_paths must not be empty")
        ensure_repo_relative_mapping(self.artifact_paths, field_name="artifact_paths")
        if any(not value for value in self.notes):
            raise ValueError("notes must contain only non-empty strings")
        return self


class PicaClosureDiverseSearchTable(SixBirdsModel):
    table_format_version: str
    search_id: str
    row_count: int
    rows: list[PicaClosureDiverseSearchRow]
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_table(self) -> "PicaClosureDiverseSearchTable":
        if self.table_format_version != "pica-closure-diverse-search-results.v1":
            raise ValueError(
                "table_format_version must equal 'pica-closure-diverse-search-results.v1'"
            )
        if not self.search_id:
            raise ValueError("search_id must be a non-empty string")
        if self.row_count != len(self.rows):
            raise ValueError("row_count must equal len(rows)")
        duplicates = collect_list_duplicates([row.point_id for row in self.rows])
        if duplicates:
            raise ValueError(
                f"pica closure-diverse rows must be unique by point_id: {', '.join(duplicates)}"
            )
        if any(row.search_id != self.search_id for row in self.rows):
            raise ValueError("all rows must share the table search_id")
        ensure_metadata_shape(self.metadata)
        return self


class PicaFrozenSliceSearchRow(SixBirdsModel):
    row_format_version: str
    search_id: str
    point_id: str
    source_pica_campaign_config_path: str
    projection_family_ids: list[str]
    preparation_id: str
    protocol_id: str
    selected_protocol_step_ids: list[str]
    selected_step_indices: list[int]
    trajectories: int
    seed_list: list[int]
    produced_export_bundle_path: str
    discovered_context_family_path: str
    event_package_path: str | None = None
    provenance_classification: AdmissibilityClassification | None = None
    accepted_context_count: int
    accepted_proper_coarse_event_count: int
    accepted_shared_event_proposal_count: int
    accepted_proper_coarse_structural_proposal_count: int
    accepted_primary_same_slice_proper_coarse_proposal_count: int
    equal_context_pair_count: int
    left_refines_right_count: int
    right_refines_left_count: int
    incomparable_context_pair_count: int
    disjoint_or_unaligned_context_pair_count: int
    same_slice_non_nested_context_pair_count: int
    primary_identity_admissible_pair_count: int
    median_accepted_proposal_support: float | None = None
    baseline_hard_only: TargetedSearchEvaluation
    all_accepted_proposals: TargetedSearchEvaluation
    ccd_status: AtlasStatus
    ccd_overall: float | None = None
    sec_status: AtlasStatus
    sec_mean: float | None = None
    rm_status: AtlasStatus
    rm_overall: float | None = None
    candidate_classification: TargetedCandidateLabel
    run_ids: dict[str, str]
    artifact_paths: dict[str, str]
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_row(self) -> "PicaFrozenSliceSearchRow":
        if self.row_format_version != "pica-frozen-slice-search-row.v1":
            raise ValueError(
                "row_format_version must equal 'pica-frozen-slice-search-row.v1'"
            )
        for name in [
            "search_id",
            "point_id",
            "source_pica_campaign_config_path",
            "preparation_id",
            "protocol_id",
            "produced_export_bundle_path",
            "discovered_context_family_path",
        ]:
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise ValueError(f"{name} must be a non-empty string")
        ensure_repo_relative_mapping(
            {
                "source_pica_campaign_config_path": self.source_pica_campaign_config_path,
                "produced_export_bundle_path": self.produced_export_bundle_path,
                "discovered_context_family_path": self.discovered_context_family_path,
            },
            field_name="row_artifacts",
        )
        if self.event_package_path is not None and not is_repo_relative_path(
            self.event_package_path
        ):
            raise ValueError(
                "event_package_path must be a normalized repo-relative path when present"
            )
        if not self.projection_family_ids:
            raise ValueError("projection_family_ids must not be empty")
        if not self.selected_protocol_step_ids:
            raise ValueError("selected_protocol_step_ids must not be empty")
        if not self.selected_step_indices:
            raise ValueError("selected_step_indices must not be empty")
        if isinstance(self.trajectories, bool) or self.trajectories <= 0:
            raise ValueError("trajectories must be a positive integer")
        if not self.seed_list:
            raise ValueError("seed_list must not be empty")
        for name in [
            "accepted_context_count",
            "accepted_proper_coarse_event_count",
            "accepted_shared_event_proposal_count",
            "accepted_proper_coarse_structural_proposal_count",
            "accepted_primary_same_slice_proper_coarse_proposal_count",
            "equal_context_pair_count",
            "left_refines_right_count",
            "right_refines_left_count",
            "incomparable_context_pair_count",
            "disjoint_or_unaligned_context_pair_count",
            "same_slice_non_nested_context_pair_count",
            "primary_identity_admissible_pair_count",
        ]:
            value = getattr(self, name)
            if isinstance(value, bool) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if self.median_accepted_proposal_support is not None and (
            isinstance(self.median_accepted_proposal_support, bool)
            or not math.isfinite(self.median_accepted_proposal_support)
            or self.median_accepted_proposal_support < 0
        ):
            raise ValueError(
                "median_accepted_proposal_support must be a finite non-negative value when present"
            )
        for status_name, value_name in [
            ("ccd_status", "ccd_overall"),
            ("sec_status", "sec_mean"),
            ("rm_status", "rm_overall"),
        ]:
            status = getattr(self, status_name)
            value = getattr(self, value_name)
            if status in {"scored", "solved"}:
                if value is None:
                    raise ValueError(
                        f"{value_name} must be present when {status_name} is {status}"
                    )
            elif value is not None:
                raise ValueError(
                    f"{value_name} must be null unless {status_name} is scored"
                )
        for name in ["ccd_overall", "sec_mean", "rm_overall"]:
            value = getattr(self, name)
            if value is not None and (
                isinstance(value, bool) or not math.isfinite(value) or value < 0
            ):
                raise ValueError(f"{name} must be a finite non-negative value")
        if not self.run_ids:
            raise ValueError("run_ids must not be empty")
        if not self.artifact_paths:
            raise ValueError("artifact_paths must not be empty")
        ensure_repo_relative_mapping(self.artifact_paths, field_name="artifact_paths")
        if any(not value for value in self.notes):
            raise ValueError("notes must contain only non-empty strings")
        return self


class PicaFrozenSliceSearchTable(SixBirdsModel):
    table_format_version: str
    search_id: str
    row_count: int
    rows: list[PicaFrozenSliceSearchRow]
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_table(self) -> "PicaFrozenSliceSearchTable":
        if self.table_format_version != "pica-frozen-slice-search-results.v1":
            raise ValueError(
                "table_format_version must equal 'pica-frozen-slice-search-results.v1'"
            )
        if not self.search_id:
            raise ValueError("search_id must be a non-empty string")
        if self.row_count != len(self.rows):
            raise ValueError("row_count must equal len(rows)")
        duplicates = collect_list_duplicates([row.point_id for row in self.rows])
        if duplicates:
            raise ValueError(
                f"pica frozen-slice rows must be unique by point_id: {', '.join(duplicates)}"
            )
        if any(row.search_id != self.search_id for row in self.rows):
            raise ValueError("all rows must share the table search_id")
        ensure_metadata_shape(self.metadata)
        return self


class PicaPackagingConflictAdequacyFloor(SixBirdsModel):
    min_total_point_count: int = 3
    min_admissible_built_package_count: int = 2
    min_points_with_proper_coarse_events: int = 2
    min_points_with_package_conflict_same_slice_proper_coarse_structural_proposals: int = 1
    min_points_with_non_nested_same_slice_package_conflict_pairs: int = 1
    min_points_with_dual_mode_difference: int = 1
    min_points_with_nonzero_relevant_p5_commutator_support: int = 1
    min_median_accepted_proposal_support: float = 3.0

    @model_validator(mode="after")
    def validate_floor(self) -> "PicaPackagingConflictAdequacyFloor":
        for name in [
            "min_total_point_count",
            "min_admissible_built_package_count",
            "min_points_with_proper_coarse_events",
            "min_points_with_package_conflict_same_slice_proper_coarse_structural_proposals",
            "min_points_with_non_nested_same_slice_package_conflict_pairs",
            "min_points_with_dual_mode_difference",
            "min_points_with_nonzero_relevant_p5_commutator_support",
        ]:
            value = getattr(self, name)
            if isinstance(value, bool) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if (
            isinstance(self.min_median_accepted_proposal_support, bool)
            or not math.isfinite(self.min_median_accepted_proposal_support)
            or self.min_median_accepted_proposal_support < 0
        ):
            raise ValueError(
                "min_median_accepted_proposal_support must be a finite non-negative value"
            )
        return self


class PackagingConflictSearchPoint(SixBirdsModel):
    point_id: str
    pilot_config_artifact: str
    preparation_id: str
    protocol_id: str
    trajectories: int
    seed_list: list[int]
    projection_family_ids: list[str]
    selected_protocol_step_ids: list[str] = Field(default_factory=list)
    selected_step_indices: list[int] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_point(self) -> "PackagingConflictSearchPoint":
        if not self.point_id:
            raise ValueError("point_id must be a non-empty string")
        if not self.preparation_id:
            raise ValueError("preparation_id must be a non-empty string")
        if not self.protocol_id:
            raise ValueError("protocol_id must be a non-empty string")
        ensure_repo_relative_mapping(
            {"pilot_config_artifact": self.pilot_config_artifact},
            field_name="point_artifacts",
        )
        if isinstance(self.trajectories, bool) or self.trajectories <= 0:
            raise ValueError("trajectories must be a positive integer")
        if not self.seed_list:
            raise ValueError("seed_list must not be empty")
        seed_duplicates = collect_list_duplicates(
            [str(seed) for seed in self.seed_list]
        )
        if seed_duplicates:
            raise ValueError(f"seed_list must be unique: {', '.join(seed_duplicates)}")
        if any(isinstance(seed, bool) for seed in self.seed_list):
            raise ValueError("seed_list must contain only integers")
        if not self.projection_family_ids:
            raise ValueError("projection_family_ids must not be empty")
        projection_duplicates = collect_list_duplicates(self.projection_family_ids)
        if projection_duplicates:
            raise ValueError(
                f"projection_family_ids must be unique: {', '.join(projection_duplicates)}"
            )
        step_duplicates = collect_list_duplicates(self.selected_protocol_step_ids)
        if step_duplicates:
            raise ValueError(
                f"selected_protocol_step_ids must be unique: {', '.join(step_duplicates)}"
            )
        if any(not value for value in self.selected_protocol_step_ids):
            raise ValueError(
                "selected_protocol_step_ids must contain only non-empty strings"
            )
        index_duplicates = collect_list_duplicates(
            [str(value) for value in self.selected_step_indices]
        )
        if index_duplicates:
            raise ValueError(
                f"selected_step_indices must be unique: {', '.join(index_duplicates)}"
            )
        if any(
            isinstance(value, bool) or value < 0 for value in self.selected_step_indices
        ):
            raise ValueError("selected_step_indices must contain non-negative integers")
        if any(not value for value in self.notes):
            raise ValueError("notes must contain only non-empty strings")
        return self


class PicaPackagingConflictSearch(SixBirdsModel):
    search_format_version: str
    search_id: str
    points: list[PackagingConflictSearchPoint]
    projection_families: list[FrozenSliceProjectionFamily]
    source_pair_policy: FrozenSliceSourcePairPolicy = Field(
        default_factory=FrozenSliceSourcePairPolicy
    )
    relevant_commutator_pairs: list[str] = Field(
        default_factory=lambda: ["[P1,P5]", "[P2,P5]", "[P4,P5]"]
    )
    commutator_admissibility_mode: CommutatorAdmissibilityMode = "p5_only"
    min_relevant_commutator_value: float = 1e-12
    event_generation_thresholds: DiscoveredEventGenerationThresholds
    shared_event_inference_thresholds: SharedEventInferenceThresholds
    provenance_required: bool = True
    candidate_classification_thresholds: TargetedCandidateClassificationThresholds
    adequacy_floor: PicaPackagingConflictAdequacyFloor
    output_category: str | None = None
    output_label: str | None = None
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_search(self) -> "PicaPackagingConflictSearch":
        if self.search_format_version != "pica-packaging-conflict-search.v1":
            raise ValueError(
                "search_format_version must equal 'pica-packaging-conflict-search.v1'"
            )
        if not self.search_id:
            raise ValueError("search_id must be a non-empty string")
        if not self.points:
            raise ValueError("points must not be empty")
        point_duplicates = collect_list_duplicates(
            [point.point_id for point in self.points]
        )
        if point_duplicates:
            raise ValueError(
                f"point_id values must be unique: {', '.join(point_duplicates)}"
            )
        if not self.projection_families:
            raise ValueError("projection_families must not be empty")
        family_duplicates = collect_list_duplicates(
            [family.projection_id for family in self.projection_families]
        )
        if family_duplicates:
            raise ValueError(
                f"projection_families must be unique by projection_id: {', '.join(family_duplicates)}"
            )
        family_ids = {family.projection_id for family in self.projection_families}
        primary_ids = {
            family.projection_id
            for family in self.projection_families
            if "primary_context" in family.allowed_roles
            and family.projection_kind in {"packaging_outcome", "derived_row_outcome"}
        }
        for point in self.points:
            unknown = sorted(set(point.projection_family_ids) - family_ids)
            if unknown:
                raise ValueError(
                    f"point {point.point_id} references unknown projection families: {', '.join(unknown)}"
                )
            if not set(point.projection_family_ids) & primary_ids:
                raise ValueError(
                    f"point {point.point_id} must reference at least one primary-admissible projection family"
                )
        if not self.relevant_commutator_pairs:
            raise ValueError("relevant_commutator_pairs must not be empty")
        pair_duplicates = collect_list_duplicates(self.relevant_commutator_pairs)
        if pair_duplicates:
            raise ValueError(
                f"relevant_commutator_pairs must be unique: {', '.join(pair_duplicates)}"
            )
        if any(not pair for pair in self.relevant_commutator_pairs):
            raise ValueError(
                "relevant_commutator_pairs must contain only non-empty strings"
            )
        if self.commutator_admissibility_mode not in {"p5_only", "p5_p6_combined"}:
            raise ValueError(
                "commutator_admissibility_mode must be p5_only or p5_p6_combined"
            )
        if (
            isinstance(self.min_relevant_commutator_value, bool)
            or not math.isfinite(self.min_relevant_commutator_value)
            or self.min_relevant_commutator_value < 0
        ):
            raise ValueError(
                "min_relevant_commutator_value must be a finite non-negative value"
            )
        if self.output_category is not None and not self.output_category:
            raise ValueError("output_category must be non-empty when present")
        if self.output_label is not None and not self.output_label:
            raise ValueError("output_label must be non-empty when present")
        ensure_metadata_shape(self.metadata)
        return self


class PackagingConflictSearchRow(SixBirdsModel):
    row_format_version: str
    search_id: str
    point_id: str
    source_pica_campaign_config_path: str
    projection_family_ids: list[str]
    preparation_id: str
    protocol_id: str
    selected_protocol_step_ids: list[str]
    selected_step_indices: list[int]
    trajectories: int
    seed_list: list[int]
    produced_export_bundle_path: str
    discovered_context_family_path: str
    event_package_path: str | None = None
    provenance_classification: AdmissibilityClassification | None = None
    accepted_context_count: int
    accepted_proper_coarse_event_count: int
    accepted_shared_event_proposal_count: int
    accepted_proper_coarse_structural_proposal_count: int
    accepted_package_conflict_same_slice_proper_coarse_proposal_count: int
    accepted_non_nested_package_conflict_proposal_count: int
    equal_context_pair_count: int
    left_refines_right_count: int
    right_refines_left_count: int
    incomparable_context_pair_count: int
    disjoint_or_unaligned_context_pair_count: int
    same_slice_non_nested_context_pair_count: int
    primary_identity_admissible_pair_count: int
    packaging_conflict_admissible_pair_count: int
    same_slice_non_nested_packaging_conflict_pair_count: int
    nonzero_relevant_p5_commutator_support_count: int
    median_accepted_proposal_support: float | None = None
    baseline_hard_only: TargetedSearchEvaluation
    all_accepted_proposals: TargetedSearchEvaluation
    ccd_status: AtlasStatus
    ccd_overall: float | None = None
    sec_status: AtlasStatus
    sec_mean: float | None = None
    rm_status: AtlasStatus
    rm_overall: float | None = None
    candidate_classification: TargetedCandidateLabel
    run_ids: dict[str, str]
    artifact_paths: dict[str, str]
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_row(self) -> "PackagingConflictSearchRow":
        if self.row_format_version != "packaging-conflict-search-row.v1":
            raise ValueError(
                "row_format_version must equal 'packaging-conflict-search-row.v1'"
            )
        for name in [
            "search_id",
            "point_id",
            "source_pica_campaign_config_path",
            "preparation_id",
            "protocol_id",
            "produced_export_bundle_path",
            "discovered_context_family_path",
        ]:
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise ValueError(f"{name} must be a non-empty string")
        ensure_repo_relative_mapping(
            {
                "source_pica_campaign_config_path": self.source_pica_campaign_config_path,
                "produced_export_bundle_path": self.produced_export_bundle_path,
                "discovered_context_family_path": self.discovered_context_family_path,
            },
            field_name="row_artifacts",
        )
        if self.event_package_path is not None and not is_repo_relative_path(
            self.event_package_path
        ):
            raise ValueError(
                "event_package_path must be a normalized repo-relative path when present"
            )
        if not self.projection_family_ids:
            raise ValueError("projection_family_ids must not be empty")
        if not self.selected_protocol_step_ids:
            raise ValueError("selected_protocol_step_ids must not be empty")
        if not self.selected_step_indices:
            raise ValueError("selected_step_indices must not be empty")
        if isinstance(self.trajectories, bool) or self.trajectories <= 0:
            raise ValueError("trajectories must be a positive integer")
        if not self.seed_list:
            raise ValueError("seed_list must not be empty")
        for name in [
            "accepted_context_count",
            "accepted_proper_coarse_event_count",
            "accepted_shared_event_proposal_count",
            "accepted_proper_coarse_structural_proposal_count",
            "accepted_package_conflict_same_slice_proper_coarse_proposal_count",
            "accepted_non_nested_package_conflict_proposal_count",
            "equal_context_pair_count",
            "left_refines_right_count",
            "right_refines_left_count",
            "incomparable_context_pair_count",
            "disjoint_or_unaligned_context_pair_count",
            "same_slice_non_nested_context_pair_count",
            "primary_identity_admissible_pair_count",
            "packaging_conflict_admissible_pair_count",
            "same_slice_non_nested_packaging_conflict_pair_count",
            "nonzero_relevant_p5_commutator_support_count",
        ]:
            value = getattr(self, name)
            if isinstance(value, bool) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if self.median_accepted_proposal_support is not None and (
            isinstance(self.median_accepted_proposal_support, bool)
            or not math.isfinite(self.median_accepted_proposal_support)
            or self.median_accepted_proposal_support < 0
        ):
            raise ValueError(
                "median_accepted_proposal_support must be a finite non-negative value when present"
            )
        for status_name, value_name in [
            ("ccd_status", "ccd_overall"),
            ("sec_status", "sec_mean"),
            ("rm_status", "rm_overall"),
        ]:
            status = getattr(self, status_name)
            value = getattr(self, value_name)
            if status in {"scored", "solved"}:
                if value is None:
                    raise ValueError(
                        f"{value_name} must be present when {status_name} is {status}"
                    )
            elif value is not None:
                raise ValueError(
                    f"{value_name} must be null unless {status_name} is scored"
                )
        for name in ["ccd_overall", "sec_mean", "rm_overall"]:
            value = getattr(self, name)
            if value is not None and (
                isinstance(value, bool) or not math.isfinite(value) or value < 0
            ):
                raise ValueError(f"{name} must be a finite non-negative value")
        if not self.run_ids:
            raise ValueError("run_ids must not be empty")
        if not self.artifact_paths:
            raise ValueError("artifact_paths must not be empty")
        ensure_repo_relative_mapping(self.artifact_paths, field_name="artifact_paths")
        if any(not value for value in self.notes):
            raise ValueError("notes must contain only non-empty strings")
        return self


class PackagingConflictModeResult(SixBirdsModel):
    commutator_admissibility_mode: CommutatorAdmissibilityMode
    relevant_commutator_pairs: list[str]
    accepted_shared_event_proposal_count: int
    accepted_proper_coarse_structural_proposal_count: int
    accepted_package_conflict_same_slice_proper_coarse_proposal_count: int
    accepted_non_nested_package_conflict_proposal_count: int
    packaging_conflict_admissible_pair_count: int
    same_slice_non_nested_packaging_conflict_pair_count: int
    nonzero_relevant_commutator_support_count: int
    median_accepted_proposal_support: float | None = None
    support_relation_kind_counts: dict[str, int] = Field(default_factory=dict)
    baseline_hard_only: TargetedSearchEvaluation
    all_accepted_proposals: TargetedSearchEvaluation
    candidate_classification: TargetedCandidateLabel
    artifact_paths: dict[str, str]

    @model_validator(mode="after")
    def validate_mode(self) -> "PackagingConflictModeResult":
        if not self.relevant_commutator_pairs:
            raise ValueError("relevant_commutator_pairs must not be empty")
        pair_duplicates = collect_list_duplicates(self.relevant_commutator_pairs)
        if pair_duplicates:
            raise ValueError(
                f"relevant_commutator_pairs must be unique: {', '.join(pair_duplicates)}"
            )
        for name in [
            "accepted_shared_event_proposal_count",
            "accepted_proper_coarse_structural_proposal_count",
            "accepted_package_conflict_same_slice_proper_coarse_proposal_count",
            "accepted_non_nested_package_conflict_proposal_count",
            "packaging_conflict_admissible_pair_count",
            "same_slice_non_nested_packaging_conflict_pair_count",
            "nonzero_relevant_commutator_support_count",
        ]:
            value = getattr(self, name)
            if isinstance(value, bool) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if self.median_accepted_proposal_support is not None and (
            isinstance(self.median_accepted_proposal_support, bool)
            or not math.isfinite(self.median_accepted_proposal_support)
            or self.median_accepted_proposal_support < 0
        ):
            raise ValueError(
                "median_accepted_proposal_support must be a finite non-negative value when present"
            )
        for key, value in self.support_relation_kind_counts.items():
            if not key:
                raise ValueError(
                    "support_relation_kind_counts keys must be non-empty strings"
                )
            if isinstance(value, bool) or value < 0:
                raise ValueError(
                    "support_relation_kind_counts values must be non-negative integers"
                )
        if not self.artifact_paths:
            raise ValueError("artifact_paths must not be empty")
        ensure_repo_relative_mapping(self.artifact_paths, field_name="artifact_paths")
        return self


class PackagingConflictComparisonRow(SixBirdsModel):
    row_format_version: str
    search_id: str
    point_id: str
    source_pica_campaign_config_path: str
    projection_family_ids: list[str]
    preparation_id: str
    protocol_id: str
    selected_protocol_step_ids: list[str]
    selected_step_indices: list[int]
    trajectories: int
    seed_list: list[int]
    produced_export_bundle_path: str
    discovered_context_family_path: str
    event_package_path: str | None = None
    provenance_classification: AdmissibilityClassification | None = None
    accepted_context_count: int
    accepted_proper_coarse_event_count: int
    equal_context_pair_count: int
    left_refines_right_count: int
    right_refines_left_count: int
    incomparable_context_pair_count: int
    disjoint_or_unaligned_context_pair_count: int
    same_slice_non_nested_context_pair_count: int
    primary_identity_admissible_pair_count: int
    p5_only: PackagingConflictModeResult
    p5_p6_combined: PackagingConflictModeResult
    run_ids: dict[str, str]
    artifact_paths: dict[str, str]
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_row(self) -> "PackagingConflictComparisonRow":
        if self.row_format_version != "packaging-conflict-comparison-row.v1":
            raise ValueError(
                "row_format_version must equal 'packaging-conflict-comparison-row.v1'"
            )
        for name in [
            "search_id",
            "point_id",
            "source_pica_campaign_config_path",
            "preparation_id",
            "protocol_id",
            "produced_export_bundle_path",
            "discovered_context_family_path",
        ]:
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise ValueError(f"{name} must be a non-empty string")
        ensure_repo_relative_mapping(
            {
                "source_pica_campaign_config_path": self.source_pica_campaign_config_path,
                "produced_export_bundle_path": self.produced_export_bundle_path,
                "discovered_context_family_path": self.discovered_context_family_path,
            },
            field_name="row_artifacts",
        )
        if self.event_package_path is not None and not is_repo_relative_path(
            self.event_package_path
        ):
            raise ValueError(
                "event_package_path must be a normalized repo-relative path when present"
            )
        if not self.projection_family_ids:
            raise ValueError("projection_family_ids must not be empty")
        if not self.selected_protocol_step_ids:
            raise ValueError("selected_protocol_step_ids must not be empty")
        if not self.selected_step_indices:
            raise ValueError("selected_step_indices must not be empty")
        if isinstance(self.trajectories, bool) or self.trajectories <= 0:
            raise ValueError("trajectories must be a positive integer")
        if not self.seed_list:
            raise ValueError("seed_list must not be empty")
        for name in [
            "accepted_context_count",
            "accepted_proper_coarse_event_count",
            "equal_context_pair_count",
            "left_refines_right_count",
            "right_refines_left_count",
            "incomparable_context_pair_count",
            "disjoint_or_unaligned_context_pair_count",
            "same_slice_non_nested_context_pair_count",
            "primary_identity_admissible_pair_count",
        ]:
            value = getattr(self, name)
            if isinstance(value, bool) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if not self.run_ids:
            raise ValueError("run_ids must not be empty")
        if not self.artifact_paths:
            raise ValueError("artifact_paths must not be empty")
        ensure_repo_relative_mapping(self.artifact_paths, field_name="artifact_paths")
        if any(not value for value in self.notes):
            raise ValueError("notes must contain only non-empty strings")
        return self


class PackagingConflictComparisonTable(SixBirdsModel):
    table_format_version: str
    search_id: str
    row_count: int
    rows: list[PackagingConflictComparisonRow]
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_table(self) -> "PackagingConflictComparisonTable":
        if self.table_format_version != "packaging-conflict-comparison-results.v1":
            raise ValueError(
                "table_format_version must equal 'packaging-conflict-comparison-results.v1'"
            )
        if not self.search_id:
            raise ValueError("search_id must be a non-empty string")
        if self.row_count != len(self.rows):
            raise ValueError("row_count must equal len(rows)")
        duplicates = collect_list_duplicates([row.point_id for row in self.rows])
        if duplicates:
            raise ValueError(
                f"packaging-conflict rows must be unique by point_id: {', '.join(duplicates)}"
            )
        if any(row.search_id != self.search_id for row in self.rows):
            raise ValueError("all rows must share the table search_id")
        ensure_metadata_shape(self.metadata)
        return self


class MechanismAxisSearchPoint(SixBirdsModel):
    point_id: str
    pilot_config_artifact: str
    preparation_id: str
    protocol_id: str
    trajectories: int
    seed_list: list[int]
    quotient_feasibility_audit_artifact: str | None = None
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_point(self) -> "MechanismAxisSearchPoint":
        for name in [
            "point_id",
            "pilot_config_artifact",
            "preparation_id",
            "protocol_id",
        ]:
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise ValueError(f"{name} must be a non-empty string")
        ensure_repo_relative_mapping(
            {"pilot_config_artifact": self.pilot_config_artifact},
            field_name="pilot_config_artifact",
        )
        if self.quotient_feasibility_audit_artifact is not None:
            ensure_repo_relative_mapping(
                {
                    "quotient_feasibility_audit_artifact": self.quotient_feasibility_audit_artifact
                },
                field_name="quotient_feasibility_audit_artifact",
            )
        if isinstance(self.trajectories, bool) or self.trajectories <= 0:
            raise ValueError("trajectories must be a positive integer")
        if not self.seed_list:
            raise ValueError("seed_list must not be empty")
        duplicates = collect_list_duplicates([str(seed) for seed in self.seed_list])
        if duplicates:
            raise ValueError(f"seed_list must be unique: {', '.join(duplicates)}")
        if any(isinstance(seed, bool) for seed in self.seed_list):
            raise ValueError("seed_list must contain integers")
        if any(not note for note in self.notes):
            raise ValueError("notes must contain only non-empty strings")
        return self


class MechanismAxisAdequacyFloor(SixBirdsModel):
    min_total_point_count: int = 4
    min_admissible_built_package_count: int = 2
    min_points_with_proper_coarse_events: int = 1
    min_points_with_changed_packaging_surface_relative_to_control: int = 1
    min_points_with_dual_mode_difference: int = 1

    @model_validator(mode="after")
    def validate_floor(self) -> "MechanismAxisAdequacyFloor":
        for name in [
            "min_total_point_count",
            "min_admissible_built_package_count",
            "min_points_with_proper_coarse_events",
            "min_points_with_changed_packaging_surface_relative_to_control",
            "min_points_with_dual_mode_difference",
        ]:
            value = getattr(self, name)
            if isinstance(value, bool) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        return self


class MechanismAxisSearch(SixBirdsModel):
    search_format_version: str
    search_id: str
    points: list[MechanismAxisSearchPoint]
    projection_families: list[FrozenSliceProjectionFamily]
    active_projection_family_ids: list[str]
    selected_protocol_step_ids: list[str]
    selected_step_indices: list[int]
    fixed_lens_family_label: str
    fixed_packaging_policy_label: str
    event_generation_thresholds: DiscoveredEventGenerationThresholds
    shared_event_inference_thresholds: SharedEventInferenceThresholds
    candidate_classification_thresholds: TargetedCandidateClassificationThresholds
    adequacy_floor: MechanismAxisAdequacyFloor
    claim_ceiling: MechanismAxisClaimLevel = "package_conflict_tension"
    output_category: str = "search"
    output_label: str | None = None
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_search(self) -> "MechanismAxisSearch":
        if self.search_format_version != "mechanism-axis-search.v1":
            raise ValueError(
                "search_format_version must equal 'mechanism-axis-search.v1'"
            )
        if not self.search_id:
            raise ValueError("search_id must be a non-empty string")
        if not self.points:
            raise ValueError("points must not be empty")
        point_duplicates = collect_list_duplicates(
            [point.point_id for point in self.points]
        )
        if point_duplicates:
            raise ValueError(
                f"points must be unique by point_id: {', '.join(point_duplicates)}"
            )
        projection_map = {
            family.projection_id: family for family in self.projection_families
        }
        if not self.projection_families:
            raise ValueError("projection_families must not be empty")
        if not self.active_projection_family_ids:
            raise ValueError("active_projection_family_ids must not be empty")
        for projection_id in self.active_projection_family_ids:
            if projection_id not in projection_map:
                raise ValueError(
                    f"active_projection_family_ids includes unknown projection_id '{projection_id}'"
                )
        if not self.selected_protocol_step_ids:
            raise ValueError("selected_protocol_step_ids must not be empty")
        if not self.selected_step_indices:
            raise ValueError("selected_step_indices must not be empty")
        if not self.fixed_lens_family_label:
            raise ValueError("fixed_lens_family_label must be a non-empty string")
        if not self.fixed_packaging_policy_label:
            raise ValueError("fixed_packaging_policy_label must be a non-empty string")
        ensure_metadata_shape(self.metadata)
        return self


class MechanismAxisRow(SixBirdsModel):
    row_format_version: str
    search_id: str
    point_id: str
    axis: Literal["mechanism"] = "mechanism"
    source_pica_campaign_config_path: str
    produced_export_bundle_path: str
    packaging_surface_summary_path: str
    discovered_context_family_path: str
    event_package_path: str | None = None
    provenance_classification: AdmissibilityClassification | None = None
    accepted_context_count: int
    accepted_singleton_event_count: int
    accepted_proper_coarse_event_count: int
    accepted_shared_event_proposal_count: int
    accepted_proper_coarse_proposal_count: int
    baseline_hard_only: TargetedSearchEvaluation
    all_accepted_proposals: TargetedSearchEvaluation
    selected_packaging_sources: list[str]
    selected_packaging_operator_count: int
    selected_packaging_family_count: int
    packaging_support_slice_count: int
    changed_packaging_surface_relative_to_control: bool
    quotient_class_count: int | None = None
    quotient_accepted_only_survivor_count: int | None = None
    quotient_natural_pairing_survivor_count: int | None = None
    quotient_candidate_subset_witness_found: bool | None = None
    quotient_witness_classification: (
        MechanismAxisQuotientWitnessClassification | None
    ) = None
    quotient_witness_candidate_ids: list[str] = Field(default_factory=list)
    quotient_feasibility_summary_path: str | None = None
    candidate_classification: TargetedCandidateLabel
    claim_level_supported: MechanismAxisClaimLevel
    mechanism_signal_kind: MechanismSignalKind
    run_ids: dict[str, str]
    artifact_paths: dict[str, str]
    notes: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_row(self) -> "MechanismAxisRow":
        if self.row_format_version != "mechanism-axis-row.v1":
            raise ValueError("row_format_version must equal 'mechanism-axis-row.v1'")
        for name in [
            "search_id",
            "point_id",
            "source_pica_campaign_config_path",
            "produced_export_bundle_path",
            "packaging_surface_summary_path",
            "discovered_context_family_path",
        ]:
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise ValueError(f"{name} must be a non-empty string")
        ensure_repo_relative_mapping(
            {
                "source_pica_campaign_config_path": self.source_pica_campaign_config_path,
                "produced_export_bundle_path": self.produced_export_bundle_path,
                "packaging_surface_summary_path": self.packaging_surface_summary_path,
                "discovered_context_family_path": self.discovered_context_family_path,
            },
            field_name="mechanism_axis_artifacts",
        )
        if self.event_package_path is not None and not is_repo_relative_path(
            self.event_package_path
        ):
            raise ValueError(
                "event_package_path must be a normalized repo-relative path when present"
            )
        for name in [
            "accepted_context_count",
            "accepted_singleton_event_count",
            "accepted_proper_coarse_event_count",
            "accepted_shared_event_proposal_count",
            "accepted_proper_coarse_proposal_count",
            "selected_packaging_operator_count",
            "selected_packaging_family_count",
            "packaging_support_slice_count",
        ]:
            value = getattr(self, name)
            if isinstance(value, bool) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        for name in [
            "quotient_class_count",
            "quotient_accepted_only_survivor_count",
            "quotient_natural_pairing_survivor_count",
        ]:
            value = getattr(self, name)
            if value is not None and (isinstance(value, bool) or value < 0):
                raise ValueError(f"{name} must be a non-negative integer when present")
        duplicates = collect_list_duplicates(self.selected_packaging_sources)
        if duplicates:
            raise ValueError(
                f"selected_packaging_sources must be unique: {', '.join(duplicates)}"
            )
        if any(not value for value in self.selected_packaging_sources):
            raise ValueError(
                "selected_packaging_sources must contain only non-empty strings"
            )
        if not self.run_ids:
            raise ValueError("run_ids must not be empty")
        if not self.artifact_paths:
            raise ValueError("artifact_paths must not be empty")
        ensure_repo_relative_mapping(self.artifact_paths, field_name="artifact_paths")
        duplicates = collect_list_duplicates(self.quotient_witness_candidate_ids)
        if duplicates:
            raise ValueError(
                "quotient_witness_candidate_ids must be unique: "
                + ", ".join(duplicates)
            )
        if any(not value for value in self.quotient_witness_candidate_ids):
            raise ValueError(
                "quotient_witness_candidate_ids must contain only non-empty strings"
            )
        if (
            self.quotient_feasibility_summary_path is not None
            and not is_repo_relative_path(self.quotient_feasibility_summary_path)
        ):
            raise ValueError(
                "quotient_feasibility_summary_path must be a normalized repo-relative path when present"
            )
        if any(not value for value in self.notes + self.flags):
            raise ValueError("notes and flags must contain only non-empty strings")
        return self


class MechanismAxisTable(SixBirdsModel):
    table_format_version: str
    search_id: str
    row_count: int
    rows: list[MechanismAxisRow]
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_table(self) -> "MechanismAxisTable":
        if self.table_format_version != "mechanism-axis-results.v1":
            raise ValueError(
                "table_format_version must equal 'mechanism-axis-results.v1'"
            )
        if not self.search_id:
            raise ValueError("search_id must be a non-empty string")
        if self.row_count != len(self.rows):
            raise ValueError("row_count must equal len(rows)")
        duplicates = collect_list_duplicates([row.point_id for row in self.rows])
        if duplicates:
            raise ValueError(
                f"mechanism-axis rows must be unique by point_id: {', '.join(duplicates)}"
            )
        if any(row.search_id != self.search_id for row in self.rows):
            raise ValueError("all rows must share the table search_id")
        ensure_metadata_shape(self.metadata)
        return self


class LensFamilyAdmissibilityRow(SixBirdsModel):
    projection_id: str
    source_field: str
    projection_kind: ProjectionFamilyKind
    same_slice_eligible: bool
    allowed_roles: list[ProjectionFamilyRole]
    allowed_role: ProjectionFamilyRole
    notes: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_row(self) -> "LensFamilyAdmissibilityRow":
        for name in ["projection_id", "source_field"]:
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise ValueError(f"{name} must be a non-empty string")
        if not self.allowed_roles:
            raise ValueError("allowed_roles must not be empty")
        duplicates = collect_list_duplicates(self.allowed_roles)
        if duplicates:
            raise ValueError(f"allowed_roles must be unique: {', '.join(duplicates)}")
        if self.allowed_role not in self.allowed_roles:
            raise ValueError("allowed_role must be included in allowed_roles")
        if any(not value for value in self.notes + self.flags):
            raise ValueError("notes and flags must contain only non-empty strings")
        return self


class LensFamilyAdmissibility(SixBirdsModel):
    catalog_format_version: str
    search_id: str
    axis: Literal["lens"] = "lens"
    fixed_mechanism_label: str
    fixed_packaging_family_label: str
    row_count: int
    rows: list[LensFamilyAdmissibilityRow]
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_catalog(self) -> "LensFamilyAdmissibility":
        if self.catalog_format_version != "lens-family-admissibility.v1":
            raise ValueError(
                "catalog_format_version must equal 'lens-family-admissibility.v1'"
            )
        for name in [
            "search_id",
            "fixed_mechanism_label",
            "fixed_packaging_family_label",
        ]:
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise ValueError(f"{name} must be a non-empty string")
        if self.row_count != len(self.rows):
            raise ValueError("row_count must equal len(rows)")
        duplicates = collect_list_duplicates([row.projection_id for row in self.rows])
        if duplicates:
            raise ValueError(
                f"lens-family admissibility rows must be unique by projection_id: {', '.join(duplicates)}"
            )
        ensure_metadata_shape(self.metadata)
        return self


class LensAxisSearchPoint(SixBirdsModel):
    point_id: str
    projection_family_ids: list[str]
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_point(self) -> "LensAxisSearchPoint":
        if not self.point_id:
            raise ValueError("point_id must be a non-empty string")
        if not self.projection_family_ids:
            raise ValueError("projection_family_ids must not be empty")
        duplicates = collect_list_duplicates(self.projection_family_ids)
        if duplicates:
            raise ValueError(
                f"projection_family_ids must be unique: {', '.join(duplicates)}"
            )
        if any(not value for value in self.projection_family_ids):
            raise ValueError(
                "projection_family_ids must contain only non-empty strings"
            )
        if any(not note for note in self.notes):
            raise ValueError("notes must contain only non-empty strings")
        return self


class LensAxisAdequacyFloor(SixBirdsModel):
    min_total_point_count: int = 3
    min_admissible_built_package_count: int = 2
    min_points_with_proper_coarse_events: int = 1
    min_points_with_accepted_proper_coarse_structural_proposals: int = 1
    min_points_with_same_slice_non_nested_lens_pairs: int = 1
    min_points_with_dual_mode_difference: int = 1
    min_points_with_nontrivial_quotient_result_recorded: int = 1

    @model_validator(mode="after")
    def validate_floor(self) -> "LensAxisAdequacyFloor":
        for name in [
            "min_total_point_count",
            "min_admissible_built_package_count",
            "min_points_with_proper_coarse_events",
            "min_points_with_accepted_proper_coarse_structural_proposals",
            "min_points_with_same_slice_non_nested_lens_pairs",
            "min_points_with_dual_mode_difference",
            "min_points_with_nontrivial_quotient_result_recorded",
        ]:
            value = getattr(self, name)
            if isinstance(value, bool) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        return self


class LensAxisSearch(SixBirdsModel):
    search_format_version: str
    search_id: str
    fixed_pilot_config_artifact: str
    preparation_id: str
    protocol_id: str
    trajectories: int
    seed_list: list[int]
    points: list[LensAxisSearchPoint]
    projection_families: list[FrozenSliceProjectionFamily]
    selected_protocol_step_ids: list[str]
    selected_step_indices: list[int]
    selected_resolution_ids: list[str]
    fixed_mechanism_label: str
    fixed_packaging_family_label: str
    event_generation_thresholds: DiscoveredEventGenerationThresholds
    shared_event_inference_thresholds: SharedEventInferenceThresholds
    candidate_classification_thresholds: TargetedCandidateClassificationThresholds
    adequacy_floor: LensAxisAdequacyFloor
    allow_cross_resolution_pairs: bool = False
    include_natural_pairing_control: bool = True
    quotient_subset_search_enabled: bool = True
    quotient_max_subset_size: int = 2
    quotient_stop_at_first_witness: bool = True
    provenance_required: bool = True
    claim_ceiling: LensAxisClaimLevel = "provenance_admissible_strong_obstruction"
    output_category: str = "search"
    output_label: str | None = None
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_search(self) -> "LensAxisSearch":
        if self.search_format_version != "lens-axis-search.v1":
            raise ValueError("search_format_version must equal 'lens-axis-search.v1'")
        for name in [
            "search_id",
            "fixed_pilot_config_artifact",
            "preparation_id",
            "protocol_id",
            "fixed_mechanism_label",
            "fixed_packaging_family_label",
        ]:
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise ValueError(f"{name} must be a non-empty string")
        ensure_repo_relative_mapping(
            {"fixed_pilot_config_artifact": self.fixed_pilot_config_artifact},
            field_name="fixed_pilot_config_artifact",
        )
        if isinstance(self.trajectories, bool) or self.trajectories <= 0:
            raise ValueError("trajectories must be a positive integer")
        if not self.seed_list:
            raise ValueError("seed_list must not be empty")
        duplicates = collect_list_duplicates([str(seed) for seed in self.seed_list])
        if duplicates:
            raise ValueError(f"seed_list must be unique: {', '.join(duplicates)}")
        if any(isinstance(seed, bool) for seed in self.seed_list):
            raise ValueError("seed_list must contain integers")
        if not self.points:
            raise ValueError("points must not be empty")
        duplicates = collect_list_duplicates([point.point_id for point in self.points])
        if duplicates:
            raise ValueError(
                f"points must be unique by point_id: {', '.join(duplicates)}"
            )
        if not self.projection_families:
            raise ValueError("projection_families must not be empty")
        projection_map = {
            family.projection_id: family for family in self.projection_families
        }
        for point in self.points:
            for projection_id in point.projection_family_ids:
                if projection_id not in projection_map:
                    raise ValueError(
                        f"point '{point.point_id}' references unknown projection_id '{projection_id}'"
                    )
        if not self.selected_protocol_step_ids:
            raise ValueError("selected_protocol_step_ids must not be empty")
        if not self.selected_step_indices:
            raise ValueError("selected_step_indices must not be empty")
        if not self.selected_resolution_ids:
            raise ValueError("selected_resolution_ids must not be empty")
        if (
            isinstance(self.quotient_max_subset_size, bool)
            or self.quotient_max_subset_size <= 0
        ):
            raise ValueError("quotient_max_subset_size must be a positive integer")
        ensure_metadata_shape(self.metadata)
        return self


class LensAxisRow(SixBirdsModel):
    row_format_version: str
    search_id: str
    point_id: str
    axis: Literal["lens"] = "lens"
    source_pica_campaign_config_path: str
    produced_export_bundle_path: str
    packaging_surface_summary_path: str
    discovered_context_family_path: str
    event_package_path: str | None = None
    provenance_classification: AdmissibilityClassification | None = None
    fixed_mechanism_label: str
    fixed_packaging_family_label: str
    lens_projection_family_ids: list[str]
    accepted_context_count: int
    accepted_singleton_event_count: int
    accepted_proper_coarse_event_count: int
    accepted_shared_event_proposal_count: int
    accepted_proper_coarse_proposal_count: int
    accepted_lens_diverse_proper_coarse_proposal_count: int
    same_slice_non_nested_lens_pair_count: int
    baseline_hard_only: TargetedSearchEvaluation
    all_accepted_proposals: TargetedSearchEvaluation
    quotient_class_count: int | None = None
    quotient_accepted_only_survivor_count: int | None = None
    quotient_accepted_only_exact_feasible: bool | None = None
    quotient_accepted_only_failure_reason: str | None = None
    quotient_natural_pairing_survivor_count: int | None = None
    quotient_natural_pairing_exact_feasible: bool | None = None
    quotient_candidate_subset_witness_found: bool | None = None
    quotient_candidate_subset_minimal_witness_size: int | None = None
    quotient_witness_status: LensAxisQuotientWitnessStatus | None = None
    quotient_witness_candidate_ids: list[str] = Field(default_factory=list)
    quotient_feasibility_summary_path: str | None = None
    selected_packaging_sources: list[str]
    selected_packaging_operator_count: int
    selected_packaging_family_count: int
    packaging_support_slice_count: int
    support_relation_kind_counts: dict[str, int] = Field(default_factory=dict)
    candidate_classification: TargetedCandidateLabel
    claim_level_supported: LensAxisClaimLevel
    run_ids: dict[str, str]
    artifact_paths: dict[str, str]
    notes: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_row(self) -> "LensAxisRow":
        if self.row_format_version != "lens-axis-row.v1":
            raise ValueError("row_format_version must equal 'lens-axis-row.v1'")
        for name in [
            "search_id",
            "point_id",
            "source_pica_campaign_config_path",
            "produced_export_bundle_path",
            "packaging_surface_summary_path",
            "discovered_context_family_path",
            "fixed_mechanism_label",
            "fixed_packaging_family_label",
        ]:
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise ValueError(f"{name} must be a non-empty string")
        ensure_repo_relative_mapping(
            {
                "source_pica_campaign_config_path": self.source_pica_campaign_config_path,
                "produced_export_bundle_path": self.produced_export_bundle_path,
                "packaging_surface_summary_path": self.packaging_surface_summary_path,
                "discovered_context_family_path": self.discovered_context_family_path,
            },
            field_name="lens_axis_artifacts",
        )
        if self.event_package_path is not None and not is_repo_relative_path(
            self.event_package_path
        ):
            raise ValueError(
                "event_package_path must be a normalized repo-relative path when present"
            )
        for name in [
            "accepted_context_count",
            "accepted_singleton_event_count",
            "accepted_proper_coarse_event_count",
            "accepted_shared_event_proposal_count",
            "accepted_proper_coarse_proposal_count",
            "accepted_lens_diverse_proper_coarse_proposal_count",
            "same_slice_non_nested_lens_pair_count",
            "selected_packaging_operator_count",
            "selected_packaging_family_count",
            "packaging_support_slice_count",
        ]:
            value = getattr(self, name)
            if isinstance(value, bool) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        for name in [
            "quotient_class_count",
            "quotient_accepted_only_survivor_count",
            "quotient_natural_pairing_survivor_count",
            "quotient_candidate_subset_minimal_witness_size",
        ]:
            value = getattr(self, name)
            if value is not None and (isinstance(value, bool) or value < 0):
                raise ValueError(f"{name} must be a non-negative integer when present")
        duplicates = collect_list_duplicates(self.lens_projection_family_ids)
        if duplicates:
            raise ValueError(
                f"lens_projection_family_ids must be unique: {', '.join(duplicates)}"
            )
        duplicates = collect_list_duplicates(self.selected_packaging_sources)
        if duplicates:
            raise ValueError(
                f"selected_packaging_sources must be unique: {', '.join(duplicates)}"
            )
        duplicates = collect_list_duplicates(self.quotient_witness_candidate_ids)
        if duplicates:
            raise ValueError(
                f"quotient_witness_candidate_ids must be unique: {', '.join(duplicates)}"
            )
        if (
            self.quotient_feasibility_summary_path is not None
            and not is_repo_relative_path(self.quotient_feasibility_summary_path)
        ):
            raise ValueError(
                "quotient_feasibility_summary_path must be a normalized repo-relative path when present"
            )
        if not self.run_ids:
            raise ValueError("run_ids must not be empty")
        if not self.artifact_paths:
            raise ValueError("artifact_paths must not be empty")
        ensure_repo_relative_mapping(self.artifact_paths, field_name="artifact_paths")
        for key, value in self.support_relation_kind_counts.items():
            if not key:
                raise ValueError(
                    "support_relation_kind_counts keys must be non-empty strings"
                )
            if isinstance(value, bool) or value < 0:
                raise ValueError(
                    "support_relation_kind_counts values must be non-negative integers"
                )
        if any(not value for value in self.notes + self.flags):
            raise ValueError("notes and flags must contain only non-empty strings")
        return self


class LensAxisTable(SixBirdsModel):
    table_format_version: str
    search_id: str
    row_count: int
    rows: list[LensAxisRow]
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_table(self) -> "LensAxisTable":
        if self.table_format_version != "lens-axis-results.v1":
            raise ValueError("table_format_version must equal 'lens-axis-results.v1'")
        if not self.search_id:
            raise ValueError("search_id must be a non-empty string")
        if self.row_count != len(self.rows):
            raise ValueError("row_count must equal len(rows)")
        duplicates = collect_list_duplicates([row.point_id for row in self.rows])
        if duplicates:
            raise ValueError(
                f"lens-axis rows must be unique by point_id: {', '.join(duplicates)}"
            )
        if any(row.search_id != self.search_id for row in self.rows):
            raise ValueError("all rows must share the table search_id")
        ensure_metadata_shape(self.metadata)
        return self


LensAxisCrossResolutionFinalAdjudication = Literal[
    "accepted_as_lens_axis_strict_extension",
    "rejected_as_out_of_contract",
]


class LensAxisCrossResolutionAdjudication(SixBirdsModel):
    adjudication_format_version: str
    witness_case_id: str
    source_discovered_context_family_artifact: str
    source_event_package_artifact: str
    source_package_provenance_artifact: str
    source_quotient_feasibility_audit_artifact: str
    source_lens_family_admissibility_artifact: str | None = None
    same_support_status: bool
    same_run_status: bool
    same_evaluation_regime_status: bool
    same_step_status: bool
    cross_resolution_status: bool
    theory_alignment_flags: list[str] = Field(default_factory=list)
    consulted_paper_refs: list[str] = Field(default_factory=list)
    final_adjudication: LensAxisCrossResolutionFinalAdjudication
    rationale_notes: list[str] = Field(default_factory=list)
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_adjudication(self) -> "LensAxisCrossResolutionAdjudication":
        if (
            self.adjudication_format_version
            != "lens-axis-cross-resolution-adjudication.v1"
        ):
            raise ValueError(
                "adjudication_format_version must equal "
                "'lens-axis-cross-resolution-adjudication.v1'"
            )
        for name in [
            "witness_case_id",
            "source_discovered_context_family_artifact",
            "source_event_package_artifact",
            "source_package_provenance_artifact",
            "source_quotient_feasibility_audit_artifact",
        ]:
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise ValueError(f"{name} must be a non-empty string")
        mapping = {
            "source_discovered_context_family_artifact": self.source_discovered_context_family_artifact,
            "source_event_package_artifact": self.source_event_package_artifact,
            "source_package_provenance_artifact": self.source_package_provenance_artifact,
            "source_quotient_feasibility_audit_artifact": self.source_quotient_feasibility_audit_artifact,
        }
        if self.source_lens_family_admissibility_artifact is not None:
            if not self.source_lens_family_admissibility_artifact:
                raise ValueError(
                    "source_lens_family_admissibility_artifact must be non-empty when present"
                )
            mapping["source_lens_family_admissibility_artifact"] = (
                self.source_lens_family_admissibility_artifact
            )
        ensure_repo_relative_mapping(
            mapping,
            field_name="lens_axis_cross_resolution_artifacts",
        )
        for name in [
            "theory_alignment_flags",
            "consulted_paper_refs",
            "rationale_notes",
        ]:
            values = getattr(self, name)
            duplicates = collect_list_duplicates(values)
            if duplicates:
                raise ValueError(f"{name} must be unique: {', '.join(duplicates)}")
            if any(not value for value in values):
                raise ValueError(f"{name} must contain only non-empty strings")
        if self.final_adjudication == "accepted_as_lens_axis_strict_extension":
            if not (
                self.same_support_status
                and self.same_run_status
                and self.same_evaluation_regime_status
                and self.cross_resolution_status
            ):
                raise ValueError(
                    "accepted_as_lens_axis_strict_extension requires same_support_status, "
                    "same_run_status, same_evaluation_regime_status, and "
                    "cross_resolution_status to all be true"
                )
            if self.same_step_status:
                raise ValueError(
                    "accepted_as_lens_axis_strict_extension requires same_step_status to be false"
                )
        ensure_metadata_shape(self.metadata)
        return self


class LensAxisFinalizationRegime(SixBirdsModel):
    regime_label: str
    varies: str
    fixed: str
    candidate_class: TargetedCandidateLabel
    quotient_witness_status: LensAxisQuotientWitnessStatus
    flagship_artifact: str
    control_artifact: str | None = None
    notes: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_regime(self) -> "LensAxisFinalizationRegime":
        for name in ["regime_label", "varies", "fixed", "flagship_artifact"]:
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise ValueError(f"{name} must be a non-empty string")
        mapping = {"flagship_artifact": self.flagship_artifact}
        if self.control_artifact is not None:
            if not self.control_artifact:
                raise ValueError("control_artifact must be non-empty when present")
            mapping["control_artifact"] = self.control_artifact
        ensure_repo_relative_mapping(
            mapping, field_name="lens_axis_finalization_regime"
        )
        duplicates = collect_list_duplicates(self.notes + self.flags)
        if duplicates:
            raise ValueError(
                f"notes/flags values must be unique within a regime: {', '.join(duplicates)}"
            )
        if any(not value for value in self.notes + self.flags):
            raise ValueError("notes and flags must contain only non-empty strings")
        return self


class LensAxisFinalizationConfig(SixBirdsModel):
    config_format_version: str
    lens_axis_id: str
    same_step_table_artifact: str
    same_step_negative_summary_artifact: str
    same_step_negative_outcome_artifact: str
    same_step_support_relation_artifact: str
    same_step_quotient_diagnostics_artifact: str
    same_step_flagship_point_id: str
    cross_resolution_search_config_artifact: str
    cross_resolution_package_build_summary_artifact: str
    cross_resolution_provenance_summary_artifact: str
    cross_resolution_quotient_summary_artifact: str
    canonical_flagship_case_id: str
    final_claim_level: LensAxisClaimLevel = "provenance_admissible_strong_obstruction"
    output_category: str = "results"
    output_label: str | None = None
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_config(self) -> "LensAxisFinalizationConfig":
        if self.config_format_version != "lens-axis-finalization.v1":
            raise ValueError(
                "config_format_version must equal 'lens-axis-finalization.v1'"
            )
        for name in [
            "lens_axis_id",
            "same_step_table_artifact",
            "same_step_negative_summary_artifact",
            "same_step_negative_outcome_artifact",
            "same_step_support_relation_artifact",
            "same_step_quotient_diagnostics_artifact",
            "same_step_flagship_point_id",
            "cross_resolution_search_config_artifact",
            "cross_resolution_package_build_summary_artifact",
            "cross_resolution_provenance_summary_artifact",
            "cross_resolution_quotient_summary_artifact",
            "canonical_flagship_case_id",
        ]:
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise ValueError(f"{name} must be a non-empty string")
        ensure_repo_relative_mapping(
            {
                "same_step_table_artifact": self.same_step_table_artifact,
                "same_step_negative_summary_artifact": self.same_step_negative_summary_artifact,
                "same_step_negative_outcome_artifact": self.same_step_negative_outcome_artifact,
                "same_step_support_relation_artifact": self.same_step_support_relation_artifact,
                "same_step_quotient_diagnostics_artifact": self.same_step_quotient_diagnostics_artifact,
                "cross_resolution_search_config_artifact": self.cross_resolution_search_config_artifact,
                "cross_resolution_package_build_summary_artifact": self.cross_resolution_package_build_summary_artifact,
                "cross_resolution_provenance_summary_artifact": self.cross_resolution_provenance_summary_artifact,
                "cross_resolution_quotient_summary_artifact": self.cross_resolution_quotient_summary_artifact,
            },
            field_name="lens_axis_finalization_artifacts",
        )
        ensure_metadata_shape(self.metadata)
        return self


class LensAxisFinalOutcome(SixBirdsModel):
    final_outcome_format_version: str
    lens_axis_id: str
    final_axis_status: str
    canonical_flagship_case_id: str
    same_step_table_artifact: str
    same_step_negative_summary_artifact: str
    same_step_negative_outcome_artifact: str
    cross_resolution_search_config_artifact: str
    cross_resolution_package_build_summary_artifact: str
    cross_resolution_provenance_summary_artifact: str
    cross_resolution_quotient_summary_artifact: str
    accepted_only_survivor_count: int
    natural_pairing_survivor_count: int
    accepted_only_failure_reason: str | None = None
    accepted_proposal_obstruction: bool
    final_claim_level: LensAxisClaimLevel
    regimes: list[LensAxisFinalizationRegime]
    notes: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_outcome(self) -> "LensAxisFinalOutcome":
        if self.final_outcome_format_version != "lens-axis-final-outcome.v1":
            raise ValueError(
                "final_outcome_format_version must equal 'lens-axis-final-outcome.v1'"
            )
        for name in [
            "lens_axis_id",
            "final_axis_status",
            "canonical_flagship_case_id",
            "same_step_table_artifact",
            "same_step_negative_summary_artifact",
            "same_step_negative_outcome_artifact",
            "cross_resolution_search_config_artifact",
            "cross_resolution_package_build_summary_artifact",
            "cross_resolution_provenance_summary_artifact",
            "cross_resolution_quotient_summary_artifact",
        ]:
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise ValueError(f"{name} must be a non-empty string")
        ensure_repo_relative_mapping(
            {
                "same_step_table_artifact": self.same_step_table_artifact,
                "same_step_negative_summary_artifact": self.same_step_negative_summary_artifact,
                "same_step_negative_outcome_artifact": self.same_step_negative_outcome_artifact,
                "cross_resolution_search_config_artifact": self.cross_resolution_search_config_artifact,
                "cross_resolution_package_build_summary_artifact": self.cross_resolution_package_build_summary_artifact,
                "cross_resolution_provenance_summary_artifact": self.cross_resolution_provenance_summary_artifact,
                "cross_resolution_quotient_summary_artifact": self.cross_resolution_quotient_summary_artifact,
            },
            field_name="lens_axis_final_outcome_artifacts",
        )
        for name in [
            "accepted_only_survivor_count",
            "natural_pairing_survivor_count",
        ]:
            value = getattr(self, name)
            if isinstance(value, bool) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if not self.regimes:
            raise ValueError("regimes must not be empty")
        duplicates = collect_list_duplicates(
            [regime.regime_label for regime in self.regimes]
        )
        if duplicates:
            raise ValueError(
                f"regimes must be unique by regime_label: {', '.join(duplicates)}"
            )
        duplicates = collect_list_duplicates(self.notes + self.flags)
        if duplicates:
            raise ValueError(
                f"notes/flags values must be unique within final outcome: {', '.join(duplicates)}"
            )
        if any(not value for value in self.notes + self.flags):
            raise ValueError("notes and flags must contain only non-empty strings")
        ensure_metadata_shape(self.metadata)
        return self


class PackagingAxisSearchPoint(SixBirdsModel):
    point_id: str
    selected_protocol_step_ids: list[str]
    selected_step_indices: list[int]
    selected_resolution_ids: list[str]
    allow_cross_resolution_pairs: bool = False
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_point(self) -> "PackagingAxisSearchPoint":
        if not self.point_id:
            raise ValueError("point_id must be a non-empty string")
        for name in [
            "selected_protocol_step_ids",
            "selected_step_indices",
            "selected_resolution_ids",
        ]:
            values = getattr(self, name)
            if not values:
                raise ValueError(f"{name} must not be empty")
        duplicates = collect_list_duplicates(self.selected_protocol_step_ids)
        if duplicates:
            raise ValueError(
                f"selected_protocol_step_ids must be unique: {', '.join(duplicates)}"
            )
        if any(not value for value in self.selected_protocol_step_ids):
            raise ValueError(
                "selected_protocol_step_ids must contain only non-empty strings"
            )
        duplicates = collect_list_duplicates(
            [str(value) for value in self.selected_step_indices]
        )
        if duplicates:
            raise ValueError(
                f"selected_step_indices must be unique: {', '.join(duplicates)}"
            )
        if any(
            isinstance(value, bool) or value < 0 for value in self.selected_step_indices
        ):
            raise ValueError(
                "selected_step_indices must contain only non-negative integers"
            )
        duplicates = collect_list_duplicates(self.selected_resolution_ids)
        if duplicates:
            raise ValueError(
                f"selected_resolution_ids must be unique: {', '.join(duplicates)}"
            )
        if any(not value for value in self.selected_resolution_ids):
            raise ValueError(
                "selected_resolution_ids must contain only non-empty strings"
            )
        if any(not note for note in self.notes):
            raise ValueError("notes must contain only non-empty strings")
        return self


class PackagingAxisAdequacyFloor(SixBirdsModel):
    min_total_point_count: int = 3
    min_admissible_built_package_count: int = 2
    min_points_with_proper_coarse_events: int = 1
    min_points_with_accepted_proper_coarse_structural_proposals: int = 1
    min_points_with_same_support_packaging_divergent_pairs: int = 1
    min_points_with_dual_mode_difference: int = 1
    min_points_with_nontrivial_quotient_result_recorded: int = 1

    @model_validator(mode="after")
    def validate_floor(self) -> "PackagingAxisAdequacyFloor":
        for name in [
            "min_total_point_count",
            "min_admissible_built_package_count",
            "min_points_with_proper_coarse_events",
            "min_points_with_accepted_proper_coarse_structural_proposals",
            "min_points_with_same_support_packaging_divergent_pairs",
            "min_points_with_dual_mode_difference",
            "min_points_with_nontrivial_quotient_result_recorded",
        ]:
            value = getattr(self, name)
            if isinstance(value, bool) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        return self


class PackagingAxisSearch(SixBirdsModel):
    search_format_version: str
    search_id: str
    fixed_pilot_config_artifact: str
    preparation_id: str
    protocol_id: str
    trajectories: int
    seed_list: list[int]
    points: list[PackagingAxisSearchPoint]
    projection_families: list[FrozenSliceProjectionFamily]
    fixed_projection_family_ids: list[str]
    fixed_mechanism_label: str
    fixed_lens_label: str
    event_generation_thresholds: DiscoveredEventGenerationThresholds
    shared_event_inference_thresholds: SharedEventInferenceThresholds
    candidate_classification_thresholds: TargetedCandidateClassificationThresholds
    adequacy_floor: PackagingAxisAdequacyFloor
    include_natural_pairing_control: bool = True
    quotient_subset_search_enabled: bool = True
    quotient_max_subset_size: int = 2
    quotient_stop_at_first_witness: bool = True
    provenance_required: bool = True
    claim_ceiling: PackagingAxisClaimLevel = (
        "provenance_admissible_packaging_obstruction"
    )
    output_category: str = "search"
    output_label: str | None = None
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_search(self) -> "PackagingAxisSearch":
        if self.search_format_version != "packaging-axis-search.v1":
            raise ValueError(
                "search_format_version must equal 'packaging-axis-search.v1'"
            )
        for name in [
            "search_id",
            "fixed_pilot_config_artifact",
            "preparation_id",
            "protocol_id",
            "fixed_mechanism_label",
            "fixed_lens_label",
        ]:
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise ValueError(f"{name} must be a non-empty string")
        ensure_repo_relative_mapping(
            {"fixed_pilot_config_artifact": self.fixed_pilot_config_artifact},
            field_name="fixed_pilot_config_artifact",
        )
        if isinstance(self.trajectories, bool) or self.trajectories <= 0:
            raise ValueError("trajectories must be a positive integer")
        if not self.seed_list:
            raise ValueError("seed_list must not be empty")
        duplicates = collect_list_duplicates([str(seed) for seed in self.seed_list])
        if duplicates:
            raise ValueError(f"seed_list must be unique: {', '.join(duplicates)}")
        if any(isinstance(seed, bool) for seed in self.seed_list):
            raise ValueError("seed_list must contain integers")
        if not self.points:
            raise ValueError("points must not be empty")
        duplicates = collect_list_duplicates([point.point_id for point in self.points])
        if duplicates:
            raise ValueError(
                f"points must be unique by point_id: {', '.join(duplicates)}"
            )
        if not self.projection_families:
            raise ValueError("projection_families must not be empty")
        projection_map = {
            family.projection_id: family for family in self.projection_families
        }
        duplicates = collect_list_duplicates(self.fixed_projection_family_ids)
        if duplicates:
            raise ValueError(
                f"fixed_projection_family_ids must be unique: {', '.join(duplicates)}"
            )
        if not self.fixed_projection_family_ids:
            raise ValueError("fixed_projection_family_ids must not be empty")
        for projection_id in self.fixed_projection_family_ids:
            if projection_id not in projection_map:
                raise ValueError(
                    f"fixed_projection_family_ids references unknown projection_id '{projection_id}'"
                )
            family = projection_map[projection_id]
            if "primary_context" not in family.allowed_roles:
                raise ValueError(
                    f"fixed projection family '{projection_id}' must allow primary_context"
                )
        if (
            isinstance(self.quotient_max_subset_size, bool)
            or self.quotient_max_subset_size <= 0
        ):
            raise ValueError("quotient_max_subset_size must be a positive integer")
        ensure_metadata_shape(self.metadata)
        return self


class PackagingFamilyAdmissibilityRow(SixBirdsModel):
    packaging_operator_id: str
    packaging_family_id: str
    packaging_source: str
    selector_branch_outcome: str
    same_support_eligible: bool
    allowed_roles: list[PackagingFamilyRole]
    allowed_role: PackagingFamilyRole
    notes: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_row(self) -> "PackagingFamilyAdmissibilityRow":
        for name in [
            "packaging_operator_id",
            "packaging_family_id",
            "packaging_source",
            "selector_branch_outcome",
            "allowed_role",
        ]:
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise ValueError(f"{name} must be a non-empty string")
        if not self.allowed_roles:
            raise ValueError("allowed_roles must not be empty")
        duplicates = collect_list_duplicates(self.allowed_roles)
        if duplicates:
            raise ValueError(f"allowed_roles must be unique: {', '.join(duplicates)}")
        if self.allowed_role not in self.allowed_roles:
            raise ValueError("allowed_role must be present in allowed_roles")
        duplicates = collect_list_duplicates(self.notes + self.flags)
        if duplicates:
            raise ValueError(
                f"notes/flags values must be unique: {', '.join(duplicates)}"
            )
        if any(not value for value in self.notes + self.flags):
            raise ValueError("notes and flags must contain only non-empty strings")
        return self


class PackagingFamilyAdmissibility(SixBirdsModel):
    catalog_format_version: str
    search_id: str
    fixed_mechanism_label: str
    fixed_lens_label: str
    row_count: int
    rows: list[PackagingFamilyAdmissibilityRow]
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_catalog(self) -> "PackagingFamilyAdmissibility":
        if self.catalog_format_version != "packaging-family-admissibility.v1":
            raise ValueError(
                "catalog_format_version must equal 'packaging-family-admissibility.v1'"
            )
        for name in ["search_id", "fixed_mechanism_label", "fixed_lens_label"]:
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise ValueError(f"{name} must be a non-empty string")
        if self.row_count != len(self.rows):
            raise ValueError("row_count must equal len(rows)")
        duplicates = collect_list_duplicates(
            [
                "::".join(
                    [
                        row.packaging_operator_id,
                        row.packaging_family_id,
                        row.packaging_source,
                        row.selector_branch_outcome,
                    ]
                )
                for row in self.rows
            ]
        )
        if duplicates:
            raise ValueError(
                "rows must be unique by operator/family/source/selector_branch_outcome"
            )
        ensure_metadata_shape(self.metadata)
        return self


class PackagingAxisRow(SixBirdsModel):
    row_format_version: str
    search_id: str
    point_id: str
    axis: Literal["packaging"] = "packaging"
    source_pica_campaign_config_path: str
    produced_export_bundle_path: str
    packaging_surface_summary_path: str
    discovered_context_family_path: str
    event_package_path: str | None = None
    provenance_classification: AdmissibilityClassification | None = None
    fixed_mechanism_label: str
    fixed_lens_label: str
    fixed_projection_family_ids: list[str]
    selected_protocol_step_ids: list[str]
    selected_step_indices: list[int]
    selected_resolution_ids: list[str]
    accepted_context_count: int
    accepted_singleton_event_count: int
    accepted_proper_coarse_event_count: int
    accepted_shared_event_proposal_count: int
    accepted_proper_coarse_proposal_count: int
    accepted_packaging_divergent_proposal_count: int
    accepted_packaging_divergent_proper_coarse_proposal_count: int
    same_support_packaging_divergent_pair_count: int
    same_step_packaging_divergent_pair_count: int
    cross_resolution_packaging_divergent_pair_count: int
    same_support_non_nested_packaging_divergent_pair_count: int
    baseline_hard_only: TargetedSearchEvaluation
    all_accepted_proposals: TargetedSearchEvaluation
    quotient_class_count: int | None = None
    quotient_accepted_only_survivor_count: int | None = None
    quotient_accepted_only_exact_feasible: bool | None = None
    quotient_accepted_only_failure_reason: str | None = None
    quotient_natural_pairing_survivor_count: int | None = None
    quotient_natural_pairing_exact_feasible: bool | None = None
    quotient_candidate_subset_witness_found: bool | None = None
    quotient_candidate_subset_minimal_witness_size: int | None = None
    quotient_witness_status: PackagingAxisQuotientWitnessStatus | None = None
    quotient_witness_candidate_ids: list[str] = Field(default_factory=list)
    quotient_feasibility_summary_path: str | None = None
    selected_packaging_sources: list[str]
    selected_packaging_operator_count: int
    selected_packaging_family_count: int
    packaging_support_slice_count: int
    selector_branch_outcome_counts: dict[str, int] = Field(default_factory=dict)
    support_relation_kind_counts: dict[str, int] = Field(default_factory=dict)
    candidate_classification: TargetedCandidateLabel
    claim_level_supported: PackagingAxisClaimLevel
    run_ids: dict[str, str]
    artifact_paths: dict[str, str]
    notes: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_row(self) -> "PackagingAxisRow":
        if self.row_format_version != "packaging-axis-row.v1":
            raise ValueError("row_format_version must equal 'packaging-axis-row.v1'")
        for name in [
            "search_id",
            "point_id",
            "source_pica_campaign_config_path",
            "produced_export_bundle_path",
            "packaging_surface_summary_path",
            "discovered_context_family_path",
            "fixed_mechanism_label",
            "fixed_lens_label",
        ]:
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise ValueError(f"{name} must be a non-empty string")
        ensure_repo_relative_mapping(
            {
                "source_pica_campaign_config_path": self.source_pica_campaign_config_path,
                "produced_export_bundle_path": self.produced_export_bundle_path,
                "packaging_surface_summary_path": self.packaging_surface_summary_path,
                "discovered_context_family_path": self.discovered_context_family_path,
            },
            field_name="packaging_axis_artifacts",
        )
        if self.event_package_path is not None and not is_repo_relative_path(
            self.event_package_path
        ):
            raise ValueError(
                "event_package_path must be a normalized repo-relative path when present"
            )
        for name in [
            "accepted_context_count",
            "accepted_singleton_event_count",
            "accepted_proper_coarse_event_count",
            "accepted_shared_event_proposal_count",
            "accepted_proper_coarse_proposal_count",
            "accepted_packaging_divergent_proposal_count",
            "accepted_packaging_divergent_proper_coarse_proposal_count",
            "same_support_packaging_divergent_pair_count",
            "same_step_packaging_divergent_pair_count",
            "cross_resolution_packaging_divergent_pair_count",
            "same_support_non_nested_packaging_divergent_pair_count",
            "selected_packaging_operator_count",
            "selected_packaging_family_count",
            "packaging_support_slice_count",
        ]:
            value = getattr(self, name)
            if isinstance(value, bool) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        for name in [
            "quotient_class_count",
            "quotient_accepted_only_survivor_count",
            "quotient_natural_pairing_survivor_count",
            "quotient_candidate_subset_minimal_witness_size",
        ]:
            value = getattr(self, name)
            if value is not None and (isinstance(value, bool) or value < 0):
                raise ValueError(f"{name} must be a non-negative integer when present")
        for name, values in [
            ("fixed_projection_family_ids", self.fixed_projection_family_ids),
            ("selected_protocol_step_ids", self.selected_protocol_step_ids),
            ("selected_resolution_ids", self.selected_resolution_ids),
            ("selected_packaging_sources", self.selected_packaging_sources),
            ("quotient_witness_candidate_ids", self.quotient_witness_candidate_ids),
        ]:
            duplicates = collect_list_duplicates(values)
            if duplicates:
                raise ValueError(f"{name} must be unique: {', '.join(duplicates)}")
            if any(not value for value in values):
                raise ValueError(f"{name} must contain only non-empty strings")
        duplicates = collect_list_duplicates(
            [str(value) for value in self.selected_step_indices]
        )
        if duplicates:
            raise ValueError(
                f"selected_step_indices must be unique: {', '.join(duplicates)}"
            )
        if any(
            isinstance(value, bool) or value < 0 for value in self.selected_step_indices
        ):
            raise ValueError(
                "selected_step_indices must contain only non-negative integers"
            )
        if (
            self.quotient_feasibility_summary_path is not None
            and not is_repo_relative_path(self.quotient_feasibility_summary_path)
        ):
            raise ValueError(
                "quotient_feasibility_summary_path must be a normalized repo-relative path when present"
            )
        if not self.run_ids:
            raise ValueError("run_ids must not be empty")
        if not self.artifact_paths:
            raise ValueError("artifact_paths must not be empty")
        ensure_repo_relative_mapping(self.artifact_paths, field_name="artifact_paths")
        for name, mapping in [
            ("selector_branch_outcome_counts", self.selector_branch_outcome_counts),
            ("support_relation_kind_counts", self.support_relation_kind_counts),
        ]:
            for key, value in mapping.items():
                if not key:
                    raise ValueError(f"{name} keys must be non-empty strings")
                if isinstance(value, bool) or value < 0:
                    raise ValueError(f"{name} values must be non-negative integers")
        if any(not value for value in self.notes + self.flags):
            raise ValueError("notes and flags must contain only non-empty strings")
        return self


class PackagingAxisTable(SixBirdsModel):
    table_format_version: str
    search_id: str
    row_count: int
    rows: list[PackagingAxisRow]
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_table(self) -> "PackagingAxisTable":
        if self.table_format_version != "packaging-axis-results.v1":
            raise ValueError(
                "table_format_version must equal 'packaging-axis-results.v1'"
            )
        if not self.search_id:
            raise ValueError("search_id must be a non-empty string")
        if self.row_count != len(self.rows):
            raise ValueError("row_count must equal len(rows)")
        duplicates = collect_list_duplicates([row.point_id for row in self.rows])
        if duplicates:
            raise ValueError(
                f"packaging-axis rows must be unique by point_id: {', '.join(duplicates)}"
            )
        if any(row.search_id != self.search_id for row in self.rows):
            raise ValueError("all rows must share the table search_id")
        ensure_metadata_shape(self.metadata)
        return self
