from __future__ import annotations

import math

from pydantic import Field, model_validator

from ..discovery.models import ExtractionThresholds, SharedEventInferenceThresholds
from ..schemas.common import (
    MetadataValue,
    SixBirdsModel,
    collect_list_duplicates,
    ensure_metadata_shape,
    ensure_repo_relative_mapping,
)


class ProposalResidueAssignment(SixBirdsModel):
    proposal_id: str
    residue_values: list[str]
    copied_constraint_kind: str | None = None

    @model_validator(mode="after")
    def validate_assignment(self) -> "ProposalResidueAssignment":
        if not self.proposal_id:
            raise ValueError("proposal_id must be a non-empty string")
        if not self.residue_values:
            raise ValueError("residue_values must not be empty")
        duplicates = collect_list_duplicates(self.residue_values)
        if duplicates:
            raise ValueError(f"residue_values must be unique: {', '.join(duplicates)}")
        if self.copied_constraint_kind not in {None, "hard", "soft"}:
            raise ValueError("copied_constraint_kind must be 'hard', 'soft', or null")
        return self


class HiddenRecordComparisonConfig(SixBirdsModel):
    allow_relax_hard: bool = True
    hard_proposal_relax_weight: float = 1.0
    include_rm: bool = True

    @model_validator(mode="after")
    def validate_config(self) -> "HiddenRecordComparisonConfig":
        if (
            isinstance(self.hard_proposal_relax_weight, bool)
            or not math.isfinite(self.hard_proposal_relax_weight)
            or self.hard_proposal_relax_weight < 0
        ):
            raise ValueError(
                "hard_proposal_relax_weight must be a finite non-negative value"
            )
        return self


class HiddenRecordIntervention(SixBirdsModel):
    intervention_format_version: str
    intervention_id: str
    before_instance_artifact: str
    route_source_artifact: str
    residue_field_name: str
    residue_values: list[str]
    selected_context_ids: list[str]
    augmentation_policy: str
    proposal_residue_assignments: list[ProposalResidueAssignment]
    comparison_config: HiddenRecordComparisonConfig
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_intervention(self) -> "HiddenRecordIntervention":
        if self.intervention_format_version != "hidden-record-intervention.v1":
            raise ValueError(
                "intervention_format_version must equal 'hidden-record-intervention.v1'"
            )
        if not self.intervention_id:
            raise ValueError("intervention_id must be a non-empty string")
        ensure_repo_relative_mapping(
            {
                "before_instance_artifact": self.before_instance_artifact,
                "route_source_artifact": self.route_source_artifact,
            },
            field_name="artifacts",
        )
        if not self.residue_field_name:
            raise ValueError("residue_field_name must be a non-empty string")
        if not self.residue_values:
            raise ValueError("residue_values must not be empty")
        residue_duplicates = collect_list_duplicates(self.residue_values)
        if residue_duplicates:
            raise ValueError(
                f"residue_values must be unique: {', '.join(residue_duplicates)}"
            )
        if not self.selected_context_ids:
            raise ValueError("selected_context_ids must not be empty")
        context_duplicates = collect_list_duplicates(self.selected_context_ids)
        if context_duplicates:
            raise ValueError(
                f"selected_context_ids must be unique: {', '.join(context_duplicates)}"
            )
        if self.augmentation_policy != "split_contexts_by_residue":
            raise ValueError(
                "augmentation_policy must equal 'split_contexts_by_residue'"
            )
        if not self.proposal_residue_assignments:
            raise ValueError("proposal_residue_assignments must not be empty")
        proposal_ids = [
            assignment.proposal_id for assignment in self.proposal_residue_assignments
        ]
        duplicates = collect_list_duplicates(proposal_ids)
        if duplicates:
            raise ValueError(
                f"proposal_residue_assignments must be unique by proposal_id: {', '.join(duplicates)}"
            )
        residue_set = set(self.residue_values)
        for assignment in self.proposal_residue_assignments:
            if not set(assignment.residue_values).issubset(residue_set):
                raise ValueError(
                    f"proposal '{assignment.proposal_id}' residue_values must be a subset of top-level residue_values"
                )
        ensure_metadata_shape(self.metadata)
        return self


class FlatteningCompletionPolicy(SixBirdsModel):
    append_action_id: str
    append_repetitions: int
    after_protocol_id: str | None = None

    @model_validator(mode="after")
    def validate_policy(self) -> "FlatteningCompletionPolicy":
        if not self.append_action_id:
            raise ValueError("append_action_id must be a non-empty string")
        if isinstance(self.append_repetitions, bool) or self.append_repetitions <= 0:
            raise ValueError("append_repetitions must be a positive integer")
        if self.after_protocol_id is not None and not self.after_protocol_id:
            raise ValueError("after_protocol_id must be a non-empty string when set")
        return self


class FlatteningRouteExtraction(SixBirdsModel):
    route_lens_id: str
    route_step_index: int
    endpoint_lens_id: str
    before_endpoint_step_index: int
    after_endpoint_step_index: int
    endpoint_id: str

    @model_validator(mode="after")
    def validate_settings(self) -> "FlatteningRouteExtraction":
        for name in ["route_lens_id", "endpoint_lens_id", "endpoint_id"]:
            if not getattr(self, name):
                raise ValueError(f"{name} must be a non-empty string")
        for name in [
            "route_step_index",
            "before_endpoint_step_index",
            "after_endpoint_step_index",
        ]:
            value = getattr(self, name)
            if isinstance(value, bool) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        return self


class FlatteningComparisonConfig(SixBirdsModel):
    allow_relax_hard: bool = True
    hard_proposal_relax_weight: float = 1.0
    include_rm: bool = True
    rm_material_decrease_min: float = 0.25

    @model_validator(mode="after")
    def validate_config(self) -> "FlatteningComparisonConfig":
        for name in ["hard_proposal_relax_weight", "rm_material_decrease_min"]:
            value = getattr(self, name)
            if isinstance(value, bool) or not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be a finite non-negative value")
        return self


class FlatteningIntervention(SixBirdsModel):
    intervention_format_version: str
    intervention_id: str
    source_config_artifact: str
    preparation_id: str
    before_protocol_id: str
    trajectory_count: int
    seed: int
    completion_policy: FlatteningCompletionPolicy
    route_extraction: FlatteningRouteExtraction
    discovery_thresholds: ExtractionThresholds
    shared_event_inference_thresholds: SharedEventInferenceThresholds
    comparison_config: FlatteningComparisonConfig
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_intervention(self) -> "FlatteningIntervention":
        if self.intervention_format_version != "flattening-intervention.v1":
            raise ValueError(
                "intervention_format_version must equal 'flattening-intervention.v1'"
            )
        if not self.intervention_id:
            raise ValueError("intervention_id must be a non-empty string")
        ensure_repo_relative_mapping(
            {"source_config_artifact": self.source_config_artifact},
            field_name="source_config_artifact",
        )
        if not self.preparation_id:
            raise ValueError("preparation_id must be a non-empty string")
        if not self.before_protocol_id:
            raise ValueError("before_protocol_id must be a non-empty string")
        if isinstance(self.trajectory_count, bool) or self.trajectory_count <= 0:
            raise ValueError("trajectory_count must be a positive integer")
        if isinstance(self.seed, bool):
            raise ValueError("seed must be an integer")
        ensure_metadata_shape(self.metadata)
        return self
