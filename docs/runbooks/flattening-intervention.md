# Flattening Intervention Runbook

## Purpose

The flattening / completion intervention tests whether visible route dependence or
non-confluence at a finite observation horizon is removable by appending a small
explicit settling policy to the protocol.

## Intervention logic

1. Run the source substrate config with the before protocol.
2. Extract route IDs from an observable route lens at a fixed route step.
3. Extract endpoint outcomes from an observable endpoint lens at a fixed endpoint step.
4. Build a before RM trace from those observable route and endpoint labels.
5. Run context discovery and shared-event package building on the before raw run.
6. Compute structural, statistical, and RM metrics where applicable.
7. Derive the after protocol by appending the configured completion action a fixed
   number of times.
8. Rerun the substrate simulation with the after protocol.
9. Rebuild the route trace, discovered contexts, event package, and available metrics.
10. Compare before vs after without collapsing unsupported statuses into zeros.

## Completion policy

This ticket uses append-only completion:

- before protocol: source protocol from the intervention input
- after protocol: before protocol plus `append_action_id` repeated
  `append_repetitions` times

## Produced artifacts

The bundle writes at minimum:

- `before-route-trace.json`
- `after-route-trace.json`
- `comparison-summary.json`
- `comparison-note.md`
- `result-note.json`
- `run-manifest.json`

It also references before/after raw-run, discovery, package-build, structural, and
statistical sub-run artifacts.

## Comparison outcomes

- `repairable`
  - route dependence decreases materially after completion and the after package is
    structurally feasible with `gpd_str = 0`
- `weakened`
  - route dependence or structural deficit improves but the issue does not fully clear
- `robust`
  - the available evidence does not show meaningful improvement

If a metric is unavailable, the bundle preserves explicit statuses such as
`unsolved`, `insufficient_data`, or `not_applicable`.

## Difference from hidden-record intervention

- Hidden-record intervention exposes a previously collapsed bookkeeping variable in the
  package itself.
- Flattening intervention changes the protocol horizon by appending a small explicit
  completion policy, then rebuilds the discovery/package pipeline from the new raw
  runs.
