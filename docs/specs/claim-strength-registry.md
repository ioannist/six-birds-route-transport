# Claim-Strength Registry

## Purpose

`claim-strength-registry.v1` records the strongest current claim supported on each axis, together with the evidence object that justifies it and the caveats that bound how the claim should be interpreted.

## Versioning

- Version field: `registry_format_version`
- Initial value: `claim-strength-registry.v1`

## Required fields

- `registry_format_version: str`
- `registry_id: str`
- `entries: list[{claim_id, axis, claim_level, best_evidence_row_id, primary_artifact_refs}]`

## Entry semantics

Each entry must provide:

- `claim_id`
- `axis`
- `claim_level`
- `best_evidence_row_id`
- `primary_artifact_refs`
- optional `supporting_artifact_refs`
- `caveat_flags`
- optional `notes`

## Validation notes

- exactly one claim-strength entry should be present per axis
- caveats are mandatory where the axis evidence has a known interpretation bound
- TH6 should keep the packaging caveat visible in this registry
