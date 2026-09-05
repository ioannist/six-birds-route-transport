from __future__ import annotations

from pathlib import Path

from ..schemas.event_package import EventPackageInstance
from ..substrates.run_trace import SubstrateRun
from .event_algebra import generate_context_event_context
from .models import (
    DiscoveredEventFamily,
    DiscoveredEventFamilySummary,
    DiscoveredEventGenerationThresholds,
    DiscoveredContextFamily,
)


def load_discovered_event_family(path: str | Path) -> DiscoveredEventFamily:
    from ..validation import load_model

    model = load_model(path, kind="discovered-event-family")
    assert isinstance(model, DiscoveredEventFamily)
    return model


def _singleton_event_id(context_id: str, outcome_id: str) -> str:
    return f"event_{context_id}_{outcome_id}"


def _coarse_event_id(context_id: str, atom_ids: list[str]) -> str:
    return f"event_{context_id}__union__{'__'.join(atom_ids)}"


def _event_lookup_from_skeleton(
    skeleton: EventPackageInstance | None,
) -> dict[tuple[str, tuple[str, ...]], str]:
    if skeleton is None:
        return {}
    lookup: dict[tuple[str, tuple[str, ...]], str] = {}
    for event in skeleton.events:
        lookup[(event.context_id, tuple(sorted(event.atom_ids)))] = event.event_id
    return lookup


def _event_id_for_atoms(
    *,
    context_id: str,
    atom_ids: list[str],
    event_lookup: dict[tuple[str, tuple[str, ...]], str],
) -> str:
    atom_key = tuple(sorted(atom_ids))
    if len(atom_ids) == 1:
        return event_lookup.get(
            (context_id, atom_key),
            _singleton_event_id(context_id, atom_ids[0]),
        )
    return event_lookup.get(
        (context_id, atom_key), _coarse_event_id(context_id, atom_ids)
    )


def discover_event_family(
    family: DiscoveredContextFamily,
    runs: list[SubstrateRun],
    *,
    thresholds: DiscoveredEventGenerationThresholds,
    event_family_id: str,
    source_discovered_context_family_artifact: str,
    source_run_artifacts: list[str],
    skeleton: EventPackageInstance | None = None,
    built_event_package_artifact: str | None = None,
) -> DiscoveredEventFamily:
    event_lookup = _event_lookup_from_skeleton(skeleton)
    context_payloads = []
    accepted_coarse_event_ids: list[str] = []
    total_event_count = 0
    generated_empty_event_count = 0
    generated_singleton_event_count = 0
    generated_proper_coarse_event_count = 0
    generated_full_event_count = 0
    match_eligible_event_count = 0
    accepted_singleton_event_count = 0
    accepted_coarse_event_count = 0
    rejected_coarse_event_count = 0

    for context in family.accepted_contexts:
        context_payload = generate_context_event_context(
            context=context,
            thresholds=thresholds,
            event_lookup=event_lookup,
        )
        context_payloads.append(context_payload)
        total_event_count += len(context_payload.events)
        generated_empty_event_count += sum(
            1
            for event in context_payload.events
            if event.accepted and event.event_kind == "empty"
        )
        generated_singleton_event_count += sum(
            1
            for event in context_payload.events
            if event.accepted and event.event_kind == "singleton"
        )
        generated_proper_coarse_event_count += sum(
            1
            for event in context_payload.events
            if event.accepted and event.event_kind == "proper_coarse"
        )
        generated_full_event_count += sum(
            1
            for event in context_payload.events
            if event.accepted and event.event_kind == "full"
        )
        match_eligible_event_count += sum(
            1
            for event in context_payload.events
            if event.accepted and event.match_eligible
        )
        accepted_singleton_event_count += sum(
            1
            for event in context_payload.events
            if event.accepted and event.event_kind == "singleton"
        )
        accepted_coarse_event_count += sum(
            1
            for event in context_payload.events
            if event.accepted and event.event_kind == "proper_coarse"
        )
        rejected_coarse_event_count += sum(
            1
            for event in context_payload.events
            if not event.accepted and event.event_kind == "proper_coarse"
        )
        accepted_coarse_event_ids.extend(
            event.event_id
            for event in context_payload.events
            if event.accepted and event.event_kind == "proper_coarse"
        )

    return DiscoveredEventFamily(
        event_family_format_version="discovered-event-family.v1",
        event_family_id=event_family_id,
        source_discovered_context_family_artifact=source_discovered_context_family_artifact,
        source_run_artifacts=source_run_artifacts,
        source_mode=family.source_mode,
        source_bundle_artifact=family.source_bundle_artifact,
        thresholds=thresholds,
        contexts=context_payloads,
        diagnostics_summary=DiscoveredEventFamilySummary(
            total_event_count=total_event_count,
            generated_empty_event_count=generated_empty_event_count,
            generated_singleton_event_count=generated_singleton_event_count,
            generated_proper_coarse_event_count=generated_proper_coarse_event_count,
            generated_full_event_count=generated_full_event_count,
            match_eligible_event_count=match_eligible_event_count,
            accepted_singleton_event_count=accepted_singleton_event_count,
            accepted_coarse_event_count=accepted_coarse_event_count,
            rejected_coarse_event_count=rejected_coarse_event_count,
            accepted_proper_coarse_event_ids=accepted_coarse_event_ids,
        ),
        built_event_package_artifact=built_event_package_artifact,
        metadata={"observable_only": True},
    )
