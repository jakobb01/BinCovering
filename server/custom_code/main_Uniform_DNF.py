"""
Driver for running DNF strategy with Optimal Uniform Generator.
Generates items using bin-filling approach with uniform distribution,
where OPT (optimal bins) is known in advance.
Applies swaps, runs DNF, and logs results to CSV.
Plots performance ratio (DNF/OPT) and item distribution.
"""
import sys
import datetime
import os
import csv
import math

from bincovering.generators.OptimalUniformGenerator import OptimalUniformGenerator
from bincovering.generators.FileShuffleGenerator import FileShuffleGenerator

from bincovering.algorithms.DNF_1 import DNFStrategy

# Try to import matplotlib for plotting
try:
    import matplotlib.pyplot as plt
    import numpy as np
    PLOTTING_AVAILABLE = True
except ImportError:
    PLOTTING_AVAILABLE = False
    print("Warning: matplotlib/numpy not available. Plotting will be skipped.")


def run_single_experiment(base_file, base_path, num_swaps):
    """
    Run a single DNF experiment with the specified number of swaps.
    
    Args:
        base_file: filename of the generated data
        base_path: path to the data directory
        num_swaps: number of random swaps to perform
        
    Returns:
        int: number of bins filled
    """
    file_gen = FileShuffleGenerator(
        filename=base_file,
        path=base_path,
        num_swaps=num_swaps
    )
    file_gen.start()

    strat = DNFStrategy()
    strat.start(generator=file_gen)

    while True:
        result = strat.next()
        if result is None:
            break

    strat.stop()
    return int(strat.full_bins)


def plot_results(csv_path, items_list, output_path=None):
    """
    Plot results from a CSV file.
    Shows: 1) Performance ratio (DNF/OPT) vs swaps, 2) Item size distribution histogram.
    
    Args:
        csv_path: path to the CSV file with results
        items_list: list of generated items for distribution analysis
        output_path: optional path to save the plot image
    """
    if not PLOTTING_AVAILABLE:
        print("Plotting not available (matplotlib not installed).")
        return
    
    swaps = []
    ratios = []
    opt_bins = 0
    
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            swaps.append(int(row['swaps']))
            ratio = float(row['ratio'])
            ratios.append(ratio)
            opt_bins = int(row['opt_bins'])
    
    if not swaps:
        print("No data to plot.")
        return
    
    # Create figure with two subplots
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))
    
    # Plot 1: Ratio (DNF/OPT) vs Swaps
    ax1.plot(swaps, ratios, 'g-', linewidth=0.5, alpha=0.7, label='DNF/OPT Ratio')
    ax1.scatter(swaps, ratios, s=1, c='green', alpha=0.5)
    ax1.axhline(y=1.0, color='r', linestyle='--', alpha=0.5, label='OPT (1.0)')
    
    ax1.set_xlabel('Number of Swaps', fontsize=12)
    ax1.set_ylabel('Ratio (DNF / OPT)', fontsize=12)
    ax1.set_title(f'DNF Strategy Performance Ratio (OPT = {opt_bins} bins)\n(Higher is better, 1.0 = Optimal)', fontsize=14)
    ax1.grid(True, alpha=0.3)
    ax1.legend()
    
    # Calculate statistics for ratio
    min_ratio = min(ratios)
    max_ratio = max(ratios)
    avg_ratio = sum(ratios) / len(ratios)
    variance = sum((r - avg_ratio) ** 2 for r in ratios) / len(ratios)
    std_ratio = math.sqrt(variance)
    
    stats_text = f'Min: {min_ratio:.4f}\nMax: {max_ratio:.4f}\nAvg: {avg_ratio:.4f}\nStd: {std_ratio:.4f}'
    ax1.text(0.98, 0.02, stats_text, transform=ax1.transAxes, fontsize=10,
            verticalalignment='bottom', horizontalalignment='right',
            bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.5))
    
    # Plot 2: Item Size Distribution (Histogram)
    if items_list:
        # Create histogram
        n_bins = min(50, len(items_list) // 10) if len(items_list) > 50 else 20
        ax2.hist(items_list, bins=n_bins, color='steelblue', edgecolor='black', alpha=0.7)
        
        # Add reference line for uniform distribution
        uniform_expected = len(items_list) / n_bins
        ax2.axhline(y=uniform_expected, color='r', linestyle='--', alpha=0.7, 
                   label=f'Expected if Uniform ({uniform_expected:.1f})')
        
        ax2.set_xlabel('Item Size', fontsize=12)
        ax2.set_ylabel('Frequency', fontsize=12)
        ax2.set_title(f'Item Size Distribution ({len(items_list)} items)', fontsize=14)
        ax2.grid(True, alpha=0.3, axis='y')
        ax2.legend()
        
        # Calculate distribution statistics
        items_arr = items_list
        min_item = min(items_arr)
        max_item = max(items_arr)
        avg_item = sum(items_arr) / len(items_arr)
        variance_item = sum((x - avg_item) ** 2 for x in items_arr) / len(items_arr)
        std_item = math.sqrt(variance_item)
        
        dist_stats = f'Min: {min_item:.4f}\nMax: {max_item:.4f}\nAvg: {avg_item:.4f}\nStd: {std_item:.4f}'
        ax2.text(0.98, 0.98, dist_stats, transform=ax2.transAxes, fontsize=10,
                verticalalignment='top', horizontalalignment='right',
                bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.5))
    
    plt.tight_layout()
    
    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        print(f"Plot saved to: {output_path}")
    
    plt.show()


def run_uniform_dnf_experiment(opt_bins=500, swap_step=1, max_swaps=None, data_path="./data/"):
    """
    Run the DNF experiment with optimal uniform distribution generator.
    
    Args:
        opt_bins: number of bins to cover (OPT) - generator produces items for this many bins
        swap_step: step size for number of swaps (default 1)
        max_swaps: maximum number of swaps (default = number of generated items)
        data_path: path to store data files
        
    Returns:
        str: path to the generated CSV file
    """
    print(f"\n{'='*60}")
    print(f"Running Optimal Uniform DNF Experiment")
    print(f"OPT bins: {opt_bins}, Swap step: {swap_step}")
    print(f"{'='*60}\n")
    
    # Step 1: Generate items for the specified number of bins
    base_gen = OptimalUniformGenerator(path=data_path)
    print("Generating optimal uniform distribution data file...")
    print(base_gen.start(opt_bins))
    
    # Get the generated items for distribution analysis
    items_list = base_gen.get_items()
    num_items = len(items_list)
    
    print(f"Total items generated: {num_items}")
    print(f"OPT (optimal bins): {opt_bins}")
    
    base_gen.stop()
    
    base_file = base_gen._filename
    base_path = base_gen._path
    print(f"Base file generated: {base_file}")
    
    # Set max_swaps to number of items if not specified
    if max_swaps is None:
        max_swaps = num_items
    
    # Create CSV filename
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    csv_filename = f"uniform_dnf_results_{opt_bins}bins_{timestamp}.csv"
    csv_path = os.path.join(base_path, csv_filename)
    
    # Step 2: Run DNF for increasing number of swaps and log to CSV
    print(f"\nRunning experiments (0 to {max_swaps} swaps)...")
    
    with open(csv_path, 'w', newline='') as csvfile:
        fieldnames = ['experiment_id', 'num_items', 'swaps', 'bins_filled', 'opt_bins', 'ratio', 'timestamp']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        experiment_id = 0
        total_experiments = (max_swaps // swap_step) + 1
        
        for swaps in range(0, max_swaps + 1, swap_step):
            bins_filled = run_single_experiment(base_file, base_path, swaps)
            
            # Calculate ratio (DNF / OPT)
            ratio = bins_filled / opt_bins if opt_bins > 0 else 0.0
            
            writer.writerow({
                'experiment_id': experiment_id,
                'num_items': num_items,
                'swaps': swaps,
                'bins_filled': bins_filled,
                'opt_bins': opt_bins,
                'ratio': f"{ratio:.6f}",
                'timestamp': datetime.datetime.now().isoformat()
            })
            
            # Progress update every 10%
            if experiment_id % max(1, total_experiments // 10) == 0:
                progress = (experiment_id / total_experiments) * 100
                print(f"Progress: {progress:.1f}% ({experiment_id}/{total_experiments}) - Swaps: {swaps}, Bins: {bins_filled}, Ratio: {ratio:.4f}")
            
            experiment_id += 1
    
    print(f"\nResults saved to: {csv_path}")
    print(f"OPT (Optimal bins): {opt_bins}")
    print(f"Total items: {num_items}")
    
    # Step 3: Generate plot
    if PLOTTING_AVAILABLE:
        plot_filename = f"uniform_dnf_plot_{opt_bins}bins_{timestamp}.png"
        plot_path = os.path.join(base_path, plot_filename)
        print("\nGenerating plot...")
        plot_results(csv_path, items_list, plot_path)
    
    return csv_path


def main():
    """Main entry point for the uniform DNF driver."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Run DNF strategy with uniform distribution generator'
    )
    parser.add_argument(
        '-n', '--opt-bins',
        type=int,
        default=500,
        help='Number of bins to cover (OPT) - generator produces items for this many bins (default: 500)'
    )
    parser.add_argument(
        '-s', '--swap-step',
        type=int,
        default=1,
        help='Step size for number of swaps (default: 1)'
    )
    parser.add_argument(
        '-m', '--max-swaps',
        type=int,
        default=None,
        help='Maximum number of swaps (default: same as number of generated items)'
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
            plot_results(args.plot_only, [], None)
        else:
            print(f"Error: CSV file not found: {args.plot_only}")
            sys.exit(1)
    else:
        # Run full experiment
        csv_path = run_uniform_dnf_experiment(
            opt_bins=args.opt_bins,
            swap_step=args.swap_step,
            max_swaps=args.max_swaps,
            data_path=args.path
        )
        
        print(f"\nExperiment complete!")
        print(f"CSV results: {csv_path}")


if __name__ == "__main__":
    main()
