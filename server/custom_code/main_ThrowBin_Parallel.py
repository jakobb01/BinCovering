"""
Parallel Driver for ThrowBin Strategy with Variable Bin Ratios.

This driver runs ThrowBin experiments across:
- Bin ratios from 30% to 50% (in 5% steps: 0.30, 0.35, 0.40, 0.45, 0.50)
- N from 10,000 to 100,000 (in 10,000 steps)
- Each experiment runs N times

Uses multiprocessing to parallelize across different (N, ratio) combinations.

Usage:
    python3 custom_code/main_ThrowBin_Parallel.py
    python3 custom_code/main_ThrowBin_Parallel.py --workers 4
    python3 custom_code/main_ThrowBin_Parallel.py --ratios 0.30,0.35,0.40,0.45,0.50 --n-values 10000,20000,30000
"""
import sys
import datetime
import os
import csv
import random
from multiprocessing import Pool, cpu_count
from functools import partial

from bincovering.generators.UniformGenerator import UniformGenerator

from bincovering.algorithms.ThrowBin import ThrowBinStrategy

# Try to import matplotlib
try:
    import matplotlib.pyplot as plt
    import numpy as np
    PLOTTING_AVAILABLE = True
except ImportError:
    PLOTTING_AVAILABLE = False
    print("Warning: matplotlib not available. Plotting will be skipped.")


class InMemoryGenerator:
    """
    A simple generator that serves items from an in-memory list.
    """
    def __init__(self, items):
        self._items = items.copy()
        self._index = 0
    
    def start(self):
        self._index = 0
        return f"InMemoryGenerator ready with {len(self._items)} items"
    
    def next(self):
        if self._index < len(self._items):
            item = self._items[self._index]
            self._index += 1
            return item
        else:
            raise StopIteration("No more items")
    
    def stop(self):
        return f"InMemoryGenerator stopped."


def run_single_experiment(items, num_items, bin_ratio):
    """Run a single ThrowBin experiment."""
    gen = InMemoryGenerator(items)
    gen.start()
    
    strat = ThrowBinStrategy(bin_ratio=bin_ratio)
    strat.start(generator=gen, num_items=num_items)
    
    while True:
        result = strat.next()
        if result is None:
            break
    
    strat.stop()
    return strat.get_covered_bins(), strat.get_total_bins()


def run_experiment_batch(params, data_path="./data/"):
    """
    Run a complete experiment for a given (num_items, bin_ratio) pair.
    
    Args:
        params: tuple of (num_items, bin_ratio)
        data_path: path to store data files
        
    Returns:
        dict with experiment results summary
    """
    num_items, bin_ratio = params
    num_runs = num_items  # Equal to N
    
    print(f"[START] N={num_items}, Ratio={bin_ratio*100:.0f}%, Runs={num_runs}")
    
    # Generate items with uniform distribution
    base_gen = UniformGenerator(path=data_path)
    base_gen.start(num_items)
    items_list = base_gen.get_items()
    base_gen.stop()
    
    # Create CSV filename
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    ratio_str = f"{int(bin_ratio*100)}pct"
    csv_filename = f"throwbin_parallel_{num_items}items_{ratio_str}_{timestamp}.csv"
    csv_path = os.path.join(data_path, csv_filename)
    
    num_bins = int(num_items * bin_ratio)
    
    # Run experiments and collect results
    all_bins_covered = []
    
    with open(csv_path, 'w', newline='') as csvfile:
        fieldnames = ['run_id', 'num_items', 'bin_ratio', 'num_bins', 'bins_covered', 'coverage_pct', 'timestamp']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for run_id in range(num_runs):
            bins_covered, _ = run_single_experiment(items_list, num_items, bin_ratio)
            all_bins_covered.append(bins_covered)
            coverage_pct = (bins_covered / num_bins) * 100 if num_bins > 0 else 0
            
            writer.writerow({
                'run_id': run_id,
                'num_items': num_items,
                'bin_ratio': bin_ratio,
                'num_bins': num_bins,
                'bins_covered': bins_covered,
                'coverage_pct': f'{coverage_pct:.2f}',
                'timestamp': datetime.datetime.now().isoformat()
            })
            
            # Progress update every 25%
            if run_id % max(1, num_runs // 4) == 0:
                progress = (run_id / num_runs) * 100
                print(f"  [N={num_items}, {ratio_str}] Progress: {progress:.0f}%")
    
    # Calculate summary statistics
    avg_covered = sum(all_bins_covered) / len(all_bins_covered)
    min_covered = min(all_bins_covered)
    max_covered = max(all_bins_covered)
    avg_coverage_pct = (avg_covered / num_bins) * 100 if num_bins > 0 else 0
    
    print(f"[DONE] N={num_items}, Ratio={bin_ratio*100:.0f}% -> Avg: {avg_covered:.1f}/{num_bins} ({avg_coverage_pct:.2f}%)")
    
    return {
        'num_items': num_items,
        'bin_ratio': bin_ratio,
        'num_bins': num_bins,
        'num_runs': num_runs,
        'avg_covered': avg_covered,
        'min_covered': min_covered,
        'max_covered': max_covered,
        'avg_coverage_pct': avg_coverage_pct,
        'csv_path': csv_path
    }


def create_summary_plots(results, output_path):
    """Create comprehensive summary plots from all experiments."""
    if not PLOTTING_AVAILABLE:
        return
    
    # Organize data by N and ratio
    n_values = sorted(set(r['num_items'] for r in results))
    ratios = sorted(set(r['bin_ratio'] for r in results))
    
    # Create figure with 2x2 subplots
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
    
    # Plot 1: Coverage Percentage vs N for different bin ratios
    for ratio in ratios:
        ratio_results = [r for r in results if r['bin_ratio'] == ratio]
        ratio_results.sort(key=lambda x: x['num_items'])
        
        n_vals = [r['num_items'] for r in ratio_results]
        avg_pcts = [r['avg_coverage_pct'] for r in ratio_results]
        
        ax1.plot(n_vals, avg_pcts, marker='o', label=f'{ratio*100:.0f}% bins', linewidth=2)
    
    ax1.set_xlabel('Number of Items (N)', fontsize=12)
    ax1.set_ylabel('Avg Coverage %', fontsize=12)
    ax1.set_title('ThrowBin: Coverage % vs N', fontsize=14, fontweight='bold')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    ax1.axhline(y=100, color='red', linestyle='--', alpha=0.5, label='100%')
    
    # Plot 2: Average Bins Covered vs N for different ratios
    for ratio in ratios:
        ratio_results = [r for r in results if r['bin_ratio'] == ratio]
        ratio_results.sort(key=lambda x: x['num_items'])
        
        n_vals = [r['num_items'] for r in ratio_results]
        avg_covered = [r['avg_covered'] for r in ratio_results]
        
        ax2.plot(n_vals, avg_covered, marker='s', label=f'{ratio*100:.0f}% bins', linewidth=2)
    
    ax2.set_xlabel('Number of Items (N)', fontsize=12)
    ax2.set_ylabel('Avg Bins Covered', fontsize=12)
    ax2.set_title('ThrowBin: Bins Covered vs N', fontsize=14, fontweight='bold')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    # Plot 3: Coverage % vs Bin Ratio for different N
    for n in n_values:
        n_results = [r for r in results if r['num_items'] == n]
        n_results.sort(key=lambda x: x['bin_ratio'])
        
        ratio_vals = [r['bin_ratio']*100 for r in n_results]
        avg_pcts = [r['avg_coverage_pct'] for r in n_results]
        
        ax3.plot(ratio_vals, avg_pcts, marker='^', label=f'N={n}', linewidth=2)
    
    ax3.set_xlabel('Bin Ratio (%)', fontsize=12)
    ax3.set_ylabel('Avg Coverage %', fontsize=12)
    ax3.set_title('ThrowBin: Coverage % vs Bin Ratio', fontsize=14, fontweight='bold')
    ax3.legend()
    ax3.grid(True, alpha=0.3)
    ax3.axhline(y=100, color='red', linestyle='--', alpha=0.5)
    
    # Plot 4: Heatmap of Coverage %
    matrix = np.zeros((len(n_values), len(ratios)))
    for i, n in enumerate(n_values):
        for j, ratio in enumerate(ratios):
            result = next((r for r in results if r['num_items'] == n and r['bin_ratio'] == ratio), None)
            if result:
                matrix[i, j] = result['avg_coverage_pct']
    
    im = ax4.imshow(matrix, cmap='RdYlGn', aspect='auto', vmin=0, vmax=100)
    ax4.set_xticks(range(len(ratios)))
    ax4.set_yticks(range(len(n_values)))
    ax4.set_xticklabels([f'{r*100:.0f}%' for r in ratios])
    ax4.set_yticklabels([f'{n}' for n in n_values])
    ax4.set_xlabel('Bin Ratio', fontsize=12)
    ax4.set_ylabel('Number of Items (N)', fontsize=12)
    ax4.set_title('ThrowBin: Coverage % Heatmap', fontsize=14, fontweight='bold')
    
    cbar = plt.colorbar(im, ax=ax4)
    cbar.set_label('Avg Coverage %', rotation=270, labelpad=20)
    
    # Add text annotations to heatmap
    for i in range(len(n_values)):
        for j in range(len(ratios)):
            text = ax4.text(j, i, f'{matrix[i, j]:.1f}%',
                           ha="center", va="center", color="black", fontsize=8)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"\nSummary plots saved to: {output_path}")
    plt.close()


def run_parallel_experiments(n_values, bin_ratios, num_workers=None, data_path="./data/"):
    """
    Run all experiments in parallel.
    
    Args:
        n_values: list of N values (number of items)
        bin_ratios: list of bin ratios (e.g., [0.30, 0.35, 0.40, 0.45, 0.50])
        num_workers: number of parallel workers (default: CPU count - 1)
        data_path: path to store data files
        
    Returns:
        list of result dictionaries
    """
    if num_workers is None:
        num_workers = max(1, cpu_count() - 1)
    
    # Generate all parameter combinations
    param_combinations = []
    for n in n_values:
        for ratio in bin_ratios:
            param_combinations.append((n, ratio))
    
    total_experiments = len(param_combinations)
    
    print(f"\n{'='*70}")
    print(f"ThrowBin Parallel Experiment Runner")
    print(f"{'='*70}")
    print(f"N values: {n_values}")
    print(f"Bin ratios: {[f'{r*100:.0f}%' for r in bin_ratios]}")
    print(f"Total experiment combinations: {total_experiments}")
    print(f"Workers: {num_workers}")
    print(f"Data path: {data_path}")
    print(f"{'='*70}\n")
    
    # Create partial function with fixed data_path
    run_func = partial(run_experiment_batch, data_path=data_path)
    
    # Run experiments in parallel
    start_time = datetime.datetime.now()
    
    with Pool(processes=num_workers) as pool:
        results = pool.map(run_func, param_combinations)
    
    end_time = datetime.datetime.now()
    duration = end_time - start_time
    
    # Create summary file
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    summary_filename = f"throwbin_parallel_summary_{timestamp}.csv"
    summary_path = os.path.join(data_path, summary_filename)
    
    with open(summary_path, 'w', newline='') as csvfile:
        fieldnames = ['num_items', 'bin_ratio', 'bin_ratio_pct', 'num_bins', 'num_runs', 
                      'avg_covered', 'min_covered', 'max_covered', 'avg_coverage_pct', 'csv_path']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for result in results:
            writer.writerow({
                'num_items': result['num_items'],
                'bin_ratio': result['bin_ratio'],
                'bin_ratio_pct': f"{result['bin_ratio']*100:.0f}%",
                'num_bins': result['num_bins'],
                'num_runs': result['num_runs'],
                'avg_covered': f"{result['avg_covered']:.2f}",
                'min_covered': result['min_covered'],
                'max_covered': result['max_covered'],
                'avg_coverage_pct': f"{result['avg_coverage_pct']:.2f}",
                'csv_path': result['csv_path']
            })
    
    # Create summary plots
    if PLOTTING_AVAILABLE:
        plot_filename = f"throwbin_parallel_summary_{timestamp}.png"
        plot_path = os.path.join(data_path, plot_filename)
        create_summary_plots(results, plot_path)
    
    # Print summary
    print(f"\n{'='*70}")
    print(f"EXPERIMENT COMPLETE")
    print(f"{'='*70}")
    print(f"Duration: {duration}")
    print(f"Summary saved to: {summary_path}")
    print(f"\nResults by (N, Ratio):")
    print(f"{'-'*70}")
    print(f"{'N':>10} | {'Ratio':>6} | {'Bins':>8} | {'Avg Covered':>12} | {'Avg %':>8}")
    print(f"{'-'*70}")
    
    for result in sorted(results, key=lambda x: (x['num_items'], x['bin_ratio'])):
        print(f"{result['num_items']:>10} | {result['bin_ratio']*100:>5.0f}% | {result['num_bins']:>8} | "
              f"{result['avg_covered']:>12.2f} | {result['avg_coverage_pct']:>7.2f}%")
    
    print(f"{'-'*70}")
    print(f"\nGenerated CSV files:")
    for result in results:
        print(f"  - {result['csv_path']}")
    
    return results


def main():
    """Main entry point for the parallel ThrowBin driver."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Run ThrowBin experiments in parallel across multiple N and bin ratio values'
    )
    parser.add_argument(
        '--n-values',
        type=str,
        default='10000,20000,30000,40000,50000,60000,70000,80000,90000,100000',
        help='Comma-separated list of N values (default: 10k to 100k in 10k steps)'
    )
    parser.add_argument(
        '--ratios',
        type=str,
        default='0.30,0.35,0.40,0.45,0.50',
        help='Comma-separated list of bin ratios (default: 0.30,0.35,0.40,0.45,0.50)'
    )
    parser.add_argument(
        '-w', '--workers',
        type=int,
        default=None,
        help='Number of parallel workers (default: CPU count - 1)'
    )
    parser.add_argument(
        '-p', '--path',
        type=str,
        default='./data/',
        help='Path to store data files (default: ./data/)'
    )
    
    args = parser.parse_args()
    
    # Parse N values
    n_values = [int(n.strip()) for n in args.n_values.split(',')]
    
    # Parse bin ratios
    bin_ratios = [float(r.strip()) for r in args.ratios.split(',')]
    
    # Run experiments
    results = run_parallel_experiments(
        n_values=n_values,
        bin_ratios=bin_ratios,
        num_workers=args.workers,
        data_path=args.path
    )
    
    print(f"\nAll experiments complete!")
    print(f"To analyze individual results:")
    print(f"  python3 custom_code/analyze_csv_results.py data/throwbin_parallel_*.csv")


if __name__ == "__main__":
    main()
