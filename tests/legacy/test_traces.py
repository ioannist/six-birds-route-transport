from __future__ import annotations

import json
from pathlib import Path

from sixbirds_event.reporting.structural_report import load_event_package_instance
from sixbirds_event.schemas.observation_trace import ObservationTrace
from sixbirds_event.traces.builders import (
    build_observation_trace,
    load_observation_trace,
    make_downstream_probe,
    make_observation,
    make_repeated_read_sequence,
    make_route_trace,
    write_observation_trace,
)
from sixbirds_event.traces.synthetic import generate_clean_trace, generate_noisy_trace
from sixbirds_event.validation import validate_observation_trace


SMOKE_INSTANCE = Path("experiments/instances/smoke/exact-extendable.json")
SMOKE_TRACE_DIR = Path("experiments/instances/smoke/traces")


def test_build_and_validate_trace_with_linked_instance(tmp_path: Path) -> None:
    instance = load_event_package_instance(SMOKE_INSTANCE)
    trace = build_observation_trace(
        trace_id="trace_builder_demo",
        instance_id=instance.instance_id,
        instance_artifact=SMOKE_INSTANCE.as_posix(),
        observations=[
            make_observation(
                context_id="ctx_a",
                atom_ids=["a0"],
                status="observed",
                count=4,
                probability=0.4,
            ),
            make_observation(
                context_id="ctx_b",
                atom_ids=["b0"],
                status="observed",
                count=6,
                probability=0.6,
            ),
        ],
        repeated_read_sequences=[
            make_repeated_read_sequence(
                context_id="ctx_a",
                reads=[["a0"], ["a0"], ["a1"]],
            )
        ],
        downstream_probes=[
            make_downstream_probe(
                probe_id="probe_builder",
                signature="builder:ctx_a",
                payload={"summary": "toy"},
            )
        ],
        route_trace=make_route_trace(
            route_id="route_builder",
            steps=["read", "repeat", "probe"],
            notes="builder trace",
        ),
        metadata={"source": "test"},
    )
    target = write_observation_trace(trace, tmp_path / "trace.json")
    loaded = load_observation_trace(target, linked_instance=instance)
    assert isinstance(loaded, ObservationTrace)
    assert loaded.repeated_read_sequences
    assert loaded.downstream_probes
    assert loaded.route_trace is not None


def test_sample_trace_files_validate() -> None:
    for path in sorted(SMOKE_TRACE_DIR.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        instance_path = Path(payload["instance_artifact"])
        instance = load_event_package_instance(instance_path)
        trace = load_observation_trace(path, linked_instance=instance)
        assert trace.instance_artifact == instance_path.as_posix()


def test_synthetic_trace_generation_is_seeded_and_deterministic() -> None:
    instance = load_event_package_instance(SMOKE_INSTANCE)
    clean_a = generate_clean_trace(
        instance,
        trace_id="trace_clean",
        seed=7,
        instance_artifact=SMOKE_INSTANCE.as_posix(),
    )
    clean_b = generate_clean_trace(
        instance,
        trace_id="trace_clean",
        seed=7,
        instance_artifact=SMOKE_INSTANCE.as_posix(),
    )
    noisy_a = generate_noisy_trace(
        instance,
        trace_id="trace_noisy",
        seed=7,
        instance_artifact=SMOKE_INSTANCE.as_posix(),
    )
    noisy_b = generate_noisy_trace(
        instance,
        trace_id="trace_noisy",
        seed=7,
        instance_artifact=SMOKE_INSTANCE.as_posix(),
    )
    assert clean_a.model_dump(mode="json") == clean_b.model_dump(mode="json")
    assert noisy_a.model_dump(mode="json") == noisy_b.model_dump(mode="json")


def test_clean_and_noisy_generators_differ_meaningfully() -> None:
    instance = load_event_package_instance(SMOKE_INSTANCE)
    clean = generate_clean_trace(
        instance,
        trace_id="trace_clean",
        seed=7,
        instance_artifact=SMOKE_INSTANCE.as_posix(),
    )
    noisy = generate_noisy_trace(
        instance,
        trace_id="trace_noisy",
        seed=7,
        instance_artifact=SMOKE_INSTANCE.as_posix(),
    )
    assert clean.model_dump(mode="json") != noisy.model_dump(mode="json")
    assert clean.metadata["generator"] == "clean"
    assert noisy.metadata["generator"] == "noisy"
    assert clean.observations[0].status != noisy.observations[0].status


def test_saved_trace_round_trips_through_validation_layer(tmp_path: Path) -> None:
    instance = load_event_package_instance(SMOKE_INSTANCE)
    trace = generate_noisy_trace(
        instance,
        trace_id="trace_round_trip",
        seed=11,
        instance_artifact=SMOKE_INSTANCE.as_posix(),
    )
    target = write_observation_trace(trace, tmp_path / "generated.json")
    payload = json.loads(target.read_text(encoding="utf-8"))
    result = validate_observation_trace(payload, linked_instance=instance)
    assert result.ok
