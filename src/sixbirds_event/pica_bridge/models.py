from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from ..schemas.common import (
    MetadataValue,
    SixBirdsModel,
    collect_list_duplicates,
    ensure_metadata_shape,
    ensure_repo_relative_mapping,
)


PathPolicy = Literal["repo_relative", "bundle_relative"]
PicaPilotCommandMode = Literal["cargo_runner_release"]
PicaPilotExportMode = Literal["adapter_export", "native_export"]
PicaObservationExportMode = Literal[
    "aggregate_summary",
    "discovery_grade_per_trajectory",
]
PicaPilotArtifactOutputMode = Literal["run_dir"]
BridgeValidationStatus = Literal["validated", "failed"]
PicaObservationGranularity = Literal["aggregate_summary", "per_trajectory"]
PicaCooccurrenceScope = Literal[
    "none",
    "within_run",
    "within_run_and_trajectory",
]
PicaDiscoveryReadinessClassification = Literal[
    "discovery_grade_ready",
    "discovery_grade_inadequate",
]
PicaPackagingSelectionStatus = Literal["selected", "candidate", "not_available"]


class PicaArtifactRef(SixBirdsModel):
    artifact_path: str

    @model_validator(mode="after")
    def validate_ref(self) -> "PicaArtifactRef":
        ensure_repo_relative_mapping(
            {"artifact_path": self.artifact_path},
            field_name="artifact_path",
        )
        return self


class PicaCampaignExportRef(PicaArtifactRef):
    campaign_id: str

    @model_validator(mode="after")
    def validate_ref(self) -> "PicaCampaignExportRef":
        super().validate_ref()
        if not self.campaign_id:
            raise ValueError("campaign_id must be a non-empty string")
        return self


class PicaRunLedgerRef(PicaArtifactRef):
    run_id: str
    campaign_id: str

    @model_validator(mode="after")
    def validate_ref(self) -> "PicaRunLedgerRef":
        super().validate_ref()
        for name in ["run_id", "campaign_id"]:
            if not getattr(self, name):
                raise ValueError(f"{name} must be a non-empty string")
        return self


class PicaClosureCatalogRef(PicaArtifactRef):
    closure_catalog_id: str
    run_id: str

    @model_validator(mode="after")
    def validate_ref(self) -> "PicaClosureCatalogRef":
        super().validate_ref()
        for name in ["closure_catalog_id", "run_id"]:
            if not getattr(self, name):
                raise ValueError(f"{name} must be a non-empty string")
        return self


class PicaObservableLedgerRef(PicaArtifactRef):
    observable_ledger_id: str
    run_id: str

    @model_validator(mode="after")
    def validate_ref(self) -> "PicaObservableLedgerRef":
        super().validate_ref()
        for name in ["observable_ledger_id", "run_id"]:
            if not getattr(self, name):
                raise ValueError(f"{name} must be a non-empty string")
        return self


class PicaCommutatorCatalogRef(PicaArtifactRef):
    commutator_catalog_id: str
    run_id: str

    @model_validator(mode="after")
    def validate_ref(self) -> "PicaCommutatorCatalogRef":
        super().validate_ref()
        for name in ["commutator_catalog_id", "run_id"]:
            if not getattr(self, name):
                raise ValueError(f"{name} must be a non-empty string")
        return self


class PicaPackagingOperatorCatalogRef(PicaArtifactRef):
    packaging_operator_catalog_id: str
    run_id: str

    @model_validator(mode="after")
    def validate_ref(self) -> "PicaPackagingOperatorCatalogRef":
        super().validate_ref()
        for name in ["packaging_operator_catalog_id", "run_id"]:
            if not getattr(self, name):
                raise ValueError(f"{name} must be a non-empty string")
        return self


class PicaPackagingSelectionLedgerRef(PicaArtifactRef):
    packaging_selection_ledger_id: str
    run_id: str

    @model_validator(mode="after")
    def validate_ref(self) -> "PicaPackagingSelectionLedgerRef":
        super().validate_ref()
        for name in ["packaging_selection_ledger_id", "run_id"]:
            if not getattr(self, name):
                raise ValueError(f"{name} must be a non-empty string")
        return self


class PicaProducerMetadata(SixBirdsModel):
    name: str
    version: str | None = None
    commit: str | None = None
    build_label: str | None = None

    @model_validator(mode="after")
    def validate_metadata(self) -> "PicaProducerMetadata":
        if not self.name:
            raise ValueError("name must be a non-empty string")
        for name in ["version", "commit", "build_label"]:
            value = getattr(self, name)
            if value is not None and not value:
                raise ValueError(f"{name} must be non-empty when present")
        return self


class PicaExportBundle(SixBirdsModel):
    schema_version: str
    export_bundle_id: str
    producer: PicaProducerMetadata
    export_timestamp: str
    path_policy: PathPolicy
    campaign_exports: list[PicaCampaignExportRef]
    run_ledgers: list[PicaRunLedgerRef]
    closure_catalogs: list[PicaClosureCatalogRef]
    observable_ledgers: list[PicaObservableLedgerRef]
    commutator_catalogs: list[PicaCommutatorCatalogRef] = Field(default_factory=list)
    packaging_operator_catalogs: list[PicaPackagingOperatorCatalogRef] = Field(
        default_factory=list
    )
    packaging_selection_ledgers: list[PicaPackagingSelectionLedgerRef] = Field(
        default_factory=list
    )
    notes: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)
    debug_sidecars: list[PicaArtifactRef] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_bundle(self) -> "PicaExportBundle":
        if self.schema_version != "pica-export-bundle.v1":
            raise ValueError("schema_version must equal 'pica-export-bundle.v1'")
        if not self.export_bundle_id:
            raise ValueError("export_bundle_id must be a non-empty string")
        for name, values in [
            ("campaign_exports", [row.campaign_id for row in self.campaign_exports]),
            ("run_ledgers", [row.run_id for row in self.run_ledgers]),
            (
                "closure_catalogs",
                [row.closure_catalog_id for row in self.closure_catalogs],
            ),
            (
                "observable_ledgers",
                [row.observable_ledger_id for row in self.observable_ledgers],
            ),
            (
                "commutator_catalogs",
                [row.commutator_catalog_id for row in self.commutator_catalogs],
            ),
            (
                "packaging_operator_catalogs",
                [
                    row.packaging_operator_catalog_id
                    for row in self.packaging_operator_catalogs
                ],
            ),
            (
                "packaging_selection_ledgers",
                [
                    row.packaging_selection_ledger_id
                    for row in self.packaging_selection_ledgers
                ],
            ),
        ]:
            duplicates = collect_list_duplicates(values)
            if duplicates:
                raise ValueError(
                    f"{name} must be unique by ID: {', '.join(duplicates)}"
                )
        for name, values in [("notes", self.notes), ("flags", self.flags)]:
            if any(not value for value in values):
                raise ValueError(f"{name} must contain only non-empty strings")
        return self


class PicaMechanismSummary(SixBirdsModel):
    substrate_config_id: str
    mechanism_family_id: str
    enable_matrix_id: str | None = None

    @model_validator(mode="after")
    def validate_summary(self) -> "PicaMechanismSummary":
        for name in ["substrate_config_id", "mechanism_family_id"]:
            if not getattr(self, name):
                raise ValueError(f"{name} must be a non-empty string")
        if self.enable_matrix_id is not None and not self.enable_matrix_id:
            raise ValueError("enable_matrix_id must be non-empty when present")
        return self


class PicaCampaignPoint(SixBirdsModel):
    point_id: str
    substrate_config_id: str
    mechanism_family_id: str
    enable_matrix_id: str | None = None
    preparation_id: str
    protocol_id: str
    seed: int
    run_id: str

    @model_validator(mode="after")
    def validate_point(self) -> "PicaCampaignPoint":
        for name in [
            "point_id",
            "substrate_config_id",
            "mechanism_family_id",
            "preparation_id",
            "protocol_id",
            "run_id",
        ]:
            if not getattr(self, name):
                raise ValueError(f"{name} must be a non-empty string")
        if self.enable_matrix_id is not None and not self.enable_matrix_id:
            raise ValueError("enable_matrix_id must be non-empty when present")
        if isinstance(self.seed, bool):
            raise ValueError("seed must be an integer")
        return self


class PicaCampaignRunInventory(SixBirdsModel):
    run_id: str
    point_id: str
    run_ledger_path: str
    closure_catalog_path: str
    observable_ledger_path: str
    commutator_catalog_path: str | None = None
    packaging_operator_catalog_path: str | None = None
    packaging_selection_ledger_path: str | None = None

    @model_validator(mode="after")
    def validate_inventory(self) -> "PicaCampaignRunInventory":
        for name in ["run_id", "point_id"]:
            if not getattr(self, name):
                raise ValueError(f"{name} must be a non-empty string")
        ensure_repo_relative_mapping(
            {
                "run_ledger_path": self.run_ledger_path,
                "closure_catalog_path": self.closure_catalog_path,
                "observable_ledger_path": self.observable_ledger_path,
            },
            field_name="run_inventory",
        )
        if self.commutator_catalog_path is not None:
            ensure_repo_relative_mapping(
                {"commutator_catalog_path": self.commutator_catalog_path},
                field_name="commutator_catalog_path",
            )
        for name in [
            "packaging_operator_catalog_path",
            "packaging_selection_ledger_path",
        ]:
            value = getattr(self, name)
            if value is not None:
                ensure_repo_relative_mapping({name: value}, field_name=name)
        return self


class PicaCampaignExport(SixBirdsModel):
    schema_version: str
    campaign_id: str
    campaign_label: str
    source_config_path: str
    path_policy: PathPolicy
    mechanism_summary: PicaMechanismSummary
    point_inventory: list[PicaCampaignPoint]
    run_inventory: list[PicaCampaignRunInventory]
    notes: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_campaign(self) -> "PicaCampaignExport":
        if self.schema_version != "pica-campaign-export.v1":
            raise ValueError("schema_version must equal 'pica-campaign-export.v1'")
        for name in ["campaign_id", "campaign_label"]:
            if not getattr(self, name):
                raise ValueError(f"{name} must be a non-empty string")
        ensure_repo_relative_mapping(
            {"source_config_path": self.source_config_path},
            field_name="source_config_path",
        )
        point_duplicates = collect_list_duplicates(
            [row.point_id for row in self.point_inventory]
        )
        if point_duplicates:
            raise ValueError(
                f"point_inventory must be unique by point_id: {', '.join(point_duplicates)}"
            )
        run_duplicates = collect_list_duplicates(
            [row.run_id for row in self.run_inventory]
        )
        if run_duplicates:
            raise ValueError(
                f"run_inventory must be unique by run_id: {', '.join(run_duplicates)}"
            )
        for name, values in [("notes", self.notes), ("flags", self.flags)]:
            if any(not value for value in values):
                raise ValueError(f"{name} must contain only non-empty strings")
        return self


class PicaProtocolStep(SixBirdsModel):
    step_index: int
    protocol_step_id: str
    stage_label: str | None = None
    action_label: str | None = None

    @model_validator(mode="after")
    def validate_step(self) -> "PicaProtocolStep":
        if isinstance(self.step_index, bool) or self.step_index < 0:
            raise ValueError("step_index must be a non-negative integer")
        if not self.protocol_step_id:
            raise ValueError("protocol_step_id must be a non-empty string")
        for name in ["stage_label", "action_label"]:
            value = getattr(self, name)
            if value is not None and not value:
                raise ValueError(f"{name} must be non-empty when present")
        return self


class PicaRunLedger(SixBirdsModel):
    schema_version: str
    run_id: str
    campaign_id: str
    point_id: str
    substrate_config_id: str
    mechanism_family_id: str
    enable_matrix_id: str | None = None
    preparation_id: str
    protocol_id: str
    seed: int
    trajectory_count: int
    protocol_steps: list[PicaProtocolStep]
    closure_catalog_id: str
    closure_catalog_path: str
    observable_ledger_id: str
    observable_ledger_path: str
    commutator_catalog_id: str | None = None
    commutator_catalog_path: str | None = None
    packaging_operator_catalog_id: str | None = None
    packaging_operator_catalog_path: str | None = None
    packaging_selection_ledger_id: str | None = None
    packaging_selection_ledger_path: str | None = None
    notes: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)
    debug_sidecars: list[PicaArtifactRef] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_run_ledger(self) -> "PicaRunLedger":
        if self.schema_version != "pica-run-ledger.v1":
            raise ValueError("schema_version must equal 'pica-run-ledger.v1'")
        for name in [
            "run_id",
            "campaign_id",
            "point_id",
            "substrate_config_id",
            "mechanism_family_id",
            "preparation_id",
            "protocol_id",
            "closure_catalog_id",
            "observable_ledger_id",
        ]:
            if not getattr(self, name):
                raise ValueError(f"{name} must be a non-empty string")
        if self.enable_matrix_id is not None and not self.enable_matrix_id:
            raise ValueError("enable_matrix_id must be non-empty when present")
        if isinstance(self.seed, bool):
            raise ValueError("seed must be an integer")
        if isinstance(self.trajectory_count, bool) or self.trajectory_count <= 0:
            raise ValueError("trajectory_count must be a positive integer")
        ensure_repo_relative_mapping(
            {
                "closure_catalog_path": self.closure_catalog_path,
                "observable_ledger_path": self.observable_ledger_path,
            },
            field_name="run_ledger",
        )
        for name in [
            "commutator_catalog_id",
            "packaging_operator_catalog_id",
            "packaging_selection_ledger_id",
        ]:
            value = getattr(self, name)
            if value is not None and not value:
                raise ValueError(f"{name} must be non-empty when present")
        for name in [
            "commutator_catalog_path",
            "packaging_operator_catalog_path",
            "packaging_selection_ledger_path",
        ]:
            value = getattr(self, name)
            if value is not None:
                ensure_repo_relative_mapping({name: value}, field_name=name)
        step_ids = [row.protocol_step_id for row in self.protocol_steps]
        duplicates = collect_list_duplicates(step_ids)
        if duplicates:
            raise ValueError(
                f"protocol_steps must be unique by protocol_step_id: {', '.join(duplicates)}"
            )
        step_indices = [row.step_index for row in self.protocol_steps]
        if step_indices != sorted(step_indices):
            raise ValueError("protocol_steps must be ordered by step_index")
        if len(set(step_indices)) != len(step_indices):
            raise ValueError("protocol_steps must be unique by step_index")
        return self


class PicaLevelRecord(SixBirdsModel):
    level_id: str
    label: str
    role: str
    parent_level_id: str | None = None

    @model_validator(mode="after")
    def validate_record(self) -> "PicaLevelRecord":
        for name in ["level_id", "label", "role"]:
            if not getattr(self, name):
                raise ValueError(f"{name} must be a non-empty string")
        if self.parent_level_id is not None and not self.parent_level_id:
            raise ValueError("parent_level_id must be non-empty when present")
        return self


class PicaResolutionRecord(SixBirdsModel):
    resolution_id: str
    level_id: str
    label: str
    role: str
    parent_resolution_id: str | None = None

    @model_validator(mode="after")
    def validate_record(self) -> "PicaResolutionRecord":
        for name in ["resolution_id", "level_id", "label", "role"]:
            if not getattr(self, name):
                raise ValueError(f"{name} must be a non-empty string")
        if self.parent_resolution_id is not None and not self.parent_resolution_id:
            raise ValueError("parent_resolution_id must be non-empty when present")
        return self


class PicaClosureRecord(SixBirdsModel):
    closure_id: str
    level_id: str
    resolution_id: str
    label: str
    role: str
    parent_closure_id: str | None = None
    support_metadata: dict[str, MetadataValue] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)
    debug_metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_record(self) -> "PicaClosureRecord":
        for name in ["closure_id", "level_id", "resolution_id", "label", "role"]:
            if not getattr(self, name):
                raise ValueError(f"{name} must be a non-empty string")
        if self.parent_closure_id is not None and not self.parent_closure_id:
            raise ValueError("parent_closure_id must be non-empty when present")
        ensure_metadata_shape(self.support_metadata)
        ensure_metadata_shape(self.debug_metadata)
        if any(not value for value in self.notes + self.flags):
            raise ValueError("notes and flags must contain only non-empty strings")
        return self


class PicaLensRecord(SixBirdsModel):
    lens_id: str
    level_id: str
    resolution_id: str
    closure_id: str
    label: str
    role: str
    ancestor_lens_id: str | None = None
    support_metadata: dict[str, MetadataValue] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)
    debug_metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_record(self) -> "PicaLensRecord":
        for name in [
            "lens_id",
            "level_id",
            "resolution_id",
            "closure_id",
            "label",
            "role",
        ]:
            if not getattr(self, name):
                raise ValueError(f"{name} must be a non-empty string")
        if self.ancestor_lens_id is not None and not self.ancestor_lens_id:
            raise ValueError("ancestor_lens_id must be non-empty when present")
        ensure_metadata_shape(self.support_metadata)
        ensure_metadata_shape(self.debug_metadata)
        if any(not value for value in self.notes + self.flags):
            raise ValueError("notes and flags must contain only non-empty strings")
        return self


class PicaClosureCatalog(SixBirdsModel):
    schema_version: str
    closure_catalog_id: str
    campaign_id: str
    run_id: str
    point_id: str
    levels: list[PicaLevelRecord]
    resolutions: list[PicaResolutionRecord]
    closures: list[PicaClosureRecord]
    lenses: list[PicaLensRecord]
    notes: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_catalog(self) -> "PicaClosureCatalog":
        if self.schema_version != "pica-closure-catalog.v1":
            raise ValueError("schema_version must equal 'pica-closure-catalog.v1'")
        for name in ["closure_catalog_id", "campaign_id", "run_id", "point_id"]:
            if not getattr(self, name):
                raise ValueError(f"{name} must be a non-empty string")
        level_ids = [row.level_id for row in self.levels]
        resolution_ids = [row.resolution_id for row in self.resolutions]
        closure_ids = [row.closure_id for row in self.closures]
        lens_ids = [row.lens_id for row in self.lenses]
        for name, values in [
            ("levels", level_ids),
            ("resolutions", resolution_ids),
            ("closures", closure_ids),
            ("lenses", lens_ids),
        ]:
            duplicates = collect_list_duplicates(values)
            if duplicates:
                raise ValueError(
                    f"{name} must be unique by ID: {', '.join(duplicates)}"
                )
        level_id_set = set(level_ids)
        resolution_id_set = set(resolution_ids)
        closure_id_set = set(closure_ids)
        for resolution in self.resolutions:
            if resolution.level_id not in level_id_set:
                raise ValueError(
                    f"resolution '{resolution.resolution_id}' references unknown level_id '{resolution.level_id}'"
                )
        for closure in self.closures:
            if closure.level_id not in level_id_set:
                raise ValueError(
                    f"closure '{closure.closure_id}' references unknown level_id '{closure.level_id}'"
                )
            if closure.resolution_id not in resolution_id_set:
                raise ValueError(
                    f"closure '{closure.closure_id}' references unknown resolution_id '{closure.resolution_id}'"
                )
        for lens in self.lenses:
            if lens.level_id not in level_id_set:
                raise ValueError(
                    f"lens '{lens.lens_id}' references unknown level_id '{lens.level_id}'"
                )
            if lens.resolution_id not in resolution_id_set:
                raise ValueError(
                    f"lens '{lens.lens_id}' references unknown resolution_id '{lens.resolution_id}'"
                )
            if lens.closure_id not in closure_id_set:
                raise ValueError(
                    f"lens '{lens.lens_id}' references unknown closure_id '{lens.closure_id}'"
                )
        return self


class PicaObservableRow(SixBirdsModel):
    trajectory_id: str
    step_index: int
    protocol_step_id: str
    preparation_id: str
    protocol_id: str
    level_id: str
    resolution_id: str
    closure_id: str
    lens_id: str
    observation_label: str
    route_label: str | None = None
    phase_label: str | None = None
    macrostate_label: str | None = None
    observation_payload: dict[str, MetadataValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_row(self) -> "PicaObservableRow":
        for name in [
            "trajectory_id",
            "protocol_step_id",
            "preparation_id",
            "protocol_id",
            "level_id",
            "resolution_id",
            "closure_id",
            "lens_id",
            "observation_label",
        ]:
            if not getattr(self, name):
                raise ValueError(f"{name} must be a non-empty string")
        if isinstance(self.step_index, bool) or self.step_index < 0:
            raise ValueError("step_index must be a non-negative integer")
        for name in ["route_label", "phase_label", "macrostate_label"]:
            value = getattr(self, name)
            if value is not None and not value:
                raise ValueError(f"{name} must be non-empty when present")
        ensure_metadata_shape(self.observation_payload)
        return self


class PicaObservableLedger(SixBirdsModel):
    schema_version: str
    observable_ledger_id: str
    campaign_id: str
    run_id: str
    point_id: str
    observation_granularity: PicaObservationGranularity = "aggregate_summary"
    cooccurrence_scope: PicaCooccurrenceScope = "none"
    trajectory_count: int = 0
    supports_structural_probe_conditioning: bool = False
    row_count: int
    rows: list[PicaObservableRow]
    notes: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)
    debug_sidecars: list[PicaArtifactRef] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_ledger(self) -> "PicaObservableLedger":
        if self.schema_version != "pica-observable-ledger.v1":
            raise ValueError("schema_version must equal 'pica-observable-ledger.v1'")
        for name in ["observable_ledger_id", "campaign_id", "run_id", "point_id"]:
            if not getattr(self, name):
                raise ValueError(f"{name} must be a non-empty string")
        if isinstance(self.trajectory_count, bool) or self.trajectory_count < 0:
            raise ValueError("trajectory_count must be a non-negative integer")
        if isinstance(self.row_count, bool) or self.row_count < 0:
            raise ValueError("row_count must be a non-negative integer")
        if self.row_count != len(self.rows):
            raise ValueError("row_count must equal len(rows)")
        trajectory_ids = {row.trajectory_id for row in self.rows}
        inferred_trajectory_count = len(trajectory_ids)
        if self.trajectory_count == 0:
            self.trajectory_count = inferred_trajectory_count
        if self.trajectory_count and inferred_trajectory_count != self.trajectory_count:
            raise ValueError(
                "trajectory_count must equal the number of distinct trajectory_id values"
            )
        row_keys = [
            (
                row.trajectory_id,
                row.step_index,
                row.protocol_step_id,
                row.lens_id,
                row.observation_label,
            )
            for row in self.rows
        ]
        if len(set(row_keys)) != len(row_keys):
            raise ValueError(
                "rows must be unique by (trajectory_id, step_index, protocol_step_id, lens_id, observation_label)"
            )
        if self.supports_structural_probe_conditioning:
            if self.observation_granularity != "per_trajectory":
                raise ValueError(
                    "supports_structural_probe_conditioning requires observation_granularity='per_trajectory'"
                )
            if self.cooccurrence_scope != "within_run_and_trajectory":
                raise ValueError(
                    "supports_structural_probe_conditioning requires cooccurrence_scope='within_run_and_trajectory'"
                )
        return self


class PicaCommutatorEntry(SixBirdsModel):
    pair_id: str
    primitive_pair: str
    metric_name: str
    metric_value: float
    nonzero: bool
    notes: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_entry(self) -> "PicaCommutatorEntry":
        for name in ["pair_id", "primitive_pair", "metric_name"]:
            if not getattr(self, name):
                raise ValueError(f"{name} must be a non-empty string")
        if isinstance(self.metric_value, bool):
            raise ValueError("metric_value must be numeric")
        if any(not value for value in self.notes + self.flags):
            raise ValueError("notes and flags must contain only non-empty strings")
        return self


class PicaCommutatorCatalog(SixBirdsModel):
    schema_version: str
    commutator_catalog_id: str
    campaign_id: str
    run_id: str
    point_id: str
    row_count: int
    rows: list[PicaCommutatorEntry]
    notes: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_catalog(self) -> "PicaCommutatorCatalog":
        if self.schema_version != "pica-commutator-catalog.v1":
            raise ValueError("schema_version must equal 'pica-commutator-catalog.v1'")
        for name in ["commutator_catalog_id", "campaign_id", "run_id", "point_id"]:
            if not getattr(self, name):
                raise ValueError(f"{name} must be a non-empty string")
        if isinstance(self.row_count, bool) or self.row_count < 0:
            raise ValueError("row_count must be a non-negative integer")
        if self.row_count != len(self.rows):
            raise ValueError("row_count must equal len(rows)")
        duplicates = collect_list_duplicates([row.pair_id for row in self.rows])
        if duplicates:
            raise ValueError(f"rows must be unique by pair_id: {', '.join(duplicates)}")
        if any(not value for value in self.notes + self.flags):
            raise ValueError("notes and flags must contain only non-empty strings")
        return self


class PicaPackagingOperatorEntry(SixBirdsModel):
    packaging_operator_id: str
    packaging_family_id: str
    packaging_source: str
    producer_id: str
    operator_label: str
    family_label: str
    operator_kind: str
    parameter_digest: str | None = None
    support_metadata: dict[str, MetadataValue] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_entry(self) -> "PicaPackagingOperatorEntry":
        for name in [
            "packaging_operator_id",
            "packaging_family_id",
            "packaging_source",
            "producer_id",
            "operator_label",
            "family_label",
            "operator_kind",
        ]:
            if not getattr(self, name):
                raise ValueError(f"{name} must be a non-empty string")
        if self.parameter_digest is not None and not self.parameter_digest:
            raise ValueError("parameter_digest must be non-empty when present")
        ensure_metadata_shape(self.support_metadata)
        if any(not value for value in self.notes + self.flags):
            raise ValueError("notes and flags must contain only non-empty strings")
        return self


class PicaPackagingOperatorCatalog(SixBirdsModel):
    schema_version: str
    packaging_operator_catalog_id: str
    export_bundle_id: str
    campaign_id: str
    run_id: str
    point_id: str
    row_count: int
    rows: list[PicaPackagingOperatorEntry]
    notes: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_catalog(self) -> "PicaPackagingOperatorCatalog":
        if self.schema_version != "pica-packaging-operator-catalog.v1":
            raise ValueError(
                "schema_version must equal 'pica-packaging-operator-catalog.v1'"
            )
        for name in [
            "packaging_operator_catalog_id",
            "export_bundle_id",
            "campaign_id",
            "run_id",
            "point_id",
        ]:
            if not getattr(self, name):
                raise ValueError(f"{name} must be a non-empty string")
        if isinstance(self.row_count, bool) or self.row_count < 0:
            raise ValueError("row_count must be a non-negative integer")
        if self.row_count != len(self.rows):
            raise ValueError("row_count must equal len(rows)")
        duplicates = collect_list_duplicates(
            [row.packaging_operator_id for row in self.rows]
        )
        if duplicates:
            raise ValueError(
                f"rows must be unique by packaging_operator_id: {', '.join(duplicates)}"
            )
        if any(not value for value in self.notes + self.flags):
            raise ValueError("notes and flags must contain only non-empty strings")
        return self


class PicaPackagingSelectionRow(SixBirdsModel):
    selection_row_id: str
    run_id: str
    point_id: str
    preparation_id: str
    protocol_id: str
    protocol_step_id: str
    step_index: int
    trajectory_id: str | None = None
    support_group_id: str | None = None
    level_id: str
    resolution_id: str
    closure_id: str
    lens_id: str | None = None
    packaging_operator_id: str
    packaging_family_id: str
    packaging_source: str
    selection_status: PicaPackagingSelectionStatus
    candidate_operator_ids: list[str] = Field(default_factory=list)
    support_scope_metadata: dict[str, MetadataValue] = Field(default_factory=dict)
    candidate_set_metadata: dict[str, MetadataValue] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_row(self) -> "PicaPackagingSelectionRow":
        for name in [
            "selection_row_id",
            "run_id",
            "point_id",
            "preparation_id",
            "protocol_id",
            "protocol_step_id",
            "level_id",
            "resolution_id",
            "closure_id",
            "packaging_operator_id",
            "packaging_family_id",
            "packaging_source",
        ]:
            if not getattr(self, name):
                raise ValueError(f"{name} must be a non-empty string")
        if self.lens_id is not None and not self.lens_id:
            raise ValueError("lens_id must be non-empty when present")
        if self.trajectory_id is None and self.support_group_id is None:
            raise ValueError(
                "at least one of trajectory_id or support_group_id must be present"
            )
        if self.trajectory_id is not None and not self.trajectory_id:
            raise ValueError("trajectory_id must be non-empty when present")
        if self.support_group_id is not None and not self.support_group_id:
            raise ValueError("support_group_id must be non-empty when present")
        if isinstance(self.step_index, bool) or self.step_index < 0:
            raise ValueError("step_index must be a non-negative integer")
        duplicates = collect_list_duplicates(self.candidate_operator_ids)
        if duplicates:
            raise ValueError(
                f"candidate_operator_ids must be unique: {', '.join(duplicates)}"
            )
        if any(not value for value in self.candidate_operator_ids):
            raise ValueError(
                "candidate_operator_ids must contain only non-empty strings"
            )
        ensure_metadata_shape(self.support_scope_metadata)
        ensure_metadata_shape(self.candidate_set_metadata)
        if any(not value for value in self.notes + self.flags):
            raise ValueError("notes and flags must contain only non-empty strings")
        return self


class PicaPackagingSelectionLedger(SixBirdsModel):
    schema_version: str
    packaging_selection_ledger_id: str
    export_bundle_id: str
    campaign_id: str
    run_id: str
    point_id: str
    row_count: int
    rows: list[PicaPackagingSelectionRow]
    notes: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_ledger(self) -> "PicaPackagingSelectionLedger":
        if self.schema_version != "pica-packaging-selection-ledger.v1":
            raise ValueError(
                "schema_version must equal 'pica-packaging-selection-ledger.v1'"
            )
        for name in [
            "packaging_selection_ledger_id",
            "export_bundle_id",
            "campaign_id",
            "run_id",
            "point_id",
        ]:
            if not getattr(self, name):
                raise ValueError(f"{name} must be a non-empty string")
        if isinstance(self.row_count, bool) or self.row_count < 0:
            raise ValueError("row_count must be a non-negative integer")
        if self.row_count != len(self.rows):
            raise ValueError("row_count must equal len(rows)")
        duplicates = collect_list_duplicates(
            [row.selection_row_id for row in self.rows]
        )
        if duplicates:
            raise ValueError(
                f"rows must be unique by selection_row_id: {', '.join(duplicates)}"
            )
        if any(not value for value in self.notes + self.flags):
            raise ValueError("notes and flags must contain only non-empty strings")
        return self


class PicaPackagingSurface(SixBirdsModel):
    schema_version: str
    bundle_artifact: str
    export_bundle_id: str
    packaging_operator_catalog_artifacts: list[str]
    packaging_selection_ledger_artifacts: list[str]
    distinct_packaging_operator_count: int
    distinct_packaging_family_count: int
    source_counts: dict[str, int]
    selected_operator_counts: dict[str, int]
    selected_family_counts: dict[str, int]
    support_slice_count: int
    notes: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)
    artifact_refs: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_surface(self) -> "PicaPackagingSurface":
        if self.schema_version != "pica-packaging-surface.v1":
            raise ValueError("schema_version must equal 'pica-packaging-surface.v1'")
        ensure_repo_relative_mapping(
            {"bundle_artifact": self.bundle_artifact},
            field_name="bundle_artifact",
        )
        for name in [
            "export_bundle_id",
        ]:
            if not getattr(self, name):
                raise ValueError(f"{name} must be a non-empty string")
        ensure_repo_relative_mapping(
            {
                f"packaging_operator_catalog_artifact_{index}": artifact
                for index, artifact in enumerate(
                    self.packaging_operator_catalog_artifacts
                )
            },
            field_name="packaging_operator_catalog_artifacts",
        )
        ensure_repo_relative_mapping(
            {
                f"packaging_selection_ledger_artifact_{index}": artifact
                for index, artifact in enumerate(
                    self.packaging_selection_ledger_artifacts
                )
            },
            field_name="packaging_selection_ledger_artifacts",
        )
        ensure_repo_relative_mapping(self.artifact_refs, field_name="artifact_refs")
        for name in [
            "distinct_packaging_operator_count",
            "distinct_packaging_family_count",
            "support_slice_count",
        ]:
            value = getattr(self, name)
            if isinstance(value, bool) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        for mapping_name in [
            "source_counts",
            "selected_operator_counts",
            "selected_family_counts",
        ]:
            mapping = getattr(self, mapping_name)
            for key, value in mapping.items():
                if not key:
                    raise ValueError(f"{mapping_name} keys must be non-empty strings")
                if isinstance(value, bool) or value < 0:
                    raise ValueError(
                        f"{mapping_name} values must be non-negative integers"
                    )
        if any(not value for value in self.notes + self.flags):
            raise ValueError("notes and flags must contain only non-empty strings")
        return self


class PicaPilotInvocation(SixBirdsModel):
    vendor_root: str
    manifest_path: str
    command_mode: PicaPilotCommandMode
    cargo_target_dir: str
    binary_name: str = "runner"

    @model_validator(mode="after")
    def validate_invocation(self) -> "PicaPilotInvocation":
        ensure_repo_relative_mapping(
            {
                "vendor_root": self.vendor_root,
                "manifest_path": self.manifest_path,
                "cargo_target_dir": self.cargo_target_dir,
            },
            field_name="invocation",
        )
        if not self.binary_name:
            raise ValueError("binary_name must be a non-empty string")
        return self


class PicaPilotRunSettings(SixBirdsModel):
    exp_id: str
    config_name: str
    seed: int
    scale: int
    timeout_seconds: int = 120

    @model_validator(mode="after")
    def validate_run_settings(self) -> "PicaPilotRunSettings":
        for name in ["exp_id", "config_name"]:
            if not getattr(self, name):
                raise ValueError(f"{name} must be a non-empty string")
        for name in ["seed", "scale", "timeout_seconds"]:
            value = getattr(self, name)
            if isinstance(value, bool):
                raise ValueError(f"{name} must be an integer")
        if self.scale <= 0:
            raise ValueError("scale must be a positive integer")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be a positive integer")
        return self


class PicaPilotExportSettings(SixBirdsModel):
    export_mode: PicaPilotExportMode
    pica_export_mode: PicaObservationExportMode = "aggregate_summary"
    artifact_output_mode: PicaPilotArtifactOutputMode
    path_policy: PathPolicy = "repo_relative"
    adapter_mode: str | None = None

    @model_validator(mode="after")
    def validate_export_settings(self) -> "PicaPilotExportSettings":
        if self.adapter_mode is not None and not self.adapter_mode:
            raise ValueError("adapter_mode must be non-empty when present")
        return self


class PicaPilotCampaign(SixBirdsModel):
    schema_version: str
    pilot_campaign_id: str
    pilot_label: str
    source_config_path: str
    invocation: PicaPilotInvocation
    run_settings: PicaPilotRunSettings
    export_settings: PicaPilotExportSettings
    campaign_id: str
    campaign_label: str
    point_id: str
    substrate_config_id: str
    mechanism_family_id: str
    enable_matrix_id: str | None = None
    preparation_id: str
    protocol_id: str
    notes: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_campaign(self) -> "PicaPilotCampaign":
        if self.schema_version != "pica-pilot-campaign.v1":
            raise ValueError("schema_version must equal 'pica-pilot-campaign.v1'")
        for name in [
            "pilot_campaign_id",
            "pilot_label",
            "campaign_id",
            "campaign_label",
            "point_id",
            "substrate_config_id",
            "mechanism_family_id",
            "preparation_id",
            "protocol_id",
        ]:
            if not getattr(self, name):
                raise ValueError(f"{name} must be a non-empty string")
        ensure_repo_relative_mapping(
            {"source_config_path": self.source_config_path},
            field_name="source_config_path",
        )
        if self.enable_matrix_id is not None and not self.enable_matrix_id:
            raise ValueError("enable_matrix_id must be non-empty when present")
        if any(not value for value in self.notes + self.flags):
            raise ValueError("notes and flags must contain only non-empty strings")
        return self


class PicaPilotArtifactPaths(SixBirdsModel):
    export_bundle: str
    campaign_export: str
    run_ledger: str
    closure_catalog: str
    observable_ledger: str
    commutator_catalog: str | None = None
    packaging_operator_catalog: str | None = None
    packaging_selection_ledger: str | None = None
    stdout: str | None = None
    stderr: str | None = None

    @model_validator(mode="after")
    def validate_artifacts(self) -> "PicaPilotArtifactPaths":
        ensure_repo_relative_mapping(
            {
                "export_bundle": self.export_bundle,
                "campaign_export": self.campaign_export,
                "run_ledger": self.run_ledger,
                "closure_catalog": self.closure_catalog,
                "observable_ledger": self.observable_ledger,
            },
            field_name="stable_artifacts",
        )
        for name in ["stdout", "stderr"]:
            value = getattr(self, name)
            if value is not None:
                ensure_repo_relative_mapping({name: value}, field_name=name)
        if self.commutator_catalog is not None:
            ensure_repo_relative_mapping(
                {"commutator_catalog": self.commutator_catalog},
                field_name="commutator_catalog",
            )
        for name in [
            "packaging_operator_catalog",
            "packaging_selection_ledger",
        ]:
            value = getattr(self, name)
            if value is not None:
                ensure_repo_relative_mapping({name: value}, field_name=name)
        return self


class PicaPilotSummaryCounts(SixBirdsModel):
    campaign_count: int
    run_count: int
    closure_count: int
    lens_count: int
    observable_ledger_count: int
    commutator_catalog_count: int = 0
    packaging_operator_catalog_count: int = 0
    packaging_selection_ledger_count: int = 0

    @model_validator(mode="after")
    def validate_counts(self) -> "PicaPilotSummaryCounts":
        for name in [
            "campaign_count",
            "run_count",
            "closure_count",
            "lens_count",
            "observable_ledger_count",
            "commutator_catalog_count",
            "packaging_operator_catalog_count",
            "packaging_selection_ledger_count",
        ]:
            value = getattr(self, name)
            if isinstance(value, bool) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        return self


class PicaPilotResult(SixBirdsModel):
    schema_version: str
    pilot_run_id: str
    pilot_config_path: str
    vendor_root_path: str
    wrapper_command: list[str]
    command_mode: PicaPilotCommandMode
    export_mode: PicaPilotExportMode
    pica_export_mode: PicaObservationExportMode
    adapter_mode: str | None = None
    observation_granularity: PicaObservationGranularity
    cooccurrence_scope: PicaCooccurrenceScope
    supports_structural_probe_conditioning: bool
    return_code: int
    success: bool
    bridge_validation_status: BridgeValidationStatus
    stable_artifacts: PicaPilotArtifactPaths
    summary_counts: PicaPilotSummaryCounts
    notes: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_result(self) -> "PicaPilotResult":
        if self.schema_version != "pica-pilot-result.v1":
            raise ValueError("schema_version must equal 'pica-pilot-result.v1'")
        for name in [
            "pilot_run_id",
            "command_mode",
            "export_mode",
            "pica_export_mode",
        ]:
            if not getattr(self, name):
                raise ValueError(f"{name} must be a non-empty string")
        ensure_repo_relative_mapping(
            {
                "pilot_config_path": self.pilot_config_path,
                "vendor_root_path": self.vendor_root_path,
            },
            field_name="result_paths",
        )
        if not self.wrapper_command or any(not part for part in self.wrapper_command):
            raise ValueError("wrapper_command must be a non-empty list of strings")
        if isinstance(self.return_code, bool):
            raise ValueError("return_code must be an integer")
        if self.adapter_mode is not None and not self.adapter_mode:
            raise ValueError("adapter_mode must be non-empty when present")
        if self.supports_structural_probe_conditioning:
            if self.observation_granularity != "per_trajectory":
                raise ValueError(
                    "supports_structural_probe_conditioning requires observation_granularity='per_trajectory'"
                )
            if self.cooccurrence_scope != "within_run_and_trajectory":
                raise ValueError(
                    "supports_structural_probe_conditioning requires cooccurrence_scope='within_run_and_trajectory'"
                )
        if any(not value for value in self.notes + self.flags):
            raise ValueError("notes and flags must contain only non-empty strings")
        return self


class PicaDiscoveryReadinessSummary(SixBirdsModel):
    schema_version: str
    bundle_artifact: str
    export_bundle_id: str
    pica_export_mode: PicaObservationExportMode
    observation_granularity: PicaObservationGranularity
    cooccurrence_scope: PicaCooccurrenceScope
    run_count: int
    trajectory_count: int
    closure_count: int
    lens_count: int
    step_count: int
    context_key_count: int
    context_pair_count: int
    context_pairs_with_shared_trajectory_support: int
    context_pairs_with_probe_conditioning_potential: int
    supports_structural_probe_conditioning: bool
    readiness_classification: PicaDiscoveryReadinessClassification
    notes: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)
    artifact_refs: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_summary(self) -> "PicaDiscoveryReadinessSummary":
        if self.schema_version != "pica-discovery-readiness.v1":
            raise ValueError("schema_version must equal 'pica-discovery-readiness.v1'")
        for name in ["bundle_artifact", "export_bundle_id"]:
            if not getattr(self, name):
                raise ValueError(f"{name} must be a non-empty string")
        ensure_repo_relative_mapping(
            {"bundle_artifact": self.bundle_artifact},
            field_name="bundle_artifact",
        )
        ensure_repo_relative_mapping(self.artifact_refs, field_name="artifact_refs")
        for name in [
            "run_count",
            "trajectory_count",
            "closure_count",
            "lens_count",
            "step_count",
            "context_key_count",
            "context_pair_count",
            "context_pairs_with_shared_trajectory_support",
            "context_pairs_with_probe_conditioning_potential",
        ]:
            value = getattr(self, name)
            if isinstance(value, bool) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if self.supports_structural_probe_conditioning:
            if self.observation_granularity != "per_trajectory":
                raise ValueError(
                    "supports_structural_probe_conditioning requires observation_granularity='per_trajectory'"
                )
            if self.cooccurrence_scope != "within_run_and_trajectory":
                raise ValueError(
                    "supports_structural_probe_conditioning requires cooccurrence_scope='within_run_and_trajectory'"
                )
        if any(not value for value in self.notes + self.flags):
            raise ValueError("notes and flags must contain only non-empty strings")
        return self
