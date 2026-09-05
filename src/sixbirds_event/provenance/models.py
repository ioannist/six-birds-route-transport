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


AdmissibilityClassification = Literal[
    "admissible",
    "partially_supported",
    "unsupported",
]
AuditStatus = Literal["completed"]


class ProvenanceSourceRef(SixBirdsModel):
    artifact: str
    source_kind: str
    source_item_id: str | None = None
    pica_ref: PicaSourceRef | None = None

    @model_validator(mode="after")
    def validate_source_ref(self) -> "ProvenanceSourceRef":
        ensure_repo_relative_mapping({"artifact": self.artifact}, field_name="artifact")
        if not self.source_kind:
            raise ValueError("source_kind must be a non-empty string")
        if self.source_item_id is not None and not self.source_item_id:
            raise ValueError("source_item_id must be non-empty when present")
        return self


PICA_OBSERVABLE_ROW_FILTER_FIELDS: frozenset[str] = frozenset(
    {
        "trajectory_id",
        "step_index",
        "protocol_step_id",
        "preparation_id",
        "protocol_id",
        "level_id",
        "resolution_id",
        "closure_id",
        "lens_id",
        "observation_label",
        "route_label",
        "phase_label",
        "macrostate_label",
    }
)


class PicaSourceRef(SixBirdsModel):
    export_bundle_id: str
    campaign_id: str
    run_id: str
    observable_ledger_id: str
    closure_id: str
    lens_id: str
    level_id: str
    resolution_id: str
    preparation_id: str
    protocol_id: str
    protocol_step_id: str | None = None
    step_index: int | None = None
    packaging_selection_ledger_id: str | None = None
    packaging_selection_row_id: str | None = None
    packaging_operator_id: str | None = None
    packaging_family_id: str | None = None
    packaging_source: str | None = None
    source_row_filters: dict[str, str | int] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_pica_ref(self) -> "PicaSourceRef":
        for name in [
            "export_bundle_id",
            "campaign_id",
            "run_id",
            "observable_ledger_id",
            "closure_id",
            "lens_id",
            "level_id",
            "resolution_id",
            "preparation_id",
            "protocol_id",
        ]:
            if not getattr(self, name):
                raise ValueError(f"{name} must be a non-empty string")
        if self.protocol_step_id is None and self.step_index is None:
            raise ValueError(
                "at least one of protocol_step_id or step_index must be present"
            )
        if self.protocol_step_id is not None and not self.protocol_step_id:
            raise ValueError("protocol_step_id must be non-empty when present")
        if self.step_index is not None and (
            isinstance(self.step_index, bool) or self.step_index < 0
        ):
            raise ValueError("step_index must be a non-negative integer when present")
        for name in [
            "packaging_selection_ledger_id",
            "packaging_selection_row_id",
            "packaging_operator_id",
            "packaging_family_id",
            "packaging_source",
        ]:
            value = getattr(self, name)
            if value is not None and not value:
                raise ValueError(f"{name} must be non-empty when present")
        if (
            self.packaging_selection_row_id is not None
            and self.packaging_selection_ledger_id is None
        ):
            raise ValueError(
                "packaging_selection_row_id requires packaging_selection_ledger_id"
            )
        if (
            any(
                value is not None
                for value in [
                    self.packaging_operator_id,
                    self.packaging_family_id,
                    self.packaging_source,
                ]
            )
            and self.packaging_selection_ledger_id is None
        ):
            raise ValueError(
                "packaging_operator_id, packaging_family_id, and packaging_source require packaging_selection_ledger_id"
            )
        for key, value in self.source_row_filters.items():
            if not key:
                raise ValueError("source_row_filters keys must be non-empty strings")
            if isinstance(value, bool):
                raise ValueError(
                    "source_row_filters values must be strings or integers"
                )
            if not isinstance(value, (str, int)):
                raise ValueError(
                    "source_row_filters values must be strings or integers"
                )
            if isinstance(value, str) and not value:
                raise ValueError("source_row_filters string values must be non-empty")
        return self

    @property
    def unknown_row_filter_fields(self) -> list[str]:
        return sorted(
            key
            for key in self.source_row_filters
            if key not in PICA_OBSERVABLE_ROW_FILTER_FIELDS
        )


class RefinementProvenance(SixBirdsModel):
    ancestor_id: str
    residue_field_name: str
    residue_value: str
    source_artifact: str

    @model_validator(mode="after")
    def validate_refinement(self) -> "RefinementProvenance":
        for name in ["ancestor_id", "residue_field_name", "residue_value"]:
            if not getattr(self, name):
                raise ValueError(f"{name} must be a non-empty string")
        ensure_repo_relative_mapping(
            {"source_artifact": self.source_artifact},
            field_name="source_artifact",
        )
        return self


class ContextProvenanceEntry(SixBirdsModel):
    context_id: str
    origin_kind: str
    source_refs: list[ProvenanceSourceRef]
    ancestor_context_id: str | None = None
    refinement: RefinementProvenance | None = None
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_entry(self) -> "ContextProvenanceEntry":
        if not self.context_id:
            raise ValueError("context_id must be a non-empty string")
        if not self.origin_kind:
            raise ValueError("origin_kind must be a non-empty string")
        if self.ancestor_context_id is not None and not self.ancestor_context_id:
            raise ValueError("ancestor_context_id must be non-empty when present")
        if any(not note for note in self.notes):
            raise ValueError("notes must contain only non-empty strings")
        return self


class EventProvenanceEntry(SixBirdsModel):
    event_id: str
    origin_kind: str
    source_refs: list[ProvenanceSourceRef]
    source_context_id: str | None = None
    source_atom_ids: list[str] = Field(default_factory=list)
    ancestor_event_id: str | None = None
    refinement: RefinementProvenance | None = None
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_entry(self) -> "EventProvenanceEntry":
        if not self.event_id:
            raise ValueError("event_id must be a non-empty string")
        if not self.origin_kind:
            raise ValueError("origin_kind must be a non-empty string")
        if self.source_context_id is not None and not self.source_context_id:
            raise ValueError("source_context_id must be non-empty when present")
        duplicates = collect_list_duplicates(self.source_atom_ids)
        if duplicates:
            raise ValueError(f"source_atom_ids must be unique: {', '.join(duplicates)}")
        if any(not atom_id for atom_id in self.source_atom_ids):
            raise ValueError("source_atom_ids must contain only non-empty strings")
        if self.ancestor_event_id is not None and not self.ancestor_event_id:
            raise ValueError("ancestor_event_id must be non-empty when present")
        if any(not note for note in self.notes):
            raise ValueError("notes must contain only non-empty strings")
        return self


class ProposalProvenanceEntry(SixBirdsModel):
    proposal_id: str
    origin_kind: str
    source_refs: list[ProvenanceSourceRef]
    ancestor_proposal_id: str | None = None
    refinement: RefinementProvenance | None = None
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_entry(self) -> "ProposalProvenanceEntry":
        if not self.proposal_id:
            raise ValueError("proposal_id must be a non-empty string")
        if not self.origin_kind:
            raise ValueError("origin_kind must be a non-empty string")
        if self.ancestor_proposal_id is not None and not self.ancestor_proposal_id:
            raise ValueError("ancestor_proposal_id must be non-empty when present")
        if any(not note for note in self.notes):
            raise ValueError("notes must contain only non-empty strings")
        return self


class PackageProvenance(SixBirdsModel):
    provenance_format_version: str
    package_artifact: str
    package_id: str
    provenance_mode: str
    source_artifacts: dict[str, str]
    context_entries: list[ContextProvenanceEntry]
    event_entries: list[EventProvenanceEntry]
    proposal_entries: list[ProposalProvenanceEntry]
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_manifest(self) -> "PackageProvenance":
        if self.provenance_format_version != "package-provenance.v1":
            raise ValueError(
                "provenance_format_version must equal 'package-provenance.v1'"
            )
        if not self.package_id:
            raise ValueError("package_id must be a non-empty string")
        if not self.provenance_mode:
            raise ValueError("provenance_mode must be a non-empty string")
        ensure_repo_relative_mapping(
            {"package_artifact": self.package_artifact},
            field_name="package_artifact",
        )
        if not self.source_artifacts:
            raise ValueError("source_artifacts must not be empty")
        ensure_repo_relative_mapping(
            self.source_artifacts, field_name="source_artifacts"
        )
        context_duplicates = collect_list_duplicates(
            [entry.context_id for entry in self.context_entries]
        )
        if context_duplicates:
            raise ValueError(
                f"context_entries must be unique by context_id: {', '.join(context_duplicates)}"
            )
        event_duplicates = collect_list_duplicates(
            [entry.event_id for entry in self.event_entries]
        )
        if event_duplicates:
            raise ValueError(
                f"event_entries must be unique by event_id: {', '.join(event_duplicates)}"
            )
        proposal_duplicates = collect_list_duplicates(
            [entry.proposal_id for entry in self.proposal_entries]
        )
        if proposal_duplicates:
            raise ValueError(
                f"proposal_entries must be unique by proposal_id: {', '.join(proposal_duplicates)}"
            )
        ensure_metadata_shape(self.metadata)
        return self


class ProvenanceAuditResult(SixBirdsModel):
    audit_format_version: str
    package_artifact: str
    provenance_artifact: str | None = None
    package_id: str
    audit_status: AuditStatus
    context_total_count: int
    context_covered_count: int
    context_missing_count: int
    event_total_count: int
    event_covered_count: int
    event_missing_count: int
    proposal_total_count: int
    proposal_covered_count: int
    proposal_missing_count: int
    unsupported_context_count: int
    unsupported_event_count: int
    unsupported_proposal_count: int
    missing_source_ref_count: int
    unresolved_source_ref_count: int
    unknown_row_filter_field_count: int = 0
    refinement_warning_count: int
    suspicious_refinement_flags: list[str] = Field(default_factory=list)
    admissibility_classification: AdmissibilityClassification
    artifact_refs: dict[str, str]
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_result(self) -> "ProvenanceAuditResult":
        if self.audit_format_version != "provenance-audit-result.v1":
            raise ValueError(
                "audit_format_version must equal 'provenance-audit-result.v1'"
            )
        for name in ["package_artifact", "package_id"]:
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise ValueError(f"{name} must be a non-empty string")
        ensure_repo_relative_mapping(
            {"package_artifact": self.package_artifact},
            field_name="package_artifact",
        )
        if self.provenance_artifact is not None and not is_repo_relative_path(
            self.provenance_artifact
        ):
            raise ValueError(
                "provenance_artifact must be a normalized repo-relative path when present"
            )
        for name in [
            "context_total_count",
            "context_covered_count",
            "context_missing_count",
            "event_total_count",
            "event_covered_count",
            "event_missing_count",
            "proposal_total_count",
            "proposal_covered_count",
            "proposal_missing_count",
            "unsupported_context_count",
            "unsupported_event_count",
            "unsupported_proposal_count",
            "missing_source_ref_count",
            "unresolved_source_ref_count",
            "unknown_row_filter_field_count",
            "refinement_warning_count",
        ]:
            value = getattr(self, name)
            if isinstance(value, bool) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        ensure_repo_relative_mapping(self.artifact_refs, field_name="artifact_refs")
        if any(not flag for flag in self.suspicious_refinement_flags):
            raise ValueError(
                "suspicious_refinement_flags must contain only non-empty strings"
            )
        if any(not note for note in self.notes):
            raise ValueError("notes must contain only non-empty strings")
        return self


ProvenanceSourceRef.model_rebuild()
