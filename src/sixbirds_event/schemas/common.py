from __future__ import annotations

import math
import re
from enum import Enum
from pathlib import PurePosixPath
from typing import Any, TypeAlias

from pydantic import BaseModel, ConfigDict

JsonScalar: TypeAlias = str | int | float | bool | None
MetadataValue: TypeAlias = JsonScalar | list[str]
MetricValue: TypeAlias = JsonScalar


class SchemaKind(str, Enum):
    EVENT_PACKAGE_INSTANCE = "event-package-instance"
    OBSERVATION_TRACE = "observation-trace"
    RUN_MANIFEST = "run-manifest"
    RESULT_NOTE = "result-note"
    SUBSTRATE_CONFIG = "substrate-config"
    SUBSTRATE_RUN = "substrate-run"
    DISCOVERED_CONTEXT_FAMILY = "discovered-context-family"
    DISCOVERED_EVENT_FAMILY = "discovered-event-family"
    SHARED_EVENT_CANDIDATES = "shared-event-candidates"
    HIDDEN_RECORD_INTERVENTION = "hidden-record-intervention"
    FLATTENING_INTERVENTION = "flattening-intervention"
    SEARCH_SWEEP = "search-sweep"
    SEARCH_ATLAS = "search-atlas"
    TARGETED_NONEXTENDABILITY_SEARCH = "targeted-nonextendability-search"
    TARGETED_SEARCH_RESULTS = "targeted-search-results"
    PICA_TARGETED_OBSTRUCTION_SEARCH = "pica-targeted-obstruction-search"
    PICA_TARGETED_SEARCH_RESULTS = "pica-targeted-search-results"
    PICA_CLOSURE_DIVERSE_SEARCH = "pica-closure-diverse-search"
    PICA_CLOSURE_DIVERSE_SEARCH_RESULTS = "pica-closure-diverse-search-results"
    CONTEXT_PAIR_STRUCTURE = "context-pair-structure"
    PICA_FROZEN_SLICE_SEARCH = "pica-frozen-slice-search"
    PICA_FROZEN_SLICE_SEARCH_RESULTS = "pica-frozen-slice-search-results"
    PICA_PACKAGING_CONFLICT_SEARCH = "pica-packaging-conflict-search"
    PICA_PACKAGING_CONFLICT_SEARCH_RESULTS = "pica-packaging-conflict-search-results"
    PROJECTION_FAMILY_ADMISSIBILITY = "projection-family-admissibility"
    ATLAS_UPGRADE_CONFIG = "atlas-upgrade-config"
    ATLAS_UPGRADE_RESULTS = "atlas-upgrade-results"
    DISCOVERED_CASE_FALSIFICATION = "discovered-case-falsification"
    DISCOVERED_CASE_FALSIFICATION_RESULT = "discovered-case-falsification-result"
    FLAGSHIP_CONTROL_BUNDLE = "flagship-control-bundle"
    FLAGSHIP_CONTROL_RESULT = "flagship-control-result"
    EXACT_CROSSCHECK = "exact-crosscheck"
    EXACT_CROSSCHECK_RESULT = "exact-crosscheck-result"
    NOISE_ROBUSTNESS_SWEEP = "noise-robustness-sweep"
    NOISE_ROBUSTNESS_TABLE = "noise-robustness-table"
    REDTEAM_SUITE = "redteam-suite"
    REDTEAM_RESULTS = "redteam-results"
    PICA_EXPORT_BUNDLE = "pica-export-bundle"
    PICA_CAMPAIGN_EXPORT = "pica-campaign-export"
    PICA_RUN_LEDGER = "pica-run-ledger"
    PICA_CLOSURE_CATALOG = "pica-closure-catalog"
    PICA_OBSERVABLE_LEDGER = "pica-observable-ledger"
    PICA_COMMUTATOR_CATALOG = "pica-commutator-catalog"
    PICA_PACKAGING_OPERATOR_CATALOG = "pica-packaging-operator-catalog"
    PICA_PACKAGING_SELECTION_LEDGER = "pica-packaging-selection-ledger"
    PICA_PACKAGING_SURFACE = "pica-packaging-surface"
    PICA_PILOT_CAMPAIGN = "pica-pilot-campaign"
    PICA_PILOT_RESULT = "pica-pilot-result"
    PICA_DISCOVERY_READINESS = "pica-discovery-readiness"
    PICA_CONTEXT_DISCOVERY = "pica-context-discovery"
    EVENT_ALGEBRA_COVERAGE = "event-algebra-coverage"
    PROBE_INDISTINGUISHABILITY_SIGNATURE = "probe-indistinguishability-signature"
    PACKAGE_PROVENANCE = "package-provenance"
    PROVENANCE_AUDIT_RESULT = "provenance-audit-result"
    FINDINGS_REGISTRY_CONFIG = "findings-registry-config"
    FINDING_ENTRY = "finding-entry"
    CLAIM_EVIDENCE_MAP = "claim-evidence-map"
    FINDINGS_REGISTRY = "findings-registry"
    THREE_AXIS_SEARCH_CONFIG = "three-axis-search-config"
    THREE_AXIS_SEARCH_ROW = "three-axis-search-row"
    AXIS_CLAIM_LADDER = "axis-claim-ladder"
    SHARED_METRIC_SURFACE = "shared-metric-surface"
    MECHANISM_AXIS_SEARCH = "mechanism-axis-search"
    MECHANISM_AXIS_RESULTS = "mechanism-axis-results"
    LENS_AXIS_SEARCH = "lens-axis-search"
    LENS_AXIS_RESULTS = "lens-axis-results"
    LENS_FAMILY_ADMISSIBILITY = "lens-family-admissibility"
    LENS_AXIS_CROSS_RESOLUTION_ADJUDICATION = "lens-axis-cross-resolution-adjudication"
    LENS_AXIS_FINALIZATION = "lens-axis-finalization"
    LENS_AXIS_FINAL_OUTCOME = "lens-axis-final-outcome"
    PACKAGING_AXIS_SEARCH = "packaging-axis-search"
    PACKAGING_AXIS_RESULTS = "packaging-axis-results"
    PACKAGING_FAMILY_ADMISSIBILITY = "packaging-family-admissibility"
    THREE_AXIS_HIERARCHY_CONFIG = "three-axis-hierarchy-config"
    THREE_AXIS_HIERARCHY_RESULTS = "three-axis-hierarchy-results"
    CLAIM_STRENGTH_REGISTRY = "claim-strength-registry"
    BEST_EVIDENCE_BY_AXIS = "best-evidence-by-axis"
    FROZEN_SLICE_SUPPORT_OBJECT = "frozen-slice-support-object"
    FROZEN_SLICE_COMPARISON_REGIME = "frozen-slice-comparison-regime"
    HIERARCHY_PROPOSITION_INDEX = "hierarchy-proposition-index"
    PACKAGE_CONFLICT_OBJECT = "package-conflict-object"
    PACKAGE_CONFLICT_RELATION = "package-conflict-relation"
    PAPER_EVIDENCE_PACK = "paper-evidence-pack"
    THEOREM_EXPERIMENT_MAP = "theorem-experiment-map"
    CAVEAT_REGISTRY = "caveat-registry"
    QUOTIENT_CLASS_LEDGER = "quotient-class-ledger"
    QUOTIENT_FEASIBILITY_AUDIT = "quotient-feasibility-audit"
    QUOTIENT_FEASIBILITY_RESULT = "quotient-feasibility-result"


VERSION_FIELDS: dict[SchemaKind, tuple[str, str]] = {
    SchemaKind.EVENT_PACKAGE_INSTANCE: (
        "instance_format_version",
        "event-package-instance.v1",
    ),
    SchemaKind.OBSERVATION_TRACE: ("trace_format_version", "observation-trace.v1"),
    SchemaKind.RUN_MANIFEST: ("manifest_format_version", "run-manifest.v1"),
    SchemaKind.RESULT_NOTE: ("note_format_version", "result-note.v1"),
    SchemaKind.SUBSTRATE_CONFIG: ("config_format_version", "substrate-config.v1"),
    SchemaKind.SUBSTRATE_RUN: ("run_format_version", "substrate-run.v1"),
    SchemaKind.DISCOVERED_CONTEXT_FAMILY: (
        "family_format_version",
        "discovered-context-family.v1",
    ),
    SchemaKind.DISCOVERED_EVENT_FAMILY: (
        "event_family_format_version",
        "discovered-event-family.v1",
    ),
    SchemaKind.SHARED_EVENT_CANDIDATES: (
        "candidates_format_version",
        "shared-event-candidates.v1",
    ),
    SchemaKind.HIDDEN_RECORD_INTERVENTION: (
        "intervention_format_version",
        "hidden-record-intervention.v1",
    ),
    SchemaKind.FLATTENING_INTERVENTION: (
        "intervention_format_version",
        "flattening-intervention.v1",
    ),
    SchemaKind.SEARCH_SWEEP: ("sweep_format_version", "search-sweep.v1"),
    SchemaKind.SEARCH_ATLAS: ("atlas_format_version", "search-atlas.v1"),
    SchemaKind.TARGETED_NONEXTENDABILITY_SEARCH: (
        "search_format_version",
        "targeted-nonextendability-search.v1",
    ),
    SchemaKind.TARGETED_SEARCH_RESULTS: (
        "table_format_version",
        "targeted-search-results.v1",
    ),
    SchemaKind.PICA_TARGETED_OBSTRUCTION_SEARCH: (
        "search_format_version",
        "pica-targeted-obstruction-search.v1",
    ),
    SchemaKind.PICA_TARGETED_SEARCH_RESULTS: (
        "table_format_version",
        "pica-targeted-search-results.v1",
    ),
    SchemaKind.PICA_CLOSURE_DIVERSE_SEARCH: (
        "search_format_version",
        "pica-closure-diverse-search.v1",
    ),
    SchemaKind.PICA_CLOSURE_DIVERSE_SEARCH_RESULTS: (
        "table_format_version",
        "pica-closure-diverse-search-results.v1",
    ),
    SchemaKind.CONTEXT_PAIR_STRUCTURE: (
        "structure_format_version",
        "context-pair-structure.v1",
    ),
    SchemaKind.PICA_FROZEN_SLICE_SEARCH: (
        "search_format_version",
        "pica-frozen-slice-search.v1",
    ),
    SchemaKind.PICA_FROZEN_SLICE_SEARCH_RESULTS: (
        "table_format_version",
        "pica-frozen-slice-search-results.v1",
    ),
    SchemaKind.PICA_PACKAGING_CONFLICT_SEARCH: (
        "search_format_version",
        "pica-packaging-conflict-search.v1",
    ),
    SchemaKind.PICA_PACKAGING_CONFLICT_SEARCH_RESULTS: (
        "table_format_version",
        "packaging-conflict-comparison-results.v1",
    ),
    SchemaKind.PROJECTION_FAMILY_ADMISSIBILITY: (
        "table_format_version",
        "projection-family-admissibility.v1",
    ),
    SchemaKind.ATLAS_UPGRADE_CONFIG: (
        "atlas_format_version",
        "atlas-upgrade-config.v1",
    ),
    SchemaKind.ATLAS_UPGRADE_RESULTS: (
        "table_format_version",
        "atlas-upgrade-results.v1",
    ),
    SchemaKind.DISCOVERED_CASE_FALSIFICATION: (
        "falsification_format_version",
        "discovered-case-falsification.v1",
    ),
    SchemaKind.DISCOVERED_CASE_FALSIFICATION_RESULT: (
        "result_format_version",
        "discovered-case-falsification-result.v1",
    ),
    SchemaKind.FLAGSHIP_CONTROL_BUNDLE: (
        "bundle_format_version",
        "flagship-control-bundle.v1",
    ),
    SchemaKind.FLAGSHIP_CONTROL_RESULT: (
        "result_format_version",
        "flagship-control-result.v1",
    ),
    SchemaKind.EXACT_CROSSCHECK: (
        "crosscheck_format_version",
        "exact-crosscheck.v1",
    ),
    SchemaKind.EXACT_CROSSCHECK_RESULT: (
        "result_format_version",
        "exact-crosscheck-result.v1",
    ),
    SchemaKind.NOISE_ROBUSTNESS_SWEEP: (
        "sweep_format_version",
        "noise-robustness-sweep.v1",
    ),
    SchemaKind.NOISE_ROBUSTNESS_TABLE: (
        "table_format_version",
        "noise-robustness-table.v1",
    ),
    SchemaKind.REDTEAM_SUITE: ("suite_format_version", "redteam-suite.v1"),
    SchemaKind.REDTEAM_RESULTS: ("table_format_version", "redteam-results.v1"),
    SchemaKind.PICA_EXPORT_BUNDLE: ("schema_version", "pica-export-bundle.v1"),
    SchemaKind.PICA_CAMPAIGN_EXPORT: ("schema_version", "pica-campaign-export.v1"),
    SchemaKind.PICA_RUN_LEDGER: ("schema_version", "pica-run-ledger.v1"),
    SchemaKind.PICA_CLOSURE_CATALOG: ("schema_version", "pica-closure-catalog.v1"),
    SchemaKind.PICA_OBSERVABLE_LEDGER: (
        "schema_version",
        "pica-observable-ledger.v1",
    ),
    SchemaKind.PICA_COMMUTATOR_CATALOG: (
        "schema_version",
        "pica-commutator-catalog.v1",
    ),
    SchemaKind.PICA_PACKAGING_OPERATOR_CATALOG: (
        "schema_version",
        "pica-packaging-operator-catalog.v1",
    ),
    SchemaKind.PICA_PACKAGING_SELECTION_LEDGER: (
        "schema_version",
        "pica-packaging-selection-ledger.v1",
    ),
    SchemaKind.PICA_PACKAGING_SURFACE: (
        "schema_version",
        "pica-packaging-surface.v1",
    ),
    SchemaKind.PICA_PILOT_CAMPAIGN: ("schema_version", "pica-pilot-campaign.v1"),
    SchemaKind.PICA_PILOT_RESULT: ("schema_version", "pica-pilot-result.v1"),
    SchemaKind.PICA_DISCOVERY_READINESS: (
        "schema_version",
        "pica-discovery-readiness.v1",
    ),
    SchemaKind.PICA_CONTEXT_DISCOVERY: (
        "schema_version",
        "pica-context-discovery.v1",
    ),
    SchemaKind.EVENT_ALGEBRA_COVERAGE: (
        "coverage_format_version",
        "event-algebra-coverage.v1",
    ),
    SchemaKind.PROBE_INDISTINGUISHABILITY_SIGNATURE: (
        "signatures_format_version",
        "probe-indistinguishability-signature.v1",
    ),
    SchemaKind.PACKAGE_PROVENANCE: (
        "provenance_format_version",
        "package-provenance.v1",
    ),
    SchemaKind.PROVENANCE_AUDIT_RESULT: (
        "audit_format_version",
        "provenance-audit-result.v1",
    ),
    SchemaKind.FINDINGS_REGISTRY_CONFIG: (
        "config_format_version",
        "findings-registry-config.v1",
    ),
    SchemaKind.FINDING_ENTRY: ("finding_format_version", "finding-entry.v1"),
    SchemaKind.CLAIM_EVIDENCE_MAP: (
        "claim_map_format_version",
        "claim-evidence-map.v1",
    ),
    SchemaKind.FINDINGS_REGISTRY: (
        "registry_format_version",
        "findings-registry.v1",
    ),
    SchemaKind.THREE_AXIS_SEARCH_CONFIG: (
        "config_format_version",
        "three-axis-search-config.v1",
    ),
    SchemaKind.THREE_AXIS_SEARCH_ROW: (
        "row_format_version",
        "three-axis-search-row.v1",
    ),
    SchemaKind.AXIS_CLAIM_LADDER: (
        "ladder_format_version",
        "axis-claim-ladder.v1",
    ),
    SchemaKind.SHARED_METRIC_SURFACE: (
        "metric_surface_format_version",
        "shared-metric-surface.v1",
    ),
    SchemaKind.MECHANISM_AXIS_SEARCH: (
        "search_format_version",
        "mechanism-axis-search.v1",
    ),
    SchemaKind.MECHANISM_AXIS_RESULTS: (
        "table_format_version",
        "mechanism-axis-results.v1",
    ),
    SchemaKind.LENS_AXIS_SEARCH: (
        "search_format_version",
        "lens-axis-search.v1",
    ),
    SchemaKind.LENS_AXIS_RESULTS: (
        "table_format_version",
        "lens-axis-results.v1",
    ),
    SchemaKind.LENS_FAMILY_ADMISSIBILITY: (
        "catalog_format_version",
        "lens-family-admissibility.v1",
    ),
    SchemaKind.LENS_AXIS_CROSS_RESOLUTION_ADJUDICATION: (
        "adjudication_format_version",
        "lens-axis-cross-resolution-adjudication.v1",
    ),
    SchemaKind.LENS_AXIS_FINALIZATION: (
        "config_format_version",
        "lens-axis-finalization.v1",
    ),
    SchemaKind.LENS_AXIS_FINAL_OUTCOME: (
        "final_outcome_format_version",
        "lens-axis-final-outcome.v1",
    ),
    SchemaKind.PACKAGING_AXIS_SEARCH: (
        "search_format_version",
        "packaging-axis-search.v1",
    ),
    SchemaKind.PACKAGING_AXIS_RESULTS: (
        "table_format_version",
        "packaging-axis-results.v1",
    ),
    SchemaKind.PACKAGING_FAMILY_ADMISSIBILITY: (
        "catalog_format_version",
        "packaging-family-admissibility.v1",
    ),
    SchemaKind.THREE_AXIS_HIERARCHY_CONFIG: (
        "config_format_version",
        "three-axis-hierarchy-config.v1",
    ),
    SchemaKind.THREE_AXIS_HIERARCHY_RESULTS: (
        "table_format_version",
        "three-axis-hierarchy-results.v1",
    ),
    SchemaKind.CLAIM_STRENGTH_REGISTRY: (
        "registry_format_version",
        "claim-strength-registry.v1",
    ),
    SchemaKind.BEST_EVIDENCE_BY_AXIS: (
        "mapping_format_version",
        "best-evidence-by-axis.v1",
    ),
    SchemaKind.FROZEN_SLICE_SUPPORT_OBJECT: (
        "object_format_version",
        "frozen-slice-support-object.v1",
    ),
    SchemaKind.FROZEN_SLICE_COMPARISON_REGIME: (
        "regime_format_version",
        "frozen-slice-comparison-regime.v1",
    ),
    SchemaKind.HIERARCHY_PROPOSITION_INDEX: (
        "index_format_version",
        "hierarchy-proposition-index.v1",
    ),
    SchemaKind.PACKAGE_CONFLICT_OBJECT: (
        "object_format_version",
        "package-conflict-object.v1",
    ),
    SchemaKind.PACKAGE_CONFLICT_RELATION: (
        "relation_format_version",
        "package-conflict-relation.v1",
    ),
    SchemaKind.PAPER_EVIDENCE_PACK: (
        "pack_format_version",
        "paper-evidence-pack.v1",
    ),
    SchemaKind.THEOREM_EXPERIMENT_MAP: (
        "map_format_version",
        "theorem-experiment-map.v1",
    ),
    SchemaKind.CAVEAT_REGISTRY: (
        "registry_format_version",
        "caveat-registry.v1",
    ),
    SchemaKind.QUOTIENT_CLASS_LEDGER: (
        "ledger_format_version",
        "quotient-class-ledger.v1",
    ),
    SchemaKind.QUOTIENT_FEASIBILITY_AUDIT: (
        "audit_format_version",
        "quotient-feasibility-audit.v1",
    ),
    SchemaKind.QUOTIENT_FEASIBILITY_RESULT: (
        "result_format_version",
        "quotient-feasibility-result.v1",
    ),
}


class SixBirdsModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


_DRIVE_PATTERN = re.compile(r"^[A-Za-z]:")


def is_repo_relative_path(value: str) -> bool:
    if not isinstance(value, str) or not value:
        return False
    if (
        value.startswith("/")
        or "://" in value
        or "\\" in value
        or _DRIVE_PATTERN.match(value)
    ):
        return False
    path = PurePosixPath(value)
    if path.is_absolute():
        return False
    if path.as_posix() != value:
        return False
    if any(part in {".", ".."} for part in path.parts):
        return False
    return True


def is_json_scalar(value: Any, *, allow_bool: bool = True) -> bool:
    if value is None:
        return True
    if isinstance(value, bool):
        return allow_bool
    if isinstance(value, str) or isinstance(value, int):
        return True
    if isinstance(value, float):
        return math.isfinite(value)
    return False


def ensure_metadata_shape(mapping: dict[str, MetadataValue]) -> None:
    for key, value in mapping.items():
        if not isinstance(key, str) or not key:
            raise ValueError("metadata keys must be non-empty strings")
        if isinstance(value, list):
            if not all(isinstance(item, str) for item in value):
                raise ValueError(f"metadata['{key}'] must be a flat list of strings")
            continue
        if not is_json_scalar(value):
            raise ValueError(
                f"metadata['{key}'] must be a JSON scalar or list of strings"
            )


def ensure_metric_shape(mapping: dict[str, MetricValue]) -> None:
    for key, value in mapping.items():
        if not isinstance(key, str) or not key:
            raise ValueError("metric names must be non-empty strings")
        if not is_json_scalar(value):
            raise ValueError(f"metrics['{key}'] must be a JSON scalar")


def ensure_repo_relative_mapping(mapping: dict[str, str], *, field_name: str) -> None:
    for key, value in mapping.items():
        if not isinstance(key, str) or not key:
            raise ValueError(f"{field_name} keys must be non-empty strings")
        if not is_repo_relative_path(value):
            raise ValueError(
                f"{field_name}['{key}'] must be a normalized repo-relative path"
            )


def collect_list_duplicates(values: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: list[str] = []
    for value in values:
        if value in seen and value not in duplicates:
            duplicates.append(value)
        seen.add(value)
    return duplicates
