from __future__ import annotations

from fractions import Fraction
from pathlib import Path

import pytest

from holonomy_memory import (
    CurrentSignature,
    DiscrepancyMetricResult,
    FutureSignature,
    MemoryWitness,
    compute_current_partition,
    compute_current_signature,
    compute_exact_max_abs_future_gap,
    compute_future_signature,
    compute_predictive_partition,
    enumerate_memory_witnesses,
    load_route_transport_package,
    predictive_refines_current,
)
from holonomy_memory.analysis import MissingEventPackageError
from holonomy_memory.core import RouteTransportPackage
from holonomy_memory.schemas import RouteTransportPackageConfig


FLAT_CONFIG = Path("configs/benchmarks/toy_flat_signatures.json")
WITNESS_CONFIG = Path("configs/benchmarks/toy_predictive_witness.json")


def test_public_analysis_imports_are_clean() -> None:
    assert CurrentSignature.__name__ == "CurrentSignature"
    assert FutureSignature.__name__ == "FutureSignature"
    assert DiscrepancyMetricResult.__name__ == "DiscrepancyMetricResult"


def test_smoke_baseline_and_placeholder_dirs_still_exist() -> None:
    import holonomy_memory
    import sixbirds_event

    assert holonomy_memory.__version__ == "0.0.0"
    assert sixbirds_event.__version__ == "0.0.0"
    assert Path("artifacts/results/.gitkeep").is_file()
    assert Path("docs/results/.gitkeep").is_file()


def test_current_signatures_match_exact_fixture_values() -> None:
    flat_package = load_route_transport_package(FLAT_CONFIG)
    witness_package = load_route_transport_package(WITNESS_CONFIG)

    flat_signature_0 = compute_current_signature(flat_package, "h_mid_0")
    flat_signature_1 = compute_current_signature(flat_package, "h_mid_1")
    witness_signature_0 = compute_current_signature(witness_package, "h_mid_0")
    witness_signature_1 = compute_current_signature(witness_package, "h_mid_1")

    expected = (("indicator_A", Fraction(1, 1)),)
    assert flat_signature_0.signature_key == expected
    assert flat_signature_1.signature_key == expected
    assert witness_signature_0.signature_key == expected
    assert witness_signature_1.signature_key == expected


def test_future_signatures_are_exact_and_diverge_on_witness_fixture() -> None:
    flat_package = load_route_transport_package(FLAT_CONFIG)
    witness_package = load_route_transport_package(WITNESS_CONFIG)

    flat_signature_0 = compute_future_signature(flat_package, "h_mid_0")
    flat_signature_1 = compute_future_signature(flat_package, "h_mid_1")
    witness_signature_0 = compute_future_signature(witness_package, "h_mid_0")
    witness_signature_1 = compute_future_signature(witness_package, "h_mid_1")

    assert flat_signature_0.signature_key == (
        ("k_mid_end", "end", "indicator_A", Fraction(1, 1)),
    )
    assert flat_signature_0.signature_key == flat_signature_1.signature_key
    assert witness_signature_0.signature_key == (
        ("k_mid_end", "end", "indicator_B", Fraction(0, 1)),
    )
    assert witness_signature_1.signature_key == (
        ("k_mid_end", "end", "indicator_B", Fraction(1, 1)),
    )


def test_current_and_predictive_partitions_are_deterministic() -> None:
    flat_package = load_route_transport_package(FLAT_CONFIG)
    witness_package = load_route_transport_package(WITNESS_CONFIG)

    flat_current = compute_current_partition(flat_package, "mid")
    flat_predictive = compute_predictive_partition(flat_package, "mid")
    witness_current = compute_current_partition(witness_package, "mid")
    witness_predictive = compute_predictive_partition(witness_package, "mid")

    assert flat_current.class_count == 1
    assert flat_predictive.class_count == 1
    assert witness_current.class_count == 1
    assert witness_predictive.class_count == 2
    assert flat_current.classes[0].member_history_ids == ("h_mid_0", "h_mid_1")
    assert witness_predictive.classes[0].member_history_ids == ("h_mid_0",)
    assert witness_predictive.classes[1].member_history_ids == ("h_mid_1",)


def test_predictive_partition_refines_current_partition() -> None:
    flat_package = load_route_transport_package(FLAT_CONFIG)
    witness_package = load_route_transport_package(WITNESS_CONFIG)

    assert predictive_refines_current(
        compute_current_partition(flat_package, "mid"),
        compute_predictive_partition(flat_package, "mid"),
    )
    assert predictive_refines_current(
        compute_current_partition(witness_package, "mid"),
        compute_predictive_partition(witness_package, "mid"),
    )


def test_memory_witnesses_and_exact_discrepancy_match_expected_values() -> None:
    flat_package = load_route_transport_package(FLAT_CONFIG)
    witness_package = load_route_transport_package(WITNESS_CONFIG)

    flat_witnesses = enumerate_memory_witnesses(flat_package, "mid")
    witness_witnesses = enumerate_memory_witnesses(witness_package, "mid")
    flat_metric = compute_exact_max_abs_future_gap(flat_package, "mid")
    witness_metric = compute_exact_max_abs_future_gap(witness_package, "mid")

    assert flat_witnesses == ()
    assert flat_metric.metric_value == Fraction(0, 1)
    assert witness_witnesses == (
        MemoryWitness(
            interface_id="mid",
            history_id_1="h_mid_0",
            history_id_2="h_mid_1",
            current_class_id="C0",
            predictive_class_id_1="C0",
            predictive_class_id_2="C1",
        ),
    )
    assert witness_metric.metric_value == Fraction(1, 1)
    assert witness_metric.current_class_id == "C0"
    assert witness_metric.history_pair == ("h_mid_0", "h_mid_1")
    assert witness_metric.continuation_id == "k_mid_end"
    assert witness_metric.event_id == "indicator_B"


def test_missing_measured_event_package_fails_cleanly() -> None:
    package = _build_runtime_package(
        {
            "schema_version": "route-transport-package.v1",
            "package_id": "missing_mid_events",
            "support": {
                "support_id": "support",
                "visible_support_labels": ["A", "B"],
                "same_support_required": True,
            },
            "state_space": {
                "internal_state_ids": ["m0", "e0"],
                "support_projection": {"m0": "A", "e0": "A"},
            },
            "interfaces": [{"interface_id": "mid"}, {"interface_id": "end"}],
            "event_packages": [
                {
                    "package_id": "end_events",
                    "interface_id": "end",
                    "events": [{"event_id": "indicator_A", "weights": {"A": 1, "B": 0}}],
                }
            ],
            "histories": [
                {
                    "history_id": "h_mid",
                    "source_interface_id": "mid",
                    "target_interface_id": "mid",
                    "probabilities": {"m0": 1},
                }
            ],
            "continuations": [
                {
                    "continuation_id": "k_mid_end",
                    "source_interface_id": "mid",
                    "target_interface_id": "end",
                    "kernel": {"m0": {"e0": 1}, "e0": {"e0": 1}},
                },
                {
                    "continuation_id": "loop_end",
                    "source_interface_id": "end",
                    "target_interface_id": "end",
                    "kernel": {"m0": {"m0": 1}, "e0": {"e0": 1}},
                },
            ],
            "loops": [{"loop_id": "end_loop", "interface_id": "end", "continuation_id": "loop_end"}],
        }
    )

    with pytest.raises(MissingEventPackageError, match="interface mid has no event package"):
        compute_current_signature(package, "h_mid", interface_id="mid")


def test_missing_future_target_event_package_fails_cleanly() -> None:
    package = _build_runtime_package(
        {
            "schema_version": "route-transport-package.v1",
            "package_id": "missing_end_events",
            "support": {
                "support_id": "support",
                "visible_support_labels": ["A", "B"],
                "same_support_required": True,
            },
            "state_space": {
                "internal_state_ids": ["m0", "e0"],
                "support_projection": {"m0": "A", "e0": "A"},
            },
            "interfaces": [{"interface_id": "mid"}, {"interface_id": "end"}],
            "event_packages": [
                {
                    "package_id": "mid_events",
                    "interface_id": "mid",
                    "events": [{"event_id": "indicator_A", "weights": {"A": 1, "B": 0}}],
                }
            ],
            "histories": [
                {
                    "history_id": "h_mid",
                    "source_interface_id": "mid",
                    "target_interface_id": "mid",
                    "probabilities": {"m0": 1},
                }
            ],
            "continuations": [
                {
                    "continuation_id": "k_mid_end",
                    "source_interface_id": "mid",
                    "target_interface_id": "end",
                    "kernel": {"m0": {"e0": 1}, "e0": {"e0": 1}},
                },
                {
                    "continuation_id": "loop_end",
                    "source_interface_id": "end",
                    "target_interface_id": "end",
                    "kernel": {"m0": {"m0": 1}, "e0": {"e0": 1}},
                },
            ],
            "loops": [{"loop_id": "end_loop", "interface_id": "end", "continuation_id": "loop_end"}],
        }
    )

    with pytest.raises(MissingEventPackageError, match="interface end has no event package"):
        compute_future_signature(package, "h_mid", interface_id="mid")


def _build_runtime_package(payload: dict[str, object]) -> RouteTransportPackage:
    config = RouteTransportPackageConfig.model_validate(payload)
    return RouteTransportPackage.from_config(config)
