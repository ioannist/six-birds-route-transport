from __future__ import annotations

from dataclasses import dataclass

from .models import (
    AcceptedContext,
    DiscoveredEventKind,
    ProbeIndistinguishabilitySignatureEntry,
)


@dataclass(slots=True)
class ComputedProbeSignature:
    entry: ProbeIndistinguishabilitySignatureEntry
    support_counts: dict[str, int]
    distribution: dict[str, float]


def classify_probe_image_event_kind(
    probe_image_atom_ids: list[str],
    *,
    probe_context: AcceptedContext,
) -> DiscoveredEventKind:
    if not probe_image_atom_ids:
        return "empty"
    if len(probe_image_atom_ids) == len(probe_context.atomic_outcomes):
        return "full"
    if len(probe_image_atom_ids) == 1:
        return "singleton"
    return "proper_coarse"
