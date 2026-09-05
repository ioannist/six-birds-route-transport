from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from holonomy_memory import schemas
from holonomy_memory.schemas import (
    BenchmarkManifest,
    BenchmarkResultManifest,
    CompletionManifest,
    CurrentizationManifest,
    ContinuationKernelSpec,
    HistoryDistributionSpec,
    InterfaceResultRecord,
    PerturbationSweep,
    RouteTransportPackageConfig,
    SearchSpace,
)
from holonomy_memory.validation import (
    load_benchmark_manifest,
    load_benchmark_result_manifest,
    load_completion_manifest,
    load_currentization_manifest,
    load_perturbation_sweep,
    load_route_transport_package_config,
    load_search_space,
)


FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_public_schema_imports_are_clean() -> None:
    assert schemas.RouteTransportPackageConfig.__name__ == "RouteTransportPackageConfig"
    assert schemas.BenchmarkManifest.__name__ == "BenchmarkManifest"
    assert schemas.BenchmarkResultManifest.__name__ == "BenchmarkResultManifest"


@pytest.mark.parametrize(
    ("loader", "path", "model_type"),
    [
        (load_route_transport_package_config, "route_transport_package_stub.json", RouteTransportPackageConfig),
        (load_benchmark_manifest, "benchmark_manifest_stub.json", BenchmarkManifest),
        (load_completion_manifest, "completion_manifest_stub.json", CompletionManifest),
        (load_currentization_manifest, "currentization_manifest_stub.json", CurrentizationManifest),
        (load_perturbation_sweep, "perturbation_sweep_stub.json", PerturbationSweep),
        (load_search_space, "search_space_stub.json", SearchSpace),
        (load_benchmark_result_manifest, "result_manifest_stub.json", BenchmarkResultManifest),
    ],
)
def test_stub_fixtures_validate(loader, path: str, model_type) -> None:
    model = loader(FIXTURES / path)
    if model_type is not None:
        assert isinstance(model, model_type)


def test_hm001_smoke_baseline_still_passes() -> None:
    import holonomy_memory
    import sixbirds_event

    assert holonomy_memory.__version__ == "0.0.0"
    assert sixbirds_event.__version__ == "0.0.0"
    assert Path("artifacts/results").is_dir()
    assert Path("docs/results").is_dir()
    assert Path("lean").is_dir()


def test_extra_field_is_rejected() -> None:
    payload = {
        "schema_version": "route-transport-package.v1",
        "package_id": "route_transport_stub",
        "support": {
            "support_id": "support_stub",
            "visible_support_labels": ["visible_a", "visible_b"],
            "same_support_required": True,
        },
        "state_space": {
            "internal_state_ids": ["q0", "q1"],
            "support_projection": {"q0": "visible_a", "q1": "visible_b"},
        },
        "interfaces": [{"interface_id": "i0"}],
        "event_packages": [
            {
                "package_id": "ep0",
                "interface_id": "i0",
                "events": [{"event_id": "e0", "weights": {"visible_a": 1.0}}],
            }
        ],
        "histories": [
            {
                "history_id": "h0",
                "source_interface_id": "i0",
                "target_interface_id": "i0",
                "probabilities": {"q0": 1.0},
            }
        ],
        "continuations": [
            {
                "continuation_id": "c0",
                "source_interface_id": "i0",
                "target_interface_id": "i0",
                "kernel": {"q0": {"q0": 1.0}},
            }
        ],
        "loops": [{"loop_id": "l0", "interface_id": "i0", "continuation_id": "c0"}],
        "unexpected": True,
    }
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        RouteTransportPackageConfig.model_validate(payload)


def test_bad_class_label_is_rejected() -> None:
    payload = {
        "benchmark_id": "benchmark_stub",
        "interface_id": "i0",
        "history_count": 1,
        "current_quotient_size": 2,
        "predictive_quotient_size": 2,
        "witness_count": 1,
        "max_fiber_size": 1,
        "discrepancy_metric_name": "psd_exact_gap",
        "discrepancy_metric_value": 0.0,
        "loop_action_score_current_quotient": 0.0,
        "loop_action_score_predictive_quotient": 0.0,
        "support_fixation_status": "passed",
        "currentization_status": "passed",
        "flattening_status": "passed",
        "robustness_fraction": 1.0,
        "class_label": "bad_label",
        "runtime": 0.01,
        "seed": 0,
    }
    with pytest.raises(ValidationError, match="class_label"):
        InterfaceResultRecord.model_validate(payload)


def test_history_distribution_must_sum_to_one() -> None:
    payload = {
        "history_id": "h0",
        "source_interface_id": "i0",
        "target_interface_id": "i1",
        "probabilities": {"q0": 0.7, "q1": 0.2},
    }
    with pytest.raises(ValidationError, match="must sum to 1"):
        HistoryDistributionSpec.model_validate(payload)


def test_continuation_rows_must_sum_to_one() -> None:
    payload = {
        "continuation_id": "c0",
        "source_interface_id": "i0",
        "target_interface_id": "i0",
        "kernel": {"q0": {"q0": 0.7, "q1": 0.1}},
    }
    with pytest.raises(ValidationError, match="must sum to 1"):
        ContinuationKernelSpec.model_validate(payload)


def test_loop_must_reference_closed_continuation() -> None:
    payload = {
        "schema_version": "route-transport-package.v1",
        "package_id": "route_transport_stub",
        "support": {
            "support_id": "support_stub",
            "visible_support_labels": ["visible_a", "visible_b"],
            "same_support_required": True,
        },
        "state_space": {
            "internal_state_ids": ["q0", "q1"],
            "support_projection": {"q0": "visible_a", "q1": "visible_b"},
        },
        "interfaces": [
            {"interface_id": "i0"},
            {"interface_id": "i1"},
        ],
        "event_packages": [
            {
                "package_id": "ep0",
                "interface_id": "i0",
                "events": [{"event_id": "e0", "weights": {"visible_a": 1.0}}],
            }
        ],
        "histories": [
            {
                "history_id": "h0",
                "source_interface_id": "i0",
                "target_interface_id": "i1",
                "probabilities": {"q0": 1.0},
            }
        ],
        "continuations": [
            {
                "continuation_id": "c0",
                "source_interface_id": "i0",
                "target_interface_id": "i1",
                "kernel": {"q0": {"q0": 1.0}},
            }
        ],
        "loops": [{"loop_id": "l0", "interface_id": "i0", "continuation_id": "c0"}],
    }
    with pytest.raises(ValidationError, match="same interface"):
        RouteTransportPackageConfig.model_validate(payload)


def test_bad_support_projection_reference_is_rejected() -> None:
    payload = {
        "schema_version": "route-transport-package.v1",
        "package_id": "route_transport_stub",
        "support": {
            "support_id": "support_stub",
            "visible_support_labels": ["visible_a", "visible_b"],
            "same_support_required": True,
        },
        "state_space": {
            "internal_state_ids": ["q0", "q1"],
            "support_projection": {"q0": "visible_a", "q1": "visible_c"},
        },
        "interfaces": [
            {"interface_id": "i0"},
        ],
        "event_packages": [
            {
                "package_id": "ep0",
                "interface_id": "i0",
                "events": [{"event_id": "e0", "weights": {"visible_a": 1.0}}],
            }
        ],
        "histories": [
            {
                "history_id": "h0",
                "source_interface_id": "i0",
                "target_interface_id": "i0",
                "probabilities": {"q0": 1.0},
            }
        ],
        "continuations": [
            {
                "continuation_id": "c0",
                "source_interface_id": "i0",
                "target_interface_id": "i0",
                "kernel": {"q0": {"q0": 1.0}},
            }
        ],
        "loops": [{"loop_id": "l0", "interface_id": "i0", "continuation_id": "c0"}],
    }
    with pytest.raises(ValidationError, match="undeclared support labels"):
        RouteTransportPackageConfig.model_validate(payload)
