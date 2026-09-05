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

EvidenceGapHandling = Literal[
    "committed_summary_substitution",
    "fresh_rerun",
    "not_needed",
]
TheoremExperimentRelation = Literal[
    "direct_theorem_anchor",
    "direct_numerical_support",
    "supportive_case",
    "control_support",
    "formal_clarification",
]
CaveatScope = Literal[
    "theorem",
    "mechanism",
    "lens",
    "packaging",
    "controls",
    "general",
]


class TheoremExperimentMapEntry(SixBirdsModel):
    theorem_anchor_id: str
    theorem_anchor_label: str
    relation_type: TheoremExperimentRelation
    primary_artifact_refs: dict[str, str]
    supporting_artifact_refs: dict[str, str] = Field(default_factory=dict)
    caveat_flags: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_entry(self) -> "TheoremExperimentMapEntry":
        if not self.theorem_anchor_id:
            raise ValueError("theorem_anchor_id must be a non-empty string")
        if not self.theorem_anchor_label:
            raise ValueError("theorem_anchor_label must be a non-empty string")
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


class TheoremExperimentMap(SixBirdsModel):
    map_format_version: str
    map_id: str
    theorem_object_label: str
    entries: list[TheoremExperimentMapEntry]
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_map(self) -> "TheoremExperimentMap":
        if self.map_format_version != "theorem-experiment-map.v1":
            raise ValueError(
                "map_format_version must equal 'theorem-experiment-map.v1'"
            )
        if not self.map_id:
            raise ValueError("map_id must be a non-empty string")
        if not self.theorem_object_label:
            raise ValueError("theorem_object_label must be a non-empty string")
        if not self.entries:
            raise ValueError("entries must not be empty")
        duplicates = collect_list_duplicates(
            [entry.theorem_anchor_id for entry in self.entries]
        )
        if duplicates:
            raise ValueError(
                f"entries must be unique by theorem_anchor_id: {', '.join(duplicates)}"
            )
        ensure_metadata_shape(self.metadata)
        return self


class CaveatRegistryEntry(SixBirdsModel):
    caveat_id: str
    scope: CaveatScope
    label: str
    statement: str
    primary_artifact_refs: dict[str, str]
    supporting_artifact_refs: dict[str, str] = Field(default_factory=dict)
    caveat_flags: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_entry(self) -> "CaveatRegistryEntry":
        if not self.caveat_id:
            raise ValueError("caveat_id must be a non-empty string")
        if not self.label:
            raise ValueError("label must be a non-empty string")
        if not self.statement:
            raise ValueError("statement must be a non-empty string")
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


class CaveatRegistry(SixBirdsModel):
    registry_format_version: str
    registry_id: str
    entries: list[CaveatRegistryEntry]
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_registry(self) -> "CaveatRegistry":
        if self.registry_format_version != "caveat-registry.v1":
            raise ValueError("registry_format_version must equal 'caveat-registry.v1'")
        if not self.registry_id:
            raise ValueError("registry_id must be a non-empty string")
        if not self.entries:
            raise ValueError("entries must not be empty")
        duplicates = collect_list_duplicates(
            [entry.caveat_id for entry in self.entries]
        )
        if duplicates:
            raise ValueError(
                f"entries must be unique by caveat_id: {', '.join(duplicates)}"
            )
        ensure_metadata_shape(self.metadata)
        return self


class PaperEvidencePack(SixBirdsModel):
    pack_format_version: str
    evidence_pack_id: str
    theorem_experiment_map_ref: str
    flagship_witnesses_ref: str
    best_evidence_by_axis_ref: str
    control_bundle_summary_ref: str
    caveat_registry_ref: str
    theorem_side_anchor_refs: dict[str, str]
    mechanism_evidence_refs: dict[str, str]
    lens_evidence_refs: dict[str, str]
    packaging_evidence_refs: dict[str, str]
    control_bundle_evidence_refs: dict[str, str]
    hierarchy_claim_strength_refs: dict[str, str]
    figure_candidate_refs: dict[str, str]
    table_candidate_refs: dict[str, str]
    transient_gap_resolution: dict[str, EvidenceGapHandling]
    notes: list[str] = Field(default_factory=list)
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_pack(self) -> "PaperEvidencePack":
        if self.pack_format_version != "paper-evidence-pack.v1":
            raise ValueError("pack_format_version must equal 'paper-evidence-pack.v1'")
        if not self.evidence_pack_id:
            raise ValueError("evidence_pack_id must be a non-empty string")
        for name in [
            "theorem_experiment_map_ref",
            "flagship_witnesses_ref",
            "best_evidence_by_axis_ref",
            "control_bundle_summary_ref",
            "caveat_registry_ref",
        ]:
            value = getattr(self, name)
            if not is_repo_relative_path(value):
                raise ValueError(f"{name} must be a normalized repo-relative path")
        for field_name in [
            "theorem_side_anchor_refs",
            "mechanism_evidence_refs",
            "lens_evidence_refs",
            "packaging_evidence_refs",
            "control_bundle_evidence_refs",
            "hierarchy_claim_strength_refs",
            "figure_candidate_refs",
            "table_candidate_refs",
        ]:
            mapping = getattr(self, field_name)
            if not mapping:
                raise ValueError(f"{field_name} must not be empty")
            ensure_repo_relative_mapping(mapping, field_name=field_name)
        if "figure_candidates_manifest" not in self.figure_candidate_refs:
            raise ValueError(
                "figure_candidate_refs must contain figure_candidates_manifest"
            )
        if "table_candidates_manifest" not in self.table_candidate_refs:
            raise ValueError(
                "table_candidate_refs must contain table_candidates_manifest"
            )
        required_gap_keys = {"t50_runtime_outputs", "th6_runtime_outputs"}
        if set(self.transient_gap_resolution) != required_gap_keys:
            raise ValueError(
                "transient_gap_resolution must contain exactly t50_runtime_outputs and th6_runtime_outputs"
            )
        if any(not note for note in self.notes):
            raise ValueError("notes must contain only non-empty strings")
        ensure_metadata_shape(self.metadata)
        return self
