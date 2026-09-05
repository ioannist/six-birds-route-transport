from __future__ import annotations


class HolonomyMemoryControlsError(RuntimeError):
    """Base exception for holonomy-with-memory control and audit hooks."""


class ControlInputMismatchError(HolonomyMemoryControlsError):
    """Raised when control-hook inputs cannot be compared coherently."""
