# Temporal Experiment Artifact - audited final package

This directory contains the exact TFF0 theories used in the reported runs, the corrected 200-conjecture benchmark, validation scripts, prover runners, and the retained raw result archives for the paper **Stratified First-Order Reasoning for Gregorian Calendar Arithmetic: Axiomatization, Quantified Queries, and Proof-Search Evaluation**.

## What is validated

Run:

```bash
python3 scripts/validate_suite.py
```

The validator checks all of the following without modifying the distributed theory files:

1. theory/conjecture syntax at the formula-block level and expected suite sizes;
2. all 200 main benchmark conjectures against an independent Python implementation of proleptic Gregorian arithmetic;
3. every closed Tier-3 weekday, February-length, and exact year-span anchor;
4. direct Tier-3 anchor overlap with benchmark targets (12 disclosed structural coincidences; 0 direct coincidences in the 159-query extended subset);
5. the theorem counts reported in the manuscript by recomputing them from the retained `results.csv` files;
6. every `theory_sha256` stored in those CSV files against the exact theory file distributed here.

A successful run ends with `[OK] suite validation passed`.  The output from the packaged audit is stored in `VALIDATION_REPORT.txt`.

## Directory layout

- `theories/sound_tiers/`
  - `T1_structural.tff` - 54 formulas.
  - `T2_core_no_accel.tff` - 84 formulas.
  - `T2_full_sound.tff` - 97 formulas; Tier-2 core plus seven general accelerator components.
  - `T3_validated_anchors.tff` - 163 formulas; Tier-2 full plus 66 validated closed anchors.
- `theories/ablation_variants/` - seven add-one and seven leave-one-out Tier-2 variants.
- `conjectures/ground_200_corrected.tff` - corrected 200-conjecture main benchmark.
- `conjectures/structural_subset.tff` - 41 structural-vocabulary conjectures.
- `conjectures/extended_subset.tff` - 159 Tier-2/extended-vocabulary conjectures.
- `conjectures/quantified_T1.tff` - six quantified queries reported in the paper.
- `conjectures/source_benchmark_raw.tff` - source benchmark from which the corrected benchmark is regenerated.
- `conjectures/correction_manifest.json` - 25 recorded benchmark/identifier corrections.
- `scripts/` - builders, validators, Vampire/Z3 runners, and result analysis.
- `raw_results/` - the retained raw experiment archives used in the manuscript tables.

## Rebuilding generated TFF0 files

The supplied generated files are already the files used in the experiments.  To regenerate them deterministically:

```bash
python3 scripts/build_conjectures.py
python3 scripts/build_sound_tiers.py
python3 scripts/validate_suite.py
```

The current builders reproduce the distributed conjecture and theory files byte-for-byte.

## Vampire

Set either `--exe` or the environment variable `VAMPIRE_EXE`.  For example:

```bash
export VAMPIRE_EXE=/full/path/to/vampire-main
python3 scripts/run_vampire.py \
  --exe "$VAMPIRE_EXE" \
  --theories theories/sound_tiers/T2_core_no_accel.tff \
             theories/sound_tiers/T2_full_sound.tff \
             theories/sound_tiers/T3_validated_anchors.tff \
  --conjectures conjectures/ground_200_corrected.tff \
  --timeout 60 --seed-mode none --outdir results/example_vampire
```

The runner contains no machine-specific executable path.

## Z3 TPTP frontend

The experiments used the Z3 TPTP frontend (`z3_tptp5`), not the ordinary `z3` command.  See `Z3_TPTP_SETUP_MACOS.txt`.  Then set:

```bash
export Z3_TPTP_EXE=/full/path/to/z3_tptp5
```

and run, for example:

```bash
python3 scripts/run_z3.py \
  --exe "$Z3_TPTP_EXE" \
  --theories theories/sound_tiers/T2_core_no_accel.tff \
             theories/sound_tiers/T2_full_sound.tff \
             theories/sound_tiers/T3_validated_anchors.tff \
  --conjectures conjectures/ground_200_corrected.tff \
  --timeout 60 --seed-mode none --outdir results/example_z3
```

The TPTP frontend requires the `-file:<problem>` argument internally; the packaged runner uses that syntax.

## Timing protocol

Each timed call used a fresh prover process and a 60-second limit per theory-conjecture pair.  Paper runs used `--seed-mode none`: no Python-computed weekday or endpoint facts were injected into the prover input.  Each CSV row records the theory filename, SHA-256, conjecture name, status, elapsed time, timeout, and seed mode.

`UNKNOWN` on a deliberately false consistency probe is not a proof of consistency.  The preflight probes are contradiction detectors only.
