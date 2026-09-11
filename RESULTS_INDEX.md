# Raw result index

All counts below are recomputed by `scripts/verify_reported_results.py` from the CSV files inside `raw_results/*.zip`.

## Main 200-conjecture comparison

| Prover | T2 core | T2 full | T3 |
|---|---:|---:|---:|
| Vampire | 126 | 161 | 165 |
| Z3 | 138 | 73 | 77 |

Raw archives: `E2V_full.zip`, `E2Z_full.zip`.

### Structural / extended split

Entries are `structural / extended`; the subsets contain 41 and 159 conjectures respectively.

| Prover | T2 core | T2 full | T3 |
|---|---:|---:|---:|
| Vampire | 41 / 85 | 41 / 120 | 41 / 124 |
| Z3 | 41 / 97 | 41 / 32 | 36 / 41 |

The Tier-3 anchor audit finds 12 direct coincidences with structural targets and zero direct coincidences with extended targets.  Thus the Vampire change from 120 to 124 on the extended subset cannot be explained by direct target insertion.

## Vampire add-one accelerator run

Paired core baseline in `E4V_add1.zip`: 130/200.

| Variant | Theorems |
|---|---:|
| +1y | 161 |
| +4y | 150 |
| +10y | 147 |
| +100y | 140 |
| +400y | 140 |
| +month_hopper | 133 |
| +weekday400 | 124 |

## Z3 add-one year-span runs

Each archive reruns the same paired 138/200 core baseline.

| Variant | Theorems |
|---|---:|
| +1y | 111 |
| +4y | 90 |
| +10y | 86 |
| +100y | 91 |
| +400y | 79 |

Raw archives: `E4Z_add1_*.zip`.

## Vampire leave-one-out runs

Each row is paired within its own archive, so the full-theory baseline may vary slightly around the 60-second boundary.

| Removed component | Full | Without component |
|---|---:|---:|
| 1y | 165 | 159 |
| 4y | 160 | 156 |
| 10y | 158 | 160 |
| 100y | 157 | 156 |
| 400y | 160 | 159 |
| month_hopper | 160 | 158 |
| weekday400 | 161 | 159 |

Raw archives: `E5V_loo_*.zip`.

## Six quantified Tier-1 queries

| Prover | T1 | T2 core | T2 full | T3 |
|---|---:|---:|---:|---:|
| Vampire | 6/6 | 5/6 | 5/6 | 6/6 |
| Z3 | 6/6 | 5/6 | 4/6 | 4/6 |

Raw archives: `E6V_quantified_T1.zip`, `E6Z_quantified_T1.zip`.
