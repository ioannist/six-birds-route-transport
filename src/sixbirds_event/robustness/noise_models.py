from __future__ import annotations

import hashlib
import json
import random
from collections import defaultdict

from ..schemas.event_package import EventPackageInstance
from ..schemas.observation_trace import (
    DownstreamProbe,
    Observation,
    ObservationTrace,
    RepeatedReadSequence,
    RouteObservation,
)


def _seed_from_parts(base_seed: int, *parts: object) -> int:
    payload = json.dumps([base_seed, *parts], sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(payload.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def _normalize_distribution(values: dict[str, float]) -> dict[str, float]:
    total = sum(values.values())
    if total <= 0:
        raise ValueError("distribution total must be positive")
    return {key: values[key] / total for key in sorted(values)}


def _jitter_distribution(
    support: list[str],
    *,
    base_seed: int,
    parts: tuple[object, ...],
) -> dict[str, float]:
    rng = random.Random(_seed_from_parts(base_seed, *parts))
    weights = {outcome: rng.random() + 1e-9 for outcome in support}
    return _normalize_distribution(weights)


def _mix_distribution(
    baseline: dict[str, float],
    *,
    noise_level: float,
    base_seed: int,
    parts: tuple[object, ...],
) -> dict[str, float]:
    if noise_level <= 0:
        return dict(sorted(baseline.items()))
    support = sorted(baseline)
    jitter = _jitter_distribution(support, base_seed=base_seed, parts=parts)
    mixed = {
        outcome: (1.0 - noise_level) * baseline[outcome] + noise_level * jitter[outcome]
        for outcome in support
    }
    return _normalize_distribution(mixed)


def _observation_support(
    trace: ObservationTrace,
) -> dict[str, list[Observation]]:
    grouped: dict[str, list[Observation]] = defaultdict(list)
    for observation in trace.observations:
        grouped[observation.context_id].append(observation)
    return dict(grouped)


def _observation_distribution(observations: list[Observation]) -> dict[str, float]:
    raw: dict[str, float] = {}
    for observation in observations:
        key = "|".join(observation.atom_ids)
        if observation.count is not None:
            raw[key] = float(observation.count)
        elif observation.probability is not None:
            raw[key] = observation.probability
        else:
            raise ValueError("observation must carry count or probability")
    return _normalize_distribution(raw)


def make_noisy_stat_trace(
    trace: ObservationTrace,
    *,
    noise_level: float,
    base_seed: int,
    target_id: str,
) -> ObservationTrace:
    grouped = _observation_support(trace)
    noised_observations: list[Observation] = []
    for context_id, observations in sorted(grouped.items()):
        baseline = _observation_distribution(observations)
        mixed = _mix_distribution(
            baseline,
            noise_level=noise_level,
            base_seed=base_seed,
            parts=(target_id, "stat", context_id, noise_level),
        )
        for observation in observations:
            key = "|".join(observation.atom_ids)
            noised_observations.append(
                observation.model_copy(
                    update={
                        "count": None,
                        "probability": mixed[key],
                        "status": "noised_probability",
                    }
                )
            )
    return trace.model_copy(
        update={
            "trace_id": f"{trace.trace_id}__noise_{noise_level:.2f}",
            "observations": noised_observations,
            "metadata": {
                **trace.metadata,
                "noise_level": noise_level,
                "noise_model": "independent_jitter_mix_v1",
            },
        }
    )


def make_noisy_sec_trace(
    trace: ObservationTrace,
    *,
    noise_level: float,
    base_seed: int,
    target_id: str,
) -> ObservationTrace:
    noised_probes: list[DownstreamProbe] = []
    for probe in trace.downstream_probes:
        baseline_raw = (
            {key: float(value) for key, value in probe.outcome_counts.items()}
            if probe.outcome_counts is not None
            else dict(probe.outcome_probabilities or {})
        )
        baseline = _normalize_distribution(baseline_raw)
        mixed = _mix_distribution(
            baseline,
            noise_level=noise_level,
            base_seed=base_seed,
            parts=(
                target_id,
                "sec",
                probe.event_id,
                probe.probe_id,
                noise_level,
            ),
        )
        noised_probes.append(
            probe.model_copy(
                update={
                    "outcome_counts": None,
                    "outcome_probabilities": mixed,
                }
            )
        )
    return trace.model_copy(
        update={
            "trace_id": f"{trace.trace_id}__noise_{noise_level:.2f}",
            "downstream_probes": noised_probes,
            "metadata": {
                **trace.metadata,
                "noise_level": noise_level,
                "noise_model": "independent_jitter_mix_v1",
            },
        }
    )


def make_noisy_rm_trace(
    trace: ObservationTrace,
    *,
    noise_level: float,
    base_seed: int,
    target_id: str,
) -> ObservationTrace:
    noised_routes: list[RouteObservation] = []
    for route in trace.route_observations:
        baseline_raw = (
            {key: float(value) for key, value in route.outcome_counts.items()}
            if route.outcome_counts is not None
            else dict(route.outcome_probabilities or {})
        )
        baseline = _normalize_distribution(baseline_raw)
        mixed = _mix_distribution(
            baseline,
            noise_level=noise_level,
            base_seed=base_seed,
            parts=(
                target_id,
                "rm",
                route.preparation_id or route.macrostate_id,
                route.route_id,
                route.endpoint_id,
                noise_level,
            ),
        )
        noised_routes.append(
            route.model_copy(
                update={
                    "outcome_counts": None,
                    "outcome_probabilities": mixed,
                }
            )
        )
    return trace.model_copy(
        update={
            "trace_id": f"{trace.trace_id}__noise_{noise_level:.2f}",
            "route_observations": noised_routes,
            "metadata": {
                **trace.metadata,
                "noise_level": noise_level,
                "noise_model": "independent_jitter_mix_v1",
            },
        }
    )


def make_noisy_ccd_trace(
    trace: ObservationTrace,
    *,
    instance: EventPackageInstance | None,
    noise_level: float,
    base_seed: int,
    target_id: str,
) -> ObservationTrace:
    atoms_by_context = (
        {
            context.context_id: [atom.atom_id for atom in context.atoms]
            for context in instance.contexts
        }
        if instance is not None
        else {}
    )
    noised_sequences: list[RepeatedReadSequence] = []
    for sequence in trace.repeated_read_sequences:
        context_atoms = atoms_by_context.get(
            sequence.context_id,
            sorted({atom_id for read in sequence.reads for atom_id in read}),
        )
        noised_reads: list[list[str]] = []
        for read_index, read in enumerate(sequence.reads):
            if len(read) != 1 or noise_level <= 0:
                noised_reads.append(list(read))
                continue
            current_atom = read[0]
            alternative_atoms = [
                atom_id for atom_id in context_atoms if atom_id != current_atom
            ]
            rng = random.Random(
                _seed_from_parts(
                    base_seed,
                    target_id,
                    "ccd",
                    sequence.context_id,
                    read_index,
                    noise_level,
                )
            )
            draw = rng.random()
            if draw < noise_level / 3:
                noised_reads.append([])
            elif draw < (2 * noise_level) / 3 and alternative_atoms:
                noised_reads.append(
                    [alternative_atoms[int(rng.random() * len(alternative_atoms))]]
                )
            elif draw < noise_level and alternative_atoms:
                extra_atom = alternative_atoms[
                    int(rng.random() * len(alternative_atoms))
                ]
                noised_reads.append(sorted([current_atom, extra_atom]))
            else:
                noised_reads.append([current_atom])
        noised_sequences.append(sequence.model_copy(update={"reads": noised_reads}))
    return trace.model_copy(
        update={
            "trace_id": f"{trace.trace_id}__noise_{noise_level:.2f}",
            "repeated_read_sequences": noised_sequences,
            "metadata": {
                **trace.metadata,
                "noise_level": noise_level,
                "noise_model": "singleton_corruption_v1",
            },
        }
    )
