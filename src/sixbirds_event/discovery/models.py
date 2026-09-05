from __future__ import annotations

import math
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

EventBasisMode = Literal["singleton_only", "singleton_plus_small_unions"]
EventAlgebraMode = Literal["full_powerset", "conservative_truncation", "auto"]
DiscoveredEventKind = Literal["empty", "singleton", "proper_coarse", "full"]
SharedEventInferenceMode = Literal[
    "structural_primary",
    "legacy_statistical_primary",
]
PicaProjectionMode = Literal[
    "observation_label",
    "macrostate_label",
    "phase_label",
    "payload_numeric_bins",
]


class CandidateKey(SixBirdsModel):
    preparation_id: str
    protocol_id: str
    lens_id: str
    step_index: int
    level_id: str | None = None
    resolution_id: str | None = None
    closure_id: str | None = None
    protocol_step_id: str | None = None

    @model_validator(mode="after")
    def validate_key(self) -> "CandidateKey":
        if not self.preparation_id:
            raise ValueError("preparation_id must be a non-empty string")
        if not self.protocol_id:
            raise ValueError("protocol_id must be a non-empty string")
        if not self.lens_id:
            raise ValueError("lens_id must be a non-empty string")
        if isinstance(self.step_index, bool) or self.step_index < 0:
            raise ValueError("step_index must be a non-negative integer")
        for name in ["level_id", "resolution_id", "closure_id", "protocol_step_id"]:
            value = getattr(self, name)
            if value is not None and not value:
                raise ValueError(f"{name} must be non-empty when present")
        return self


class ExtractionThresholds(SixBirdsModel):
    min_trajectory_count: int
    min_atom_count: int
    min_atom_support_count: int
    min_atom_support_fraction: float = 0.0
    min_coverage: float
    max_batch_tv: float
    max_persistence_flip_rate: float | None = None
    batch_count: int

    @model_validator(mode="after")
    def validate_thresholds(self) -> "ExtractionThresholds":
        integer_fields = {
            "min_trajectory_count": self.min_trajectory_count,
            "min_atom_count": self.min_atom_count,
            "min_atom_support_count": self.min_atom_support_count,
            "batch_count": self.batch_count,
        }
        for name, value in integer_fields.items():
            if isinstance(value, bool) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        float_fields = {
            "min_atom_support_fraction": self.min_atom_support_fraction,
            "min_coverage": self.min_coverage,
            "max_batch_tv": self.max_batch_tv,
        }
        for name, value in float_fields.items():
            if (
                isinstance(value, bool)
                or not math.isfinite(value)
                or value < 0
                or value > 1
            ):
                raise ValueError(f"{name} must be a finite value in [0, 1]")
        if self.max_persistence_flip_rate is not None and (
            isinstance(self.max_persistence_flip_rate, bool)
            or not math.isfinite(self.max_persistence_flip_rate)
            or self.max_persistence_flip_rate < 0
            or self.max_persistence_flip_rate > 1
        ):
            raise ValueError(
                "max_persistence_flip_rate must be a finite value in [0, 1]"
            )
        return self


class DiscoveredAtomicOutcome(SixBirdsModel):
    outcome_id: str
    observation_label: str
    support_count: int
    support_fraction: float

    @model_validator(mode="after")
    def validate_outcome(self) -> "DiscoveredAtomicOutcome":
        if not self.outcome_id:
            raise ValueError("outcome_id must be a non-empty string")
        if not self.observation_label:
            raise ValueError("observation_label must be a non-empty string")
        if isinstance(self.support_count, bool) or self.support_count < 0:
            raise ValueError("support_count must be a non-negative integer")
        if (
            isinstance(self.support_fraction, bool)
            or not math.isfinite(self.support_fraction)
            or self.support_fraction < 0
            or self.support_fraction > 1
        ):
            raise ValueError("support_fraction must be a finite value in [0, 1]")
        return self


class ContextDiagnostics(SixBirdsModel):
    trajectory_count: int
    retained_atom_count: int
    coverage_fraction: float
    empirical_entropy: float
    batch_tv_max: float
    persistence_flip_rate: float | None = None
    row_count: int | None = None
    support_by_retained_atom: dict[str, int] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_diagnostics(self) -> "ContextDiagnostics":
        if isinstance(self.trajectory_count, bool) or self.trajectory_count < 0:
            raise ValueError("trajectory_count must be a non-negative integer")
        if isinstance(self.retained_atom_count, bool) or self.retained_atom_count < 0:
            raise ValueError("retained_atom_count must be a non-negative integer")
        bounded_fields = {
            "coverage_fraction": self.coverage_fraction,
            "batch_tv_max": self.batch_tv_max,
        }
        for name, value in bounded_fields.items():
            if (
                isinstance(value, bool)
                or not math.isfinite(value)
                or value < 0
                or value > 1
            ):
                raise ValueError(f"{name} must be a finite value in [0, 1]")
        if (
            isinstance(self.empirical_entropy, bool)
            or not math.isfinite(self.empirical_entropy)
            or self.empirical_entropy < 0
        ):
            raise ValueError("empirical_entropy must be a finite non-negative value")
        if self.persistence_flip_rate is not None and (
            isinstance(self.persistence_flip_rate, bool)
            or not math.isfinite(self.persistence_flip_rate)
            or self.persistence_flip_rate < 0
            or self.persistence_flip_rate > 1
        ):
            raise ValueError("persistence_flip_rate must be a finite value in [0, 1]")
        if self.row_count is not None and (
            isinstance(self.row_count, bool) or self.row_count < 0
        ):
            raise ValueError("row_count must be a non-negative integer when present")
        for key, value in self.support_by_retained_atom.items():
            if not key:
                raise ValueError(
                    "support_by_retained_atom keys must be non-empty strings"
                )
            if isinstance(value, bool) or value < 0:
                raise ValueError(
                    "support_by_retained_atom values must be non-negative integers"
                )
        return self


class PicaContextSourceMetadata(SixBirdsModel):
    source_mode: str
    source_kind: str
    export_bundle_id: str
    campaign_id: str
    run_ids: list[str]
    observable_ledger_ids: list[str]
    level_id: str
    resolution_id: str
    closure_id: str
    lens_id: str
    preparation_id: str
    protocol_id: str
    protocol_step_id: str
    step_index: int
    projection_id: str | None = None
    projection_mode: PicaProjectionMode
    projection_field: str
    projection_bin_edges: list[float] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_metadata(self) -> "PicaContextSourceMetadata":
        for name in [
            "source_mode",
            "source_kind",
            "export_bundle_id",
            "campaign_id",
            "level_id",
            "resolution_id",
            "closure_id",
            "lens_id",
            "preparation_id",
            "protocol_id",
            "protocol_step_id",
            "projection_field",
        ]:
            if not getattr(self, name):
                raise ValueError(f"{name} must be a non-empty string")
        if self.projection_id is not None and not self.projection_id:
            raise ValueError("projection_id must be non-empty when present")
        for name in ["run_ids", "observable_ledger_ids"]:
            values = getattr(self, name)
            if not values:
                raise ValueError(f"{name} must not be empty")
            duplicates = collect_list_duplicates(values)
            if duplicates:
                raise ValueError(f"{name} must be unique: {', '.join(duplicates)}")
            if any(not value for value in values):
                raise ValueError(f"{name} must contain only non-empty strings")
        if isinstance(self.step_index, bool) or self.step_index < 0:
            raise ValueError("step_index must be a non-negative integer")
        if any(
            isinstance(edge, bool) or not math.isfinite(edge)
            for edge in self.projection_bin_edges
        ):
            raise ValueError("projection_bin_edges must contain only finite numbers")
        if self.projection_bin_edges != sorted(self.projection_bin_edges):
            raise ValueError("projection_bin_edges must be sorted")
        return self


class AcceptedContext(SixBirdsModel):
    context_id: str
    candidate_key: CandidateKey
    atomic_outcomes: list[DiscoveredAtomicOutcome]
    diagnostics: ContextDiagnostics
    source_metadata: PicaContextSourceMetadata | None = None

    @model_validator(mode="after")
    def validate_context(self) -> "AcceptedContext":
        if not self.context_id:
            raise ValueError("context_id must be a non-empty string")
        if not self.atomic_outcomes:
            raise ValueError("atomic_outcomes must not be empty")
        outcome_ids = [outcome.outcome_id for outcome in self.atomic_outcomes]
        duplicates = collect_list_duplicates(outcome_ids)
        if duplicates:
            raise ValueError(
                f"atomic outcome_ids must be unique: {', '.join(duplicates)}"
            )
        return self


class RejectedCandidate(SixBirdsModel):
    candidate_key: CandidateKey
    rejection_reasons: list[str]
    diagnostics: ContextDiagnostics
    source_metadata: PicaContextSourceMetadata | None = None

    @model_validator(mode="after")
    def validate_rejected_candidate(self) -> "RejectedCandidate":
        if not self.rejection_reasons:
            raise ValueError("rejection_reasons must not be empty")
        if any(not reason for reason in self.rejection_reasons):
            raise ValueError("rejection_reasons must contain only non-empty strings")
        return self


class DiscoverySummary(SixBirdsModel):
    candidate_count: int
    accepted_context_count: int
    rejected_candidate_count: int
    rejection_reason_counts: dict[str, int]
    accepted_context_ids: list[str]

    @model_validator(mode="after")
    def validate_summary(self) -> "DiscoverySummary":
        integer_fields = {
            "candidate_count": self.candidate_count,
            "accepted_context_count": self.accepted_context_count,
            "rejected_candidate_count": self.rejected_candidate_count,
        }
        for name, value in integer_fields.items():
            if isinstance(value, bool) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        for reason, count in self.rejection_reason_counts.items():
            if not reason:
                raise ValueError(
                    "rejection_reason_counts keys must be non-empty strings"
                )
            if isinstance(count, bool) or count < 0:
                raise ValueError(
                    "rejection_reason_counts values must be non-negative integers"
                )
        return self


class DiscoveredContextFamily(SixBirdsModel):
    family_format_version: str
    family_id: str
    source_run_artifacts: list[str]
    thresholds: ExtractionThresholds
    accepted_contexts: list[AcceptedContext]
    rejected_candidates: list[RejectedCandidate]
    diagnostics_summary: DiscoverySummary
    event_package_skeleton_artifact: str | None = None
    source_mode: str = "substrate_runs"
    source_bundle_artifact: str | None = None
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_family(self) -> "DiscoveredContextFamily":
        if self.family_format_version != "discovered-context-family.v1":
            raise ValueError(
                "family_format_version must equal 'discovered-context-family.v1'"
            )
        if not self.family_id:
            raise ValueError("family_id must be a non-empty string")
        if self.source_mode not in {"substrate_runs", "pica_export_bundle"}:
            raise ValueError(
                "source_mode must be either 'substrate_runs' or 'pica_export_bundle'"
            )
        if self.source_run_artifacts:
            ensure_repo_relative_mapping(
                {
                    f"run_{index}": path
                    for index, path in enumerate(self.source_run_artifacts)
                },
                field_name="source_run_artifacts",
            )
        if self.source_mode == "substrate_runs" and not self.source_run_artifacts:
            raise ValueError(
                "source_run_artifacts must not be empty for substrate_runs mode"
            )
        if self.source_bundle_artifact is not None and not is_repo_relative_path(
            self.source_bundle_artifact
        ):
            raise ValueError(
                "source_bundle_artifact must be a normalized repo-relative path"
            )
        if (
            self.source_mode == "pica_export_bundle"
            and self.source_bundle_artifact is None
        ):
            raise ValueError(
                "source_bundle_artifact must be provided for pica_export_bundle mode"
            )
        if (
            self.event_package_skeleton_artifact is not None
            and not is_repo_relative_path(self.event_package_skeleton_artifact)
        ):
            raise ValueError(
                "event_package_skeleton_artifact must be a normalized repo-relative path"
            )
        ensure_metadata_shape(self.metadata)

        accepted_ids = [context.context_id for context in self.accepted_contexts]
        duplicates = collect_list_duplicates(accepted_ids)
        if duplicates:
            raise ValueError(
                f"accepted context_id values must be unique: {', '.join(duplicates)}"
            )
        if self.diagnostics_summary.accepted_context_count != len(
            self.accepted_contexts
        ):
            raise ValueError(
                "diagnostics_summary.accepted_context_count must equal len(accepted_contexts)"
            )
        if self.diagnostics_summary.rejected_candidate_count != len(
            self.rejected_candidates
        ):
            raise ValueError(
                "diagnostics_summary.rejected_candidate_count must equal len(rejected_candidates)"
            )
        if self.diagnostics_summary.candidate_count != len(
            self.accepted_contexts
        ) + len(self.rejected_candidates):
            raise ValueError(
                "diagnostics_summary.candidate_count must equal accepted + rejected counts"
            )
        if self.diagnostics_summary.accepted_context_ids != accepted_ids:
            raise ValueError(
                "diagnostics_summary.accepted_context_ids must match accepted_contexts order"
            )
        return self


class PicaObservableProjection(SixBirdsModel):
    projection_mode: PicaProjectionMode
    payload_key: str | None = None
    bin_edges: list[float] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_projection(self) -> "PicaObservableProjection":
        if self.projection_mode == "payload_numeric_bins":
            if self.payload_key is None or not self.payload_key:
                raise ValueError(
                    "payload_key must be provided for payload_numeric_bins projection"
                )
            if not self.bin_edges:
                raise ValueError(
                    "bin_edges must be provided for payload_numeric_bins projection"
                )
        if self.payload_key is not None and not self.payload_key:
            raise ValueError("payload_key must be non-empty when present")
        if any(
            isinstance(edge, bool) or not math.isfinite(edge) for edge in self.bin_edges
        ):
            raise ValueError("bin_edges must contain only finite numbers")
        if self.bin_edges != sorted(self.bin_edges):
            raise ValueError("bin_edges must be sorted")
        return self


class PicaContextDiscoveryThresholds(SixBirdsModel):
    min_row_count: int
    min_atom_count: int
    min_atom_support_count: int
    min_atom_support_fraction: float = 0.0
    min_coverage: float
    max_batch_tv: float
    batch_count: int

    @model_validator(mode="after")
    def validate_thresholds(self) -> "PicaContextDiscoveryThresholds":
        for name in [
            "min_row_count",
            "min_atom_count",
            "min_atom_support_count",
            "batch_count",
        ]:
            value = getattr(self, name)
            if isinstance(value, bool) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        for name in ["min_atom_support_fraction", "min_coverage", "max_batch_tv"]:
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not math.isfinite(value)
                or value < 0
                or value > 1
            ):
                raise ValueError(f"{name} must be a finite value in [0, 1]")
        return self


class PicaContextDiscoveryConfig(SixBirdsModel):
    schema_version: str
    bundle_artifact: str
    selected_run_ids: list[str] = Field(default_factory=list)
    selected_point_ids: list[str] = Field(default_factory=list)
    projection: PicaObservableProjection
    grouping_key_fields: list[str]
    thresholds: PicaContextDiscoveryThresholds
    notes: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_config(self) -> "PicaContextDiscoveryConfig":
        if self.schema_version != "pica-context-discovery.v1":
            raise ValueError("schema_version must equal 'pica-context-discovery.v1'")
        ensure_repo_relative_mapping(
            {"bundle_artifact": self.bundle_artifact},
            field_name="bundle_artifact",
        )
        required_fields = [
            "preparation_id",
            "protocol_id",
            "level_id",
            "resolution_id",
            "closure_id",
            "lens_id",
            "protocol_step_id",
        ]
        if self.grouping_key_fields != required_fields:
            raise ValueError(
                "grouping_key_fields must equal the required multilayer key field order"
            )
        for name in ["selected_run_ids", "selected_point_ids", "notes", "flags"]:
            values = getattr(self, name)
            duplicates = collect_list_duplicates(values)
            if duplicates:
                raise ValueError(f"{name} must be unique: {', '.join(duplicates)}")
            if any(not value for value in values):
                raise ValueError(f"{name} must contain only non-empty strings")
        return self


class SharedEventInferenceThresholds(SixBirdsModel):
    inference_mode: SharedEventInferenceMode = "structural_primary"
    min_common_probes: int
    min_conditioning_count: int
    min_probe_atom_support_count: int = 1
    max_mean_tv: float
    exact_tolerance: float
    proposal_constraint_kind: str = "soft"

    @model_validator(mode="after")
    def validate_thresholds(self) -> "SharedEventInferenceThresholds":
        integer_fields = {
            "min_common_probes": self.min_common_probes,
            "min_conditioning_count": self.min_conditioning_count,
            "min_probe_atom_support_count": self.min_probe_atom_support_count,
        }
        for name, value in integer_fields.items():
            if isinstance(value, bool) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        float_fields = {
            "max_mean_tv": self.max_mean_tv,
            "exact_tolerance": self.exact_tolerance,
        }
        for name, value in float_fields.items():
            if (
                isinstance(value, bool)
                or not math.isfinite(value)
                or value < 0
                or value > 1
            ):
                raise ValueError(f"{name} must be a finite value in [0, 1]")
        if self.proposal_constraint_kind not in {"soft", "hard"}:
            raise ValueError("proposal_constraint_kind must be 'soft' or 'hard'")
        return self


class DiscoveredEventGenerationThresholds(SixBirdsModel):
    event_basis_mode: EventBasisMode = "singleton_only"
    event_algebra_mode: EventAlgebraMode | None = None
    max_full_powerset_atom_count: int = 6
    max_union_size: int = 2
    min_event_support_count: int = 3
    min_event_support_fraction: float = 0.1
    include_empty_and_full_in_truncation: bool = True
    match_empty_for_inference: bool = False
    match_full_for_inference: bool = False

    @model_validator(mode="after")
    def validate_thresholds(self) -> "DiscoveredEventGenerationThresholds":
        if (
            isinstance(self.max_full_powerset_atom_count, bool)
            or self.max_full_powerset_atom_count < 1
        ):
            raise ValueError("max_full_powerset_atom_count must be a positive integer")
        if isinstance(self.max_union_size, bool) or self.max_union_size < 2:
            raise ValueError("max_union_size must be an integer >= 2")
        if (
            isinstance(self.min_event_support_count, bool)
            or self.min_event_support_count <= 0
        ):
            raise ValueError("min_event_support_count must be a positive integer")
        if (
            isinstance(self.min_event_support_fraction, bool)
            or not math.isfinite(self.min_event_support_fraction)
            or self.min_event_support_fraction < 0
            or self.min_event_support_fraction > 1
        ):
            raise ValueError(
                "min_event_support_fraction must be a finite value in [0, 1]"
            )
        return self


class DiscoveredEventEntry(SixBirdsModel):
    event_id: str
    context_id: str
    event_kind: DiscoveredEventKind
    retained_atom_ids: list[str]
    event_size: int
    conditioning_support_count: int
    conditioning_support_fraction: float
    accepted: bool
    match_eligible: bool = True
    rejection_reasons: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_event(self) -> "DiscoveredEventEntry":
        for name in ["event_id", "context_id"]:
            if not getattr(self, name):
                raise ValueError(f"{name} must be a non-empty string")
        duplicates = collect_list_duplicates(self.retained_atom_ids)
        if duplicates:
            raise ValueError(
                f"retained_atom_ids must be unique: {', '.join(duplicates)}"
            )
        if self.event_kind == "empty" and self.retained_atom_ids:
            raise ValueError("empty events must not carry retained_atom_ids")
        if self.event_kind != "empty" and not self.retained_atom_ids:
            raise ValueError("non-empty events must carry retained_atom_ids")
        if self.event_size != len(self.retained_atom_ids):
            raise ValueError("event_size must equal len(retained_atom_ids)")
        if (
            isinstance(self.conditioning_support_count, bool)
            or self.conditioning_support_count < 0
        ):
            raise ValueError(
                "conditioning_support_count must be a non-negative integer"
            )
        if (
            isinstance(self.conditioning_support_fraction, bool)
            or not math.isfinite(self.conditioning_support_fraction)
            or self.conditioning_support_fraction < 0
            or self.conditioning_support_fraction > 1
        ):
            raise ValueError(
                "conditioning_support_fraction must be a finite value in [0, 1]"
            )
        if self.event_kind == "empty" and self.event_size != 0:
            raise ValueError("empty events must have event_size 0")
        if self.event_kind == "singleton" and self.event_size != 1:
            raise ValueError("singleton events must have event_size 1")
        if self.event_kind == "proper_coarse" and self.event_size <= 1:
            raise ValueError("proper_coarse events must have event_size > 1")
        if self.event_kind == "full" and self.event_size < 1:
            raise ValueError("full events must have event_size >= 1")
        if self.accepted and self.rejection_reasons:
            raise ValueError("accepted events must not carry rejection_reasons")
        if any(not reason for reason in self.rejection_reasons):
            raise ValueError("rejection_reasons must contain only non-empty strings")
        return self


class DiscoveredEventContext(SixBirdsModel):
    context_id: str
    events: list[DiscoveredEventEntry]
    atom_count: int | None = None
    expected_full_event_count: int | None = None
    generated_event_count: int | None = None
    match_eligible_event_count: int | None = None
    event_algebra_complete: bool | None = None
    generation_mode_used: str | None = None
    coverage_fraction: float | None = None
    truncation_reason: str | None = None
    rejection_reason_counts: dict[str, int] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_context(self) -> "DiscoveredEventContext":
        if not self.context_id:
            raise ValueError("context_id must be a non-empty string")
        if not self.events:
            raise ValueError("events must not be empty")
        for name in [
            "atom_count",
            "expected_full_event_count",
            "generated_event_count",
            "match_eligible_event_count",
        ]:
            value = getattr(self, name)
            if value is not None and (isinstance(value, bool) or value < 0):
                raise ValueError(f"{name} must be a non-negative integer when present")
        if self.generation_mode_used is not None and not self.generation_mode_used:
            raise ValueError("generation_mode_used must be non-empty when present")
        if self.coverage_fraction is not None and (
            isinstance(self.coverage_fraction, bool)
            or not math.isfinite(self.coverage_fraction)
            or self.coverage_fraction < 0
            or self.coverage_fraction > 1
        ):
            raise ValueError(
                "coverage_fraction must be a finite value in [0, 1] when present"
            )
        if self.truncation_reason is not None and not self.truncation_reason:
            raise ValueError("truncation_reason must be non-empty when present")
        duplicates = collect_list_duplicates([event.event_id for event in self.events])
        if duplicates:
            raise ValueError(
                f"events must be unique by event_id: {', '.join(duplicates)}"
            )
        if self.generated_event_count is not None and self.generated_event_count != len(
            self.events
        ):
            raise ValueError("generated_event_count must equal len(events)")
        if (
            self.match_eligible_event_count is not None
            and self.match_eligible_event_count
            != sum(
                1 for event in self.events if event.accepted and event.match_eligible
            )
        ):
            raise ValueError(
                "match_eligible_event_count must equal accepted match-eligible event count"
            )
        for reason, count in self.rejection_reason_counts.items():
            if not reason:
                raise ValueError(
                    "rejection_reason_counts keys must be non-empty strings"
                )
            if isinstance(count, bool) or count < 0:
                raise ValueError(
                    "rejection_reason_counts values must be non-negative integers"
                )
        return self


class DiscoveredEventFamilySummary(SixBirdsModel):
    total_event_count: int
    generated_empty_event_count: int = 0
    generated_singleton_event_count: int = 0
    generated_proper_coarse_event_count: int = 0
    generated_full_event_count: int = 0
    match_eligible_event_count: int = 0
    accepted_singleton_event_count: int
    accepted_coarse_event_count: int
    rejected_coarse_event_count: int
    accepted_proper_coarse_event_ids: list[str]

    @model_validator(mode="after")
    def validate_summary(self) -> "DiscoveredEventFamilySummary":
        for name, value in {
            "total_event_count": self.total_event_count,
            "generated_empty_event_count": self.generated_empty_event_count,
            "generated_singleton_event_count": self.generated_singleton_event_count,
            "generated_proper_coarse_event_count": self.generated_proper_coarse_event_count,
            "generated_full_event_count": self.generated_full_event_count,
            "match_eligible_event_count": self.match_eligible_event_count,
            "accepted_singleton_event_count": self.accepted_singleton_event_count,
            "accepted_coarse_event_count": self.accepted_coarse_event_count,
            "rejected_coarse_event_count": self.rejected_coarse_event_count,
        }.items():
            if isinstance(value, bool) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        duplicates = collect_list_duplicates(self.accepted_proper_coarse_event_ids)
        if duplicates:
            raise ValueError(
                f"accepted_proper_coarse_event_ids must be unique: {', '.join(duplicates)}"
            )
        return self


class DiscoveredEventFamily(SixBirdsModel):
    event_family_format_version: str
    event_family_id: str
    source_discovered_context_family_artifact: str
    source_run_artifacts: list[str] = Field(default_factory=list)
    source_mode: str = "substrate_runs"
    source_bundle_artifact: str | None = None
    thresholds: DiscoveredEventGenerationThresholds
    contexts: list[DiscoveredEventContext]
    diagnostics_summary: DiscoveredEventFamilySummary
    built_event_package_artifact: str | None = None
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_family(self) -> "DiscoveredEventFamily":
        if self.event_family_format_version != "discovered-event-family.v1":
            raise ValueError(
                "event_family_format_version must equal 'discovered-event-family.v1'"
            )
        if not self.event_family_id:
            raise ValueError("event_family_id must be a non-empty string")
        ensure_repo_relative_mapping(
            {
                "source_discovered_context_family_artifact": self.source_discovered_context_family_artifact
            },
            field_name="source_discovered_context_family_artifact",
        )
        if self.source_mode not in {"substrate_runs", "pica_export_bundle"}:
            raise ValueError(
                "source_mode must be either 'substrate_runs' or 'pica_export_bundle'"
            )
        if self.source_run_artifacts:
            ensure_repo_relative_mapping(
                {
                    f"run_{index}": path
                    for index, path in enumerate(self.source_run_artifacts)
                },
                field_name="source_run_artifacts",
            )
        if self.source_mode == "substrate_runs" and not self.source_run_artifacts:
            raise ValueError(
                "source_run_artifacts must not be empty for substrate_runs source_mode"
            )
        if self.source_bundle_artifact is not None and not is_repo_relative_path(
            self.source_bundle_artifact
        ):
            raise ValueError(
                "source_bundle_artifact must be a normalized repo-relative path"
            )
        if (
            self.source_mode == "pica_export_bundle"
            and self.source_bundle_artifact is None
        ):
            raise ValueError(
                "source_bundle_artifact must be provided for pica_export_bundle source_mode"
            )
        if self.built_event_package_artifact is not None and not is_repo_relative_path(
            self.built_event_package_artifact
        ):
            raise ValueError(
                "built_event_package_artifact must be a normalized repo-relative path"
            )
        ensure_metadata_shape(self.metadata)
        duplicates = collect_list_duplicates(
            [context.context_id for context in self.contexts]
        )
        if duplicates:
            raise ValueError(
                f"contexts must be unique by context_id: {', '.join(duplicates)}"
            )
        all_events = [event for context in self.contexts for event in context.events]
        if self.diagnostics_summary.total_event_count != len(all_events):
            raise ValueError(
                "diagnostics_summary.total_event_count must equal total event entry count"
            )
        if self.diagnostics_summary.accepted_singleton_event_count != sum(
            1
            for event in all_events
            if event.accepted and event.event_kind == "singleton"
        ):
            raise ValueError(
                "diagnostics_summary.accepted_singleton_event_count must equal accepted singleton count"
            )
        if self.diagnostics_summary.accepted_coarse_event_count != sum(
            1
            for event in all_events
            if event.accepted and event.event_kind == "proper_coarse"
        ):
            raise ValueError(
                "diagnostics_summary.accepted_coarse_event_count must equal accepted coarse count"
            )
        if self.diagnostics_summary.rejected_coarse_event_count != sum(
            1
            for event in all_events
            if not event.accepted and event.event_kind == "proper_coarse"
        ):
            raise ValueError(
                "diagnostics_summary.rejected_coarse_event_count must equal rejected coarse count"
            )
        if self.diagnostics_summary.generated_empty_event_count != sum(
            1 for event in all_events if event.accepted and event.event_kind == "empty"
        ):
            raise ValueError(
                "diagnostics_summary.generated_empty_event_count must equal accepted empty-event count"
            )
        if self.diagnostics_summary.generated_singleton_event_count != sum(
            1
            for event in all_events
            if event.accepted and event.event_kind == "singleton"
        ):
            raise ValueError(
                "diagnostics_summary.generated_singleton_event_count must equal accepted singleton-event count"
            )
        if self.diagnostics_summary.generated_proper_coarse_event_count != sum(
            1
            for event in all_events
            if event.accepted and event.event_kind == "proper_coarse"
        ):
            raise ValueError(
                "diagnostics_summary.generated_proper_coarse_event_count must equal accepted proper-coarse-event count"
            )
        if self.diagnostics_summary.generated_full_event_count != sum(
            1 for event in all_events if event.accepted and event.event_kind == "full"
        ):
            raise ValueError(
                "diagnostics_summary.generated_full_event_count must equal accepted full-event count"
            )
        if self.diagnostics_summary.match_eligible_event_count != sum(
            1 for event in all_events if event.accepted and event.match_eligible
        ):
            raise ValueError(
                "diagnostics_summary.match_eligible_event_count must equal accepted match-eligible event count"
            )
        accepted_coarse_ids = [
            event.event_id
            for event in all_events
            if event.accepted and event.event_kind == "proper_coarse"
        ]
        if (
            self.diagnostics_summary.accepted_proper_coarse_event_ids
            != accepted_coarse_ids
        ):
            raise ValueError(
                "diagnostics_summary.accepted_proper_coarse_event_ids must match accepted coarse events order"
            )
        return self


class ProbeSignatureComparison(SixBirdsModel):
    probe_context_id: str
    left_conditioning_count: int
    right_conditioning_count: int
    left_support_counts: dict[str, int]
    right_support_counts: dict[str, int]
    left_probe_image_atom_ids: list[str] = Field(default_factory=list)
    right_probe_image_atom_ids: list[str] = Field(default_factory=list)
    left_probe_image_event_kind: DiscoveredEventKind = "empty"
    right_probe_image_event_kind: DiscoveredEventKind = "empty"
    structural_valid: bool = True
    structural_match: bool = False
    structural_mismatch_reasons: list[str] = Field(default_factory=list)
    left_distribution: dict[str, float]
    right_distribution: dict[str, float]
    tv_distance: float

    @model_validator(mode="after")
    def validate_comparison(self) -> "ProbeSignatureComparison":
        if not self.probe_context_id:
            raise ValueError("probe_context_id must be a non-empty string")
        for name, value in {
            "left_conditioning_count": self.left_conditioning_count,
            "right_conditioning_count": self.right_conditioning_count,
        }.items():
            if isinstance(value, bool) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        for mapping_name, mapping in {
            "left_support_counts": self.left_support_counts,
            "right_support_counts": self.right_support_counts,
        }.items():
            for outcome_id, count in mapping.items():
                if not outcome_id:
                    raise ValueError(
                        f"{mapping_name} keys must be non-empty outcome IDs"
                    )
                if isinstance(count, bool) or count < 0:
                    raise ValueError(
                        f"{mapping_name} values must be non-negative integers"
                    )
        for name, kind in [
            ("left_probe_image_atom_ids", self.left_probe_image_event_kind),
            ("right_probe_image_atom_ids", self.right_probe_image_event_kind),
        ]:
            values = getattr(self, name)
            duplicates = collect_list_duplicates(values)
            if duplicates:
                raise ValueError(f"{name} must be unique: {', '.join(duplicates)}")
            if kind != "empty" and not values:
                raise ValueError(f"{name} must not be empty for non-empty event kinds")
        for mapping_name, mapping in {
            "left_distribution": self.left_distribution,
            "right_distribution": self.right_distribution,
        }.items():
            for outcome_id, probability in mapping.items():
                if not outcome_id:
                    raise ValueError(
                        f"{mapping_name} keys must be non-empty outcome IDs"
                    )
                if (
                    isinstance(probability, bool)
                    or not math.isfinite(probability)
                    or probability < 0
                    or probability > 1
                ):
                    raise ValueError(
                        f"{mapping_name} values must be finite probabilities in [0, 1]"
                    )
            if mapping and not math.isclose(sum(mapping.values()), 1.0, abs_tol=1e-9):
                raise ValueError(f"{mapping_name} must sum to 1 within tolerance")
        if (
            isinstance(self.tv_distance, bool)
            or not math.isfinite(self.tv_distance)
            or self.tv_distance < 0
            or self.tv_distance > 1
        ):
            raise ValueError("tv_distance must be a finite value in [0, 1]")
        if self.structural_match and not self.structural_valid:
            raise ValueError("structural_match implies structural_valid")
        if self.structural_match and self.structural_mismatch_reasons:
            raise ValueError(
                "structurally matched comparisons must not carry mismatch reasons"
            )
        if any(not reason for reason in self.structural_mismatch_reasons):
            raise ValueError(
                "structural_mismatch_reasons must contain only non-empty strings"
            )
        return self


class ProbeIndistinguishabilitySignatureEntry(SixBirdsModel):
    source_event_id: str
    source_context_id: str
    probe_context_id: str
    probe_image_atom_ids: list[str]
    probe_image_event_kind: DiscoveredEventKind
    conditioning_support_count: int
    support_by_retained_probe_atom: dict[str, int]
    structural_valid: bool
    probe_distribution: dict[str, float] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_signature(self) -> "ProbeIndistinguishabilitySignatureEntry":
        for name in ["source_event_id", "source_context_id", "probe_context_id"]:
            if not getattr(self, name):
                raise ValueError(f"{name} must be a non-empty string")
        duplicates = collect_list_duplicates(self.probe_image_atom_ids)
        if duplicates:
            raise ValueError(
                f"probe_image_atom_ids must be unique: {', '.join(duplicates)}"
            )
        if self.probe_image_event_kind != "empty" and not self.probe_image_atom_ids:
            raise ValueError("non-empty probe images must carry atom IDs")
        if (
            isinstance(self.conditioning_support_count, bool)
            or self.conditioning_support_count < 0
        ):
            raise ValueError(
                "conditioning_support_count must be a non-negative integer"
            )
        for mapping_name, mapping in {
            "support_by_retained_probe_atom": self.support_by_retained_probe_atom,
        }.items():
            for atom_id, count in mapping.items():
                if not atom_id:
                    raise ValueError(f"{mapping_name} keys must be non-empty atom IDs")
                if isinstance(count, bool) or count < 0:
                    raise ValueError(
                        f"{mapping_name} values must be non-negative integers"
                    )
        if self.probe_distribution and not math.isclose(
            sum(self.probe_distribution.values()),
            1.0,
            abs_tol=1e-9,
        ):
            raise ValueError("probe_distribution must sum to 1 within tolerance")
        if any(not value for value in self.notes + self.flags):
            raise ValueError("notes and flags must contain only non-empty strings")
        return self


class ProbeIndistinguishabilitySignatureTable(SixBirdsModel):
    signatures_format_version: str
    inference_id: str
    source_discovered_context_family_artifact: str
    source_run_artifacts: list[str] = Field(default_factory=list)
    source_mode: str = "substrate_runs"
    source_bundle_artifact: str | None = None
    thresholds: SharedEventInferenceThresholds
    signature_rows: list[ProbeIndistinguishabilitySignatureEntry]
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_table(self) -> "ProbeIndistinguishabilitySignatureTable":
        if self.signatures_format_version != "probe-indistinguishability-signature.v1":
            raise ValueError(
                "signatures_format_version must equal 'probe-indistinguishability-signature.v1'"
            )
        if not self.inference_id:
            raise ValueError("inference_id must be a non-empty string")
        ensure_repo_relative_mapping(
            {
                "source_discovered_context_family_artifact": self.source_discovered_context_family_artifact
            },
            field_name="source_discovered_context_family_artifact",
        )
        if self.source_mode not in {"substrate_runs", "pica_export_bundle"}:
            raise ValueError(
                "source_mode must be either 'substrate_runs' or 'pica_export_bundle'"
            )
        if self.source_run_artifacts:
            ensure_repo_relative_mapping(
                {
                    f"run_{index}": path
                    for index, path in enumerate(self.source_run_artifacts)
                },
                field_name="source_run_artifacts",
            )
        if self.source_bundle_artifact is not None and not is_repo_relative_path(
            self.source_bundle_artifact
        ):
            raise ValueError(
                "source_bundle_artifact must be a normalized repo-relative path"
            )
        ensure_metadata_shape(self.metadata)
        return self


SharedEventSupportRelationKind = Literal[
    "identical_support",
    "same_support_relabeling",
    "cross_support_match",
    "crosscutting_match",
    "disjoint_support_match",
]


class SharedEventCandidateRow(SixBirdsModel):
    candidate_id: str
    left_context_id: str
    right_context_id: str
    left_event_id: str
    right_event_id: str
    left_outcome_id: str
    right_outcome_id: str
    left_event_kind: DiscoveredEventKind
    right_event_kind: DiscoveredEventKind
    left_event_atom_ids: list[str]
    right_event_atom_ids: list[str]
    left_event_size: int
    right_event_size: int
    left_is_proper_coarse: bool
    right_is_proper_coarse: bool
    common_probe_ids: list[str]
    common_probe_count: int
    probe_comparisons: list[ProbeSignatureComparison]
    structural_match: bool = False
    structural_mismatch_count: int = 0
    structural_mismatch_reasons: list[str] = Field(default_factory=list)
    mean_tv: float | None = None
    max_tv: float | None = None
    approx_score: float | None = None
    confidence: float | None = None
    exact_consistent: bool | None = None
    left_support_count: int = 0
    right_support_count: int = 0
    shared_support_count: int = 0
    support_relation_kind: SharedEventSupportRelationKind | None = None
    insufficient_data: bool
    accepted: bool
    rejection_reasons: list[str] = Field(default_factory=list)
    proposed_proposal_id: str | None = None

    @model_validator(mode="after")
    def validate_candidate(self) -> "SharedEventCandidateRow":
        for name in [
            "candidate_id",
            "left_context_id",
            "right_context_id",
            "left_event_id",
            "right_event_id",
            "left_outcome_id",
            "right_outcome_id",
        ]:
            if not getattr(self, name):
                raise ValueError(f"{name} must be a non-empty string")
        for name, kind in [
            ("left_event_atom_ids", self.left_event_kind),
            ("right_event_atom_ids", self.right_event_kind),
        ]:
            values = getattr(self, name)
            duplicates = collect_list_duplicates(values)
            if duplicates:
                raise ValueError(f"{name} must be unique: {', '.join(duplicates)}")
            if kind != "empty" and not values:
                raise ValueError(f"{name} must not be empty")
        if self.left_event_size != len(self.left_event_atom_ids):
            raise ValueError("left_event_size must equal len(left_event_atom_ids)")
        if self.right_event_size != len(self.right_event_atom_ids):
            raise ValueError("right_event_size must equal len(right_event_atom_ids)")
        if self.left_event_kind == "empty" and self.left_event_size != 0:
            raise ValueError("empty left events must have size 0")
        if self.right_event_kind == "empty" and self.right_event_size != 0:
            raise ValueError("empty right events must have size 0")
        if self.left_event_kind == "singleton" and self.left_event_size != 1:
            raise ValueError("singleton left events must have size 1")
        if self.right_event_kind == "singleton" and self.right_event_size != 1:
            raise ValueError("singleton right events must have size 1")
        if self.left_event_kind == "proper_coarse" and self.left_event_size <= 1:
            raise ValueError("proper_coarse left events must have size > 1")
        if self.right_event_kind == "proper_coarse" and self.right_event_size <= 1:
            raise ValueError("proper_coarse right events must have size > 1")
        if self.left_is_proper_coarse != (self.left_event_kind == "proper_coarse"):
            raise ValueError(
                "left_is_proper_coarse must match whether left_event_kind is proper_coarse"
            )
        if self.right_is_proper_coarse != (self.right_event_kind == "proper_coarse"):
            raise ValueError(
                "right_is_proper_coarse must match whether right_event_kind is proper_coarse"
            )
        duplicates = collect_list_duplicates(self.common_probe_ids)
        if duplicates:
            raise ValueError(
                f"common_probe_ids must be unique: {', '.join(duplicates)}"
            )
        if isinstance(self.common_probe_count, bool) or self.common_probe_count < 0:
            raise ValueError("common_probe_count must be a non-negative integer")
        if self.common_probe_count != len(self.common_probe_ids):
            raise ValueError("common_probe_count must equal len(common_probe_ids)")
        comparison_probe_ids = [
            comparison.probe_context_id for comparison in self.probe_comparisons
        ]
        if comparison_probe_ids != self.common_probe_ids:
            raise ValueError(
                "probe_comparisons probe_context_id values must match common_probe_ids order"
            )
        if (
            isinstance(self.structural_mismatch_count, bool)
            or self.structural_mismatch_count < 0
        ):
            raise ValueError("structural_mismatch_count must be a non-negative integer")
        if self.structural_match and self.structural_mismatch_count != 0:
            raise ValueError(
                "structurally matched candidates must have structural_mismatch_count 0"
            )
        if self.structural_match and self.structural_mismatch_reasons:
            raise ValueError(
                "structurally matched candidates must not carry mismatch reasons"
            )
        if any(not reason for reason in self.structural_mismatch_reasons):
            raise ValueError(
                "structural_mismatch_reasons must contain only non-empty strings"
            )
        for name in [
            "left_support_count",
            "right_support_count",
            "shared_support_count",
        ]:
            value = getattr(self, name)
            if isinstance(value, bool) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if self.shared_support_count > min(
            self.left_support_count, self.right_support_count
        ):
            raise ValueError(
                "shared_support_count must not exceed either source support count"
            )
        if self.insufficient_data:
            if self.accepted:
                raise ValueError("insufficient-data candidates cannot be accepted")
            if self.proposed_proposal_id is not None:
                raise ValueError(
                    "insufficient-data candidates must not carry proposed_proposal_id"
                )
        else:
            if self.approx_score is None or self.confidence is None:
                raise ValueError(
                    "non-insufficient candidates must carry approx_score and confidence"
                )
            for name, value in {
                "mean_tv": self.mean_tv
                if self.mean_tv is not None
                else self.approx_score,
                "max_tv": self.max_tv if self.max_tv is not None else self.approx_score,
                "approx_score": self.approx_score,
                "confidence": self.confidence,
            }.items():
                if (
                    isinstance(value, bool)
                    or not math.isfinite(value)
                    or value < 0
                    or value > 1
                ):
                    raise ValueError(f"{name} must be a finite value in [0, 1]")
            if self.accepted:
                if self.proposed_proposal_id is None:
                    raise ValueError(
                        "accepted candidates must carry proposed_proposal_id"
                    )
                if self.rejection_reasons:
                    raise ValueError(
                        "accepted candidates must not carry rejection_reasons"
                    )
        if any(not reason for reason in self.rejection_reasons):
            raise ValueError("rejection_reasons must contain only non-empty strings")
        return self


class SharedEventInferenceSummary(SixBirdsModel):
    total_candidate_pair_count: int
    structurally_valid_candidate_pair_count: int = 0
    accepted_candidate_pair_count: int
    insufficient_data_candidate_pair_count: int
    rejected_candidate_pair_count: int
    accepted_proposal_ids: list[str]

    @model_validator(mode="after")
    def validate_summary(self) -> "SharedEventInferenceSummary":
        for name, value in {
            "total_candidate_pair_count": self.total_candidate_pair_count,
            "structurally_valid_candidate_pair_count": self.structurally_valid_candidate_pair_count,
            "accepted_candidate_pair_count": self.accepted_candidate_pair_count,
            "insufficient_data_candidate_pair_count": self.insufficient_data_candidate_pair_count,
            "rejected_candidate_pair_count": self.rejected_candidate_pair_count,
        }.items():
            if isinstance(value, bool) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        duplicates = collect_list_duplicates(self.accepted_proposal_ids)
        if duplicates:
            raise ValueError(
                f"accepted_proposal_ids must be unique: {', '.join(duplicates)}"
            )
        return self


class SharedEventCandidates(SixBirdsModel):
    candidates_format_version: str
    inference_id: str
    inference_mode: SharedEventInferenceMode = "legacy_statistical_primary"
    source_discovered_context_family_artifact: str
    source_run_artifacts: list[str] = Field(default_factory=list)
    source_mode: str = "substrate_runs"
    source_bundle_artifact: str | None = None
    thresholds: SharedEventInferenceThresholds
    candidate_rows: list[SharedEventCandidateRow]
    diagnostics_summary: SharedEventInferenceSummary
    built_event_package_artifact: str | None = None
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_candidates(self) -> "SharedEventCandidates":
        if self.candidates_format_version != "shared-event-candidates.v1":
            raise ValueError(
                "candidates_format_version must equal 'shared-event-candidates.v1'"
            )
        if not self.inference_id:
            raise ValueError("inference_id must be a non-empty string")
        ensure_repo_relative_mapping(
            {
                "source_discovered_context_family_artifact": self.source_discovered_context_family_artifact
            },
            field_name="source_discovered_context_family_artifact",
        )
        if self.source_mode not in {"substrate_runs", "pica_export_bundle"}:
            raise ValueError(
                "source_mode must be either 'substrate_runs' or 'pica_export_bundle'"
            )
        if self.source_run_artifacts:
            ensure_repo_relative_mapping(
                {
                    f"run_{index}": path
                    for index, path in enumerate(self.source_run_artifacts)
                },
                field_name="source_run_artifacts",
            )
        if self.source_mode == "substrate_runs" and not self.source_run_artifacts:
            raise ValueError(
                "source_run_artifacts must not be empty for substrate_runs source_mode"
            )
        if self.source_bundle_artifact is not None and not is_repo_relative_path(
            self.source_bundle_artifact
        ):
            raise ValueError(
                "source_bundle_artifact must be a normalized repo-relative path"
            )
        if (
            self.source_mode == "pica_export_bundle"
            and self.source_bundle_artifact is None
        ):
            raise ValueError(
                "source_bundle_artifact must be provided for pica_export_bundle source_mode"
            )
        if self.built_event_package_artifact is not None and not is_repo_relative_path(
            self.built_event_package_artifact
        ):
            raise ValueError(
                "built_event_package_artifact must be a normalized repo-relative path"
            )
        ensure_metadata_shape(self.metadata)

        candidate_ids = [row.candidate_id for row in self.candidate_rows]
        duplicates = collect_list_duplicates(candidate_ids)
        if duplicates:
            raise ValueError(
                f"candidate_id values must be unique: {', '.join(duplicates)}"
            )
        proposal_ids = [
            row.proposed_proposal_id
            for row in self.candidate_rows
            if row.proposed_proposal_id is not None
        ]
        duplicates = collect_list_duplicates(proposal_ids)
        if duplicates:
            raise ValueError(
                f"proposed_proposal_id values must be unique: {', '.join(duplicates)}"
            )

        accepted_rows = [row for row in self.candidate_rows if row.accepted]
        structurally_valid_rows = [
            row for row in self.candidate_rows if row.structural_match
        ]
        insufficient_rows = [
            row for row in self.candidate_rows if row.insufficient_data
        ]
        rejected_rows = [
            row
            for row in self.candidate_rows
            if not row.accepted and not row.insufficient_data
        ]
        if self.diagnostics_summary.total_candidate_pair_count != len(
            self.candidate_rows
        ):
            raise ValueError(
                "diagnostics_summary.total_candidate_pair_count must equal len(candidate_rows)"
            )
        if self.diagnostics_summary.structurally_valid_candidate_pair_count != len(
            structurally_valid_rows
        ):
            raise ValueError(
                "diagnostics_summary.structurally_valid_candidate_pair_count must equal structural-match row count"
            )
        if self.diagnostics_summary.accepted_candidate_pair_count != len(accepted_rows):
            raise ValueError(
                "diagnostics_summary.accepted_candidate_pair_count must equal accepted row count"
            )
        if self.diagnostics_summary.insufficient_data_candidate_pair_count != len(
            insufficient_rows
        ):
            raise ValueError(
                "diagnostics_summary.insufficient_data_candidate_pair_count must equal insufficient-data row count"
            )
        if self.diagnostics_summary.rejected_candidate_pair_count != len(rejected_rows):
            raise ValueError(
                "diagnostics_summary.rejected_candidate_pair_count must equal rejected row count"
            )
        accepted_proposal_ids = [
            row.proposed_proposal_id
            for row in accepted_rows
            if row.proposed_proposal_id
        ]
        if self.diagnostics_summary.accepted_proposal_ids != accepted_proposal_ids:
            raise ValueError(
                "diagnostics_summary.accepted_proposal_ids must match accepted rows order"
            )
        if self.inference_mode == "structural_primary" and any(
            not row.structural_match for row in accepted_rows
        ):
            raise ValueError(
                "accepted rows must be structural matches in structural_primary mode"
            )
        return self


class EventAlgebraCoverageContext(SixBirdsModel):
    context_id: str
    atom_count: int
    expected_full_event_count: int
    generated_event_count: int
    event_algebra_complete: bool
    coverage_fraction: float
    generation_mode_used: str
    truncation_reason: str | None = None
    notes: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_context(self) -> "EventAlgebraCoverageContext":
        if not self.context_id:
            raise ValueError("context_id must be a non-empty string")
        for name in [
            "atom_count",
            "expected_full_event_count",
            "generated_event_count",
        ]:
            value = getattr(self, name)
            if isinstance(value, bool) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if (
            isinstance(self.coverage_fraction, bool)
            or not math.isfinite(self.coverage_fraction)
            or self.coverage_fraction < 0
            or self.coverage_fraction > 1
        ):
            raise ValueError("coverage_fraction must be a finite value in [0, 1]")
        if not self.generation_mode_used:
            raise ValueError("generation_mode_used must be a non-empty string")
        if self.truncation_reason is not None and not self.truncation_reason:
            raise ValueError("truncation_reason must be non-empty when present")
        if any(not note for note in self.notes):
            raise ValueError("notes must contain only non-empty strings")
        if any(not flag for flag in self.flags):
            raise ValueError("flags must contain only non-empty strings")
        return self


class EventAlgebraCoverage(SixBirdsModel):
    coverage_format_version: str
    source_discovered_context_family_artifact: str
    event_algebra_mode: str
    max_full_powerset_atom_count: int
    contexts: list[EventAlgebraCoverageContext]
    notes: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_report(self) -> "EventAlgebraCoverage":
        if self.coverage_format_version != "event-algebra-coverage.v1":
            raise ValueError(
                "coverage_format_version must equal 'event-algebra-coverage.v1'"
            )
        ensure_repo_relative_mapping(
            {
                "source_discovered_context_family_artifact": self.source_discovered_context_family_artifact
            },
            field_name="source_discovered_context_family_artifact",
        )
        if not self.event_algebra_mode:
            raise ValueError("event_algebra_mode must be a non-empty string")
        if (
            isinstance(self.max_full_powerset_atom_count, bool)
            or self.max_full_powerset_atom_count < 1
        ):
            raise ValueError("max_full_powerset_atom_count must be a positive integer")
        duplicates = collect_list_duplicates(
            [context.context_id for context in self.contexts]
        )
        if duplicates:
            raise ValueError(
                f"contexts must be unique by context_id: {', '.join(duplicates)}"
            )
        if any(not note for note in self.notes):
            raise ValueError("notes must contain only non-empty strings")
        if any(not flag for flag in self.flags):
            raise ValueError("flags must contain only non-empty strings")
        return self
