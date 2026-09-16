"""
Driver for running ThrowBin strategy with Uniform Generator.

This driver:
1. Generates N random items with uniform distribution, sorted in descending order
2. Runs the ThrowBin strategy which opens N/2 bins and randomly assigns items
3. Repeats the experiment N times (or configurable number of runs)
4. Logs results to CSV
5. Can be analyzed with analyze_csv_results.py

Usage:
    python3 custom_code/main_ThrowBin.py -n 1000 -r 1000
    python3 custom_code/main_ThrowBin.py --num-items 5000 --runs 5000
"""
import sys
import datetime
import os
import csv
import random

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../generate_bins/')))
from UniformGenerator import UniformGenerator

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../strategies/')))
from ThrowBin import ThrowBinStrategy

# Try to import matplotlib for plotting
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
    Used to re-run experiments with the same set of items but different random placements.
    """
    def __init__(self, items):
        """
        Args:
            items: list of item sizes (should be sorted in descending order)
        """
        self._items = items.copy()
        self._index = 0
    
    def start(self):
        """Reset the generator to the beginning."""
        self._index = 0
        return f"InMemoryGenerator ready with {len(self._items)} items"
    
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
        return f"InMemoryGenerator stopped. Served {self._index} items."


def run_single_experiment(items, num_items, bin_ratio=0.5):
    """
    Run a single ThrowBin experiment with the given items.
    
    Args:
        items: list of item sizes (sorted in descending order)
        num_items: total number of items (N)
        bin_ratio: ratio of N to use as number of bins (default 0.5 = 50%)
        
    Returns:
        int: number of covered bins
    """
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


def plot_results(csv_path, items_list, output_path=None, num_items=None):
    """
    Plot results from a CSV file.
    Shows: 1) Item size distribution, 2) Covered bins over runs, 3) Result distribution histogram
    
    Args:
        csv_path: path to the CSV file with results
        items_list: list of generated items for distribution analysis
        output_path: optional path to save the plot image
        num_items: number of items (N), used for percentage calculation
    """
    if not PLOTTING_AVAILABLE:
        print("Plotting not available (matplotlib not installed).")
        return
    
    runs = []
    bins_covered_list = []
    
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            runs.append(int(row['run_id']))
            bins_covered_list.append(int(row['bins_covered']))
    
    if not runs:
        print("No data to plot.")
        return
    
    # Calculate statistics for bins covered
    min_bins = min(bins_covered_list)
    max_bins = max(bins_covered_list)
    avg_bins = sum(bins_covered_list) / len(bins_covered_list)
    variance = sum((b - avg_bins) ** 2 for b in bins_covered_list) / len(bins_covered_list)
    std_bins = variance ** 0.5
    
    # Optimal is N/2
    optimal = num_items // 2 if num_items else max_bins
    
    # Create figure with three subplots
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 14))
    
    # Plot 1: Item Size Distribution (Histogram) - TOP
    if items_list:
        n_bins_hist = min(50, len(items_list) // 10) if len(items_list) > 50 else 20
        ax1.hist(items_list, bins=n_bins_hist, color='steelblue', edgecolor='black', alpha=0.7)
        
        # Add reference line for uniform distribution
        uniform_expected = len(items_list) / n_bins_hist
        ax1.axhline(y=uniform_expected, color='r', linestyle='--', alpha=0.7, 
                   label=f'Expected if Uniform ({uniform_expected:.1f})')
        
        ax1.set_xlabel('Item Size', fontsize=12)
        ax1.set_ylabel('Frequency', fontsize=12)
        ax1.set_title(f'Item Size Distribution ({len(items_list)} items, sorted descending)', fontsize=14)
        ax1.grid(True, alpha=0.3, axis='y')
        ax1.legend()
        
        # Calculate distribution statistics
        min_item = min(items_list)
        max_item = max(items_list)
        avg_item = sum(items_list) / len(items_list)
        variance_item = sum((x - avg_item) ** 2 for x in items_list) / len(items_list)
        std_item = variance_item ** 0.5
        
        dist_stats = f'Min: {min_item:.4f}\nMax: {max_item:.4f}\nAvg: {avg_item:.4f}\nStd: {std_item:.4f}'
        ax1.text(0.98, 0.98, dist_stats, transform=ax1.transAxes, fontsize=10,
                verticalalignment='top', horizontalalignment='right',
                bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.5))
    
    # Plot 2: Covered Bins vs Run Number - MIDDLE
    ax2.plot(runs, bins_covered_list, 'b-', linewidth=0.5, alpha=0.7, label='Bins Covered')
    ax2.scatter(runs, bins_covered_list, s=1, c='blue', alpha=0.5)
    
    # Add horizontal line for average
    ax2.axhline(y=avg_bins, color='r', linestyle='-', linewidth=1.5, alpha=0.8, 
                label=f'Average: {avg_bins:.2f}')
    
    # Add N/2 reference line
    ax2.axhline(y=optimal, color='green', linestyle='--', linewidth=1.5, alpha=0.8,
                label=f'Optimal (N/2): {optimal}')
    
    ax2.set_xlabel('Run Number', fontsize=12)
    ax2.set_ylabel('Bins Covered', fontsize=12)
    ax2.set_title('ThrowBin Strategy Performance\n(Covered Bins per Run)', fontsize=14)
    ax2.grid(True, alpha=0.3)
    ax2.legend()
    
    stats_text = f'Min: {min_bins}\nMax: {max_bins}\nAvg: {avg_bins:.2f}\nStd: {std_bins:.2f}'
    ax2.text(0.98, 0.02, stats_text, transform=ax2.transAxes, fontsize=10,
            verticalalignment='bottom', horizontalalignment='right',
            bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.5))
    
    # Plot 3: Result Size Class Histogram - BOTTOM
    # Convert to percentage of optimal (N/2)
    if optimal > 0:
        results_pct = [(b / optimal) * 100 for b in bins_covered_list]
    else:
        results_pct = bins_covered_list
    
    num_classes = 20
    class_min = min(results_pct)
    class_max = max(results_pct)
    class_range = class_max - class_min
    
    if class_range == 0:
        # All results are the same
        ax3.bar([f'{class_min:.1f}%'], [len(bins_covered_list)], color='coral', 
                edgecolor='black', alpha=0.7)
    else:
        class_width = class_range / num_classes
        class_boundaries = []
        class_counts = [0] * num_classes
        
        for i in range(num_classes):
            lower = class_min + i * class_width
            upper = class_min + (i + 1) * class_width
            class_boundaries.append((lower, upper))
        
        # Count results in each class
        for pct in results_pct:
            for i, (lower, upper) in enumerate(class_boundaries):
                if i == num_classes - 1:
                    if lower <= pct <= upper:
                        class_counts[i] += 1
                        break
                else:
                    if lower <= pct < upper:
                        class_counts[i] += 1
                        break
        
        x_positions = range(num_classes)
        ax3.bar(x_positions, class_counts, color='coral', edgecolor='black', alpha=0.7)
        
        # Create x-axis labels
        labels = [f'{class_boundaries[i][0]:.1f}' for i in range(num_classes)]
        ax3.set_xticks(x_positions)
        ax3.set_xticklabels(labels, rotation=45, ha='right', fontsize=8)
    
    ax3.set_xlabel('Covered Bins (% of N/2)', fontsize=12)
    ax3.set_ylabel('Frequency', fontsize=12)
    ax3.set_title('Distribution of ThrowBin Results', fontsize=14)
    ax3.grid(True, alpha=0.3, axis='y')
    
    class_stats = f'Classes: {num_classes}\nRange: [{class_min:.2f}%, {class_max:.2f}%]'
    ax3.text(0.98, 0.98, class_stats, transform=ax3.transAxes, fontsize=10,
            verticalalignment='top', horizontalalignment='right',
            bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.5))
    
    plt.tight_layout()
    
    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        print(f"Plot saved to: {output_path}")
    
    plt.show()


def run_throwbin_experiment(num_items=1000, num_runs=None, bin_ratio=0.5, data_path="./data/"):
    """
    Run the ThrowBin experiment with uniform distribution generator.
    
    Args:
        num_items: number of items to generate (N)
        num_runs: number of times to run the strategy (default = N)
        bin_ratio: ratio of N to use as number of bins (default 0.5 = 50%)
        data_path: path to store data files
        
    Returns:
        str: path to the generated CSV file
    """
    if num_runs is None:
        num_runs = num_items
    
    print(f"\n{'='*60}")
    print(f"Running ThrowBin Experiment")
    print(f"Items: {num_items}, Bin Ratio: {bin_ratio*100:.0f}%, Runs: {num_runs}")
    print(f"{'='*60}\n")
    
    # Step 1: Generate items with true uniform distribution
    base_gen = UniformGenerator(path=data_path)
    print("Generating uniform distribution data file...")
    print(base_gen.start(num_items))
    
    # Get the generated items (sorted in descending order by UniformGenerator)
    items_list = base_gen.get_items()
    
    print(f"Total items generated: {len(items_list)}")
    print(f"Items sorted in descending order: {items_list[0]:.4f} > ... > {items_list[-1]:.4f}")
    
    base_gen.stop()
    
    # Create CSV filename
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    ratio_str = f"{int(bin_ratio*100)}pct"
    csv_filename = f"throwbin_results_{num_items}items_{ratio_str}_{timestamp}.csv"
    csv_path = os.path.join(data_path, csv_filename)
    
    # Step 2: Run ThrowBin strategy num_runs times and log to CSV
    print(f"\nRunning {num_runs} experiments...")
    
    with open(csv_path, 'w', newline='') as csvfile:
        fieldnames = ['run_id', 'num_items', 'bin_ratio', 'num_bins', 'bins_covered', 'coverage_pct', 'timestamp']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        num_bins = int(num_items * bin_ratio)
        
        for run_id in range(num_runs):
            bins_covered, actual_bins = run_single_experiment(items_list, num_items, bin_ratio)
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
            
            # Progress update every 10%
            if run_id % max(1, num_runs // 10) == 0:
                progress = (run_id / num_runs) * 100
                print(f"Progress: {progress:.1f}% ({run_id}/{num_runs}) - Covered: {bins_covered}/{num_bins} ({coverage_pct:.2f}%)")
    
    print(f"\nResults saved to: {csv_path}")
    print(f"Total items: {num_items}, Bin ratio: {bin_ratio*100:.0f}%, Total runs: {num_runs}")
    
    # Step 3: Generate plot
    if PLOTTING_AVAILABLE:
        plot_filename = f"throwbin_plot_{num_items}items_{ratio_str}_{timestamp}.png"
        plot_path = os.path.join(data_path, plot_filename)
        print("\nGenerating plot...")
        plot_results(csv_path, items_list, plot_path, num_items)
    
    return csv_path


def main():
    """Main entry point for the ThrowBin driver."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Run ThrowBin strategy with uniform distribution generator'
    )
    parser.add_argument(
        '-n', '--num-items',
        type=int,
        default=1000,
        help='Number of items to generate (N) (default: 1000)'
    )
    parser.add_argument(
        '-r', '--runs',
        type=int,
        default=None,
        help='Number of runs (default: N)'
    )
    parser.add_argument(
        '-b', '--bin-ratio',
        type=float,
        default=0.5,
        help='Ratio of N to use as number of bins (default: 0.5 = 50%%)'
    )
    parser.add_argument(
        '-p', '--path',
        type=str,
        default='./data/',
        help='Path to store data files (default: ./data/)'
    )
    parser.add_argument(
        '--plot-only',
        type=str,
        default=None,
        help='Only generate plot from existing CSV file (provide CSV path)'
    )
    
    args = parser.parse_args()
    
    if args.plot_only:
        # Only plot from existing CSV (no item distribution available)
        if os.path.exists(args.plot_only):
            # Try to extract num_items from filename
            import re
            match = re.search(r'(\d+)items', args.plot_only)
            num_items = int(match.group(1)) if match else None
            plot_results(args.plot_only, [], None, num_items)
        else:
            print(f"Error: CSV file not found: {args.plot_only}")
            sys.exit(1)
    else:
        # Run full experiment
        csv_path = run_throwbin_experiment(
            num_items=args.num_items,
            num_runs=args.runs,
            bin_ratio=args.bin_ratio,
            data_path=args.path
        )
        
        print(f"\nExperiment complete!")
        print(f"CSV results: {csv_path}")
        print(f"\nTo analyze with the CSV analyzer:")
        print(f"  python3 custom_code/analyze_csv_results.py {csv_path}")


if __name__ == "__main__":
    main()
