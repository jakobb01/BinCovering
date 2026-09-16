"""
Parallel Driver for ThrowBin_1 Strategy with Variable Bin Ratios.

ThrowBin_1 maintains constant active bins by replacing covered bins with new empty ones.

Runs experiments with configurable N values and bin ratios.
Defaults:
- Bin ratios: 0.60 to 1.00 (60% to 100%)
- N: 10,000 to 100,000 (steps of 10,000)
- Each experiment runs N times

Usage:
    # Run with defaults
    python3 custom_code/main_ThrowBin_1_Parallel.py

    # Run with custom N values and bin ratios
    python3 custom_code/main_ThrowBin_1_Parallel.py --n-values 1000,5000,10000 --ratios 0.3,0.5,0.7

    # Run with specific number of workers
    python3 custom_code/main_ThrowBin_1_Parallel.py --workers 4
"""
import sys
import datetime
import os
import csv
import random
from multiprocessing import Pool, cpu_count
from functools import partial

from bincovering.generators.UniformGenerator import UniformGenerator

from bincovering.algorithms.ThrowBin_1 import ThrowBin_1_Strategy

# Try to import matplotlib
try:
    import matplotlib.pyplot as plt
    import numpy as np
    PLOTTING_AVAILABLE = True
except ImportError:
    PLOTTING_AVAILABLE = False
    print("Warning: matplotlib not available. Plotting will be skipped.")


class InMemoryGenerator:
    """A simple generator that serves items from an in-memory list."""
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
    """Run a single ThrowBin_1 experiment."""
    gen = InMemoryGenerator(items)
    gen.start()
    
    strat = ThrowBin_1_Strategy(bin_ratio=bin_ratio)
    strat.start(generator=gen, num_items=num_items)
    
    while True:
        result = strat.next()
        if result is None:
            break
    
    strat.stop()
    return strat.get_covered_bins(), strat.get_total_bins()


def run_experiment_batch(params, data_path="./data/"):
    """Run a complete experiment for a given (num_items, bin_ratio) pair."""
    num_items, bin_ratio = params
    num_runs = num_items
    
    print(f"[START] N={num_items}, Ratio={bin_ratio*100:.0f}%, Runs={num_runs}")
    
    base_gen = UniformGenerator(path=data_path)
    base_gen.start(num_items)
    items_list = base_gen.get_items()
    base_gen.stop()
    
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    ratio_str = f"{int(bin_ratio*100)}pct"
    csv_filename = f"throwbin1_parallel_{num_items}items_{ratio_str}_{timestamp}.csv"
    csv_path = os.path.join(data_path, csv_filename)
    
    num_bins = int(num_items * bin_ratio)
    all_bins_covered = []
    
    with open(csv_path, 'w', newline='') as csvfile:
        fieldnames = ['run_id', 'num_items', 'bin_ratio', 'num_bins', 'bins_covered', 'coverage_ratio', 'timestamp']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for run_id in range(num_runs):
            bins_covered, _ = run_single_experiment(items_list, num_items, bin_ratio)
            all_bins_covered.append(bins_covered)
            coverage_ratio = bins_covered / num_bins if num_bins > 0 else 0
            
            writer.writerow({
                'run_id': run_id,
                'num_items': num_items,
                'bin_ratio': bin_ratio,
                'num_bins': num_bins,
                'bins_covered': bins_covered,
                'coverage_ratio': f'{coverage_ratio:.2f}',
                'timestamp': datetime.datetime.now().isoformat()
            })
            
            if run_id % max(1, num_runs // 4) == 0:
                progress = (run_id / num_runs) * 100
                print(f"  [N={num_items}, {ratio_str}] Progress: {progress:.0f}%")
    
    avg_covered = sum(all_bins_covered) / len(all_bins_covered)
    min_covered = min(all_bins_covered)
    max_covered = max(all_bins_covered)
    avg_ratio = avg_covered / num_bins if num_bins > 0 else 0
    avg_covered_over_half_n = avg_covered / (num_items / 2) if num_items > 0 else 0
    
    print(f"[DONE] N={num_items}, Ratio={bin_ratio*100:.0f}% -> Avg: {avg_covered:.1f} (ratio: {avg_ratio:.2f})")
    
    return {
        'num_items': num_items,
        'bin_ratio': bin_ratio,
        'num_bins': num_bins,
        'num_runs': num_runs,
        'avg_covered': avg_covered,
        'min_covered': min_covered,
        'max_covered': max_covered,
        'avg_ratio': avg_ratio,
        'avg_covered_over_half_n': avg_covered_over_half_n,
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
    
    # Plot 1: Coverage Metric vs N for different bin ratios
    for ratio in ratios:
        ratio_results = [r for r in results if r['bin_ratio'] == ratio]
        ratio_results.sort(key=lambda x: x['num_items'])
        
        n_vals = [r['num_items'] for r in ratio_results]
        # Changed from avg_ratio to avg_covered_over_half_n
        metric_vals = [r['avg_covered_over_half_n'] for r in ratio_results]
        
        ax1.plot(n_vals, metric_vals, marker='o', label=f'{ratio*100:.0f}% bins', linewidth=2)
    
    ax1.set_xlabel('Number of Items (N)', fontsize=12)
    ax1.set_ylabel('Avg Covered / (N/2)', fontsize=12)
    ax1.set_title('ThrowBin_1: Coverage Efficiency vs N', fontsize=14, fontweight='bold')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # Plot 2: Average Bins Covered vs N for different ratios
    for ratio in ratios:
        ratio_results = [r for r in results if r['bin_ratio'] == ratio]
        ratio_results.sort(key=lambda x: x['num_items'])
        
        n_vals = [r['num_items'] for r in ratio_results]
        avg_covered = [r['avg_covered'] for r in ratio_results]
        
        ax2.plot(n_vals, avg_covered, marker='s', label=f'{ratio*100:.0f}% bins', linewidth=2)
    
    ax2.set_xlabel('Number of Items (N)', fontsize=12)
    ax2.set_ylabel('Avg Bins Covered', fontsize=12)
    ax2.set_title('ThrowBin_1: Total Bins Covered vs N', fontsize=14, fontweight='bold')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    # Plot 3: Coverage Metric vs Bin Ratio for different N
    for n in n_values:
        n_results = [r for r in results if r['num_items'] == n]
        n_results.sort(key=lambda x: x['bin_ratio'])
        
        ratio_vals = [r['bin_ratio']*100 for r in n_results]
        # Changed from avg_ratio to avg_covered_over_half_n
        metric_vals = [r['avg_covered_over_half_n'] for r in n_results]
        
        ax3.plot(ratio_vals, metric_vals, marker='^', label=f'N={n}', linewidth=2)
    
    ax3.set_xlabel('Bin Ratio (%)', fontsize=12)
    ax3.set_ylabel('Avg Covered / (N/2)', fontsize=12)
    ax3.set_title('ThrowBin_1: Coverage Efficiency vs Bin Ratio', fontsize=14, fontweight='bold')
    ax3.legend()
    ax3.grid(True, alpha=0.3)
    
    # Plot 4: Heatmap of Coverage Metric
    # Create matrix for heatmap
    matrix = np.zeros((len(n_values), len(ratios)))
    for i, n in enumerate(n_values):
        for j, ratio in enumerate(ratios):
            result = next((r for r in results if r['num_items'] == n and r['bin_ratio'] == ratio), None)
            if result:
                # Changed from avg_ratio to avg_covered_over_half_n
                matrix[i, j] = result['avg_covered_over_half_n']
    
    im = ax4.imshow(matrix, cmap='YlOrRd', aspect='auto')
    ax4.set_xticks(range(len(ratios)))
    ax4.set_yticks(range(len(n_values)))
    ax4.set_xticklabels([f'{r*100:.0f}%' for r in ratios])
    ax4.set_yticklabels([f'{n}' for n in n_values])
    ax4.set_xlabel('Bin Ratio', fontsize=12)
    ax4.set_ylabel('Number of Items (N)', fontsize=12)
    ax4.set_title('ThrowBin_1: Coverage Efficiency Heatmap', fontsize=14, fontweight='bold')
    
    # Add colorbar
    cbar = plt.colorbar(im, ax=ax4)
    cbar.set_label('Avg Covered / (N/2)', rotation=270, labelpad=20)
    
    # Add text annotations to heatmap
    for i in range(len(n_values)):
        for j in range(len(ratios)):
            text = ax4.text(j, i, f'{matrix[i, j]:.2f}',
                           ha="center", va="center", color="black", fontsize=8)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"\nSummary plots saved to: {output_path}")
    plt.close()


def run_parallel_experiments(n_values, bin_ratios, num_workers=None, data_path="./data/"):
    """Run all experiments in parallel."""
    if num_workers is None:
        num_workers = max(1, cpu_count() - 1)
    
    param_combinations = []
    for n in n_values:
        for ratio in bin_ratios:
            param_combinations.append((n, ratio))
    
    total_experiments = len(param_combinations)
    
    print(f"\n{'='*70}")
    print(f"ThrowBin_1 Parallel Experiment Runner")
    print(f"{'='*70}")
    print(f"N values: {n_values}")
    print(f"Bin ratios: {[f'{r*100:.0f}%' for r in bin_ratios]}")
    print(f"Total experiment combinations: {total_experiments}")
    print(f"Workers: {num_workers}")
    print(f"Data path: {data_path}")
    print(f"{'='*70}\n")
    
    run_func = partial(run_experiment_batch, data_path=data_path)
    
    start_time = datetime.datetime.now()
    
    with Pool(processes=num_workers) as pool:
        results = pool.map(run_func, param_combinations)
    
    end_time = datetime.datetime.now()
    duration = end_time - start_time
    
    # Create summary CSV
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    summary_filename = f"throwbin1_parallel_summary_{timestamp}.csv"
    summary_path = os.path.join(data_path, summary_filename)
    
    with open(summary_path, 'w', newline='') as csvfile:
        fieldnames = ['num_items', 'bin_ratio', 'bin_ratio_pct', 'num_bins', 'num_runs', 
                      'avg_covered', 'min_covered', 'max_covered', 'avg_ratio', 'avg_covered_over_half_n', 'csv_path']
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
                'avg_ratio': f"{result['avg_ratio']:.2f}",
                'avg_covered_over_half_n': f"{result['avg_covered_over_half_n']:.2f}",
                'csv_path': result['csv_path']
            })
    
    # Create summary plots
    if PLOTTING_AVAILABLE:
        plot_filename = f"throwbin1_parallel_summary_{timestamp}.png"
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
    print(f"{'N':>10} | {'Ratio':>6} | {'Bins':>8} | {'Avg Covered':>12} | {'Eff (Avg/N/2)':>14}")
    print(f"{'-'*70}")
    
    for result in sorted(results, key=lambda x: (x['num_items'], x['bin_ratio'])):
        print(f"{result['num_items']:>10} | {result['bin_ratio']*100:>5.0f}% | {result['num_bins']:>8} | "
              f"{result['avg_covered']:>12.2f} | {result['avg_covered_over_half_n']:>14.2f}")
    
    print(f"{'-'*70}")
    
    return results


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Run ThrowBin_1 experiments in parallel'
    )
    parser.add_argument('--n-values', type=str,
                       default='10000,20000,30000,40000,50000,60000,70000,80000,90000,100000',
                       help='Comma-separated N values')
    parser.add_argument('--ratios', type=str, default='0.60,0.70,0.80,0.90,1.00',
                       help='Comma-separated bin ratios')
    parser.add_argument('-w', '--workers', type=int, default=None,
                       help='Number of workers')
    parser.add_argument('-p', '--path', type=str, default='./data/',
                       help='Data path')
    
    args = parser.parse_args()
    
    n_values = [int(n.strip()) for n in args.n_values.split(',')]
    bin_ratios = [float(r.strip()) for r in args.ratios.split(',')]
    
    results = run_parallel_experiments(n_values, bin_ratios, args.workers, args.path)
    
    print(f"\nAll experiments complete!")


if __name__ == "__main__":
    main()
