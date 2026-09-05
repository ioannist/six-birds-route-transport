from __future__ import annotations

from fractions import Fraction
from pathlib import Path

import pytest

from holonomy_memory import (
    ClassTransportImage,
    ClassTransportMap,
    LoopActionResult,
    LoopMetricResult,
    compute_current_loop_action,
    compute_loop_action_metrics,
    compute_predictive_loop_action,
    compute_predictive_transport_map,
    load_route_transport_package,
)
from holonomy_memory.analysis import (
    LoopActionUndefinedError,
    TransportMapNotWellDefinedError,
    compute_current_transport_map,
)
from holonomy_memory.core import RouteTransportPackage
from holonomy_memory.schemas import RouteTransportPackageConfig

TOY_MEMORY_LOOP = Path("configs/benchmarks/toy_memory_loop.json")


def test_memory_readout_does_not_descend_to_current_quotient() -> None:
    package = load_route_transport_package(TOY_MEMORY_LOOP)
    with pytest.raises(TransportMapNotWellDefinedError, match="not well-defined"):
        compute_current_transport_map(package, "to_end")
    assert compute_current_transport_map(package, "swap_mid").is_identity


def test_public_transport_imports_are_clean() -> None:
    assert ClassTransportImage.__name__ == "ClassTransportImage"
    assert ClassTransportMap.__name__ == "ClassTransportMap"
    assert LoopActionResult.__name__ == "LoopActionResult"
    assert LoopMetricResult.__name__ == "LoopMetricResult"


def test_baseline_placeholders_exist_after_snapshot_repair() -> None:
    assert Path("artifacts/results/.gitkeep").is_file()
    assert Path("docs/results/.gitkeep").is_file()


def test_predictive_transport_map_to_end_is_exact() -> None:
    package = load_route_transport_package(TOY_MEMORY_LOOP)

    transport_map = compute_predictive_transport_map(package, "to_end")

    assert transport_map == ClassTransportMap(
        partition_kind="predictive",
        source_interface_id="mid",
        target_interface_id="end",
        continuation_id="to_end",
        source_classes=transport_map.source_classes,
        target_classes=transport_map.target_classes,
        class_images=(
            ClassTransportImage(
                source_class_id="C0",
                target_class_id="C0",
                representative_source_history_id="h_mid_0",
                image_signature_key=transport_map.class_images[0].image_signature_key,
            ),
            ClassTransportImage(
                source_class_id="C1",
                target_class_id="C1",
                representative_source_history_id="h_mid_1",
                image_signature_key=transport_map.class_images[1].image_signature_key,
            ),
        ),
        class_image_by_source_id=transport_map.class_image_by_source_id,
        is_identity=False,
    )
    assert transport_map.class_image_by_source_id == {"C0": "C0", "C1": "C1"}


def test_identity_loop_actions_are_identity() -> None:
    package = load_route_transport_package(TOY_MEMORY_LOOP)

    predictive_identity = compute_predictive_loop_action(package, "id_mid")
    current_identity = compute_current_loop_action(package, "id_mid")

    assert predictive_identity.is_trivial
    assert predictive_identity.moved_class_fraction == Fraction(0, 1)
    assert predictive_identity.class_images == (
        ClassTransportImage(
            source_class_id="C0",
            target_class_id="C0",
            representative_source_history_id="h_mid_0",
            image_signature_key=predictive_identity.class_images[0].image_signature_key,
        ),
        ClassTransportImage(
            source_class_id="C1",
            target_class_id="C1",
            representative_source_history_id="h_mid_1",
            image_signature_key=predictive_identity.class_images[1].image_signature_key,
        ),
    )
    assert current_identity.is_trivial
    assert current_identity.moved_class_fraction == Fraction(0, 1)


def test_swap_loop_is_trivial_on_current_and_nontrivial_on_predictive() -> None:
    package = load_route_transport_package(TOY_MEMORY_LOOP)

    current_action = compute_current_loop_action(package, "swap_mid")
    predictive_action = compute_predictive_loop_action(package, "swap_mid")
    current_metrics = compute_loop_action_metrics(current_action)
    predictive_metrics = compute_loop_action_metrics(predictive_action)

    assert current_action.is_trivial
    assert current_action.moved_class_count == 0
    assert current_action.moved_class_fraction == Fraction(0, 1)
    assert predictive_action.is_trivial is False
    assert predictive_action.moved_class_ids == ("C0", "C1")
    assert predictive_action.moved_class_count == 2
    assert predictive_action.moved_class_fraction == Fraction(1, 1)
    assert predictive_action.class_images == (
        ClassTransportImage(
            source_class_id="C0",
            target_class_id="C1",
            representative_source_history_id="h_mid_0",
            image_signature_key=predictive_action.class_images[0].image_signature_key,
        ),
        ClassTransportImage(
            source_class_id="C1",
            target_class_id="C0",
            representative_source_history_id="h_mid_1",
            image_signature_key=predictive_action.class_images[1].image_signature_key,
        ),
    )
    assert current_metrics[0].metric_name == "loop_moved_class_fraction"
    assert current_metrics[0].metric_value == Fraction(0, 1)
    assert predictive_metrics[0].metric_name == "loop_moved_class_fraction"
    assert predictive_metrics[0].metric_value == Fraction(1, 1)


def test_non_well_defined_predictive_transport_raises_cleanly() -> None:
    package = _build_runtime_package(
        {
            "schema_version": "route-transport-package.v1",
            "package_id": "non_well_defined_predictive_transport",
            "support": {
                "support_id": "support",
                "visible_support_labels": ["A", "B"],
                "same_support_required": True,
            },
            "state_space": {
                "internal_state_ids": ["s0", "s1", "j0", "j1", "tA", "tB"],
                "support_projection": {
                    "s0": "A",
                    "s1": "A",
                    "j0": "A",
                    "j1": "A",
                    "tA": "A",
                    "tB": "B"
                },
            },
            "interfaces": [
                {"interface_id": "src"},
                {"interface_id": "mid"},
                {"interface_id": "end"},
            ],
            "event_packages": [
                {
                    "package_id": "src_events",
                    "interface_id": "src",
                    "events": [{"event_id": "indicator_A", "weights": {"A": 1, "B": 0}}],
                },
                {
                    "package_id": "mid_events",
                    "interface_id": "mid",
                    "events": [{"event_id": "indicator_A", "weights": {"A": 1, "B": 0}}],
                },
                {
                    "package_id": "end_events",
                    "interface_id": "end",
                    "events": [{"event_id": "indicator_B", "weights": {"A": 0, "B": 1}}],
                }
            ],
            "histories": [
                {
                    "history_id": "h_src_0",
                    "source_interface_id": "src",
                    "target_interface_id": "src",
                    "probabilities": {"s0": 1},
                },
                {
                    "history_id": "h_src_1",
                    "source_interface_id": "src",
                    "target_interface_id": "src",
                    "probabilities": {"s1": 1},
                },
                {
                    "history_id": "h_mid_0",
                    "source_interface_id": "src",
                    "target_interface_id": "mid",
                    "probabilities": {"j0": 1},
                },
                {
                    "history_id": "h_mid_1",
                    "source_interface_id": "src",
                    "target_interface_id": "mid",
                    "probabilities": {"j1": 1},
                },
                {
                    "history_id": "h_end_A",
                    "source_interface_id": "mid",
                    "target_interface_id": "end",
                    "probabilities": {"tA": 1},
                },
                {
                    "history_id": "h_end_B",
                    "source_interface_id": "mid",
                    "target_interface_id": "end",
                    "probabilities": {"tB": 1},
                }
            ],
            "continuations": [
                {
                    "continuation_id": "src_to_mid",
                    "source_interface_id": "src",
                    "target_interface_id": "mid",
                    "kernel": {
                        "s0": {"j0": 1},
                        "s1": {"j1": 1},
                        "j0": {"j0": 1},
                        "j1": {"j1": 1},
                        "tA": {"tA": 1},
                        "tB": {"tB": 1}
                    },
                },
                {
                    "continuation_id": "mid_to_end",
                    "source_interface_id": "mid",
                    "target_interface_id": "end",
                    "kernel": {
                        "s0": {"s0": 1},
                        "s1": {"s1": 1},
                        "j0": {"tA": 1},
                        "j1": {"tB": 1},
                        "tA": {"tA": 1},
                        "tB": {"tB": 1}
                    },
                },
                {
                    "continuation_id": "end_id",
                    "source_interface_id": "end",
                    "target_interface_id": "end",
                    "kernel": {
                        "s0": {"s0": 1},
                        "s1": {"s1": 1},
                        "j0": {"j0": 1},
                        "j1": {"j1": 1},
                        "tA": {"tA": 1},
                        "tB": {"tB": 1}
                    },
                }
            ],
            "loops": [
                {"loop_id": "end_id", "interface_id": "end", "continuation_id": "end_id"}
            ],
        }
    )

    with pytest.raises(TransportMapNotWellDefinedError, match="not well-defined"):
        compute_predictive_transport_map(package, "src_to_mid")


def test_loop_action_failure_is_wrapped_cleanly() -> None:
    package = _build_runtime_package(
        {
            "schema_version": "route-transport-package.v1",
            "package_id": "undefined_loop_action",
            "support": {
                "support_id": "support",
                "visible_support_labels": ["A", "B"],
                "same_support_required": True,
            },
            "state_space": {
                "internal_state_ids": ["m0", "m1", "eA", "eB"],
                "support_projection": {"m0": "A", "m1": "A", "eA": "A", "eB": "B"},
            },
            "interfaces": [{"interface_id": "mid"}, {"interface_id": "end"}],
            "event_packages": [
                {
                    "package_id": "mid_events",
                    "interface_id": "mid",
                    "events": [{"event_id": "indicator_A", "weights": {"A": 1, "B": 0}}],
                },
                {
                    "package_id": "end_events",
                    "interface_id": "end",
                    "events": [{"event_id": "indicator_B", "weights": {"A": 0, "B": 1}}],
                }
            ],
            "histories": [
                {
                    "history_id": "h0",
                    "source_interface_id": "mid",
                    "target_interface_id": "mid",
                    "probabilities": {"m0": 1},
                }
            ],
            "continuations": [
                {
                    "continuation_id": "bad_loop",
                    "source_interface_id": "mid",
                    "target_interface_id": "mid",
                    "kernel": {
                        "m0": {"m1": 1},
                        "m1": {"m1": 1},
                        "eA": {"eA": 1},
                        "eB": {"eB": 1}
                    },
                },
                {
                    "continuation_id": "to_end",
                    "source_interface_id": "mid",
                    "target_interface_id": "end",
                    "kernel": {
                        "m0": {"eA": 1},
                        "m1": {"eB": 1},
                        "eA": {"eA": 1},
                        "eB": {"eB": 1}
                    },
                },
                {
                    "continuation_id": "end_id",
                    "source_interface_id": "end",
                    "target_interface_id": "end",
                    "kernel": {
                        "m0": {"m0": 1},
                        "m1": {"m1": 1},
                        "eA": {"eA": 1},
                        "eB": {"eB": 1}
                    },
                }
            ],
            "loops": [
                {"loop_id": "bad_loop", "interface_id": "mid", "continuation_id": "bad_loop"},
                {"loop_id": "end_id", "interface_id": "end", "continuation_id": "end_id"}
            ],
        }
    )

    with pytest.raises(LoopActionUndefinedError, match="loop action bad_loop is undefined"):
        compute_predictive_loop_action(package, "bad_loop")


def _build_runtime_package(payload: dict[str, object]) -> RouteTransportPackage:
    config = RouteTransportPackageConfig.model_validate(payload)
    return RouteTransportPackage.from_config(config)
