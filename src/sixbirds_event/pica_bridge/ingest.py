from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..run_registry import get_repo_root, repo_relative_path
from ..validation import load_model
from .models import (
    PicaCampaignExport,
    PicaClosureCatalog,
    PicaCommutatorCatalog,
    PicaExportBundle,
    PicaObservableLedger,
    PicaObservableRow,
    PicaPackagingOperatorCatalog,
    PicaPackagingSelectionLedger,
    PicaRunLedger,
)


@dataclass(slots=True)
class PicaBundleResolved:
    repo_root: Path
    bundle_path: Path
    export_bundle: PicaExportBundle
    campaigns: dict[str, PicaCampaignExport]
    points: dict[str, object]
    runs: dict[str, PicaRunLedger]
    closure_catalogs: dict[str, PicaClosureCatalog]
    observable_ledgers: dict[str, PicaObservableLedger]
    commutator_catalogs: dict[str, PicaCommutatorCatalog]
    packaging_operator_catalogs: dict[str, PicaPackagingOperatorCatalog]
    packaging_selection_ledgers: dict[str, PicaPackagingSelectionLedger]

    def rows_for_run(self, run_id: str) -> list[PicaObservableRow]:
        ledger = self.observable_ledgers_by_run().get(run_id)
        if ledger is None:
            raise KeyError(f"unknown run_id '{run_id}'")
        return list(ledger.rows)

    def observable_ledgers_by_run(self) -> dict[str, PicaObservableLedger]:
        return {ledger.run_id: ledger for ledger in self.observable_ledgers.values()}

    def commutator_catalogs_by_run(self) -> dict[str, PicaCommutatorCatalog]:
        return {
            catalog.run_id: catalog for catalog in self.commutator_catalogs.values()
        }

    def packaging_operator_catalogs_by_run(
        self,
    ) -> dict[str, PicaPackagingOperatorCatalog]:
        return {
            catalog.run_id: catalog
            for catalog in self.packaging_operator_catalogs.values()
        }

    def packaging_selection_ledgers_by_run(
        self,
    ) -> dict[str, PicaPackagingSelectionLedger]:
        return {
            ledger.run_id: ledger
            for ledger in self.packaging_selection_ledgers.values()
        }

    def protocol_steps_for_run(self, run_id: str) -> dict[str, int]:
        run = self.runs[run_id]
        return {step.protocol_step_id: step.step_index for step in run.protocol_steps}

    def filter_rows(
        self,
        *,
        run_id: str | None = None,
        preparation_id: str | None = None,
        protocol_id: str | None = None,
        closure_id: str | None = None,
        lens_id: str | None = None,
        level_id: str | None = None,
        resolution_id: str | None = None,
        protocol_step_id: str | None = None,
        step_index: int | None = None,
        observation_label: str | None = None,
        route_label: str | None = None,
    ) -> list[PicaObservableRow]:
        ledgers = (
            [self.observable_ledgers_by_run()[run_id]]
            if run_id is not None
            else list(self.observable_ledgers.values())
        )
        rows: list[PicaObservableRow] = []
        for ledger in ledgers:
            for row in ledger.rows:
                if preparation_id is not None and row.preparation_id != preparation_id:
                    continue
                if protocol_id is not None and row.protocol_id != protocol_id:
                    continue
                if closure_id is not None and row.closure_id != closure_id:
                    continue
                if lens_id is not None and row.lens_id != lens_id:
                    continue
                if level_id is not None and row.level_id != level_id:
                    continue
                if resolution_id is not None and row.resolution_id != resolution_id:
                    continue
                if (
                    protocol_step_id is not None
                    and row.protocol_step_id != protocol_step_id
                ):
                    continue
                if step_index is not None and row.step_index != step_index:
                    continue
                if (
                    observation_label is not None
                    and row.observation_label != observation_label
                ):
                    continue
                if route_label is not None and row.route_label != route_label:
                    continue
                rows.append(row)
        return rows

    def to_source_index_payload(self) -> dict[str, object]:
        return {
            "export_bundle_id": self.export_bundle.export_bundle_id,
            "campaign_ids": sorted(self.campaigns),
            "point_ids": sorted(self.points),
            "run_ids": sorted(self.runs),
            "closure_catalog_ids": sorted(self.closure_catalogs),
            "observable_ledger_ids": sorted(self.observable_ledgers),
            "commutator_catalog_ids": sorted(self.commutator_catalogs),
            "packaging_operator_catalog_ids": sorted(self.packaging_operator_catalogs),
            "packaging_selection_ledger_ids": sorted(self.packaging_selection_ledgers),
            "level_ids": sorted(
                {
                    level.level_id
                    for catalog in self.closure_catalogs.values()
                    for level in catalog.levels
                }
            ),
            "resolution_ids": sorted(
                {
                    resolution.resolution_id
                    for catalog in self.closure_catalogs.values()
                    for resolution in catalog.resolutions
                }
            ),
            "closure_ids": sorted(
                {
                    closure.closure_id
                    for catalog in self.closure_catalogs.values()
                    for closure in catalog.closures
                }
            ),
            "lens_ids": sorted(
                {
                    lens.lens_id
                    for catalog in self.closure_catalogs.values()
                    for lens in catalog.lenses
                }
            ),
            "preparation_ids": sorted(
                {run.preparation_id for run in self.runs.values()}
            ),
            "protocol_ids": sorted({run.protocol_id for run in self.runs.values()}),
            "protocol_step_ids": sorted(
                {
                    step.protocol_step_id
                    for run in self.runs.values()
                    for step in run.protocol_steps
                }
            ),
            "step_indices": sorted(
                {
                    step.step_index
                    for run in self.runs.values()
                    for step in run.protocol_steps
                }
            ),
            "packaging_sources": sorted(
                {
                    row.packaging_source
                    for ledger in self.packaging_selection_ledgers.values()
                    for row in ledger.rows
                }
            ),
            "packaging_operator_ids": sorted(
                {
                    row.packaging_operator_id
                    for catalog in self.packaging_operator_catalogs.values()
                    for row in catalog.rows
                }
            ),
            "packaging_family_ids": sorted(
                {
                    row.packaging_family_id
                    for catalog in self.packaging_operator_catalogs.values()
                    for row in catalog.rows
                }
            ),
        }


def _resolve_artifact_path(
    artifact_path: str,
    *,
    bundle_path: Path,
    repo_root: Path,
) -> Path:
    candidate_repo = repo_root / artifact_path
    if candidate_repo.exists():
        return candidate_repo
    candidate_cwd = Path.cwd() / artifact_path
    if candidate_cwd.exists():
        return candidate_cwd
    candidate_bundle = bundle_path.parent / artifact_path
    if candidate_bundle.exists():
        return candidate_bundle
    raise FileNotFoundError(f"referenced artifact not found: {artifact_path}")


def load_pica_export_bundle(
    path: str | Path, *, repo_root: str | Path | None = None
) -> PicaBundleResolved:
    repo_root_path = get_repo_root(repo_root)
    bundle_path = Path(path)
    if not bundle_path.is_absolute():
        repo_candidate = repo_root_path / bundle_path
        cwd_candidate = Path.cwd() / bundle_path
        if repo_candidate.exists():
            bundle_path = repo_candidate
        elif cwd_candidate.exists():
            bundle_path = cwd_candidate
        else:
            bundle_path = repo_candidate
    bundle_path = bundle_path.resolve()
    bundle = load_model(bundle_path, kind="pica-export-bundle")
    assert isinstance(bundle, PicaExportBundle)

    campaigns: dict[str, PicaCampaignExport] = {}
    runs: dict[str, PicaRunLedger] = {}
    closure_catalogs: dict[str, PicaClosureCatalog] = {}
    observable_ledgers: dict[str, PicaObservableLedger] = {}
    commutator_catalogs: dict[str, PicaCommutatorCatalog] = {}
    packaging_operator_catalogs: dict[str, PicaPackagingOperatorCatalog] = {}
    packaging_selection_ledgers: dict[str, PicaPackagingSelectionLedger] = {}
    points: dict[str, object] = {}

    for ref in bundle.campaign_exports:
        artifact_path = _resolve_artifact_path(
            ref.artifact_path,
            bundle_path=bundle_path,
            repo_root=repo_root_path,
        )
        model = load_model(artifact_path, kind="pica-campaign-export")
        assert isinstance(model, PicaCampaignExport)
        if model.campaign_id != ref.campaign_id:
            raise ValueError(
                f"campaign_id mismatch for {ref.artifact_path}: expected '{ref.campaign_id}', got '{model.campaign_id}'"
            )
        campaigns[model.campaign_id] = model
        for point in model.point_inventory:
            if point.point_id in points:
                raise ValueError(
                    f"duplicate point_id '{point.point_id}' across campaigns"
                )
            points[point.point_id] = point

    for ref in bundle.run_ledgers:
        artifact_path = _resolve_artifact_path(
            ref.artifact_path,
            bundle_path=bundle_path,
            repo_root=repo_root_path,
        )
        model = load_model(artifact_path, kind="pica-run-ledger")
        assert isinstance(model, PicaRunLedger)
        if model.run_id != ref.run_id:
            raise ValueError(
                f"run_id mismatch for {ref.artifact_path}: expected '{ref.run_id}', got '{model.run_id}'"
            )
        if model.campaign_id != ref.campaign_id:
            raise ValueError(
                f"campaign_id mismatch for run '{model.run_id}': expected '{ref.campaign_id}', got '{model.campaign_id}'"
            )
        runs[model.run_id] = model

    for ref in bundle.closure_catalogs:
        artifact_path = _resolve_artifact_path(
            ref.artifact_path,
            bundle_path=bundle_path,
            repo_root=repo_root_path,
        )
        model = load_model(artifact_path, kind="pica-closure-catalog")
        assert isinstance(model, PicaClosureCatalog)
        if model.closure_catalog_id != ref.closure_catalog_id:
            raise ValueError(
                f"closure_catalog_id mismatch for {ref.artifact_path}: expected '{ref.closure_catalog_id}', got '{model.closure_catalog_id}'"
            )
        if model.run_id != ref.run_id:
            raise ValueError(
                f"run_id mismatch for closure catalog '{model.closure_catalog_id}': expected '{ref.run_id}', got '{model.run_id}'"
            )
        closure_catalogs[model.closure_catalog_id] = model

    for ref in bundle.observable_ledgers:
        artifact_path = _resolve_artifact_path(
            ref.artifact_path,
            bundle_path=bundle_path,
            repo_root=repo_root_path,
        )
        model = load_model(artifact_path, kind="pica-observable-ledger")
        assert isinstance(model, PicaObservableLedger)
        if model.observable_ledger_id != ref.observable_ledger_id:
            raise ValueError(
                f"observable_ledger_id mismatch for {ref.artifact_path}: expected '{ref.observable_ledger_id}', got '{model.observable_ledger_id}'"
            )
        if model.run_id != ref.run_id:
            raise ValueError(
                f"run_id mismatch for observable ledger '{model.observable_ledger_id}': expected '{ref.run_id}', got '{model.run_id}'"
            )
        observable_ledgers[model.observable_ledger_id] = model

    for ref in bundle.commutator_catalogs:
        artifact_path = _resolve_artifact_path(
            ref.artifact_path,
            bundle_path=bundle_path,
            repo_root=repo_root_path,
        )
        model = load_model(artifact_path, kind="pica-commutator-catalog")
        assert isinstance(model, PicaCommutatorCatalog)
        if model.commutator_catalog_id != ref.commutator_catalog_id:
            raise ValueError(
                f"commutator_catalog_id mismatch for {ref.artifact_path}: expected '{ref.commutator_catalog_id}', got '{model.commutator_catalog_id}'"
            )
        if model.run_id != ref.run_id:
            raise ValueError(
                f"run_id mismatch for commutator catalog '{model.commutator_catalog_id}': expected '{ref.run_id}', got '{model.run_id}'"
            )
        commutator_catalogs[model.commutator_catalog_id] = model

    for ref in bundle.packaging_operator_catalogs:
        artifact_path = _resolve_artifact_path(
            ref.artifact_path,
            bundle_path=bundle_path,
            repo_root=repo_root_path,
        )
        model = load_model(artifact_path, kind="pica-packaging-operator-catalog")
        assert isinstance(model, PicaPackagingOperatorCatalog)
        if model.packaging_operator_catalog_id != ref.packaging_operator_catalog_id:
            raise ValueError(
                f"packaging_operator_catalog_id mismatch for {ref.artifact_path}: expected '{ref.packaging_operator_catalog_id}', got '{model.packaging_operator_catalog_id}'"
            )
        if model.run_id != ref.run_id:
            raise ValueError(
                f"run_id mismatch for packaging operator catalog '{model.packaging_operator_catalog_id}': expected '{ref.run_id}', got '{model.run_id}'"
            )
        packaging_operator_catalogs[model.packaging_operator_catalog_id] = model

    for ref in bundle.packaging_selection_ledgers:
        artifact_path = _resolve_artifact_path(
            ref.artifact_path,
            bundle_path=bundle_path,
            repo_root=repo_root_path,
        )
        model = load_model(artifact_path, kind="pica-packaging-selection-ledger")
        assert isinstance(model, PicaPackagingSelectionLedger)
        if model.packaging_selection_ledger_id != ref.packaging_selection_ledger_id:
            raise ValueError(
                f"packaging_selection_ledger_id mismatch for {ref.artifact_path}: expected '{ref.packaging_selection_ledger_id}', got '{model.packaging_selection_ledger_id}'"
            )
        if model.run_id != ref.run_id:
            raise ValueError(
                f"run_id mismatch for packaging selection ledger '{model.packaging_selection_ledger_id}': expected '{ref.run_id}', got '{model.run_id}'"
            )
        packaging_selection_ledgers[model.packaging_selection_ledger_id] = model

    for campaign in campaigns.values():
        for run_inventory in campaign.run_inventory:
            if run_inventory.run_id not in runs:
                raise ValueError(
                    f"campaign '{campaign.campaign_id}' references unknown run_id '{run_inventory.run_id}'"
                )

    for run in runs.values():
        if run.campaign_id not in campaigns:
            raise ValueError(
                f"run '{run.run_id}' references unknown campaign_id '{run.campaign_id}'"
            )
        if run.point_id not in points:
            raise ValueError(
                f"run '{run.run_id}' references unknown point_id '{run.point_id}'"
            )
        if run.closure_catalog_id not in closure_catalogs:
            raise ValueError(
                f"run '{run.run_id}' references unknown closure_catalog_id '{run.closure_catalog_id}'"
            )
        if run.observable_ledger_id not in observable_ledgers:
            raise ValueError(
                f"run '{run.run_id}' references unknown observable_ledger_id '{run.observable_ledger_id}'"
            )
        if (
            run.commutator_catalog_id is not None
            and run.commutator_catalog_id not in commutator_catalogs
        ):
            raise ValueError(
                f"run '{run.run_id}' references unknown commutator_catalog_id '{run.commutator_catalog_id}'"
            )
        if (
            run.packaging_operator_catalog_id is not None
            and run.packaging_operator_catalog_id not in packaging_operator_catalogs
        ):
            raise ValueError(
                f"run '{run.run_id}' references unknown packaging_operator_catalog_id '{run.packaging_operator_catalog_id}'"
            )
        if (
            run.packaging_selection_ledger_id is not None
            and run.packaging_selection_ledger_id not in packaging_selection_ledgers
        ):
            raise ValueError(
                f"run '{run.run_id}' references unknown packaging_selection_ledger_id '{run.packaging_selection_ledger_id}'"
            )

    return PicaBundleResolved(
        repo_root=repo_root_path,
        bundle_path=bundle_path,
        export_bundle=bundle,
        campaigns=campaigns,
        points=points,
        runs=runs,
        closure_catalogs=closure_catalogs,
        observable_ledgers=observable_ledgers,
        commutator_catalogs=commutator_catalogs,
        packaging_operator_catalogs=packaging_operator_catalogs,
        packaging_selection_ledgers=packaging_selection_ledgers,
    )


def repo_relative_bundle_path(
    path: str | Path, *, repo_root: str | Path | None = None
) -> str:
    return repo_relative_path(path, root=get_repo_root(repo_root))
