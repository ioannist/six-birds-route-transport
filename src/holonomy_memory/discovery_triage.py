from __future__ import annotations

import csv
import hashlib
import json
import random
from copy import deepcopy
from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from typing import Any

from .benchmarks import REPO_ROOT
from .core import load_route_transport_package_from_config
from .discovery import (
    DISCOVERY_LABELS,
    DiscoveryAtlas,
    DiscoveryCandidateRecord,
    DiscoveryRunArtifacts,
    _RealizedCandidate,
    _evaluate_realized_candidate,
    _realize_candidate,
    run_discovery_search,
)
from .schemas import RouteTransportPackageConfig
from .search_spaces import load_search_space, load_search_space_for_id
from .validation import load_json_file


DEFAULT_DISCOVERY_TRIAGE_SEARCH_ID = "cyclic_memory_small"
DEFAULT_PROXY_TRIAL_COUNT = 6


@dataclass(frozen=True)
class DiscoveryShortlistEntry:
    search_id: str
    candidate_id: str
    class_label: str
    primary_interface_id: str
    primary_witness_count: int
    primary_discrepancy_metric_value: Fraction
    primary_predictive_loop_score: Fraction
    robustness_proxy_fraction: Fraction
    selected_by_discrepancy: bool
    selected_by_predictive_loop: bool
    selected_by_robustness_proxy: bool
    evidence_reasons: tuple[str, ...]


@dataclass(frozen=True)
class DiscoveryShortlist:
    search_id: str
    seed: int
    atlas_path: Path
    class_counts: tuple[tuple[str, int], ...]
    top_by_discrepancy: tuple[DiscoveryShortlistEntry, ...]
    top_by_predictive_loop: tuple[DiscoveryShortlistEntry, ...]
    top_by_robustness_proxy: tuple[DiscoveryShortlistEntry, ...]
    combined_shortlist: tuple[DiscoveryShortlistEntry, ...]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class DiscoveryTriageArtifacts:
    search_id: str
    seed: int
    atlas_json_path: Path
    atlas_csv_path: Path
    atlas_note_path: Path
    shortlist_json_path: Path
    shortlist_csv_path: Path
    shortlist_note_path: Path
    shortlist: DiscoveryShortlist


def triage_discovery_candidates(
    *,
    search_id: str | None = None,
    search_path: str | Path | None = None,
    seed: int = 0,
    output_root: str | Path | None = None,
    top_k: int = 3,
    proxy_trial_count: int = DEFAULT_PROXY_TRIAL_COUNT,
    allow_all_flat: bool = False,
) -> DiscoveryTriageArtifacts:
    resolved_search_id = search_id or DEFAULT_DISCOVERY_TRIAGE_SEARCH_ID
    discovery_artifacts = run_discovery_search(
        search_id=resolved_search_id if search_path is None else None,
        search_path=search_path,
        seed=seed,
        output_root=output_root,
    )
    atlas = discovery_artifacts.atlas
    if not allow_all_flat:
        _validate_atlas_for_triage(atlas)

    if search_path is not None:
        search_space = load_search_space(search_path)
    else:
        search_space = load_search_space_for_id(resolved_search_id)

    entries = tuple(
        _build_shortlist_entry(
            atlas=atlas,
            record=record,
            search_space=search_space,
            seed=seed,
            proxy_trial_count=proxy_trial_count,
        )
        for record in atlas.candidate_records
    )

    top_by_discrepancy = _select_top_k(
        (
            entry
            for entry in entries
            if entry.primary_witness_count > 0
        ),
        key_name="discrepancy",
        top_k=top_k,
    )
    top_by_predictive_loop = _select_top_k(
        (
            entry
            for entry in entries
            if entry.primary_predictive_loop_score > 0
        ),
        key_name="predictive_loop",
        top_k=top_k,
    )
    top_by_robustness_proxy = _select_top_k(
        (
            entry
            for entry in entries
            if entry.class_label != "flat"
        ),
        key_name="robustness_proxy",
        top_k=top_k,
    )
    combined_shortlist = _combine_shortlist_lists(
        top_by_discrepancy,
        top_by_predictive_loop,
        top_by_robustness_proxy,
    )
    shortlist = DiscoveryShortlist(
        search_id=atlas.search_id,
        seed=seed,
        atlas_path=discovery_artifacts.json_atlas_path,
        class_counts=tuple((label, dict(atlas.class_counts).get(label, 0)) for label in DISCOVERY_LABELS),
        top_by_discrepancy=top_by_discrepancy,
        top_by_predictive_loop=top_by_predictive_loop,
        top_by_robustness_proxy=top_by_robustness_proxy,
        combined_shortlist=combined_shortlist,
        warnings=atlas.warnings,
    )
    return write_discovery_shortlist(
        shortlist=shortlist,
        atlas_artifacts=discovery_artifacts,
        output_root=output_root,
    )


def write_discovery_shortlist(
    *,
    shortlist: DiscoveryShortlist,
    atlas_artifacts: DiscoveryRunArtifacts,
    output_root: str | Path | None = None,
) -> DiscoveryTriageArtifacts:
    root = Path(output_root) if output_root is not None else REPO_ROOT
    shortlist_json_path = (
        root / "artifacts" / "results" / "discovery" / f"{shortlist.search_id}.shortlist.json"
    )
    shortlist_csv_path = (
        root / "artifacts" / "tables" / f"discovery_{shortlist.search_id}_shortlist.csv"
    )
    shortlist_note_path = root / "docs" / "results" / f"{shortlist.search_id}.shortlist.md"
    shortlist_json_path.parent.mkdir(parents=True, exist_ok=True)
    shortlist_csv_path.parent.mkdir(parents=True, exist_ok=True)
    shortlist_note_path.parent.mkdir(parents=True, exist_ok=True)

    shortlist_json_path.write_text(
        json.dumps(_shortlist_payload(shortlist, atlas_artifacts), indent=2) + "\n",
        encoding="utf-8",
    )
    _write_shortlist_csv(shortlist, shortlist_csv_path)
    shortlist_note_path.write_text(
        _build_shortlist_note(
            shortlist=shortlist,
            atlas_artifacts=atlas_artifacts,
            shortlist_json_path=shortlist_json_path,
            shortlist_csv_path=shortlist_csv_path,
            shortlist_note_path=shortlist_note_path,
        ),
        encoding="utf-8",
    )
    return DiscoveryTriageArtifacts(
        search_id=shortlist.search_id,
        seed=shortlist.seed,
        atlas_json_path=atlas_artifacts.json_atlas_path,
        atlas_csv_path=atlas_artifacts.csv_summary_path,
        atlas_note_path=atlas_artifacts.summary_note_path,
        shortlist_json_path=shortlist_json_path,
        shortlist_csv_path=shortlist_csv_path,
        shortlist_note_path=shortlist_note_path,
        shortlist=shortlist,
    )


def compute_discovery_robustness_proxy(
    *,
    record: DiscoveryCandidateRecord,
    search_space: Any,
    seed: int,
    proxy_trial_count: int = DEFAULT_PROXY_TRIAL_COUNT,
) -> Fraction:
    realized = _realize_candidate(record.candidate_spec, search_space)
    pass_count = 0
    for trial_index in range(proxy_trial_count):
        trial_seed = _derive_proxy_trial_seed(
            search_id=record.candidate_spec.search_id,
            candidate_id=record.candidate_spec.candidate_id,
            base_seed=seed,
            trial_index=trial_index,
        )
        perturbed_config = _apply_proxy_trial(realized, record, trial_seed=trial_seed)
        perturbed_realized = _RealizedCandidate(
            spec=realized.spec,
            config=RouteTransportPackageConfig.model_validate(perturbed_config),
            package=load_route_transport_package_from_config(
                RouteTransportPackageConfig.model_validate(perturbed_config)
            ),
            forward_continuation_ids=realized.forward_continuation_ids,
        )
        perturbed_record = _evaluate_realized_candidate(perturbed_realized)
        if _proxy_predicate_passes(record.candidate_label, perturbed_record):
            pass_count += 1
    return Fraction(pass_count, proxy_trial_count)


def _validate_atlas_for_triage(atlas: DiscoveryAtlas) -> None:
    if atlas.evaluated_candidate_count <= 0:
        raise ValueError(f"search {atlas.search_id} evaluated zero candidates")
    if not any(
        _primary_metrics(record).witness_count > 0 for record in atlas.candidate_records
    ):
        raise ValueError(
            f"search {atlas.search_id} did not produce any candidate with witness_count > 0"
        )
    if not any(
        _primary_metrics(record).predictive_loop_score > 0
        for record in atlas.candidate_records
    ):
        raise ValueError(
            f"search {atlas.search_id} did not produce any candidate with predictive loop score > 0"
        )


def _build_shortlist_entry(
    *,
    atlas: DiscoveryAtlas,
    record: DiscoveryCandidateRecord,
    search_space: Any,
    seed: int,
    proxy_trial_count: int,
) -> DiscoveryShortlistEntry:
    primary_metrics = _primary_metrics(record)
    proxy_fraction = compute_discovery_robustness_proxy(
        record=record,
        search_space=search_space,
        seed=seed,
        proxy_trial_count=proxy_trial_count,
    )
    evidence_reasons = (
        f"class={record.candidate_label}",
        f"primary={record.primary_interface_id}",
        f"witnesses={primary_metrics.witness_count}",
        f"discrepancy={_fraction_string(primary_metrics.discrepancy_metric_value)}",
        f"predictive_loop={_fraction_string(primary_metrics.predictive_loop_score)}",
        f"robustness_proxy={_fraction_string(proxy_fraction)}",
    )
    return DiscoveryShortlistEntry(
        search_id=atlas.search_id,
        candidate_id=record.candidate_spec.candidate_id,
        class_label=record.candidate_label,
        primary_interface_id=record.primary_interface_id,
        primary_witness_count=primary_metrics.witness_count,
        primary_discrepancy_metric_value=primary_metrics.discrepancy_metric_value,
        primary_predictive_loop_score=primary_metrics.predictive_loop_score,
        robustness_proxy_fraction=proxy_fraction,
        selected_by_discrepancy=False,
        selected_by_predictive_loop=False,
        selected_by_robustness_proxy=False,
        evidence_reasons=evidence_reasons,
    )


def _select_top_k(
    entries: Any,
    *,
    key_name: str,
    top_k: int,
) -> tuple[DiscoveryShortlistEntry, ...]:
    entry_list = list(entries)
    if key_name == "discrepancy":
        sorted_entries = sorted(
            entry_list,
            key=lambda entry: (
                -float(entry.primary_discrepancy_metric_value),
                entry.candidate_id,
            ),
        )
        return tuple(
            _with_selection_flag(entry, "discrepancy")
            for entry in sorted_entries[:top_k]
        )
    if key_name == "predictive_loop":
        sorted_entries = sorted(
            entry_list,
            key=lambda entry: (
                -float(entry.primary_predictive_loop_score),
                entry.candidate_id,
            ),
        )
        return tuple(
            _with_selection_flag(entry, "predictive_loop")
            for entry in sorted_entries[:top_k]
        )
    if key_name == "robustness_proxy":
        sorted_entries = sorted(
            entry_list,
            key=lambda entry: (
                -float(entry.robustness_proxy_fraction),
                entry.candidate_id,
            ),
        )
        return tuple(
            _with_selection_flag(entry, "robustness_proxy")
            for entry in sorted_entries[:top_k]
        )
    raise ValueError(f"unsupported shortlist key: {key_name}")


def _with_selection_flag(
    entry: DiscoveryShortlistEntry,
    key_name: str,
) -> DiscoveryShortlistEntry:
    return DiscoveryShortlistEntry(
        search_id=entry.search_id,
        candidate_id=entry.candidate_id,
        class_label=entry.class_label,
        primary_interface_id=entry.primary_interface_id,
        primary_witness_count=entry.primary_witness_count,
        primary_discrepancy_metric_value=entry.primary_discrepancy_metric_value,
        primary_predictive_loop_score=entry.primary_predictive_loop_score,
        robustness_proxy_fraction=entry.robustness_proxy_fraction,
        selected_by_discrepancy=entry.selected_by_discrepancy or key_name == "discrepancy",
        selected_by_predictive_loop=entry.selected_by_predictive_loop or key_name == "predictive_loop",
        selected_by_robustness_proxy=entry.selected_by_robustness_proxy or key_name == "robustness_proxy",
        evidence_reasons=entry.evidence_reasons,
    )


def _combine_shortlist_lists(
    *lists: tuple[DiscoveryShortlistEntry, ...],
) -> tuple[DiscoveryShortlistEntry, ...]:
    combined: dict[str, DiscoveryShortlistEntry] = {}
    ordered_ids: list[str] = []
    for entries in lists:
        for entry in entries:
            existing = combined.get(entry.candidate_id)
            if existing is None:
                combined[entry.candidate_id] = entry
                ordered_ids.append(entry.candidate_id)
                continue
            combined[entry.candidate_id] = DiscoveryShortlistEntry(
                search_id=entry.search_id,
                candidate_id=entry.candidate_id,
                class_label=entry.class_label,
                primary_interface_id=entry.primary_interface_id,
                primary_witness_count=entry.primary_witness_count,
                primary_discrepancy_metric_value=entry.primary_discrepancy_metric_value,
                primary_predictive_loop_score=entry.primary_predictive_loop_score,
                robustness_proxy_fraction=entry.robustness_proxy_fraction,
                selected_by_discrepancy=(
                    existing.selected_by_discrepancy or entry.selected_by_discrepancy
                ),
                selected_by_predictive_loop=(
                    existing.selected_by_predictive_loop or entry.selected_by_predictive_loop
                ),
                selected_by_robustness_proxy=(
                    existing.selected_by_robustness_proxy or entry.selected_by_robustness_proxy
                ),
                evidence_reasons=existing.evidence_reasons,
            )
    return tuple(combined[candidate_id] for candidate_id in ordered_ids)


def _primary_metrics(record: DiscoveryCandidateRecord) -> Any:
    return next(
        metrics
        for metrics in record.interface_metrics
        if metrics.interface_id == record.primary_interface_id
    )


def _apply_proxy_trial(
    realized: _RealizedCandidate,
    record: DiscoveryCandidateRecord,
    *,
    trial_seed: int,
) -> dict[str, object]:
    root = deepcopy(realized.config.model_dump(mode="python"))
    targets = _build_proxy_targets(realized, record)
    for target_index, target in enumerate(targets):
        _apply_proxy_mapping_shift(
            root,
            mapping_path=target["mapping_path"],
            donor_key=target["donor_key"],
            receiver_key=target["receiver_key"],
            trial_seed=trial_seed,
            target_index=target_index,
            magnitude=target["magnitude"],
            radius=target["radius"],
        )
    return root


def _build_proxy_targets(
    realized: _RealizedCandidate,
    record: DiscoveryCandidateRecord,
) -> tuple[dict[str, Any], ...]:
    targets: list[dict[str, Any]] = []
    config = realized.config.model_dump(mode="python")
    primary_interface_id = record.primary_interface_id
    support_labels = tuple(config["support"]["visible_support_labels"])

    event_package_index = next(
        index
        for index, package in enumerate(config["event_packages"])
        if package["interface_id"] == primary_interface_id
    )
    event_weights = config["event_packages"][event_package_index]["events"][0]["weights"]
    event_donor = max(event_weights, key=event_weights.get)
    event_receiver = next(label for label in support_labels if label != event_donor)
    targets.append(
        {
            "mapping_path": f"event_packages[{event_package_index}].events[0].weights",
            "donor_key": event_donor,
            "receiver_key": event_receiver,
            "magnitude": 0.1,
            "radius": 0.1,
        }
    )

    forward_continuation = next(
        (
            continuation
            for continuation in config["continuations"]
            if continuation["source_interface_id"] == primary_interface_id
            and continuation["target_interface_id"] != primary_interface_id
        ),
        None,
    )
    if forward_continuation is not None:
        source_state = sorted(forward_continuation["kernel"])[0]
        donor_key = max(
            forward_continuation["kernel"][source_state],
            key=forward_continuation["kernel"][source_state].get,
        )
        alt_target = next(
            state_id
            for state_id in config["state_space"]["internal_state_ids"]
            if state_id != donor_key
        )
        targets.append(
            {
                "mapping_path": (
                    "continuations"
                    f"[{_continuation_index(config, forward_continuation['continuation_id'])}]"
                    f".kernel.{source_state}"
                ),
                "donor_key": donor_key,
                "receiver_key": alt_target,
                "magnitude": 0.1,
                "radius": 0.1,
            }
        )

    if record.loop_action_evidence is not None:
        loop = next(
            item
            for item in config["loops"]
            if item["loop_id"] == record.loop_action_evidence.loop_id
        )
        continuation_index = _continuation_index(config, loop["continuation_id"])
        continuation = config["continuations"][continuation_index]
        source_state = sorted(continuation["kernel"])[0]
        donor_key = max(
            continuation["kernel"][source_state],
            key=continuation["kernel"][source_state].get,
        )
        alt_target = next(
            state_id
            for state_id in config["state_space"]["internal_state_ids"]
            if state_id != donor_key
        )
        targets.append(
            {
                "mapping_path": f"continuations[{continuation_index}].kernel.{source_state}",
                "donor_key": donor_key,
                "receiver_key": alt_target,
                "magnitude": 0.1,
                "radius": 0.1,
            }
        )
    return tuple(targets)


def _continuation_index(config: dict[str, Any], continuation_id: str) -> int:
    return next(
        index
        for index, continuation in enumerate(config["continuations"])
        if continuation["continuation_id"] == continuation_id
    )


def _apply_proxy_mapping_shift(
    root: dict[str, object],
    *,
    mapping_path: str,
    donor_key: str,
    receiver_key: str,
    trial_seed: int,
    target_index: int,
    magnitude: float,
    radius: float,
) -> None:
    tokens = _tokenize_target_path(mapping_path)
    container: Any = root
    for token in tokens:
        container = container[token]
    if not isinstance(container, dict):
        raise TypeError(f"target {mapping_path} does not resolve to a mapping")
    donor_value = Decimal(str(container.get(donor_key, 0.0)))
    receiver_value = Decimal(str(container.get(receiver_key, 0.0)))
    delta = _draw_nonnegative_lattice_delta(
        magnitude=magnitude,
        radius=radius,
        trial_seed=trial_seed,
        target_index=target_index,
    )
    shift = min(donor_value, delta)
    container[donor_key] = float(donor_value - shift)
    container[receiver_key] = float(receiver_value + shift)


def _proxy_predicate_passes(
    class_label: str,
    record: DiscoveryCandidateRecord,
) -> bool:
    if class_label == "flat":
        return all(
            metrics.witness_count == 0
            and metrics.discrepancy_metric_value == 0
            and metrics.predictive_loop_score == 0
            for metrics in record.interface_metrics
        )
    if class_label == "dissipative":
        earliest = record.interface_metrics[0]
        return (
            earliest.witness_count > 0
            and earliest.discrepancy_metric_value > 0
            and any(
                metrics.witness_count == 0
                and metrics.discrepancy_metric_value == 0
                and metrics.current_quotient_size == metrics.predictive_quotient_size
                and metrics.max_fiber_size == 1
                for metrics in record.interface_metrics[1:]
            )
            and record.transport_collapse_evidence is not None
        )
    primary = _primary_metrics(record)
    return (
        primary.witness_count > 0
        and primary.discrepancy_metric_value > 0
        and primary.current_loop_score == 0
        and primary.predictive_loop_score > 0
    )


def _shortlist_payload(
    shortlist: DiscoveryShortlist,
    atlas_artifacts: DiscoveryRunArtifacts,
) -> dict[str, Any]:
    return {
        "search_id": shortlist.search_id,
        "seed": shortlist.seed,
        "atlas_json_path": _relative_string(atlas_artifacts.json_atlas_path),
        "atlas_csv_path": _relative_string(atlas_artifacts.csv_summary_path),
        "atlas_note_path": _relative_string(atlas_artifacts.summary_note_path),
        "class_counts": {label: count for label, count in shortlist.class_counts},
        "top_by_discrepancy": [_entry_payload(entry) for entry in shortlist.top_by_discrepancy],
        "top_by_predictive_loop": [
            _entry_payload(entry) for entry in shortlist.top_by_predictive_loop
        ],
        "top_by_robustness_proxy": [
            _entry_payload(entry) for entry in shortlist.top_by_robustness_proxy
        ],
        "combined_shortlist": [_entry_payload(entry) for entry in shortlist.combined_shortlist],
        "warnings": list(shortlist.warnings),
    }


def _entry_payload(entry: DiscoveryShortlistEntry) -> dict[str, Any]:
    return {
        "search_id": entry.search_id,
        "candidate_id": entry.candidate_id,
        "class_label": entry.class_label,
        "primary_interface_id": entry.primary_interface_id,
        "primary_witness_count": entry.primary_witness_count,
        "primary_discrepancy_metric_value": float(entry.primary_discrepancy_metric_value),
        "primary_discrepancy_metric_value_exact": _fraction_string(
            entry.primary_discrepancy_metric_value
        ),
        "primary_predictive_loop_score": float(entry.primary_predictive_loop_score),
        "primary_predictive_loop_score_exact": _fraction_string(
            entry.primary_predictive_loop_score
        ),
        "robustness_proxy_fraction": float(entry.robustness_proxy_fraction),
        "robustness_proxy_fraction_exact": _fraction_string(entry.robustness_proxy_fraction),
        "selected_by_discrepancy": entry.selected_by_discrepancy,
        "selected_by_predictive_loop": entry.selected_by_predictive_loop,
        "selected_by_robustness_proxy": entry.selected_by_robustness_proxy,
        "evidence_reasons": list(entry.evidence_reasons),
    }


def _write_shortlist_csv(shortlist: DiscoveryShortlist, path: Path) -> None:
    fieldnames = [
        "search_id",
        "candidate_id",
        "class_label",
        "primary_interface_id",
        "primary_witness_count",
        "primary_discrepancy_metric_value",
        "primary_predictive_loop_score",
        "robustness_proxy_fraction",
        "selected_by_discrepancy",
        "selected_by_predictive_loop",
        "selected_by_robustness_proxy",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for entry in shortlist.combined_shortlist:
            writer.writerow(
                {
                    "search_id": entry.search_id,
                    "candidate_id": entry.candidate_id,
                    "class_label": entry.class_label,
                    "primary_interface_id": entry.primary_interface_id,
                    "primary_witness_count": entry.primary_witness_count,
                    "primary_discrepancy_metric_value": float(
                        entry.primary_discrepancy_metric_value
                    ),
                    "primary_predictive_loop_score": float(
                        entry.primary_predictive_loop_score
                    ),
                    "robustness_proxy_fraction": float(entry.robustness_proxy_fraction),
                    "selected_by_discrepancy": str(entry.selected_by_discrepancy).lower(),
                    "selected_by_predictive_loop": str(
                        entry.selected_by_predictive_loop
                    ).lower(),
                    "selected_by_robustness_proxy": str(
                        entry.selected_by_robustness_proxy
                    ).lower(),
                }
            )


def _build_shortlist_note(
    *,
    shortlist: DiscoveryShortlist,
    atlas_artifacts: DiscoveryRunArtifacts,
    shortlist_json_path: Path,
    shortlist_csv_path: Path,
    shortlist_note_path: Path,
) -> str:
    lines = [
        f"# Discovery Shortlist: {shortlist.search_id}",
        "",
        f"- search_id: {shortlist.search_id}",
        f"- seed: {shortlist.seed}",
        f"- atlas_json_path: {_relative_string(atlas_artifacts.json_atlas_path)}",
        f"- atlas_csv_path: {_relative_string(atlas_artifacts.csv_summary_path)}",
        f"- atlas_note_path: {_relative_string(atlas_artifacts.summary_note_path)}",
        f"- shortlist_json_path: {_relative_string(shortlist_json_path)}",
        f"- shortlist_csv_path: {_relative_string(shortlist_csv_path)}",
        f"- shortlist_note_path: {_relative_string(shortlist_note_path)}",
        "- class_counts:",
    ]
    for label, count in shortlist.class_counts:
        lines.append(f"  - {label}: {count}")
    lines.append(
        f"- evaluated_candidate_count: {sum(count for _, count in shortlist.class_counts)}"
    )
    lines.extend(
        [
            "",
            "## Top By Discrepancy",
            "",
            *_entry_lines(shortlist.top_by_discrepancy),
            "",
            "## Top By Predictive Loop",
            "",
            *_entry_lines(shortlist.top_by_predictive_loop),
            "",
            "## Top By Robustness Proxy",
            "",
            *_entry_lines(shortlist.top_by_robustness_proxy),
            "",
            "## Combined Shortlist",
            "",
            *_entry_lines(shortlist.combined_shortlist),
            "",
            "## Conclusion",
            "",
        ]
    )
    if shortlist.combined_shortlist:
        lines.append(
            "- Follow-up priority stays with the first coherent candidates that remain tied on discrepancy, predictive loop score, and proxy robustness; tie-break is candidate id."
        )
    else:
        lines.append("- No follow-up candidates met the shortlist criteria.")
    if shortlist.warnings:
        lines.extend(["", "## Warnings", ""])
        for warning in shortlist.warnings:
            lines.append(f"- {warning}")
    return "\n".join(lines) + "\n"


def _entry_lines(entries: tuple[DiscoveryShortlistEntry, ...]) -> list[str]:
    if not entries:
        return ["- none"]
    return [
        (
            f"- {entry.candidate_id}: {entry.class_label}, "
            f"primary={entry.primary_interface_id}, "
            f"witnesses={entry.primary_witness_count}, "
            f"discrepancy={_fraction_string(entry.primary_discrepancy_metric_value)}, "
            f"predictive_loop={_fraction_string(entry.primary_predictive_loop_score)}, "
            f"proxy={_fraction_string(entry.robustness_proxy_fraction)}"
        )
        for entry in entries
    ]


def _derive_proxy_trial_seed(
    *,
    search_id: str,
    candidate_id: str,
    base_seed: int,
    trial_index: int,
) -> int:
    digest = hashlib.sha256(
        f"{search_id}|{candidate_id}|{base_seed}|{trial_index}".encode("utf-8")
    ).hexdigest()
    return int(digest[:16], 16)


def _draw_nonnegative_lattice_delta(
    *,
    magnitude: float,
    radius: float,
    trial_seed: int,
    target_index: int,
) -> Decimal:
    step = Decimal(str(magnitude))
    max_radius = Decimal(str(radius))
    step_count = int(max_radius / step)
    lattice = [Decimal(index) * step for index in range(0, step_count + 1)]
    rng = random.Random(trial_seed + target_index)
    return lattice[rng.randrange(len(lattice))]


def _tokenize_target_path(path: str) -> tuple[str | int, ...]:
    tokens: list[str | int] = []
    buffer = ""
    index = 0
    while index < len(path):
        character = path[index]
        if character == ".":
            if buffer:
                tokens.append(buffer)
                buffer = ""
            index += 1
            continue
        if character == "[":
            if buffer:
                tokens.append(buffer)
                buffer = ""
            end_index = path.index("]", index)
            tokens.append(int(path[index + 1 : end_index]))
            index = end_index + 1
            continue
        buffer += character
        index += 1
    if buffer:
        tokens.append(buffer)
    return tuple(tokens)


def _relative_string(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _fraction_string(value: Fraction) -> str:
    if value.denominator == 1:
        return str(value.numerator)
    return f"{value.numerator}/{value.denominator}"


def load_discovery_shortlist(path: str | Path) -> dict[str, Any]:
    return load_json_file(path)
