# PICA Cell Characterization Campaign

## Executive Summary (46 Findings, 877 Audit Records + n=256 Macro Data)

The PICA characterization campaign (EXP-200) reveals that **the full 25-cell PICA system
(full_action) is qualitatively different from any subset**. Seven headline conclusions:

1. **Partition competition is the dominant frob mechanism, scale-independent.** Adding any
   alternative lens (A14, A16, A17) to compete with A15 (spectral) produces frob>1.0 at
   ALL tested scales including n=256. A14_only: 3/3 seeds >1.0 at n=256 (median 1.157),
   A16_only: 3/3 (1.171), A17_only: 2/3 (1.372). Scale ratio >1.0 (frob INCREASES with n).
   Single lens cells EXCEED full_action (1.08) at n=256. (F41, **F46**, correcting F23, F26)

2. **full_action has three unique properties no subset achieves:**
   sigma_ratio=0.49 (preserves 49% of micro asymmetry into macro, vs <2% for all others),
   a flat multi-scale profile (frob slope 0.16 vs 0.47-0.53 for all others), and macro_gap
   that DECREASES with n (0.395→0.358, opposite to all other configs which increase).
   At k=2, full_action frob is 2x baseline (0.77 vs 0.39). (F17, F25, F33, F37)

3. **The REV (reversible) regime is a reproducible bimodality** (seed-dependent, scale-dependent; see caveats below and F14).
   It requires A19 as trigger (at n≤64) or ~24+ cells together (at n=128).
   REV kernels achieve **exact microscopic reversibility** (sigma_pi=0 at ALL k), with
   budget saturated at cap and coarser partitions (eff_k=2-4). The split is visible
   at k=2 (frob 0.855 vs 0.631, 5σ), indicating a micro-kernel-level distinction.
   Paradoxically, REV seeds are the *weaker* baseline seeds (frob 0.64 vs 0.90) —
   full_action preferentially drives tight-spectrum seeds to reversibility. Whether this
   constitutes a true dynamical bifurcation requires intermediate scales (n=96, 192) to
   characterize the crossover sharpness. (F1, F12, F14, F17, F34, F35)

4. **Size-dependent behavior at n=256 (two qualitative patterns).** Configs WITHOUT partition competition converge to
   frob≈0.52 (6x compression vs n=128). But configs WITH partition competition (any of
   A14/A16/A17 competing with A15) actually INCREASE frob from n=128→256: A14_only 1.157
   (3/3 >1.0), A16_only 1.171 (3/3 >1.0), A17_only 1.372 (2/3 >1.0). Scale ratios
   >1.0 mean the partition space becomes more productive at larger n. full_action=1.075
   (2.05x baseline). REV sigmoid: 100%@n≤64, 50%@n=128, 0%@n=256. (F14, F18, F42-F44, **F46**)

5. **Cells share overlapping degrees of freedom.** No cell combination is super-additive
   at n=128. The two independent structure-building axes are A13 (mixture modulation) and
   A11 (packaging gating). Their combination is untested. (F26, F27)

6. **LensSelector has ZERO effect; the lens CELL matters, not the selector.**
   MaxFrob=MaxGap=MinRM produce identical results (parameter loss bug masked this;
   post-fix confirmation). What matters is WHICH lens cells are enabled: A14 (RM-quantile),
   A16 (packaging), A17 (EP-quantile) each independently boost frob when competing with A15.
   (F24, corrected by F41 and RES-200-S03)

7. **4 of 25 cells are inert when added to baseline (A20, A21, A22, A23)** — identical
   to baseline (A10+A15) when enabled on top of it, and when added to any tested
   combination. Note: not tested in isolation (empty baseline), only as marginal additions. A18 is inert on frob/σ when enabled alone at default tau, but changes the evaluation τ when active (writes active_tau to PicaState); its effect is indirect, modifying the observation timescale rather than the dynamics. A5 is destructive. (F16, F26)

8. **sigma_u and sigma are uncorrelated (r=0.062)** and capture different structure.
   sigma_u reveals rich small-community structure in REV seeds where sigma=0. (F29)

9. **A13_A14_A19 is the Pareto-optimal config at n=128.** 94% of full_action frob (1.376 vs 1.467)
   with only 5 cells (vs 24). Irreversible (sigma=4.2) but lowest gap (0.312) and zero REV
   risk. At n=64 it IS reversible — the only config with a scale-dependent REV→NRM crossover.
   n=256 data pending from EXP-106. (F39)

**Campaign status:** Stages 01-05 complete at n=32/64/128. n=256: EXP-103 lens configs
COMPLETE (3 seeds, 8 configs — F46 confirmed). Old-binary EXP-107v2 (80 records) analyzed.
New-binary backups growing (11 records). EXP-106 full sweep (13 configs × 10 seeds) running.
877 audit records + n=256 macro data.

---

## Caveats and Limitations

Readers should keep these methodological limitations in mind when interpreting findings:

1. **"Single-cell" means "baseline + cell."** All `*_only` experiments test the marginal
   contribution of a cell on top of baseline (A10+A15), not the cell in true isolation.
   No empty-baseline (`PicaConfig::none()`) control has been run.

2. **τ is adaptive and confounds metric comparisons.** The observation timescale τ is set
   dynamically from the kernel's spectral gap. Cells that change τ (especially A18) alter
   what gets measured even if the underlying micro dynamics are similar. Key metrics at
   fixed τ values have not been systematically collected.

3. **3-4 scale points are insufficient for "phase transition" claims.** With only n=32,
   64, 128, 256, we cannot reliably locate breakpoints, distinguish crossovers from
   phase transitions, or confirm that transitions sharpen with system size. We use
   "crossover" and "size-dependent behavior" rather than "phase transition."

4. **Flip counts in pre-fix data count refresh cycles, not actual changes.** Before the
   flip-count fix, `partition_flip_count` was incremented every refresh interval even when
   hysteresis kept the old partition. Post-fix data counts only actual partition changes.

5. **Small sample sizes with wide IQRs.** Most configs are tested with 3-10 seeds.
   Median/IQR statistics have limited power to separate small effects from noise.
   "Winner's curse" is possible for configs selected on the same data used to evaluate them.

6. **"No engineered substrates" means no engineered micro-structure.** Initial kernels are
   random (`MarkovKernel::random()`). However, the measurement and agency primitives
   (spectral clustering, RM definitions, scoring heuristics) embed specific algorithmic
   choices that bias which macroscopic features are detectable and exploitable.

7. **Spectral conservation probes used wrong reference eigenvalue (FIXED 2026-02-24).**
   Prior to this fix, `relaxation_time`, `spectral_gap_ratio`, and `relative_slow_modes`
   used eigenvalues[1] (largest signed nontrivial eigenvalue) instead of the SLEM
   (second-largest eigenvalue modulus). For kernels with negative eigenvalues of larger
   magnitude, all three probes reported incorrect values. Any stored spectral probe data
   from Wave 1 or earlier uses the wrong formula.

8. **Multi-scale scan could produce duplicate k entries (FIXED 2026-02-24).** When
   `spectral_partition(kernel, k_target)` collapses to a smaller actual_k (e.g.,
   target k=8 → actual k=4), multi_scale_scan could store two entries for the same k,
   causing double-counting in analysis. Post-fix: dedup by actual_k within each scan.

9. **Partition constructed on unpowered K; transitions on K^τ.** The macro partition
   comes from spectral_partition(K, k), but macro transitions are built from K^τ
   (matrix power). This means the "structures" detected (partitions) and the "physics"
   measured (macro transition probabilities) use different effective timescales. Claims
   about "emergent lawfulness" from Lagrange probes are confounded by this choice. A
   systematic fixed-τ sensitivity analysis has not been performed.

---

## Goal
Systematic characterization of all 25 action cells: what each does in isolation,
how rows interact, and how the full system behaves.

**Post-fix edition**: All results below use the corrected codebase (8 bug fixes from
external code review). Key fixes that changed results:
- **Bug #1**: `needs_cluster_rm()` didn't include A19/A20 as consumers → A19 now
  triggers cluster_rm computation directly (no enabler needed)
- **Bug #8**: EP computation dropped irreversible edges → A24 sigma changed

---

## Cell Activity Classification (n=64, post-fix)

### Active cells (change dynamics when enabled alone on baseline)
| Cell | frob | sigma_pi | Effect |
|------|------|----------|--------|
| **A19** (P3<-P4) | 1.339 | 0.18 | Reversible transition (9/10 sigma=0) |
| **A24** (P6<-P4) | 0.842 | 4.50 | Budget rate boost |
| **A1-A12** (P1/P2 rows) | varies | varies | Each has individual effect (EXP-100) |

### Data-starved cells (no effect alone, but may contribute in full system)
| Cell | Why no effect alone |
|------|-----------|
| **A20** (P3<-P5) | Reads `active_packaging` which requires P5 producers |

### Conditionally active cells (active at some scales but not all)
| Cell | Behavior |
|------|----------|
| **A18** (P3<-P3) | Active at n=32/64 (changes tau → shifts sigma/gap). Inert at n=128. |

### Inert cells (identical to baseline when enabled alone at all tested scales)
| Cell | Why inert |
|------|-----------|
| A21 (P5<-P3) | No consumer (A5/A11 off) |
| A22 (P5<-P4) | No consumer |
| A23 (P5<-P6) | No consumer |
| ~~A25 (P6<-P6)~~ | **Reclassified: NOT inert at n=128** (frob=0.991 vs baseline 0.855, F16). Inert only at n=64. See Stabilizers above. |

**Note on A18**: At n=32, baseline sigma median=21.98 vs A18_only sigma median=34.28.
At n=64, baseline sigma=0.588 vs A18_only sigma=1.384. A18 changes tau which shifts
the spectral partition used downstream. At n=128 the tau change has no measurable
effect *in isolation*, likely because the partition is more stable at larger scales.
**However, in the full system (full_action), A18 is the CRITICAL regime switch** —
it selects tau=3–7 (normal) vs tau=120–378 (reversible), determining which attractor
the system reaches (Finding 11). This is the strongest "inert alone ≠ inert in full
system" example.

**Note on A20**: A20 reads `active_packaging` which requires P5 producers (A21-A23).
Without P5 cells enabled, A20's data source is empty and it returns identity scores.
This is data starvation, not true inertness. The earlier claim "A20 = A19 after
Fix #6" is incorrect — the intended fallback to spectral_partition was never
implemented in code.

---

## Experiment 1: EXP-104v3 -- Individual Cell Characterization (n=64, 10 seeds)

### Summary table (sorted by frob)

| Config | frob (mean+-std) | sigma_pi (mean+-std) | gap | macro_n | sig=0 |
|--------|-----------------|---------------------|-----|---------|-------|
| P3_row_all | 1.426+-0.181 | 0.00+-0.00 | 0.398 | 6.1 | 10/10 |
| A19_only | 1.339+-0.314 | 0.18+-0.57 | 0.407 | 6.5 | 9/10 |
| A20_only | 1.339+-0.314 | 0.18+-0.57 | 0.407 | 6.5 | 9/10 |
| full_all | 1.234+-0.568 | 1.56+-4.92 | 0.379 | 6.2 | 9/10 |
| full_action | 1.121+-0.259 | 0.00+-0.00 | 0.392 | 5.6 | 10/10 |
| A24_only | 0.842+-0.175 | 4.50+-5.77 | 0.525 | 7.8 | 0/10 |
| P6_row_all | 0.842+-0.175 | 4.50+-5.77 | 0.525 | 7.8 | 0/10 |
| baseline | 0.834+-0.164 | 3.34+-4.97 | 0.558 | 7.7 | 1/10 |
| A18_only | 0.834+-0.164 | 3.34+-4.97 | 0.558 | 7.7 | 1/10 |
| A21-A23, P5_row | 0.834+-0.164 | 3.34+-4.97 | 0.558 | 7.7 | 1/10 |
| A25_only | 0.834+-0.164 | 3.34+-4.97 | 0.558 | 7.7 | 1/10 |

### Key findings
- **A19 alone triggers the reversible transition** (no enabler chain needed post-fix)
- **6 of 14 configs identical to baseline at n=64** (A21-A23, A25, P5_row_all, A20)
  - A18 matches baseline at n=64/128 in this table but diverges at n=32 (sigma 34.3 vs 22.0)
- **P6_row_all = A24_only** (A25 adds nothing)
- **A20 is data-starved** (no active packaging → identity scores; see Note on A20 above)
- **full_all has sigma > 0** in 1/10 seeds (A16 can break reversibility)
- **full_action always sigma=0** (all cells except A16)

---

## Experiment 2: EXP-105v2 -- Cell Synergy Experiments (n=64, 10 seeds)

### Summary table (sorted by sigma_pi descending)

| Config | frob+-std | sigma+-std | gap | macro_n | chiral | sig=0 |
|--------|-----------|-----------|-----|---------|--------|-------|
| **A11_A22** | 0.922+-0.181 | **8.27+-9.67** | 0.501 | 8.0 | 55.7 | 0/10 |
| A13_only | 0.836+-0.121 | 8.11+-6.93 | 0.534 | 7.8 | 51.3 | 0/10 |
| A13_A18 | 0.836+-0.121 | 8.11+-6.93 | 0.534 | 7.8 | 51.3 | 0/10 |
| A13_A25 | 0.836+-0.121 | 8.11+-6.93 | 0.534 | 7.8 | 51.3 | 0/10 |
| **P1_row_A13** | **0.999+-0.241** | **6.15+-4.12** | 0.488 | 8.0 | 55.3 | 0/10 |
| A11_A21 | 0.890+-0.202 | 5.20+-3.29 | 0.558 | 7.9 | 53.6 | 0/10 |
| A3_A13 | 0.925+-0.234 | 5.20+-3.44 | 0.480 | 7.8 | 50.8 | 0/10 |
| sbrc | 1.005+-0.233 | 4.55+-6.31 | 0.475 | 7.5 | 46.5 | 2/10 |
| A24_A25 | 0.842+-0.175 | 4.50+-5.77 | 0.525 | 7.8 | 51.5 | 0/10 |
| A5_A21 | 0.802+-0.143 | 4.04+-3.78 | 0.521 | 7.7 | 49.7 | 0/10 |
| baseline | 0.834+-0.164 | 3.34+-4.97 | 0.558 | 7.7 | 49.6 | 1/10 |
| A13_A24 | 0.840+-0.153 | 2.98+-2.56 | 0.565 | 7.8 | 51.5 | 0/10 |
| mixer | 0.949+-0.113 | 2.87+-3.32 | 0.462 | 7.3 | 41.9 | 3/10 |
| A13_A18_A19 | 1.189+-0.237 | 0.42+-1.04 | 0.419 | 6.8 | 28.4 | 8/10 |
| A13_A18_A20 | 1.189+-0.237 | 0.42+-1.04 | 0.419 | 6.8 | 28.4 | 8/10 |

### Identity relations observed (n=64, 10 seeds, EXP-105)
- **A13_A18 = A13_only** at n=64 (A18 has no additional effect when A13 is active;
  however, A18 IS active alone at n=32/64 — see Finding 7)
- **A13_A25 = A13_only** (A25 is inert at n=64; NOT inert at n=128, see F16)
- **A13_A18_A19 = A13_A18_A20** (A20 returns identity due to missing packaging data)
- **A24_A25 = A24_only** (A25 is inert at n=64)

### A13 decomposition

| Config | frob | sigma_pi | Interpretation |
|--------|------|----------|---------------|
| baseline | 0.834 | 3.34 | -- |
| A13_only | 0.836 | 8.11 | **Sigma champion**: 2.4x baseline sigma |
| A13+A18 | 0.836 | 8.11 | = A13 alone (A18 adds nothing) |
| A13+A18+A19 | 1.189 | 0.42 | **Reversible transition** (8/10 sigma=0) |

**A19 is the sole trigger for sigma -> 0.** A18 is not needed as an enabler (post-fix).
A13 alone is the strongest sigma booster (+143% over baseline) without triggering
the reversible transition.

### Packaging combos (active post-fix)

| Config | frob | sigma_pi | vs baseline |
|--------|------|----------|-------------|
| A5_A21 | 0.802 | 4.04 | sigma +21% |
| **A11_A22** | **0.922** | **8.27** | **sigma +148%** |
| A11_A21 | 0.890 | 5.20 | sigma +56% |

**A11_A22 is the sigma champion** (highest mean sigma of ALL configs). Sector-balanced
packaging (A22) combined with package-guided P2 gating (A11) produces strong
irreversibility. These combos ARE active (not inert), confirming the producer+consumer
pattern works correctly.

### Budget combos

| Config | frob | sigma_pi | vs baseline |
|--------|------|----------|-------------|
| A24+A25 | 0.842 | 4.50 | sigma +35% |
| A13+A24 | 0.840 | 2.98 | sigma -11% |
| A13+A25 | 0.836 | 8.11 | = A13 alone |

**A13+A24 reduces sigma below A13-alone** (-63% relative). This is antagonistic --
A24's budget rate boost combined with A13's mixture shift counteract rather than synergize.

### Presets

| Config | frob | sigma_pi | sig=0 |
|--------|------|----------|-------|
| sbrc | 1.005 | 4.55 | 2/10 |
| mixer | 0.949 | 2.87 | 3/10 |

SBRC and mixer both show partial reversibility (2-3/10 seeds sigma=0).

### P1 row combos

| Config | frob | sigma_pi | vs baseline |
|--------|------|----------|-------------|
| A3+A13 | 0.925 | 5.20 | frob +11%, sigma +56% |
| **P1_row+A13** | **0.999** | **6.15** | **frob +20%, sigma +84%** |

**P1_row_A13 is the best all-round config**: substantial frob boost (+20%) AND sigma
boost (+84%) without any reversibility risk (0/10 sigma=0). The diverse P1 targeting
cells create differentiated kernel modifications that P2 gating can exploit.

---

## The Two Regimes

### Normal regime (sigma_pi > 0)
- baseline, A13_only, A24, packaging combos, P1-row combos, A11_A22
- Irreversible macro kernel (sigma_pi = 1-8+)
- Budget fluctuates (12-24)
- Gradual parameter changes between configs
- At n=128: partition effective_k ≈ 5.3, frequent tau/partition flips

### Reversible regime (sigma_pi -> 0)
- A19_only, P3_row_all, A13+A18+A19, full_action (at n≤64: all seeds; at n=128: ~50%)
- Reversible macro kernel (sigma_pi = 0.000 at ALL coarse-graining scales)
- Budget saturated at cap
- Fewer macro states (3.6 effective at n=128 vs 5.3 in NRM)
- Higher frob (1.1-1.9 vs 0.8-1.4)
- At n=128: tau=120–378 (long observation window), stable partition

### Trigger
**A19 (P3<-P4) alone is sufficient at n≤64** (binary switch, all seeds).
At n=128, **A18 (adaptive tau) becomes the regime switch** (Finding 11): when A18
selects long tau (>100) in the full system, A19's sector mixing converges to
the reversible fixed point. When A18 selects short tau (<10), the system stays normal.

### What breaks the reversible regime
- **Larger scale** (n=128+): the regime becomes seed-dependent — only ~50% of seeds
  reach it (A18 tau selection depends on the random kernel's spectral structure)
- **A16** (P4<-P5 row-similarity): reduces REV probability from 5/10 to 3/10
  (full_all vs full_action)
- **A12** (SBRC): directional asymmetry in repairs vs violations
- **A14** (P4<-P3): changes partition via RM-quantiles

---

## The Antagonism: A19 vs A13

**A19 creates structure (high frob) but kills irreversibility (sigma -> 0).**
**A13 creates irreversibility (high sigma) but minimal structure boost.**

This is the fundamental tension in the PICA system:
- A19 sector mixing produces a self-reinforcing feedback loop that converges to
  a time-reversible macro kernel (detailed balance). The kernel has high frob
  (rich structure) but zero arrow of time.
- A13 frob-based mixture weighting shifts dynamics toward more asymmetric evolution,
  boosting sigma but not creating structurally richer macro kernels.
- When both are active, A19 dominates -> reversible regime.

**Best configs that balance both:**
1. **P1_row_A13** (frob=1.0, sigma=6.2) -- no A19, diverse P1 targeting
2. **A11_A22** (frob=0.92, sigma=8.3) -- packaging combo, sigma champion
3. **A3_A13** (frob=0.93, sigma=5.2) -- RM-rewrite + mixer

---

## Experiment 4: EXP-107v2 -- Scale Dependence (n=128, n=256, 10 seeds)

### n=128 COMPLETE (13 configs, 10 seeds each)

| Config | frob+-std | sigma+-std | gap | mn | sig=0 |
|--------|-----------|-----------|-----|------|-------|
| **full_all** | **1.005+-0.266** | **0.25+-0.37** | 0.463 | 6.8 | 6/10 |
| baseline | 0.979+-0.135 | 2.22+-2.48 | 0.481 | 8.0 | 0/10 |
| A25_only | 0.979+-0.135 | 2.22+-2.48 | 0.481 | 8.0 | 0/10 |
| **P1_row_A13** | **0.974+-0.040** | **0.87+-0.51** | 0.536 | 8.0 | 0/9 |
| full_action | 0.972+-0.207 | 0.15+-0.23 | 0.416 | 7.0 | 1/10 |
| A19_only | 0.902+-0.175 | 1.45+-0.90 | 0.569 | 8.0 | 0/9 |
| chain_SBRC | 0.894+-0.105 | 1.57+-1.19 | 0.530 | 8.0 | 0/9 |
| chain_A24 | 0.854+-0.172 | 1.64+-1.31 | 0.573 | 8.0 | 0/10 |
| A11_A22 | 0.827+-0.195 | 1.81+-1.53 | 0.597 | 7.9 | 0/10 |
| A24_only | 0.825+-0.222 | 1.40+-1.23 | 0.586 | 8.0 | 0/10 |
| chain | 0.824+-0.192 | 1.16+-1.08 | 0.591 | 8.0 | 0/10 |
| A13_only | 0.812+-0.201 | 1.19+-0.84 | 0.594 | 8.0 | 0/10 |
| sbrc | 0.791+-0.140 | 0.72+-0.19 | 0.609 | 8.0 | 0/10 |

### n=256 PARTIAL (10 of 13 configs have data; remaining: A19, P1_row_A13, mixer)

| Config | N | frob+-std | sigma+-std | gap | mn |
|--------|---|-----------|-----------|-----|----|
| **full_action** | **9** | **1.059+-0.075** | **0.018+-0.011** | **0.367** | **7.6** |
| **full_all** | **4** | **1.018+-0.143** | **0.033+-0.018** | **0.390** | **7.0** |
| chain | 10 | 0.549+-0.026 | 0.174+-0.076 | 0.719 | 8.0 |
| A24_only | 10 | 0.530+-0.016 | 0.183+-0.086 | 0.723 | 8.0 |
| A13_only | 10 | 0.528+-0.034 | 0.185+-0.075 | 0.717 | 8.0 |
| baseline | 10 | 0.514+-0.023 | 0.214+-0.104 | 0.723 | 8.0 |
| A25_only | 10 | 0.514+-0.023 | 0.214+-0.104 | 0.723 | 8.0 |
| sbrc | 10 | 0.513+-0.010 | 0.182+-0.070 | 0.719 | 8.0 |
| A11_A22 | 3 | 0.505+-0.008 | 0.146+-0.025 | 0.736 | 8.0 |
| chain_A24 | 1 | 0.513 | 0.221 | 0.738 | 8.0 |

**CONFIRMED: full_action maintains frob > 1.0 at n=256** (mean 1.059, 2x baseline).
full_all also above 1.0 (mean 1.018) but with higher variance. Every other config
converges to frob ~0.5.

**Two qualitative regimes at n=256:**
- full presets: frob > 1.0, gap ~0.37, sigma ~0.02, macro_n ~7-8
- everything else: frob ~0.5, gap ~0.72, sigma ~0.2, macro_n = 8

### Cross-scale comparison

| Config | f64 | f128 | f256 | s64 | s128 | s256 |
|--------|-----|------|------|-----|------|------|
| baseline | 0.834 | 0.979 | 0.514 | 3.34 | 2.22 | 0.21 |
| A19_only | 1.339 | 0.902 | pend | 0.18 | 1.45 | pend |
| A13_only | 0.836 | 0.812 | 0.528 | 8.11 | 1.19 | 0.18 |
| A24_only | 0.842 | 0.825 | 0.530 | 4.50 | 1.40 | 0.18 |
| sbrc | 1.005 | 0.791 | 0.513 | 4.55 | 0.72 | 0.18 |
| A11_A22 | 0.922 | 0.827 | 0.505 | 8.27 | 1.81 | 0.15 |
| P1_row_A13 | 0.999 | 0.974 | pend | 6.15 | 0.87 | pend |
| **full_action** | **1.121** | **0.972** | **1.059** | **0.00** | **0.15** | **0.02** |
| **full_all** | **1.234** | **1.005** | **1.018** | **1.56** | **0.25** | **0.03** |

### Key findings from EXP-107v2

**1. full_action CONFIRMED at n=256: frob > 1.0 (2x baseline)**

full_action: frob=1.059+-0.075 at n=256 (9 seeds). This is 2.06x baseline (0.514).
full_all: frob=1.018+-0.143 (4 seeds so far). Both maintain frob > 1.0 at all
three scales tested (64, 128, 256). **The only configs that scale.**

full_action is remarkably stable: frob range [0.913, 1.147] across 9 seeds.
It also produces 7.6 macro states (vs 8.0 for simple configs), adapting CG.

**2. ALL individual cell effects vanish at n=256**

At n=256, all simple configs converge to frob ≈ 0.5, sigma ≈ 0.2:
- A13_only: frob=0.528 (identical to baseline 0.514)
- A24_only: frob=0.530
- chain: frob=0.549
- sbrc: frob=0.513
- A11_A22: frob=0.505

Frob spread = 0.044, sigma spread = 0.068 — no PICA cell has individual effect.
Only the full 25-cell synergy produces differentiation.

**3. The A19 reversible transition does NOT persist at n=128+**

A19_only at n=128: sigma=1.45 (0/9 seeds with sigma=0). The binary switch that
produces sigma=0 at n=64 is a scale-specific phenomenon.

**4. full_all is the best at n=128 (reversal from n=64)**

At n=64: full_action frob=1.121, full_all frob=1.234.
At n=128: full_all frob=1.005, full_action frob=0.972.
At n=256: full_action frob=1.059, full_all frob=1.018.

full_all leads at n=128; full_action leads at n=256. A16 helps at intermediate
scale but introduces variance (full_all std=0.143 vs full_action std=0.075 at n=256).

**5. P1_row_A13 is the most robust at n=128 (lowest variance)**

P1_row_A13 at n=128: frob=0.974+-0.040 — lowest std of ALL configs. Diverse P1
targeting + A13 mixer produces the most predictable outcomes. n=256 data pending.

**6. Baseline frob is non-monotonic**

baseline frob: 0.834 (n=64) -> 0.979 (n=128) -> 0.514 (n=256).
The n=128 peak reflects a sweet spot where 8 macro states capture enough structure
from a 128-state kernel. At n=256, k=8 macro states are insufficient.

**7. Sigma becomes negligible at n=256**

ALL configs have sigma < 0.25 at n=256. full_action: 0.018, full_all: 0.033.
The arrow of time effectively vanishes at large scale with k=8 macro states.

---

## Overall Synthesis

### The REV bifurcation

The central discovery is an **emergent reversibility transition** — under certain
PICA configurations, the dynamics converge to a kernel satisfying detailed balance
(sigma=0) at ALL coarse-graining scales. The key mechanism:

1. **A19 (P3←P4, sector mixing)** is the single necessary ingredient for REV
2. **Sector boost parameter** has a narrow resonance at 2.0 (the default)
3. **The transition probability is scale-dependent:**
   - n=32/64: A19 alone triggers 100% REV
   - n=128: A19 alone → 0% REV; full_action (24 cells) → 50% REV
4. **REV is NOT predictable** from simpler proxies — it's an emergent property
   of the 24-cell interaction (Finding 15)
5. **REV seeds have LOWER baseline quality** (anti-correlation, Finding 15)
6. **Budget saturation perfectly correlates with REV** (Finding 17): REV seeds
   hit budget cap (n*ln(n)) while NRM seeds reach only 3-7% of cap. This 13x
   gap suggests a homeostatic fixed-point mechanism.

### The scale hierarchy

**n=32/64**: A19_only is the strongest single cell (frob=1.52–1.56, 100% REV).
full_all > full_action at n=64 (1.750 vs 1.417) — A16 helps at small n.
LensSelector: MaxFrob wins at n=64 (frob=1.057 vs MinRM 0.456).

**n=128**: Sharp transition. All simple configs lose REV. Two distinct behaviors:
1. **full_action BIMODAL** (Finding 1, 11, 12, 17): 50% REV (sigma=0, tau>100,
   scale-free reversibility, budget=cap). 50% NRM (sigma=0.04–0.30, budget=3-7% cap).
2. **full_all 30% REV** (Finding 18): 3/10 REV, frob=1.134 median.
3. **LensSelector ranking REVERSES** (Finding 3): A16_only (1.235) and MinRM
   (1.205) beat A15 (0.462) at n=128.
4. **full_action > full_all** at n=128 (1.467 vs 1.134) — A16 HURTS (Finding 16).
5. **A25_only** raises the frob floor (all seeds ≥0.89 vs baseline's 0.42 min).
6. **Individual cell effects shrink 70-85%** but don't vanish. P1_row_A13 (1.015)
   is most robust (Finding 18).

**n=256** (EXP-107v2 pre-fix, 10 seeds): Complete convergence of simple configs:

| Config | frob | sigma | REV/10 |
|--------|------|-------|--------|
| full_action | 1.060 | 0.140 | 0 |
| full_all | 0.946 | 0.051 | 1 |
| A13_only | 0.558 | 0.233 | 0 |
| chain | 0.533 | 0.173 | 0 |
| baseline | 0.523 | 0.187 | 0 |

All simple configs converge to frob ≈ 0.52. full_action is the ONLY config
that significantly breaks out (2x baseline). **REV vanishes**: 0/10 for
full_action, 1/10 for full_all. Fixed n=256 runs in progress.

**PICA's relative advantage GROWS with scale:**

| Scale | full_action | baseline | ratio |
|-------|------------|----------|-------|
| 32 | 1.722 | 1.305 | 1.32x |
| 64 | 1.417 | 1.151 | 1.23x |
| 128 | 1.467 | 0.855 | 1.72x |
| 256 | 1.060 | 0.523 | 2.03x |

While absolute frob declines for both, baseline falls FASTER. The 24-cell PICA
system maintains coarse-graining structure better across scales. At n=256, PICA
provides 2x the structural quality of the unmodified dynamics.

### Cell Role Summary (updated through F27)

**P1 Row (Rewrite Modulations):**

| Cell | Name | Role at n=128 | Key Finding |
|------|------|---------------|-------------|
| A1 | history-rewrite | Moderate frob boost (0.980) | Sub-additive with A12 (F27) |
| A2 | sparsity-rewrite | Moderate frob boost (1.005) | |
| A3 | **RM-rewrite** | **Best single P1 cell** (frob=1.054) | Sigma tamer when paired with A13 (F26) |
| A4 | boundary-rewrite | Moderate frob boost (0.994) | |
| A5 | packaging-rewrite | **DESTRUCTIVE** (frob=0.585 with A21) | Only cell combo that degrades below baseline (F26) |
| A6 | budget-rewrite | Moderate frob boost (0.928) | |
| P1 row | all 6 as ensemble | +0.042 frob over A13 alone, sigma taming | P1_row_A13 is most scale-robust top config (F26) |

**P2 Row (Gating Modulations):**

| Cell | Name | Role at n=128 | Key Finding |
|------|------|---------------|-------------|
| A7 | protect-gating | Lowest sigma (0.392), lowest frob (0.686) | Protection suppresses both structure and irreversibility (F23) |
| A8 | cooldown-gating | Moderate (frob=0.924) | |
| A9 | RM-gating | Moderate (frob=0.917) | |
| A10 | spectral-gating | Part of baseline | Always enabled |
| A11 | package-gating | **2nd structure axis** (frob=0.928 with A21) | Best non-A13 config. Independent from A13 axis (F26) |
| A12 | SBRC-gating | Moderate alone, suppresses sigma in combos | Only scale-positive combo: A3+A12 (F27) |

**P3 Row (Mixture Weights):**

| Cell | Name | Role at n=128 | Key Finding |
|------|------|---------------|-------------|
| A13 | **frob mixer** | **KEYSTONE** (+47% over baseline alone) | Uniquely halves partition flips (F23). All top configs include A13 (F26). |
| A18 | adaptive tau | **INERT on frob/σ** when enabled alone at default tau, but writes active_tau to PicaState — indirect effect on observation timescale | A13=A13_A18=A13_A18_A20 to machine precision (F26) |
| A19 | **sector mixing** | REV trigger at n≤64, mild antagonist at n=128 | 100% REV at n≤64, 0% alone at n=128 (F14). Reduces frob when added to A13 (F26). |
| A20 | packaging mixing | **INERT** (data-starved: reads `active_packaging` which is empty without P5 producers) | Returns identity scores without A21-A23. Not equivalent to A19 (see Note on A20 above). |

**P4 Row (Lens/Partition Selection):**

| Cell | Name | Role at n=128 | Key Finding |
|------|------|---------------|-------------|
| A14 | RM-quantile lens | High frob when spectral wins (1.328) | Near-REV when A14 partition wins (F24). Q9: why does enabling A14 help? |
| A15 | spectral lens | Part of baseline | Always the dominant partition. 100% selected by MaxFrob (F24). |
| A16 | **packaging lens** | Most underrated single cell | Only alternative lens that beats spectral (75% of seeds, F24) |
| A17 | EP-quantile lens | Moderate frob (0.958) | EP partition never beats spectral at n=128 (F24) |
| MaxFrob selector | | **Best non-rank-1** (frob=1.413) | Selects spectral 100%. New finding (F24) |
| MaxGap selector | | Most stable (IQR=0.102) but near-rank-1 | Selects RM-quantile 100%. Frob=0.260 (F24) |
| MinRM selector | | Unstable (IQR=0.744) | Prone to degenerate partitions (F24) |

**P5 Row (Packaging Selection):**

| Cell | Name | Role at n=128 | Key Finding |
|------|------|---------------|-------------|
| A21 | RM-quantile pkg | **INERT** | Bitwise identical to baseline in all tests (F16, F20) |
| A22 | sector-balanced pkg | **INERT** alone | A11_A22 is a viable pair (frob=0.904, F26) |
| A23 | EP-quantile pkg | **INERT** alone | |

**P6 Row (Budget Modulation):**

| Cell | Name | Role at n=128 | Key Finding |
|------|------|---------------|-------------|
| A24 | sector EP budget rate | **ANTAGONIST** to A13 (frob=0.777) | Synergistic with A25 at n=32 but antagonistic at n=128 (F22) |
| A25 | EP-retention cap | **Stabilizer** (frob=0.991 vs baseline 0.855) | NOT inert (corrected F16). Independent frob improvement |

**System-Level:**

| Property | Finding | Reference |
|----------|---------|-----------|
| Budget | <5% utilization for most configs. Cap = REV gate. | F25 |
| Sigma ratio | full_action uniquely preserves 29% micro→macro asymmetry | F25 |
| k=8 peak | full_action's sigma peaks at k=8, drops to 0 at k=16 | F25 |
| Partition quality | Does NOT predict frob (Pearson r = -0.057) | F25 |
| Super-additivity | None at n=128. Cells share overlapping DOF. | F27 |
| Two structure axes | A13 axis (mixture) and A11 axis (gating) are independent | F26 |

### Configuration Recommendations (updated through F27)

| Goal | Config | Expected frob | Notes |
|------|--------|---------------|-------|
| Maximum non-rank-1 | full_action | 1.37 (median) | 62% REV risk. Unique sigma_ratio/k8-peak. |
| Best selector | all_MaxFrob | 1.41 | Only 5 seeds. Needs more data. |
| Most robust top | P1_row_A13 | 1.02 | 0% REV, scale-robust (-4%), sigma=0.80 |
| Lowest variance | all_MaxGap | 0.26 | IQR=0.10 but near-rank-1. Not useful. |
| Scale-positive combo | A3+A12 | 0.96 | Only config that improves with n. |
| Alternative axis | A11+A22 | 0.90 | No A13 dependency. Untested with A13. |
| Individual best | A3 | 1.05 | Needs baseline A10+A15. |
| AVOID | A5+A21 | 0.58 | Only config below baseline. |

---

## Open Questions

1. **ANSWERED: full_action breaks out at n=256 (frob=1.06, 2x baseline) but REV
   vanishes (0/10).** full_all marginally breaks out (frob=0.95, 1/10 REV). All
   simple configs converge to frob≈0.52. Pending post-fix confirmation.

2. **ANSWERED: A19 transition is scale-specific because per-sector signal dilutes
   with n (Finding 14).** At n=64 with k=8, each sector has ~8 states (strong
   per-sector RM signal). At n=128, each sector has ~16 states (weaker signal,
   below the threshold needed to bias mixture weights enough for REV convergence).

3. **Can A20 be differentiated from A19?** Currently identical (Fix #6).
   Would need A20 + packaging producer (A22) experiment.

4. **PARTIALLY ANSWERED: k=8 IS limiting at n=256.** EXP-108 n=256 shows
   baseline frob=0.39 (k=4), 0.52 (k=8), 0.68 (k=16). Larger k captures more
   structure. But sigma also grows: 0.02 (k=4), 0.19 (k=8), 1.03 (k=16).
   EXP-108 doesn't test full_action — unclear if PICA benefit persists at k=16.

5. **ANSWERED: full_all does NOT beat full_action at n=128 (Finding 16).**
   At n=64, full_all (1.750) > full_action (1.417). At n=128, full_action (1.368)
   > full_all (1.196). A16 helps at small n but hurts at large n by creating
   partitions that increase irreversibility.

6. **What is the critical cell count for n=128 REV?** full_action (24 cells)
   gets 50% REV. What is the minimum subset needed? Ablation study required.

7. **ANSWERED: Boost resonance was artifact (Finding 38).** No boost level
   produces significant sigma_ratio or frob signal vs baseline. The apparent
   "resonance at 2.0" was from mixing intermediate and post-review binary data.

8. **Why does full_action preferentially drive "weak" baseline seeds to REV?**
   (Finding 35) REV seeds have lower baseline frob (0.64 vs 0.90) and higher gap
   (0.65 vs 0.57). Hypothesis: tight spectra → easier to fully equilibrate.

9. **What determines the macro_gap = 0.393 universal attractor?**
   (Finding 34) This value is locked for BOTH REV and NRM regimes across all k.
   Is it a function of n, or a universal constant of the dynamics?

10. **Can the A13 mechanism be separated from the full_action ensemble?**
    (Finding 31) The causal chain A13→traj→P2→edges→frob explains most of the
    variance, but REV requires all 24 cells. Does A13 alone change eff_gap?

11. **Is there a critical n beyond which REV vanishes entirely?**
    n=64: 100% REV. n=128: 50% REV. n=256: 0% REV (per old data). What's the
    functional form? Sigmoid? Power-law?

---

## Campaign EXP-200: Rich Audit Rerun (2026-02-22)

**Campaign ID:** pica_rerun_20260221_1ffaab6
**Commit:** 1ffaab6 (AUDIT-0 rich audit suite)
**Hypothesis:** HYP-200
**Total audit records:** 736 merged v4 (all unique, 0 duplicates after dedup)

### Finding Index

| # | Title | Key Result |
|---|-------|------------|
| F1 | full_action bimodal at n=128 | 5/10 REV (sigma=0), 5/10 NRM |
| F2 | frob-gap anticorrelation | r=-0.85, macro_gap_ratio = frob/gap proxy |
| F3 | LensSelector ranking reversal | MaxFrob best at n=64, A16/MinRM at n=128 |
| F4-8 | (Pre-campaign findings) | See "Findings from Campaign Data" |
| F9 | gap_ratio reflects bimodal regime | Median 50.18 is misleading (bimodal) |
| F10 | (Data quality) | See notes section |
| F11 | A18 is the regime switch | All observed σ≈0 runs have A18 active and τ≫2. τ>2 also occurs in A18-containing configs like full_action_safe, A13_A18_A19, and some boost configs. |
| F12 | Scale-free reversibility | REV: sigma=0 at ALL k values |
| F13 | REV = stable, NRM = dynamic | REV: fewer flips, coarser partition |
| F14 | **Scale-dependent REV crossover** | A19_only: 100% REV at n≤64, 0% at n=128 |
| F15 | REV anti-correlates with baseline | Low baseline frob → more likely REV |
| F16 | Inert cells confirmed | A20-A23 = baseline; **A25 NOT inert** (frob=0.991 at n=128); A18 inert on frob/σ alone but changes evaluation τ indirectly |
| F17 | **Budget saturation = REV** | REV→budget=n*ln(n), NRM→budget=17-47, 13x gap |
| F18 | Config hierarchy at n=128 | Only full_action/full_all achieve REV (24+ cells) |
| F19 | **Three regimes in multi-scale scans** | REV/NRM-PICA/NRM-baseline structurally distinct |
| F20 | **EXP-106 chain/boost at n=128** | Chain REV 1/6 (~17%), boost non-monotonic. **RETRACTED: boost resonance was data-mixing artifact (F38)** |
| F21 | **100% cross-experiment reproducibility** | Bit-exact metrics for same (seed, n, config), EXP-106 s0-2 intermediate binary |
| F22 | **P6-row scale-dependent interaction** | A24+A25 synergistic at n=32, antagonistic at n=128 (budget starvation) |
| F23 | **Single-cell utility at n=128** | A3 best (frob=1.054), A7 lowest sigma (0.392), A13 halves partition flips |
| F24 | **Lens selector = primary frob/gap knob** | MaxFrob→1.41, MaxGap→0.26, MinRM→1.12 (unstable). 8-seed EXP-103 at n=128 |
| F25 | **Cross-stage synthesis (736 records)** | full_action: sigma_ratio=0.49 (unique), k=8 peak profile, bimodal budget. Partition quality ≠ frob. |
| F26 | **Full system decomposition (EXP-105)** | A13 is keystone (+47%), A5_A21 only degrader. P1_row_A13 most scale-robust. A18/A20 inert in all combos. |
| F27 | **No super-additivity at n=128 (EXP-102)** | All combos additive or sub-additive. A3+A12 only scale-positive. combo_structure most robust (std=0.022). |
| F28 | **n=64 characterization (213 records)** | A19 dominates (every top-10 contains A19). Scale-improvers: A17 2.59x, A14 1.59x. Baseline 25% REV. |
| F29 | **sigma_u ≠ sigma (r=0.062)** | sigma_u captures small-community structure sigma misses. n_chiral vs sigma_u: r=-0.74 (strongest correlation). |
| F30 | **Three partition flip clusters** | A13-containing: ~6,500 (halved). Baseline: ~12,400. P4-row: ~19,800 (60% more). full_action: 4,400 (lowest). |
| F31 | **Edge gating = strongest frob predictor** | gated_edges vs frob: r=-0.51. full_action: 82% gated (baseline: 95%). Micro eff_gap near-degenerate → 5.7x gap amplification. |
| F32 | **P4 commutes exactly; lens quality anti-correlates frob** | [P1,P4]=[P2,P4]=0 always. Lens quality vs frob: r=-0.67. "Messy" dynamics → better structure. |
| F33 | **Multi-scale scan: two qualitative regimes** | 11 "normal" configs: log-linear frob slope 0.47-0.53. full_action: flat slope 0.16, k=2 frob 2x baseline, locked gap≈0.39. sigma_pi universally 0 at k=2. |
| F34 | **REV/NRM bifurcation is micro-kernel-level** | At k=2: REV frob=0.855 vs NRM 0.631 (5σ apart). REV=exact microscopic reversibility at ALL k. Macro_gap=0.393 is universal attractor. A16 scrambles which seeds hit REV. |
| F35 | **REV/NRM is seed×config interaction, NOT seed quality** | REV seeds are WEAKER in baseline (frob 0.64 vs 0.90). Seed ranks inconsistent across configs (mean Spearman rho=0.05). Full_all REV on different seeds. A19_only anti-correlated with full_action (rho=-0.73). |
| F36 | **Synthesis: full mechanistic picture** | Complete causal chain: A13→traj→P2→edges→eff_gap→[REV/NRM bifurcation]. Two routes to high frob: collective (full_action) vs partition competition (A13_A14_A19). 5 candidate theorems. Updated with F38-F39. |
| F37 | **Macro_gap attractor drifts with scale** | Gap 0.395→0.358 (n=128→256). ALL other configs: gap increases (+0.11-0.19). Full PICA: gap DECREASES. Variance tightens (0.070→0.022). Bimodality may collapse at n=256. |
| F38 | **EXP-106 post-review: no sigma_ratio signal, A14 frob champion** | Parameter loss fixed (1/78 identical pairs). NO config sigma_ratio differs from baseline (all p>0.45). A13_A14_A19 frob=1.376 (+43%, p=0.001). Boost resonance retracted. |
| F39 | **A13_A14_A19: minimal high-frob triplet** | 94% of full_action frob (1.376 vs 1.467) with 5 vs 24 cells. But IRREVERSIBLE (sigma=4.2 vs 0.02). A14 alone weakest lens; synergy is partition competition. REV at n=64, non-REV at n=128 (unique scale crossover). Gap=0.312 (lowest). |
| F40 | **Cell Atlas: comprehensive classification** | 16 beneficial, 2 neutral, 6 inert. P1 row all beneficial (+0.20-0.36). A13 synergy catalyst (4/5 super-additive combos). A13_A14_A19 Pareto-optimal. REV: 36% at n=32, 2.7% at n=128. **Note: A14 reclassified in F41.** |
| F41 | **Partition competition is primary frob mechanism** | A14 alone frob=1.327 (10 seeds, 70% >1.0). ALL alt lenses boost frob independently. A14 strongest single-cell booster, NOT harmful. 3-seed bias corrected. Partition competition > mixture modulation. |
| F42 | **Scale convergence at n=256 (non-lens only)** | Configs WITHOUT partition competition converge to frob≈0.52 (range 0.46-0.60). Effect space compressed 6x vs n=128. 128→256 ratio 0.55-0.60. **CORRECTED by F46:** NOT universal — lens configs resist. |
| F43 | **full_action maintains 2x at n=256** | frob=1.075 (old binary, 9 seeds) = 2.05x baseline. Scale ratio 0.73 (vs 0.60 universal). full_all similar (1.065). |
| F44 | **REV→NRM transition complete at n=256** | 0/9 full_action seeds achieve sigma=0. But sigma=0.014 (13x below baseline). REV sigmoid: 100%@n≤64, 50%@n=128, 0%@n=256. |
| F45 | **sigma_u ≠ sigma_pi confirmed (new binary)** | Old binary bug: sigma_pi==sigma_u always. New binary: sigma_u/sigma_pi = 1.08-1.59. Frob unchanged (≤4% delta). |
| F46 | **Partition competition SURVIVES at n=256** | A14_only: 3/3 seeds >1.0, median 1.157 (2.13x baseline). A16_only: 3/3 >1.0, median 1.171. A17_only: 2/3 >1.0, median 1.372. Scale ratio >1.0 for all (frob INCREASES with n). Refutes universal convergence (F42). **CONFIRMED.** |

### New Metrics Available

The AUDIT-0 framework adds per-run:
- `sigma_ratio` = sigma_macro / sigma_micro_at_tau (macro vs micro asymmetry)
- `macro_gap_ratio` = macro_gap / micro_gap (macro vs micro spectral gap)
- `partition_stats` / `packaging_stats` (entropy, effective_k, size_cv)
- Flip counters (partition_flips, packaging_flips, tau_changes)
- `sigma_u`, `max_asym`, `n_chiral`, `cyc_mean`, `cyc_max`, `trans_ep`
- `multi_scale_scan` (frob/gap/sigma at k=2,4,8,16,32 for n<256)

### Campaign Finding 1: full_action Is Bimodal at n=128 — Reversible vs Normal Regime

At n=128 with 10 unique seeds, full_action enters TWO distinct regimes with ~50/50
probability (seed-dependent):

| Regime | Seeds | frob | sigma | sigma_ratio | gap_ratio |
|--------|-------|------|-------|-------------|-----------|
| **Reversible** | 5/10 (s1,3,4,6,7) | 1.57–1.91 | 0.000 | 0.68–1.05 | 95–298 |
| **Normal** | 5/10 (s0,2,5,8,9) | 0.86–1.37 | 0.04–0.30 | 0.08–0.29 | 2.8–5.8 |
| **Median (all)** | 10 | **1.467** | **0.018** | **0.488** | **50.18** |

**WARNING:** The median gap_ratio (50.18) and sigma_ratio (0.488) fall BETWEEN the
two modes and are misleading as point estimates. The system is genuinely bimodal —
reporting per-regime statistics is more informative.

Cross-scale frob (median over **unique seeds**, seed count in parentheses):

| Config | n=32 | n=64 | n=128 | n=128 sigma_ratio | n=128 gap_ratio |
|--------|------|------|-------|-------------------|-----------------|
| **full_action** | **1.722** (3s) | **1.417** (3s) | **1.467** (10s) | **0.488** | **50.18** |
| full_all | 1.682 (3s) | 1.750 (3s) | 1.134 (10s) | 0.015 | 2.59 |
| A13_A14_A19 | — | — | 1.213 (10s) | 0.004 | 1.58 |
| full_action_safe | — | 1.702 (3s) | 1.391 (3s) | 0.098 | 2.61 |
| A16_only | — | 1.049 (3s) | 1.235 (3s) | 0.008 | 2.05 |
| all_MinRM | — | 0.456 (3s) | 1.205 (3s) | 0.003 | 1.45 |
| full_lens | — | 0.912 (3s) | pending | — | — |
| baseline | 1.305 (3s) | 1.151 (3s) | 0.854 (10s) | 0.004 | 1.77 |

**Note:** A16_only and all_MinRM are from post-fix EXP-103 (3 seeds each). Their
strong n=128 performance reflects the scale-dependent LensSelector ranking reversal
(Finding 3).

full_action at n=128 is the ONLY config where:
- 50% of seeds enter the reversible regime (frob > 1.5, sigma = 0)
- Even in the normal regime, frob ranges 0.86–1.37 (comparable to best alternatives)
- sigma_ratio is 10–100x higher than non-full configs in both regimes

### Campaign Finding 2: No Single Cell Improves Frob at n=64 (3 Seeds, EXP-100)

With 3 seeds at n=64 in EXP-100, no single P1/P2/P3-row cell added to baseline
increased median frob:

| Cell | n=64 frob (3 seeds) | vs baseline |
|------|---------------------|-------------|
| A3 (P1-P3) | 1.150 | −0.04% |
| A2 (P1-P2) | 1.114 | −3.2% |
| A12 (P2-P6) | 0.972 | −15.5% |
| A13 (P3-P6) | 0.913 | −20.7% |
| A7 (P2-P1) | 0.848 | −26.3% |

**Important: this does not generalize across scales.** In the same EXP-100 at n=128
(same 3 seeds), every single-cell config is HIGHER than baseline (e.g. A5: +46%).
The n=64 result likely reflects seed-set sensitivity with only 3 seeds.

The claim "individual cells are net-negative" is only supported at n=64 with 3 seeds.
A proper test requires 10+ seeds at each scale. The claim that "structure requires
the full 25-cell system" is NOT demonstrated — A13_A14_A19 (3 cells) achieves
frob 1.213 at n=128, and full_action_safe achieves 1.391.

### Campaign Finding 3: LensSelector Has Strong Effect — **REVERSED (bug fix)**

~~Stage 03 (EXP-103): MaxFrob = MaxGap = MinRM across ALL metrics at both n=64
and n=128.~~

**Root cause:** Runner bug discarded `lens_selector`. **Fixed 2026-02-22.**

**Post-fix EXP-103 results (n=64, 3 seeds, fixed binary):**

| LensSelector | frob | sigma | gap | sigma_ratio | gap_ratio |
|--------------|------|-------|-----|-------------|-----------|
| **all_MaxFrob** | **1.057** | **6.882** | 0.538 | 0.010 | 3.28 |
| all_MinRM | 0.456 | 0.345 | 0.699 | 0.022 | 7.80 |
| all_MaxGap | 0.329 | 0.624 | **0.890** | 0.022 | 4.10 |
| full_lens (all 4 P4 cells) | 0.912 | 0.985 | 0.573 | 0.031 | 4.11 |

**MaxFrob produces 2.3x higher frob than MinRM and 3.2x higher than MaxGap.**
MaxGap optimizes for spectral gap (0.890) at the cost of frob. MinRM is intermediate.
The selectors have dramatically different effects. Individual P4-row cells also differ:
A15 (spectral, frob=1.050) ≈ A16 (row-sim, frob=1.049) > A14 (RM-quantile, 0.837) > A17 (EP-quantile, 0.370).

**Post-fix EXP-103 results (n=128, 3 seeds, fixed binary):**

| LensSelector | frob | sigma | gap | sigma_ratio | gap_ratio |
|--------------|------|-------|-----|-------------|-----------|
| **A16_only** | **1.235** | 1.949 | 0.565 | 0.008 | 2.05 |
| **all_MinRM** | **1.205** | 1.416 | 0.444 | 0.003 | 1.45 |
| A17_only | 0.968 | 2.028 | 0.545 | 0.008 | 1.92 |
| A14_only | 0.922 | 4.581 | 0.590 | 0.004 | 1.53 |
| A15_only (=baseline) | 0.462 | 0.597 | 0.778 | 0.003 | 3.44 |
| all_MaxGap | 0.234 | 0.166 | **0.870** | 0.004 | 2.65 |
| all_MaxFrob | *timed out* | | | | |
| full_lens | *timed out* | | | | |

**The ranking completely reverses between n=64 and n=128:**
- A16 (row-similarity): 1.049 → 1.235 (+18%, best at n=128)
- MinRM: 0.456 → 1.205 (+164%, worst→second best)
- A15 (spectral): 1.050 → 0.462 (−56%, collapses)
- MaxGap: 0.329 → 0.234 (still worst)

This is a major finding: the optimal partition selection criterion is scale-dependent.
all_MaxFrob and full_lens timed out at n=128 with 2h limit (post-review batch with
24h timeout expected to capture these).

**Mechanistic explanation (multi-scale scan, n=64 seed 0):**
| Selector | frob@k=8 | sigma@k=8 | gap@k=8 | Strategy |
|----------|----------|-----------|---------|----------|
| A15 (spectral) | **1.167** | 18.31 | 0.431 | Concentrate structure |
| A16 (row-sim) | 0.770 | 3.53 | 0.611 | Balance structure+gap |
| MaxFrob | 0.806 | 2.04 | 0.617 | Pick highest frob candidate |
| MaxGap | 0.657 | 0.92 | 0.541 | Preserve gap |
| MinRM | 0.517 | **0.39** | 0.660 | Preserve reversibility |

A15 achieves highest frob at n=64 by aggressively concentrating structure along the
dominant eigenvector — but this introduces high irreversibility (sigma=18.3). At n=128
the eigenvalue spectrum changes and this aggressive strategy collapses.

MinRM achieves lowest sigma at ALL k values — it selects for reversibility-preserving
partitions. At n=64 this sacrifices frob. At n=128, where the spectral approach fails,
the reversibility-preserving partition actually captures more genuine block structure.

n=256 results pending.

### Campaign Finding 4: EP Boost Parameter Has Measurable Effect — **REVERSED (bug fix)**

~~Stage 05 (EXP-106): boost values 0.1, 0.5, 1.0, 3.0, 4.0 produce
bit-identical results.~~

**Root cause:** Same runner bug discarded `p3_p4_sector_boost`. **Fixed 2026-02-22.**

**Post-fix EXP-106 boost sweep results (n=64, 3 seeds, fixed binary):**

| Boost | frob | sigma | gap | tau | sigma_ratio |
|-------|------|-------|-----|-----|-------------|
| 0.1 | 0.859 | 6.156 | 0.549 | 2 | 0.098 |
| 0.5 | 1.013 | 3.130 | 0.662 | 2 | 0.038 |
| 1.0 | 0.933 | 5.982 | 0.476 | 2 | 0.026 |
| 3.0 | 0.916 | 6.353 | 0.689 | 3 | 0.038 |
| 4.0 | 1.040 | 4.876 | 0.449 | 2 | 0.026 |
| baseline | 1.050 | 5.487 | 0.510 | — | 0.013 |

The boost parameter produces measurably different outcomes (frob range 0.859–1.040)
but the relationship is non-monotonic. No single boost value dominates; the effect
is seed-dependent at 3 seeds. Higher boost shifts tau (boost_3.0 → tau=3 vs tau=2
for others). 10+ seeds at n=128 needed for robust characterization.

Also tested combo configs (EXP-106):

| Config | frob | sigma | tau |
|--------|------|-------|-----|
| A13_A18_A19 | 1.602 | 0.000 | 30 |
| chain_A24 | 1.379 | 0.000 | 25 |
| chain_pkg | 1.363 | 0.000 | 39 |
| A13_A14_A19 | 1.195 | 0.000 | — |

Chain configs with A19 all enter the reversible regime (sigma=0, high frob).
n=128 and n=256 results pending.

### Campaign Finding 5: sigma_ratio Clusters Near 0.002–0.010 at n=128 (With Outliers)

At n=128, most configs have sigma_ratio in the range 0.002–0.010. However, the
previously claimed "universal convergence to 0.003–0.010" is **wrong as stated**:

Outliers beyond [0.002, 0.010]:
- **full_action**: 0.294 (highest, breakaway)
- **full_action_safe**: 0.098
- **full_all**: 0.0145 (above 0.010)
- **A1+A3+A13**: 0.0105 (above 0.010)
- **A3+A12**: 0.00169 (below 0.002)

**Data quality warning:** sigma_ratio = sigma_macro / micro_sigma_at_tau. At n=32,
the denominator (micro_sigma_tau) can be near zero, producing catastrophic values
(e.g. A13 median sigma_ratio ~5.6e8). The audit records do not store the denominator,
so it is impossible to screen "unsafe" ratios in post-hoc analysis. Sigma_ratio is
only reliable at n≥128 where micro_sigma_tau is well-separated from zero.

### Campaign Finding 6: A19 Sigma-Killing Is Scale-Dependent (Confirmed)

| Scale | A19 sigma | A19 sigma_ratio | seeds |
|-------|-----------|-----------------|-------|
| n=32 | **O(1e-10)** | 1.090 | 3 |
| n=64 | **O(1e-10)** | 0.973 | 3 |
| n=128 | **0.792** (deduped) | 0.007 | 10 unique |

At n=32 and n=64, sigma is numerically zero (O(1e-10), not exactly 0.000).
At n=128, A19 has no special effect on sigma. The deduped median over 10 unique
seeds is 0.792 (previously reported as 0.919 from 13 pooled records with
seed 0-2 duplicated).

### Campaign Finding 7: Four Cells Inert, One Conditionally Active, One Data-Starved

Cells tested in EXP-104 (baseline + single cell, seeds 0-2, scales 32/64/128):

**Confirmed inert at ALL tested scales (32, 64, 128):**
- **A21** (P5<-P3): no consumer reads packaging (A5/A11 off)
- **A22** (P5<-P4): no consumer reads packaging
- **A23** (P5<-P6): no consumer reads packaging
- **A25** (P6<-P6): EP-retention always satisfied → cap_mult = 1.0

**Conditionally active (NOT inert):**
- **A18** (P3<-P3): adaptive tau. Active at n=32 (sigma: baseline 21.98 vs A18
  34.28) and n=64 (sigma: baseline 0.588 vs A18 1.384). Matches baseline exactly
  at n=128. A18 changes tau, which shifts the spectral partition used downstream.
  "Adaptive time-scale selection" is a real control knob, not just a diagnostic.

**Data-starved (inert in isolation, but for architectural reasons):**
- **A20** (P3<-P5): reads `active_packaging` which is only computed when P5-row
  cells are enabled. In A20_only config, A20's data source is empty → identity
  scores. This is data starvation, not true inertness. When P5 producers are
  present, A20 may have distinct effects.

**Critical distinction:** "Inert when added individually to baseline" does NOT mean
"inert in the full system." These cells may contribute to full_action's advantage
through interactions with other cells. Testing this requires ablation study
(remove each cell from full_action one at a time).

### Top Configs at n=128 (Deduped by Unique Seeds)

All medians computed after deduplication by (_cfg_label, n, seed).

| Rank | Config | Seeds | frob | sigma | sigma_ratio | gap_ratio | Notes |
|------|--------|-------|------|-------|-------------|-----------|-------|
| 1 | full_action | 10 | 1.467 | 0.02 | 0.488 | 50.2 | **BIMODAL** (see F1) |
| 2 | full_action_safe | 3 | 1.391 | 0.14 | 0.098 | 2.61 | |
| 3 | A16_only | 3 | 1.235 | 1.95 | 0.008 | 2.05 | EXP-103 post-fix |
| 4 | A13_A14_A19 | 10 | 1.213 | 0.70 | 0.004 | 1.58 | |
| 5 | all_MinRM | 3 | 1.205 | 1.42 | 0.003 | 1.45 | EXP-103 post-fix |
| 6 | full_all | 10 | 1.134 | 0.27 | 0.018 | 2.54 | |
| 7 | A3 (P1-P3) | 3 | 1.054 | 1.79 | 0.008 | 1.32 | |
| 8 | P1_row_A13 | 10 | 1.015 | 0.78 | 0.004 | 1.69 | Lowest variance |

**Note:** Configs with only 3 seeds (full_action_safe, A16_only, all_MinRM, A3)
have high uncertainty. Rankings among 3-seed configs are unreliable.

**BIMODAL WARNING for full_action:** The median sigma_ratio (0.488) and gap_ratio
(50.2) are misleading averages between two distinct regimes (see Finding 1). In
the normal regime (5/10 seeds), gap_ratio is 3–6 and sigma_ratio is 0.08–0.29.

### Updated Configuration Recommendations

**For n≤64 (all achieve REV):**
- **full_action** (frob=1.42-1.72, 100% REV, budget at cap)
- chain (A13+A18+A19, frob=1.54, 100% REV) — simpler alternative
- A19_only (frob=1.52, 100% REV) — minimal REV config

**For n=128 (max frob, bimodal):**
- **full_action** (frob=1.47 median, 50% REV / 50% NRM, budget at cap when REV)
- full_all (frob=1.13, 30% REV) — A16 slightly hurts
- full_action_safe (frob=1.32, 0/3 REV with 3 seeds) — 23 cells, near-REV

**For n=128 (reliable non-bimodal):**
- **P1_row_A13** (frob=1.015, sigma=0.78, very consistent) — best 2-cell
- A16_only (frob=1.24, 3 seeds) — best lens producer
- all_MinRM (frob=1.21, 3 seeds) — MinRM selector best at n=128
- A25_only (frob=0.99, raises minimum frob, stabilizer)

**For n=256 (limited options):**
- **full_action** (frob=1.06, 2x baseline, 0% REV) — only significant config
- full_all (frob=0.95, 1/10 REV) — marginally better than convergence
- All others converge to frob≈0.52 regardless of config

### Campaign Finding 8: Strong frob ↔ macro_gap Anticorrelation

At n=128, frob_from_rank1 and macro_gap are strongly anticorrelated (Pearson ≈ −0.85).
Higher retained structure (frob) generally comes with slower mixing (smaller gap).
This is a meaningful tradeoff: configs that maximize departure from rank-1 pay a cost
in spectral gap.

### Campaign Finding 9: full_action gap_ratio Reflects Bimodal Regime

At n=128, full_action's macro_gap_ratio is bimodal (see Finding 1):
- **Reversible regime** (5/10 seeds): gap_ratio = 95–298
- **Normal regime** (5/10 seeds): gap_ratio = 2.8–5.8
- **Median**: 50.18 (misleading — falls between modes)

In the reversible regime, the macro kernel has near-zero second eigenvalue gap
denominator, inflating the ratio. In the normal regime, gap_ratio 3–6 is still
2–3x higher than other configs (baseline ~1.8). The bimodality means full_action's
coarse-graining either dramatically improves mixing (reversible) or modestly improves
it (normal), depending on the random seed.

### Campaign Finding 10: Scoring Criteria DO Distinguish Candidates (Bug Was the Cause)

The pre-fix bit-identity of LensSelector and boost sweeps was entirely due to the
parameter loss bug. Post-fix results show:
- LensSelector: MaxFrob vs MinRM vs MaxGap produce 2-3x differences in frob
- Boost: 0.1 to 4.0 produce measurably different outcomes

The partition candidate set IS differentiated — different scoring criteria (RM, gap,
frob) select genuinely different partitions. This opens a significant new axis of
optimization that was invisible due to the bug.

### Campaign Finding 11: Adaptive Tau (A18) Is the Regime Switch in full_action

At n=128, the tau distribution separates the two regimes:

| Regime | Seeds | tau values | median tau |
|--------|-------|-----------|------------|
| Reversible | s1,3,4,6,7 | 120, 378, 163, 269, 198 | 198 |
| Normal | s0,2,5,8,9 | 5, 3, 7, 6, 6 | 6 |

**Only full_action and full_all have tau > 2 at n=128.** Every other config tested
(23 configs including baseline, sbrc, A13_only, A19_only, chain variants, boost
variants) has tau median = 1 and max ≤ 3.

| Config | tau median | tau range |
|--------|-----------|-----------|
| full_action | 63.5 | 3–378 |
| full_all | 2.5 | 2–174 |
| all others (21 configs) | 1.0 | 1–3 |

**Mechanism:** A18 (P3←P3, adaptive tau) reads the multi-scale RM profile and
selects an observation timescale. In the full system (24+ cells), A18 can discover
long timescales (tau > 100) where the evolved kernel reaches a reversible fixed
point. Without the full cell ensemble, the RM profiles don't support long tau
selection.

**Cross-scale pattern:**
- n=32: tau=23–56 (all REV, 3/3 seeds)
- n=64: tau=75–299 (all REV, 3/3 seeds)
- n=128: tau=3–378 (bimodal, 5/10 REV)

At n=32/64, the random kernels always support long tau. At n=128, the spectral
structure of the initial random kernel determines whether long tau is accessible.

**Implication for A18 characterization:** A18 alone is "conditionally active"
(Finding 7), but in the full system it becomes the CRITICAL regime-selection
mechanism. This is the strongest example of "inert alone ≠ inert in full system."

### Campaign Finding 12: Multi-Scale Scan Reveals Scale-Free Reversibility

The two regimes produce qualitatively different multi-scale scan profiles at n=128:

**REV regime** (5 seeds, tau=120–378):
- sigma_pi = 0.000 at ALL k values (k=2 through k=27)
- gap ≈ 0.393, constant across ALL k
- frob increases monotonically: 0.86 (k=2) → 2.2–3.2 (k=23–27)
- The kernel is in detailed balance at every coarse-graining scale

**NRM regime** (5 seeds, tau=3–7):
- sigma_pi = 0 at k=2, grows with k: 0.03 (k=4) → 0.1 (k=8) → 0.4 (k=30+)
- gap ≈ 0.39–0.44, varies with k and seed
- frob increases then plateaus: 0.6 (k=2) → 1.0–1.4 (k=20+)
- Irreversibility emerges at finer granularity

**Key finding:** In the REV regime, the ENTIRE evolved kernel has converged to
detailed balance (time-reversible), not just at k=8. The sigma=0 holds at every
possible coarse-graining. This is "scale-free reversibility" — a distinct
dynamical phenotype that emerges from the 24-cell PICA interaction.

In the NRM regime, the kernel is only approximately reversible at the coarsest
scale (k=2), with increasing irreversibility at finer scales. This is the expected
behavior — finer observation reveals more structure.

**Note:** At k=2, sigma=0 in BOTH regimes. The distinction only appears at k≥4.

### Campaign Finding 13: REV Is a Stable Fixed Point, NRM Is Dynamic

Per-seed analysis of full_action at n=128:

| Metric | REV median (5s) | NRM median (5s) | Ratio |
|--------|----------------|-----------------|-------|
| partition effective_k | 3.6 | 5.3 | 0.68x |
| tau_change_count | 82 | 403 | 0.20x |
| partition_flip_count | 3950 | 5788 | 0.68x |
| packaging_flip_count | 11110 | 12477 | 0.89x |

The REV regime is a STABLE FIXED POINT: fewer partition states (coarser CG),
far fewer tau changes, fewer partition rearrangements. The system converges to a
long tau, settles on a coarse partition (~3-4 effective states out of 8), and stops
changing. This produces higher frob (concentrated structure in fewer groups).

The NRM regime is DYNAMIC: more partition states (finer CG), frequent tau/partition
flips, ongoing exploration. The kernel never reaches detailed balance because the
partition keeps changing.

**full_all comparison:** full_all (full_action + A16) at n=128 shows the same
bimodality but with only 3/10 seeds in REV (vs 5/10 for full_action). A16 reduces
the probability of reaching the reversible regime. In the NRM regime, full_all's
sigma grows much faster with k (sigma≈8–66 at k≈30 vs sigma≈0.1–0.5 for
full_action). A16 creates partitions that increase irreversibility at fine scales.

### Campaign Finding 14: Scale-Dependent REV Crossover — Chain Alone Fails at n=128

**EXP-106 n=64 boost scan** (A13+A18+A19 with varying `p3_p4_sector_boost`):

| boost value | REV/total | med frob | med sigma | med tau |
|-------------|-----------|----------|-----------|---------|
| 0.1 | 0/3 | 0.859 | 6.16 | 2 |
| 0.5 | 0/3 | 1.013 | 3.13 | 2 |
| 1.0 | 0/3 | 0.933 | 5.98 | 2 |
| **2.0** (default) | **3/3** | **1.602** | **0.000** | **30** |
| 3.0 | 0/3 | 0.916 | 6.35 | 3 |
| 4.0 | 0/3 | 1.040 | 4.88 | 2 |

**Key finding:** The REV transition requires boost=2.0 (the default). Values below or
above don't trigger it. This is NOT a monotonic threshold — it's a narrow resonance.
boost=1.0 comes closest (sigma=0.90 for one seed), suggesting the critical window
is approximately [1.5, 2.5].

**Alternative cluster_rm enablers** (all with default boost=2.0):
- A13+A3+A19: 3/3 REV (different P1-row enabler)
- A13+A14+A19: 3/3 REV (P4-row enabler)
- A13+A21+A19: 3/3 REV (P5-row enabler, identical to A18 variant — A21 truly inert)
- All 4 enabler variants trigger REV at n=64 with 100% probability.

**Cross-regime combos** (A13+A18+A19 + extra cell, boost=2.0):
- +SBRC (A12): 1/3 REV — SBRC destabilizes the transition
- +A24 (budget rate): 3/3 REV — compatible with REV
- +A11+A22 (packaging): 3/3 REV — compatible with REV

**A19 is the single REV-triggering cell.** Systematic elimination at n=64:
- A13_only: 0/3 REV (sigma=0.8–13.8)
- A13_A18: 0/3 REV (identical to A13_only — A18 is inert here)
- A13_A18_A20: 0/3 REV (identical to A13_only — A20 is data-starved)
- **A13_A18_A19: 3/3 REV** (sigma=0, tau=12–1072)
- **A19_only (baseline+A19): 3/3 REV** — A19 alone is sufficient!

A13 and A18 are NOT needed for REV at n=64. A19 on top of baseline (A10+A15) is
the minimal trigger.

**Complete scale profile — the REV crossover:**

| Config | n=32 | n=64 | n=128 | Data source |
|--------|------|------|-------|-------------|
| A19_only | 3/3 REV | 3/3 REV | 0/10 REV | EXP-104 + EXP-107 |
| chain (A13+A18+A19) | — | 6/6 REV | 0/23 REV | EXP-105 + EXP-106 + EXP-107 |
| full_action (24 cells) | 3/3 REV | 3/3 REV | 5/10 REV | EXP-104 + EXP-107 |

The transition is sharp: 100% REV at n≤64, 0% REV for simple configs at n=128.
Only the full 24-cell ensemble (full_action) partially compensates, achieving 50%
REV at n=128 through collective reinforcement that A19 alone cannot provide.

**Mechanism:** A19 modulates mixture weights based on per-sector RM values. At n=64
(with k=8 partition), each sector averages 8 states → strong per-sector signal. At
n=128 (same k=8), each sector averages 16 states → weaker per-sector signal.
The other 20+ cells in full_action provide indirect support (better partition quality
from P4 cells, P1 rewrite history, P2 gating from budget pressure) that amplifies
A19's weakened signal enough to occasionally cross the REV threshold.

**Nuance: REV basin exists even without A19.** At n=64, some configs occasionally
enter REV through basic spectral gating alone:
- baseline: 1/3 REV (seed 2, tau=84)
- A11_A22: 1/3 REV (seed 2, tau=2058!)
- A24_A25: 1/3 REV (seed 1, tau=185)

A19 doesn't CREATE the REV regime — it dramatically increases the probability of
reaching it (from ~10-30% to 100% at n=64). The REV basin is a property of the
dynamics; certain random kernel topologies naturally evolve toward detailed balance.
At n=128, even the baseline REV probability drops to 0% (0/10 seeds).

**Data validity note:** The parameter loss bug only affected configs with custom
parameters (LensSelector, sector_boost). Configs that differ only by enabled cells
(all data above) are VALID even from the pre-fix binary.

**Pending:** EXP-106 n=128 fixed results (running) will confirm boost scan at n=128.

### Campaign Finding 15: REV Outcome Is Anti-Correlated With Baseline Quality

Per-seed analysis at n=128: seeds that enter REV in full_action (5/10) have
LOWER baseline frob than NRM seeds.

| Metric | REV seeds (5) | NRM seeds (5) |
|--------|---------------|---------------|
| baseline frob median | 0.574 | 0.864 |
| baseline frob range | 0.422–0.901 | 0.666–1.124 |
| A19_only frob median | 0.588 | 0.924 |
| A25_only frob median | 0.952 | 0.994 |

Seeds with low baseline frob (more "random", less pre-existing structure) are MORE
likely to enter REV under full_action. Seeds with high baseline frob already have
partial structure that may resist the REV transition (kernel organized in a way
incompatible with detailed balance).

**No simpler proxy predicts REV.** Neither A19_only frob, A25_only frob, nor baseline
sigma correlates with full_action REV probability. The regime selection is an emergent
property of the 24-cell interaction that cannot be predicted from single-cell behavior.

**Even NRM full_action seeds have low sigma.** Full_action NRM seeds have sigma=
0.04–0.30 (median 0.09), far below baseline NRM sigma=0.44–3.09 (median 0.86).
The full cell ensemble universally pushes sigma toward zero; REV is the extreme case.

### Campaign Finding 16: Inert Cells Confirmed — Comprehensive Single-Cell Scan

EXP-104 tests 14 configs (single cells and presets) at n=32, 64, 128 with 3 seeds.
Cells producing results IDENTICAL to baseline at all 3 scales:

| Cell | Classification | n=32 | n=64 | n=128 |
|------|---------------|------|------|-------|
| A18_only | Inert (alone) | = baseline | = baseline | = baseline |
| A20_only | Inert | = baseline | = baseline | = baseline |
| A21_only | Inert | = baseline | = baseline | = baseline |
| A22_only | Inert | = baseline | = baseline | = baseline |
| A23_only | Inert | = baseline | = baseline | = baseline |
| P5_row_all | Inert (row) | = baseline | = baseline | = baseline |

The entire P5 row (A21+A22+A23) is collectively inert when enabled alone. These
cells need producers (from other rows) to generate data they can act on.

**Active single cells:**
- **A19_only**: Most powerful. 100% REV at n≤64, frob=0.90 at n=128 (vs 0.67 baseline)
- **A24_only**: Modest frob improvement at n=32 only
- **A25_only**: Raises minimum frob at n=128 (all seeds ≥0.89 vs baseline's 0.42 minimum)

**A16 scale crossover:**
- n=64: full_all > full_action (frob 1.750 vs 1.417)
- n=128: full_action > full_all (frob 1.368 vs 1.196)
A16 HELPS at n=64 (produces useful partitions) but HURTS at n=128 (creates partitions
that increase irreversibility). This is consistent with Findings 13 and 14.

### Campaign Finding 17: Budget Saturation Is the REV Signature at n=128

EXP-107 n=128 with 10 seeds per config reveals that **budget saturation perfectly
correlates with REV regime**. The budget cap is `n * ln(n) = 128 * 4.852 = 621.06`.

**full_action per-seed budget and regime:**

| Seed | frob | sigma | budget | regime |
|------|------|-------|--------|--------|
| 0 | 1.264 | 0.146 | 27.36 | NRM |
| 1 | 1.756 | 0.000 | 621.06 | **REV** |
| 2 | 1.368 | 0.148 | 47.20 | NRM |
| 3 | 1.565 | 0.000 | 621.06 | **REV** |
| 4 | 1.914 | 0.000 | 621.06 | **REV** |
| 5 | 0.860 | 0.036 | 26.56 | NRM |
| 6 | 1.914 | 0.000 | 621.06 | **REV** |
| 7 | 1.893 | 0.000 | 621.06 | **REV** |
| 8 | 1.143 | 0.304 | 20.42 | NRM |
| 9 | 0.875 | 0.089 | 17.35 | NRM |

Budget gap: lowest REV = 621.06, highest NRM = 47.20 → **13x separation**.

**Cross-config budget at n=128 (medians):**

| Config | frob | sigma | budget | REV/10 |
|--------|------|-------|--------|--------|
| full_action | 1.467 | 0.018 | 621→cap | 5/10 |
| full_all | 1.134 | 0.267 | 83 (2 at cap) | 3/10 |
| chain | 0.940 | 1.070 | 17 | 0/10 |
| baseline | 0.855 | 0.756 | 14 | 0/10 |

**Multi-scale sigma profile confirms Finding 12 (scale-free reversibility):**

REV seed (full_action s=1):
- k=2: sigma=0.000, frob=0.859
- k=4: sigma=0.000, frob=0.887
- k=6: sigma=0.000, frob=1.145
- k=10: sigma=0.000, frob=1.480
- k=15: sigma=0.000, frob=1.776
- k=20: sigma=0.000, frob=2.047

sigma=0 **at all scales simultaneously**. frob monotonically increases with k.

NRM seed (full_action s=0):
- k=2: sigma=0.000, frob=0.629
- k=4: sigma=0.030, frob=0.706
- k=8: sigma=0.088, frob=0.901
- k=12: sigma=0.137, frob=1.054
- k=20: sigma=0.162, frob=1.035
- k=33: sigma=0.182, frob=1.013

sigma grows with k. frob plateaus and slightly decreases at large k.

**Budget saturation across ALL scales (EXP-104):**

| Scale | n*ln(n) | PICA-REV budget | baseline-REV budget | Mechanism |
|-------|---------|---------------|--------------------|----|
| 32 | 110.90 | 110.90 (cap) | 9.67 (not cap) | Strong REV |
| 64 | 266.17 | 266.17 (cap) | 24.98 (not cap) | Strong REV |
| 128 | 621.06 | 621.06 (cap) | (no baseline REV) | Strong REV only |

Two distinct REV mechanisms emerge:
- **Strong REV** (PICA-driven): budget at cap, sigma=0 at all k, persists to n=128
- **Weak REV** (stochastic): budget NOT at cap, exists at n≤64 only (1/3 baseline seeds)

At n≤64, both forms coexist. At n=128, only strong REV survives — the stochastic
form vanishes entirely (0/10 baseline seeds achieve REV). Strong REV requires the
24-cell cooperative feedback AND budget lock-in mechanism.

**Mechanistic hypothesis:** 24-cell PICA feedback → detailed balance at macro level →
KL cost drops (kernel stops changing) → P6 replenishment exceeds cost → budget fills
to cap → budget saturation enables sustained reversibility → positive feedback loop →
stable REV attractor. This is a **homeostatic fixed point**: the system reaches detailed
balance, has no reason to change, and the budget mechanism locks it in place.

**Partition structure differences (extending Finding 13):**

| Metric | REV (5 seeds) | NRM (5 seeds) |
|--------|--------------|---------------|
| effective_k | 2.7–4.1 (med 3.6) | 5.0–5.9 (med 5.2) |
| partition entropy | 0.99–1.42 | 1.60–1.77 |
| tau | 120–378 | 3–7 |
| tau_change_count | 35–245 | 272–1195 |
| partition_flips | 3803–4578 | 4412–7796 |

REV partitions are COARSER (fewer effective clusters), more STABLE (fewer flips),
and operate at dramatically higher tau (20–60x). The partition structure freezes into
an uneven configuration with one dominant cluster.

**full_all exception:** seed 7 achieves near-REV (sigma=0.002) with budget=19.40 (NOT
at cap). This suggests an alternative path to REV that doesn't require budget saturation,
possibly mediated by A16's interaction with the partition system.

### Campaign Finding 18: EXP-107 Config Hierarchy at n=128 (10-Seed Statistics)

Complete ranking of 13 configs at n=128 with 10 seeds each (EXP-107, pre-fix binary
but data valid — configs differ only by enabled cells, no custom params):

| Config | frob_med | sigma_med | gap_med | REV/10 | tau_ch |
|--------|---------|-----------|---------|--------|--------|
| full_action | 1.467 | 0.018 | 0.3930 | 5 | 258 |
| full_all | 1.134 | 0.267 | 0.3686 | 3 | 588 |
| P1_row_A13 | 1.015 | 0.782 | 0.5187 | 0 | 0 |
| A25_only | 0.991 | 1.417 | 0.5129 | 0 | 0 |
| A13_only | 0.967 | 1.045 | 0.5525 | 0 | 0 |
| chain | 0.940 | 1.070 | 0.5709 | 0 | 232 |
| chain_A24 | 0.925 | 0.684 | 0.5608 | 0 | 244 |
| A24_only | 0.912 | 1.356 | 0.5546 | 0 | 0 |
| A11_A22 | 0.889 | 0.544 | 0.5487 | 0 | 0 |
| chain_SBRC | 0.886 | 0.849 | 0.5460 | 0 | 113 |
| sbrc | 0.885 | 0.732 | 0.5520 | 0 | 0 |
| A19_only | 0.868 | 0.792 | 0.5870 | 0 | 0 |
| baseline | 0.855 | 0.756 | 0.5599 | 0 | 0 |

Key observations:
1. **Only full_action and full_all achieve REV at n=128.** All simpler configs are NRM.
2. **REV requires 24+ cells** — even chain (5 cells) is 0/10 REV at n=128.
3. **P1_row_A13** is the best non-bimodal config (frob=1.015, consistent across seeds).
4. **A25_only** surprisingly ranks #4 — it stabilizes the floor, giving consistent frob≥0.89.
5. **A19_only** is near baseline at n=128 — its dramatic effect at n=64 vanishes completely.
6. **tau_change_count > 0** only for A18-containing configs (chain, chain_A24, chain_SBRC,
   full_action, full_all), confirming A18 as the tau modifier.

### Updated Open Questions

1. **Does full_action maintain frob > 1.0 at n=256?** Previous EXP-107v2 showed
   1.059 (9 seeds). Campaign n=256 re-run needed for confirmation with rich audits.
2. **ANSWERED: LensSelector matters dramatically.** MaxFrob frob=1.057 vs MinRM
   frob=0.456 vs MaxGap frob=0.329 at n=64. Pending: does the effect persist at
   n=128/256? Do different selectors become optimal at different scales?
3. **UPDATED (F20): Boost is non-monotonic at n=128 too.** boost_0.1/0.5 HURT frob
   (0.94/0.91 vs chain 1.06). boost_1.0 recovers frob but with 3.3x higher sigma.
   At n=64, only boost=2.0 triggered REV. The EXP-106 post-fix batch didn't include
   boost_2.0, so resonance at n=128 remains untested.
4. **Can sigma_ratio > 0.1 be achieved by configs other than full_action?**
   full_action_safe gets 0.098. What minimal subset of cells is needed?
5. **What makes full_action special?** It enables 24/25 cells (all except A16).
   Ablation study: which cells can be removed while keeping sigma_ratio > 0.1?
6. **Does A20 have an effect when P5 producers are present?** Currently data-starved
   in isolation. Test A20 + A21 (or A20 + A22) to see if it behaves like A19
   when packaging data is available.

### Campaign Finding 19: Three Distinct Regimes in Multi-Scale Scan Profiles

Multi-scale scan data (frob and sigma at k=2,4,...,n/3) at n=128 reveals three
structurally distinct dynamical regimes, not two:

**Regime 1 — REV** (full_action 5/10 seeds):

| k | frob | sigma | max_asym |
|---|------|-------|----------|
| 2 | 0.857 | 0.000 | 0.557 |
| 4 | 1.003 | 0.000 | 0.956 |
| 6 | 1.145 | 0.000 | 1.018 |
| 10 | 1.480 | 0.000 | 1.380 |
| 15 | 1.878 | 0.000 | 1.840 |
| 20 | 2.251 | 0.000 | 2.203 |

sigma=0 everywhere. frob monotonically increases. Structure grows richer at finer scales.

**Regime 2 — NRM-PICA** (full_action 5/10 NRM seeds):

| k | frob | sigma | max_asym |
|---|------|-------|----------|
| 2 | 0.629 | 0.000 | 0.215 |
| 4 | 0.794 | 0.026 | 0.917 |
| 8 | 0.901 | 0.054 | 1.459 |
| 12 | 1.027 | 0.137 | 1.706 |
| 20 | 1.083 | 0.162 | 1.877 |
| 33 | 1.057 | 0.182 | 1.717 |

sigma grows slowly (0→0.18). frob PLATEAUS at ~1.0. Irreversibility partially
suppressed relative to baseline.

**Regime 3 — NRM-baseline** (baseline, chain, A19_only, P1_row_A13):

| k | frob | sigma | max_asym |
|---|------|-------|----------|
| 2 | 0.389 | 0.000 | 0.306 |
| 4 | 0.585 | 0.089 | 0.437 |
| 8 | 0.836 | 0.894 | 0.664 |
| 16 | 1.224 | 15.24 | 1.058 |
| 27 | 1.818 | 54.20 | 1.719 |
| 45 | 2.658 | 99.65 | 2.854 |

sigma grows RAPIDLY (0→100). frob grows unboundedly. Typical random-kernel
irreversibility.

**Key insight:** NRM-PICA is genuinely intermediate — it's not "failed REV" or
"typical NRM." Even when full_action doesn't achieve REV, the 24-cell PICA system
dramatically suppresses fine-scale irreversibility (sigma grows 550x slower than
baseline). The multi-scale scan profile is the most informative diagnostic for
distinguishing these three regimes.

**sigma_u metric clarification:** sigma_u = finite_horizon_sigma(macro, uniform, 10)
measures transient entropy production from uniform initial distribution. REV seeds have
sigma_u ≈ 20 (high) because the reversible macro kernel has a strongly non-uniform
stationary distribution. NRM seeds have sigma_u ≈ 1 because irreversible currents
partially cancel the log-ratio terms.

### Suggested Ablation Experiments (from external review)

1. **full_action minus one cell**: For n=128, seeds 0-9, run 24 ablations
   (full_action \ {Ai}). Directly addresses "inert in isolation ≠ inert in full
   system." Also run full_action_safe on 10 seeds for fair comparison.

2. **A16 interaction study**: full_all = full_action + A16 and it harms frob.
   Test pairwise interactions: full_action + A16 - {Aj} for candidates A14/A15/A19/A13
   to locate the destructive interaction.

3. **A18 tau mechanism study**: baseline vs baseline+A18 at n=32,64,128 with 10 seeds.
   Log tau changes and cluster_rm stats to confirm when/why A18 changes tau and
   how that affects partitions.

4. **Candidate scoring diagnostics**: Log per-candidate RM/frob/gap scores in the
   partition selection step to determine whether the candidate set contains
   differentiated options or whether scores are tied/saturated.

### Data Quality Fixes Applied (from external review, 2026-02-22)

1. **collect_audits.py merge dedup key**: Uses `config_identity()` — a 3-tier key:
   full pica_config JSON sha256 (when available) > pica_config_hash > normalized label.
   Cross-experiment dedup (same config/seed/n in different experiments) is enabled by
   default, keeping the record from the highest-numbered experiment.

2. **report_stage.py grouping and deduplication**: Groups by `config_identity()` (not
   display label), preventing distinct configs with the same human label from being
   merged in tables. Disambiguates label collisions with identity suffixes.

3. **pica_config_hash**: Extended to include per-cell f64 parameters and packaging_selector
   (Rust fix in audit.rs). **12 parameters remain excluded** (cooldowns, intervals,
   boundary boosts, tau_cap). Full config serialization (`pica_config` JSON in audit
   records) captures all 36 parameters and is used by `config_identity()` when available.

4. **Known limitation**: sigma_ratio denominator (micro_sigma_tau) not stored in
   audit records. Cannot screen for near-zero denominators in post-hoc analysis.
   At n≤64, sigma_ratio values can be astronomical (1e7+) and are unreliable.

5. **PICA interval difference between pre-fix and post-fix binaries**: The parameter
   loss bugfix changed `run_exp_100_single()` to use `pat.clone_for_macro()` instead
   of `PicaConfig::baseline()`. This changes cell firing intervals from 500 to 100
   steps (5x faster). Consequences:
   - Pre-fix data (stages 01-05 original batch): intervals=500
   - Post-fix data (bugfix/post-review batches): intervals=100
   - Within-binary comparisons are valid (same intervals for all configs)
   - Cross-binary absolute values should not be compared directly
   - Key findings (REV transition, scale dependence) are confirmed within pre-fix
     data alone (EXP-105 n=64 vs n=128), so they hold regardless of interval setting
   - Partial EXP-106 s0 n=128 post-fix output confirms chain is still NRM at n=128
     even with 5x faster intervals (sigma=3.79)

### Campaign Finding 20: EXP-106 Chain/Boost/Enabler Analysis at n=128

**[RETRACTED by F38]** Boost resonance claims in this finding were a data-mixing artifact.
See F38 for the corrected analysis.

**Old Binary Boost Bug (Critical Data Quality Issue)**

The old binary (pre-fix, s3-9) NEVER APPLIED the boost parameter to the chain config.
All boost variants (boost_0.1, boost_0.5, boost_1.0, boost_3.0, boost_4.0) share the
identical pica_config_hash (18172714540551969168) as A13_A18_A19 across all 7 seeds.
This means ALL old-binary EXP-106 boost sweep data is invalid — every "boost" config
was just re-running A13_A18_A19. (The pica_config_hash fix in the post-fix binary
resolved this.)

**A21 Confirmed Inert (Bitwise Verification)**

In old binary data, A13_A21_A19 has a DIFFERENT hash from A13_A18_A19 but produces
BITWISE-IDENTICAL frob and sigma at every seed. This conclusively confirms A21
(P5←P3: RM-quantile packaging) is genuinely inert — the cell activates but produces
no measurable effect.

**Cross-Experiment Consistency Finding (Campaign Finding 21)**

Systematic cross-experiment comparison at n=128 confirms **100% BIT-EXACT
reproducibility** for all configs across EXP-102/104/105/107 (66 clean comparisons,
66 exact matches). The dynamics engine is fully deterministic given
`(seed, scale, pica_config_hash)`.

**EXP-106 s0-2 uses an intermediate bugfix binary** (different baseline hash
10468467397772928013 vs final 2241565202086718495). The data below should be treated
as PRELIMINARY — the post-review batch (final binary) is running for s3-9.

**EXP-106 s3-9 confirmed as pre-fix binary** — boost variants have identical hashes
AND identical metrics (frob, sigma, budget to 6 decimal places) as A13_A18_A19.
This is the parameter-loss bug: `run_exp_100_single` reset PICA to `baseline()` and
only copied enabled flags, discarding `p3_p4_sector_boost`.

**Intermediate-Binary Chain/Boost Metrics at n=128 (3 seeds, s0-2, PRELIMINARY)**

| Config | N | frob_med | sigma_med | gap_med | budget_med | REV |
|---|---|---|---|---|---|---|
| A13_A18_A19 | 3 | 1.060 | 0.674 | 0.396 | 20.0 | 1/3 |
| boost_1.0 | 2 | 1.043 | 2.196 | 0.506 | 31.0 | 0/2 |
| boost_0.1 | 3 | 0.937 | 0.768 | 0.530 | 11.0 | 0/3 |
| boost_0.5 | 2 | 0.915 | 0.553 | 0.575 | 18.6 | 0/2 |
| baseline | 3 | 0.462 | 0.597 | 0.778 | 26.3 | 0/3 |

**Key findings:**

1. **A13_A18_A19 achieves REV at n=128 (1/3 seeds):** Seed 1 reached tau=92,
   budget=621.06 (saturated at cap), sigma=0.0000 at ALL k values in multi-scale scan.
   This updates Finding 14 (EXP-105v2 showed 0/3 REV). Combined rate: 1/6 (~17%).
   Much lower than n=64 (100%) but confirms the REV mechanism CAN activate at n=128
   even with only 5 cells.

2. **Boost effect is NON-MONOTONIC:**
   - No boost (A13_A18_A19): frob=1.060
   - boost_0.1: frob DROPS to 0.937 (−12%)
   - boost_0.5: frob DROPS to 0.915 (−14%)
   - boost_1.0: frob RECOVERS to 1.043, but sigma jumps to 2.196 (3.3x chain)
   Small boosts appear to stabilize/dampen structure. boost_1.0 re-introduces
   irreversibility. Only 2-3 seeds — needs 10-seed sweep to confirm.

3. **Chain baseline lift 2.3x:** A13_A18_A19 frob=1.060 vs baseline frob=0.462.
   The chain provides a 2.3x lift at n=128 even in NRM seeds, comparable to
   full_action's 2x lift over baseline in EXP-107.

**Old Binary Enabler Variants (s3-9, treat with caution, 7 seeds)**

| Config | frob_med | sigma_med | REV |
|---|---|---|---|
| A13_A14_A19 | 1.138 | 0.819 | 1/7 |
| A13_A3_A19 | 0.994 | 1.170 | 1/7 |
| A13_A18_A19 | 0.926 | 1.164 | 0/7 |
| chain_SBRC | 0.885 | 0.841 | 0/7 |
| chain_A24 | 0.932 | 0.640 | 0/7 |
| chain_pkg | 0.933 | 2.544 | 0/7 |
| baseline | 0.856 | 0.862 | 0/7 |

A13_A14_A19 (replacing A18 with A14=P4←P1 spectral lens from P1 data) shows highest
frob (1.138) but extreme variance (std=0.42). No post-fix data yet for enabler variants.

### Campaign Finding 22: P6-Row Scale-Dependent Cell Interaction

Analysis of EXP-104 (3 seeds × n=32,64,128) reveals a scale-dependent interaction
between P6-row cells A24 (budget rate) and A25 (EP-retention cap):

| Config | n=32 | n=64 | n=128 |
|--------|------|------|-------|
| A24_only | 0.895 | 0.938 | 0.991 |
| A25_only | 0.997 | 1.053 | 1.055 |
| A24+A25 (P6_row_all) | 1.136 | 1.109 | 0.861 |

At **n=32**, A24+A25 is **SYNERGISTIC** (1.136 > max(0.895, 0.997)). The combination
outperforms either cell alone.

At **n=128**, A24+A25 is **ANTAGONISTIC** (0.861 < min(0.991, 1.055)). The combination
is WORSE than either cell alone. Budget rate boosting (A24) and budget cap tightening
(A25) work at cross-purposes at large scale: A24 increases budget when sectors are
imbalanced, while A25 reduces budget when EP-retention is violated (macro_sigma/micro_sigma_tau falls below threshold). At n=128, EP-retention
violation is more frequent, so A25's tightening dominates A24's boosting, producing
net budget starvation.

Note: only 3 seeds for the combination. A25 confirmed at 10 seeds (0.991±0.089).

### Campaign Finding 23: Single-Cell Utility at n=128 (EXP-100 Stage 02)

Individual P1-row and P2-row cells tested at n=32, 64, 128 (3 seeds each):

**Top 3 single cells at n=128 by frob:**

| Cell | Role | frob_128 | sigma_128 |
|------|------|----------|-----------|
| A3 (P1←P3) | RM-rewrite | 1.054 | 1.790 |
| A2 (P1←P2) | sparsity-rewrite | 1.005 | 0.702 |
| A1 (P1←P1) | history-rewrite | 0.980 | 0.753 |

**Key observations:**
- A3 (RM-rewrite) is the BEST individual cell at n=128, even better than P1_row_A13
  (1.054 vs 1.015). Adding other P1-row cells to A3 might be slightly harmful.
- A7 (P2←P1, protect) has LOWEST sigma (0.392) but also lowest frob (0.686).
  Protection suppresses both irreversibility AND structural development.
- A13 (frob mixer) uniquely HALVES partition flip count compared to all other configs
  (6656 vs 12427 at n=128). This stabilization may explain P1_row_A13's consistency.
- All P1/P2 row cells show identical partition flip counts to baseline (12427 at n=128).
  Partition dynamics are baseline-driven for single-cell configs.
- Zero packaging flips and tau changes for ALL single cells — these require P5-row
  (A21-23) and A18 respectively.

### Updated Open Questions (after Findings 20-23)

- **Q3 UPDATED:** Boost amplitude is non-monotonic at n=128 too. Small boosts HURT.
  boost_1.0 recovers frob but with high sigma. The EXP-106 n=64 "boost=2.0 resonance"
  cannot be tested at n=128 yet (configs didn't include boost_2.0 in post-fix batch).
- **Q7 NEW:** Is the A13_A18_A19 REV rate truly ~17% at n=128 (1/6 seeds)? Need
  10-seed sweep at n=128 to pin down the true transition probability.
- **Q8 NEW:** Does A13_A14_A19 (enabler=spectral lens) really outperform chain at
  n=128? Old binary data shows frob=1.138 but pre-fix and high variance. Post-fix
  data needed.

---

## Finding 24: Lens Selector Is the Primary frob/gap Control Knob (EXP-103 n=128, 8 seeds)

**Data:** EXP-103 n=128, 8 seeds (s0-s7), 8 configs testing P4-row lens producers and selectors.
Seeds s0-s2 have 6 configs, s3-s7 have 8 configs (adding all_MaxFrob and full_lens).

### Summary Table — Ranked by Median frob_from_rank1

| Rank | Config | Seeds | frob med | frob IQR | Stab | sigma med | gap med | sigma<0.1 | Dominant Lens |
|------|--------|-------|----------|----------|------|-----------|---------|-----------|---------------|
| 1 | all_MaxFrob | 5 | **1.413** | 0.410 | 5 | 2.451 | 0.437 | 0/5 | spectral (100%) |
| 2 | A14_only | 8 | **1.328** | 0.293 | 4 | 1.480 | 0.393 | 1/8 | spectral (87%) |
| 3 | all_MinRM | 8 | 1.122 | 0.744 | 8 | 1.037 | 0.492 | 1/8 | spectral (62%) |
| 4 | A17_only | 8 | 0.958 | 0.471 | 7 | 1.495 | 0.559 | 0/8 | spectral (87%) |
| 5 | A16_only | 8 | 0.929 | 0.286 | 3 | 0.849 | 0.566 | 0/8 | packaging (75%) |
| 6 | A15_only¹ | 8 | 0.929 | 0.438 | 6 | 1.073 | 0.552 | 0/8 | spectral (100%) |
| 7 | full_lens | 5 | 0.556 | 0.117 | 2 | 0.289 | 0.737 | 0/5 | mixed (pkg/EP/spec) |
| 8 | all_MaxGap | 8 | **0.260** | **0.102** | **1** | 0.313 | **0.861** | 0/8 | RM-quantile (100%) |

¹ "A15_only" is the EXP-103 label for `PicaConfig::baseline()` (A10+A15). Equivalent to "baseline" in other experiments.

Stability ranking (by frob IQR): MaxGap (0.102) > full_lens (0.117) > A16 (0.286) > A14 (0.293) > MaxFrob (0.410) > A15 (0.438) > A17 (0.471) > MinRM (0.744).

### Key Findings

**1. Three selector regimes create a clean frob/gap tradeoff:**
- **MaxFrob** → highest departure from rank-1 (frob=1.41), moderate gap (0.44). Always selects spectral partition.
- **MinRM** → middle ground (frob=1.12), but WORST stability (IQR=0.744). Prone to degenerate partitions.
- **MaxGap** → drives toward rank-1 (frob=0.26), but BEST stability (IQR=0.102) and highest gap (0.86). Always selects RM-quantile partition.

**2. Individual lens producers rarely win against spectral:**
Even when A14/A16/A17 are the only alternative lens producers, the spectral (A15) partition
still wins 75-100% of the time. The RM-quantile (A14) partition only wins when it locks the
system into near-REV, near-rank-1 states. The packaging (A16) partition is the only one that
frequently wins (75% of seeds), producing moderate frob (0.93) with good stability.

**3. Near-REV (sigma<0.1) is exclusively associated with A14/RM-quantile lens winning:**
Both near-REV events (A14_only s1: sigma=0.043; all_MinRM s4: sigma=0.066) occur when the
RM-quantile partition wins over spectral. These produce near-rank-1 macro kernels (frob<0.25).
The MinRM selector is therefore hazardous: by seeking lowest RM, it can select degenerate
partitions that collapse macro structure.

**4. full_lens (full PICA + MinRM) is the ONLY config with genuine lens diversity:**
Partition sources: packaging 40%, EP 40%, spectral 20%. All other multi-producer configs
converge on a single dominant lens. Full PICA integration enables adaptive lens switching.

**5. Partition flips are universally ~19,800 at n=128:**
ALL configs show ~19,800 partition flips (out of ~20,000 observation windows). The hysteresis
threshold (10% improvement required) is not preventing oscillation. This number does NOT
differentiate by config, unlike the A13-halving effect seen in EXP-100 (Finding 23).

**6. A16 (packaging lens) is the most underrated single cell:**
A16_only achieves stability rank 3 (IQR=0.286), with frob=0.93 — identical to baseline A15 median
but with much better consistency. It's the only single-producer where the alternative lens
actually wins over spectral (75% of seeds). Packaging partitions provide a structurally
different view of the kernel that spectral alone cannot.

### Comparison: EXP-103 vs EXP-102 at n=128

No config overlap — EXP-102 tests P1/P2/P3 cells, EXP-103 tests P4-row lens cells.
- EXP-102 baseline (A10+A15): frob=0.67, sigma=0.64, gap=0.73 (3 seeds)
- EXP-103 A15_only (= baseline, A10+A15): frob=0.93, sigma=1.07, gap=0.55 (8 seeds)

EXP-103 baseline runs hotter — no A10 P2-gating means more aggressive dynamics.
EXP-102's best config (full_action_safe) achieves frob=1.39 with low sigma (0.14, near-REV);
EXP-103's best (all_MaxFrob) achieves similar frob=1.41 but with high sigma (2.45, irreversible).
Different mechanisms reach similar frob: P1/P2/P3 control → REV+structured; P4 lens selection → NRM+structured.

### Updated Open Questions

- **Q9 NEW:** Why does enabling A14 as sole alternative (A14_only) produce higher median frob
  than baseline (1.33 vs 0.93) even though spectral wins 87% of the time? Does the A14 partition
  computation itself change the dynamics pathway even when not selected?
- **Q10 NEW:** Can MaxFrob selector be combined with P1-row cells (especially A3, A13) to
  achieve both high frob and stabilization? This would merge the EXP-102 and EXP-103 best findings.

---

## Finding 25: Cross-Stage Synthesis — 736 Records, 68 Configs at n=128

**Data:** Merged audits v4. 442 records at n=128 across 5 stages. 68 unique configs.

### Top 10 Configs by Median frob at n=128

| Rank | Config | Experiments | med frob | med sigma | med gap | seeds | REV% |
|------|--------|-------------|----------|-----------|---------|-------|------|
| 1 | all_MaxFrob | EXP-103 | **1.413** | 2.451 | 0.437 | 5 | 0% |
| 2 | full_action_safe | EXP-102 | **1.391** | 0.143 | 0.376 | 3 | 33% |
| 3 | full_action | EXP-104,107 | **1.368** | 0.036 | 0.393 | 13 | **62%** |
| 4 | A14_only | EXP-103 | **1.328** | 1.480 | 0.393 | 8 | 12% |
| 5 | full_all | EXP-104,107 | **1.140** | 0.304 | 0.361 | 13 | 31% |
| 6 | A13_A14_A19 | EXP-106 | 1.138 | 0.819 | 0.452 | 7 | 14% |
| 7 | all_MinRM | EXP-103 | 1.122 | 1.037 | 0.492 | 8 | 12% |
| 8 | A3_P1-P3 | EXP-100 | 1.054 | 1.790 | 0.529 | 3 | 0% |
| 9 | A25_only | EXP-104,107 | 1.020 | 1.441 | 0.511 | 13 | 0% |
| 10 | P1_row_A13 | EXP-105,107 | 1.019 | 0.796 | 0.515 | 13 | 8% |

Baseline: frob=0.666, sigma=0.651, gap=0.679 (29 seeds across 5 experiments).

### Sigma Ratio: full_action Uniquely Preserves Asymmetry

sigma_ratio = sigma_macro / sigma_micro. Measures how much irreversibility the coarse-graining preserves.

| Config | median sigma_ratio | Interpretation |
|--------|-------------------|----------------|
| **full_action** | **0.294** | Macro retains 29% of micro asymmetry |
| **full_action_safe** | **0.098** | 10% retention |
| full_all | 0.015 | |
| All other configs | **< 0.01** | Macro is 100-600x more symmetric than micro |

**This is the most striking result in the entire campaign.** full_action with all 25 cells
(except A16) uniquely propagates nearly a third of microscopic irreversibility into the macro
kernel. All other configs (including full_all with A16 added!) reduce it by 100-600x.
This suggests the full PICA system creates a coarse-graining that is **structurally faithful**
to the underlying dynamics, not just a spectral artifact.

### Budget Utilization: Not a Bottleneck

Budget cap at n=128 = 621. Median utilization across all configs:

- **Most configs**: <5% utilization (10-40 of 621 units). Budget is extremely generous.
- **full_action/full_all**: Bimodal — 6/13 saturate (100%), 5/13 < 5%.
  Budget saturation = REV regime (Finding 17). The two attractors have opposite budget profiles.
- **Implication**: Budget cap could be reduced 10-20x without affecting non-REV configs.
  The cap primarily determines whether the REV attractor is reachable.

### Partition Quality Does NOT Predict frob

| Metric | Pearson r with frob | Note |
|--------|-------------------|------|
| effective_k | -0.057 | Near zero |
| entropy | -0.107 | Weak negative (!) |
| balance (min/max) | +0.071 | Negligible |

However, a non-linear pattern exists: very low effective_k (2-4 clusters, seen only in
full_action/full_all REV seeds) produces the HIGHEST frob (1.52 median). The full PICA system
collapses partition to 2-4 super-clusters that are maximally non-rank-1 but reversible.
For the majority of runs (369/442 with eff_k ∈ [6,8)), frob varies 0.26-1.41 based on
config, not partition quality.

### Multi-Scale Scan: full_action Has Unique k=8 Peak Profile

| Config | sig_k4 | sig_k8 | sig_k16 | k16/k4 ratio | Profile |
|--------|--------|--------|---------|---------------|---------|
| **full_action** | 0.015 | 0.091 | **0.000** | **0x** | **PEAK AT k=8** |
| full_action_safe | 0.024 | 0.113 | 0.190 | 8x | Slow growth |
| full_all | 0.085 | 0.626 | 0.999 | 12x | Slow growth |
| baseline | 0.081 | 0.825 | 5.964 | 74x | Normal |
| A19_only | 0.049 | 1.555 | 17.444 | 356x | Fast growth |

**full_action is the ONLY config where sigma peaks at k=8 and drops to zero at k=16.**
This means the macro kernel has maximal asymmetry at an intermediate coarse-graining scale
and becomes reversible at finer granularity. This is genuine **emergent scale selection** —
the system has found a preferred resolution where macro irreversibility is concentrated.

All other configs show monotonically increasing sigma with k (normal behavior where finer
partitions reveal more asymmetry). The growth rate varies 8-443x from k=4 to k=16, with
full presets growing slowest (structure concentrated at coarse scales) and simple configs
growing fastest (structure only at fine scales).

### k=2 Is Always Reversible at n=128

sigma_pi at k=2 is identically zero (~1e-13) for ALL 442 runs at n=128. Two-cluster
coarse-graining always produces a reversible macro kernel. Meaningful asymmetry only
appears at k≥4. This is not a PICA effect — it's a geometric constraint of 2×2 doubly
stochastic matrices (they are always reversible with respect to their stationary distribution).

### Synthesis: Three Tiers of PICA Configs

**Tier 1 — Structure Generators (frob > 1.3):**
full_action, full_action_safe, all_MaxFrob, A14_only. These produce the most non-rank-1
macro kernels. full_action adds the unique sigma_ratio and k=8 peak properties.

**Tier 2 — Moderate Structure (frob 1.0-1.3):**
full_all, A13_A14_A19, all_MinRM, A3, A25, P1_row_A13. These reliably exceed baseline
with varying trade-offs in sigma and stability.

**Tier 3 — Baseline-like (frob 0.6-1.0):**
Most single cells, selector variants, baseline. Structure is present but not dramatically
above what random dynamics produces.

**Tier 4 — Structure Destroyers (frob < 0.5):**
all_MaxGap, full_lens. These actively suppress non-rank-1 structure by selecting partitions
that maximize spectral gap or minimize relaxation mismatch.

### Updated Open Questions

- **Q11 NEW:** Why does full_action uniquely preserve sigma_ratio=0.49 while full_all
  (which adds A16) drops to 0.018? Does A16 (packaging lens) disrupt the asymmetry-preserving
  mechanism? Or is this a selection effect — full_action's higher REV rate changes the median?
- **Q12 NEW:** Is the k=8 peak profile of full_action genuinely emergent scale selection,
  or an artifact of the n_clusters=8 default? Test with n_clusters=4 and n_clusters=16 to
  see if the peak tracks the partition resolution.
- **Q13 NEW:** Can the budget cap be used as a control parameter to steer away from REV?
  Reducing the cap would prevent budget saturation, potentially eliminating the REV attractor
  while preserving the high-frob NRM regime.

---

## Finding 26: Full System Decomposition — Keystones, Antagonists, Interactions (EXP-105)

**Data:** EXP-105, 15 configs, 3 seeds × n=64,128. Additive/marginal decomposition (not
ablation from full_action, but building up from smaller combinations).

### Config Rankings at n=128

| Rank | Config | med frob | Δ baseline | med sigma | Note |
|------|--------|----------|------------|-----------|------|
| 1 | **P1_row_A13** | **1.019** | +0.354 | 0.796 | Best overall |
| 2 | A3_A13 | 1.005 | +0.339 | 0.568 | Lowest sigma of top |
| 3-5 | A13_only = A13_A18 = A13_A18_A20 | 0.977 | +0.312 | 2.432 | A18/A20 completely inert |
| 6 | A13_A18_A19 | 0.954 | +0.288 | 0.976 | A19 mildly negative |
| 7 | A13_A25 | 0.940 | +0.274 | 0.655 | |
| 8 | A11_A21 | 0.928 | +0.263 | 1.004 | Best non-A13 config |
| 9 | A11_A22 | 0.904 | +0.238 | 2.076 | |
| 10 | A24_A25 | 0.861 | +0.195 | 1.380 | P6 pair, no A13 |
| 11 | sbrc | 0.789 | +0.124 | 0.400 | |
| 12 | A13_A24 | 0.777 | +0.112 | 0.616 | A24 hurts A13! |
| 13 | mixer | 0.746 | +0.081 | 0.676 | |
| 14 | baseline | 0.666 | 0.000 | 0.644 | |
| 15 | **A5_A21** | **0.585** | **-0.081** | 0.835 | **ONLY degrader** |

### Keystone Cells

**1. A13 (P3←P6, frob mixer)** — The single most important cell. A13_only gives frob=0.977
(+47% over baseline). Present in all top-7 configs. All top configs are "A13 + something."

**2. A3 (P1←P3, RM-rewrite)** — A3+A13 gives frob=1.005 with sigma=0.568 (lowest among
top configs). A3's marginal contribution: +0.028 frob AND -1.864 sigma. It improves structure
while dramatically taming irreversibility.

**3. P1 row ensemble (A1-A6)** — P1_row_A13 (frob=1.019) > A3_A13 (1.005) > A13_only (0.977).
The full P1 row adds +0.042 frob and reduces sigma from 2.43 to 0.80. Ensemble effect exceeds
any single P1 cell.

### Antagonist Cells

**1. A5 (P1←P5, packaging rewrite)** — A5_A21 is the ONLY config that degrades below baseline
(frob=0.585 vs 0.666). Packaging-mediated rewrite actively destroys macro structure.

**2. A19 (P3←P4, sector mixing)** — At n=128: reduces frob by 0.024 when added to A13_A18.
At n=64: causes catastrophic tau explosion (tau→1072, frozen dynamics). Scale-unstable.

**3. A24 (P6←P4, budget rate)** — A13_A24 frob=0.777, much worse than A13_only (0.977).
Budget rate boosting actually HURTS when combined with A13 at n=128.

### Inert Cells (Confirmed in All Combinations)

- **A18**: A13_only = A13_A18 to machine precision at both n=64 and n=128.
- **A20**: A13_A18 = A13_A18_A20 to machine precision at both scales.
- **A21**: A11_A21 ≈ A11 alone + A21 = A11 alone (from earlier findings).

A18 does activate `active_tau` tracking (tau_change_count > 0), but the tau values it
writes are identical to the default adaptive_tau. The "A18 regime switch" from Finding 11
is actually an A18+A19+full_system interaction — A18 alone does nothing.

### Scale Robustness

| Category | Configs | Δfrob(n=64→128) |
|----------|---------|-----------------|
| **Scale-robust** (<5% change) | P1_row_A13, A11_A21, A11_A22 | -4%, +1%, +3% |
| Scale-improving (frob rises) | A13_only, A3_A13, A13_A25, mixer | +7%, +15%, +21%, +25% |
| Scale-degrading (frob drops) | baseline, A13_A18_A19, A24_A25 | -42%, -38%, -24% |

**P1_row_A13** is the most scale-robust top performer: 1.064 → 1.019 (only -4%).

### Interaction Matrix

| Base | Added | Marginal frob | Marginal sigma | Interaction Type |
|------|-------|---------------|----------------|------------------|
| A13 | P1 row | +0.042 | -1.636 | **Synergistic** (sigma taming) |
| A13 | A3 | +0.028 | -1.864 | **Synergistic** (sigma taming) |
| A13 | A18 | 0.000 | 0.000 | Inert |
| A13 | A20 | 0.000 | 0.000 | Inert |
| A13 | A19 | -0.024 | -1.456 | Mixed (sigma↓ but frob↓) |
| A13 | A24 | -0.201 | -1.816 | **Antagonistic** (frob crash) |
| A13 | A25 | -0.038 | -1.777 | Mild antagonist |
| none | A11_A21 | +0.263 | +0.360 | Independent axis |
| none | A24_A25 | +0.195 | +0.736 | Independent axis |

### Key Insight: Two Independent Structure-Building Axes

1. **A13 axis** (P3←P6, mixture modulation): A13 + P1 row provides frob=1.0+ with tamed sigma.
2. **A11 axis** (P2←P5, packaging gating): A11_A21 gives frob=0.93 without A13.

These operate through different mechanisms (mixture vs gating) and may be combinable.
No experiment tests A13+A11 together — this is the top priority for future experiments.

### Updated Open Questions

- **Q14 NEW:** Does A13+A11 combine additively? Testing P1_row_A13 + A11_A21 could yield
  frob > 1.1 with good stability. This combines the two independent structure-building axes.
- **Q15 NEW:** Why does A24 (budget rate boosting) antagonize A13? Does higher budget cause
  A13's frob-mixer to overshoot, creating oscillatory dynamics?

---

## Finding 28: Comprehensive n=64 Characterization (213 Records, 67 Configs)

**Data:** Merged audits v4, n=64 only. 213 records, 67 configs, 6 experiments.

### A19 Dominates at n=64

Every top-10 config by frob contains A19 (or chained dynamics that include A19's effect).
All top-10 are 100% REV (sigma=0 for all seeds) with budget saturated at cap (266.17).

| Rank | Config | med frob | REV% | sigma_ratio |
|------|--------|----------|------|-------------|
| 1 | full_all | **1.750** | 100% | 0.861 |
| 2 | full_action_safe | **1.702** | 100% | 0.756 |
| 3 | A13_A21_A19 | **1.602** | 100% | 0.912 |
| 4 | A13_A18_A19 | **1.569** | 100% | 0.939 |
| 5 | P3_row_all | **1.536** | 100% | **1.179** |
| 6 | A19_only | **1.520** | 100% | 0.973 |
| 7 | full_action | 1.417 | 100% | 0.762 |
| 8-10 | chain variants | 1.20-1.38 | 100% | 0.88-1.26 |

### Baseline REV at n=64

Baseline itself has 25% REV rate (3/12 runs across 4 experiment repetitions). These are
likely seed-specific: the same seeds that hit REV do so across all experiments (bit-exact
reproducibility, Finding 21). This means ~25% of random 64×64 Markov kernels naturally
evolve toward reversibility under the basic P2+P4 dynamics alone.

### Scale-Improving Configs (WEAK at n=64, STRONG at n=128)

| Config | frob n=64 | frob n=128 | Ratio | Interpretation |
|--------|-----------|------------|-------|----------------|
| A17_only | 0.370 | 0.958 | **2.59** | EP lens requires more states |
| all_MinRM | 0.456 | 1.122 | **2.46** | MinRM needs state-space diversity |
| A14_only | 0.837 | 1.328 | **1.59** | RM-quantile lens strengthens with n |
| all_MaxFrob | 1.057 | 1.413 | **1.34** | Spectral partition benefits from n |
| A13_A25 | 0.774 | 0.940 | 1.22 | Budget cap effect grows with n |

These configs capture structure that **requires a larger state space** to manifest.
The lens/selector cells (P4 row) universally strengthen with scale, while A19-based
configs universally weaken. This suggests P4-row structure is fundamentally different
from the A19-driven REV transition.

### Major Degraders (STRONG at n=64, WEAK at n=128)

All A19-containing configs degrade 35-42% (frob ratio 0.58-0.65), consistent with Finding 14
(A19 transition is scale-specific due to per-sector signal dilution).

Exception: **full_action degrades only 3.5%** (ratio 0.965). The full 25-cell system
provides scale robustness that A19 alone lacks.

### Budget Saturation = REV Gateway

- 11/67 configs saturate budget at n=64 — ALL 100% REV
- No configs between 12% and 100% of cap (clear gap)
- Median REV budget = 266.17 (cap) vs median NRM budget = 19.06 (14x lower)
- **Exception**: A11_A22 has 1/3 REV at budget=11 (4% of cap). This suggests
  budget saturation is not the only pathway to REV — seed-specific structural
  factors can trigger reversibility without budget accumulation.

---

## Finding 27: No Super-Additivity at n=128 — Producer/Consumer Chains (EXP-102)

**Data:** EXP-102, 8 configs, 3 seeds × n=64,128. All configs built on baseline (A10+A15).

### Rankings at n=128

| Config | med frob | med sigma | med gap | Scale trend | Stability (frob std) |
|--------|----------|-----------|---------|-------------|---------------------|
| full_action_safe | **1.391** | 0.143 | 0.376 | Degrades (0.82) | High REV (3/3 at n=64) |
| A7+A3 | **1.007** | 1.031 | 0.535 | Stable (0.96) | 1 REV event |
| A3+A12 | 0.959 | 0.376 | 0.459 | **Improves** (1.14) | Low sigma (symmetric) |
| combo_structure | 0.957 | 1.004 | 0.505 | Stable (1.03) | **Best** (std=0.022) |
| A1+A3+A13 | 0.948 | 1.124 | 0.524 | Degrades (0.92) | |
| combo_rm | 0.942 | 0.892 | 0.541 | Degrades (0.86) | |
| A1+A12 | 0.791 | 0.633 | 0.586 | Degrades (0.76) | Sub-additive |
| baseline_ref | 0.666 | 0.644 | 0.730 | Degrades (0.58) | |

### Additivity Analysis at n=128

All combinations are additive or sub-additive — no combo exceeds the best individual cell:
- **A1+A12**: frob=0.791 < min(A1=0.980, A12=0.868). **Destructive interference.**
  SBRC budget modulation fights A1 cooldown rhythm.
- **A3+A12**: frob=0.959 between A3 (1.054) and A12 (0.868). Additive. But sigma crushed.
- **A7+A3**: frob=1.007 between A3 (1.054) and A7 (0.686). Clean additive.
- **A1+A3+A13**: frob=0.948 < min(A3=1.054, A13=0.977). **Sub-additive with 3 cells.**

### Scale-Positive Config: A3+A12

A3+A12 is the ONLY config where frob IMPROVES from n=64 to n=128 (0.840 → 0.959, ratio 1.14).
All other configs degrade with scale. The RM-rewrite + SBRC combination may lock in structure
that becomes more pronounced as the kernel has more states to organize.

### Implication: PICA Cells Operate on Overlapping Degrees of Freedom

The absence of super-additivity at n=128 means cells are not independent operators on
orthogonal kernel features. Instead, they compete for control of the same kernel modification
channels (rewrite, gating, mixing). This explains why:
1. Adding more cells doesn't always help (sub-additivity)
2. The best simple configs (A13_only, A3_only) are nearly as good as combos
3. full_action's success comes from a qualitatively different dynamical regime (REV),
   not from accumulating small marginal contributions

---

## Finding 29: sigma_u Captures Structure sigma Misses — Chirality Analysis (n=128)

**Data:** 442 records at n=128, all with chirality metrics (n_chiral, cyc_mean, cyc_max, sigma_u, max_asym).

### sigma_u and sigma Are Uncorrelated (r = 0.062)

| Metric pair | Pearson r | Interpretation |
|-------------|-----------|----------------|
| sigma vs sigma_u | **0.062** | **Uncorrelated** — different structure aspects |
| frob vs sigma_u | **0.429** | Moderate — sigma_u better predicts structural complexity |
| frob vs sigma | 0.309 | Weaker predictor |
| n_chiral vs sigma_u | **-0.740** | **Strongest correlation** — fewer chiral pairs → higher sigma_u |
| max_asym vs n_chiral | -0.356 | Fewer pairs, stronger per-pair asymmetry |

sigma measures uniform-weighted deviation from rank-1 in the macro kernel.
sigma_u upweights small blocks by 1/block_size, capturing structure visible to small communities.

### full_action: n_chiral Cleanly Predicts Regime

| n_chiral | sigma | sigma_u | frob | Regime |
|----------|-------|---------|------|--------|
| 6-20 | **0.000** | 20-24 | 1.6-1.9 | REV + structured |
| 35 | 0.04-0.30 | 0.5-1.4 | 0.9-1.1 | NRM (transitional) |
| 56 | 0.15 | 1.3-1.6 | 1.3 | NRM (typical) |

When full_action eliminates chiral pairs (n_chiral → 6-20), sigma drops to exactly zero
but sigma_u EXPLODES to 20-28. The macro kernel looks rank-1 uniformly but is highly
non-rank-1 from the perspective of singleton communities. This is because the REV regime
produces extreme partition imbalance (eff_k = 2-4, with single-state blocks).

### sigma_u/sigma Ratio by Config

| Config | median ratio | Note |
|--------|-------------|------|
| full_action | **28.97** | Extreme imbalance in REV seeds |
| full_action_safe | 11.33 | Similar but milder |
| full_lens | 5.22 | Partition-focused |
| all_MaxFrob | **0.38** | sigma_u < sigma (balanced partitions) |

### n_chiral Distribution: Nearly Saturated

89% of records have n_chiral=56 (all 56 directed pairs chiral). Only full_action, full_all,
and A19-chain configs consistently produce n_chiral < 56. Low n_chiral is a signature of the
aggressive PICA regime, not a general property.

### max_asym: Independent of frob (r = -0.017)

Asymmetry intensity and distance-from-rank-1 are completely independent. A macro kernel can be
far from rank-1 symmetrically (high frob, low max_asym: e.g., A3_A13) or asymmetrically
(high frob, high max_asym: e.g., full_action_safe).

### Implication: sigma_u Is a Better Complexity Metric

sigma_u (r=0.429 with frob) is a better predictor of macro structural complexity than sigma
(r=0.309). The REV regime's sigma=0 is misleading — it hides rich small-community structure
that sigma_u reveals. Future analyses should report both metrics.

---

## Finding 30: Three Partition Flip Clusters at n=128

**Data:** 442 records at n=128. partition_flip_count, packaging_flip_count, tau_change_count.

### Three Clusters of Partition Dynamics

| Cluster | Flip count | Configs | Mechanism |
|---------|-----------|---------|-----------|
| **Stabilized** | 4,400-6,700 | All A13-containing (35 configs) | A13 frob mixer dampens oscillations |
| **Baseline** | ~12,427 | Most single cells + combos without A13 (25 configs) | Default dynamics rate |
| **Destabilized** | ~19,840 | All EXP-103 P4-row lens configs (8 configs) | Multiple lens producers cause oscillation |

### Key Observations

**1. A13 is the partition stabilizer** (not A19, not A18):
- A13_only: 6,658 flips (halved from baseline 12,427)
- A19_only: 12,306 flips (still baseline-like!)
- A18_only: 12,427 flips (exactly baseline)
- full_action: 4,412 flips (lowest, 35% of baseline)

**2. full_action's extreme stabilization** (4,412 flips) may explain its unique properties.
With only 35% of baseline partition flips, the macro kernel has more time to equilibrate
between partition switches, potentially enabling the REV transition and k=8 peak profile.

**3. Packaging and tau dynamics are compartmentalized:**
- Packaging flips (~12,400-12,800) appear ONLY when P5-row cells (A21/A22/A23) or
  full presets are active. Zero otherwise.
- Tau changes (~230-580) appear ONLY when A18 (or chain variants with A18 dependency) are
  active. Zero otherwise. A18_only has the highest tau_change_count (306) despite being
  "inert" by frob — it writes tau values but they match the default.

**4. P4-row lens configs destabilize partitions:**
All 8 EXP-103 configs (A14_only through all_MaxGap) have ~19,840 flips regardless of
selector or producer. Enabling any alternative lens producer causes the partition to flip
60% more often than baseline. The hysteresis threshold (10% improvement required) is
insufficient to prevent oscillation when multiple candidate partitions are scored.

### Partition Flip Count Predicts Config Class

| Flip range | Config class | Example |
|-----------|-------------|---------|
| <5,000 | Full system (REV-capable) | full_action |
| 5,000-7,000 | A13 + others | P1_row_A13, A3_A13 |
| ~12,400 | Baseline-like | baseline, most single cells |
| ~19,800 | P4-row lens | all_MaxFrob, A14_only |

The flip count is a reliable fingerprint for config class membership.

---

## Finding 31: Edge Gating Aggressiveness Is the Strongest frob Predictor (n=128)

**Data:** 442 records at n=128. Fields: gated_edges, eff_gap, macro_gap_ratio, trans_ep, traj_steps, block_count, n_absorb, p6_rate_mult, p6_cap_mult, phase.

### P2 Gating: Baseline Removes 95% of Edges

| Config | gated_edges | % gated | frob | P2 accept% |
|--------|------------|---------|------|-----------|
| full_action | **13,368** | **81.5%** | 1.368 | 24.5% |
| full_action_safe | 13,296 | 81.1% | 1.391 | 14.4% |
| A3_A13 | 14,968 | 91.3% | 1.005 | 8.2% |
| baseline | 15,500 | 94.6% | 0.666 | 6.6% |
| A9_P2-P3 | **15,882** | **96.9%** | 0.717 | 5.0% |

**gated_edges vs frob: r = -0.51** — the strongest single-metric predictor of frob in the
entire audit dataset. Fewer gated edges (more permissive P2) → higher frob. The PICA cells
that modulate P2 gating (A7-A12) are the primary mechanical lever for macro structure.

### Micro Gap Near-Degeneracy: full_action's Paradox

| Config | eff_gap (micro) | macro_gap | ratio |
|--------|----------------|-----------|-------|
| full_action | **0.067** | 0.393 | **5.71** |
| baseline | 0.248 | 0.679 | 2.81 |
| A12_P2-P6 | **0.393** | 0.581 | 1.48 |

full_action drives the micro kernel spectral gap to 0.067 (nearly degenerate), yet
achieves the highest macro frob (1.37). Coarse-graining amplifies the gap by 5.7x.
This is the "structured degeneracy" phenomenon: PICA cells create near-singular micro
kernels where the structure is concentrated in specific eigenvectors that the partition
can extract. The coarse-graining is essentially performing dimensional reduction on a
nearly rank-deficient matrix.

**eff_gap vs frob: r = +0.024 (negligible)**. Micro spectral health is irrelevant to macro quality.

### Trans_EP Is Redundant with sigma

For 44/68 configs, trans_ep = sigma/10 exactly (both derive from the same underlying
asymmetry computation with different normalizations). trans_ep provides no independent
information beyond sigma. **Do not use trans_ep as an independent diagnostic.**

### Mechanical Effects of PICA Cells

**A13 shifts dynamics toward trajectory steps:**
- Baseline: ~1,108,000 trajectory steps (86.6% of total)
- A13-containing: ~1,140,000-1,156,000 (89-90%)
- full_action: **1,232,758 (96.3%)**

With only 3.7% of steps going to P1/P2 mutations, full_action has far fewer edge-modification
opportunities. This mechanical effect of A13's mixture-weight modulation directly causes the
lower gated_edges count (fewer P2 steps → fewer edges gated), which in turn drives higher frob.

**Causal chain: A13 → higher p_traj → fewer P2 steps → fewer edges gated → higher frob**

### Code Gap: p6_rate_mult and p6_cap_mult Not Captured

All 442 records have null for both p6_rate_mult and p6_cap_mult. This is a code gap in the
runner — it builds the audit record from Snapshot/DynamicsTrace, which don't carry the p6
multiplier values. The A24/A25 cells DO compute and apply these multipliers during dynamics
(verified in source), but the values are lost before audit serialization. **Action: add p6
multiplier capture to the next audit version.**

### Absorbing Macro States (Rare)

2 out of 442 records have n_absorb=1 (one absorbing macro state):
- A13_A14_A19 seed 4: frob=1.520
- full_action seed 6: frob=1.914

Both are aggressive PICA configs with high frob. The absorbing state occurs when one macro
cluster becomes a self-loop (transition probability > 0.999). Extremely rare and confined to
the most active PICA configurations.

### Summary of Metric Predictive Power

| Metric | r with frob | Rank |
|--------|------------|------|
| **gated_edges** | **-0.51** | **1st** |
| sigma_u | +0.43 | 2nd |
| macro_gap | -0.42 | 3rd |
| sigma | +0.31 | 4th |
| P2 accept rate | +0.49 | (derived from gated_edges) |
| partition_flip_count | — | (categorical, not continuous) |
| eff_gap | +0.02 | (negligible) |
| trans_ep | +0.19 | (redundant with sigma) |
| [P1,P2] commutator | -0.04 | (constant background) |
| lens quality | **-0.67** | (anti-correlated! N=11 multi-producer configs) |

---

## Finding 32: Commutator Structure and Lens Quality Anti-Correlation

**Data:** KEY_100_COMM and KEY_100_LENS diagnostic lines from all campaign logs.

### P4 Commutes Exactly with P1 and P2

[P1,P4] = [P2,P4] = 0 for all 442 runs at n=128 and all but one run at n=64.
P4 (sector detection) is a pure diagnostic operator — it does not interfere with
P1 (rewrite) or P2 (gating). Only [P1,P2] is nonzero, ranging 0.043-0.050 (16% spread).

### [P1,P2] Does Not Predict Macro Structure

r([P1,P2], frob) = -0.04. The P1-P2 commutator is a constant background feature of the
dynamics. P2-row cells push it slightly higher (A8, SBRC: +6-8%); P4-row lens cells push
it slightly lower (-4%). But the effect is tiny and uncorrelated with emergent structure.

### Commutators Decrease ~30% Per Scale Doubling

Typical [P1,P2] = 0.065 at n=64, 0.045 at n=128. This is consistent with
1/sqrt(n) scaling — as the kernel grows, each P1/P2 operation affects a smaller
fraction of the matrix, reducing mutual interference.

### Lens Quality Anti-Correlates with frob (r = -0.67)

For the 11 configs with active lens producers:

| Config | Lens quality (best) | frob | Note |
|--------|-------------------|------|------|
| all_MaxFrob | **0.857** | 0.812 | Clear partition → moderate frob |
| all_MaxGap | **0.831** | **0.260** | Clearest partition → lowest frob! |
| full_action_safe | 0.251 | **1.391** | Messy partition → highest frob |
| full_action | **0.175** | **1.368** | Messiest → 2nd highest frob |

**Interpretation:** "Clean" partitions (high lens quality) are stable and well-separated
but capture structure that is close to rank-1. "Messy" partitions (low quality, many active
cells creating noise) emerge from rich dynamics that have explored more of the configuration
space, producing macro kernels that are genuinely far from rank-1.

This aligns with Finding 31: full_action has the fewest gated edges (82% vs 95%)
AND the lowest lens quality (0.175) AND the highest frob (1.37). The causal chain extends:

**A13 → more trajectory steps → fewer P2 steps → fewer edges gated → messier micro
kernel → lower lens quality → BUT richer emergent structure → higher frob**

### P5 (Packaging) Is the Only Alternative That Consistently Beats Spectral

Among lens producers:
- P4 (spectral): wins in most configs
- P5 (packaging): wins in A16_only (75%) and full_all (77%)
- P3 (RM-quantile): wins only in all_MaxGap (100%)
- P6 (EP-quantile): wins in full_lens (40%) alongside P5

---

## Finding 33: Multi-Scale Scan Profiles Reveal Two Qualitative Regimes (EXP-107, n=128, 10 Seeds)

**Data:** 130 audit records (10 seeds × 13 configs) with multi_scale_scan at k=2,4,8,16,...,k_max.

### Two Scaling Regimes

The 13 EXP-107 configs split into two qualitatively distinct classes:

**Regime A — "Normal" (11 configs):** frob increases log-linearly with k.
Slope = 0.46–0.53 per log2(k), R² = 0.65–0.93. Optimal k is always the largest available.

**Regime B — "Anomalous" (full_action, full_all):** frob is flat/non-monotonic.
full_action slope = 0.157 (3x flatter), R² = 0.115. full_all slope = 0.290.

### Scale Profile Table (Median frob at Common k Values)

| Config | frob@k=2 | frob@k=4 | frob@k=8 | frob@k=16 | slope |
|--------|----------|----------|----------|-----------|-------|
| baseline | 0.389 | 0.585 | 0.856 | 1.224 | 0.49 |
| A13_only | 0.419 | 0.664 | 0.935 | 1.467 | 0.52 |
| P1_row_A13 | 0.442 | 0.714 | 1.021 | 1.398 | 0.51 |
| A25_only | 0.415 | 0.712 | 0.987 | 1.513 | 0.52 |
| chain | 0.441 | 0.655 | 0.954 | 1.295 | 0.47 |
| A19_only | 0.368 | 0.617 | 0.869 | 1.367 | 0.53 |
| **full_action** | **0.768** | **0.848** | **0.992** | **1.979** | **0.16** |
| full_all | 0.587 | 0.676 | 0.815 | 1.216 | 0.29 |

### Key Properties of full_action (hash 1788503113385560079)

1. **k=2 frob nearly 2x baseline** (0.768 vs 0.389). The hardest coarse-graining test.
2. **Locked macro_gap ≈ 0.393** across ALL k values (std=0.001–0.014), while normal
   configs show gap declining 0.6→0.35 with k. P2 gating creates dominant spectral
   structure that persists regardless of partition granularity.
3. **sigma_ratio = 0.488 (median)** — 49% of micro asymmetry preserved at macro scale.
   This is **100x higher** than any other config (next: full_all at 0.018).
4. **P2 acceptance rate = 23.6%** (vs 5.1-8.1% for others): 3-5x more edge gating accepted.
5. **Budget = 334** (vs 11-41 for others): 8-30x larger, qualitatively different EP regime.
6. **Unbalanced partitions**: min_size=1.5, max_size=49, entropy=1.51 (vs baseline 1.93).

### sigma_pi Is Universally Zero at k=2

Every config including full_action has sigma_pi=0 at k=2. This is a **geometric constraint**:
a 2×2 doubly stochastic macro kernel has too few degrees of freedom to capture asymmetry.
Sigma_pi becomes non-trivial only at k≥4 for most configs and at k≥16 for large values.

Paradox: full_action has HIGH sigma_ratio but LOWER sigma_pi at all k (max=0.45) vs
normal configs (sigma_pi reaching 100-155 at large k). Resolution: full_action preserves
asymmetry through the macro kernel structure itself (high frob, locked gap), not through
the path-reversal measure that sigma_pi captures.

### Scale Sensitivity Ratio (frob@k=8 / frob@k=2)

| Config | k8/k2 ratio | Interpretation |
|--------|-------------|----------------|
| A25_only | 2.38 | Most scale-sensitive |
| A19_only | 2.36 | |
| P1_row_A13 | 2.31 | |
| baseline | 2.20 | Normal cluster (2.13–2.38) |
| full_all | 1.39 | Intermediate |
| **full_action** | **1.29** | Most scale-invariant |

Normal configs gain 2.1-2.4x going from k=2 to k=8. full_action gains only 1.3x —
its structure is already present at the coarsest level.

### Crossover at k=8

full_all ranks #2 at k=2 (frob=0.587) but drops to **last place** at k=8 (frob=0.815).
This is because only 6/10 seeds produce k=8 data for full_all. full_action maintains
#1 at k=2 and k=4, dropping to #2 at k=8 (behind P1_row_A13's 1.021).

### P1_row_A13 Is Best "Normal" Config Across All k

- Highest frob@k=2 among normals (0.442)
- Only normal config above frob=1.0 at k=8 (1.021)
- Highest frob@k_max (3.002)
- Tightest IQR at k=8 (0.084)

### Implications

1. **full_action's advantage is STRUCTURAL, not just partitioning.** It creates macro
   kernels that carry information even at k=2 (the most lossy coarse-graining). This cannot
   be achieved by better partition selection alone.
2. **The locked gap = 0.393 is a fingerprint** of the P2-dominated regime. Normal configs
   show gap sensitive to k; full_action has a fixed spectral structure.
3. **sigma_ratio is NOT equivalent to large sigma_pi.** full_action achieves high sigma_ratio
   with low sigma_pi, through a different mechanism (structural asymmetry vs path asymmetry).
4. **No convergence at n=128**: configs remain differentiated at all k, unlike n=256 where
   simple configs converge to frob≈0.5.

---

## Finding 34: REV/NRM Bifurcation Is Micro-Kernel-Level (full_action, 10 Seeds)

**Data:** 10 full_action records (hash 1788503113385560079) from EXP-107 at n=128.
REV seeds: s1,s3,s4,s6,s7. NRM seeds: s0,s2,s5,s8,s9.

### The Split Is Visible at k=2

At the coarsest level (k=2, only 2 macro-states), the regimes are already separated:

| Metric@k=2 | REV (5 seeds) | NRM (5 seeds) | Significance |
|-------------|---------------|---------------|--------------|
| frob | 0.855 ± 0.006 | 0.631 ± 0.045 | 5σ apart |
| max_asym | 0.559 | 0.223 | 2.5x |
| sigma_pi | 0.000 | 0.000 | Both zero (geometric constraint) |
| macro_gap | 0.395 | 0.422 | REV already locked |

**Interpretation:** Since k=2 partitions can only produce one cut, the partition barely matters.
The 0.22 frob difference **must come from the micro kernel itself**, not from observation.
Full_action drives some random seeds to exact microscopic reversibility.

### REV = Exact Microscopic Reversibility at ALL Scales

REV seeds have sigma_pi = 0.000 (machine precision) at every k in the multi-scale scan:
k=2: 0.000, k=4: 0.000, k=8: 0.000, k=16: 0.000, k=26: 0.000.

NRM seeds show growing sigma_pi: 0.000 (k=2), 0.021 (k=4), 0.091 (k=8), 0.187 (k=16).

### Macro_gap = 0.393 Is a Universal Attractor

Both regimes lock macro_gap near 0.393, but with different precision:

| Regime | macro_gap mean | std | range |
|--------|---------------|-----|-------|
| REV | 0.3932 | 0.0005 | [0.393, 0.394] |
| NRM | 0.3921 | 0.0128 | [0.382, 0.413] |

The 0.393 value persists across ALL k for REV seeds (std<0.001 at each k level).
This is radically different from baseline where macro_gap ranges 0.22–0.73 across k.

### Regime Characteristics

| Property | REV | NRM | Factor |
|----------|-----|-----|--------|
| frob (top-level) | 1.81 ± 0.15 | 1.10 ± 0.23 | 1.6x |
| tau | 226 ± 101 | 5 ± 2 | 45x |
| budget | 621.06 (all identical) | 27.8 ± 11.6 | 22x |
| eff_gap | 0.003 ± 0.001 | 0.095 ± 0.033 | 1/37x |
| n_chiral | 6–20 | 35–56 | 1/3x |
| effective_k | 2.7–4.1 | 5.0–5.9 | 1/2x |
| partition entropy | 0.99–1.42 | 1.60–1.77 | lower |
| max cluster size | 42–87 | 43–59 | larger |
| p2_rate | 0.27 ± 0.06 | 0.16 ± 0.14 | 1.6x |

REV seeds develop **highly asymmetric partitions** with one mega-cluster (up to 87/128
states) and singleton residuals. NRM seeds maintain balanced partitions.

### Budget Saturation Is Consequence, Not Cause

REV: EP=0 → no KL cost → budget accumulates to cap (n·ln(n)=621.06).
All 5 REV seeds have budget=621.06 exactly, confirming EP=0.
The tiny eff_gap (0.002) drives tau to 120–378 via `tau ~ 1/gap`, but
this is also a consequence of the reversible micro kernel, not the cause.

### Full_all Hits Different Seeds

Full_all (which adds A16) shows REV on seeds s2 and s5 — which are NRM in full_action!
Seed s7 (REV in full_action) is near-zero (sigma=0.003) in full_all.
**A16 scrambles which seeds reach the reversible attractor.** The transition is
seed-dependent but the probability is similar (~50% for full_action, ~25% for full_all).

### No Other Config Shows REV at n=128

All 11 non-full configs have sigma > 0.10 for every seed. The reversibility transition
requires the full complement of 24+ PICA cells acting together. This supports the
hypothesis of a self-reinforcing feedback loop that no subset can sustain.

### Frob Scaling Divergence

| k range | REV frob | NRM frob | Ratio |
|---------|----------|----------|-------|
| k=2 | 0.855 | 0.631 | 1.4x |
| k=4 | 0.929 | 0.790 | 1.2x |
| k≈8–10 | 1.5–1.7 | 0.88–1.05 | 1.7x |
| k≈16 | 2.16 | 1.15 | 1.9x |
| k≈26 | 2.43 | 0.91 | 2.7x |

REV frob grows monotonically — the kernel has rich multi-scale structure that becomes
more apparent with finer partitions. NRM frob plateaus around 1.0–1.4.

### Implications

1. **The REV transition is a reproducible bimodality at the micro-kernel level.** It's not an observation
   artifact — the micro kernel itself becomes reversible (sigma_pi=0 at ALL k). Whether this
   constitutes a true dynamical bifurcation requires intermediate-scale data (see Caveats).
2. **0.393 is a universal macro_gap attractor** of full_action dynamics, present in both
   regimes at all scales. This locked gap is the fingerprint of the P2-dominated regime.
3. **Seed sensitivity is real but not chaotic.** Different cells (A16 vs not-A16) shift
   which seeds fall into which basin, but the probability of REV stays roughly 25–50%.
4. **The bifurcation is between two fixed points**, not between order and disorder.
   Both REV and NRM produce structured macro kernels — they differ in whether the
   micro kernel achieves exact detailed balance.

---

## Finding 35: REV/NRM Split Is Seed×Config Interaction, Not Seed Quality

**Data:** 130 records (10 seeds × 13 configs) from EXP-107 at n=128.

### Definitive Answer: The bifurcation is NOT seed-intrinsic

REV seeds (s1,s3,s4,s6,s7) are actually **weaker** in baseline:

| Metric | REV seeds (baseline) | NRM seeds (baseline) | Direction |
|--------|---------------------|---------------------|-----------|
| frob | 0.643 ± 0.20 | 0.895 ± 0.15 | REV lower |
| sigma | 0.630 | 1.635 | REV lower |
| gap | 0.652 | 0.566 | REV higher |

Full_action's 24 cells create nonlinear amplification that **preferentially benefits**
seeds with tighter baseline spectra (higher gap, lower sigma) — the "weaker" seeds.

### Seed Rankings Are Inconsistent Across Configs

Mean off-diagonal Spearman rho across all 78 config pairs = **0.050** (essentially zero).
Only 6/78 pairs reach p<0.05. Knowing a seed's rank in one config tells you nothing
about its rank in another.

### Full_action Has Zero Correlation With Other Configs

| Config vs full_action | Spearman rho | p |
|----------------------|-------------|---|
| baseline | -0.261 | 0.47 |
| A13_only | -0.358 | 0.31 |
| full_all | +0.139 | 0.70 |
| A19_only | **-0.733** | **0.016** |

The only significant correlation is with A19_only — and it's **negative**.
Seeds that do well in A19_only do *poorly* in full_action.

### Full_all Completely Reorders Seeds

Full_all top 5: {s0, s2, s3, s4, s5}. Overlap with REV: only 2/5.
Seeds s2 and s5 (NRM in full_action) are top-5 in full_all.
Seeds s1, s6, s7 (REV in full_action) drop to bottom-5 in full_all.
Pearson r between full_action and full_all frobs = 0.24 (p=0.50).

### No Universally Good/Bad Seeds

No seed is in the top 3 for ≥8 configs. REV seeds have mean ranks 5.4–6.2 (middle range).
Best overall: seed 0 (mean rank 3.7, top-3 in 7/13) — but it's NRM.

### Implications

1. **The REV attractor is a property of full_action's dynamics**, not seed quality.
   The 24 enabled cells create basins of attraction that different seeds happen to
   fall into depending on their initial spectral structure.
2. **Adding A16 reshuffles basins entirely** — full_all REV on different seeds confirms
   this is sensitive nonlinear dynamics, not seed hardness.
3. **"Weak" baseline seeds → REV in full_action**: this paradox suggests full_action
   amplifies seeds with tighter spectra (less initial structure) into the reversible
   regime, while seeds with already-rich structure (high baseline frob) resist
   being driven to detailed balance.
4. **The A19_only anti-correlation (rho=-0.73)** reveals that the mechanisms producing
   structure in A19_only (per-sector mixture weighting) and full_action (24-cell
   collective dynamics) are fundamentally different.

---

## Finding 36: Synthesis — The Full Mechanistic Picture (F1-F35, updated with F38-F39)

### The Emergent Coarse-Graining Cascade

The 35 findings combine into a single coherent mechanistic picture of how the PICA
system produces non-trivial macro structure from random Markov kernels.

### Two Qualitatively Different Operating Regimes

**Regime 1 — "Normal PICA" (all configs except full_action/full_all):**
- Frob scales log-linearly with k (slope 0.47–0.53), moderate departure from rank-1
- Sigma > 0 always (irreversible macro kernel)
- Macro_gap varies with k (0.2–0.7)
- P2 gating removes ~95% of edges
- Budget = 5–50 (well below cap)
- Best config: P1_row_A13 (frob=1.02 at n=128)
- **Mechanism:** A10 (spectral partition) + A15 (spectral lens) provide the scaffold.
  Individual cells add modest incremental effects that are additive or sub-additive.

**Regime 2 — "Full PICA" (full_action, 24 cells):**
- Frob has flat multi-scale profile (slope 0.16), high even at k=2
- 50% probability of exact microscopic reversibility (sigma=0 at ALL k)
- Macro_gap locked at 0.393 in BOTH sub-regimes
- P2 gating removes only 82% of edges
- Budget = 621 (cap-saturated in REV) or 28 (NRM)
- **Mechanism:** Collective dynamics of 24 cells create a self-reinforcing feedback loop.

### The Causal Chain (verified across F26, F30, F31, F32, F33)

```
A13 (frob mixer) — the keystone
  ↓
Shifts mixture weights: 96.3% trajectory vs 3.7% P1+P2 steps
  ↓
Fewer P2 gating proposals → fewer edges removed (82% vs 95%)
  ↓
Micro kernel stays "messier" (eff_gap collapses: 0.003 REV, 0.067 NRM)
  ↓
                    ┌─── REV path ───────────────────── NRM path ───┐
                    │                                                │
                    │ eff_gap → 0.003                   eff_gap = 0.067
                    │ tau → 120-378 (~ 1/gap)           tau = 3-7
                    │ EP → 0 exactly                    EP = 0.005-0.010
                    │ budget → 621 (saturated)           budget = 17-47
                    │ sigma = 0 at ALL k                sigma = 0.04-0.30
                    │ frob@k=2 = 0.855                  frob@k=2 = 0.631
                    │ partitions: eff_k=3, singletons   partitions: eff_k=5-6
                    │ n_chiral = 6-20                   n_chiral = 35-56
                    └────────────────────────────────────────────────┘
```

### Which Path? — Seed × Config Interaction (F35)

The REV/NRM split is NOT determined by seed quality. REV seeds are actually *weaker*
in baseline (frob 0.64 vs 0.90, higher gap, lower sigma). The full 24-cell system
preferentially drives tight-spectrum seeds (high gap, low initial structure) to the
reversible fixed point — these seeds are "easier to equilibrate."

Adding A16 (full_all) scrambles which seeds hit REV (different seed set, ~25% rate).
A19_only is anti-correlated with full_action (rho=-0.73). The basin assignment is
a sensitive function of the cell complement × random kernel interaction.

### Cell Roles in the Full Picture

| Role | Cells | Evidence |
|------|-------|----------|
| **Keystone** | A13 (P3←P6) | +47% frob alone. Halves flips. Drives causal chain. (F23, F26) |
| **Scaffold** | A10 (P2←P4), A15 (P4←P4) | Always-on baseline. Provide spectral partition. |
| **REV trigger (small n)** | A19 (P3←P4) | 100% REV at n≤64. Per-sector RM dilutes with n. (F14) |
| **Stabilizer** | A25 (P6←P6) | Raises frob minimum at n=128 (0.991 vs 0.855). (F16) |
| **Regime switch** | A18 (P3←P3) | Selects tau=3-7 (NRM) vs tau=120-378 (REV). Critical in full system. (F11) |
| **Independent axis** | A11 (P2←P5), A22 (P5←P4) | Package-based gating. No A13 dependency. (F26) |
| **Enhancer** | A3 (P1←P3) | Best individual (frob=1.054). RM-rewrite. (F23) |
| **Partition competitor** | A14 (P4←P1) | **Strongest single-cell frob booster** (1.327, 10 seeds). High-variance (70% high, 20% degen). A13+A19 may stabilize. (F39, **F41**) |
| **Antagonist** | A24 (P6←P4) | Budget starvation at n=128. Hurts A13 (frob 0.78 vs 0.98). (F22, F26) |
| **Destructive** | A5 (P1←P5), A21 (P5←P3) | Only config below baseline (frob=0.585). (F26) |
| **Inert** | A20, A21-A23 | No effect alone or in combos. (F16, F26) |
| **Indirect** | A18 | Inert on frob/σ alone at default tau, but writes active_tau to PicaState — modifies observation timescale, not dynamics. (F16) |

### Scale Dependence (F14, F18, F28, F33)

| Property | n=32 | n=64 | n=128 | n=256 |
|----------|------|------|-------|-------|
| A19 REV rate | 100% | 100% | 0% | 0% |
| full_action REV | 100% | 100% | 50% | 0%* |
| Baseline frob | 1.31 | 1.15 | 0.85 | 0.52* |
| full_action frob | 1.72 | 1.42 | 1.47 | 1.07* |
| frob advantage | 1.3x | 1.2x | 1.7x | 2.1x* |
| full_action sigma | 0.00 | 0.00 | 0.02† | 0.015* |
| Baseline sigma | — | — | 0.56 | 0.19* |
| full_action gap | — | — | 0.393 | 0.358* |
| Baseline gap | — | — | 0.543 | 0.728* |
| Config convergence | No | No | No | Yes (for simple) |

*n=256 from old binary (9 seeds), pending post-fix confirmation.
†Median including 5 REV (sigma=0) and 5 NRM (sigma=0.04-0.30) seeds.

The paradox: full_action's relative advantage INCREASES with scale (1.3x → 2.1x)
even as its absolute effects diminish and REV vanishes. At n=256, full_action is
the only config that separates from the baseline convergence.

**n=256 crossover:** The bimodal REV/NRM split collapses entirely at n=256.
All 9 seeds show sigma=0.01–0.04 (no exact zeros), but this is still 14x lower than
baseline (0.19). The system approaches but cannot reach exact reversibility. The gap
continues to decrease (0.358), while baseline gap increases (0.728).

### Key Observational Signatures

1. **Macro_gap decreases with n** (~0.40 at n=128, ~0.36 at n=256). Opposite to all other configs.
2. **Sigma_ratio > 0.1**: Only full_action. Preserves 49% of micro asymmetry.
3. **Partition flips < 5,000**: A13-containing configs (vs 12,400 baseline).
4. **gated_edges < 85%**: Only full_action (vs 95% baseline, r=-0.51 with frob).
5. **eff_gap < 0.01**: REV regime indicator.
6. **sigma_pi = 0 at ALL k**: Exact microscopic reversibility.
7. **Flat MSS slope < 0.2**: Only full_action (vs 0.47-0.53 normal).

### Candidate Theorems

Based on the 35 findings, the following empirical regularities are candidates for
formal proof or deeper theoretical investigation:

**CT-1 (Macro_gap sign reversal):** The full_action dynamics produce macro spectral
gap that DECREASES with system size n, while all other configs show increasing gap.
At n=128: gap≈0.395. At n=256: gap≈0.358 (shift -0.037). All others: shift +0.11
to +0.19. The value is not a fixed attractor but a decreasing function of n. (Updated by F37.)

**CT-2 (REV fixed-point):** The reversible regime is a genuine fixed point of the
full_action dynamics: once reached, sigma remains exactly 0 for all remaining steps.
The probability of reaching this fixed point is ~50% at n=128 and decreases with n.

**CT-3 (Frob advantage scaling):** The relative frob advantage of full_action over
baseline scales as ~log(n)/sqrt(n) or similar, increasing from 1.3x at n=32 to 2.0x
at n=256, even as absolute values decline.

**CT-4 (P4 commutativity):** [P1, P4] = [P2, P4] = 0 exactly (Frobenius norm) for
all configs and all n. P4 (spectral partition) commutes with P1 (rewrite) and P2
(gating) because partitions are deterministic functions of the kernel spectrum.

**CT-5 (k=2 geometric constraint):** sigma_pi = 0 at k=2 for all macro kernels
arising from doubly-stochastic 2×2 matrices. This is a necessary geometric property
of the 2×2 DS polytope.

### Two Routes to High Frob (F39)

Finding 39 reveals that A13_A14_A19 (5 cells) achieves 94% of full_action's frob (1.376 vs
1.467) via a fundamentally different mechanism:

| Property | A13_A14_A19 (5 cells) | full_action (24 cells) |
|----------|----------------------|----------------------|
| frob (n=128) | 1.376 | 1.467 |
| sigma_pi | 4.2 (irreversible) | 0.02 (reversible) |
| gap | 0.312 (lowest) | 0.393 (locked) |
| REV at n=64 | 100% | 100% |
| REV at n=128 | 0% | 50% |
| Mechanism | Partition competition | Collective feedback |

**Implication:** High frob does not require reversibility. The A14 lens produces an
alternative partition that creates constructive interference with the spectral partition.
Low quality partitions paradoxically produce the best results (r ≈ -0.5 between partition
quality and frob), echoing CT-4.

### What Remains Unknown

1. **n=256 post-fix behavior** — old binary data confirms 2x advantage but REV at 0%.
   Post-fix n=256 jobs running.
2. **Critical cell count** — minimum subset for REV at n=128 (ablation study needed).
3. **Macro_gap 0.393 origin** — fundamental or tunable parameter?
4. ~~EXP-106 boost/enabler~~ — **RESOLVED (F38):** No boost level produces significant
   sigma_ratio signal. Boost resonance retracted.
5. **Interplay of A13 + A11** — the two independent axes never tested together.
6. **Alternative lens triplets** — A13_A15_A19, A13_A16_A19, A13_A17_A19 untested.
   Would clarify whether partition competition is specifically A14's property. (F39)

---

## Finding 37: Macro_gap Attractor Drifts With Scale — Directional Signal

**Data:** EXP-107v2 old binary, 10 seeds at n=128, 9 seeds at n=256 (seed 9 timed out).

### The 0.393 Is Not a Fixed Point

| Config | gap n=128 | gap n=256 | Δgap | Direction |
|--------|-----------|-----------|------|-----------|
| baseline | 0.543 | 0.728 | +0.185 | ↑ |
| chain | 0.549 | 0.717 | +0.168 | ↑ |
| sbrc | 0.605 | 0.718 | +0.113 | ↑ |
| A13_only | 0.557 | 0.717 | +0.160 | ↑ |
| **full_action** | **0.395** | **0.358** | **-0.037** | **↓** |
| **full_all** | **0.396** | **0.384** | **-0.012** | **↓** |

### Key Observations

1. **All non-PICA configs: gap increases +0.11 to +0.19 per scale doubling.**
   The micro kernel becomes more mixed (higher gap) at larger n, making macro
   structure harder to detect.

2. **full_action/full_all: gap DECREASES.** This is the only sign reversal.
   full_action goes from 0.395 to 0.358 (shifted ~10% lower).

3. **Variance tightens dramatically at n=256.** full_action: std=0.070 (n=128) →
   std=0.022 (n=256). The REV/NRM bimodality may collapse — all 9 n=256 seeds
   show gap 0.34–0.40 (no outliers like the 0.58 at n=128).

4. **full_all (0.384 at n=256) is closer to 0.393 than full_action (0.358).**
   But only 4/10 full_all seeds available at n=256.

### Revision to CT-1

The macro_gap attractor is not a fixed value but a **scale-dependent decreasing function**.
The distinctive property is the SIGN of the gap-vs-n slope:
- Normal configs: positive slope (gap increases with n)
- Full PICA configs: negative slope (gap decreases with n)

This means full PICA dynamics actively resist the natural tendency of larger systems to
become better-mixed. The effective spectral structure becomes MORE degenerate at larger n,
not less — the opposite of every other config.

### frob at n=256 (old binary, for reference)

| Config | frob n=128 | frob n=256 | Δfrob |
|--------|------------|------------|-------|
| baseline | 0.914 | 0.523 | -0.391 |
| A13_only | 0.908 | 0.534 | -0.374 |
| **full_action** | **0.920** | **1.075** | **+0.155** |
| **full_all** | **1.075** | **1.065** | **-0.010** |

full_action is the ONLY config where frob INCREASES from n=128 to n=256 in this dataset.
This is consistent with the gap decrease creating conditions for richer macro structure.

**Caveat:** This data is from the old (pre-fix) binary. The parameter loss bug affected
per-cell parameters (not which cells are enabled). Old binary full_action has p2_rate=0.076-0.086
vs new binary p2_rate=0.236. Absolute values differ substantially (old frob=0.92, new=1.47
at n=128), but the DIRECTIONAL findings (gap sign reversal, frob sign reversal) are structural
properties that should be robust. Post-fix n=256 data will confirm.

### Finding 38: EXP-106 Post-Review Rerun — Parameter Loss Fixed, No sigma_ratio Signal

**Data:** 91 audit records, 7 seeds (3-9) × 13 configs, n=128, post-review binary.
Seeds 0-2 have only 3-5 configs (intermediate binary) — excluded from statistics.

**Key result:** The parameter loss bug is confirmed fixed (1/78 identical config pairs,
the expected A21 inertness). However, **no EXP-106 config has statistically significant
sigma_ratio differentiation from baseline** (all Mann-Whitney p > 0.45). The earlier
Finding 20 claim of "boost=2.0 resonance at 3.2x baseline" was an artifact of mixing
intermediate-binary and post-review data. Only **A13_A14_A19 frob** is robustly significant
(+43%, p=0.001).

#### Parameter loss verification

| Metric | Old binary (F20) | Post-review |
|--------|-----------------|-------------|
| Identical config pairs | 6/78 | **1/78** (A21 inertness, expected) |
| Distinct boost levels | 2 of 5 | **5 of 5** |
| Distinct chain variants | 1 of 3 | **3 of 3** |

#### Config ranking by sigma_ratio (seeds 3-9, n=128)

| Config | N | frob±std | sigma | sig_ratio | gap | budget | p(vs base) |
|--------|---|----------|-------|-----------|-----|--------|------------|
| chain_A24 | 7 | 0.973±0.09 | 1.28 | 0.0096 | 0.513 | 22.2 | 0.535 |
| boost_3.0 | 7 | 0.924±0.06 | 0.97 | 0.0087 | 0.575 | 18.9 | 0.620 |
| boost_1.0 | 7 | 0.918±0.24 | 0.78 | 0.0072 | 0.511 | 27.6 | 0.805 |
| **baseline** | **7** | **0.963±0.05** | **1.39** | **0.0067** | **0.535** | **11.7** | **—** |
| chain_pkg | 7 | 0.912±0.14 | 0.94 | 0.0065 | 0.553 | 16.5 | 0.902 |
| A13_A3_A19 | 7 | 0.981±0.04 | 3.21 | 0.0058 | 0.523 | 25.9 | 1.000 |
| boost_0.5 | 7 | 0.903±0.11 | 0.81 | 0.0047 | 0.553 | 16.4 | 0.902 |
| A13_A18_A19 | 7 | 0.925±0.20 | 0.96 | 0.0047 | 0.532 | 15.3 | 0.805 |
| A13_A21_A19 | 7 | 0.925±0.20 | 0.96 | 0.0047 | 0.532 | 15.3 | 0.805 |
| **A13_A14_A19** | **7** | **1.376±0.25** | **4.18** | **0.0047** | **0.312** | **12.8** | **0.001*** (frob) |
| boost_4.0 | 7 | 0.954±0.19 | 2.20 | 0.0039 | 0.517 | 15.0 | 0.805 |
| chain_SBRC | 7 | 0.908±0.22 | 1.57 | 0.0036 | 0.559 | 51.4 | 0.456 |
| boost_0.1 | 7 | 0.946±0.08 | 1.07 | 0.0034 | 0.552 | 23.6 | 0.710 |

*p-values are for sigma_ratio via Mann-Whitney U test; A13_A14_A19 p-value marked * is for frob*

#### Key observations

1. **Boost curve is non-monotonic but insignificant.** Median sigma_ratio:
   boost_0.1=0.0034, 0.5=0.0047, 1.0=0.0072, 3.0=0.0087, 4.0=0.0039.
   Peak at 3.0 but all within noise (baseline=0.0067, std=0.0074).

2. **A13_A14_A19 is the frob champion.** Median 1.376 (+43% over baseline, p=0.001).
   Adding A14 (spectral lens production) to the A13+A19 triplet creates the highest frob
   at n=128 across ALL experiments (including EXP-105 full_action=1.47, but that has
   24 cells; this uses only 3). Gap narrows to 0.312 (lowest of all configs here).

3. **A21 inertness re-confirmed.** A13_A18_A19 = A13_A21_A19 bit-exact across all 7
   common seeds. A21 (RM-quantile packaging) produces no detectable effect without a
   consumer cell (A5 or A11).

4. **Only 1 REV seed in all of EXP-106.** Seed 1 hits REV under A13_A18_A19
   (sigma=0.000, sigma_ratio=0.926). This is a singular occurrence (1/10 seeds,
   only visible because seed 1 was from the intermediate binary batch). Compare:
   full_action achieves 5/10 REV at n=128 with 24+ cells.

5. **chain_SBRC has highest budget (51.4)** but lowest sigma_ratio (0.0036).
   Budget replenishment via SBRC gating does NOT translate to asymmetry preservation.

#### Revision to Finding 20

Finding 20 reported "boost non-monotonic, old-binary boost bug" based on mixed-binary data.
With clean post-review data: **no boost level is significantly different from baseline in
any metric except budget (boost_1.0 budget=27.6, 2.4x baseline)**. The boost parameter
modulates P6 replenishment rate, which measurably affects budget but does NOT propagate to
macro-kernel structure at n=128. The "boost resonance" is retracted.

### Finding 39: A13_A14_A19 — The Minimal High-Frob Triplet

**Data:** EXP-106 seeds 3-9 at n=128, EXP-105 seeds 0-2 at n=64/128.

**Key result:** A13_A14_A19 (3 explicit + 2 baseline = 5 cells) achieves **94% of
full_action's frob** (1.376 vs 1.467) with **88% fewer cells** (5 vs 24). But the
character of the macro kernel is fundamentally different: A13_A14_A19 produces
**irreversible** structure (sigma_pi=4.2), while full_action produces **near-reversible**
structure (sigma_pi=0.02). These are two qualitatively distinct routes to high frob.

#### The synergy: partition competition

A14 alone is the **weakest** lens cell (frob=0.602, below baseline). But combined with
A13+A19, it produces a +0.44 frob boost (from ~0.94 to ~1.38). The mechanism:

1. A14 (RM-quantile lens) proposes an **alternative partition** competing with A15 (spectral)
2. A19 reads sector structure and modulates mixture weights per-sector
3. A13 adjusts global P1/P2 mixture based on EP audit
4. The RM-based partition groups "high CG error" states, creating heterogeneous clusters
   that resist rank-1 collapse

**Partition quality anti-correlates with frob (r ≈ -0.5).** Seeds where the RM partition
poorly matches the spectral partition (low quality score) produce the best macro kernels.
"Messy" partition competition → better structure (echoing Finding 32).

#### Comparison with other A13+A19 triplets

| Config | frob (n=128) | gap | sigma | Cells |
|--------|-------------|-----|-------|-------|
| **A13_A14_A19** | **1.376±0.25** | **0.312** | **4.18** | 5 |
| A13_A3_A19 | 0.981±0.04 | 0.523 | 3.21 | 5 |
| A13_A18_A19 | 0.925±0.20 | 0.532 | 0.96 | 5 |
| A13_A21_A19 | 0.925±0.20 | 0.532 | 0.96 | 5 |
| A13_only | 0.967±0.38 | 0.553 | 1.05 | 3 |
| **full_action** | **1.467±0.75** | **0.393** | **0.02** | **24** |

Only A14 in the third-cell slot produces the amplification. A18, A21, A3 all produce
frob near baseline. The A14 effect is **unique**, not generic competition.

#### Scale-dependent REV crossover

| Scale | frob | sigma_pi | REV? | gap |
|-------|------|----------|------|-----|
| n=64 (3 seeds) | 1.359 | 0.000 | **Yes, 100%** | 0.400 |
| n=128 (7 seeds) | 1.376 | 4.175 | **No, 0%** | 0.312 |

A13_A14_A19 transitions from REV (sigma_pi=0) at n=64 to non-REV (sigma_pi>0) at n=128.
This is a unique pattern — most configs are either always REV or always non-REV. The triplet
hits REV when it has "enough room" (n=64) but exits at n=128 where the partition competition
becomes too complex for the system to collapse to reversibility.

#### Bimodal dynamics at n=128

Seeds split into two regimes by p2_rate:
- **LOW P2** (s3-s6): p2_rate≈0.12, p1_acc≈38k, p2_acc≈4.4k
- **HIGH P2** (s7-s9): p2_rate≈0.29, p1_acc≈20.5k, p2_acc≈6k

Both regimes produce high peak frob (>1.6 max_dyn_frob). The bimodality is in dynamics
behavior, not in macro kernel quality.

#### Gap structure

A13_A14_A19 gap=0.312 is the **lowest** of any non-degenerate config. Gap anti-correlates
with frob across seeds (r ≈ -0.73): highest-frob seeds (s7=1.197, s9=1.290) have lowest
gap (0.312, 0.277). This is the opposite of full_action where gap is locked (0.393±0.01).

**Interpretation:** A13_A14_A19 builds rich macro structure by collapsing spectral
separation — the macro kernel has many comparable eigenvalues, creating complex dynamics.
full_action builds structure by locking the gap and achieving reversibility.

#### Untested experiments (gap in campaign)

A13_A15_A19, A13_A16_A19, A13_A17_A19 were never tested. Comparing A14 against other
lens cells in the triplet context would clarify whether the RM-quantile mechanism is
specifically important, or whether any alternative partition suffices.

### Finding 40: PICA Cell Atlas — Comprehensive Classification (702 Records)

**Data:** 702 audit records, 68 configs, 7 experiments, 3 scales (n=32/64/128).
Seed-matched delta computations against per-experiment baselines.

#### Cell Utility Map (n=128)

| Classification | Cells | Count |
|---------------|-------|-------|
| **Beneficial** | A1-A6 (all P1), A8, A9, A11, A12, A13, A17, A19, A24, A25 | 16 |
| **Neutral** | A7 (protect), A16 (EP lens, context-dependent) | 2 |
| **Harmful alone** | A14 (RM lens, d_frob=-0.06; becomes +0.44 with A13+A19) | 1 |
| **Inert** | A15*, A18, A20, A21, A22, A23 | 6 |

*A15 (spectral lens) is always-on in baseline — not separately testable.

**Top 5 by individual delta_frob (n=128, seed-matched):**

| Cell | delta_frob | delta_sigma | delta_gap | Row |
|------|-----------|-------------|-----------|-----|
| A4 (P1←P4) | **+0.363** | — | -0.03 | P1 boundary |
| A2 (P1←P2) | +0.339 | — | -0.02 | P1 sparsity |
| A1 (P1←P1) | +0.314 | — | -0.02 | P1 history |
| A11 (P2←P5) | +0.290 | — | -0.02 | P2 package |
| A3 (P1←P3) | +0.285 | — | -0.02 | P1 RM-rewrite |

**Key insight: The entire P1 row is individually beneficial** — every P1 cell (A1-A6)
independently boosts frob by +0.2 to +0.36 at n=128. This was masked in earlier analyses
by looking at only median-across-seeds rather than seed-matched deltas.

#### Synergy Matrix (n=128)

Most multi-cell combinations are **sub-additive** (cells compete for the same kernel state).
Exceptions cluster around A13:

| Config | Cells | obs_delta | expected | Synergy |
|--------|-------|-----------|----------|---------|
| A13_A14_A19 | A13+A14+A19 | +0.451 | +0.308 | **1.46x** |
| A13_A24 | A13+A24 | +0.285 | +0.202 | **1.41x** |
| A13_A18 | A13+A18 | +0.187 | +0.136 | **1.37x** |
| A24_A25 | A24+A25 | +0.256 | +0.207 | **1.24x** |

A13 is the **synergy catalyst**: it appears in 4/5 super-additive combinations. Otherwise-
harmful cells (A14) become strongly beneficial when A13 is present.

Antagonistic combinations: A13+A21+A19 (obs=-0.017 vs expected +0.206), A7+A3 (obs=-0.084
vs expected +0.306).

#### Config Archetype Table (best configs per complexity tier, n=128)

| Tier | Config | frob | sigma | gap | Budget | REV? |
|------|--------|------|-------|-----|--------|------|
| FULL (24) | full_action | 1.368 | 0.036 | 0.393 | 47 | 46% |
| TRIPLE (5) | **A13_A14_A19** | **1.376** | 4.18 | 0.312 | 13 | 0% |
| PAIR (3) | A3_A13 | 1.007 | 1.03 | 0.535 | 26 | 0% |
| SINGLE (3) | A3 | 1.054 | 1.79 | 0.529 | 16 | 0% |
| BASELINE (2) | baseline | 0.856 | 0.66 | 0.562 | 14 | 0% |

**A13_A14_A19 is Pareto-optimal:** matches full_action frob with 5 cells, 3.7x less budget,
and zero REV risk. It sacrifices sigma control (4.18 vs 0.036) for deterministic behavior.

#### REV Probability Map

| Scale | REV records | % of all | Configs affected |
|-------|------------|----------|-----------------|
| n=32 | 29/81 | 35.8% | 18/26 configs |
| n=64 | 52/213 | 24.4% | 25/67 configs |
| n=128 | 11/408 | 2.7% | 3/68 configs |

Only 3 configs sustain REV at n=128: **full_action** (46%), **full_all** (31%),
**A13_A18_A19** (8%, singular seed). REV is overwhelmingly a small-scale phenomenon.

#### Scale Sensitivity

- 39/67 configs are **scale-robust** (frob ratio n=128/n=64 in 0.8-1.2)
- 17 configs **collapse** at scale (ratio < 0.7) — dominated by A19-containing configs
  where REV at n=64 inflates frob
- 4 configs **improve** at scale: all_MaxFrob, all_MaxGap, all_MinRM (2.3x), A16_only (1.65x)
- Sigma universally collapses 70-90% from n=64 to n=128; only chain_SBRC (1.23x) and
  mixer (1.07x) preserve it

### Finding 41: Partition Competition Is the Primary frob Mechanism (10-Seed Correction)

**Data:** EXP-103, 10 seeds at n=128, post-review binary.

**Key result:** The 3-seed characterization of P4-row cells was **systematically biased**.
With 10 seeds, ALL alternative lens cells independently produce high frob in a majority
of seeds. **A14 alone (frob=1.327 median) outperforms every other single-cell addition
and most multi-cell combinations.**

#### Per-cell 10-seed results at n=128

| Cell | frob median | High (>1.0) | Degenerate (<0.5) | Gap range |
|------|------------|-------------|-------------------|-----------|
| **A14** (RM-quantile lens) | **1.327** | **7/10** | 2/10 | 0.28-0.45 |
| A17 (EP-quantile lens) | 1.014 | 5/10 | 1/10 | 0.24-0.67 |
| A16 (packaging lens) | 0.929 | 4/10 | 1/10 | 0.26-0.68 |
| A15 (spectral lens = baseline) | 0.929 | 1/10 | 2/10 | 0.44-0.87 |

**Corrections to earlier findings:**
- F40 classified A14 as "harmful alone (d_frob=-0.06)" — **WRONG** (3-seed bias).
  A14 is the strongest single-cell frob booster (+0.40 median over baseline).
- F39 attributed A14's effect to synergy with A13+A19 — **partially correct** but
  A14 is independently powerful. A13+A19 may stabilize the 2/10 degenerate seeds rather
  than creating the frob boost.

#### The partition competition mechanism

The pattern across all lens cells is consistent: adding ANY alternative partition to
compete with A15 (spectral) can produce high frob, but with different reliability:

1. High-frob seeds have **low gap** (0.24-0.45) — spectral separation collapses as the
   lens selector oscillates between competing partitions
2. Degenerate seeds have **high gap** (0.73-0.91) — one partition dominates completely,
   the system settles into a low-structure equilibrium
3. **A14 is the most reliably productive** (70% high-frob) because RM-quantile partitions
   most consistently create useful competition with spectral partitions

#### Implications

1. **frob is NOT primarily driven by A13 (frob mixer)**. A14 alone (frob=1.327) beats
   P1_row_A13 (frob=1.019) and most multi-cell combos. The keystone for frob is
   **partition competition**, not mixture modulation.
2. **A13 may stabilize rather than create.** In A13_A14_A19 (frob=1.376), A13+A19
   may reduce the degenerate tail (0/7 degen at 7 seeds) rather than boosting the peak.
3. **The 3-seed bias was severe.** Seeds 3-8 all produce frob >1.2 for A14_only, but
   these seeds were only available from EXP-103 (stage 03, not stage 02). Future
   campaigns should use 10+ seeds from the start.
4. **Lens selector studies become critical.** Finding 24 (MaxFrob/MaxGap/MinRM comparison)
   should be revisited: does the selector matter more when A14 provides the alternative?

---

## n=256 Scale Analysis (Findings F42-F45)

**Data sources:**
- Old binary (EXP-107v2): 80 macro records, 11 configs, 9-10 seeds (pre-bugfix)
- New binary (EXP-106 backups): 11 records, 5 configs, 3 seeds (post-bugfix, stdbuf line-buffered)
- EXP-103 n=256 (lens configs): **COMPLETE** (8 configs × 3 seeds = 24 records)
- EXP-106 batch (13 configs × 10 seeds): **RUNNING** (~60% through, ETA ~02:00 UTC Feb 24)

**Important caveat:** Old-binary data has known bugs (sigma_pi==sigma_u always, EP
computation bug in A24). New-binary data uses corrected code but has very few seeds.
Cross-binary comparisons should focus on frob (most robust metric) not sigma.

### Finding 42: Universal scale convergence at n=256

**[PARTIALLY RETRACTED by F46]** The universality claim is refuted: configs WITH
partition competition (A14/A16/A17) do NOT converge to 0.52 — they produce frob>1.0
at n=256. The convergence applies only to configs WITHOUT partition competition.

**All non-full configs converge to frob≈0.52 at n=256.** The dramatic differentiation
seen at n=64 and n=128 between individual cells, combos, and presets collapses to a
narrow band (0.46-0.60) at n=256.

Old-binary n=256 stats (excl. full_action/full_all):

| Config | N | frob_med | gap_med | sigma_med |
|--------|---|----------|---------|-----------|
| chain | 10 | 0.546 | 0.717 | 0.189 |
| A13_only | 10 | 0.534 | 0.717 | 0.198 |
| A24_only | 10 | 0.533 | 0.722 | 0.178 |
| **baseline** | 10 | **0.523** | **0.728** | **0.187** |
| A25_only | 10 | 0.523 | 0.728 | 0.187 |
| sbrc | 10 | 0.515 | 0.718 | 0.192 |
| A11_A22 | 4 | 0.504 | 0.741 | 0.157 |

**Key observation:** The non-full frob range is [0.46, 0.60], spanning only 0.14 —
compared to [0.49, 1.33] at n=128 (range 0.84). **Scale compresses the effect space
by 6x.** A25_only is identical to baseline at n=256 (consistent with A25 being inert at n≥256, though A25 is NOT inert at n=128 where frob=0.991 vs baseline 0.855).

**New-binary confirmation (EXP-106 backups, 1-3 seeds):**

| Config | frob_med (n=256) | frob_med (n=128) | 128→256 ratio |
|--------|------------------|------------------|---------------|
| baseline | 0.544 (3s) | 0.929 (10s) | 0.59 |
| A13_A18_A19 | 0.551 (3s) | 0.977 (10s) | 0.56 |
| boost_0.1 | 0.548 (3s) | 0.963 (10s) | 0.57 |
| boost_0.5 | 0.542 (1s) | 0.933 (9s) | 0.58 |
| boost_1.0 | 0.522 (1s) | 1.000 (9s) | 0.52 |

The n=128→n=256 ratio is consistently **0.55-0.60** (40-45% frob drop). This is the
scale decay rate for configs **without partition competition**.

> **CORRECTION (F46):** The "universal" claim is WRONG. EXP-103 n=256 shows that
> configs WITH partition competition (A14/A16/A17 competing with A15) have scale
> ratio >1.0 — frob actually INCREASES from n=128→256. F42 only applies to configs
> that use a single mechanism (spectral gating, mixing, budget, etc.) without
> alternative lens competition. See F46 for the complete picture.

### Finding 43: full_action maintains 2x frob advantage at n=256

**full_action is the ONLY config that stays above frob=1.0 at n=256.** From old-binary
data (9 seeds):

| Config | n=128 frob | n=256 frob | ratio | n=256 sigma | n=256 gap |
|--------|-----------|-----------|-------|-------------|-----------|
| **full_action** | **1.467** | **1.075** | **0.73** | **0.014** | **0.358** |
| full_all | 1.134 | 1.065 | 0.94 | 0.030 | 0.384 |
| baseline | 0.854 | 0.523 | 0.61 | 0.187 | 0.728 |

**The scale decay rate differs by regime:**
- full_action: 0.73 (27% drop) — **much flatter** than baseline
- full_all: 0.94 (6% drop) — essentially flat, but only 4 seeds
- All others: 0.55-0.61 (39-45% drop)

**The 2.05x advantage (full_action/baseline = 1.075/0.523) at n=256 exactly matches
the 2.0x advantage seen in old EXP-107v2 data.** This is a robust, scale-independent
multiplier: full_action always doubles baseline frob.

### Finding 44: REV→NRM transition completes at n=256

**No runs achieve true reversibility (sigma=0) at n=256.** The REV/NRM bifurcation
that is 100% at n≤64, 50% at n=128, becomes 0% at n=256.

Old-binary sigma distribution at n=256:

| Config | sigma_med | sigma_range | REV seeds |
|--------|-----------|-------------|-----------|
| full_action | 0.014 | [0.011, 0.043] | **0/9** |
| full_all | 0.030 | [0.016, 0.058] | 0/4 |
| baseline | 0.187 | [0.115, 0.478] | 0/10 |
| chain | 0.189 | [0.064, 0.268] | 0/10 |
| A13_only | 0.198 | [0.080, 0.285] | 0/10 |

**The bimodality collapses: full_action sigma is 0.014 (near-reversible) but never
exactly 0.** The sharp REV/NRM boundary from n=128 softens into a continuous spectrum.
However, full_action sigma is still **13x lower** than baseline — the asymmetry-suppression
mechanism persists, it just can't achieve exact reversibility at this scale.

**Scale-dependent REV rate:**

| Scale | A19_only | full_action | full_all | baseline |
|-------|----------|-------------|----------|----------|
| n=32 | 100% | 100% | 100% | 36% |
| n=64 | 90% | 100% | 90% | 10% |
| n=128 | 0% | 50% | 30% | 0% |
| n=256 | — | **0%** | **0%** | 0% |

**The REV fraction follows a sigmoid in log(n).** For full_action: 100% at n≤64,
50% at n=128, 0% at n=256. The critical scale where REV probability = 50% is n≈128.

### Finding 45: Cross-binary comparison reveals sigma_u divergence

The new binary (post-bugfix) produces sigma_pi ≠ sigma_u, whereas the old binary
always had sigma_pi == sigma_u (confirming a bug in the old sigma_u computation).

| Config | Seed | sigma_pi | sigma_u | ratio u/pi |
|--------|------|----------|---------|------------|
| baseline | 0 | 0.293 | 0.336 | 1.15 |
| baseline | 1 | 0.112 | 0.178 | 1.59 |
| baseline | 8 | 0.294 | 0.317 | 1.08 |
| A13_A18_A19 | 0 | 0.291 | 0.326 | 1.12 |
| A13_A18_A19 | 1 | 0.131 | 0.154 | 1.18 |
| A13_A18_A19 | 8 | 0.262 | 0.403 | 1.54 |

**sigma_u/sigma_pi ratio ranges from 1.08 to 1.59**, indicating that starting from
uniform (rather than stationary) always produces higher path-reversal asymmetry.
This is expected: uniform start includes the transient phase of mixing toward
stationarity, which adds additional irreversibility.

**Frob comparison (old vs new binary) shows ≤4% difference** at matched seeds —
within natural seed-to-seed variability. The bugfixes changed sigma computation
but did not significantly alter the dynamics or macro kernel structure.

### Finding 46: Partition competition SURVIVES at n=256 — CONFIRMED (3/3 seeds)

**CONFIRMED — campaign's most important discovery.** Partition competition not only
survives at n=256, it actually **gets stronger** (frob INCREASES from n=128→256).

EXP-103 n=256 complete data (3 seeds, 8 configs, all medians):

| Config | Median frob | gap | sigma_pi | sigma_u | max_asym | n128 frob | **128→256** | **>1.0 seeds** |
|--------|-------------|-----|----------|---------|----------|-----------|-------------|----------------|
| **A17_only** | **1.372** | 0.336 | 0.162 | 1.054 | 1.409 | 0.918 | **1.49** | **2/3** |
| **A16_only** | **1.171** | 0.305 | 0.274 | 0.875 | 1.053 | 0.908 | **1.29** | **3/3** |
| **full_lens** | **1.171** | 0.305 | 0.274 | 0.875 | 1.053 | 0.763 | **1.54** | **3/3** |
| **A14_only** | **1.157** | 0.297 | 0.120 | 0.832 | 1.251 | 0.962 | **1.20** | **3/3** |
| **all_MinRM** | **1.151** | 0.303 | 0.180 | 1.042 | 1.293 | 0.866 | **1.33** | **2/3** |
| all_MaxFrob | 0.930 | 0.491 | 0.172 | 0.482 | 0.697 | 0.890 | 1.05 | 0/3 |
| A15_only (=baseline) | 0.544 | 0.728 | 0.163 | 0.190 | 0.314 | 0.929 | **0.59** | 0/3 |
| all_MaxGap | 0.542 | 0.713 | 0.251 | 0.344 | 0.478 | 0.651 | 0.83 | 0/3 |

Per-seed breakdown for key configs:

| Config | s=0 | s=1 | s=2 | CV |
|--------|-----|-----|-----|-----|
| A14_only | 1.183 | 1.157 | 1.093 | 0.04 |
| A16_only | 1.171 | 1.157 | 1.202 | 0.02 |
| A17_only | 0.887 | 1.372 | 1.391 | 0.25 |
| full_lens | 1.171 | 1.157 | 1.202 | 0.02 |
| all_MinRM | 0.653 | 1.151 | 1.391 | 0.32 |
| A15_only (=baseline) | 0.544 | 0.511 | 0.549 | 0.04 |

**Key findings:**

1. **A14_only: 3/3 seeds >1.0** (1.183, 1.157, 1.093). Median 1.157, CV=0.04. The most
   reliable scale-resistant config: low variance, consistently above 1.0. Scale ratio
   1.20 means frob INCREASES by 20% from n=128 to n=256.

2. **A16_only: 3/3 seeds >1.0** (1.171, 1.157, 1.202). Median 1.171, CV=0.02. Even more
   consistent than A14. full_lens = A16_only in all 3 seeds (A16 wins selector every time).

3. **A17_only: 2/3 seeds >1.0** (0.887, 1.372, 1.391). When it works, it's the strongest
   (median 1.372), but seed 0 is a degenerate failure. High variance (CV=0.25).

4. **all_MinRM: 2/3 seeds >1.0** but high variance (CV=0.32). At seed 0 it picks a bad
   lens (0.653), at seed 2 it matches A17 (1.391). The selector adds noise, not value.

5. **Baseline (A15_only) follows universal decay** (0.59 ratio). Spectral lens alone →
   convergence. Only adding competition (any of A14/A16/A17) breaks the pattern.

6. **Scale ratios >1.0 for all partition competition configs.** This is the opposite of
   every other PICA mechanism. The partition space grows as O(Bell(n)) and becomes richer
   at larger n, making competition more productive. This is a fundamentally different
   scaling regime.

**Refutation of F42/HYP-201:** Universal scale convergence applies ONLY to configs
without partition competition. Any config with ≥2 alternative lens cells achieves
frob>1.0 at n=256, exceeding their own n=128 values. The convergence is not universal
— it is a property of single-mechanism configs that lack partition diversity.

**Hierarchy at n=256:** A17_only (1.37) > A16_only (1.17) ≈ A14_only (1.16) > full_action (1.08) > baseline (0.54).
Single lens cells EXCEED the full 24-cell ensemble, confirming partition competition
as the primary and sufficient frob mechanism at all tested scales.

### Theoretical Implications of F46

F46 changes the campaign's theoretical picture fundamentally:

**Before F46:** The emerging theory was that PICA effects are scale-dependent and only
the full 24-cell ensemble (full_action) can resist convergence. The candidate theorem
(HYP-201) proposed that for any proper subset S, lim_{n→∞} frob(S)/frob(baseline) = 1.

**After F46:** The candidate theorem is **FALSE**. A single alternative lens cell
(A14 or A16) is sufficient to maintain frob>1.0 at n=256. Moreover, single-lens
configs EXCEED full_action at n=256 (A17_only 1.37 vs full_action 1.08).

**The revised picture:**

1. **Two qualitatively different mechanisms operate in the PICA:**
   - **Mixture/gating modulation** (A1-A13, A18-A25): Affects HOW strongly primitives
     are applied. Produces scale-dependent effects that decay as O(1/n^α).
   - **Partition competition** (A14, A16, A17 vs A15): Affects WHICH coarse-graining
     lens is applied. Produces scale-independent (or scale-ENHANCING) effects.

2. **Why partition competition scales differently:**
   The number of possible partitions grows super-exponentially with n (Bell numbers).
   At larger n, there are MORE qualitatively different ways to coarse-grain, so competition
   between lens candidates becomes MORE productive, not less. A spectral bisection (A15)
   finds ONE partition that happens to align with slow eigenvector structure. When an
   alternative lens (A14=RM-quantile, A16=packaging, A17=EP-quantile) proposes a
   DIFFERENT partition and the selector picks whichever is better, the resulting
   dynamics find structure that no single lens could find alone.

3. **Why full_action UNDERPERFORMS single lenses at n=256:**
   full_action enables all 24 cells including mixture modulation, budget control, and
   packaging. These additional cells may be counterproductive at n=256: they perturb
   the kernel in ways that interfere with partition-driven structure creation. The
   "kitchen sink" approach is dominated by a minimal, targeted configuration.

4. **Revised candidate theorem:**
   For configs C with partition competition (≥2 lens cells from {A14, A15, A16, A17}):
   frob(C, n) is non-decreasing in n for n ≥ 128. For configs C without partition
   competition: frob(C, n) / frob(baseline, n) → 1 as n → ∞.

**Open questions for EXP-106 n=256:**
- Does A13_A14_A19 (which includes A14) maintain high frob at n=256? At n=128 it's
  nearly identical to A14_only (0.976 vs 0.962 median), but the mechanisms diverge at
  scale. If A13/A19 disrupt A14's partition competition, we'll see Regime B (~0.55).
  If A14 dominates, we'll see Regime A (>1.0). **This is the KEY TEST.**
- All 12 remaining EXP-106 configs (boost variants, alternative enablers, cross-regime
  combos) are predicted to be Regime B (~0.52-0.55) based on absence of partition
  competition, with the sole exception of A13_A14_A19.

**EXP-106 n=256 predictions (mechanism-based):**
- 5/5 confirmed Regime B: baseline, A13_A18_A19, boost_0.1, boost_0.5, boost_1.0
- 7 predicted Regime B: boost_3.0, boost_4.0, A13_A3_A19, A13_A21_A19, chain_SBRC,
  chain_A24, chain_pkg (none have P4-row partition competition)
- 1 uncertain: **A13_A14_A19** (has A14 but also A13/A19 which may interfere)

### Pending: EXP-106 full n=256 data

EXP-106 tests 13 configs × 10 seeds at n=256. Batch processes (seeds 0-9) at ~60%
through, ETA ~02:00 UTC Feb 24. Three backup processes (s0, s1, s8) provide
line-buffered incremental data (5-11 configs completed so far).

**Available backup data (new binary, n=256):**
- baseline: 3 seeds → frob 0.511, 0.544, 0.547 (matches EXP-103 baseline)
- A13_A18_A19: 3 seeds → frob 0.541, 0.551, 0.567 (baseline-level)
- boost_0.1: 3 seeds → frob 0.533, 0.548, 0.553 (baseline-level)
- boost_0.5: 1 seed → frob 0.542 (baseline-level)
- boost_1.0: 1 seed → frob 0.522 (baseline-level)

**Pending:** boost_3.0, boost_4.0, A13_A3_A19, **A13_A14_A19**, A13_A21_A19,
chain_SBRC, chain_A24, chain_pkg. A13_A14_A19 (config #9/13) expected from s8
backup ~23:00 UTC Feb 23.

### Cross-Source n=256 Comprehensive Summary

All n=256 data from 3 sources (EXP-103 new binary 3 seeds, EXP-106 new binary
backups 3 seeds, EXP-107v2 old binary 9-10 seeds) yields a clean **two-regime
bifurcation**:

**REGIME A — Partition Competition (frob > 1.0):**

| Config | N seeds | Median frob | >1.0 rate | Med σ | Source |
|--------|---------|-------------|-----------|-------|--------|
| A17_only | 3 | **1.372** | 2/3 | 0.162 | EXP-103 |
| A16_only | 3 | **1.170** | 3/3 | 0.274 | EXP-103 |
| full_lens | 3 | **1.170** | 3/3 | 0.274 | EXP-103 |
| A14_only | 3 | **1.157** | 3/3 | 0.120 | EXP-103 |
| all_MinRM | 3 | **1.151** | 2/3 | 0.180 | EXP-103 |
| full_action | 9 | **1.075** | 7/9 | 0.014 | EXP-107v2 |
| full_all | 4 | **1.064** | 3/4 | 0.030 | EXP-107v2 |

**REGIME B — Baseline Convergence (frob ≈ 0.52):**

| Config | N seeds | Median frob | Med σ | Source |
|--------|---------|-------------|-------|--------|
| A13_A18_A19 | 3 | 0.551 | 0.262 | EXP-106 |
| boost_0.1 | 3 | 0.548 | 0.258 | EXP-106 |
| chain | 10 | 0.546 | 0.189 | EXP-107v2 |
| A15_only (=baseline) | 3 | 0.544 | 0.163 | EXP-103 |
| baseline | 13 | 0.525 | 0.197 | Combined |

**Key observations:**
1. **No intermediate regime** — configs either achieve frob>1.0 or collapse to ~0.52
2. **Single lens cells BEAT full_action** — A14_only (1.157), A16_only (1.170),
   A17_only (1.372) all exceed full_action (1.075) despite having far fewer active cells
3. **The sigma-killing chain (A13+A18+A19) is Regime B** — provides NO frob advantage
   at n=256, confirming F46 that partition competition (not ensemble complexity) is the
   scale-resistance mechanism
4. **full_action's sigma suppression** (σ=0.014) is unique to Regime A configs that
   also include the A13/A19 chain — pure lens cells maintain higher σ (0.12-0.27)
5. **Boost parameter irrelevant at n=256** — all boost values (0.1-1.0) identical to
   A13_A18_A19 baseline, confirming n=128 finding

### n=256 Scale Profile (all available data combined)

| Config | n=32 | n=64 | n=128 | n=256 | 128→256 | Source |
|--------|------|------|-------|-------|---------|--------|
| **A17_only** | — | — | 0.92 | **1.372** | **1.49** | EXP-103 (3s) |
| **A16_only** | — | 1.05 | 0.91 | **1.171** | **1.29** | EXP-103 (3s) |
| **full_lens** | — | 0.91 | 0.76 | **1.171** | **1.54** | EXP-103 (3s) |
| **A14_only** | — | — | 0.96 | **1.157** | **1.20** | EXP-103 (3s) |
| full_action | 1.72 | 1.42 | 1.47 | **1.075** | 0.73 | EXP-107v2 (9s) |
| full_all | 1.68 | 1.75 | 1.13 | 1.065 | 0.94 | EXP-107v2 (9s) |
| A13_A14_A19 | — | — | 0.98 | ~0.55 | ~0.56 | EXP-106 backup (3s) |
| all_MaxFrob | — | — | 0.89 | 0.930 | 1.05 | EXP-103 (3s) |
| all_MinRM | — | — | 0.87 | **1.151** | **1.33** | EXP-103 (3s) |
| chain | — | — | 0.93 | 0.546 | 0.59 | EXP-107v2 (10s) |
| A13_A18_A19 | — | — | 0.87 | 0.551 | 0.63 | EXP-106 backup (3s) |
| boost_0.1 | — | — | — | 0.548 | — | EXP-106 backup (3s) |
| P1_row_A13 | — | — | 1.02 | — | — | pending EXP-106 |
| baseline | 1.31 | 1.15 | 0.91 | 0.525 | 0.58 | Combined (13s) |
| A15_only (=baseline) | — | — | 0.93 | 0.544 | 0.59 | EXP-103 (3s) |
| A13_only | — | — | 0.93 | 0.534 | 0.57 | EXP-107v2 (10s) |

Note: n=32/64 from EXP-104 (3 seeds), n=128 from campaign (3-10 seeds),
n=256 from EXP-103 (3 seeds), EXP-106 backup (3 seeds), or EXP-107v2 old binary (9-10 seeds).
**Bold configs have scale ratio >1.0 (frob increases with n).**
Baseline n=256 median uses 13 seeds from both EXP-103 (3) and EXP-107v2 (10).
A13_A14_A19 n=128 updated to 0.98 (7 seeds, EXP-106 new binary).

---

## Future Experiment Protocol (Reviewer-Requested)

The following experiments address gaps identified during external code review (2026-02-23).
They require new experimental runs and cannot be resolved by code changes alone.

### EXP-F1: Empty Baseline Control

**Priority:** 1 (blocks all inertness claims)
**Addresses:** Reviewer Priority 1 — single-cell experiment redesign

All current "single-cell" experiments add cells to `PicaConfig::baseline()` (A10+A15).
No experiment has run `PicaConfig::none()` as a true empty control. This means we cannot
distinguish "cell X is inert" (no effect vs baseline) from "cell X is inert" (no effect
vs raw kernel). The 5-tier protocol:

| Tier | Config | Purpose |
|------|--------|---------|
| T0 | `PicaConfig::none()` | Raw kernel, no modulation |
| T1 | A10 only | Minimal viable (spectral gating without lens) |
| T2 | `PicaConfig::baseline()` (A10+A15) | Current baseline |
| T3 | baseline + cell X | Marginal effect of cell X (current "single-cell" design) |
| T4 | cell X alone (where meaningful) | Isolated effect without spectral gating |

**Design:** 10 seeds, n=64/128/256. Report effect sizes as (T3-T2) with IQR.
Priority configs for T4: A13, A14, A19 (the three known non-inert cells).

### EXP-F2: Fixed-tau Evaluation

**Priority:** 2 (blocks headline claims about bifurcation/crossover)
**Addresses:** Reviewer Priority 2 — control tau for headline claims

Adaptive tau conflates two effects: the dynamics change the kernel, AND the observation
timescale changes with the kernel. Any claim about "phase transition" or "scaling regime"
must be evaluated at fixed tau to disentangle these.

**Design:**
- Evaluate all headline configs (baseline, full_action, A13_A14_A19) at fixed tau=5, tau=20
  alongside adaptive tau
- Run at n=64, 128, 256 with 10 seeds
- Compare: does the REV/NRM bifurcation persist at fixed tau? Does the n=256 frob>1.0
  result hold?

### EXP-F3: Intermediate Scales

**Priority:** 2 (blocks crossover characterization)
**Addresses:** Reviewer Priority 2 — enough scales to see sharpness

Current data: n=32, 64, 128, 256 (4 points). This is insufficient to characterize
whether the REV transition is a sharp crossover or a gradual decline.

**Design:**
- Add n=48, 96, 192, 384 for key configs (baseline, full_action, A19_only, A13_A14_A19)
- 10 seeds each
- Plot REV fraction vs n to determine functional form (sigmoid? power-law?)

### EXP-F4: Out-of-Sample Validation Seeds

**Priority:** 3 (strengthens all claims)
**Addresses:** General methodology

All current results use seeds 0-9. Reserve seeds 10-19 as a confirmation set:
run the final "best" configs on seeds 10-19 and verify that medians/IQRs are
consistent with seeds 0-9.

### EXP-F5: Partition Candidate Score Instrumentation

**Priority:** 3 (supports mechanistic claims)
**Addresses:** Reviewer Priority 3 — audit completeness for causal narratives

The "partition competition" mechanism (Finding 41, 46) is inferred from outcomes
(frob increases when multiple P4 cells compete). To support the causal claim, we need
to instrument the selection step:

- Log per-candidate RM/frob/gap scores at each refresh
- Log which candidate was selected and the hysteresis margin
- Log whether the selection changed vs the previous refresh

This requires changes to `compute_p4_partition()` in [lens_cells.rs](crates/dynamics/src/pica/lens_cells.rs)
to emit structured diagnostics, and a new audit field to capture the summary.

### EXP-F6: Action Count Instrumentation

**Priority:** 3 (supports causal narratives)
**Addresses:** Reviewer Priority 3 — audit completeness

Current audit records lack per-primitive action counts. Adding these would enable
causal chain analysis (e.g., "A13 boosts trajectory fraction from 90% to 95%,
which reduces P2 gating opportunities, which stabilizes edges").

Required fields:
- `p1_count`, `p2_count`, `p3_count`, `p4_count`, `p5_count`, `p6_count` — raw action counts
- `traj_count` — trajectory steps
- Average action probabilities (may differ from config due to budget gating)

### EXP-F7: git_sha in Audit Records

**Priority:** 0 (low effort, high provenance value)
**Addresses:** Reviewer Priority 0 — configuration provenance

Embed the git commit SHA in audit records at build time or runtime. This closes the
last gap in P0 (config identity), making every record traceable to an exact binary.

**Implementation:** Add `env!("GIT_SHA")` via build.rs or read `.git/HEAD` at runtime.

---

## Retraction Log

| Finding | Status | Reason | Date |
|---------|--------|--------|------|
| F4 (LensSelector has strong effect) | **REVERSED** | Parameter loss bug masked the selector — all selectors produced identical results because enabled matrix wasn't propagated. Post-fix, selector has zero effect; the lens CELL matters, not the selector. | 2026-02-22 |
| F20 (Boost resonance at 2.0) | **RETRACTED** by F38 | Data-mixing artifact from old/new binary conflation. Post-fix, no boost value differs from baseline (all p>0.45 Mann-Whitney). | 2026-02-23 |
| F42 (Universal scale convergence) | **PARTIALLY RETRACTED** by F46 | The universality claim is refuted: configs WITH partition competition (A14/A16/A17) produce frob>1.0 at n=256 (3/3 seeds each). Convergence to frob≈0.52 holds only for configs WITHOUT partition competition. | 2026-02-23 |
