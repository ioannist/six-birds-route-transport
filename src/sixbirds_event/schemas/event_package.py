from __future__ import annotations

import math
from typing import Literal

from pydantic import Field, field_validator, model_validator

from .common import (
    MetadataValue,
    SixBirdsModel,
    collect_list_duplicates,
    ensure_metadata_shape,
)


class Atom(SixBirdsModel):
    atom_id: str
    label: str | None = None


class Context(SixBirdsModel):
    context_id: str
    label: str | None = None
    atoms: list[Atom]

    @field_validator("atoms")
    @classmethod
    def validate_atoms(cls, atoms: list[Atom]) -> list[Atom]:
        if not atoms:
            raise ValueError("atoms must not be empty")
        atom_ids = [atom.atom_id for atom in atoms]
        duplicates = collect_list_duplicates(atom_ids)
        if duplicates:
            raise ValueError(
                f"duplicate atom_id values in context: {', '.join(duplicates)}"
            )
        return atoms


class Event(SixBirdsModel):
    event_id: str
    context_id: str
    atom_ids: list[str] = Field(default_factory=list)
    label: str | None = None

    @field_validator("atom_ids")
    @classmethod
    def validate_atom_ids(cls, atom_ids: list[str]) -> list[str]:
        duplicates = collect_list_duplicates(atom_ids)
        if duplicates:
            raise ValueError(f"duplicate atom_ids in event: {', '.join(duplicates)}")
        return atom_ids


class EqualityProposal(SixBirdsModel):
    proposal_id: str
    left_event_id: str
    right_event_id: str
    constraint_kind: Literal["hard", "soft"]
    weight_key: str | None = None
    notes: str | None = None


class AuditMetadata(SixBirdsModel):
    created_at: str
    created_by: str | None = None
    source: str | None = None
    checksum: str | None = None


class EventPackageInstance(SixBirdsModel):
    instance_format_version: str
    instance_id: str
    contexts: list[Context]
    events: list[Event]
    equality_proposals: list[EqualityProposal] = Field(default_factory=list)
    weights: dict[str, float] = Field(default_factory=dict)
    notes: str | None = None
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)
    audit: AuditMetadata

    @model_validator(mode="after")
    def validate_instance(self) -> "EventPackageInstance":
        if self.instance_format_version != "event-package-instance.v1":
            raise ValueError(
                "instance_format_version must equal 'event-package-instance.v1'"
            )
        if not self.contexts:
            raise ValueError("contexts must not be empty")
        if not self.events:
            raise ValueError("events must not be empty")

        ensure_metadata_shape(self.metadata)

        if any(
            isinstance(weight, bool) or not math.isfinite(weight) or weight < 0
            for weight in self.weights.values()
        ):
            raise ValueError("weights must be finite and non-negative")

        context_by_id = {context.context_id: context for context in self.contexts}
        if len(context_by_id) != len(self.contexts):
            raise ValueError("context_id values must be unique")

        event_by_id = {event.event_id: event for event in self.events}
        if len(event_by_id) != len(self.events):
            raise ValueError("event_id values must be unique")

        proposal_ids = [proposal.proposal_id for proposal in self.equality_proposals]
        duplicates = collect_list_duplicates(proposal_ids)
        if duplicates:
            raise ValueError(
                f"proposal_id values must be unique: {', '.join(duplicates)}"
            )

        weight_keys = set(self.weights)

        for event in self.events:
            context = context_by_id.get(event.context_id)
            if context is None:
                raise ValueError(
                    f"event '{event.event_id}' references unknown context_id '{event.context_id}'"
                )
            context_atom_ids = {atom.atom_id for atom in context.atoms}
            if not set(event.atom_ids).issubset(context_atom_ids):
                raise ValueError(
                    f"event '{event.event_id}' atom_ids must be a subset of context '{context.context_id}' atoms"
                )

        for proposal in self.equality_proposals:
            if proposal.left_event_id not in event_by_id:
                raise ValueError(
                    f"proposal '{proposal.proposal_id}' references unknown left_event_id '{proposal.left_event_id}'"
                )
            if proposal.right_event_id not in event_by_id:
                raise ValueError(
                    f"proposal '{proposal.proposal_id}' references unknown right_event_id '{proposal.right_event_id}'"
                )
            if proposal.constraint_kind == "hard":
                if proposal.weight_key is not None:
                    raise ValueError(
                        f"proposal '{proposal.proposal_id}' with hard constraint_kind must not carry weight_key"
                    )
            else:
                if proposal.weight_key is None:
                    raise ValueError(
                        f"proposal '{proposal.proposal_id}' with soft constraint_kind must carry weight_key"
                    )
                if proposal.weight_key not in weight_keys:
                    raise ValueError(
                        f"proposal '{proposal.proposal_id}' weight_key '{proposal.weight_key}' must exist in weights"
                    )

        return self
