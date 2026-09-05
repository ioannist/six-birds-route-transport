from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

from ..pica_bridge.ingest import load_pica_export_bundle
from ..run_registry import (
    build_run_manifest,
    create_run_directory,
    detect_git_commit,
    get_repo_root,
    repo_relative_path,
    write_run_manifest,
)
from ..schemas.result_note import ResultNote
from ..validation import load_model
from .models import (
    PicaCampaignExport,
    PicaCampaignExportRef,
    PicaCampaignPoint,
    PicaCampaignRunInventory,
    PicaClosureCatalog,
    PicaClosureCatalogRef,
    PicaClosureRecord,
    PicaCommutatorCatalog,
    PicaCommutatorCatalogRef,
    PicaCommutatorEntry,
    PicaExportBundle,
    PicaLevelRecord,
    PicaLensRecord,
    PicaObservableLedger,
    PicaObservableLedgerRef,
    PicaObservableRow,
    PicaPackagingOperatorCatalog,
    PicaPackagingOperatorCatalogRef,
    PicaPackagingOperatorEntry,
    PicaPackagingSelectionLedger,
    PicaPackagingSelectionLedgerRef,
    PicaPackagingSelectionRow,
    PicaPilotArtifactPaths,
    PicaPilotCampaign,
    PicaPilotResult,
    PicaPilotSummaryCounts,
    PicaProducerMetadata,
    PicaProtocolStep,
    PicaResolutionRecord,
    PicaRunLedger,
    PicaRunLedgerRef,
)


_KEY_LENS_PATTERN = re.compile(r"\bsource=([^\s]+)")
_KEY_LEVEL_PATTERN = re.compile(r"\blevel=([^\s]+)")


@dataclass(slots=True)
class PicaPilotArtifacts:
    run_id: str
    run_dir: str
    summary_path: str
    note_path: str
    result_note_path: str
    manifest_path: str
    export_bundle_path: str
    campaign_export_path: str
    run_ledger_path: str
    closure_catalog_path: str
    observable_ledger_path: str
    commutator_catalog_path: str | None
    packaging_operator_catalog_path: str | None
    packaging_selection_ledger_path: str | None
    stdout_path: str
    stderr_path: str
    result: PicaPilotResult


def _sanitize_token(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


def _extract_audit_json(stdout: str) -> dict[str, object]:
    for line in stdout.splitlines():
        if line.startswith("KEY_AUDIT_JSON "):
            return json.loads(line.split(" ", 1)[1])
    raise ValueError("PICA stdout did not contain a KEY_AUDIT_JSON line")


def _extract_lens_source(stdout: str) -> str:
    for line in stdout.splitlines():
        if line.startswith("KEY_100_LENS "):
            match = _KEY_LENS_PATTERN.search(line)
            if match is not None:
                return match.group(1)
    return "unknown"


def _extract_discovery_grade_json(stdout: str) -> dict[str, object]:
    for line in stdout.splitlines():
        if line.startswith("KEY_DISCOVERY_GRADE_JSON "):
            return json.loads(line.split(" ", 1)[1])
    raise ValueError("PICA stdout did not contain a KEY_DISCOVERY_GRADE_JSON line")


def _extract_commutator_catalog_json(stdout: str) -> dict[str, object]:
    for line in stdout.splitlines():
        if line.startswith("KEY_PICA_COMMUTATOR_CATALOG_JSON "):
            return json.loads(line.split(" ", 1)[1])
    return {"rows": []}


def _extract_macro_level(stdout: str) -> str:
    for line in stdout.splitlines():
        if line.startswith("KEY_100_MACRO "):
            match = _KEY_LEVEL_PATTERN.search(line)
            if match is not None:
                return match.group(1)
    return "L0"


def _scalar_payload(scan_row: dict[str, object]) -> dict[str, str | int | float | bool]:
    payload: dict[str, str | int | float | bool] = {}
    for key, value in scan_row.items():
        if value is None:
            continue
        if isinstance(value, bool):
            payload[key] = value
        elif isinstance(value, (str, int, float)):
            payload[key] = value
        else:
            payload[f"{key}_json"] = json.dumps(value, sort_keys=True)
    return payload


def _scalar_metadata(
    payload: dict[str, object],
) -> dict[str, str | int | float | bool]:
    metadata: dict[str, str | int | float | bool] = {}
    for key, value in payload.items():
        if value is None:
            continue
        if isinstance(value, bool):
            metadata[key] = value
        elif isinstance(value, (str, int, float)):
            metadata[key] = value
    return metadata


def _normalize_packaging_source(value: object) -> tuple[str, str, str]:
    if not isinstance(value, str) or not value.strip():
        return ("packaging_source_unknown", "unknown", "packaging")
    source_token = _sanitize_token(value)
    if "_from_" in source_token:
        selector_prefix, producer_suffix = source_token.split("_from_", maxsplit=1)
        producer_id = producer_suffix or "unknown"
        selector_token = selector_prefix or "packaging"
        return source_token, producer_id, selector_token
    return source_token, source_token, "packaging"


def _packaging_operator_identity(
    *,
    packaging_source: str,
    selector_token: str,
) -> tuple[str, str, str, str, str]:
    operator_id = f"packaging_operator_{packaging_source}"
    family_id = f"packaging_family_{selector_token}"
    operator_label = packaging_source.replace("_", " ")
    family_label = selector_token.replace("_", " ")
    parameter_digest = hashlib.sha1(
        f"{family_id}:{operator_id}".encode("utf-8")
    ).hexdigest()[:12]
    return operator_id, family_id, operator_label, family_label, parameter_digest


def _enabled_packaging_operator_entries(
    audit: dict[str, object],
) -> list[tuple[str, str, str, str, str, str, str]]:
    config = audit.get("pica_config")
    if not isinstance(config, dict):
        return []
    enabled = config.get("enabled")
    if not isinstance(enabled, list) or len(enabled) <= 4:
        return []
    p5_row = enabled[4]
    if not isinstance(p5_row, list):
        return []
    producer_columns = {2: "p3", 3: "p4", 5: "p6"}
    entries: list[tuple[str, str, str, str, str, str, str]] = []
    for column_index, producer_id in producer_columns.items():
        if column_index >= len(p5_row) or not bool(p5_row[column_index]):
            continue
        packaging_source = f"p5_from_{producer_id}"
        (
            operator_id,
            family_id,
            operator_label,
            family_label,
            parameter_digest,
        ) = _packaging_operator_identity(
            packaging_source=packaging_source,
            selector_token="p5_row_selector",
        )
        entries.append(
            (
                operator_id,
                family_id,
                packaging_source,
                producer_id,
                operator_label,
                family_label,
                parameter_digest,
            )
        )
    return entries


def _ensure_runner_binary(
    *,
    repo_root: Path,
    config: PicaPilotCampaign,
    stdout_path: Path,
    stderr_path: Path,
) -> tuple[Path, list[str]]:
    target_dir = repo_root / config.invocation.cargo_target_dir
    binary_path = target_dir / "release" / config.invocation.binary_name
    build_command = [
        "cargo",
        "build",
        "--release",
        "-p",
        config.invocation.binary_name,
        "--target-dir",
        config.invocation.cargo_target_dir,
        "--manifest-path",
        config.invocation.manifest_path,
    ]
    if binary_path.exists():
        return binary_path, build_command
    build = subprocess.run(
        build_command,
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    stdout_path.write_text(build.stdout, encoding="utf-8")
    stderr_path.write_text(build.stderr, encoding="utf-8")
    if build.returncode != 0:
        raise RuntimeError(
            f"PICA build failed with return code {build.returncode}: {config.invocation.binary_name}"
        )
    if not binary_path.exists():
        raise FileNotFoundError(f"expected runner binary not found: {binary_path}")
    return binary_path, build_command


def _run_pica_subprocess(
    *,
    repo_root: Path,
    config: PicaPilotCampaign,
    stdout_path: Path,
    stderr_path: Path,
) -> tuple[list[str], subprocess.CompletedProcess[str]]:
    binary_path, _build_command = _ensure_runner_binary(
        repo_root=repo_root,
        config=config,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
    )
    command = [
        binary_path.as_posix(),
        "--exp",
        config.run_settings.exp_id,
        "--seed",
        str(config.run_settings.seed),
        "--scale",
        str(config.run_settings.scale),
        "--config",
        config.run_settings.config_name,
    ]
    completed = subprocess.run(
        command,
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
        timeout=config.run_settings.timeout_seconds,
    )
    stdout_path.write_text(completed.stdout, encoding="utf-8")
    stderr_path.write_text(completed.stderr, encoding="utf-8")
    return command, completed


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _build_bridge_artifacts(
    *,
    run_dir: Path,
    repo_root: Path,
    config: PicaPilotCampaign,
    stdout: str,
    export_timestamp: str,
) -> tuple[Path, Path, Path, Path, Path, Path, Path, Path]:
    audit = _extract_audit_json(stdout)
    scans = audit.get("multi_scale_scan")
    if not isinstance(scans, list) or not scans:
        raise ValueError("PICA audit JSON did not contain a non-empty multi_scale_scan")

    lens_source = _sanitize_token(_extract_lens_source(stdout))
    macro_level_label = _extract_macro_level(stdout)
    level_id = f"level_{_sanitize_token(macro_level_label)}"

    export_bundle_path = run_dir / "pica-export-bundle.json"
    campaign_export_path = run_dir / "pica-campaign-export.json"
    run_ledger_path = run_dir / "pica-run-ledger.json"
    closure_catalog_path = run_dir / "pica-closure-catalog.json"
    observable_ledger_path = run_dir / "pica-observable-ledger.json"
    commutator_catalog_path = run_dir / "pica-commutator-catalog.json"
    packaging_operator_catalog_path = run_dir / "pica-packaging-operator-catalog.json"
    packaging_selection_ledger_path = run_dir / "pica-packaging-selection-ledger.json"

    run_id = f"{config.point_id}__seed_{config.run_settings.seed}"
    observable_ledger_id = f"observable_ledger_{run_id}"
    closure_catalog_id = f"closure_catalog_{run_id}"
    commutator_catalog_id = f"commutator_catalog_{run_id}"
    export_bundle_id = f"{config.pilot_campaign_id}_bundle"
    packaging_operator_catalog_id = f"packaging_operator_catalog_{run_id}"
    packaging_selection_ledger_id = f"packaging_selection_ledger_{run_id}"

    protocol_steps: list[PicaProtocolStep] = []
    resolutions: list[PicaResolutionRecord] = []
    closures: list[PicaClosureRecord] = []
    lenses: list[PicaLensRecord] = []
    rows: list[PicaObservableRow] = []

    if config.export_settings.pica_export_mode == "discovery_grade_per_trajectory":
        discovery_grade = _extract_discovery_grade_json(stdout)
        raw_contexts = discovery_grade.get("contexts")
        raw_rows = discovery_grade.get("rows")
        trajectory_count = discovery_grade.get("trajectory_count")
        if not isinstance(raw_contexts, list) or not raw_contexts:
            raise ValueError(
                "discovery-grade export must include a non-empty contexts list"
            )
        if not isinstance(raw_rows, list) or not raw_rows:
            raise ValueError(
                "discovery-grade export must include a non-empty rows list"
            )
        if isinstance(trajectory_count, bool) or not isinstance(trajectory_count, int):
            raise ValueError(
                "discovery-grade export must include an integer trajectory_count"
            )
        seen_resolution_ids: set[str] = set()
        seen_closure_ids: set[str] = set()
        seen_lens_ids: set[str] = set()
        seen_protocol_step_ids: set[str] = set()
        for raw_context in raw_contexts:
            if not isinstance(raw_context, dict):
                raise ValueError("discovery-grade contexts must be objects")
            step_index = raw_context.get("step_index")
            protocol_step_id = raw_context.get("protocol_step_id")
            resolution_id = raw_context.get("resolution_id")
            closure_id = raw_context.get("closure_id")
            lens_id = raw_context.get("lens_id")
            if isinstance(step_index, bool) or not isinstance(step_index, int):
                raise ValueError(
                    "discovery-grade contexts must include integer step_index"
                )
            for name, value in [
                ("protocol_step_id", protocol_step_id),
                ("resolution_id", resolution_id),
                ("closure_id", closure_id),
                ("lens_id", lens_id),
            ]:
                if not isinstance(value, str) or not value:
                    raise ValueError(
                        f"discovery-grade contexts must include non-empty {name}"
                    )
            if protocol_step_id not in seen_protocol_step_ids:
                protocol_steps.append(
                    PicaProtocolStep(
                        step_index=step_index,
                        protocol_step_id=protocol_step_id,
                        stage_label=f"scan_k_{raw_context.get('k', step_index)}",
                    )
                )
                seen_protocol_step_ids.add(protocol_step_id)
            if resolution_id not in seen_resolution_ids:
                resolutions.append(
                    PicaResolutionRecord(
                        resolution_id=resolution_id,
                        level_id=str(raw_context.get("level_id") or level_id),
                        label=f"scan_k_{raw_context.get('k', step_index)}",
                        role="adapter_resolution",
                    )
                )
                seen_resolution_ids.add(resolution_id)
            if closure_id not in seen_closure_ids:
                closures.append(
                    PicaClosureRecord(
                        closure_id=closure_id,
                        level_id=str(raw_context.get("level_id") or level_id),
                        resolution_id=resolution_id,
                        label=f"{config.run_settings.config_name}_k_{raw_context.get('k', step_index)}",
                        role="adapter_closure",
                        support_metadata=_scalar_metadata(raw_context),
                        notes=[
                            "Adapter export derived from KEY_DISCOVERY_GRADE_JSON trajectory assignments."
                        ],
                    )
                )
                seen_closure_ids.add(closure_id)
            if lens_id not in seen_lens_ids:
                lenses.append(
                    PicaLensRecord(
                        lens_id=lens_id,
                        level_id=str(raw_context.get("level_id") or level_id),
                        resolution_id=resolution_id,
                        closure_id=closure_id,
                        label=f"{lens_source}_k_{raw_context.get('k', step_index)}",
                        role="adapter_lens",
                        support_metadata={
                            "lens_source": lens_source,
                            **_scalar_metadata(raw_context),
                        },
                    )
                )
                seen_lens_ids.add(lens_id)
        for raw_row in raw_rows:
            if not isinstance(raw_row, dict):
                raise ValueError("discovery-grade rows must be objects")
            rows.append(
                PicaObservableRow(
                    trajectory_id=str(raw_row["trajectory_id"]),
                    step_index=int(raw_row["step_index"]),
                    protocol_step_id=str(raw_row["protocol_step_id"]),
                    preparation_id=config.preparation_id,
                    protocol_id=config.protocol_id,
                    level_id=str(raw_row.get("level_id") or level_id),
                    resolution_id=str(raw_row["resolution_id"]),
                    closure_id=str(raw_row["closure_id"]),
                    lens_id=str(raw_row["lens_id"]),
                    observation_label=str(raw_row["observation_label"]),
                    phase_label="adapter_discovery_grade",
                    macrostate_label=(
                        str(raw_row["macrostate_label"])
                        if raw_row.get("macrostate_label") is not None
                        else None
                    ),
                    observation_payload=_scalar_payload(
                        raw_row.get("observation_payload", {})
                        if isinstance(raw_row.get("observation_payload"), dict)
                        else {}
                    ),
                )
            )
        observation_granularity = "per_trajectory"
        cooccurrence_scope = "within_run_and_trajectory"
        supports_structural_probe_conditioning = True
        ledger_trajectory_count = trajectory_count
        ledger_flags = ["adapter_export", "discovery_grade_per_trajectory"]
        ledger_notes = [
            "Observable-first adapter ledger derived from KEY_DISCOVERY_GRADE_JSON per-trajectory assignments."
        ]

    else:
        for index, raw_scan in enumerate(scans):
            if not isinstance(raw_scan, dict):
                raise ValueError("multi_scale_scan entries must be objects")
            k_value = raw_scan.get("k")
            if isinstance(k_value, bool) or not isinstance(k_value, int):
                raise ValueError(
                    "multi_scale_scan entries must contain integer k values"
                )
            protocol_step_id = f"{config.protocol_id}_step_{index}"
            resolution_id = f"resolution_k_{k_value}"
            closure_id = f"closure_{config.run_settings.config_name}_k_{k_value}"
            lens_id = f"lens_{lens_source}_k_{k_value}"
            protocol_steps.append(
                PicaProtocolStep(
                    step_index=index,
                    protocol_step_id=protocol_step_id,
                    stage_label=f"scan_k_{k_value}",
                )
            )
            resolutions.append(
                PicaResolutionRecord(
                    resolution_id=resolution_id,
                    level_id=level_id,
                    label=f"scan_k_{k_value}",
                    role="adapter_resolution",
                )
            )
            closures.append(
                PicaClosureRecord(
                    closure_id=closure_id,
                    level_id=level_id,
                    resolution_id=resolution_id,
                    label=f"{config.run_settings.config_name}_k_{k_value}",
                    role="adapter_closure",
                    support_metadata={
                        "scan_k": k_value,
                        "macro_gap": raw_scan.get("macro_gap"),
                        "frob": raw_scan.get("frob"),
                    },
                    notes=[
                        "Adapter export derived from KEY_AUDIT_JSON multi_scale_scan."
                    ],
                )
            )
            lenses.append(
                PicaLensRecord(
                    lens_id=lens_id,
                    level_id=level_id,
                    resolution_id=resolution_id,
                    closure_id=closure_id,
                    label=f"{lens_source}_k_{k_value}",
                    role="adapter_lens",
                    support_metadata={
                        "lens_source": lens_source,
                        "scan_k": k_value,
                    },
                )
            )
            rows.append(
                PicaObservableRow(
                    trajectory_id=f"aggregate_seed_{config.run_settings.seed}",
                    step_index=index,
                    protocol_step_id=protocol_step_id,
                    preparation_id=config.preparation_id,
                    protocol_id=config.protocol_id,
                    level_id=level_id,
                    resolution_id=resolution_id,
                    closure_id=closure_id,
                    lens_id=lens_id,
                    observation_label=f"multi_scale_scan_k_{k_value}",
                    phase_label="adapter_multi_scale_scan",
                    macrostate_label=f"macro_k_{k_value}",
                    observation_payload=_scalar_payload(raw_scan),
                )
            )
        observation_granularity = "aggregate_summary"
        cooccurrence_scope = "none"
        supports_structural_probe_conditioning = False
        ledger_trajectory_count = 1 if rows else 0
        ledger_flags = ["adapter_export", "aggregate_scan_rows"]
        ledger_notes = [
            "Observable-first adapter ledger derived from KEY_AUDIT_JSON multi_scale_scan rows."
        ]

    raw_commutators = _extract_commutator_catalog_json(stdout)
    raw_commutator_rows = raw_commutators.get("rows", [])
    if not isinstance(raw_commutator_rows, list):
        raise ValueError("commutator export rows must be a list when present")
    commutator_rows = [
        PicaCommutatorEntry(
            pair_id=str(row["pair_id"]),
            primitive_pair=str(row["primitive_pair"]),
            metric_name=str(row["metric_name"]),
            metric_value=float(row["metric_value"]),
            nonzero=bool(row["nonzero"]),
            notes=[
                str(value)
                for value in row.get("notes", [])
                if isinstance(value, str) and value
            ],
            flags=[
                str(value)
                for value in row.get("flags", [])
                if isinstance(value, str) and value
            ],
        )
        for row in raw_commutator_rows
        if isinstance(row, dict)
    ]
    enabled_packaging_entries = _enabled_packaging_operator_entries(audit)
    packaging_operator_rows: dict[str, PicaPackagingOperatorEntry] = {
        operator_id: PicaPackagingOperatorEntry(
            packaging_operator_id=operator_id,
            packaging_family_id=family_id,
            packaging_source=packaging_source,
            producer_id=producer_id,
            operator_label=operator_label,
            family_label=family_label,
            operator_kind="bridge_selector_candidate",
            parameter_digest=parameter_digest,
            support_metadata={
                "selector_token": "p5_row_selector",
                "enabled_via_pica_config": True,
            },
            notes=[
                "Bridge-derived packaging operator candidate inferred from the enabled P5 row selector."
            ],
            flags=["bridge_identity", "candidate_operator"],
        )
        for (
            operator_id,
            family_id,
            packaging_source,
            producer_id,
            operator_label,
            family_label,
            parameter_digest,
        ) in enabled_packaging_entries
    }
    packaging_selection_rows: list[PicaPackagingSelectionRow] = []
    for row in rows:
        raw_packaging_source = row.observation_payload.get("packaging_source")
        if raw_packaging_source is None:
            continue
        packaging_source, producer_id, selector_token = _normalize_packaging_source(
            raw_packaging_source
        )
        (
            packaging_operator_id,
            packaging_family_id,
            operator_label,
            family_label,
            parameter_digest,
        ) = _packaging_operator_identity(
            packaging_source=packaging_source,
            selector_token=selector_token,
        )
        if packaging_operator_id not in packaging_operator_rows:
            packaging_operator_rows[packaging_operator_id] = PicaPackagingOperatorEntry(
                packaging_operator_id=packaging_operator_id,
                packaging_family_id=packaging_family_id,
                packaging_source=packaging_source,
                producer_id=producer_id,
                operator_label=operator_label,
                family_label=family_label,
                operator_kind="bridge_selector_outcome",
                parameter_digest=parameter_digest,
                support_metadata={
                    "selector_token": selector_token,
                    "observed_in_rows": True,
                },
                notes=[
                    "Bridge-derived packaging operator identity promoted from observable row payload metadata."
                ],
                flags=["bridge_identity", "selected_operator"],
            )
        packaging_selection_rows.append(
            PicaPackagingSelectionRow(
                selection_row_id=(
                    f"packaging_selection_{run_id}_{row.protocol_step_id}_{row.trajectory_id}_{row.closure_id}_{row.lens_id or 'no_lens'}"
                ),
                run_id=run_id,
                point_id=config.point_id,
                preparation_id=row.preparation_id,
                protocol_id=row.protocol_id,
                protocol_step_id=row.protocol_step_id,
                step_index=row.step_index,
                trajectory_id=row.trajectory_id,
                support_group_id=(
                    f"{run_id}:{row.preparation_id}:{row.protocol_id}:{row.protocol_step_id}:{row.closure_id}:{row.lens_id or 'no_lens'}"
                ),
                level_id=row.level_id,
                resolution_id=row.resolution_id,
                closure_id=row.closure_id,
                lens_id=row.lens_id,
                packaging_operator_id=packaging_operator_id,
                packaging_family_id=packaging_family_id,
                packaging_source=packaging_source,
                selection_status="selected",
                candidate_operator_ids=sorted(packaging_operator_rows),
                support_scope_metadata={
                    "observation_label": row.observation_label,
                    "macrostate_label": row.macrostate_label,
                },
                candidate_set_metadata={
                    "candidate_count": len(packaging_operator_rows),
                    "selector_token": selector_token,
                },
                notes=[
                    "Packaging selection row derived from an observable-first discovery-grade row carrying packaging_source metadata."
                ],
                flags=["bridge_selection", "selected"],
            )
        )

    campaign_export = PicaCampaignExport(
        schema_version="pica-campaign-export.v1",
        campaign_id=config.campaign_id,
        campaign_label=config.campaign_label,
        source_config_path=config.source_config_path,
        path_policy=config.export_settings.path_policy,
        mechanism_summary={
            "substrate_config_id": config.substrate_config_id,
            "mechanism_family_id": config.mechanism_family_id,
            "enable_matrix_id": config.enable_matrix_id,
        },
        point_inventory=[
            PicaCampaignPoint(
                point_id=config.point_id,
                substrate_config_id=config.substrate_config_id,
                mechanism_family_id=config.mechanism_family_id,
                enable_matrix_id=config.enable_matrix_id,
                preparation_id=config.preparation_id,
                protocol_id=config.protocol_id,
                seed=config.run_settings.seed,
                run_id=run_id,
            )
        ],
        run_inventory=[
            PicaCampaignRunInventory(
                run_id=run_id,
                point_id=config.point_id,
                run_ledger_path=repo_relative_path(run_ledger_path, root=repo_root),
                closure_catalog_path=repo_relative_path(
                    closure_catalog_path,
                    root=repo_root,
                ),
                observable_ledger_path=repo_relative_path(
                    observable_ledger_path,
                    root=repo_root,
                ),
                commutator_catalog_path=repo_relative_path(
                    commutator_catalog_path,
                    root=repo_root,
                ),
                packaging_operator_catalog_path=repo_relative_path(
                    packaging_operator_catalog_path,
                    root=repo_root,
                ),
                packaging_selection_ledger_path=repo_relative_path(
                    packaging_selection_ledger_path,
                    root=repo_root,
                ),
            )
        ],
        notes=["Adapter-exported campaign created by the thin PICA pilot wrapper."],
        flags=["adapter_export"],
    )
    run_ledger = PicaRunLedger(
        schema_version="pica-run-ledger.v1",
        run_id=run_id,
        campaign_id=config.campaign_id,
        point_id=config.point_id,
        substrate_config_id=config.substrate_config_id,
        mechanism_family_id=config.mechanism_family_id,
        enable_matrix_id=config.enable_matrix_id,
        preparation_id=config.preparation_id,
        protocol_id=config.protocol_id,
        seed=config.run_settings.seed,
        trajectory_count=ledger_trajectory_count,
        protocol_steps=protocol_steps,
        closure_catalog_id=closure_catalog_id,
        closure_catalog_path=repo_relative_path(closure_catalog_path, root=repo_root),
        observable_ledger_id=observable_ledger_id,
        observable_ledger_path=repo_relative_path(
            observable_ledger_path,
            root=repo_root,
        ),
        commutator_catalog_id=commutator_catalog_id,
        commutator_catalog_path=repo_relative_path(
            commutator_catalog_path,
            root=repo_root,
        ),
        packaging_operator_catalog_id=packaging_operator_catalog_id,
        packaging_operator_catalog_path=repo_relative_path(
            packaging_operator_catalog_path,
            root=repo_root,
        ),
        packaging_selection_ledger_id=packaging_selection_ledger_id,
        packaging_selection_ledger_path=repo_relative_path(
            packaging_selection_ledger_path,
            root=repo_root,
        ),
        notes=[
            "Adapter-exported run ledger derived from one bounded runner subprocess."
        ],
        flags=["adapter_export"],
    )
    closure_catalog = PicaClosureCatalog(
        schema_version="pica-closure-catalog.v1",
        closure_catalog_id=closure_catalog_id,
        campaign_id=config.campaign_id,
        run_id=run_id,
        point_id=config.point_id,
        levels=[
            PicaLevelRecord(
                level_id=level_id,
                label=macro_level_label,
                role="adapter_observed_level",
            )
        ],
        resolutions=resolutions,
        closures=closures,
        lenses=lenses,
        notes=["Adapter-exported closure metadata from multi-scale scan rows."],
        flags=["adapter_export"],
    )
    observable_ledger = PicaObservableLedger(
        schema_version="pica-observable-ledger.v1",
        observable_ledger_id=observable_ledger_id,
        campaign_id=config.campaign_id,
        run_id=run_id,
        point_id=config.point_id,
        observation_granularity=observation_granularity,
        cooccurrence_scope=cooccurrence_scope,
        trajectory_count=ledger_trajectory_count,
        supports_structural_probe_conditioning=supports_structural_probe_conditioning,
        row_count=len(rows),
        rows=rows,
        notes=ledger_notes,
        flags=ledger_flags,
    )
    commutator_catalog = PicaCommutatorCatalog(
        schema_version="pica-commutator-catalog.v1",
        commutator_catalog_id=commutator_catalog_id,
        campaign_id=config.campaign_id,
        run_id=run_id,
        point_id=config.point_id,
        row_count=len(commutator_rows),
        rows=commutator_rows,
        notes=[
            "Structured commutator diagnostics exported from the vendor runner stdout."
        ],
        flags=["adapter_export", "structured_commutator_export"],
    )
    packaging_operator_catalog = PicaPackagingOperatorCatalog(
        schema_version="pica-packaging-operator-catalog.v1",
        packaging_operator_catalog_id=packaging_operator_catalog_id,
        export_bundle_id=export_bundle_id,
        campaign_id=config.campaign_id,
        run_id=run_id,
        point_id=config.point_id,
        row_count=len(packaging_operator_rows),
        rows=sorted(
            packaging_operator_rows.values(),
            key=lambda row: row.packaging_operator_id,
        ),
        notes=[
            "Bridge-derived packaging operator catalog promoted from observable packaging metadata and configured candidate selectors."
        ],
        flags=["adapter_export", "bridge_identity"],
    )
    packaging_selection_ledger = PicaPackagingSelectionLedger(
        schema_version="pica-packaging-selection-ledger.v1",
        packaging_selection_ledger_id=packaging_selection_ledger_id,
        export_bundle_id=export_bundle_id,
        campaign_id=config.campaign_id,
        run_id=run_id,
        point_id=config.point_id,
        row_count=len(packaging_selection_rows),
        rows=packaging_selection_rows,
        notes=[
            "Bridge-derived packaging selection ledger promoted from per-trajectory observable packaging rows."
        ],
        flags=["adapter_export", "bridge_selection"],
    )
    export_bundle = PicaExportBundle(
        schema_version="pica-export-bundle.v1",
        export_bundle_id=export_bundle_id,
        producer=PicaProducerMetadata(
            name="pica",
            version="pilot-wrapper",
            commit=(
                str(audit["git_sha"])
                if isinstance(audit.get("git_sha"), str) and audit["git_sha"]
                else None
            ),
            build_label=config.invocation.command_mode,
        ),
        export_timestamp=export_timestamp,
        path_policy=config.export_settings.path_policy,
        campaign_exports=[
            PicaCampaignExportRef(
                campaign_id=config.campaign_id,
                artifact_path=repo_relative_path(campaign_export_path, root=repo_root),
            )
        ],
        run_ledgers=[
            PicaRunLedgerRef(
                run_id=run_id,
                campaign_id=config.campaign_id,
                artifact_path=repo_relative_path(run_ledger_path, root=repo_root),
            )
        ],
        closure_catalogs=[
            PicaClosureCatalogRef(
                closure_catalog_id=closure_catalog_id,
                run_id=run_id,
                artifact_path=repo_relative_path(closure_catalog_path, root=repo_root),
            )
        ],
        observable_ledgers=[
            PicaObservableLedgerRef(
                observable_ledger_id=observable_ledger_id,
                run_id=run_id,
                artifact_path=repo_relative_path(
                    observable_ledger_path,
                    root=repo_root,
                ),
            )
        ],
        commutator_catalogs=[
            PicaCommutatorCatalogRef(
                commutator_catalog_id=commutator_catalog_id,
                run_id=run_id,
                artifact_path=repo_relative_path(
                    commutator_catalog_path,
                    root=repo_root,
                ),
            )
        ],
        packaging_operator_catalogs=[
            PicaPackagingOperatorCatalogRef(
                packaging_operator_catalog_id=packaging_operator_catalog_id,
                run_id=run_id,
                artifact_path=repo_relative_path(
                    packaging_operator_catalog_path,
                    root=repo_root,
                ),
            )
        ],
        packaging_selection_ledgers=[
            PicaPackagingSelectionLedgerRef(
                packaging_selection_ledger_id=packaging_selection_ledger_id,
                run_id=run_id,
                artifact_path=repo_relative_path(
                    packaging_selection_ledger_path,
                    root=repo_root,
                ),
            )
        ],
        notes=[
            "Thin subprocess wrapper adapter export from vendor/six-birds-pica runner output."
        ],
        flags=["adapter_export"],
    )

    _write_json(campaign_export_path, campaign_export.model_dump(mode="json"))
    _write_json(run_ledger_path, run_ledger.model_dump(mode="json"))
    _write_json(closure_catalog_path, closure_catalog.model_dump(mode="json"))
    _write_json(observable_ledger_path, observable_ledger.model_dump(mode="json"))
    _write_json(commutator_catalog_path, commutator_catalog.model_dump(mode="json"))
    _write_json(
        packaging_operator_catalog_path,
        packaging_operator_catalog.model_dump(mode="json"),
    )
    _write_json(
        packaging_selection_ledger_path,
        packaging_selection_ledger.model_dump(mode="json"),
    )
    _write_json(export_bundle_path, export_bundle.model_dump(mode="json"))

    return (
        export_bundle_path,
        campaign_export_path,
        run_ledger_path,
        closure_catalog_path,
        observable_ledger_path,
        commutator_catalog_path,
        packaging_operator_catalog_path,
        packaging_selection_ledger_path,
    )


def run_pica_pilot_campaign(
    *,
    config_path: str | Path,
    category: str,
    label: str | None = None,
    seed: int = 0,
    timestamp: str | None = None,
    root: str | Path | None = None,
    command: list[str] | None = None,
) -> PicaPilotArtifacts:
    source_root = get_repo_root()
    output_root = get_repo_root(root)
    config = load_model(config_path, kind="pica-pilot-campaign")
    assert isinstance(config, PicaPilotCampaign)

    run_dir, run_id, manifest_timestamp = create_run_directory(
        category=category,
        label=label,
        timestamp=timestamp,
        root=output_root,
    )
    stdout_path = run_dir / "stdout.txt"
    stderr_path = run_dir / "stderr.txt"
    summary_path = run_dir / "pica-pilot-summary.json"
    note_path = run_dir / "pica-pilot-note.md"
    result_note_path = run_dir / "result-note.json"
    manifest_path = run_dir / "run-manifest.json"

    wrapper_command, completed = _run_pica_subprocess(
        repo_root=source_root,
        config=config,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"PICA pilot subprocess failed with {completed.returncode}")

    (
        export_bundle_path,
        campaign_export_path,
        run_ledger_path,
        closure_catalog_path,
        observable_ledger_path,
        commutator_catalog_path,
        packaging_operator_catalog_path,
        packaging_selection_ledger_path,
    ) = _build_bridge_artifacts(
        run_dir=run_dir,
        repo_root=output_root,
        config=config,
        stdout=completed.stdout,
        export_timestamp=manifest_timestamp,
    )
    resolved = load_pica_export_bundle(export_bundle_path, repo_root=output_root)
    source_index = resolved.to_source_index_payload()
    primary_ledger = next(iter(resolved.observable_ledgers.values()))

    stable_artifacts = PicaPilotArtifactPaths(
        export_bundle=repo_relative_path(export_bundle_path, root=output_root),
        campaign_export=repo_relative_path(campaign_export_path, root=output_root),
        run_ledger=repo_relative_path(run_ledger_path, root=output_root),
        closure_catalog=repo_relative_path(closure_catalog_path, root=output_root),
        observable_ledger=repo_relative_path(
            observable_ledger_path,
            root=output_root,
        ),
        commutator_catalog=repo_relative_path(
            commutator_catalog_path,
            root=output_root,
        ),
        packaging_operator_catalog=repo_relative_path(
            packaging_operator_catalog_path,
            root=output_root,
        ),
        packaging_selection_ledger=repo_relative_path(
            packaging_selection_ledger_path,
            root=output_root,
        ),
        stdout=repo_relative_path(stdout_path, root=output_root),
        stderr=repo_relative_path(stderr_path, root=output_root),
    )
    result = PicaPilotResult(
        schema_version="pica-pilot-result.v1",
        pilot_run_id=run_id,
        pilot_config_path=repo_relative_path(config_path, root=source_root),
        vendor_root_path=config.invocation.vendor_root,
        wrapper_command=wrapper_command,
        command_mode=config.invocation.command_mode,
        export_mode=config.export_settings.export_mode,
        pica_export_mode=config.export_settings.pica_export_mode,
        adapter_mode=config.export_settings.adapter_mode,
        observation_granularity=primary_ledger.observation_granularity,
        cooccurrence_scope=primary_ledger.cooccurrence_scope,
        supports_structural_probe_conditioning=(
            primary_ledger.supports_structural_probe_conditioning
        ),
        return_code=completed.returncode,
        success=True,
        bridge_validation_status="validated",
        stable_artifacts=stable_artifacts,
        summary_counts=PicaPilotSummaryCounts(
            campaign_count=len(resolved.campaigns),
            run_count=len(resolved.runs),
            closure_count=len(source_index["closure_ids"]),
            lens_count=len(source_index["lens_ids"]),
            observable_ledger_count=len(resolved.observable_ledgers),
            commutator_catalog_count=len(resolved.commutator_catalogs),
            packaging_operator_catalog_count=len(resolved.packaging_operator_catalogs),
            packaging_selection_ledger_count=len(resolved.packaging_selection_ledgers),
        ),
        notes=[
            "Thin subprocess wrapper executed vendor/six-birds-pica without importing vendor internals.",
            "Final stable artifacts are the bridge-contract exports written in the wrapper run directory.",
        ],
        flags=["adapter_export", "subprocess_wrapper"],
    )
    _write_json(summary_path, result.model_dump(mode="json"))

    note_path.write_text(
        "\n".join(
            [
                "# PICA Pilot Wrapper",
                "",
                f"- Pilot config: `{repo_relative_path(config_path, root=source_root)}`",
                f"- Source repo root: `{source_root.as_posix()}`",
                f"- Vendor root: `{config.invocation.vendor_root}`",
                f"- Vendor command: `{' '.join(wrapper_command)}`",
                f"- Export mode: `{config.export_settings.export_mode}`",
                f"- PICA export mode: `{config.export_settings.pica_export_mode}`",
                f"- Adapter mode: `{config.export_settings.adapter_mode or 'none'}`",
                f"- Observation granularity: `{primary_ledger.observation_granularity}`",
                f"- Cooccurrence scope: `{primary_ledger.cooccurrence_scope}`",
                "- Supports structural probe conditioning: "
                f"`{primary_ledger.supports_structural_probe_conditioning}`",
                f"- Bridge bundle: `{stable_artifacts.export_bundle}`",
                f"- Campaign export: `{stable_artifacts.campaign_export}`",
                f"- Run ledger: `{stable_artifacts.run_ledger}`",
                f"- Closure catalog: `{stable_artifacts.closure_catalog}`",
                f"- Observable ledger: `{stable_artifacts.observable_ledger}`",
                f"- Commutator catalog: `{stable_artifacts.commutator_catalog}`",
                f"- Packaging operator catalog: `{stable_artifacts.packaging_operator_catalog}`",
                f"- Packaging selection ledger: `{stable_artifacts.packaging_selection_ledger}`",
                f"- Bridge validation status: `{result.bridge_validation_status}`",
                f"- Campaign count: `{result.summary_counts.campaign_count}`",
                f"- Run count: `{result.summary_counts.run_count}`",
                f"- Closure count: `{result.summary_counts.closure_count}`",
                f"- Lens count: `{result.summary_counts.lens_count}`",
                f"- Observable ledger count: `{result.summary_counts.observable_ledger_count}`",
                f"- Commutator catalog count: `{result.summary_counts.commutator_catalog_count}`",
                f"- Packaging operator catalog count: `{result.summary_counts.packaging_operator_catalog_count}`",
                f"- Packaging selection ledger count: `{result.summary_counts.packaging_selection_ledger_count}`",
                "",
            ]
        ),
        encoding="utf-8",
    )

    output_artifacts = {
        "summary": repo_relative_path(summary_path, root=output_root),
        "note": repo_relative_path(note_path, root=output_root),
        "result_note": repo_relative_path(result_note_path, root=output_root),
        "manifest": repo_relative_path(manifest_path, root=output_root),
        "stdout": stable_artifacts.stdout,
        "stderr": stable_artifacts.stderr,
        "export_bundle": stable_artifacts.export_bundle,
        "campaign_export": stable_artifacts.campaign_export,
        "run_ledger": stable_artifacts.run_ledger,
        "closure_catalog": stable_artifacts.closure_catalog,
        "observable_ledger": stable_artifacts.observable_ledger,
        "commutator_catalog": stable_artifacts.commutator_catalog,
        "packaging_operator_catalog": stable_artifacts.packaging_operator_catalog,
        "packaging_selection_ledger": stable_artifacts.packaging_selection_ledger,
    }
    result_note = ResultNote(
        note_format_version="result-note.v1",
        note_id=f"note_{run_id}",
        run_id=run_id,
        instance_ids=[resolved.export_bundle.export_bundle_id],
        metrics={
            "campaign_count": result.summary_counts.campaign_count,
            "run_count": result.summary_counts.run_count,
            "closure_count": result.summary_counts.closure_count,
            "lens_count": result.summary_counts.lens_count,
            "observable_ledger_count": result.summary_counts.observable_ledger_count,
            "commutator_catalog_count": result.summary_counts.commutator_catalog_count,
            "packaging_operator_catalog_count": (
                result.summary_counts.packaging_operator_catalog_count
            ),
            "packaging_selection_ledger_count": (
                result.summary_counts.packaging_selection_ledger_count
            ),
            "return_code": completed.returncode,
            "supports_structural_probe_conditioning": (
                1 if primary_ledger.supports_structural_probe_conditioning else 0
            ),
        },
        interpretation=(
            "PICA pilot wrapper executed a bounded vendor subprocess and normalized its output into the bridge-contract artifacts."
        ),
        caveats=[
            "This wrapper is subprocess-based and does not import or embed PICA internals into the Python runtime.",
            "The committed pilot uses adapter export from KEY_AUDIT_JSON multi_scale_scan output rather than a native bridge export.",
        ],
        artifact_refs=output_artifacts,
        metadata={
            "analysis_kind": "pica_pilot_wrapper",
            "vendor_root": config.invocation.vendor_root,
            "bridge_validation_status": result.bridge_validation_status,
            "pica_export_mode": config.export_settings.pica_export_mode,
            "observation_granularity": primary_ledger.observation_granularity,
        },
    )
    _write_json(result_note_path, result_note.model_dump(mode="json"))

    manifest = build_run_manifest(
        run_id=run_id,
        timestamp=manifest_timestamp,
        command=command
        or [
            sys.executable,
            "-m",
            "sixbirds_event",
            "pica",
            "run-pilot",
            repo_relative_path(config_path, root=source_root),
        ],
        seed=seed,
        input_artifacts={
            "pilot_config": repo_relative_path(config_path, root=source_root)
        },
        output_artifacts=output_artifacts,
        status="succeeded",
        git_commit=detect_git_commit(root=source_root),
        metadata={
            "analysis_kind": "pica_pilot_wrapper",
            "vendor_root": config.invocation.vendor_root,
            "export_mode": config.export_settings.export_mode,
            "pica_export_mode": config.export_settings.pica_export_mode,
        },
    )
    write_run_manifest(manifest, run_dir=run_dir)
    return PicaPilotArtifacts(
        run_id=run_id,
        run_dir=repo_relative_path(run_dir, root=output_root),
        summary_path=output_artifacts["summary"],
        note_path=output_artifacts["note"],
        result_note_path=output_artifacts["result_note"],
        manifest_path=output_artifacts["manifest"],
        export_bundle_path=stable_artifacts.export_bundle,
        campaign_export_path=stable_artifacts.campaign_export,
        run_ledger_path=stable_artifacts.run_ledger,
        closure_catalog_path=stable_artifacts.closure_catalog,
        observable_ledger_path=stable_artifacts.observable_ledger,
        commutator_catalog_path=stable_artifacts.commutator_catalog,
        packaging_operator_catalog_path=stable_artifacts.packaging_operator_catalog,
        packaging_selection_ledger_path=stable_artifacts.packaging_selection_ledger,
        stdout_path=stable_artifacts.stdout or output_artifacts["stdout"],
        stderr_path=stable_artifacts.stderr or output_artifacts["stderr"],
        result=result,
    )
