# RSI contribution: fixed skills vs recursive updates

## Setup

Observational comparison of existing audit cycles. Cycles with no applied skill update form the fixed-skill group; cycles with at least one applied update form the recursive-update group. Metrics are normalized per round to reduce the effect of different cycle lengths.

Source snapshot: `rsi-contribution.csv`.

## Results

| Group | Cycles | Rounds/cycle | New unique lines/round | Risk-weighted coverage/round | Verified reports/cycle |
|---|---:|---:|---:|---:|---:|
| Fixed skills | 7 | 3.4 | 5.0k | 6.1k | 1.0 |
| Recursive updates | 30 | 7.0 | 5.8k | 7.2k | 1.8 |

The recursive-update group shows higher per-round new-line coverage, higher risk-weighted coverage, and more verified reports per cycle. The direction is consistent across the three reported measures.

## Boundaries

This is an observational association, not a controlled experiment. Update timing is endogenous, project sizes are not paired, and verified reports are sparse. Repeat-read ratio is not used because it is sensitive to cycle length.
