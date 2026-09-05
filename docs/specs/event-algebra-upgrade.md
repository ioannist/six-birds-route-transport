# Event Algebra Upgrade

## Purpose
This spec defines how discovery-side event families move from sparse bases to either full finite Boolean algebras or explicitly incomplete conservative truncations.

## Version
- Logical config/version label: `event-algebra-upgrade.v1`

## Data model
The upgrade is carried by event-generation thresholds embedded in `discovered-event-family` builds.

### Required fields
| Field | Type | Constraints |
| --- | --- | --- |
| `event_algebra_mode` | string | One of `full_powerset`, `conservative_truncation`, or `auto`. |
| `max_full_powerset_atom_count` | integer | Positive threshold used only when `event_algebra_mode = auto`. |
| `max_union_size` | integer | Truncation cap for proper unions in conservative fallback modes. |
| `match_empty_for_inference` | boolean | Whether generated empty events are eligible for cross-context matching. |
| `match_full_for_inference` | boolean | Whether generated full events are eligible for cross-context matching. |
| `include_empty_and_full_in_truncation` | boolean | Whether fallback truncation still emits empty/full events. |

### Invariants
- `full_powerset` must generate exactly `P(A_c)` for each accepted context.
- `auto` must use `full_powerset` whenever `|A_c| <= max_full_powerset_atom_count`.
- Any truncation mode must be marked incomplete in the coverage output and must report exact expected-vs-generated counts.
- Generation and matching remain separate:
  - generation may include all events;
  - match eligibility may exclude empty/full events by policy.

## Event kind semantics
- `empty`: zero retained atoms.
- `singleton`: exactly one retained atom.
- `proper_coarse`: at least two retained atoms, but not the full atom set.
- `full`: exactly the full retained atom set.

## Minimal valid example
```json
{
  "event_algebra_mode": "full_powerset",
  "max_full_powerset_atom_count": 6,
  "max_union_size": 2,
  "match_empty_for_inference": false,
  "match_full_for_inference": false,
  "include_empty_and_full_in_truncation": true
}
```

## Validation notes
- Reject truncation outputs that claim completeness.
- Reject `full_powerset` outputs whose generated event count differs from `2^|A_c|`.
- Reject event-kind metadata inconsistent with retained atom IDs or event size.
