from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from sixbirds_event.discovery.models import DiscoveredEventGenerationThresholds
from sixbirds_event.discovery.shared_event_inference import (
    DEFAULT_SHARED_EVENT_INFERENCE_THRESHOLDS,
)
from sixbirds_event.provenance.models import PackageProvenance
from sixbirds_event.reporting.package_build_report import write_package_build_report
from sixbirds_event.schemas.common import SchemaKind
from sixbirds_event.schemas.event_package import EventPackageInstance
from sixbirds_event.schemas.result_note import ResultNote
from sixbirds_event.schemas.run_manifest import RunManifest
from sixbirds_event.validation import load_model, validate_payload


EXP100_BUNDLE = Path(
    "experiments/contracts/pica/pilot/exp100_multiseed/pica-export-bundle.json"
)
EXP100_FAMILY = Path(
    "experiments/instances/discovered/pica-exp100-multiseed-contexts/discovered-context-family.json"
)
EXP100_SKELETON = Path(
    "experiments/instances/discovered/pica-exp100-multiseed-contexts/event-package-skeleton.json"
)
PAIRMATCH_BUNDLE = Path(
    "experiments/contracts/pica/pilot/exp110_pairmatch/pica-export-bundle.json"
)
PAIRMATCH_FAMILY = Path(
    "experiments/instances/discovered/pica-exp110-pairmatch-contexts/discovered-context-family.json"
)
PAIRMATCH_SKELETON = Path(
    "experiments/instances/discovered/pica-exp110-pairmatch-contexts/event-package-skeleton.json"
)


def _build_pairmatch(tmp_path: Path):
    return write_package_build_report(
        family_path=PAIRMATCH_FAMILY,
        pica_bundle_path=PAIRMATCH_BUNDLE,
        skeleton_path=PAIRMATCH_SKELETON,
        category="search",
        label="build-package-pica-structural",
        seed=0,
        timestamp="2026-03-27T06:30:00Z",
        root=tmp_path,
        thresholds=DEFAULT_SHARED_EVENT_INFERENCE_THRESHOLDS,
        event_thresholds=DiscoveredEventGenerationThresholds(
            event_basis_mode="singleton_plus_small_unions",
            event_algebra_mode="full_powerset",
            max_full_powerset_atom_count=6,
            max_union_size=2,
            min_event_support_count=1,
            min_event_support_fraction=0.0,
        ),
    )


def test_probe_indistinguishability_signature_format_validates(tmp_path: Path) -> None:
    artifacts = _build_pairmatch(tmp_path)
    payload = json.loads((tmp_path / artifacts.signatures_path).read_text())
    result = validate_payload(
        payload,
        kind=SchemaKind.PROBE_INDISTINGUISHABILITY_SIGNATURE,
    )
    assert result.ok


def test_structural_primary_build_accepts_committed_pairmatch_case(
    tmp_path: Path,
) -> None:
    artifacts = _build_pairmatch(tmp_path)

    signatures = load_model(
        tmp_path / artifacts.signatures_path,
        kind=SchemaKind.PROBE_INDISTINGUISHABILITY_SIGNATURE,
    )
    candidates = load_model(
        tmp_path / artifacts.candidates_path,
        kind=SchemaKind.SHARED_EVENT_CANDIDATES,
    )
    event_package = load_model(
        tmp_path / artifacts.event_package_path,
        kind=SchemaKind.EVENT_PACKAGE_INSTANCE,
    )
    provenance = load_model(
        tmp_path / artifacts.provenance_path,
        kind=SchemaKind.PACKAGE_PROVENANCE,
    )
    result_note = load_model(
        tmp_path / artifacts.result_note_path,
        kind=SchemaKind.RESULT_NOTE,
    )
    manifest = load_model(
        tmp_path / artifacts.manifest_path,
        kind=SchemaKind.RUN_MANIFEST,
    )

    assert signatures is not None
    assert candidates is not None
    assert isinstance(event_package, EventPackageInstance)
    assert isinstance(provenance, PackageProvenance)
    assert isinstance(result_note, ResultNote)
    assert isinstance(manifest, RunManifest)

    assert candidates.inference_mode == "structural_primary"
    assert candidates.diagnostics_summary.structurally_valid_candidate_pair_count > 0
    assert candidates.diagnostics_summary.accepted_candidate_pair_count > 0
    accepted_rows = [row for row in candidates.candidate_rows if row.accepted]
    rejected_rows = [row for row in candidates.candidate_rows if not row.accepted]
    assert accepted_rows
    assert all(row.structural_match for row in accepted_rows)
    assert any(
        any(
            reason.startswith("probe_image_mismatch:")
            for reason in row.rejection_reasons
        )
        for row in rejected_rows
    )

    accepted_ids = [
        row.proposed_proposal_id for row in accepted_rows if row.proposed_proposal_id
    ]
    assert accepted_ids == [
        proposal.proposal_id for proposal in event_package.equality_proposals
    ]
    assert signatures.signature_rows
    assert all(entry.structural_valid for entry in signatures.signature_rows)

    proposal_notes = {
        entry.proposal_id: entry.notes for entry in provenance.proposal_entries
    }
    assert any(
        "inference_mode:structural_primary" in notes
        for notes in proposal_notes.values()
    )
    assert any(
        any(note.startswith("common_probe_id:") for note in notes)
        for notes in proposal_notes.values()
    )

    summary = json.loads((tmp_path / artifacts.summary_path).read_text())
    assert summary["inference_mode"] == "structural_primary"
    assert summary["structurally_valid_candidate_pair_count"] > 0
    assert summary["accepted_shared_event_proposal_count"] > 0
    assert summary["accepted_coarse_proposal_count"] == 0
    assert (
        summary["probe_indistinguishability_signatures_artifact"]
        == artifacts.signatures_path
    )

    note = (tmp_path / artifacts.note_path).read_text()
    assert "Structural rule" in note
    assert "Secondary statistical summary" in note
    assert "Probe-indistinguishability signatures" in note

    assert set(manifest.output_artifacts) == {
        "discovered_event_family",
        "event_algebra_coverage",
        "probe_indistinguishability_signatures",
        "shared_event_candidates",
        "event_package",
        "package_provenance",
        "package_build_summary",
        "note",
        "result_note",
    }


def test_exp100_multiseed_remains_honestly_uninformative_under_structural_primary(
    tmp_path: Path,
) -> None:
    artifacts = write_package_build_report(
        family_path=EXP100_FAMILY,
        pica_bundle_path=EXP100_BUNDLE,
        skeleton_path=EXP100_SKELETON,
        category="search",
        label="build-package-pica-structural-smoke",
        seed=0,
        timestamp="2026-03-27T06:00:00Z",
        root=tmp_path,
        thresholds=DEFAULT_SHARED_EVENT_INFERENCE_THRESHOLDS,
        event_thresholds=DiscoveredEventGenerationThresholds(
            event_basis_mode="singleton_plus_small_unions",
            event_algebra_mode="full_powerset",
            max_full_powerset_atom_count=6,
            max_union_size=2,
            min_event_support_count=1,
            min_event_support_fraction=0.0,
        ),
    )

    summary = json.loads((tmp_path / artifacts.summary_path).read_text())
    assert summary["structurally_valid_candidate_pair_count"] == 0
    assert summary["accepted_shared_event_proposal_count"] == 0


def test_cli_smoke_builds_structural_primary_pairmatch_package(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "sixbirds_event",
            "substrates",
            "build-event-package",
            PAIRMATCH_FAMILY.as_posix(),
            "--pica-bundle",
            PAIRMATCH_BUNDLE.as_posix(),
            "--skeleton",
            PAIRMATCH_SKELETON.as_posix(),
            "--category",
            "search",
            "--label",
            "build-package-pica-structural",
            "--event-algebra-mode",
            "full_powerset",
            "--inference-mode",
            "structural_primary",
            "--timestamp",
            "2026-03-27T06:30:00Z",
            "--root",
            str(tmp_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "probe_indistinguishability_signatures=" in result.stdout
    assert "structurally_valid_candidate_count=" in result.stdout
    assert "accepted_shared_event_proposal_count=" in result.stdout
    assert "accepted_coarse_proposal_count=" in result.stdout
    assert "accepted_shared_event_proposal_count=6" in result.stdout
