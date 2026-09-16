# ThrowBin Strategies Documentation

## Overview

Two variants of the ThrowBin strategy for the Bin Covering Problem have been implemented:

### ThrowBin (Original)
- Opens a configurable ratio of N bins at the start (default 50%)
- Randomly places each item into one of the **active (non-covered)** bins
- When a bin reaches the threshold (1.0), it's marked as **covered and removed** from active bins
- Number of active bins **decreases** as bins are covered
- Eventually runs out of bins to place items

### ThrowBin_1 (Constant Active Bins)
- Opens a configurable ratio of N bins at the start (default 50%)
- Randomly places each item into one of the active bins
- When a bin reaches the threshold (1.0), it's **replaced with a new empty bin**
- Number of active bins **remains constant** throughout the process
- Can cover many more bins than initially opened (total covered can exceed active bins)

## Files Structure

```
strategies/
├── ThrowBin.py          # Original strategy (bins removed when covered)
└── ThrowBin_1.py        # Constant bins strategy (bins replaced when covered)

custom_code/
├── main_ThrowBin.py                # Single-run driver for ThrowBin
├── main_ThrowBin_Parallel.py       # Parallel driver for ThrowBin
├── main_ThrowBin_1.py              # Single-run driver for ThrowBin_1
└── main_ThrowBin_1_Parallel.py     # Parallel driver for ThrowBin_1
```

## Usage Examples

### Single Runs

```bash
# ThrowBin - 5000 items, 40% bin ratio, 5000 runs
python3 custom_code/main_ThrowBin.py -n 5000 -b 0.40 -r 5000

# ThrowBin_1 - 5000 items, 40% bin ratio, 5000 runs
python3 custom_code/main_ThrowBin_1.py -n 5000 -b 0.40 -r 5000
```

### Parallel Experiments

```bash
# ThrowBin - Full experiment (N: 10k-100k, ratios: 30%-50%)
python3 custom_code/main_ThrowBin_Parallel.py

# ThrowBin_1 - Full experiment
python3 custom_code/main_ThrowBin_1_Parallel.py

# Custom parameters
python3 custom_code/main_ThrowBin_Parallel.py --n-values 10000,50000,100000 --ratios 0.30,0.40,0.50 -w 4
```

## Output Files

### Individual Experiment CSVs
- `throwbin_results_<N>items_<ratio>_<timestamp>.csv`
- `throwbin1_results_<N>items_<ratio>_<timestamp>.csv`
- `throwbin_parallel_<N>items_<ratio>_<timestamp>.csv`
- `throwbin1_parallel_<N>items_<ratio>_<timestamp>.csv`

### Summary Files (Parallel Runs)
- `throwbin_parallel_summary_<timestamp>.csv` - Aggregated statistics
- `throwbin_parallel_summary_<timestamp>.png` - 4-panel visualization
- `throwbin1_parallel_summary_<timestamp>.csv` - Aggregated statistics
- `throwbin1_parallel_summary_<timestamp>.png` - 4-panel visualization

### Individual Plot Files
- `throwbin_plot_<N>items_<ratio>_<timestamp>.png`
- `throwbin1_plot_<N>items_<ratio>_<timestamp>.png`

## Summary Plots (Parallel Runs)

The parallel drivers generate comprehensive 4-panel visualizations:

1. **Coverage vs N** - Shows how coverage changes with number of items
2. **Bins Covered vs N** - Absolute number of bins covered
3. **Coverage vs Bin Ratio** - Performance across different bin ratios
4. **Heatmap** - Color-coded performance matrix (N × bin ratio)

## Key Differences in Results

**ThrowBin (Original):**
- With 50% bins (N/2): Covers ~55-60% of opened bins
- With 30% bins: Can achieve 100% coverage (all bins covered)
- Lower bin ratios → higher coverage percentage
- Total covered bins ≤ number of opened bins

**ThrowBin_1 (Replacement):**
- With 50% bins: Covers ~2-3× the number of active bins
- With 30% bins: Covers ~0.7-0.8× the number of active bins per run
- Total covered bins can greatly exceed number of active bins
- Coverage ratio = total_covered / active_bins

## Analyzing Results

Use the existing CSV analyzer:

```bash
# Analyze individual results
python3 custom_code/analyze_csv_results.py data/throwbin_results_*.csv

# Analyze all parallel results
python3 custom_code/analyze_csv_results.py data/throwbin_parallel_*.csv
python3 custom_code/analyze_csv_results.py data/throwbin1_parallel_*.csv
```

## Parameters

| Parameter | Flag | Default | Description |
|-----------|------|---------|-------------|
| Number of items | `-n, --num-items` | 1000 | Total items to generate (N) |
| Number of runs | `-r, --runs` | N | How many times to repeat the experiment |
| Bin ratio | `-b, --bin-ratio` | 0.5 | Ratio of N to use as bins (0.3 = 30%, 0.5 = 50%) |
| Data path | `-p, --path` | `./data/` | Where to save results |
| Workers | `-w, --workers` | CPU-1 | Parallel workers (parallel scripts only) |

## Recommended Experiments

For comprehensive analysis:

```bash
# Quick test (fast)
python3 custom_code/main_ThrowBin_Parallel.py --n-values 1000,5000 --ratios 0.30,0.50 -w 2
python3 custom_code/main_ThrowBin_1_Parallel.py --n-values 1000,5000 --ratios 0.30,0.50 -w 2

# Full experiment (slow, ~hours)
python3 custom_code/main_ThrowBin_Parallel.py -w 8
python3 custom_code/main_ThrowBin_1_Parallel.py -w 8
```
