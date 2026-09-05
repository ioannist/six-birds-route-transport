from __future__ import annotations

import math
from typing import Literal

from pydantic import Field, model_validator

from ..provenance.models import AdmissibilityClassification
from ..schemas.common import (
    MetadataValue,
    MetricValue,
    SixBirdsModel,
    collect_list_duplicates,
    ensure_metadata_shape,
    ensure_metric_shape,
    ensure_repo_relative_mapping,
    is_json_scalar,
)

AxisName = Literal["mechanism", "lens", "packaging"]
FrozenSliceSupportIndexKind = Literal["row", "trajectory", "mixed"]
FrozenSliceVariationMode = Literal["same_step", "cross_resolution_strict_extension"]
FrozenSliceSupportedAxis = Literal["lens", "packaging"]
HierarchyPropositionKind = Literal[
    "formal_consequence",
    "non_implication",
    "adjudicated_rule",
]
HierarchyPropositionSupportType = Literal[
    "theory",
    "committed_evidence",
    "theory_and_evidence",
]
PackageConflictRelationLevel = Literal[
    "projection_difference_only",
    "lens_mismatch_only",
    "packaging_surface_divergence",
    "package_conflict_proper",
    "packaging_obstruction",
]
PackageConflictClassification = Literal[
    "projection_difference_only",
    "lens_mismatch_only",
    "selector_branch_package_divergence",
    "operator_or_family_package_divergence",
    "strict_extension_package_conflict",
    "package_conflict_with_obstruction",
]
PackageConflictObstructionStatus = Literal[
    "none",
    "candidate_subset_quotient_witness",
    "accepted_proposal_obstruction",
]
AxisClaimLevel = Literal[
    "mechanism_dependence",
    "nontrivial_multicontext_structure",
    "same_slice_non_nested_structure",
    "package_conflict_tension",
    "bounded_negative_result",
    "provenance_admissible_strong_obstruction",
]
SharedCandidateClass = Literal[
    "strongly_nonextendable_candidate",
    "weakly_frustrated_candidate",
    "extendable_candidate",
    "trivial_or_nonrecording",
    "inconclusive",
]
SharedExplicitStatus = Literal[
    "solved",
    "unsolved",
    "insufficient_data",
    "not_applicable",
]
SharedExactStatus = Literal["feasible", "infeasible", "not_applicable"]
OutcomeArtifactKind = Literal[
    "best-candidate",
    "negative-result",
    "design-inadequate-result",
]

_CLAIM_LEVEL_ORDER: dict[AxisClaimLevel, int] = {
    "mechanism_dependence": 0,
    "nontrivial_multicontext_structure": 1,
    "same_slice_non_nested_structure": 2,
    "package_conflict_tension": 3,
    "bounded_negative_result": 4,
    "provenance_admissible_strong_obstruction": 5,
}

_AXIS_REQUIRED_VARYING_FIELDS: dict[AxisName, set[str]] = {
    "mechanism": {
        "enable_matrix_id",
        "mechanism_family_id",
        "control_space_point_id",
        "mechanism_config_id",
    },
    "lens": {
        "lens_id",
        "projection_id",
        "projection_family_id",
        "record_algebra_id",
    },
    "packaging": {
        "packaging_operator_id",
        "package_family_id",
        "package_selector_branch",
        "packaging_policy_id",
    },
}

_AXIS_REQUIRED_FIXED_FIELDS: dict[AxisName, set[str]] = {
    "mechanism": {
        "lens_family_id",
        "packaging_policy_id",
    },
    "lens": {
        "mechanism_family_id",
        "packaging_policy_id",
        "protocol_step_id",
        "step_index",
    },
    "packaging": {
        "mechanism_family_id",
        "lens_family_id",
        "protocol_step_id",
        "step_index",
    },
}

_AXIS_MAX_CLAIM_LEVEL: dict[AxisName, AxisClaimLevel] = {
    "mechanism": "nontrivial_multicontext_structure",
    "lens": "same_slice_non_nested_structure",
    "packaging": "provenance_admissible_strong_obstruction",
}


def claim_level_rank(level: AxisClaimLevel) -> int:
    return _CLAIM_LEVEL_ORDER[level]


def axis_claim_ceiling(axis: AxisName) -> AxisClaimLevel:
    return _AXIS_MAX_CLAIM_LEVEL[axis]


def claim_level_allowed_for_axis(axis: AxisName, level: AxisClaimLevel) -> bool:
    return claim_level_rank(level) <= claim_level_rank(axis_claim_ceiling(axis))


class AxisAdmissibilityContract(SixBirdsModel):
    axis: AxisName
    varied_fields: list[str]
    fixed_fields: list[str]
    source_pair_match_fields: list[str]
    source_pair_variation_fields: list[str] = Field(default_factory=list)
    admissibility_requirements: list[str]
    allowed_outcome_artifacts: list[OutcomeArtifactKind]
    max_claim_level: AxisClaimLevel
    flags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_contract(self) -> "AxisAdmissibilityContract":
        for name in [
            "varied_fields",
            "fixed_fields",
            "source_pair_match_fields",
            "admissibility_requirements",
            "allowed_outcome_artifacts",
        ]:
            values = getattr(self, name)
            if not values:
                raise ValueError(f"{name} must not be empty")
            if any(not isinstance(value, str) or not value for value in values):
                raise ValueError(f"{name} must contain only non-empty strings")
        duplicates = collect_list_duplicates(self.varied_fields + self.fixed_fields)
        if duplicates:
            raise ValueError(
                f"varied_fields and fixed_fields must be disjoint: {', '.join(duplicates)}"
            )
        required_varied = _AXIS_REQUIRED_VARYING_FIELDS[self.axis]
        if not required_varied.intersection(self.varied_fields):
            raise ValueError(
                f"{self.axis} axis must vary at least one of: {', '.join(sorted(required_varied))}"
            )
        required_fixed = _AXIS_REQUIRED_FIXED_FIELDS[self.axis]
        if not required_fixed.intersection(self.fixed_fields):
            raise ValueError(
                f"{self.axis} axis must hold fixed at least one of: {', '.join(sorted(required_fixed))}"
            )
        if self.axis != "packaging" and any(
            artifact in {"best-candidate", "negative-result"}
            for artifact in self.allowed_outcome_artifacts
        ):
            raise ValueError(
                "only packaging axis may declare best-candidate or negative-result outcomes"
            )
        if self.max_claim_level != axis_claim_ceiling(self.axis):
            raise ValueError(
                f"max_claim_level for {self.axis} must equal {axis_claim_ceiling(self.axis)}"
            )
        if any(not flag for flag in self.flags):
            raise ValueError("flags must contain only non-empty strings")
        return self


class SharedMetricValue(SixBirdsModel):
    status: SharedExplicitStatus
    value: MetricValue = None
    reason: str | None = None

    @model_validator(mode="after")
    def validate_metric(self) -> "SharedMetricValue":
        if self.status == "solved" and self.value is None:
            raise ValueError("value must be present when status is solved")
        if self.status != "solved" and self.value is not None:
            raise ValueError("value must be null unless status is solved")
        if self.reason is not None and not self.reason:
            raise ValueError("reason must be non-empty when present")
        if self.value is not None and not is_json_scalar(self.value):
            raise ValueError("value must be a JSON scalar when present")
        if isinstance(self.value, float) and not math.isfinite(self.value):
            raise ValueError("value must be finite when present")
        return self


class SharedExactEvaluation(SixBirdsModel):
    exact_feasibility_status: SharedExactStatus
    exact_feasible: bool | None = None
    respecting_tuple_count: int | None = None
    exact_reason: str | None = None
    gpd_str: SharedMetricValue
    gpd_stat: SharedMetricValue

    @model_validator(mode="after")
    def validate_evaluation(self) -> "SharedExactEvaluation":
        if self.exact_feasibility_status == "not_applicable":
            if (
                self.exact_feasible is not None
                or self.respecting_tuple_count is not None
            ):
                raise ValueError(
                    "exact_feasible and respecting_tuple_count must be null when exact_feasibility_status is not_applicable"
                )
        else:
            if self.exact_feasible is None:
                raise ValueError(
                    "exact_feasible must be present when exact_feasibility_status is feasible or infeasible"
                )
        if self.respecting_tuple_count is not None and (
            isinstance(self.respecting_tuple_count, bool)
            or self.respecting_tuple_count < 0
        ):
            raise ValueError("respecting_tuple_count must be a non-negative integer")
        if self.exact_reason is not None and not self.exact_reason:
            raise ValueError("exact_reason must be non-empty when present")
        return self


class SharedSupportDiagnostics(SixBirdsModel):
    support_status: SharedExplicitStatus
    median_event_support: float | None = None
    median_proposal_support: float | None = None
    shared_support_scope: str | None = None

    @model_validator(mode="after")
    def validate_support(self) -> "SharedSupportDiagnostics":
        if self.support_status == "solved":
            if (
                self.median_event_support is None
                and self.median_proposal_support is None
            ):
                raise ValueError(
                    "at least one support median must be present when support_status is solved"
                )
        else:
            if (
                self.median_event_support is not None
                or self.median_proposal_support is not None
            ):
                raise ValueError(
                    "support medians must be null unless support_status is solved"
                )
        for name in ["median_event_support", "median_proposal_support"]:
            value = getattr(self, name)
            if value is not None and (
                isinstance(value, bool) or not math.isfinite(value) or value < 0
            ):
                raise ValueError(f"{name} must be a finite non-negative value")
        if self.shared_support_scope is not None and not self.shared_support_scope:
            raise ValueError("shared_support_scope must be non-empty when present")
        return self


class SharedContextPairStructureDiagnostics(SixBirdsModel):
    diagnostics_status: SharedExplicitStatus
    equal_pair_count: int | None = None
    refinement_pair_count: int | None = None
    non_nested_pair_count: int | None = None
    disjoint_pair_count: int | None = None

    @model_validator(mode="after")
    def validate_diagnostics(self) -> "SharedContextPairStructureDiagnostics":
        counts = [
            self.equal_pair_count,
            self.refinement_pair_count,
            self.non_nested_pair_count,
            self.disjoint_pair_count,
        ]
        if self.diagnostics_status == "solved":
            if any(value is None for value in counts):
                raise ValueError(
                    "all context-pair counts must be present when diagnostics_status is solved"
                )
        elif any(value is not None for value in counts):
            raise ValueError(
                "context-pair counts must be null unless diagnostics_status is solved"
            )
        for name in [
            "equal_pair_count",
            "refinement_pair_count",
            "non_nested_pair_count",
            "disjoint_pair_count",
        ]:
            value = getattr(self, name)
            if value is not None and (isinstance(value, bool) or value < 0):
                raise ValueError(f"{name} must be a non-negative integer")
        return self


class SharedAxisAdmissibilityDiagnostics(SixBirdsModel):
    diagnostics_status: SharedExplicitStatus
    admissible_pair_count: int | None = None
    fixed_field_match_count: int | None = None
    varying_field_difference_count: int | None = None
    diagnostic_flags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_diagnostics(self) -> "SharedAxisAdmissibilityDiagnostics":
        counts = [
            self.admissible_pair_count,
            self.fixed_field_match_count,
            self.varying_field_difference_count,
        ]
        if self.diagnostics_status == "solved":
            if any(value is None for value in counts):
                raise ValueError(
                    "axis admissibility counts must be present when diagnostics_status is solved"
                )
        elif any(value is not None for value in counts):
            raise ValueError(
                "axis admissibility counts must be null unless diagnostics_status is solved"
            )
        for name in [
            "admissible_pair_count",
            "fixed_field_match_count",
            "varying_field_difference_count",
        ]:
            value = getattr(self, name)
            if value is not None and (isinstance(value, bool) or value < 0):
                raise ValueError(f"{name} must be a non-negative integer")
        if any(not flag for flag in self.diagnostic_flags):
            raise ValueError("diagnostic_flags must contain only non-empty strings")
        return self


class SharedMetricSurface(SixBirdsModel):
    metric_surface_format_version: str
    provenance_classification: AdmissibilityClassification | None = None
    accepted_context_count: int
    accepted_singleton_event_count: int
    accepted_proper_coarse_event_count: int
    accepted_shared_event_proposal_count: int
    accepted_proper_coarse_proposal_count: int
    baseline_hard_only: SharedExactEvaluation
    all_accepted_proposals: SharedExactEvaluation
    sec: SharedMetricValue
    rm: SharedMetricValue
    ccd: SharedMetricValue
    support_diagnostics: SharedSupportDiagnostics
    context_pair_structure_diagnostics: SharedContextPairStructureDiagnostics
    axis_admissibility_diagnostics: SharedAxisAdmissibilityDiagnostics
    flags: list[str] = Field(default_factory=list)
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_metric_surface(self) -> "SharedMetricSurface":
        if self.metric_surface_format_version != "shared-metric-surface.v1":
            raise ValueError(
                "metric_surface_format_version must equal 'shared-metric-surface.v1'"
            )
        for name in [
            "accepted_context_count",
            "accepted_singleton_event_count",
            "accepted_proper_coarse_event_count",
            "accepted_shared_event_proposal_count",
            "accepted_proper_coarse_proposal_count",
        ]:
            value = getattr(self, name)
            if isinstance(value, bool) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if any(not flag for flag in self.flags):
            raise ValueError("flags must contain only non-empty strings")
        ensure_metadata_shape(self.metadata)
        return self


class AxisClaimLevelSpec(SixBirdsModel):
    level: AxisClaimLevel
    order_index: int
    short_label: str
    supported_axes: list[AxisName]
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_level(self) -> "AxisClaimLevelSpec":
        if self.order_index != claim_level_rank(self.level):
            raise ValueError(
                f"order_index for {self.level} must equal {claim_level_rank(self.level)}"
            )
        if not self.short_label:
            raise ValueError("short_label must be a non-empty string")
        if not self.supported_axes:
            raise ValueError("supported_axes must not be empty")
        if len(self.supported_axes) != len(set(self.supported_axes)):
            raise ValueError("supported_axes must be unique")
        if any(not note for note in self.notes):
            raise ValueError("notes must contain only non-empty strings")
        return self


class AxisClaimLadder(SixBirdsModel):
    ladder_format_version: str
    ladder_id: str
    levels: list[AxisClaimLevelSpec]
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_ladder(self) -> "AxisClaimLadder":
        if self.ladder_format_version != "axis-claim-ladder.v1":
            raise ValueError("ladder_format_version must equal 'axis-claim-ladder.v1'")
        if not self.ladder_id:
            raise ValueError("ladder_id must be a non-empty string")
        if len(self.levels) != len(_CLAIM_LEVEL_ORDER):
            raise ValueError(
                "levels must include every shared claim level exactly once"
            )
        duplicates = collect_list_duplicates([level.level for level in self.levels])
        if duplicates:
            raise ValueError(f"claim levels must be unique: {', '.join(duplicates)}")
        expected_order = list(_CLAIM_LEVEL_ORDER)
        actual_order = [
            level.level for level in sorted(self.levels, key=lambda x: x.order_index)
        ]
        if actual_order != expected_order:
            raise ValueError("claim levels must follow the shared claim ladder order")
        ensure_metadata_shape(self.metadata)
        return self


class SharedMetricReportingConfig(SixBirdsModel):
    required_metric_groups: list[str]
    explicit_statuses_required: bool = True
    preserve_dual_evaluation: bool = True

    @model_validator(mode="after")
    def validate_reporting(self) -> "SharedMetricReportingConfig":
        if not self.required_metric_groups:
            raise ValueError("required_metric_groups must not be empty")
        if any(
            not isinstance(group, str) or not group
            for group in self.required_metric_groups
        ):
            raise ValueError(
                "required_metric_groups must contain only non-empty strings"
            )
        return self


class ThreeAxisSearchConfig(SixBirdsModel):
    config_format_version: str
    search_id: str
    axis: AxisName
    axis_admissibility: AxisAdmissibilityContract
    shared_metric_surface_ref: str
    shared_metric_reporting: SharedMetricReportingConfig
    claim_ladder_ref: str
    candidate_classification_config_ref: str | None = None
    adequacy_floor: dict[str, MetricValue]
    notes: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_config(self) -> "ThreeAxisSearchConfig":
        if self.config_format_version != "three-axis-search-config.v1":
            raise ValueError(
                "config_format_version must equal 'three-axis-search-config.v1'"
            )
        if not self.search_id:
            raise ValueError("search_id must be a non-empty string")
        if self.axis_admissibility.axis != self.axis:
            raise ValueError("axis_admissibility.axis must match axis")
        ensure_repo_relative_mapping(
            {
                "shared_metric_surface_ref": self.shared_metric_surface_ref,
                "claim_ladder_ref": self.claim_ladder_ref,
            },
            field_name="contract_refs",
        )
        if self.candidate_classification_config_ref is not None:
            ensure_repo_relative_mapping(
                {
                    "candidate_classification_config_ref": self.candidate_classification_config_ref
                },
                field_name="contract_refs",
            )
        ensure_metric_shape(self.adequacy_floor)
        if not self.adequacy_floor:
            raise ValueError("adequacy_floor must not be empty")
        if any(not note for note in self.notes):
            raise ValueError("notes must contain only non-empty strings")
        if any(not flag for flag in self.flags):
            raise ValueError("flags must contain only non-empty strings")
        ensure_metadata_shape(self.metadata)
        return self


class ThreeAxisSearchRow(SixBirdsModel):
    row_format_version: str
    search_id: str
    point_id: str
    axis: AxisName
    source_asset_refs: dict[str, str]
    fixed_field_summary: dict[str, MetadataValue]
    varying_field_summary: dict[str, MetadataValue]
    claim_ladder_ref: str
    shared_metric_surface_ref: str | None = None
    shared_metric_surface: SharedMetricSurface | None = None
    candidate_classification: SharedCandidateClass
    claim_level_support: AxisClaimLevel
    outcome_artifact_kind: OutcomeArtifactKind | None = None
    best_evidence_eligible: bool
    flags: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_row(self) -> "ThreeAxisSearchRow":
        if self.row_format_version != "three-axis-search-row.v1":
            raise ValueError("row_format_version must equal 'three-axis-search-row.v1'")
        if not self.search_id:
            raise ValueError("search_id must be a non-empty string")
        if not self.point_id:
            raise ValueError("point_id must be a non-empty string")
        if not self.source_asset_refs:
            raise ValueError("source_asset_refs must not be empty")
        ensure_repo_relative_mapping(
            self.source_asset_refs, field_name="source_asset_refs"
        )
        ensure_metadata_shape(self.fixed_field_summary)
        ensure_metadata_shape(self.varying_field_summary)
        duplicates = set(self.fixed_field_summary).intersection(
            self.varying_field_summary
        )
        if duplicates:
            raise ValueError(
                f"fixed_field_summary and varying_field_summary must be disjoint: {', '.join(sorted(duplicates))}"
            )
        required_varied = _AXIS_REQUIRED_VARYING_FIELDS[self.axis]
        if not required_varied.intersection(self.varying_field_summary):
            raise ValueError(
                f"{self.axis} row must vary at least one of: {', '.join(sorted(required_varied))}"
            )
        required_fixed = _AXIS_REQUIRED_FIXED_FIELDS[self.axis]
        if not required_fixed.intersection(self.fixed_field_summary):
            raise ValueError(
                f"{self.axis} row must fix at least one of: {', '.join(sorted(required_fixed))}"
            )
        ensure_repo_relative_mapping(
            {"claim_ladder_ref": self.claim_ladder_ref},
            field_name="row_contract_refs",
        )
        if (
            self.shared_metric_surface_ref is None
            and self.shared_metric_surface is None
        ):
            raise ValueError(
                "either shared_metric_surface_ref or shared_metric_surface must be present"
            )
        if (
            self.shared_metric_surface_ref is not None
            and self.shared_metric_surface is not None
        ):
            raise ValueError(
                "shared_metric_surface_ref and shared_metric_surface are mutually exclusive"
            )
        if self.shared_metric_surface_ref is not None:
            ensure_repo_relative_mapping(
                {"shared_metric_surface_ref": self.shared_metric_surface_ref},
                field_name="row_contract_refs",
            )
        if not claim_level_allowed_for_axis(self.axis, self.claim_level_support):
            raise ValueError(
                f"claim_level_support={self.claim_level_support} exceeds default ceiling for axis={self.axis}"
            )
        if (
            self.outcome_artifact_kind in {"best-candidate", "negative-result"}
            and self.axis != "packaging"
        ):
            raise ValueError(
                "only packaging rows may claim best-candidate or negative-result outcomes"
            )
        if any(not flag for flag in self.flags):
            raise ValueError("flags must contain only non-empty strings")
        if any(not note for note in self.notes):
            raise ValueError("notes must contain only non-empty strings")
        return self


HierarchyCampaignOutcomeKind = Literal[
    "design_inadequate",
    "negative_result",
    "best_candidate",
    "finalized_axis_closure",
]
HierarchyQuotientStatus = Literal[
    "accepted_proposal_obstruction",
    "candidate_subset_quotient_witness",
    "no_quotient_obstruction",
]
HierarchyBestEvidenceType = Literal[
    "committed_witness_case",
    "canonical_flagship_regime",
    "campaign_best_candidate",
]
HierarchyClaimLevel = Literal[
    "mechanism_dependence",
    "nontrivial_multicontext_structure",
    "same_slice_non_nested_structure",
    "bounded_negative_result",
    "package_conflict_tension",
    "provenance_admissible_strong_obstruction",
    "provenance_admissible_packaging_obstruction",
]

_HIERARCHY_CLAIM_LEVEL_ORDER: dict[HierarchyClaimLevel, int] = {
    "mechanism_dependence": 0,
    "nontrivial_multicontext_structure": 1,
    "same_slice_non_nested_structure": 2,
    "bounded_negative_result": 2,
    "package_conflict_tension": 3,
    "provenance_admissible_strong_obstruction": 4,
    "provenance_admissible_packaging_obstruction": 5,
}


def hierarchy_claim_level_rank(level: HierarchyClaimLevel) -> int:
    return _HIERARCHY_CLAIM_LEVEL_ORDER[level]


class ThreeAxisHierarchyConfig(SixBirdsModel):
    config_format_version: str
    hierarchy_id: str
    mechanism_campaign_summary_ref: str
    mechanism_campaign_table_ref: str
    mechanism_witness_summary_ref: str
    lens_final_summary_ref: str
    packaging_campaign_summary_ref: str
    packaging_campaign_table_ref: str
    packaging_best_candidate_ref: str
    synthesis_settings: dict[str, MetadataValue] = Field(default_factory=dict)
    figure_export_settings: dict[str, MetadataValue] = Field(default_factory=dict)
    output_category: str = "results"
    output_label: str | None = None
    notes: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_config(self) -> "ThreeAxisHierarchyConfig":
        if self.config_format_version != "three-axis-hierarchy-config.v1":
            raise ValueError(
                "config_format_version must equal 'three-axis-hierarchy-config.v1'"
            )
        if not self.hierarchy_id:
            raise ValueError("hierarchy_id must be a non-empty string")
        ensure_repo_relative_mapping(
            {
                "mechanism_campaign_summary_ref": self.mechanism_campaign_summary_ref,
                "mechanism_campaign_table_ref": self.mechanism_campaign_table_ref,
                "mechanism_witness_summary_ref": self.mechanism_witness_summary_ref,
                "lens_final_summary_ref": self.lens_final_summary_ref,
                "packaging_campaign_summary_ref": self.packaging_campaign_summary_ref,
                "packaging_campaign_table_ref": self.packaging_campaign_table_ref,
                "packaging_best_candidate_ref": self.packaging_best_candidate_ref,
            },
            field_name="source_refs",
        )
        ensure_metadata_shape(self.synthesis_settings)
        ensure_metadata_shape(self.figure_export_settings)
        if self.output_label is not None and not self.output_label:
            raise ValueError("output_label must be non-empty when present")
        if any(not note for note in self.notes):
            raise ValueError("notes must contain only non-empty strings")
        if any(not flag for flag in self.flags):
            raise ValueError("flags must contain only non-empty strings")
        ensure_metadata_shape(self.metadata)
        return self


class ThreeAxisHierarchyRow(SixBirdsModel):
    row_format_version: str
    row_id: str
    hierarchy_id: str
    axis: AxisName
    axis_campaign_outcome_kind: HierarchyCampaignOutcomeKind
    axis_campaign_outcome_label: str
    best_evidence_type: HierarchyBestEvidenceType
    best_witness_label: str
    best_witness_status: HierarchyQuotientStatus
    accepted_proposal_obstruction_count: int
    candidate_subset_quotient_witness_count: int
    no_quotient_obstruction_count: int
    claim_level_supported: HierarchyClaimLevel
    caveat_flags: list[str] = Field(default_factory=list)
    primary_artifact_refs: dict[str, str]
    supporting_artifact_refs: dict[str, str] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_row(self) -> "ThreeAxisHierarchyRow":
        if self.row_format_version != "three-axis-hierarchy-row.v1":
            raise ValueError(
                "row_format_version must equal 'three-axis-hierarchy-row.v1'"
            )
        if not self.row_id:
            raise ValueError("row_id must be a non-empty string")
        if not self.hierarchy_id:
            raise ValueError("hierarchy_id must be a non-empty string")
        if not self.axis_campaign_outcome_label:
            raise ValueError("axis_campaign_outcome_label must be non-empty")
        if not self.best_witness_label:
            raise ValueError("best_witness_label must be non-empty")
        for name in [
            "accepted_proposal_obstruction_count",
            "candidate_subset_quotient_witness_count",
            "no_quotient_obstruction_count",
        ]:
            value = getattr(self, name)
            if isinstance(value, bool) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if not self.primary_artifact_refs:
            raise ValueError("primary_artifact_refs must not be empty")
        ensure_repo_relative_mapping(
            self.primary_artifact_refs,
            field_name="primary_artifact_refs",
        )
        ensure_repo_relative_mapping(
            self.supporting_artifact_refs,
            field_name="supporting_artifact_refs",
        )
        if any(not flag for flag in self.caveat_flags):
            raise ValueError("caveat_flags must contain only non-empty strings")
        if any(not note for note in self.notes):
            raise ValueError("notes must contain only non-empty strings")
        if any(not flag for flag in self.flags):
            raise ValueError("flags must contain only non-empty strings")
        return self


class ThreeAxisHierarchyResults(SixBirdsModel):
    table_format_version: str
    hierarchy_id: str
    row_count: int
    rows: list[ThreeAxisHierarchyRow]
    strongest_current_axis: AxisName
    accepted_obstruction_exists_on_mechanism: bool
    accepted_obstruction_exists_on_lens: bool
    accepted_obstruction_exists_on_packaging: bool
    claim_level_ordering: list[AxisName]
    comparative_conclusions: dict[str, MetadataValue]
    output_paths: dict[str, str]
    notes: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_results(self) -> "ThreeAxisHierarchyResults":
        if self.table_format_version != "three-axis-hierarchy-results.v1":
            raise ValueError(
                "table_format_version must equal 'three-axis-hierarchy-results.v1'"
            )
        if not self.hierarchy_id:
            raise ValueError("hierarchy_id must be a non-empty string")
        if self.row_count != len(self.rows):
            raise ValueError("row_count must equal len(rows)")
        if len(self.rows) != 3:
            raise ValueError("rows must contain exactly three axis summaries")
        axis_duplicates = collect_list_duplicates([row.axis for row in self.rows])
        if axis_duplicates:
            raise ValueError(
                f"rows must be unique by axis: {', '.join(axis_duplicates)}"
            )
        row_id_duplicates = collect_list_duplicates([row.row_id for row in self.rows])
        if row_id_duplicates:
            raise ValueError(
                f"rows must be unique by row_id: {', '.join(row_id_duplicates)}"
            )
        if self.strongest_current_axis not in {row.axis for row in self.rows}:
            raise ValueError("strongest_current_axis must appear in rows")
        if set(self.claim_level_ordering) != {"mechanism", "lens", "packaging"}:
            raise ValueError(
                "claim_level_ordering must contain mechanism, lens, packaging exactly once"
            )
        ensure_metadata_shape(self.comparative_conclusions)
        ensure_repo_relative_mapping(self.output_paths, field_name="output_paths")
        if any(not note for note in self.notes):
            raise ValueError("notes must contain only non-empty strings")
        if any(not flag for flag in self.flags):
            raise ValueError("flags must contain only non-empty strings")
        ensure_metadata_shape(self.metadata)
        return self


class ClaimStrengthRegistryEntry(SixBirdsModel):
    claim_id: str
    axis: AxisName
    claim_level: HierarchyClaimLevel
    best_evidence_row_id: str
    primary_artifact_refs: dict[str, str]
    supporting_artifact_refs: dict[str, str] = Field(default_factory=dict)
    caveat_flags: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_entry(self) -> "ClaimStrengthRegistryEntry":
        if not self.claim_id:
            raise ValueError("claim_id must be a non-empty string")
        if not self.best_evidence_row_id:
            raise ValueError("best_evidence_row_id must be a non-empty string")
        if not self.primary_artifact_refs:
            raise ValueError("primary_artifact_refs must not be empty")
        ensure_repo_relative_mapping(
            self.primary_artifact_refs,
            field_name="primary_artifact_refs",
        )
        ensure_repo_relative_mapping(
            self.supporting_artifact_refs,
            field_name="supporting_artifact_refs",
        )
        if any(not flag for flag in self.caveat_flags):
            raise ValueError("caveat_flags must contain only non-empty strings")
        if any(not note for note in self.notes):
            raise ValueError("notes must contain only non-empty strings")
        return self


class ClaimStrengthRegistry(SixBirdsModel):
    registry_format_version: str
    registry_id: str
    entries: list[ClaimStrengthRegistryEntry]
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_registry(self) -> "ClaimStrengthRegistry":
        if self.registry_format_version != "claim-strength-registry.v1":
            raise ValueError(
                "registry_format_version must equal 'claim-strength-registry.v1'"
            )
        if not self.registry_id:
            raise ValueError("registry_id must be a non-empty string")
        if len(self.entries) != 3:
            raise ValueError("entries must contain exactly three axis claims")
        axis_duplicates = collect_list_duplicates(
            [entry.axis for entry in self.entries]
        )
        if axis_duplicates:
            raise ValueError(
                f"entries must be unique by axis: {', '.join(axis_duplicates)}"
            )
        claim_duplicates = collect_list_duplicates(
            [entry.claim_id for entry in self.entries]
        )
        if claim_duplicates:
            raise ValueError(
                f"entries must be unique by claim_id: {', '.join(claim_duplicates)}"
            )
        ensure_metadata_shape(self.metadata)
        return self


class BestEvidenceEntry(SixBirdsModel):
    axis: AxisName
    best_evidence_type: HierarchyBestEvidenceType
    best_evidence_status: HierarchyQuotientStatus
    primary_artifact_refs: dict[str, str]
    supporting_artifact_refs: dict[str, str] = Field(default_factory=dict)
    reason_for_selection: str
    caveat_flags: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_entry(self) -> "BestEvidenceEntry":
        if not self.reason_for_selection:
            raise ValueError("reason_for_selection must be non-empty")
        if not self.primary_artifact_refs:
            raise ValueError("primary_artifact_refs must not be empty")
        ensure_repo_relative_mapping(
            self.primary_artifact_refs,
            field_name="primary_artifact_refs",
        )
        ensure_repo_relative_mapping(
            self.supporting_artifact_refs,
            field_name="supporting_artifact_refs",
        )
        if any(not flag for flag in self.caveat_flags):
            raise ValueError("caveat_flags must contain only non-empty strings")
        if any(not note for note in self.notes):
            raise ValueError("notes must contain only non-empty strings")
        return self


class BestEvidenceByAxis(SixBirdsModel):
    mapping_format_version: str
    mapping_id: str
    entries: list[BestEvidenceEntry]
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_mapping(self) -> "BestEvidenceByAxis":
        if self.mapping_format_version != "best-evidence-by-axis.v1":
            raise ValueError(
                "mapping_format_version must equal 'best-evidence-by-axis.v1'"
            )
        if not self.mapping_id:
            raise ValueError("mapping_id must be a non-empty string")
        if len(self.entries) != 3:
            raise ValueError("entries must contain exactly three axis evidence objects")
        axis_duplicates = collect_list_duplicates(
            [entry.axis for entry in self.entries]
        )
        if axis_duplicates:
            raise ValueError(
                f"entries must be unique by axis: {', '.join(axis_duplicates)}"
            )
        ensure_metadata_shape(self.metadata)
        return self


class FrozenSliceSupportObject(SixBirdsModel):
    object_format_version: str
    support_object_id: str
    support_index_kind: FrozenSliceSupportIndexKind
    support_index_refs: list[str]
    source_config_ref: str | None = None
    source_bundle_ref: str | None = None
    mechanism_family_id: str
    mechanism_config_id: str | None = None
    preparation_id: str
    protocol_id: str
    evaluation_regime_id: str
    fixed_protocol_step_ids: list[str] = Field(default_factory=list)
    fixed_step_indices: list[int] = Field(default_factory=list)
    fixed_resolution_ids: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_support_object(self) -> "FrozenSliceSupportObject":
        if self.object_format_version != "frozen-slice-support-object.v1":
            raise ValueError(
                "object_format_version must equal 'frozen-slice-support-object.v1'"
            )
        for name in [
            "support_object_id",
            "mechanism_family_id",
            "preparation_id",
            "protocol_id",
            "evaluation_regime_id",
        ]:
            value = getattr(self, name)
            if not value:
                raise ValueError(f"{name} must be a non-empty string")
        if not self.support_index_refs:
            raise ValueError("support_index_refs must not be empty")
        if any(not ref for ref in self.support_index_refs):
            raise ValueError(
                "support_index_refs must contain only non-empty reference strings"
            )
        duplicates = collect_list_duplicates(self.support_index_refs)
        if duplicates:
            raise ValueError(
                f"support_index_refs must be unique: {', '.join(duplicates)}"
            )
        source_refs = {
            key: value
            for key, value in {
                "source_config_ref": self.source_config_ref,
                "source_bundle_ref": self.source_bundle_ref,
            }.items()
            if value is not None
        }
        if not source_refs:
            raise ValueError(
                "at least one of source_config_ref or source_bundle_ref must be present"
            )
        ensure_repo_relative_mapping(source_refs, field_name="source_refs")
        if (
            not self.fixed_protocol_step_ids
            and not self.fixed_step_indices
            and not self.fixed_resolution_ids
        ):
            raise ValueError(
                "at least one fixed protocol step, step index, or resolution must be recorded"
            )
        if any(not step_id for step_id in self.fixed_protocol_step_ids):
            raise ValueError(
                "fixed_protocol_step_ids must contain only non-empty strings"
            )
        step_duplicates = collect_list_duplicates(self.fixed_protocol_step_ids)
        if step_duplicates:
            raise ValueError(
                f"fixed_protocol_step_ids must be unique: {', '.join(step_duplicates)}"
            )
        if any(
            isinstance(step_index, bool) or step_index < 0
            for step_index in self.fixed_step_indices
        ):
            raise ValueError(
                "fixed_step_indices must contain only non-negative integers"
            )
        resolution_duplicates = collect_list_duplicates(self.fixed_resolution_ids)
        if resolution_duplicates:
            raise ValueError(
                f"fixed_resolution_ids must be unique: {', '.join(resolution_duplicates)}"
            )
        if any(not resolution_id for resolution_id in self.fixed_resolution_ids):
            raise ValueError("fixed_resolution_ids must contain only non-empty strings")
        if any(not note for note in self.notes):
            raise ValueError("notes must contain only non-empty strings")
        if any(not flag for flag in self.flags):
            raise ValueError("flags must contain only non-empty strings")
        ensure_metadata_shape(self.metadata)
        return self


class FrozenSliceComparisonRegime(SixBirdsModel):
    regime_format_version: str
    regime_id: str
    support_object_ref: str
    theorem_object: Literal["event_package"] = "event_package"
    held_fixed_fields: list[str]
    varying_fields: list[str]
    supported_axes: list[FrozenSliceSupportedAxis]
    same_support_required: bool = True
    same_evaluation_regime_required: bool = True
    no_moving_ledger: bool = True
    allowed_variation_modes: list[FrozenSliceVariationMode]
    same_support_admissibility_fields: list[str]
    notes: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_regime(self) -> "FrozenSliceComparisonRegime":
        if self.regime_format_version != "frozen-slice-comparison-regime.v1":
            raise ValueError(
                "regime_format_version must equal 'frozen-slice-comparison-regime.v1'"
            )
        if not self.regime_id:
            raise ValueError("regime_id must be a non-empty string")
        ensure_repo_relative_mapping(
            {"support_object_ref": self.support_object_ref},
            field_name="support_object_ref",
        )
        if not self.held_fixed_fields:
            raise ValueError("held_fixed_fields must not be empty")
        if not self.varying_fields:
            raise ValueError("varying_fields must not be empty")
        if not self.supported_axes:
            raise ValueError("supported_axes must not be empty")
        if not self.allowed_variation_modes:
            raise ValueError("allowed_variation_modes must not be empty")
        if not self.same_support_admissibility_fields:
            raise ValueError("same_support_admissibility_fields must not be empty")
        for name in [
            "held_fixed_fields",
            "varying_fields",
            "supported_axes",
            "allowed_variation_modes",
            "same_support_admissibility_fields",
        ]:
            values = getattr(self, name)
            if any(not isinstance(value, str) or not value for value in values):
                raise ValueError(f"{name} must contain only non-empty strings")
            duplicates = collect_list_duplicates(values)
            if duplicates:
                raise ValueError(f"{name} must be unique: {', '.join(duplicates)}")
        overlap = collect_list_duplicates(self.held_fixed_fields + self.varying_fields)
        if overlap:
            raise ValueError(
                f"held_fixed_fields and varying_fields must be disjoint: {', '.join(overlap)}"
            )
        required_fixed = {
            "preparation_id",
            "protocol_id",
            "evaluation_regime_id",
        }
        if not required_fixed.issubset(set(self.held_fixed_fields)):
            raise ValueError(
                "held_fixed_fields must include preparation_id, protocol_id, and evaluation_regime_id"
            )
        if not {
            "mechanism_family_id",
            "mechanism_config_id",
        }.intersection(self.held_fixed_fields):
            raise ValueError(
                "held_fixed_fields must include mechanism_family_id or mechanism_config_id"
            )
        if "cross_resolution_strict_extension" in self.allowed_variation_modes and (
            "resolution_id" not in self.varying_fields
        ):
            raise ValueError(
                "varying_fields must include resolution_id when cross_resolution_strict_extension is allowed"
            )
        if not self.same_support_required:
            raise ValueError(
                "same_support_required must remain true for a frozen-slice comparison regime"
            )
        if not self.same_evaluation_regime_required:
            raise ValueError(
                "same_evaluation_regime_required must remain true for a frozen-slice comparison regime"
            )
        if not self.no_moving_ledger:
            raise ValueError(
                "no_moving_ledger must remain true for a frozen-slice comparison regime"
            )
        if any(not note for note in self.notes):
            raise ValueError("notes must contain only non-empty strings")
        if any(not flag for flag in self.flags):
            raise ValueError("flags must contain only non-empty strings")
        ensure_metadata_shape(self.metadata)
        return self


class HierarchyPropositionEntry(SixBirdsModel):
    proposition_id: str
    label: str
    kind: HierarchyPropositionKind
    statement: str
    support_type: HierarchyPropositionSupportType
    primary_refs: list[str]
    supporting_refs: list[str] = Field(default_factory=list)
    caveat_flags: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_entry(self) -> "HierarchyPropositionEntry":
        if not self.proposition_id:
            raise ValueError("proposition_id must be a non-empty string")
        if not self.label:
            raise ValueError("label must be a non-empty string")
        if not self.statement:
            raise ValueError("statement must be a non-empty string")
        if not self.primary_refs:
            raise ValueError("primary_refs must not be empty")
        if any(not isinstance(ref, str) or not ref for ref in self.primary_refs):
            raise ValueError("primary_refs must contain only non-empty strings")
        if any(not isinstance(ref, str) or not ref for ref in self.supporting_refs):
            raise ValueError("supporting_refs must contain only non-empty strings")
        ensure_repo_relative_mapping(
            {
                f"primary_ref_{index}": ref
                for index, ref in enumerate(self.primary_refs)
            },
            field_name="primary_refs",
        )
        ensure_repo_relative_mapping(
            {
                f"supporting_ref_{index}": ref
                for index, ref in enumerate(self.supporting_refs)
            },
            field_name="supporting_refs",
        )
        if any(not flag for flag in self.caveat_flags):
            raise ValueError("caveat_flags must contain only non-empty strings")
        if any(not note for note in self.notes):
            raise ValueError("notes must contain only non-empty strings")
        return self


class HierarchyPropositionIndex(SixBirdsModel):
    index_format_version: str
    index_id: str
    theorem_object_label: Literal["event_package"] = "event_package"
    entries: list[HierarchyPropositionEntry]
    notes: list[str] = Field(default_factory=list)
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_index(self) -> "HierarchyPropositionIndex":
        if self.index_format_version != "hierarchy-proposition-index.v1":
            raise ValueError(
                "index_format_version must equal 'hierarchy-proposition-index.v1'"
            )
        if not self.index_id:
            raise ValueError("index_id must be a non-empty string")
        if len(self.entries) != 4:
            raise ValueError("entries must contain exactly four propositions")
        id_duplicates = collect_list_duplicates(
            [entry.proposition_id for entry in self.entries]
        )
        if id_duplicates:
            raise ValueError(
                f"entries must be unique by proposition_id: {', '.join(id_duplicates)}"
            )
        label_duplicates = collect_list_duplicates(
            [entry.label for entry in self.entries]
        )
        if label_duplicates:
            raise ValueError(
                f"entries must be unique by label: {', '.join(label_duplicates)}"
            )
        if any(not note for note in self.notes):
            raise ValueError("notes must contain only non-empty strings")
        ensure_metadata_shape(self.metadata)
        return self


class PackageConflictObject(SixBirdsModel):
    object_format_version: str
    package_conflict_object_id: str
    theorem_object_label: Literal["event_package"] = "event_package"
    frozen_slice_required: bool = True
    fixed_support_fields: list[str]
    projection_difference_fields: list[str]
    lens_difference_fields: list[str]
    packaging_surface_fields: list[str]
    package_action_fields: list[str]
    minimum_conflict_requirements: list[str]
    notes: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_object(self) -> "PackageConflictObject":
        if self.object_format_version != "package-conflict-object.v1":
            raise ValueError(
                "object_format_version must equal 'package-conflict-object.v1'"
            )
        if not self.package_conflict_object_id:
            raise ValueError("package_conflict_object_id must be a non-empty string")
        if not self.frozen_slice_required:
            raise ValueError("frozen_slice_required must remain true")
        for name in [
            "fixed_support_fields",
            "projection_difference_fields",
            "lens_difference_fields",
            "packaging_surface_fields",
            "package_action_fields",
            "minimum_conflict_requirements",
        ]:
            values = getattr(self, name)
            if not values:
                raise ValueError(f"{name} must not be empty")
            if any(not isinstance(value, str) or not value for value in values):
                raise ValueError(f"{name} must contain only non-empty strings")
            duplicates = collect_list_duplicates(values)
            if duplicates:
                raise ValueError(f"{name} must be unique: {', '.join(duplicates)}")
        if not {"support_object_id", "evaluation_regime_id"}.issubset(
            self.fixed_support_fields
        ):
            raise ValueError(
                "fixed_support_fields must include support_object_id and evaluation_regime_id"
            )
        if "packaging_source" not in self.packaging_surface_fields:
            raise ValueError(
                "packaging_surface_fields must include packaging_source so surface metadata remains explicit"
            )
        if not set(self.package_action_fields).issubset(self.packaging_surface_fields):
            raise ValueError(
                "package_action_fields must be a subset of packaging_surface_fields"
            )
        if "package_action_divergence" not in self.minimum_conflict_requirements:
            raise ValueError(
                "minimum_conflict_requirements must include package_action_divergence"
            )
        if any(not note for note in self.notes):
            raise ValueError("notes must contain only non-empty strings")
        if any(not flag for flag in self.flags):
            raise ValueError("flags must contain only non-empty strings")
        ensure_metadata_shape(self.metadata)
        return self


class PackageConflictRelation(SixBirdsModel):
    relation_format_version: str
    relation_id: str
    package_conflict_object_ref: str
    left_context_ref: str
    right_context_ref: str
    comparison_mode: FrozenSliceVariationMode
    same_frozen_support: bool
    same_evaluation_regime: bool
    divergence_fields: list[str]
    package_action_evidence: list[str]
    relation_level: PackageConflictRelationLevel
    classification: PackageConflictClassification
    obstruction_status: PackageConflictObstructionStatus
    primary_refs: list[str]
    supporting_refs: list[str] = Field(default_factory=list)
    caveat_flags: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_relation(self) -> "PackageConflictRelation":
        if self.relation_format_version != "package-conflict-relation.v1":
            raise ValueError(
                "relation_format_version must equal 'package-conflict-relation.v1'"
            )
        for name in ["relation_id", "left_context_ref", "right_context_ref"]:
            value = getattr(self, name)
            if not value:
                raise ValueError(f"{name} must be a non-empty string")
        ensure_repo_relative_mapping(
            {"package_conflict_object_ref": self.package_conflict_object_ref},
            field_name="package_conflict_object_ref",
        )
        for name in [
            "divergence_fields",
            "primary_refs",
            "package_action_evidence",
            "supporting_refs",
        ]:
            values = getattr(self, name)
            if name == "package_action_evidence" and self.relation_level not in {
                "package_conflict_proper",
                "packaging_obstruction",
            }:
                if any(not isinstance(value, str) or not value for value in values):
                    raise ValueError(
                        "package_action_evidence must contain only non-empty strings"
                    )
                continue
            if not values:
                raise ValueError(f"{name} must not be empty")
            if any(not isinstance(value, str) or not value for value in values):
                raise ValueError(f"{name} must contain only non-empty strings")
        ensure_repo_relative_mapping(
            {
                f"primary_ref_{index}": ref
                for index, ref in enumerate(self.primary_refs)
            },
            field_name="primary_refs",
        )
        ensure_repo_relative_mapping(
            {
                f"supporting_ref_{index}": ref
                for index, ref in enumerate(self.supporting_refs)
            },
            field_name="supporting_refs",
        )
        if any(not field for field in self.divergence_fields):
            raise ValueError("divergence_fields must contain only non-empty strings")
        if any(not evidence for evidence in self.package_action_evidence):
            raise ValueError(
                "package_action_evidence must contain only non-empty strings"
            )
        if any(not flag for flag in self.caveat_flags):
            raise ValueError("caveat_flags must contain only non-empty strings")
        if any(not note for note in self.notes):
            raise ValueError("notes must contain only non-empty strings")
        if self.relation_level in {"package_conflict_proper", "packaging_obstruction"}:
            if not self.same_frozen_support or not self.same_evaluation_regime:
                raise ValueError(
                    "package_conflict_proper and packaging_obstruction require same frozen support and same evaluation regime"
                )
            if not self.package_action_evidence:
                raise ValueError(
                    "package_action_evidence must be present for package conflict proper or packaging obstruction"
                )
        if self.relation_level == "projection_difference_only":
            if self.classification != "projection_difference_only":
                raise ValueError(
                    "projection_difference_only level must use projection_difference_only classification"
                )
            if self.obstruction_status != "none":
                raise ValueError(
                    "projection_difference_only may not carry obstruction status"
                )
        if self.relation_level == "lens_mismatch_only":
            if self.classification != "lens_mismatch_only":
                raise ValueError(
                    "lens_mismatch_only level must use lens_mismatch_only classification"
                )
            if self.obstruction_status != "none":
                raise ValueError("lens_mismatch_only may not carry obstruction status")
        if self.classification == "selector_branch_package_divergence" and not {
            "selector_branch",
            "packaging_source",
        }.intersection(self.divergence_fields):
            raise ValueError(
                "selector_branch_package_divergence requires selector_branch or packaging_source divergence"
            )
        if self.classification == "operator_or_family_package_divergence" and not {
            "packaging_operator_id",
            "packaging_family_id",
        }.intersection(self.divergence_fields):
            raise ValueError(
                "operator_or_family_package_divergence requires packaging_operator_id or packaging_family_id divergence"
            )
        if self.classification == "strict_extension_package_conflict" and (
            self.relation_level
            not in {"package_conflict_proper", "packaging_obstruction"}
        ):
            raise ValueError(
                "strict_extension_package_conflict requires package_conflict_proper or packaging_obstruction level"
            )
        if self.classification == "package_conflict_with_obstruction" and (
            self.relation_level != "packaging_obstruction"
        ):
            raise ValueError(
                "package_conflict_with_obstruction requires packaging_obstruction level"
            )
        if self.relation_level == "packaging_obstruction" and (
            self.obstruction_status != "accepted_proposal_obstruction"
        ):
            raise ValueError(
                "packaging_obstruction requires accepted_proposal_obstruction status"
            )
        return self
