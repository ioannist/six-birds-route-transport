from __future__ import annotations

from pathlib import Path

from ..schemas import RouteTransportPackageConfig
from ..validation import load_route_transport_package_config
from .runtime import RouteTransportPackage


def load_route_transport_package_from_config(
    config: RouteTransportPackageConfig,
) -> RouteTransportPackage:
    return RouteTransportPackage.from_config(config)


def load_route_transport_package(path: str | Path) -> RouteTransportPackage:
    config = load_route_transport_package_config(path)
    return load_route_transport_package_from_config(config)
