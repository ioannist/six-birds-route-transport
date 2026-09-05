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
)


FindingCategory = Literal[
    "benchmark",
    "discovered_package",
    "intervention",
    "robustness",
    "redteam",
    "lean",
    "suite",
    "claim_support",
]


class ProvenanceAuditRefresh(SixBirdsModel):
    audit_id: str
    package_artifact: str
    provenance_artifact: str | None = None
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_audit(self) -> "ProvenanceAuditRefresh":
        if not self.audit_id:
            raise ValueError("audit_id must be a non-empty string")
        ensure_repo_relative_mapping(
            {"package_artifact": self.package_artifact},
            field_name="package_artifact",
        )
        if self.provenance_artifact is not None:
            ensure_repo_relative_mapping(
                {"provenance_artifact": self.provenance_artifact},
                field_name="provenance_artifact",
            )
        if any(not note for note in self.notes):
            raise ValueError("notes must contain only non-empty strings")
        return self


class FindingsEvidenceRefreshConfig(SixBirdsModel):
    run_benchmark_suite: bool = True
    run_intervention_suite: bool = True
    run_search_suite: bool = True
    run_lean_build_suite: bool = True
    robustness_sweep_artifact: str
    redteam_suite_artifact: str
    exact_crosscheck_artifact: str
    discovered_case_falsification_artifact: str
    targeted_search_artifact: str
    atlas_upgrade_artifact: str
    provenance_audits: list[ProvenanceAuditRefresh] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_refresh(self) -> "FindingsEvidenceRefreshConfig":
        ensure_repo_relative_mapping(
            {
                "robustness_sweep_artifact": self.robustness_sweep_artifact,
                "redteam_suite_artifact": self.redteam_suite_artifact,
                "exact_crosscheck_artifact": self.exact_crosscheck_artifact,
                "discovered_case_falsification_artifact": self.discovered_case_falsification_artifact,
                "targeted_search_artifact": self.targeted_search_artifact,
                "atlas_upgrade_artifact": self.atlas_upgrade_artifact,
            },
            field_name="refresh_artifacts",
        )
        duplicates = collect_list_duplicates(
            [audit.audit_id for audit in self.provenance_audits]
        )
        if duplicates:
            raise ValueError(
                f"provenance_audits must be unique by audit_id: {', '.join(duplicates)}"
            )
        return self


class FindingsRegistryConfig(SixBirdsModel):
    config_format_version: str
    registry_id: str
    evidence_refresh: FindingsEvidenceRefreshConfig
    static_artifact_refs: dict[str, str]
    claim_ids: list[str]
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_config(self) -> "FindingsRegistryConfig":
        if self.config_format_version != "findings-registry-config.v1":
            raise ValueError(
                "config_format_version must equal 'findings-registry-config.v1'"
            )
        if not self.registry_id:
            raise ValueError("registry_id must be a non-empty string")
        if not self.static_artifact_refs:
            raise ValueError("static_artifact_refs must not be empty")
        ensure_repo_relative_mapping(
            self.static_artifact_refs,
            field_name="static_artifact_refs",
        )
        if not self.claim_ids:
            raise ValueError("claim_ids must not be empty")
        duplicates = collect_list_duplicates(self.claim_ids)
        if duplicates:
            raise ValueError(f"claim_ids must be unique: {', '.join(duplicates)}")
        if any(not claim_id for claim_id in self.claim_ids):
            raise ValueError("claim_ids must contain only non-empty strings")
        ensure_metadata_shape(self.metadata)
        return self


class FindingEntry(SixBirdsModel):
    finding_format_version: str
    finding_id: str
    category: FindingCategory
    title: str
    status: str
    key_claim_tags: list[str]
    primary_artifact_refs: dict[str, str]
    supporting_artifact_refs: dict[str, str] = Field(default_factory=dict)
    key_metrics: dict[str, MetricValue] = Field(default_factory=dict)
    provenance_classification: AdmissibilityClassification | None = None
    figure_table_candidate_labels: list[str] = Field(default_factory=list)
    theorem_link_ids: list[str] = Field(default_factory=list)
    best_evidence_flag: bool = False
    best_evidence_score: float | None = None
    notes: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_entry(self) -> "FindingEntry":
        if self.finding_format_version != "finding-entry.v1":
            raise ValueError("finding_format_version must equal 'finding-entry.v1'")
        for name in ["finding_id", "title", "status"]:
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise ValueError(f"{name} must be a non-empty string")
        if not self.key_claim_tags:
            raise ValueError("key_claim_tags must not be empty")
        duplicates = collect_list_duplicates(self.key_claim_tags)
        if duplicates:
            raise ValueError(f"key_claim_tags must be unique: {', '.join(duplicates)}")
        ensure_repo_relative_mapping(
            self.primary_artifact_refs,
            field_name="primary_artifact_refs",
        )
        ensure_repo_relative_mapping(
            self.supporting_artifact_refs,
            field_name="supporting_artifact_refs",
        )
        ensure_metric_shape(self.key_metrics)
        for name, values in [
            ("figure_table_candidate_labels", self.figure_table_candidate_labels),
            ("theorem_link_ids", self.theorem_link_ids),
            ("notes", self.notes),
            ("flags", self.flags),
        ]:
            duplicates = collect_list_duplicates(values)
            if duplicates:
                raise ValueError(f"{name} must be unique: {', '.join(duplicates)}")
            if any(not value for value in values):
                raise ValueError(f"{name} must contain only non-empty strings")
        if self.best_evidence_score is not None and (
            isinstance(self.best_evidence_score, bool)
            or not math.isfinite(self.best_evidence_score)
            or self.best_evidence_score < 0
        ):
            raise ValueError(
                "best_evidence_score must be a finite non-negative value when present"
            )
        return self


class ClaimEvidenceLink(SixBirdsModel):
    claim_id: str
    claim_label: str
    evidence_entry_ids: list[str]
    best_evidence_entry_id: str
    theorem_linkage_ids: list[str] = Field(default_factory=list)
    caveat_flags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_link(self) -> "ClaimEvidenceLink":
        for name in ["claim_id", "claim_label", "best_evidence_entry_id"]:
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise ValueError(f"{name} must be a non-empty string")
        if not self.evidence_entry_ids:
            raise ValueError("evidence_entry_ids must not be empty")
        for name, values in [
            ("evidence_entry_ids", self.evidence_entry_ids),
            ("theorem_linkage_ids", self.theorem_linkage_ids),
            ("caveat_flags", self.caveat_flags),
        ]:
            duplicates = collect_list_duplicates(values)
            if duplicates:
                raise ValueError(f"{name} must be unique: {', '.join(duplicates)}")
            if any(not value for value in values):
                raise ValueError(f"{name} must contain only non-empty strings")
        if self.best_evidence_entry_id not in self.evidence_entry_ids:
            raise ValueError(
                "best_evidence_entry_id must be listed in evidence_entry_ids"
            )
        return self


class ClaimEvidenceMap(SixBirdsModel):
    claim_map_format_version: str
    claim_count: int
    claims: list[ClaimEvidenceLink]
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_map(self) -> "ClaimEvidenceMap":
        if self.claim_map_format_version != "claim-evidence-map.v1":
            raise ValueError(
                "claim_map_format_version must equal 'claim-evidence-map.v1'"
            )
        if self.claim_count != len(self.claims):
            raise ValueError("claim_count must equal len(claims)")
        duplicates = collect_list_duplicates([claim.claim_id for claim in self.claims])
        if duplicates:
            raise ValueError(
                f"claims must be unique by claim_id: {', '.join(duplicates)}"
            )
        ensure_metadata_shape(self.metadata)
        return self


class FindingsRegistry(SixBirdsModel):
    registry_format_version: str
    registry_id: str
    evidence_refresh_run_ids: dict[str, str]
    evidence_refresh_summary_paths: dict[str, str]
    entry_count: int
    entries: list[FindingEntry]
    claim_evidence_map_path: str
    flagship_examples_path: str
    figure_candidates_path: str
    table_candidates_path: str
    theorem_experiment_links_path: str
    best_evidence_paths_path: str
    summary_counts: dict[str, MetricValue]
    status_flags: list[str] = Field(default_factory=list)
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_registry(self) -> "FindingsRegistry":
        if self.registry_format_version != "findings-registry.v1":
            raise ValueError(
                "registry_format_version must equal 'findings-registry.v1'"
            )
        if not self.registry_id:
            raise ValueError("registry_id must be a non-empty string")
        if self.entry_count != len(self.entries):
            raise ValueError("entry_count must equal len(entries)")
        duplicates = collect_list_duplicates(
            [entry.finding_id for entry in self.entries]
        )
        if duplicates:
            raise ValueError(
                f"entries must be unique by finding_id: {', '.join(duplicates)}"
            )
        if not self.evidence_refresh_run_ids:
            raise ValueError("evidence_refresh_run_ids must not be empty")
        if not self.evidence_refresh_summary_paths:
            raise ValueError("evidence_refresh_summary_paths must not be empty")
        ensure_repo_relative_mapping(
            self.evidence_refresh_summary_paths,
            field_name="evidence_refresh_summary_paths",
        )
        ensure_repo_relative_mapping(
            {
                "claim_evidence_map_path": self.claim_evidence_map_path,
                "flagship_examples_path": self.flagship_examples_path,
                "figure_candidates_path": self.figure_candidates_path,
                "table_candidates_path": self.table_candidates_path,
                "theorem_experiment_links_path": self.theorem_experiment_links_path,
                "best_evidence_paths_path": self.best_evidence_paths_path,
            },
            field_name="registry_output_paths",
        )
        ensure_metric_shape(self.summary_counts)
        duplicates = collect_list_duplicates(self.status_flags)
        if duplicates:
            raise ValueError(f"status_flags must be unique: {', '.join(duplicates)}")
        if any(not flag for flag in self.status_flags):
            raise ValueError("status_flags must contain only non-empty strings")
        ensure_metadata_shape(self.metadata)
        return self
