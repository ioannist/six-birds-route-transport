from __future__ import annotations


class RouteTransportAnalysisError(RuntimeError):
    """Base exception for exact route-transport analysis operations."""


class MissingEventPackageError(RouteTransportAnalysisError):
    """Raised when an analysis requires an undeclared interface event package."""


class InvalidHistorySelectionError(RouteTransportAnalysisError):
    """Raised when a requested history subset is invalid for an interface analysis."""


class TransportMapUndefinedError(RouteTransportAnalysisError):
    """Raised when a class transport image is not representable in the target universe."""


class TransportMapNotWellDefinedError(RouteTransportAnalysisError):
    """Raised when a class transport map is not well-defined on a source class."""


class LoopActionUndefinedError(RouteTransportAnalysisError):
    """Raised when a requested loop action cannot be defined on the chosen universe."""
