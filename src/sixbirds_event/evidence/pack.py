from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import sys
from typing import Any

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
from .models import CaveatRegistry, PaperEvidencePack, TheoremExperimentMap


@dataclass(slots=True)
class PaperEvidencePackArtifacts:
    run_id: str
    run_dir: str
    summary_path: str
    note_path: str
    result_note_path: str
    manifest_path: str
    theorem_experiment_map_path: str
    flagship_witnesses_path: str
    best_evidence_by_axis_path: str
    caveat_registry_path: str


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _resolve_repo_artifact(path: str | Path, *, root: Path) -> Path:
    candidate = root / path
    if candidate.exists():
        return candidate
    canonical_root = get_repo_root()
    fallback = canonical_root / path
    if fallback.exists():
        return fallback
    return candidate


def _require_artifact(path: str | Path, *, root: Path) -> Path:
    resolved = _resolve_repo_artifact(path, root=root)
    if not resolved.exists():
        raise FileNotFoundError(f"required artifact not found: {path}")
    return resolved


def _load_json(path: str | Path, *, root: Path) -> dict[str, Any]:
    resolved = _require_artifact(path, root=root)
    return json.loads(resolved.read_text(encoding="utf-8"))


def _artifact_ref(path: str | Path) -> str:
    candidate = Path(path)
    if candidate.is_absolute():
        return repo_relative_path(candidate, root=get_repo_root())
    return candidate.as_posix()


def load_paper_evidence_pack(path: str | Path) -> PaperEvidencePack:
    model = load_model(path, kind="paper-evidence-pack")
    assert isinstance(model, PaperEvidencePack)
    return model


def _load_theorem_map(path: str | Path, *, root: Path) -> TheoremExperimentMap:
    model = load_model(
        _require_artifact(path, root=root), kind="theorem-experiment-map"
    )
    assert isinstance(model, TheoremExperimentMap)
    return model


def _load_caveat_registry(path: str | Path, *, root: Path) -> CaveatRegistry:
    model = load_model(_require_artifact(path, root=root), kind="caveat-registry")
    assert isinstance(model, CaveatRegistry)
    return model


def _load_best_evidence(path: str | Path, *, root: Path) -> dict[str, Any]:
    payload = _load_json(path, root=root)
    if payload.get("best_evidence_format_version") != "paper-best-evidence-by-axis.v1":
        raise ValueError(
            "best_evidence_format_version must equal 'paper-best-evidence-by-axis.v1'"
        )
    entries = payload.get("entries")
    if not isinstance(entries, list) or len(entries) != 3:
        raise ValueError(
            "best-evidence-by-axis entries must contain exactly three rows"
        )
    return payload


def _load_flagship_witnesses(path: str | Path, *, root: Path) -> dict[str, Any]:
    payload = _load_json(path, root=root)
    if (
        payload.get("flagship_witnesses_format_version")
        != "paper-flagship-witnesses.v1"
    ):
        raise ValueError(
            "flagship_witnesses_format_version must equal 'paper-flagship-witnesses.v1'"
        )
    entries = payload.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ValueError("flagship witness entries must be a non-empty list")
    required_types = {
        "theorem_benchmark_flagship",
        "mechanism_axis_flagship",
        "lens_axis_flagship",
        "packaging_axis_flagship",
    }
    found_types = {
        entry.get("witness_type") for entry in entries if isinstance(entry, dict)
    }
    if found_types != required_types:
        raise ValueError(
            "flagship witness entries must contain theorem, mechanism, lens, and packaging flagships"
        )
    return payload


def _load_control_summary(path: str | Path, *, root: Path) -> dict[str, Any]:
    payload = _load_json(path, root=root)
    if (
        payload.get("flagship_control_summary_format_version")
        != "paper-flagship-control-summary.v1"
    ):
        raise ValueError(
            "flagship_control_summary_format_version must equal 'paper-flagship-control-summary.v1'"
        )
    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("control summary cases must be a non-empty list")
    required_case_ids = {
        "mechanism_exp104_p6_row_all_n64_seed0",
        "lens_exp104_p6_row_all_n64_cross_res_k4_k20",
        "packaging_cross_res_k4_k20",
    }
    found_case_ids = {case.get("case_id") for case in cases if isinstance(case, dict)}
    if found_case_ids != required_case_ids:
        raise ValueError(
            "control summary must contain the committed mechanism, lens, and packaging flagship cases"
        )
    if "overall_bundle_verdict" not in payload:
        raise ValueError("control summary must include overall_bundle_verdict")
    return payload


def _load_candidate_manifest(
    path: str | Path, *, root: Path, version_key: str
) -> dict[str, Any]:
    payload = _load_json(path, root=root)
    if not isinstance(payload.get(version_key), str):
        raise ValueError(f"{path} must include {version_key}")
    return payload


def _render_note(
    *,
    pack: PaperEvidencePack,
    theorem_map: TheoremExperimentMap,
    flagship_witnesses: dict[str, Any],
    best_evidence: dict[str, Any],
    control_summary: dict[str, Any],
    caveat_registry: CaveatRegistry,
    output_paths: dict[str, str],
) -> str:
    lines = [
        "# Paper Evidence Pack",
        "",
        "## Contents",
        f"- Theorem-to-experiment map: `{pack.theorem_experiment_map_ref}`",
        f"- Flagship witness list: `{pack.flagship_witnesses_ref}`",
        f"- Best evidence by axis: `{pack.best_evidence_by_axis_ref}`",
        f"- Control-bundle summary: `{pack.control_bundle_summary_ref}`",
        f"- Caveat registry: `{pack.caveat_registry_ref}`",
        "",
        "## Primary theorem-side evidence",
    ]
    for label, ref in pack.theorem_side_anchor_refs.items():
        lines.append(f"- `{label}`: `{ref}`")
    lines.extend(
        [
            "",
            "## Flagship numerical evidence",
        ]
    )
    for entry in flagship_witnesses["entries"]:
        lines.append(
            f"- `{entry['witness_type']}`: `{entry['witness_id']}` status=`{entry['witness_status']}`"
        )
    lines.extend(
        [
            "",
            "## Supporting controls",
            f"- Control bundle overall verdict: `{control_summary['overall_bundle_verdict']}`",
        ]
    )
    for case in control_summary["cases"]:
        lines.append(
            f"- `{case['case_id']}` hidden_record=`{case['hidden_record_verdict']}` flattening=`{case['flattening_verdict']}` robustness=`{case['robustness_verdict']}` final=`{case['final_verdict']}`"
        )
    lines.extend(
        [
            "",
            "## Caveats",
        ]
    )
    for entry in caveat_registry.entries:
        lines.append(f"- `{entry.scope}` / `{entry.caveat_id}`: {entry.label}")
    lines.extend(
        [
            "",
            "## Missing transient-output handling",
            f"- `t50_runtime_outputs`: `{pack.transient_gap_resolution['t50_runtime_outputs']}`",
            f"- `th6_runtime_outputs`: `{pack.transient_gap_resolution['th6_runtime_outputs']}`",
            "",
            "## Pack artifacts",
        ]
    )
    for label, ref in output_paths.items():
        lines.append(f"- `{label}`: `{ref}`")
    lines.extend(
        [
            "",
            "## Summary counts",
            f"- theorem entries: `{len(theorem_map.entries)}`",
            f"- flagship witnesses: `{len(flagship_witnesses['entries'])}`",
            f"- best-evidence rows: `{len(best_evidence['entries'])}`",
            f"- caveat entries: `{len(caveat_registry.entries)}`",
        ]
    )
    return "\n".join(lines) + "\n"


def build_paper_evidence_pack(
    *,
    index_path: str | Path,
    category: str = "results",
    label: str | None = None,
    seed: int = 0,
    timestamp: str | None = None,
    root: str | Path | None = None,
    command: list[str] | None = None,
) -> PaperEvidencePackArtifacts:
    pack = load_paper_evidence_pack(index_path)
    repo_root = get_repo_root(root)

    theorem_map = _load_theorem_map(pack.theorem_experiment_map_ref, root=repo_root)
    flagship_witnesses = _load_flagship_witnesses(
        pack.flagship_witnesses_ref, root=repo_root
    )
    best_evidence = _load_best_evidence(pack.best_evidence_by_axis_ref, root=repo_root)
    control_summary = _load_control_summary(
        pack.control_bundle_summary_ref, root=repo_root
    )
    caveat_registry = _load_caveat_registry(pack.caveat_registry_ref, root=repo_root)
    _load_candidate_manifest(
        pack.figure_candidate_refs["figure_candidates_manifest"],
        root=repo_root,
        version_key="figure_candidates_format_version",
    )
    _load_candidate_manifest(
        pack.table_candidate_refs["table_candidates_manifest"],
        root=repo_root,
        version_key="table_candidates_format_version",
    )
    for mapping in [
        pack.theorem_side_anchor_refs,
        pack.mechanism_evidence_refs,
        pack.lens_evidence_refs,
        pack.packaging_evidence_refs,
        pack.control_bundle_evidence_refs,
        pack.hierarchy_claim_strength_refs,
        pack.figure_candidate_refs,
        pack.table_candidate_refs,
    ]:
        for ref in mapping.values():
            _require_artifact(ref, root=repo_root)

    run_dir, run_id, manifest_timestamp = create_run_directory(
        category=category,
        label=label or "paper-evidence-pack",
        timestamp=timestamp,
        root=repo_root,
    )
    summary_path = run_dir / "paper-evidence-pack-summary.json"
    note_path = run_dir / "paper-evidence-pack-note.md"
    result_note_path = run_dir / "result-note.json"

    output_paths = {
        "summary": repo_relative_path(summary_path, root=repo_root),
        "note": repo_relative_path(note_path, root=repo_root),
        "result_note": repo_relative_path(result_note_path, root=repo_root),
        "manifest": repo_relative_path(run_dir / "run-manifest.json", root=repo_root),
    }

    summary_payload = {
        "summary_format_version": "paper-evidence-pack-summary.v1",
        "evidence_pack_id": pack.evidence_pack_id,
        "theorem_experiment_map_ref": pack.theorem_experiment_map_ref,
        "flagship_witnesses_ref": pack.flagship_witnesses_ref,
        "best_evidence_by_axis_ref": pack.best_evidence_by_axis_ref,
        "control_bundle_summary_ref": pack.control_bundle_summary_ref,
        "caveat_registry_ref": pack.caveat_registry_ref,
        "figure_candidate_refs": pack.figure_candidate_refs,
        "table_candidate_refs": pack.table_candidate_refs,
        "transient_gap_resolution": pack.transient_gap_resolution,
        "summary_metrics": {
            "theorem_entry_count": len(theorem_map.entries),
            "flagship_witness_count": len(flagship_witnesses["entries"]),
            "best_evidence_row_count": len(best_evidence["entries"]),
            "caveat_count": len(caveat_registry.entries),
            "overall_control_bundle_verdict": control_summary["overall_bundle_verdict"],
        },
        "key_artifact_refs": {
            "theorem_experiment_map": pack.theorem_experiment_map_ref,
            "flagship_witnesses": pack.flagship_witnesses_ref,
            "best_evidence_by_axis": pack.best_evidence_by_axis_ref,
            "control_bundle_summary": pack.control_bundle_summary_ref,
            "caveat_registry": pack.caveat_registry_ref,
            "three_axis_context_memo": pack.hierarchy_claim_strength_refs[
                "three_axis_context_memo"
            ],
            "hierarchy_proposition_index": pack.hierarchy_claim_strength_refs[
                "hierarchy_proposition_index"
            ],
            "package_conflict_sharpening": pack.theorem_side_anchor_refs[
                "package_conflict_sharpening"
            ],
        },
        "output_paths": output_paths,
    }
    _write_json(summary_path, summary_payload)

    note_path.write_text(
        _render_note(
            pack=pack,
            theorem_map=theorem_map,
            flagship_witnesses=flagship_witnesses,
            best_evidence=best_evidence,
            control_summary=control_summary,
            caveat_registry=caveat_registry,
            output_paths=output_paths,
        ),
        encoding="utf-8",
    )

    result_note = ResultNote(
        note_format_version="result-note.v1",
        note_id=f"note_{run_id}",
        run_id=run_id,
        instance_ids=[
            pack.evidence_pack_id,
            theorem_map.map_id,
            best_evidence["best_evidence_id"],
            caveat_registry.registry_id,
        ],
        metrics={
            "theorem_entry_count": len(theorem_map.entries),
            "flagship_witness_count": len(flagship_witnesses["entries"]),
            "caveat_count": len(caveat_registry.entries),
            "overall_control_bundle_verdict": control_summary["overall_bundle_verdict"],
            "t50_gap_filled_by_committed_summary": (
                pack.transient_gap_resolution["t50_runtime_outputs"]
                == "committed_summary_substitution"
            ),
            "th6_gap_filled_by_committed_summary": (
                pack.transient_gap_resolution["th6_runtime_outputs"]
                == "committed_summary_substitution"
            ),
        },
        interpretation=(
            "The paper-facing evidence pack curates theorem anchors, flagship witnesses, controls, hierarchy clarifications, and caveats into a stable drafting-ready bundle without depending on missing transient TH6 or T50 runtime outputs."
        ),
        caveats=[
            "Mechanism evidence preserves a committed witness separately from an axis-wide design-inadequate campaign.",
            "Lens evidence preserves both the same-step bounded-negative subregime and the cross-resolution accepted-obstruction flagship.",
            "Packaging evidence remains strongest but still carries the selector-branch divergence caveat.",
        ],
        artifact_refs=output_paths,
        metadata={
            "t50_gap_resolution": pack.transient_gap_resolution["t50_runtime_outputs"],
            "th6_gap_resolution": pack.transient_gap_resolution["th6_runtime_outputs"],
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
            "evidence",
            "build-pack",
            str(index_path),
        ],
        seed=seed,
        input_artifacts={
            "paper_evidence_pack_index": _artifact_ref(index_path),
            "theorem_experiment_map": pack.theorem_experiment_map_ref,
            "flagship_witnesses": pack.flagship_witnesses_ref,
            "best_evidence_by_axis": pack.best_evidence_by_axis_ref,
            "control_bundle_summary": pack.control_bundle_summary_ref,
            "caveat_registry": pack.caveat_registry_ref,
        },
        output_artifacts=output_paths,
        status="succeeded",
        metadata={
            "analysis_kind": "paper_evidence_pack",
            "evidence_pack_id": pack.evidence_pack_id,
            "t50_gap_resolution": pack.transient_gap_resolution["t50_runtime_outputs"],
            "th6_gap_resolution": pack.transient_gap_resolution["th6_runtime_outputs"],
            "overall_control_bundle_verdict": control_summary["overall_bundle_verdict"],
        },
        git_commit=detect_git_commit(root=repo_root),
    )
    manifest_path = write_run_manifest(manifest, run_dir=run_dir)

    return PaperEvidencePackArtifacts(
        run_id=run_id,
        run_dir=repo_relative_path(run_dir, root=repo_root),
        summary_path=repo_relative_path(summary_path, root=repo_root),
        note_path=repo_relative_path(note_path, root=repo_root),
        result_note_path=repo_relative_path(result_note_path, root=repo_root),
        manifest_path=repo_relative_path(manifest_path, root=repo_root),
        theorem_experiment_map_path=pack.theorem_experiment_map_ref,
        flagship_witnesses_path=pack.flagship_witnesses_ref,
        best_evidence_by_axis_path=pack.best_evidence_by_axis_ref,
        caveat_registry_path=pack.caveat_registry_ref,
    )
