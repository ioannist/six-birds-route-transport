from __future__ import annotations

import random

from ..schemas.event_package import EventPackageInstance
from .builders import (
    build_observation_trace,
    make_downstream_probe,
    make_observation,
    make_repeated_read_sequence,
    make_route_trace,
)


def _first_atom_ids(instance: EventPackageInstance) -> dict[str, list[str]]:
    return {
        context.context_id: [context.atoms[0].atom_id] for context in instance.contexts
    }


def generate_clean_trace(
    instance: EventPackageInstance,
    *,
    trace_id: str,
    seed: int = 0,
    instance_artifact: str | None = None,
) -> object:
    rng = random.Random(seed)
    atom_map = _first_atom_ids(instance)
    observations = [
        make_observation(
            context_id=context.context_id,
            atom_ids=atom_map[context.context_id],
            status="observed",
            count=10,
            probability=1.0,
        )
        for context in instance.contexts
    ]
    repeated_reads = [
        make_repeated_read_sequence(
            context_id=context.context_id,
            reads=[atom_map[context.context_id] for _ in range(3)],
        )
        for context in instance.contexts
    ]
    downstream_probes = [
        make_downstream_probe(
            probe_id=f"probe_{context.context_id}",
            signature=f"clean:{context.context_id}:{rng.randint(0, 9999):04d}",
            payload={"mode": "clean", "stable_atom_ids": atom_map[context.context_id]},
        )
        for context in instance.contexts
    ]
    route_trace = make_route_trace(
        route_id="route_clean",
        steps=["read", "repeat", "probe", "record"],
        notes="deterministic clean synthetic trace",
    )
    return build_observation_trace(
        trace_id=trace_id,
        instance_id=instance.instance_id,
        instance_artifact=instance_artifact,
        observations=observations,
        repeated_read_sequences=repeated_reads,
        downstream_probes=downstream_probes,
        route_trace=route_trace,
        metadata={"generator": "clean", "seed": seed},
    )


def generate_noisy_trace(
    instance: EventPackageInstance,
    *,
    trace_id: str,
    seed: int = 0,
    instance_artifact: str | None = None,
) -> object:
    rng = random.Random(seed)
    observations = []
    repeated_reads = []
    downstream_probes = []
    for context in instance.contexts:
        atoms = [atom.atom_id for atom in context.atoms]
        chosen_atom = atoms[rng.randrange(len(atoms))]
        reads = []
        for _ in range(3):
            read_atom = atoms[rng.randrange(len(atoms))]
            reads.append([read_atom])
        observations.append(
            make_observation(
                context_id=context.context_id,
                atom_ids=[chosen_atom],
                status="noisy",
                count=5 + rng.randrange(6),
                probability=round(0.4 + 0.1 * rng.randrange(5), 2),
            )
        )
        repeated_reads.append(
            make_repeated_read_sequence(
                context_id=context.context_id,
                reads=reads,
            )
        )
        downstream_probes.append(
            make_downstream_probe(
                probe_id=f"probe_{context.context_id}",
                signature=f"noisy:{context.context_id}:{rng.randint(0, 9999):04d}",
                payload={
                    "mode": "noisy",
                    "observed_atom_ids": [chosen_atom],
                    "read_variation": reads,
                },
            )
        )
    route_trace = make_route_trace(
        route_id="route_noisy",
        steps=["read", "perturb", "repeat", "probe", "record"],
        notes="deterministic noisy synthetic trace",
    )
    return build_observation_trace(
        trace_id=trace_id,
        instance_id=instance.instance_id,
        instance_artifact=instance_artifact,
        observations=observations,
        repeated_read_sequences=repeated_reads,
        downstream_probes=downstream_probes,
        route_trace=route_trace,
        metadata={"generator": "noisy", "seed": seed},
    )


def generate_ccd_clean_trace(
    instance: EventPackageInstance,
    *,
    trace_id: str,
    seed: int = 0,
    instance_artifact: str | None = None,
) -> object:
    rng = random.Random(seed)
    observations = []
    repeated_reads = []
    for context in instance.contexts:
        stable_atom = context.atoms[rng.randrange(len(context.atoms))].atom_id
        observations.append(
            make_observation(
                context_id=context.context_id,
                atom_ids=[stable_atom],
                status="observed",
                count=12,
            )
        )
        repeated_reads.append(
            make_repeated_read_sequence(
                context_id=context.context_id,
                reads=[[stable_atom] for _ in range(5)],
            )
        )
    return build_observation_trace(
        trace_id=trace_id,
        instance_id=instance.instance_id,
        instance_artifact=instance_artifact,
        observations=observations,
        repeated_read_sequences=repeated_reads,
        downstream_probes=[
            make_downstream_probe(
                probe_id="probe_ccd_clean",
                signature="ccd:clean",
                payload={"mode": "clean", "seed": seed},
            )
        ],
        route_trace=make_route_trace(
            route_id="route_ccd_clean",
            steps=["read", "repeat", "record"],
            notes="stable repeated-read synthetic trace",
        ),
        metadata={"generator": "ccd_clean", "seed": seed},
    )


def generate_ccd_noisy_trace(
    instance: EventPackageInstance,
    *,
    trace_id: str,
    seed: int = 0,
    instance_artifact: str | None = None,
) -> object:
    rng = random.Random(seed)
    observations = []
    repeated_reads = []
    for index, context in enumerate(instance.contexts):
        atoms = [atom.atom_id for atom in context.atoms]
        first = atoms[0]
        second = atoms[min(1, len(atoms) - 1)]
        observations.append(
            make_observation(
                context_id=context.context_id,
                atom_ids=[first],
                status="noisy",
                count=8 + index,
            )
        )
        if index % 2 == 0:
            reads = [[first], [first, second], [], [second], [first]]
        else:
            reads = [[first], [second], [first], [second], [second]]
        repeated_reads.append(
            make_repeated_read_sequence(
                context_id=context.context_id,
                reads=reads,
            )
        )
    return build_observation_trace(
        trace_id=trace_id,
        instance_id=instance.instance_id,
        instance_artifact=instance_artifact,
        observations=observations,
        repeated_read_sequences=repeated_reads,
        downstream_probes=[
            make_downstream_probe(
                probe_id="probe_ccd_noisy",
                signature=f"ccd:noisy:{rng.randint(0, 9999):04d}",
                payload={"mode": "noisy", "seed": seed},
            )
        ],
        route_trace=make_route_trace(
            route_id="route_ccd_noisy",
            steps=["read", "perturb", "repeat", "record"],
            notes="noisy repeated-read synthetic trace",
        ),
        metadata={"generator": "ccd_noisy", "seed": seed},
    )
