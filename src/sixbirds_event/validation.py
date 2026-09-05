from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .schemas.common import SchemaKind, VERSION_FIELDS
from .schemas.event_package import EventPackageInstance
from .schemas.observation_trace import ObservationTrace
from .schemas.result_note import ResultNote
from .schemas.run_manifest import RunManifest
from .evidence.models import CaveatRegistry, PaperEvidencePack, TheoremExperimentMap
from .falsification.models import (
    DiscoveredCaseFalsification,
    DiscoveredCaseFalsificationResult,
    FlagshipControlBundle,
    FlagshipControlResult,
)
from .crosscheck.models import ExactCrosscheck, ExactCrosscheckResults
from .interventions.models import FlatteningIntervention, HiddenRecordIntervention
from .robustness.models import NoiseRobustnessSweep, NoiseRobustnessTable
from .redteam.models import RedteamResultsTable, RedteamSuite
from .provenance.models import PackageProvenance, ProvenanceAuditResult
from .pica_bridge.models import (
    PicaCampaignExport,
    PicaClosureCatalog,
    PicaCommutatorCatalog,
    PicaDiscoveryReadinessSummary,
    PicaExportBundle,
    PicaObservableLedger,
    PicaPackagingOperatorCatalog,
    PicaPackagingSelectionLedger,
    PicaPackagingSurface,
    PicaPilotCampaign,
    PicaPilotResult,
    PicaRunLedger,
)
from .findings.models import (
    ClaimEvidenceMap,
    FindingEntry,
    FindingsRegistry,
    FindingsRegistryConfig,
)
from .hierarchy.models import (
    AxisClaimLadder,
    BestEvidenceByAxis,
    FrozenSliceComparisonRegime,
    FrozenSliceSupportObject,
    HierarchyPropositionIndex,
    PackageConflictObject,
    PackageConflictRelation,
    SharedMetricSurface,
    ClaimStrengthRegistry,
    ThreeAxisHierarchyConfig,
    ThreeAxisHierarchyResults,
    ThreeAxisSearchConfig,
    ThreeAxisSearchRow,
)
from .audits.models import (
    QuotientClassLedger,
    QuotientFeasibilityAudit,
    QuotientFeasibilityResult,
)
from .discovery.models import (
    DiscoveredContextFamily,
    EventAlgebraCoverage,
    DiscoveredEventFamily,
    PicaContextDiscoveryConfig,
    ProbeIndistinguishabilitySignatureTable,
    SharedEventCandidates,
)
from .search.models import (
    AtlasUpgradeConfig,
    AtlasUpgradeTable,
    ContextPairStructureTable,
    LensAxisCrossResolutionAdjudication,
    LensAxisFinalOutcome,
    LensAxisFinalizationConfig,
    LensAxisSearch,
    LensAxisTable,
    LensFamilyAdmissibility,
    MechanismAxisSearch,
    MechanismAxisTable,
    PicaTargetedObstructionSearch,
    PicaTargetedSearchTable,
    PicaClosureDiverseSearch,
    PicaClosureDiverseSearchTable,
    PicaFrozenSliceSearch,
    PicaFrozenSliceSearchTable,
    PicaPackagingConflictSearch,
    PackagingAxisSearch,
    PackagingAxisTable,
    PackagingFamilyAdmissibility,
    PackagingConflictComparisonTable,
    ProjectionFamilyAdmissibilityTable,
    SearchAtlas,
    SearchSweep,
    TargetedNonextendabilitySearch,
    TargetedSearchTable,
)
from .substrates.config import SubstrateConfig
from .substrates.run_trace import SubstrateRun

SchemaModel = (
    EventPackageInstance
    | ObservationTrace
    | RunManifest
    | ResultNote
    | PaperEvidencePack
    | TheoremExperimentMap
    | CaveatRegistry
    | SubstrateConfig
    | SubstrateRun
    | DiscoveredContextFamily
    | DiscoveredEventFamily
    | PicaContextDiscoveryConfig
    | EventAlgebraCoverage
    | ProbeIndistinguishabilitySignatureTable
    | SharedEventCandidates
    | HiddenRecordIntervention
    | FlatteningIntervention
    | SearchSweep
    | SearchAtlas
    | TargetedNonextendabilitySearch
    | TargetedSearchTable
    | PicaTargetedObstructionSearch
    | PicaTargetedSearchTable
    | PicaClosureDiverseSearch
    | PicaClosureDiverseSearchTable
    | ContextPairStructureTable
    | PicaFrozenSliceSearch
    | PicaFrozenSliceSearchTable
    | PicaPackagingConflictSearch
    | PackagingConflictComparisonTable
    | ProjectionFamilyAdmissibilityTable
    | AtlasUpgradeConfig
    | AtlasUpgradeTable
    | DiscoveredCaseFalsification
    | DiscoveredCaseFalsificationResult
    | FlagshipControlBundle
    | FlagshipControlResult
    | ExactCrosscheck
    | ExactCrosscheckResults
    | NoiseRobustnessSweep
    | NoiseRobustnessTable
    | RedteamSuite
    | RedteamResultsTable
    | PicaExportBundle
    | PicaCampaignExport
    | PicaRunLedger
    | PicaClosureCatalog
    | PicaObservableLedger
    | PicaCommutatorCatalog
    | PicaPackagingOperatorCatalog
    | PicaPackagingSelectionLedger
    | PicaPackagingSurface
    | PicaPilotCampaign
    | PicaPilotResult
    | PicaDiscoveryReadinessSummary
    | PackageProvenance
    | ProvenanceAuditResult
    | FindingsRegistryConfig
    | FindingEntry
    | ClaimEvidenceMap
    | FindingsRegistry
    | ThreeAxisSearchConfig
    | ThreeAxisSearchRow
    | AxisClaimLadder
    | SharedMetricSurface
    | MechanismAxisSearch
    | MechanismAxisTable
    | LensAxisSearch
    | LensAxisTable
    | LensFamilyAdmissibility
    | LensAxisFinalizationConfig
    | LensAxisFinalOutcome
    | PackagingAxisSearch
    | PackagingAxisTable
    | PackagingFamilyAdmissibility
    | ThreeAxisHierarchyConfig
    | ThreeAxisHierarchyResults
    | ClaimStrengthRegistry
    | BestEvidenceByAxis
    | FrozenSliceSupportObject
    | FrozenSliceComparisonRegime
    | HierarchyPropositionIndex
    | PackageConflictObject
    | PackageConflictRelation
    | QuotientClassLedger
    | QuotientFeasibilityAudit
    | QuotientFeasibilityResult
)


@dataclass(slots=True)
class ValidationIssue:
    path: str
    message: str
    error_type: str | None = None


@dataclass(slots=True)
class ValidationResult:
    ok: bool
    kind: SchemaKind | None
    model: SchemaModel | None = None
    issues: list[ValidationIssue] = field(default_factory=list)


class SchemaValidationError(ValueError):
    def __init__(self, result: ValidationResult) -> None:
        self.result = result
        message = (
            "; ".join(
                f"{issue.path}: {issue.message}" if issue.path else issue.message
                for issue in result.issues
            )
            or "validation failed"
        )
        super().__init__(message)


MODEL_BY_KIND: dict[SchemaKind, type[SchemaModel]] = {
    SchemaKind.EVENT_PACKAGE_INSTANCE: EventPackageInstance,
    SchemaKind.OBSERVATION_TRACE: ObservationTrace,
    SchemaKind.RUN_MANIFEST: RunManifest,
    SchemaKind.RESULT_NOTE: ResultNote,
    SchemaKind.PAPER_EVIDENCE_PACK: PaperEvidencePack,
    SchemaKind.THEOREM_EXPERIMENT_MAP: TheoremExperimentMap,
    SchemaKind.CAVEAT_REGISTRY: CaveatRegistry,
    SchemaKind.SUBSTRATE_CONFIG: SubstrateConfig,
    SchemaKind.SUBSTRATE_RUN: SubstrateRun,
    SchemaKind.DISCOVERED_CONTEXT_FAMILY: DiscoveredContextFamily,
    SchemaKind.DISCOVERED_EVENT_FAMILY: DiscoveredEventFamily,
    SchemaKind.PICA_CONTEXT_DISCOVERY: PicaContextDiscoveryConfig,
    SchemaKind.EVENT_ALGEBRA_COVERAGE: EventAlgebraCoverage,
    SchemaKind.PROBE_INDISTINGUISHABILITY_SIGNATURE: (
        ProbeIndistinguishabilitySignatureTable
    ),
    SchemaKind.SHARED_EVENT_CANDIDATES: SharedEventCandidates,
    SchemaKind.HIDDEN_RECORD_INTERVENTION: HiddenRecordIntervention,
    SchemaKind.FLATTENING_INTERVENTION: FlatteningIntervention,
    SchemaKind.SEARCH_SWEEP: SearchSweep,
    SchemaKind.SEARCH_ATLAS: SearchAtlas,
    SchemaKind.TARGETED_NONEXTENDABILITY_SEARCH: TargetedNonextendabilitySearch,
    SchemaKind.TARGETED_SEARCH_RESULTS: TargetedSearchTable,
    SchemaKind.PICA_TARGETED_OBSTRUCTION_SEARCH: PicaTargetedObstructionSearch,
    SchemaKind.PICA_TARGETED_SEARCH_RESULTS: PicaTargetedSearchTable,
    SchemaKind.PICA_CLOSURE_DIVERSE_SEARCH: PicaClosureDiverseSearch,
    SchemaKind.PICA_CLOSURE_DIVERSE_SEARCH_RESULTS: PicaClosureDiverseSearchTable,
    SchemaKind.CONTEXT_PAIR_STRUCTURE: ContextPairStructureTable,
    SchemaKind.PICA_FROZEN_SLICE_SEARCH: PicaFrozenSliceSearch,
    SchemaKind.PICA_FROZEN_SLICE_SEARCH_RESULTS: PicaFrozenSliceSearchTable,
    SchemaKind.PICA_PACKAGING_CONFLICT_SEARCH: PicaPackagingConflictSearch,
    SchemaKind.PICA_PACKAGING_CONFLICT_SEARCH_RESULTS: PackagingConflictComparisonTable,
    SchemaKind.PROJECTION_FAMILY_ADMISSIBILITY: ProjectionFamilyAdmissibilityTable,
    SchemaKind.ATLAS_UPGRADE_CONFIG: AtlasUpgradeConfig,
    SchemaKind.ATLAS_UPGRADE_RESULTS: AtlasUpgradeTable,
    SchemaKind.DISCOVERED_CASE_FALSIFICATION: DiscoveredCaseFalsification,
    SchemaKind.DISCOVERED_CASE_FALSIFICATION_RESULT: (
        DiscoveredCaseFalsificationResult
    ),
    SchemaKind.FLAGSHIP_CONTROL_BUNDLE: FlagshipControlBundle,
    SchemaKind.FLAGSHIP_CONTROL_RESULT: FlagshipControlResult,
    SchemaKind.EXACT_CROSSCHECK: ExactCrosscheck,
    SchemaKind.EXACT_CROSSCHECK_RESULT: ExactCrosscheckResults,
    SchemaKind.NOISE_ROBUSTNESS_SWEEP: NoiseRobustnessSweep,
    SchemaKind.NOISE_ROBUSTNESS_TABLE: NoiseRobustnessTable,
    SchemaKind.REDTEAM_SUITE: RedteamSuite,
    SchemaKind.REDTEAM_RESULTS: RedteamResultsTable,
    SchemaKind.PICA_EXPORT_BUNDLE: PicaExportBundle,
    SchemaKind.PICA_CAMPAIGN_EXPORT: PicaCampaignExport,
    SchemaKind.PICA_RUN_LEDGER: PicaRunLedger,
    SchemaKind.PICA_CLOSURE_CATALOG: PicaClosureCatalog,
    SchemaKind.PICA_OBSERVABLE_LEDGER: PicaObservableLedger,
    SchemaKind.PICA_COMMUTATOR_CATALOG: PicaCommutatorCatalog,
    SchemaKind.PICA_PACKAGING_OPERATOR_CATALOG: PicaPackagingOperatorCatalog,
    SchemaKind.PICA_PACKAGING_SELECTION_LEDGER: PicaPackagingSelectionLedger,
    SchemaKind.PICA_PACKAGING_SURFACE: PicaPackagingSurface,
    SchemaKind.PICA_PILOT_CAMPAIGN: PicaPilotCampaign,
    SchemaKind.PICA_PILOT_RESULT: PicaPilotResult,
    SchemaKind.PICA_DISCOVERY_READINESS: PicaDiscoveryReadinessSummary,
    SchemaKind.PACKAGE_PROVENANCE: PackageProvenance,
    SchemaKind.PROVENANCE_AUDIT_RESULT: ProvenanceAuditResult,
    SchemaKind.FINDINGS_REGISTRY_CONFIG: FindingsRegistryConfig,
    SchemaKind.FINDING_ENTRY: FindingEntry,
    SchemaKind.CLAIM_EVIDENCE_MAP: ClaimEvidenceMap,
    SchemaKind.FINDINGS_REGISTRY: FindingsRegistry,
    SchemaKind.THREE_AXIS_SEARCH_CONFIG: ThreeAxisSearchConfig,
    SchemaKind.THREE_AXIS_SEARCH_ROW: ThreeAxisSearchRow,
    SchemaKind.AXIS_CLAIM_LADDER: AxisClaimLadder,
    SchemaKind.SHARED_METRIC_SURFACE: SharedMetricSurface,
    SchemaKind.MECHANISM_AXIS_SEARCH: MechanismAxisSearch,
    SchemaKind.MECHANISM_AXIS_RESULTS: MechanismAxisTable,
    SchemaKind.LENS_AXIS_SEARCH: LensAxisSearch,
    SchemaKind.LENS_AXIS_RESULTS: LensAxisTable,
    SchemaKind.LENS_FAMILY_ADMISSIBILITY: LensFamilyAdmissibility,
    SchemaKind.LENS_AXIS_CROSS_RESOLUTION_ADJUDICATION: (
        LensAxisCrossResolutionAdjudication
    ),
    SchemaKind.LENS_AXIS_FINALIZATION: LensAxisFinalizationConfig,
    SchemaKind.LENS_AXIS_FINAL_OUTCOME: LensAxisFinalOutcome,
    SchemaKind.PACKAGING_AXIS_SEARCH: PackagingAxisSearch,
    SchemaKind.PACKAGING_AXIS_RESULTS: PackagingAxisTable,
    SchemaKind.PACKAGING_FAMILY_ADMISSIBILITY: PackagingFamilyAdmissibility,
    SchemaKind.THREE_AXIS_HIERARCHY_CONFIG: ThreeAxisHierarchyConfig,
    SchemaKind.THREE_AXIS_HIERARCHY_RESULTS: ThreeAxisHierarchyResults,
    SchemaKind.CLAIM_STRENGTH_REGISTRY: ClaimStrengthRegistry,
    SchemaKind.BEST_EVIDENCE_BY_AXIS: BestEvidenceByAxis,
    SchemaKind.FROZEN_SLICE_SUPPORT_OBJECT: FrozenSliceSupportObject,
    SchemaKind.FROZEN_SLICE_COMPARISON_REGIME: FrozenSliceComparisonRegime,
    SchemaKind.HIERARCHY_PROPOSITION_INDEX: HierarchyPropositionIndex,
    SchemaKind.PACKAGE_CONFLICT_OBJECT: PackageConflictObject,
    SchemaKind.PACKAGE_CONFLICT_RELATION: PackageConflictRelation,
    SchemaKind.QUOTIENT_CLASS_LEDGER: QuotientClassLedger,
    SchemaKind.QUOTIENT_FEASIBILITY_AUDIT: QuotientFeasibilityAudit,
    SchemaKind.QUOTIENT_FEASIBILITY_RESULT: QuotientFeasibilityResult,
}


def _format_loc(loc: tuple[Any, ...]) -> str:
    if not loc:
        return "__root__"
    parts: list[str] = []
    for item in loc:
        if isinstance(item, int):
            if parts:
                parts[-1] = f"{parts[-1]}[{item}]"
            else:
                parts.append(f"[{item}]")
            continue
        if parts:
            parts.append(f".{item}")
        else:
            parts.append(str(item))
    return "".join(parts)


def _issues_from_exception(exc: ValidationError) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for error in exc.errors():
        loc = error.get("loc", ())
        issues.append(
            ValidationIssue(
                path=_format_loc(tuple(loc) if isinstance(loc, tuple) else tuple(loc)),
                message=error.get("msg", "validation error"),
                error_type=error.get("type"),
            )
        )
    return issues


def load_json_file(path: str | Path) -> Any:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _detect_kind(payload: Any) -> SchemaKind | None:
    if not isinstance(payload, dict):
        return None
    for kind, (field_name, expected_value) in VERSION_FIELDS.items():
        if payload.get(field_name) == expected_value:
            return kind
    return None


def _result_from_model(
    kind: SchemaKind, model_cls: type[SchemaModel], payload: Any
) -> ValidationResult:
    try:
        model = model_cls.model_validate(payload)
    except ValidationError as exc:
        return ValidationResult(
            ok=False,
            kind=kind,
            issues=_issues_from_exception(exc),
        )
    return ValidationResult(ok=True, kind=kind, model=model)


def validate_payload(
    payload: Any, *, kind: SchemaKind | str = "auto"
) -> ValidationResult:
    if kind == "auto":
        detected = _detect_kind(payload)
        if detected is None:
            return ValidationResult(
                ok=False,
                kind=None,
                issues=[
                    ValidationIssue(
                        path="__root__",
                        message="unable to detect schema kind from version field",
                    )
                ],
            )
        kind = detected
    if isinstance(kind, str):
        try:
            kind = SchemaKind(kind)
        except ValueError:
            return ValidationResult(
                ok=False,
                kind=None,
                issues=[
                    ValidationIssue(
                        path="__root__", message=f"unknown schema kind '{kind}'"
                    )
                ],
            )

    model_cls = MODEL_BY_KIND[kind]
    return _result_from_model(kind, model_cls, payload)


def validate_file(
    path: str | Path, *, kind: SchemaKind | str = "auto"
) -> ValidationResult:
    try:
        payload = load_json_file(path)
    except (OSError, json.JSONDecodeError) as exc:
        return ValidationResult(
            ok=False,
            kind=None,
            issues=[ValidationIssue(path="__root__", message=str(exc))],
        )
    return validate_payload(payload, kind=kind)


def load_model(path: str | Path, *, kind: SchemaKind | str = "auto") -> SchemaModel:
    result = validate_file(path, kind=kind)
    if not result.ok or result.model is None:
        raise SchemaValidationError(result)
    return result.model


def validate_observation_trace(
    trace: Any,
    *,
    linked_instance: EventPackageInstance | None = None,
) -> ValidationResult:
    result = validate_payload(trace, kind=SchemaKind.OBSERVATION_TRACE)
    if not result.ok or not isinstance(result.model, ObservationTrace):
        return result
    if linked_instance is None:
        return result

    if (
        result.model.instance_id is not None
        and result.model.instance_id != linked_instance.instance_id
    ):
        return ValidationResult(
            ok=False,
            kind=result.kind,
            issues=[
                ValidationIssue(
                    path="instance_id",
                    message=(
                        "trace instance_id must match the linked instance_id when linkage validation is requested"
                    ),
                )
            ],
        )

    context_ids = {context.context_id for context in linked_instance.contexts}
    atoms_by_context = {
        context.context_id: {atom.atom_id for atom in context.atoms}
        for context in linked_instance.contexts
    }
    event_by_id = {event.event_id: event for event in linked_instance.events}
    issues: list[ValidationIssue] = []
    for index, observation in enumerate(result.model.observations):
        if observation.context_id not in context_ids:
            issues.append(
                ValidationIssue(
                    path=f"observations[{index}].context_id",
                    message=f"unknown context_id '{observation.context_id}' for linked instance",
                )
            )
            continue
        if not set(observation.atom_ids).issubset(
            atoms_by_context[observation.context_id]
        ):
            issues.append(
                ValidationIssue(
                    path=f"observations[{index}].atom_ids",
                    message="atom_ids must be a subset of the linked instance context atoms",
                )
            )
    for index, sequence in enumerate(result.model.repeated_read_sequences):
        if sequence.context_id not in context_ids:
            issues.append(
                ValidationIssue(
                    path=f"repeated_read_sequences[{index}].context_id",
                    message=f"unknown context_id '{sequence.context_id}' for linked instance",
                )
            )
            continue
        allowed_atoms = atoms_by_context[sequence.context_id]
        for read_index, read in enumerate(sequence.reads):
            if not set(read).issubset(allowed_atoms):
                issues.append(
                    ValidationIssue(
                        path=f"repeated_read_sequences[{index}].reads[{read_index}]",
                        message="read atom_ids must be a subset of the linked instance context atoms",
                    )
                )
    for index, probe in enumerate(result.model.downstream_probes):
        if probe.event_id is not None:
            event = event_by_id.get(probe.event_id)
            if event is None:
                issues.append(
                    ValidationIssue(
                        path=f"downstream_probes[{index}].event_id",
                        message=f"unknown event_id '{probe.event_id}' for linked instance",
                    )
                )
                continue
            if probe.context_id is not None and probe.context_id != event.context_id:
                issues.append(
                    ValidationIssue(
                        path=f"downstream_probes[{index}].context_id",
                        message="probe context_id must match the referenced event context",
                    )
                )
        elif probe.context_id is not None and probe.context_id not in context_ids:
            issues.append(
                ValidationIssue(
                    path=f"downstream_probes[{index}].context_id",
                    message=f"unknown context_id '{probe.context_id}' for linked instance",
                )
            )
    for index, route_observation in enumerate(result.model.route_observations):
        if (
            route_observation.context_id is not None
            and route_observation.context_id not in context_ids
        ):
            issues.append(
                ValidationIssue(
                    path=f"route_observations[{index}].context_id",
                    message=f"unknown context_id '{route_observation.context_id}' for linked instance",
                )
            )
    if issues:
        return ValidationResult(ok=False, kind=result.kind, issues=issues)
    return result
