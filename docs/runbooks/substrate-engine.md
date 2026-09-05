# Substrate Engine

## Config concepts
T15 introduces a raw substrate layer with its own `substrate-config` contract. A config defines a finite hidden-state space, named preparations as initial distributions, named actions as transition kernels, named deterministic lenses as state-to-label readouts, and named protocols as finite action sequences.

## Raw run concepts
The engine emits `substrate-run` artifacts, not `observation-trace` artifacts. A raw substrate run records one preparation, one protocol, one seed, and a finite set of trajectories. Each trajectory stores the sampled initial hidden state plus per-step `action_id`, `state_before`, `state_after`, and the lens readouts emitted from `state_after`.

## How to run the engine
Use `python -m sixbirds_event substrates run <config.json> --preparation <prep_id> --protocol <protocol_id> --trajectories <n> --seed <seed> --category search --label <label>`. If `--trajectories` or `--seed` are omitted, the engine uses config defaults when present, otherwise `1` trajectory and seed `0`.

## Produced artifacts
Each substrate run goes through the existing run registry and writes:
- `substrate-run.json`
- `substrate-summary.json`
- `run-manifest.json`

The summary reports `config_id`, config path, preparation, protocol, seed, trajectory count, total steps, hidden-state visit counts, and lens outcome counts.

## Difference from the observation-trace layer
The raw substrate engine does not assume that contexts, tests, events, downstream probes, or routes have already been identified. It records only hidden-state trajectories and deterministic lens readouts. Later discovery tickets consume these raw runs to infer candidate contexts/tests/events before any `observation-trace` artifact is emitted.
