from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from .common import (
    MetadataValue,
    SixBirdsModel,
    ensure_metadata_shape,
    ensure_repo_relative_mapping,
)


class SoftwareVersion(SixBirdsModel):
    python: str
    package: str
    tooling: dict[str, str] = Field(default_factory=dict)


class RunManifest(SixBirdsModel):
    manifest_format_version: str
    run_id: str
    timestamp: str
    command: list[str]
    seed: int
    input_artifacts: dict[str, str]
    output_artifacts: dict[str, str]
    software_version: SoftwareVersion
    status: Literal["pending", "running", "succeeded", "failed", "canceled"]
    git_commit: str | None = None
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_manifest(self) -> "RunManifest":
        if self.manifest_format_version != "run-manifest.v1":
            raise ValueError("manifest_format_version must equal 'run-manifest.v1'")
        if not self.command:
            raise ValueError("command must not be empty")
        if any(not isinstance(item, str) for item in self.command):
            raise ValueError("command must contain only strings")
        if not isinstance(self.seed, int) or isinstance(self.seed, bool):
            raise ValueError("seed must be an integer")

        ensure_repo_relative_mapping(self.input_artifacts, field_name="input_artifacts")
        ensure_repo_relative_mapping(
            self.output_artifacts, field_name="output_artifacts"
        )
        ensure_metadata_shape(self.metadata)

        if "python" not in self.software_version.model_dump():
            raise ValueError("software_version.python is required")
        if "package" not in self.software_version.model_dump():
            raise ValueError("software_version.package is required")

        return self
