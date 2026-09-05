from __future__ import annotations

from pathlib import Path

from sixbirds_event.audits.context_closure import compute_context_closure_defect
from sixbirds_event.reporting.structural_report import load_event_package_instance
from sixbirds_event.traces.builders import (
    build_observation_trace,
    make_observation,
    make_repeated_read_sequence,
)
from sixbirds_event.traces.synthetic import (
    generate_ccd_clean_trace,
    generate_ccd_noisy_trace,
)


SMOKE_INSTANCE = Path("experiments/instances/smoke/exact-extendable.json")


def test_clean_synthetic_trace_produces_zero_or_near_zero_defects() -> None:
    instance = load_event_package_instance(SMOKE_INSTANCE)
    trace = generate_ccd_clean_trace(
        instance,
        trace_id="trace_ccd_clean_test",
        seed=7,
        instance_artifact=SMOKE_INSTANCE.as_posix(),
    )
    result = compute_context_closure_defect(trace, instance=instance)
    assert result.overall_ccd == 0.0
    for context_result in result.context_results:
        assert context_result.exclusivity_defect == 0.0
        assert context_result.exhaustivity_defect == 0.0
        assert context_result.reread_instability == 0.0
        assert context_result.closure_defect == 0.0


def test_noisy_synthetic_trace_produces_larger_defects() -> None:
    instance = load_event_package_instance(SMOKE_INSTANCE)
    clean = generate_ccd_clean_trace(
        instance,
        trace_id="trace_ccd_clean_test",
        seed=7,
        instance_artifact=SMOKE_INSTANCE.as_posix(),
    )
    noisy = generate_ccd_noisy_trace(
        instance,
        trace_id="trace_ccd_noisy_test",
        seed=11,
        instance_artifact=SMOKE_INSTANCE.as_posix(),
    )
    clean_result = compute_context_closure_defect(clean, instance=instance)
    noisy_result = compute_context_closure_defect(noisy, instance=instance)
    assert noisy_result.overall_ccd is not None
    assert clean_result.overall_ccd is not None
    assert noisy_result.overall_ccd > clean_result.overall_ccd
    assert any(
        (context_result.exclusivity_defect > 0.0)
        or (context_result.exhaustivity_defect > 0.0)
        or ((context_result.reread_instability or 0.0) > 0.0)
        or ((context_result.closure_defect or 0.0) > 0.0)
        for context_result in noisy_result.context_results
    )


def test_component_defects_respond_to_repeated_read_patterns() -> None:
    instance = load_event_package_instance(SMOKE_INSTANCE)
    trace = build_observation_trace(
        trace_id="trace_ccd_components",
        instance_id=instance.instance_id,
        instance_artifact=SMOKE_INSTANCE.as_posix(),
        observations=[
            make_observation(context_id="ctx_a", atom_ids=["a0"], count=4),
        ],
        repeated_read_sequences=[
            make_repeated_read_sequence(
                context_id="ctx_a",
                reads=[["a0"], ["a0", "a1"], [], ["a1"], ["a0"]],
            )
        ],
        metadata={"source": "test"},
    )
    result = compute_context_closure_defect(trace, instance=instance)
    context_result = result.context_results[0]
    assert context_result.exclusivity_defect > 0.0
    assert context_result.exhaustivity_defect > 0.0
    assert context_result.reread_instability is not None
    assert context_result.reread_instability > 0.0
    assert context_result.closure_defect is not None


def test_closure_defect_is_not_redundant_with_reread_instability() -> None:
    instance = load_event_package_instance(SMOKE_INSTANCE)
    trace = build_observation_trace(
        trace_id="trace_ccd_collapse",
        instance_id=instance.instance_id,
        instance_artifact=SMOKE_INSTANCE.as_posix(),
        observations=[
            make_observation(context_id="ctx_a", atom_ids=["a0"], count=2),
        ],
        repeated_read_sequences=[
            make_repeated_read_sequence(
                context_id="ctx_a",
                reads=[["a0"], ["a0"]],
            ),
            make_repeated_read_sequence(
                context_id="ctx_a",
                reads=[["a1"], ["a0"]],
            ),
        ],
        metadata={"source": "test"},
    )
    result = compute_context_closure_defect(trace, instance=instance)
    context_result = result.context_results[0]
    assert context_result.reread_instability is not None
    assert context_result.reread_instability > 0.0
    assert context_result.closure_defect == 0.0
