"""
Driver for running AdaptiveBin strategy with different generators.

Supported generators:
1. uniform: Random items with uniform distribution [0,1], tested with random permutations
2. oneovern: Complementary pairs (small + big items), tested with fresh sequences each run
3. optimaluniform: Items generated to have known OPT, tested with permutations
4. bigitems: Large items (>0.5) only, worst case for some strategies

This driver:
1. Generates N items using the selected generator
2. Runs the AdaptiveBin strategy which opens bins adaptively
3. For uniform/optimaluniform: repeats with N random permutations of the same sequence
4. For oneovern/bigitems: generates a fresh sequence for each run
5. Logs results to CSV
6. Plots covered bins vs OPT

The AdaptiveBin strategy does NOT receive any advice about N - it discovers bins
dynamically as items arrive.

Usage:
    # Uniform distribution with permutations (default)
    python3 custom_code/main_AdaptiveBin.py -n 1000 -r 1000
    python3 custom_code/main_AdaptiveBin.py -n 1000 -r 1000 --generator uniform
    
    # OneOverN generator (fresh sequence each run)
    python3 custom_code/main_AdaptiveBin.py -n 1000 -r 1000 --generator oneovern
    
    # OptimalUniform generator (known OPT)
    python3 custom_code/main_AdaptiveBin.py -n 1000 -r 100 --generator optimaluniform
    
    # BigItems generator (stress test)
    python3 custom_code/main_AdaptiveBin.py -n 1000 -r 100 --generator bigitems
"""
import sys
import datetime
import os
import csv
import random
import math
import argparse

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../generate_bins/')))
from UniformGenerator import UniformGenerator
from OneOverN import OneOverNGenerator
from OptimalUniformGenerator import OptimalUniformGenerator
from BigItemsGenerator import BigItemsGenerator

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../strategies/')))
from AdaptiveBin import AdaptiveBinStrategy

# Try to import matplotlib for plotting
try:
    import matplotlib.pyplot as plt
    import numpy as np
    PLOTTING_AVAILABLE = True
except ImportError:
    PLOTTING_AVAILABLE = False
    print("Warning: matplotlib not available. Plotting will be skipped.")


class InMemoryPermutationGenerator:
    """
    A generator that serves items from an in-memory list with random permutation.
    Used to run experiments with the same set of items but different orderings.
    """
    def __init__(self, items, seed=None):
        """
        Args:
            items: list of item sizes
            seed: random seed for permutation (None = random)
        """
        self._original_items = items.copy()
        self._items = []
        self._index = 0
        self._seed = seed
    
    def start(self):
        """Shuffle the items and reset the generator."""
        self._items = self._original_items.copy()
        if self._seed is not None:
            random.seed(self._seed)
        random.shuffle(self._items)
        self._index = 0
        return f"InMemoryPermutationGenerator ready with {len(self._items)} items"
    
    def next(self):
        """Return the next item."""
        if self._index < len(self._items):
            item = self._items[self._index]
            self._index += 1
            return item
        else:
            raise StopIteration("No more items")
    
    def stop(self):
        """Stop the generator."""
        return f"InMemoryPermutationGenerator stopped. Served {self._index} items."


class InMemorySequenceGenerator:
    """
    A generator that serves items from an in-memory list WITHOUT shuffling.
    Used for OneOverN where the sequence order matters (worst case).
    """
    def __init__(self, items):
        """
        Args:
            items: list of item sizes (will be served in order)
        """
        self._items = items.copy()
        self._index = 0
    
    def start(self):
        """Reset the generator."""
        self._index = 0
        return f"InMemorySequenceGenerator ready with {len(self._items)} items"
    
    def next(self):
        """Return the next item."""
        if self._index < len(self._items):
            item = self._items[self._index]
            self._index += 1
            return item
        else:
            raise StopIteration("No more items")
    
    def stop(self):
        """Stop the generator."""
        return f"InMemorySequenceGenerator stopped. Served {self._index} items."


def run_single_experiment_permutation(items, seed=None):
    """
    Run a single AdaptiveBin experiment with a permutation of the items.
    Used for Uniform generator testing.
    
    Args:
        items: list of item sizes
        seed: random seed for permutation
        
    Returns:
        tuple: (covered_bins, total_bins, items_received)
    """
    gen = InMemoryPermutationGenerator(items, seed=seed)
    gen.start()
    
    strat = AdaptiveBinStrategy()
    strat.start(generator=gen)
    
    while True:
        result = strat.next()
        if result is None:
            break
    
    strat.stop()
    return strat.get_covered_bins(), strat.get_total_bins(), strat.get_items_received()


def run_single_experiment_sequence(items):
    """
    Run a single AdaptiveBin experiment with items in their original order.
    Used for OneOverN generator testing (worst case sequence).
    
    Args:
        items: list of item sizes (served in order)
        
    Returns:
        tuple: (covered_bins, total_bins, items_received)
    """
    gen = InMemorySequenceGenerator(items)
    gen.start()
    
    strat = AdaptiveBinStrategy()
    strat.start(generator=gen)
    
    while True:
        result = strat.next()
        if result is None:
            break
    
    strat.stop()
    return strat.get_covered_bins(), strat.get_total_bins(), strat.get_items_received()


def generate_uniform_items(num_items, output_dir):
    """Generate items using UniformGenerator."""
    gen = UniformGenerator(max_size=1.0, path=output_dir)
    gen.start(num_items)
    
    items = []
    while True:
        try:
            item = gen.next()
            items.append(item)
        except StopIteration:
            break
    gen.stop()
    
    return items


def generate_oneovern_items(num_items, output_dir):
    """Generate items using OneOverNGenerator (worst case sequence)."""
    gen = OneOverNGenerator(max_load=1.0, path=output_dir)
    gen.start(num_items)
    
    items = []
    while True:
        try:
            item = gen.next()
            items.append(item)
        except StopIteration:
            break
    gen.stop()
    
    return items


def generate_optimaluniform_items(opt_bins, output_dir):
    """
    Generate items using OptimalUniformGenerator (known OPT).
    
    Args:
        opt_bins: the number of optimal bins (OPT value)
        output_dir: directory for output files
        
    Returns:
        tuple: (items, opt) where items is the list and opt is the known optimal
    """
    gen = OptimalUniformGenerator(path=output_dir)
    gen.start(opt_bins)
    
    items = gen.get_items()
    opt = gen.get_optimal_bins()
    gen.stop()
    
    return items, opt


def generate_bigitems(num_items, output_dir, min_size=0.51, max_size=0.99):
    """
    Generate items using BigItemsGenerator (stress test for big items).
    
    Args:
        num_items: number of items to generate
        output_dir: directory for output files
        min_size: minimum item size (default 0.51)
        max_size: maximum item size (default 0.99)
        
    Returns:
        tuple: (items, opt) where items is the list and opt is floor(sum)
    """
    gen = BigItemsGenerator(min_size=min_size, max_size=max_size, path=output_dir)
    gen.start(num_items)
    
    items = gen.get_items()
    opt = gen.get_optimal_bins()
    gen.stop()
    
    return items, opt


def plot_results(csv_path, items_list, output_path=None, num_items=None, generator_type='uniform'):
    """
    Plot results from a CSV file.
    Shows: 
    1) Item size distribution
    2) Covered bins over runs with OPT line
    3) Result distribution histogram
    
    Args:
        csv_path: path to the CSV file with results
        items_list: list of generated items for distribution analysis (last run for OneOverN)
        output_path: optional path to save the plot image
        num_items: number of items (N), used for OPT calculation
        generator_type: 'uniform' or 'oneovern'
    """
    if not PLOTTING_AVAILABLE:
        print("Plotting not available (matplotlib not installed).")
        return
    
    runs = []
    bins_covered_list = []
    total_bins_list = []
    
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            runs.append(int(row['run_id']))
            bins_covered_list.append(int(row['bins_covered']))
            total_bins_list.append(int(row['total_bins']))
    
    if not runs:
        print("No data to plot.")
        return
    
    # Calculate statistics for bins covered
    min_bins = min(bins_covered_list)
    max_bins = max(bins_covered_list)
    avg_bins = sum(bins_covered_list) / len(bins_covered_list)
    variance = sum((b - avg_bins) ** 2 for b in bins_covered_list) / len(bins_covered_list)
    std_bins = variance ** 0.5
    
    # OPT is N/2 for both generators
    optimal = num_items // 2 if num_items else max_bins
    
    # Create figure with three subplots
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(14, 16))
    
    # Plot 1: Item Size Distribution (Histogram) - TOP
    if items_list:
        n_bins_hist = min(50, len(items_list) // 10) if len(items_list) > 50 else 20
        ax1.hist(items_list, bins=n_bins_hist, color='steelblue', edgecolor='black', alpha=0.7)
        
        if generator_type == 'uniform':
            # Add reference line for uniform distribution
            uniform_expected = len(items_list) / n_bins_hist
            ax1.axhline(y=uniform_expected, color='r', linestyle='--', alpha=0.7, 
                       label=f'Expected if Uniform ({uniform_expected:.1f})')
        
        ax1.set_xlabel('Item Size', fontsize=12)
        ax1.set_ylabel('Frequency', fontsize=12)
        
        gen_label = 'Uniform' if generator_type == 'uniform' else 'OneOverN (Complementary Pairs)'
        ax1.set_title(f'Item Size Distribution - {gen_label} ({len(items_list)} items)', fontsize=14)
        ax1.grid(True, alpha=0.3, axis='y')
        if generator_type == 'uniform':
            ax1.legend()
        
        # Calculate distribution statistics
        min_item = min(items_list)
        max_item = max(items_list)
        avg_item = sum(items_list) / len(items_list)
        variance_item = sum((x - avg_item) ** 2 for x in items_list) / len(items_list)
        std_item = math.sqrt(variance_item)
        
        dist_stats = f'Min: {min_item:.4f}\nMax: {max_item:.4f}\nAvg: {avg_item:.4f}\nStd: {std_item:.4f}'
        ax1.text(0.98, 0.98, dist_stats, transform=ax1.transAxes, fontsize=10,
                verticalalignment='top', horizontalalignment='right',
                bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.5))
    
    # Plot 2: Covered Bins vs OPT over Runs - MIDDLE
    ax2.plot(runs, bins_covered_list, 'b-', linewidth=0.5, alpha=0.7, label='AdaptiveBin Covered')
    ax2.scatter(runs, bins_covered_list, s=2, c='blue', alpha=0.5)
    
    # OPT line (N/2)
    ax2.axhline(y=optimal, color='green', linestyle='-', linewidth=2, alpha=0.8, 
               label=f'OPT = N/2 = {optimal}')
    
    # Average line
    ax2.axhline(y=avg_bins, color='red', linestyle='--', linewidth=1.5, alpha=0.8,
               label=f'Average = {avg_bins:.2f}')
    
    x_label = 'Permutation Number' if generator_type == 'uniform' else 'Sequence Number (Fresh Generation)'
    ax2.set_xlabel(x_label, fontsize=12)
    ax2.set_ylabel('Bins Covered', fontsize=12)
    
    gen_label = 'Uniform (Permutations)' if generator_type == 'uniform' else 'OneOverN (Fresh Sequences)'
    ax2.set_title(f'AdaptiveBin Strategy: Covered Bins vs OPT (N={num_items})\nGenerator: {gen_label}, Formula: ceil(items_received/e)', fontsize=14)
    ax2.grid(True, alpha=0.3)
    ax2.legend(loc='lower right')
    
    # Performance ratio
    ratio = avg_bins / optimal if optimal > 0 else 0
    stats_text = f'Min: {min_bins}\nMax: {max_bins}\nAvg: {avg_bins:.2f}\nStd: {std_bins:.2f}\nRatio to OPT: {ratio:.4f}'
    ax2.text(0.02, 0.02, stats_text, transform=ax2.transAxes, fontsize=10,
            verticalalignment='bottom', horizontalalignment='left',
            bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.8))
    
    # Plot 3: Result Size Class Histogram - BOTTOM
    num_classes = min(30, max_bins - min_bins + 1) if max_bins > min_bins else 10
    
    ax3.hist(bins_covered_list, bins=num_classes, color='coral', edgecolor='black', alpha=0.7)
    
    # Add OPT line on histogram
    ax3.axvline(x=optimal, color='green', linestyle='-', linewidth=2, alpha=0.8,
               label=f'OPT = {optimal}')
    ax3.axvline(x=avg_bins, color='red', linestyle='--', linewidth=1.5, alpha=0.8,
               label=f'Average = {avg_bins:.2f}')
    
    ax3.set_xlabel('Bins Covered', fontsize=12)
    ax3.set_ylabel('Frequency', fontsize=12)
    ax3.set_title('Distribution of Covered Bins Across All Runs', fontsize=14)
    ax3.grid(True, alpha=0.3, axis='y')
    ax3.legend()
    
    plt.tight_layout()
    
    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        print(f"Plot saved to: {output_path}")
    
    plt.show()


def run_uniform_experiments(num_items, num_runs, output_dir, seed=None):
    """
    Run experiments with Uniform generator using permutations.
    
    Returns:
        tuple: (results_list, items_list, csv_path)
    """
    if seed is not None:
        random.seed(seed)
    
    print("Generating uniform distribution items...")
    items = generate_uniform_items(num_items, output_dir)
    
    print(f"Generated {len(items)} items")
    print(f"Item range: [{min(items):.6f}, {max(items):.6f}]")
    print(f"Average item size: {sum(items)/len(items):.6f}\n")
    
    # Prepare CSV output
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_filename = f"adaptivebin_uniform_{num_items}items_{timestamp}.csv"
    csv_path = os.path.join(output_dir, csv_filename)
    
    os.makedirs(output_dir, exist_ok=True)
    
    # Run experiments
    print(f"Running {num_runs} permutation experiments...")
    
    results = []
    opt = num_items // 2
    
    with open(csv_path, 'w', newline='') as csvfile:
        fieldnames = ['run_id', 'bins_covered', 'total_bins', 'items_received', 'opt', 'ratio_to_opt']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for run_id in range(1, num_runs + 1):
            covered, total, received = run_single_experiment_permutation(items, seed=run_id)
            ratio = covered / opt if opt > 0 else 0
            
            row = {
                'run_id': run_id,
                'bins_covered': covered,
                'total_bins': total,
                'items_received': received,
                'opt': opt,
                'ratio_to_opt': f"{ratio:.6f}"
            }
            writer.writerow(row)
            results.append(covered)
            
            if run_id % 100 == 0 or run_id == num_runs:
                print(f"  Completed {run_id}/{num_runs} runs...")
    
    return results, items, csv_path


def run_oneovern_experiments(num_items, num_runs, output_dir, seed=None):
    """
    Run experiments with OneOverN generator using fresh sequences each run.
    
    Returns:
        tuple: (results_list, last_items_list, csv_path)
    """
    if seed is not None:
        random.seed(seed)
    
    print(f"Will generate {num_runs} fresh OneOverN sequences...")
    print(f"Each sequence: {num_items} items ({num_items//2} small + {num_items//2} big complementary pairs)")
    print()
    
    # Prepare CSV output
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_filename = f"adaptivebin_oneovern_{num_items}items_{timestamp}.csv"
    csv_path = os.path.join(output_dir, csv_filename)
    
    os.makedirs(output_dir, exist_ok=True)
    
    # Run experiments
    print(f"Running {num_runs} experiments with fresh sequences...")
    
    results = []
    opt = num_items // 2
    last_items = None
    
    with open(csv_path, 'w', newline='') as csvfile:
        fieldnames = ['run_id', 'bins_covered', 'total_bins', 'items_received', 'opt', 'ratio_to_opt']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for run_id in range(1, num_runs + 1):
            # Generate fresh sequence for each run
            items = generate_oneovern_items(num_items, output_dir)
            last_items = items  # Keep last one for plotting
            
            covered, total, received = run_single_experiment_sequence(items)
            ratio = covered / opt if opt > 0 else 0
            
            row = {
                'run_id': run_id,
                'bins_covered': covered,
                'total_bins': total,
                'items_received': received,
                'opt': opt,
                'ratio_to_opt': f"{ratio:.6f}"
            }
            writer.writerow(row)
            results.append(covered)
            
            if run_id % 100 == 0 or run_id == num_runs:
                print(f"  Completed {run_id}/{num_runs} runs...")
    
    return results, last_items, csv_path


def main():
    parser = argparse.ArgumentParser(description='Run AdaptiveBin strategy experiments')
    parser.add_argument('-n', '--num-items', type=int, default=1000,
                       help='Number of items to generate (default: 1000, must be even for OneOverN)')
    parser.add_argument('-r', '--runs', type=int, default=1000,
                       help='Number of runs (default: 1000)')
    parser.add_argument('-g', '--generator', type=str, default='uniform',
                       choices=['uniform', 'oneovern'],
                       help='Generator type: uniform (permutations) or oneovern (fresh sequences)')
    parser.add_argument('--no-plot', action='store_true',
                       help='Skip plotting (just run experiments)')
    parser.add_argument('--seed', type=int, default=None,
                       help='Random seed for reproducibility')
    parser.add_argument('--output-dir', type=str, default='./data/',
                       help='Output directory for results')
    
    args = parser.parse_args()
    
    num_items = args.num_items
    num_runs = args.runs
    generator_type = args.generator.lower()
    
    # OneOverN requires even number of items
    if generator_type == 'oneovern' and num_items % 2 != 0:
        print(f"Error: OneOverN generator requires even number of items. Got {num_items}.")
        sys.exit(1)
    
    print(f"\n{'='*70}")
    print(f"AdaptiveBin Strategy Experiment")
    print(f"{'='*70}")
    print(f"Generator: {generator_type.upper()}")
    print(f"Number of items (N): {num_items}")
    print(f"Number of runs: {num_runs}")
    print(f"OPT (N/2): {num_items // 2}")
    print(f"Formula: ceil(items_received/e), where 1/e ≈ {1.0/math.e:.6f}")
    
    if generator_type == 'uniform':
        print(f"Mode: Same items, different random permutations each run")
    else:
        print(f"Mode: Fresh worst-case sequence generated each run")
    print(f"{'='*70}\n")
    
    # Run experiments based on generator type
    if generator_type == 'uniform':
        results, items, csv_path = run_uniform_experiments(
            num_items, num_runs, args.output_dir, args.seed
        )
    else:
        results, items, csv_path = run_oneovern_experiments(
            num_items, num_runs, args.output_dir, args.seed
        )
    
    print(f"\nResults saved to: {csv_path}")
    
    # Calculate and display summary statistics
    avg_covered = sum(results) / len(results)
    min_covered = min(results)
    max_covered = max(results)
    variance = sum((r - avg_covered) ** 2 for r in results) / len(results)
    std_covered = math.sqrt(variance)
    opt = num_items // 2
    
    print(f"\n{'='*70}")
    print(f"SUMMARY STATISTICS")
    print(f"{'='*70}")
    print(f"Generator: {generator_type.upper()}")
    print(f"Bins Covered:")
    print(f"  Minimum: {min_covered}")
    print(f"  Maximum: {max_covered}")
    print(f"  Average: {avg_covered:.2f}")
    print(f"  Std Dev: {std_covered:.2f}")
    print(f"\nComparison to OPT (N/2 = {opt}):")
    print(f"  Average ratio: {avg_covered/opt:.4f}")
    print(f"  Best ratio:    {max_covered/opt:.4f}")
    print(f"  Worst ratio:   {min_covered/opt:.4f}")
    print(f"{'='*70}\n")
    
    # Plot results
    if not args.no_plot and PLOTTING_AVAILABLE:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        plot_path = os.path.join(args.output_dir, f"adaptivebin_{generator_type}_{num_items}items_{timestamp}.png")
        plot_results(csv_path, items, output_path=plot_path, num_items=num_items, generator_type=generator_type)
    elif not PLOTTING_AVAILABLE:
        print("Matplotlib not available - skipping plot generation.")


if __name__ == "__main__":
    main()
