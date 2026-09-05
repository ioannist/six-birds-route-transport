from __future__ import annotations

from pydantic import Field, model_validator

from .common import (
    MetricValue,
    MetadataValue,
    SixBirdsModel,
    ensure_metadata_shape,
    ensure_metric_shape,
    ensure_repo_relative_mapping,
)


class ResultNote(SixBirdsModel):
    note_format_version: str
    note_id: str
    run_id: str
    instance_ids: list[str]
    metrics: dict[str, MetricValue]
    interpretation: str
    caveats: list[str] = Field(default_factory=list)
    artifact_refs: dict[str, str]
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_note(self) -> "ResultNote":
        if self.note_format_version != "result-note.v1":
            raise ValueError("note_format_version must equal 'result-note.v1'")
        if not self.instance_ids:
            raise ValueError("instance_ids must not be empty")
        if len(set(self.instance_ids)) != len(self.instance_ids):
            raise ValueError("instance_ids must be unique")
        if not self.artifact_refs:
            raise ValueError("artifact_refs must not be empty")

        ensure_metric_shape(self.metrics)
        ensure_repo_relative_mapping(self.artifact_refs, field_name="artifact_refs")
        ensure_metadata_shape(self.metadata)
        return self
