from __future__ import annotations


class RouteTransportRuntimeError(RuntimeError):
    """Base exception for the exact route-transport runtime layer."""


class RouteTransportLookupError(RouteTransportRuntimeError):
    """Raised when a requested runtime object cannot be found."""


class CompositionTypeError(RouteTransportRuntimeError):
    """Raised when interface-typed runtime composition is invalid."""
