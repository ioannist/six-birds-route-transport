# To Create a Stone with Six Birds: Emergent Geometric and Thermodynamic Regimes from a Minimal Stochastic Substrate

This repository contains the **ladder/scaling instantiation** for the paper:

> **To Create a Stone with Six Birds: Emergent Geometric and Thermodynamic Regimes from a Minimal Stochastic Substrate**
>
> Archived at: TBD
>
> DOI: 10.5281/zenodo.18838994

This project studies emergence from a minimal stochastic substrate using manifest-controlled audits across four sizes, with induced macro kernels, multiscale rung scans, and ablations over a six-primitive closure interaction algebra. The current paper dataset union contains 2307 runs: an exhaustive suite for \(n\in\{32,64,128\}\) and a selected scaling suite at \(n=256\).

## What this repository provides

- **Rust simulation engine** for substrate dynamics, closure interactions, and per-run audit outputs (`crates/`).
- **Campaign execution + audit extraction tools** (`analysis/`), including JSONL extraction/merge with provenance preserved.
- **Canonical campaign artifacts** under `lab/runs/campaign_v3/` (waves 1/2/3 and merged `audits_all.jsonl`).
- **Manifest-driven paper figdata pipeline** (`paper/scripts/build_figdata_campaign_v3.py`) producing canonical `scan_rung_table` and `run_summary_table`.
- **Regenerated paper assets** (F1--F8, T1--T6) and single-file manuscript source (`paper/main.tex`, no section/table includes).
- **Submission micro-assets + QA** (`paper/submission/*`, lint/flatten reports, artifact manifests).

## Compute requirements

On a 96-thread machine, reproducing the full campaign takes approximately:
- **~1 day** for the \(n\in\{32,64,128\}\) exhaustive suite.
- **~4 days** for the \(n=256\) scaling suite.

## Scope and limitations

- The \(n\le 128\) portion is exhaustive (69 configs \(\times\) 3 sizes \(\times\) 10 seeds).
- The \(n=256\) portion is a selected scaling suite (controls + targeted mechanisms), not a full 69-config ablation set.
- Wave 2 has 26 truncated logs missing `KEY_AUDIT_JSON`; this is tracked explicitly in `paper/figdata/wave2_missing_audit_logs.csv` and propagated into coverage/QA outputs.
- Data-availability DOI and archive metadata are still placeholders (`TBD`) pending final deposit.

## Install

Build the Rust workspace:

```bash
cargo build --release
```

Python analysis scripts assume a scientific Python environment with at least: `numpy`, `pandas`, `matplotlib` (and `scipy` where available).

## Test

Run workspace tests:

```bash
cargo test --workspace
```

Run manuscript lint/consistency checks:

```bash
python3 paper/scripts/paper_lint.py
python3 paper/scripts/build_flatten_manifest.py
```

## Run experiments

Single run:

```bash
target/release/runner --exp EXP-112 --seed 0 --scale 128
```

Single config run:

```bash
target/release/runner --exp EXP-112 --seed 0 --scale 256 --config baseline
```

Batch from manifest:

```bash
python3 analysis/run_batch.py run \
  --jobs lab/runs/campaign_v3/wave_3/manifest.json \
  --parallelism 44 \
  --timeout 172800 \
  --output-dir lab/runs/campaign_v3
```

Extract and merge audits (provenance-preserving):

```bash
python3 analysis/collect_audits.py --input-dir lab/runs/campaign_v3/wave_2/wave_2 --output lab/runs/campaign_v3/wave_2/audits.jsonl
python3 analysis/collect_audits.py \
  --merge lab/runs/campaign_v3/wave_1/audits.jsonl lab/runs/campaign_v3/wave_2/audits.jsonl lab/runs/campaign_v3/wave_3/audits.jsonl \
  --no-dedup-cross-exp \
  --output lab/runs/campaign_v3/audits_all.jsonl
```

Rebuild canonical paper figdata:

```bash
python3 paper/scripts/build_figdata_campaign_v3.py \
  --audits lab/runs/campaign_v3/audits_all.jsonl \
  --manifest paper/figdata/paper_dataset_manifest.json \
  --outdir paper/figdata \
  --force
```

## Build paper

```bash
make -C paper clean
make -C paper pdf
```

Output:

- `paper/main.pdf`

## Package snapshot

```bash
bash scripts/package_repo_snapshot.sh
```

Outputs versioned archive files at repository root:

- `six-birds-ladder_snapshot_v<NN>.zip`
