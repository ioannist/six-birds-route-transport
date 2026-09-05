from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..run_registry import repo_relative_path
from .ingest import PicaBundleResolved, load_pica_export_bundle
from .models import PicaPackagingSelectionRow, PicaPackagingSurface


@dataclass(slots=True)
class ResolvedPackagingSurface:
    surface: PicaPackagingSurface
    source_index: dict[str, object]


def _support_slice_key(row: PicaPackagingSelectionRow) -> str:
    if row.support_group_id is not None:
        return row.support_group_id
    return ":".join(
        [
            row.run_id,
            row.preparation_id,
            row.protocol_id,
            row.protocol_step_id,
            str(row.step_index),
            row.closure_id,
            row.lens_id or "no_lens",
            row.trajectory_id or "no_trajectory",
        ]
    )


def _build_packaging_source_index(
    *,
    resolved: PicaBundleResolved,
) -> dict[str, object]:
    catalogs = list(resolved.packaging_operator_catalogs.values())
    ledgers = list(resolved.packaging_selection_ledgers.values())
    source_counts: dict[str, int] = {}
    selected_operator_counts: dict[str, int] = {}
    selected_family_counts: dict[str, int] = {}
    by_source: dict[str, list[str]] = {}
    by_operator: dict[str, list[str]] = {}
    by_family: dict[str, list[str]] = {}
    support_slice_ids: set[str] = set()

    for ledger in ledgers:
        for row in ledger.rows:
            support_slice_ids.add(_support_slice_key(row))
            source_counts[row.packaging_source] = (
                source_counts.get(row.packaging_source, 0) + 1
            )
            by_source.setdefault(row.packaging_source, []).append(row.selection_row_id)
            if row.selection_status == "selected":
                selected_operator_counts[row.packaging_operator_id] = (
                    selected_operator_counts.get(row.packaging_operator_id, 0) + 1
                )
                selected_family_counts[row.packaging_family_id] = (
                    selected_family_counts.get(row.packaging_family_id, 0) + 1
                )
            by_operator.setdefault(row.packaging_operator_id, []).append(
                row.selection_row_id
            )
            by_family.setdefault(row.packaging_family_id, []).append(
                row.selection_row_id
            )

    return {
        "export_bundle_id": resolved.export_bundle.export_bundle_id,
        "packaging_operator_catalog_ids": sorted(resolved.packaging_operator_catalogs),
        "packaging_selection_ledger_ids": sorted(resolved.packaging_selection_ledgers),
        "distinct_packaging_operator_ids": sorted(
            {row.packaging_operator_id for catalog in catalogs for row in catalog.rows}
        ),
        "distinct_packaging_family_ids": sorted(
            {row.packaging_family_id for catalog in catalogs for row in catalog.rows}
        ),
        "packaging_sources": sorted(source_counts),
        "source_counts": source_counts,
        "selected_operator_counts": selected_operator_counts,
        "selected_family_counts": selected_family_counts,
        "support_slice_ids": sorted(support_slice_ids),
        "rows_by_source": {
            key: sorted(values) for key, values in sorted(by_source.items())
        },
        "rows_by_operator": {
            key: sorted(values) for key, values in sorted(by_operator.items())
        },
        "rows_by_family": {
            key: sorted(values) for key, values in sorted(by_family.items())
        },
    }


def resolve_pica_packaging_surface(
    path: str | Path,
    *,
    repo_root: str | Path | None = None,
) -> ResolvedPackagingSurface:
    resolved = load_pica_export_bundle(path, repo_root=repo_root)
    source_index = _build_packaging_source_index(resolved=resolved)
    artifact_refs = {
        "bundle": repo_relative_path(resolved.bundle_path, root=resolved.repo_root),
    }
    if resolved.export_bundle.packaging_operator_catalogs:
        artifact_refs["packaging_operator_catalog"] = (
            resolved.export_bundle.packaging_operator_catalogs[0].artifact_path
        )
    if resolved.export_bundle.packaging_selection_ledgers:
        artifact_refs["packaging_selection_ledger"] = (
            resolved.export_bundle.packaging_selection_ledgers[0].artifact_path
        )
    surface = PicaPackagingSurface(
        schema_version="pica-packaging-surface.v1",
        bundle_artifact=repo_relative_path(
            resolved.bundle_path, root=resolved.repo_root
        ),
        export_bundle_id=resolved.export_bundle.export_bundle_id,
        packaging_operator_catalog_artifacts=[
            ref.artifact_path
            for ref in resolved.export_bundle.packaging_operator_catalogs
        ],
        packaging_selection_ledger_artifacts=[
            ref.artifact_path
            for ref in resolved.export_bundle.packaging_selection_ledgers
        ],
        distinct_packaging_operator_count=len(
            source_index["distinct_packaging_operator_ids"]
        ),
        distinct_packaging_family_count=len(
            source_index["distinct_packaging_family_ids"]
        ),
        source_counts=source_index["source_counts"],
        selected_operator_counts=source_index["selected_operator_counts"],
        selected_family_counts=source_index["selected_family_counts"],
        support_slice_count=len(source_index["support_slice_ids"]),
        notes=[
            "Packaging surface summary resolved from the bridge-level operator catalog and selection ledger."
        ],
        flags=["observable_first", "packaging_axis_surface"],
        artifact_refs=artifact_refs,
    )
    return ResolvedPackagingSurface(surface=surface, source_index=source_index)
