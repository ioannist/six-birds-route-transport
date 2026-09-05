from __future__ import annotations

from .exceptions import (
    InvalidHistorySelectionError,
    LoopActionUndefinedError,
    MissingEventPackageError,
    RouteTransportAnalysisError,
    TransportMapNotWellDefinedError,
    TransportMapUndefinedError,
)
from .loops import (
    LoopActionResult,
    LoopMetricResult,
    compute_current_loop_action,
    compute_loop_action_metrics,
    compute_predictive_loop_action,
)
from .metrics import DiscrepancyMetricResult, compute_exact_max_abs_future_gap
from .quotients import (
    EquivalenceClass,
    InterfacePartition,
    MemoryWitness,
    compute_current_partition,
    compute_predictive_partition,
    enumerate_memory_witnesses,
    predictive_refines_current,
)
from .signatures import (
    CurrentSignature,
    FutureSignature,
    SignatureKey,
    compute_current_signature,
    compute_current_signature_for_history,
    compute_future_signature,
    compute_future_signature_for_history,
    resolve_interface_history_ids,
)
from .transport import (
    ClassTransportImage,
    ClassTransportMap,
    compute_current_transport_map,
    compute_predictive_transport_map,
)

__all__ = [
    "ClassTransportImage",
    "ClassTransportMap",
    "CurrentSignature",
    "DiscrepancyMetricResult",
    "EquivalenceClass",
    "FutureSignature",
    "InterfacePartition",
    "InvalidHistorySelectionError",
    "LoopActionResult",
    "LoopActionUndefinedError",
    "LoopMetricResult",
    "MemoryWitness",
    "MissingEventPackageError",
    "RouteTransportAnalysisError",
    "SignatureKey",
    "TransportMapNotWellDefinedError",
    "TransportMapUndefinedError",
    "compute_current_loop_action",
    "compute_current_partition",
    "compute_current_signature",
    "compute_current_signature_for_history",
    "compute_current_transport_map",
    "compute_exact_max_abs_future_gap",
    "compute_future_signature",
    "compute_future_signature_for_history",
    "compute_loop_action_metrics",
    "compute_predictive_loop_action",
    "compute_predictive_partition",
    "compute_predictive_transport_map",
    "enumerate_memory_witnesses",
    "predictive_refines_current",
    "resolve_interface_history_ids",
]
