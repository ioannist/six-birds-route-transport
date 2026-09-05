from __future__ import annotations

from collections import defaultdict

from ..schemas.event_package import EventPackageInstance
from ..schemas.observation_trace import ObservationTrace


def _normalize_counts(counts: dict[str, int]) -> dict[str, float]:
    total = sum(counts.values())
    if total <= 0:
        raise ValueError("outcome_counts must sum to a positive total")
    return {outcome: value / total for outcome, value in sorted(counts.items())}


def _normalize_probabilities(
    probabilities: dict[str, float],
    *,
    tolerance: float,
) -> dict[str, float]:
    total = sum(probabilities.values())
    if abs(total - 1.0) > tolerance:
        raise ValueError(
            f"outcome_probabilities must sum to 1 within tolerance; observed total {total}"
        )
    return {
        outcome: value / total if total else 0.0
        for outcome, value in sorted(probabilities.items())
    }


def extract_probe_signatures(
    traces: list[ObservationTrace],
    *,
    instance: EventPackageInstance,
    tolerance: float = 1e-9,
) -> dict[str, dict[str, dict[str, float]]]:
    if not traces:
        raise ValueError("at least one trace is required for SEC")

    event_ids = {event.event_id for event in instance.events}
    event_contexts = {event.event_id: event.context_id for event in instance.events}
    grouped: dict[
        tuple[str, str], list[tuple[str, dict[str, int] | dict[str, float]]]
    ] = defaultdict(list)

    for trace in traces:
        if trace.instance_id is not None and trace.instance_id != instance.instance_id:
            raise ValueError("trace instance_id must match the provided instance_id")
        for probe in trace.downstream_probes:
            if probe.event_id is None:
                raise ValueError("SEC downstream probes must carry event_id")
            if probe.event_id not in event_ids:
                raise ValueError(
                    f"unknown event_id '{probe.event_id}' in downstream probe"
                )
            if (
                probe.context_id is not None
                and probe.context_id != event_contexts[probe.event_id]
            ):
                raise ValueError(
                    "downstream probe context_id must match the referenced event context"
                )
            if probe.outcome_counts is None and probe.outcome_probabilities is None:
                raise ValueError(
                    "SEC downstream probes must carry outcome_counts or outcome_probabilities"
                )
            if probe.outcome_counts is not None:
                grouped[(probe.event_id, probe.probe_id)].append(
                    ("count", probe.outcome_counts)
                )
            elif probe.outcome_probabilities is not None:
                grouped[(probe.event_id, probe.probe_id)].append(
                    ("probability", probe.outcome_probabilities)
                )

    signatures: dict[str, dict[str, dict[str, float]]] = defaultdict(dict)
    for (event_id, probe_id), contributions in sorted(grouped.items()):
        modes = {mode for mode, _ in contributions}
        if len(modes) != 1:
            raise ValueError(
                f"probe group ({event_id}, {probe_id}) mixes count and probability inputs"
            )
        mode = next(iter(modes))
        if mode == "count":
            totals: dict[str, int] = defaultdict(int)
            for _, counts in contributions:
                assert isinstance(counts, dict)
                for outcome, value in counts.items():
                    totals[outcome] += int(value)
            signatures[event_id][probe_id] = _normalize_counts(dict(totals))
        else:
            normalized = [
                _normalize_probabilities(probabilities, tolerance=tolerance)
                for _, probabilities in contributions
            ]
            outcomes = sorted({outcome for item in normalized for outcome in item})
            signatures[event_id][probe_id] = {
                outcome: sum(item.get(outcome, 0.0) for item in normalized)
                / len(normalized)
                for outcome in outcomes
            }
    return dict(signatures)
