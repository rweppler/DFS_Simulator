# DFS Simulator

Monte Carlo lineup simulator that mirrors the roster build flow of Stokastic's contest generator for main-slate NFL DFS GPP tournaments. The tool:

- Loads a custom player pool with projections, volatility, ownership, and leverage data.
- Builds DraftKings-style lineups (QB/RB/RB/WR/WR/WR/TE/FLEX/DST) under a $50,000 cap using leverage- and boom-adjusted selection weights.
- Simulates scores for each lineup and for a synthetic "field" using per-player projection/volatility to approximate slate scoring distributions.
- Estimates GPP-focused ROI using top-heavy payouts (top 1% finish and min-cash thresholds) to highlight contrarian builds that can capture first-place equity.

## Data

The default player pool lives in `data/players.csv` and includes main-slate options from the provided table along with ownership, optimal rate, and leverage. You can replace or extend this file as long as the column headers remain unchanged.

## Usage

```bash
python lineup_simulator.py --lineups 25 --seed 7
```

Key flags:

- `--players`: path to the player CSV (defaults to `data/players.csv`).
- `--lineups`: number of candidate lineups to generate and evaluate.
- `--seed`: RNG seed for reproducibility.

The script prints the top simulated lineups ranked by ROI (top-heavy GPP focus) and an exposure summary showing how often each player appeared across generated builds.

## Modeling Notes

- Player scores are drawn from truncated normal distributions centered on projections with their provided standard deviation and ceiling acting as a cap.
- Lineup selection weights reward ceiling, leverage, and boom probability while applying an ownership tax to push contrarian combinations.
- ROI is computed from the probability of beating cash and top-1% thresholds derived from the simulated field distribution, using a $20 entry, $200k first prize, and $40 min cash to reflect top-heavy GPP payouts.
