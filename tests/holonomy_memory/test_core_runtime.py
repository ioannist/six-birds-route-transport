from __future__ import annotations

from collections import OrderedDict
from fractions import Fraction
from pathlib import Path

import pytest

from holonomy_memory import RouteTransportPackage, load_route_transport_package
from holonomy_memory.core import (
    CompositionTypeError,
    ContinuationKernelRuntime,
    HistoryDistributionRuntime,
    SupportRuntime,
    load_route_transport_package_from_config,
)
from holonomy_memory.validation import load_route_transport_package_config


TOY_CONFIG = Path("configs/benchmarks/toy_route_transport_package.json")


def test_public_runtime_imports_are_clean() -> None:
    assert RouteTransportPackage.__name__ == "RouteTransportPackage"
    assert CompositionTypeError.__name__ == "CompositionTypeError"


def test_toy_runtime_loads_from_path_and_config() -> None:
    runtime_from_path = load_route_transport_package(TOY_CONFIG)
    runtime_from_config = load_route_transport_package_from_config(
        load_route_transport_package_config(TOY_CONFIG)
    )

    assert isinstance(runtime_from_path, RouteTransportPackage)
    assert isinstance(runtime_from_path.support, SupportRuntime)
    assert isinstance(runtime_from_path.get_history("h_src_mid"), HistoryDistributionRuntime)
    assert isinstance(
        runtime_from_path.get_continuation("k_mid_end"),
        ContinuationKernelRuntime,
    )
    assert runtime_from_path.package_id == "toy_route_transport"
    assert runtime_from_config.interface_ids() == runtime_from_path.interface_ids()


def test_runtime_enumeration_is_deterministic() -> None:
    runtime = load_route_transport_package(TOY_CONFIG)

    assert runtime.interface_ids() == ("src", "mid", "end")
    assert runtime.history_ids() == ("h_src_mid",)
    assert runtime.continuation_ids() == ("k_mid_end", "loop_end")
    assert runtime.loop_ids() == ("end_loop",)


def test_history_support_projection_is_exact() -> None:
    runtime = load_route_transport_package(TOY_CONFIG)

    assert runtime.get_history_distribution("h_src_mid") == OrderedDict(
        [
            ("q0", Fraction(1, 8)),
            ("q1", Fraction(3, 8)),
            ("q2", Fraction(1, 2)),
        ]
    )
    assert runtime.project_history_to_support("h_src_mid") == OrderedDict(
        [
            ("A", Fraction(1, 2)),
            ("B", Fraction(1, 2)),
        ]
    )


def test_event_statistics_are_exact() -> None:
    runtime = load_route_transport_package(TOY_CONFIG)

    assert runtime.evaluate_event_statistic("h_src_mid", "indicator_A") == Fraction(1, 2)
    assert runtime.evaluate_event_package("h_src_mid") == OrderedDict(
        [
            ("indicator_A", Fraction(1, 2)),
            ("support_bias", Fraction(3, 2)),
        ]
    )


def test_history_continuation_composition_is_exact() -> None:
    runtime = load_route_transport_package(TOY_CONFIG)

    composed = runtime.compose_history_with_continuation(
        "h_src_mid",
        "k_mid_end",
        new_id="h_src_end",
    )

    assert composed == HistoryDistributionRuntime(
        history_id="h_src_end",
        source_interface_id="src",
        target_interface_id="end",
        probabilities=(
            Fraction(1, 8),
            Fraction(1, 4),
            Fraction(5, 8),
        ),
    )


def test_continuation_composition_is_exact() -> None:
    runtime = load_route_transport_package(TOY_CONFIG)

    composed = runtime.compose_continuations(
        "k_mid_end",
        "loop_end",
        new_id="k_mid_end_then_loop",
    )

    assert composed == ContinuationKernelRuntime(
        continuation_id="k_mid_end_then_loop",
        source_interface_id="mid",
        target_interface_id="end",
        kernel=(
            (Fraction(0, 1), Fraction(1, 1), Fraction(0, 1)),
            (Fraction(0, 1), Fraction(0, 1), Fraction(1, 1)),
            (Fraction(0, 1), Fraction(1, 2), Fraction(1, 2)),
        ),
    )


def test_invalid_typed_compositions_fail_cleanly() -> None:
    runtime = load_route_transport_package(TOY_CONFIG)

    with pytest.raises(CompositionTypeError, match="cannot compose history"):
        runtime.compose_history_with_continuation("h_src_mid", "loop_end")

    with pytest.raises(CompositionTypeError, match="cannot compose continuation"):
        runtime.compose_continuations("loop_end", "k_mid_end")
