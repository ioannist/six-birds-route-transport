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


QuotientWitnessClassification = Literal[
    "accepted_proposal_obstruction",
    "candidate_subset_quotient_witness",
    "no_quotient_obstruction",
]
QuotientFailureReason = Literal["no_respecting_tuples", "coverage_failure"]
QuotientContextScope = Literal["all_accepted_contexts"]
QuotientCandidatePoolMode = Literal["same_slice_candidate_pool"]
QuotientCandidateEventScope = Literal["singleton_only", "all"]
QuotientEvaluationMode = Literal[
    "accepted_only",
    "natural_pairing_control",
    "forced_candidate_subset",
]


class QuotientSameSliceSelection(SixBirdsModel):
    preparation_id: str
    protocol_id: str
    protocol_step_id: str
    step_index: int
    resolution_id: str | None = None
    candidate_event_scope: QuotientCandidateEventScope = "singleton_only"

    @model_validator(mode="after")
    def validate_selection(self) -> "QuotientSameSliceSelection":
        for name in ["preparation_id", "protocol_id", "protocol_step_id"]:
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise ValueError(f"{name} must be a non-empty string")
        if isinstance(self.step_index, bool) or self.step_index < 0:
            raise ValueError("step_index must be a non-negative integer")
        if self.resolution_id is not None and not self.resolution_id:
            raise ValueError("resolution_id must be non-empty when present")
        return self


class QuotientSubsetSearchSettings(SixBirdsModel):
    enabled: bool = True
    max_subset_size: int = 2
    stop_at_first_witness: bool = True

    @model_validator(mode="after")
    def validate_settings(self) -> "QuotientSubsetSearchSettings":
        if isinstance(self.max_subset_size, bool) or self.max_subset_size <= 0:
            raise ValueError("max_subset_size must be a positive integer")
        return self


class QuotientClassEntry(SixBirdsModel):
    quotient_class_id: str
    member_trajectory_ids: list[str]
    induced_context_atom_assignments: dict[str, str]
    induced_context_labels: dict[str, str] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_entry(self) -> "QuotientClassEntry":
        if not self.quotient_class_id:
            raise ValueError("quotient_class_id must be a non-empty string")
        if not self.member_trajectory_ids:
            raise ValueError("member_trajectory_ids must not be empty")
        duplicates = collect_list_duplicates(self.member_trajectory_ids)
        if duplicates:
            raise ValueError(
                f"member_trajectory_ids must be unique: {', '.join(duplicates)}"
            )
        if any(not value for value in self.member_trajectory_ids):
            raise ValueError(
                "member_trajectory_ids must contain only non-empty strings"
            )
        if not self.induced_context_atom_assignments:
            raise ValueError("induced_context_atom_assignments must not be empty")
        for name, mapping in [
            ("induced_context_atom_assignments", self.induced_context_atom_assignments),
            ("induced_context_labels", self.induced_context_labels),
        ]:
            for key, value in mapping.items():
                if not key or not value:
                    raise ValueError(f"{name} must contain only non-empty strings")
        if any(not note for note in self.notes):
            raise ValueError("notes must contain only non-empty strings")
        return self


class QuotientClassLedger(SixBirdsModel):
    ledger_format_version: str
    ledger_id: str
    source_discovered_context_family_artifact: str
    source_event_package_artifact: str
    source_shared_event_candidates_artifact: str
    source_bundle_artifact: str
    source_observable_ledger_artifacts: list[str]
    same_slice_selection: QuotientSameSliceSelection
    quotient_context_scope: QuotientContextScope = "all_accepted_contexts"
    raw_support_count: int
    quotient_class_count: int
    selected_context_ids: list[str]
    quotient_classes: list[QuotientClassEntry]
    notes: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_ledger(self) -> "QuotientClassLedger":
        if self.ledger_format_version != "quotient-class-ledger.v1":
            raise ValueError(
                "ledger_format_version must equal 'quotient-class-ledger.v1'"
            )
        for name in [
            "ledger_id",
            "source_discovered_context_family_artifact",
            "source_event_package_artifact",
            "source_shared_event_candidates_artifact",
            "source_bundle_artifact",
        ]:
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise ValueError(f"{name} must be a non-empty string")
        ensure_repo_relative_mapping(
            {
                "source_discovered_context_family_artifact": self.source_discovered_context_family_artifact,
                "source_event_package_artifact": self.source_event_package_artifact,
                "source_shared_event_candidates_artifact": self.source_shared_event_candidates_artifact,
                "source_bundle_artifact": self.source_bundle_artifact,
                **{
                    f"observable_ledger_{index}": path
                    for index, path in enumerate(
                        self.source_observable_ledger_artifacts
                    )
                },
            },
            field_name="quotient_class_ledger_artifacts",
        )
        for name in ["raw_support_count", "quotient_class_count"]:
            value = getattr(self, name)
            if isinstance(value, bool) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if self.quotient_class_count != len(self.quotient_classes):
            raise ValueError("quotient_class_count must equal len(quotient_classes)")
        if self.raw_support_count < self.quotient_class_count:
            raise ValueError("raw_support_count must be >= quotient_class_count")
        duplicates = collect_list_duplicates(self.selected_context_ids)
        if duplicates:
            raise ValueError(
                f"selected_context_ids must be unique: {', '.join(duplicates)}"
            )
        if any(not value for value in self.selected_context_ids):
            raise ValueError("selected_context_ids must contain only non-empty strings")
        class_ids = [entry.quotient_class_id for entry in self.quotient_classes]
        duplicates = collect_list_duplicates(class_ids)
        if duplicates:
            raise ValueError(
                f"quotient_class_id values must be unique: {', '.join(duplicates)}"
            )
        ensure_metadata_shape(self.metadata)
        if any(not value for value in self.notes + self.flags):
            raise ValueError("notes and flags must contain only non-empty strings")
        return self


class QuotientFeasibilityAudit(SixBirdsModel):
    audit_format_version: str
    audit_id: str
    source_event_package_artifact: str
    source_discovered_context_family_artifact: str
    source_shared_event_candidates_artifact: str
    source_package_provenance_artifact: str | None = None
    same_slice_selection: QuotientSameSliceSelection
    quotient_context_scope: QuotientContextScope = "all_accepted_contexts"
    candidate_pool_mode: QuotientCandidatePoolMode = "same_slice_candidate_pool"
    subset_search: QuotientSubsetSearchSettings = Field(
        default_factory=QuotientSubsetSearchSettings
    )
    forced_candidate_ids: list[str] = Field(default_factory=list)
    natural_pairing_candidate_ids: list[str] = Field(default_factory=list)
    output_category: str = "results"
    output_label: str | None = None
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_audit(self) -> "QuotientFeasibilityAudit":
        if self.audit_format_version != "quotient-feasibility-audit.v1":
            raise ValueError(
                "audit_format_version must equal 'quotient-feasibility-audit.v1'"
            )
        for name in [
            "audit_id",
            "source_event_package_artifact",
            "source_discovered_context_family_artifact",
            "source_shared_event_candidates_artifact",
        ]:
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise ValueError(f"{name} must be a non-empty string")
        mapping = {
            "source_event_package_artifact": self.source_event_package_artifact,
            "source_discovered_context_family_artifact": self.source_discovered_context_family_artifact,
            "source_shared_event_candidates_artifact": self.source_shared_event_candidates_artifact,
        }
        if self.source_package_provenance_artifact is not None:
            if not self.source_package_provenance_artifact:
                raise ValueError(
                    "source_package_provenance_artifact must be non-empty when present"
                )
            mapping["source_package_provenance_artifact"] = (
                self.source_package_provenance_artifact
            )
        ensure_repo_relative_mapping(mapping, field_name="quotient_feasibility_sources")
        for name, values in [
            ("forced_candidate_ids", self.forced_candidate_ids),
            ("natural_pairing_candidate_ids", self.natural_pairing_candidate_ids),
        ]:
            duplicates = collect_list_duplicates(values)
            if duplicates:
                raise ValueError(f"{name} must be unique: {', '.join(duplicates)}")
            if any(not value for value in values):
                raise ValueError(f"{name} must contain only non-empty strings")
        ensure_metadata_shape(self.metadata)
        return self


class QuotientEvaluationResult(SixBirdsModel):
    mode: QuotientEvaluationMode
    candidate_ids: list[str]
    proposal_ids: list[str]
    survivor_count: int
    surviving_quotient_class_ids: list[str]
    exact_feasible: bool
    exact_failure_reason: QuotientFailureReason | None = None
    uncovered_atom_refs: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_result(self) -> "QuotientEvaluationResult":
        for name, values in [
            ("candidate_ids", self.candidate_ids),
            ("proposal_ids", self.proposal_ids),
            ("surviving_quotient_class_ids", self.surviving_quotient_class_ids),
            ("uncovered_atom_refs", self.uncovered_atom_refs),
        ]:
            duplicates = collect_list_duplicates(values)
            if duplicates:
                raise ValueError(f"{name} must be unique: {', '.join(duplicates)}")
            if any(not value for value in values):
                raise ValueError(f"{name} must contain only non-empty strings")
        if isinstance(self.survivor_count, bool) or self.survivor_count < 0:
            raise ValueError("survivor_count must be a non-negative integer")
        if self.survivor_count != len(self.surviving_quotient_class_ids):
            raise ValueError(
                "survivor_count must equal len(surviving_quotient_class_ids)"
            )
        if self.exact_feasible and self.exact_failure_reason is not None:
            raise ValueError(
                "exact_failure_reason must be null when exact_feasible is true"
            )
        if not self.exact_feasible and self.exact_failure_reason is None:
            raise ValueError(
                "exact_failure_reason must be present when exact_feasible is false"
            )
        return self


class QuotientWitnessSearchResult(SixBirdsModel):
    mode: Literal["candidate_subset_search"] = "candidate_subset_search"
    searched_candidate_count: int
    searched_subset_count: int
    max_subset_size: int
    witness_found: bool
    minimal_witness_size: int | None = None
    witness_candidate_ids: list[str] = Field(default_factory=list)
    witness_proposal_ids: list[str] = Field(default_factory=list)
    witness_survivor_count: int | None = None
    witness_failure_reason: QuotientFailureReason | None = None

    @model_validator(mode="after")
    def validate_search(self) -> "QuotientWitnessSearchResult":
        for name in [
            "searched_candidate_count",
            "searched_subset_count",
            "max_subset_size",
        ]:
            value = getattr(self, name)
            if isinstance(value, bool) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if self.max_subset_size == 0:
            raise ValueError("max_subset_size must be positive")
        for name in ["witness_candidate_ids", "witness_proposal_ids"]:
            values = getattr(self, name)
            duplicates = collect_list_duplicates(values)
            if duplicates:
                raise ValueError(f"{name} must be unique: {', '.join(duplicates)}")
            if any(not value for value in values):
                raise ValueError(f"{name} must contain only non-empty strings")
        if self.witness_found:
            if self.minimal_witness_size is None:
                raise ValueError(
                    "minimal_witness_size must be present when witness_found is true"
                )
            if self.minimal_witness_size != len(self.witness_candidate_ids):
                raise ValueError(
                    "minimal_witness_size must equal len(witness_candidate_ids)"
                )
            if self.witness_survivor_count is None:
                raise ValueError(
                    "witness_survivor_count must be present when witness_found is true"
                )
            if self.witness_failure_reason is None:
                raise ValueError(
                    "witness_failure_reason must be present when witness_found is true"
                )
        else:
            if (
                self.minimal_witness_size is not None
                or self.witness_candidate_ids
                or self.witness_proposal_ids
                or self.witness_survivor_count is not None
                or self.witness_failure_reason is not None
            ):
                raise ValueError(
                    "witness fields must be empty when witness_found is false"
                )
        return self


class QuotientSummaryBlock(SixBirdsModel):
    raw_support_count: int
    quotient_class_count: int
    selected_context_count: int
    selected_context_ids: list[str]

    @model_validator(mode="after")
    def validate_summary(self) -> "QuotientSummaryBlock":
        for name in [
            "raw_support_count",
            "quotient_class_count",
            "selected_context_count",
        ]:
            value = getattr(self, name)
            if isinstance(value, bool) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        duplicates = collect_list_duplicates(self.selected_context_ids)
        if duplicates:
            raise ValueError(
                f"selected_context_ids must be unique: {', '.join(duplicates)}"
            )
        if self.selected_context_count != len(self.selected_context_ids):
            raise ValueError(
                "selected_context_count must equal len(selected_context_ids)"
            )
        return self


class QuotientFeasibilityResult(SixBirdsModel):
    result_format_version: str
    audit_id: str
    source_event_package_artifact: str
    source_discovered_context_family_artifact: str
    source_shared_event_candidates_artifact: str
    source_package_provenance_artifact: str | None = None
    quotient_class_ledger_artifact: str
    quotient_summary: QuotientSummaryBlock
    accepted_proposal_set_result: QuotientEvaluationResult
    natural_pairing_result: QuotientEvaluationResult | None = None
    forced_candidate_subset_result: QuotientEvaluationResult | None = None
    candidate_subset_witness_result: QuotientWitnessSearchResult
    witness_classification: QuotientWitnessClassification
    notes: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_result(self) -> "QuotientFeasibilityResult":
        if self.result_format_version != "quotient-feasibility-result.v1":
            raise ValueError(
                "result_format_version must equal 'quotient-feasibility-result.v1'"
            )
        mapping = {
            "source_event_package_artifact": self.source_event_package_artifact,
            "source_discovered_context_family_artifact": self.source_discovered_context_family_artifact,
            "source_shared_event_candidates_artifact": self.source_shared_event_candidates_artifact,
            "quotient_class_ledger_artifact": self.quotient_class_ledger_artifact,
        }
        if self.source_package_provenance_artifact is not None:
            if not is_repo_relative_path(self.source_package_provenance_artifact):
                raise ValueError(
                    "source_package_provenance_artifact must be a normalized repo-relative path when present"
                )
            mapping["source_package_provenance_artifact"] = (
                self.source_package_provenance_artifact
            )
        ensure_repo_relative_mapping(mapping, field_name="quotient_result_artifacts")
        if self.witness_classification == "accepted_proposal_obstruction" and (
            self.accepted_proposal_set_result.exact_feasible
        ):
            raise ValueError(
                "accepted_proposal_obstruction requires accepted_proposal_set_result.exact_feasible == false"
            )
        if self.witness_classification == "candidate_subset_quotient_witness":
            if self.accepted_proposal_set_result.exact_feasible is False:
                raise ValueError(
                    "candidate_subset_quotient_witness requires accepted proposals to remain feasible"
                )
            if not self.candidate_subset_witness_result.witness_found:
                raise ValueError(
                    "candidate_subset_quotient_witness requires witness_found == true"
                )
        if self.witness_classification == "no_quotient_obstruction":
            if self.accepted_proposal_set_result.exact_feasible is False:
                raise ValueError(
                    "no_quotient_obstruction requires accepted proposals to remain feasible"
                )
            if self.candidate_subset_witness_result.witness_found:
                raise ValueError(
                    "no_quotient_obstruction requires witness_found == false"
                )
        ensure_metadata_shape(self.metadata)
        if any(not value for value in self.notes + self.flags):
            raise ValueError("notes and flags must contain only non-empty strings")
        return self
