"""
Driver for running ThrowBin_1 strategy with Uniform Generator.

ThrowBin_1 maintains a constant number of active bins by replacing covered bins with new empty ones.

Usage:
    python3 custom_code/main_ThrowBin_1.py -n 1000 -r 1000
    python3 custom_code/main_ThrowBin_1.py --num-items 5000 --runs 5000 --bin-ratio 0.35
"""
import sys
import datetime
import os
import csv
import random

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../generate_bins/')))
from UniformGenerator import UniformGenerator

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../strategies/')))
from ThrowBin_1 import ThrowBin_1_Strategy

# Try to import matplotlib for plotting
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


def run_single_experiment(items, num_items, bin_ratio=0.5):
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


def plot_results(csv_path, items_list, output_path=None, num_items=None):
    """Plot results from CSV file."""
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
    
    # Calculate statistics
    min_bins = min(bins_covered_list)
    max_bins = max(bins_covered_list)
    avg_bins = sum(bins_covered_list) / len(bins_covered_list)
    variance = sum((b - avg_bins) ** 2 for b in bins_covered_list) / len(bins_covered_list)
    std_bins = variance ** 0.5
    
    # For ThrowBin_1, optimal comparison is different since bins are replaced
    # We'll use the active bin count for reference
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        first_row = next(reader)
        num_active_bins = int(first_row['num_bins'])
    
    # Create figure with three subplots
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 14))
    
    # Plot 1: Item Size Distribution (Histogram) - TOP
    if items_list:
        n_bins_hist = min(50, len(items_list) // 10) if len(items_list) > 50 else 20
        ax1.hist(items_list, bins=n_bins_hist, color='steelblue', edgecolor='black', alpha=0.7)
        
        uniform_expected = len(items_list) / n_bins_hist
        ax1.axhline(y=uniform_expected, color='r', linestyle='--', alpha=0.7, 
                   label=f'Expected if Uniform ({uniform_expected:.1f})')
        
        ax1.set_xlabel('Item Size', fontsize=12)
        ax1.set_ylabel('Frequency', fontsize=12)
        ax1.set_title(f'Item Size Distribution ({len(items_list)} items, sorted descending)', fontsize=14)
        ax1.grid(True, alpha=0.3, axis='y')
        ax1.legend()
        
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
    ax2.plot(runs, bins_covered_list, 'b-', linewidth=0.5, alpha=0.7, label='Total Bins Covered')
    ax2.scatter(runs, bins_covered_list, s=1, c='blue', alpha=0.5)
    
    ax2.axhline(y=avg_bins, color='r', linestyle='-', linewidth=1.5, alpha=0.8, 
                label=f'Average: {avg_bins:.2f}')
    
    # Add reference line for active bins
    ax2.axhline(y=num_active_bins, color='green', linestyle='--', linewidth=1.5, alpha=0.8,
                label=f'Active Bins: {num_active_bins}')
    
    ax2.set_xlabel('Run Number', fontsize=12)
    ax2.set_ylabel('Total Bins Covered', fontsize=12)
    ax2.set_title('ThrowBin_1 Strategy Performance\n(Total Covered Bins per Run, with constant active bins)', fontsize=14)
    ax2.grid(True, alpha=0.3)
    ax2.legend()
    
    stats_text = f'Min: {min_bins}\nMax: {max_bins}\nAvg: {avg_bins:.2f}\nStd: {std_bins:.2f}'
    ax2.text(0.98, 0.02, stats_text, transform=ax2.transAxes, fontsize=10,
            verticalalignment='bottom', horizontalalignment='right',
            bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.5))
    
    # Plot 3: Result Distribution Histogram - BOTTOM
    num_classes = 20
    class_min = min(bins_covered_list)
    class_max = max(bins_covered_list)
    class_range = class_max - class_min
    
    if class_range == 0:
        ax3.bar([f'{class_min}'], [len(bins_covered_list)], color='coral', 
                edgecolor='black', alpha=0.7)
    else:
        class_width = class_range / num_classes
        class_boundaries = []
        class_counts = [0] * num_classes
        
        for i in range(num_classes):
            lower = class_min + i * class_width
            upper = class_min + (i + 1) * class_width
            class_boundaries.append((lower, upper))
        
        for bins in bins_covered_list:
            for i, (lower, upper) in enumerate(class_boundaries):
                if i == num_classes - 1:
                    if lower <= bins <= upper:
                        class_counts[i] += 1
                        break
                else:
                    if lower <= bins < upper:
                        class_counts[i] += 1
                        break
        
        x_positions = range(num_classes)
        ax3.bar(x_positions, class_counts, color='coral', edgecolor='black', alpha=0.7)
        
        labels = [f'{int(class_boundaries[i][0])}' for i in range(num_classes)]
        ax3.set_xticks(x_positions)
        ax3.set_xticklabels(labels, rotation=45, ha='right', fontsize=8)
    
    ax3.set_xlabel('Total Bins Covered', fontsize=12)
    ax3.set_ylabel('Frequency', fontsize=12)
    ax3.set_title('Distribution of ThrowBin_1 Results', fontsize=14)
    ax3.grid(True, alpha=0.3, axis='y')
    
    class_stats = f'Classes: {num_classes}\nRange: [{int(class_min)}, {int(class_max)}]'
    ax3.text(0.98, 0.98, class_stats, transform=ax3.transAxes, fontsize=10,
            verticalalignment='top', horizontalalignment='right',
            bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.5))
    
    plt.tight_layout()
    
    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        print(f"Plot saved to: {output_path}")
    
    plt.show()


def run_throwbin1_experiment(num_items=1000, num_runs=None, bin_ratio=0.5, data_path="./data/"):
    """Run the ThrowBin_1 experiment."""
    if num_runs is None:
        num_runs = num_items
    
    print(f"\n{'='*60}")
    print(f"Running ThrowBin_1 Experiment")
    print(f"Items: {num_items}, Bin Ratio: {bin_ratio*100:.0f}%, Runs: {num_runs}")
    print(f"{'='*60}\n")
    
    base_gen = UniformGenerator(path=data_path)
    print("Generating uniform distribution data file...")
    print(base_gen.start(num_items))
    
    items_list = base_gen.get_items()
    print(f"Total items generated: {len(items_list)}")
    print(f"Items sorted in descending order: {items_list[0]:.4f} > ... > {items_list[-1]:.4f}")
    
    base_gen.stop()
    
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    ratio_str = f"{int(bin_ratio*100)}pct"
    csv_filename = f"throwbin1_results_{num_items}items_{ratio_str}_{timestamp}.csv"
    csv_path = os.path.join(data_path, csv_filename)
    
    print(f"\nRunning {num_runs} experiments...")
    
    with open(csv_path, 'w', newline='') as csvfile:
        fieldnames = ['run_id', 'num_items', 'bin_ratio', 'num_bins', 'bins_covered', 'coverage_ratio', 'timestamp']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        num_bins = int(num_items * bin_ratio)
        
        for run_id in range(num_runs):
            bins_covered, active_bins = run_single_experiment(items_list, num_items, bin_ratio)
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
            
            if run_id % max(1, num_runs // 10) == 0:
                progress = (run_id / num_runs) * 100
                print(f"Progress: {progress:.1f}% ({run_id}/{num_runs}) - Covered: {bins_covered} (ratio: {coverage_ratio:.2f})")
    
    print(f"\nResults saved to: {csv_path}")
    print(f"Total items: {num_items}, Bin ratio: {bin_ratio*100:.0f}%, Total runs: {num_runs}")
    
    if PLOTTING_AVAILABLE:
        plot_filename = f"throwbin1_plot_{num_items}items_{ratio_str}_{timestamp}.png"
        plot_path = os.path.join(data_path, plot_filename)
        print("\nGenerating plot...")
        plot_results(csv_path, items_list, plot_path, num_items)
    
    return csv_path


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Run ThrowBin_1 strategy (constant active bins with replacement)'
    )
    parser.add_argument('-n', '--num-items', type=int, default=1000, help='Number of items (N)')
    parser.add_argument('-r', '--runs', type=int, default=None, help='Number of runs (default: N)')
    parser.add_argument('-b', '--bin-ratio', type=float, default=0.5, help='Bin ratio (default: 0.5)')
    parser.add_argument('-p', '--path', type=str, default='./data/', help='Data path')
    
    args = parser.parse_args()
    
    csv_path = run_throwbin1_experiment(
        num_items=args.num_items,
        num_runs=args.runs,
        bin_ratio=args.bin_ratio,
        data_path=args.path
    )
    
    print(f"\nExperiment complete!")
    print(f"CSV results: {csv_path}")


if __name__ == "__main__":
    main()
