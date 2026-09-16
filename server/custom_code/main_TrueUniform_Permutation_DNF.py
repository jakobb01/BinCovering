"""
Driver for running DNF strategy with True Uniform Generator using PERMUTATIONS.
Generates items with true uniform distribution (no OPT known),
applies random permutations (full shuffles), runs DNF, and logs results to CSV.
Plots: 1) Item size distribution, 2) DNF bins filled vs permutation#, 3) Result size class histogram.
"""
import sys
import datetime
import os
import csv
import math

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../generate_bins/')))
from UniformGenerator import UniformGenerator
from FilePermutationGenerator import FilePermutationGenerator

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../strategies/')))
from DNF_1 import DNFStrategy

# Try to import matplotlib for plotting
try:
    import matplotlib.pyplot as plt
    PLOTTING_AVAILABLE = True
except ImportError:
    PLOTTING_AVAILABLE = False
    print("Warning: matplotlib not available. Plotting will be skipped.")


def run_single_experiment(base_file, base_path, seed):
    """
    Run a single DNF experiment with a random permutation.
    
    Args:
        base_file: filename of the generated data
        base_path: path to the data directory
        seed: random seed for the permutation
        
    Returns:
        int: number of bins filled
    """
    file_gen = FilePermutationGenerator(
        filename=base_file,
        path=base_path,
        seed=seed
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
    Shows: 1) Item size distribution, 2) DNF bins filled vs permutation#, 3) Result size class histogram.
    
    Args:
        csv_path: path to the CSV file with results
        items_list: list of generated items for distribution analysis
        output_path: optional path to save the plot image
    """
    if not PLOTTING_AVAILABLE:
        print("Plotting not available (matplotlib not installed).")
        return
    
    permutation_nums = []
    bins_filled_list = []
    
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            permutation_nums.append(int(row['permutation_num']))
            bins_filled_list.append(int(row['bins_filled']))
    
    if not permutation_nums:
        print("No data to plot.")
        return
    
    # Calculate statistics for bins filled (needed for multiple plots)
    min_bins = min(bins_filled_list)
    max_bins = max(bins_filled_list)
    avg_bins = sum(bins_filled_list) / len(bins_filled_list)
    variance = sum((b - avg_bins) ** 2 for b in bins_filled_list) / len(bins_filled_list)
    std_bins = math.sqrt(variance)
    
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
        ax1.set_title(f'Item Size Distribution ({len(items_list)} items)', fontsize=14)
        ax1.grid(True, alpha=0.3, axis='y')
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
    
    # Plot 2: DNF Bins Filled vs Permutation Number - MIDDLE
    ax2.plot(permutation_nums, bins_filled_list, 'b-', linewidth=0.5, alpha=0.7, label='DNF Bins Filled')
    ax2.scatter(permutation_nums, bins_filled_list, s=1, c='blue', alpha=0.5)
    
    ax2.set_xlabel('Permutation Number', fontsize=12)
    ax2.set_ylabel('Bins Filled (DNF)', fontsize=12)
    ax2.set_title('DNF Strategy Performance with Random Permutations\n(Bins Filled vs Permutation Number)', fontsize=14)
    ax2.grid(True, alpha=0.3)
    ax2.legend()
    
    stats_text = f'Min: {min_bins}\nMax: {max_bins}\nAvg: {avg_bins:.2f}\nStd: {std_bins:.2f}'
    ax2.text(0.98, 0.02, stats_text, transform=ax2.transAxes, fontsize=10,
            verticalalignment='bottom', horizontalalignment='right',
            bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.5))
    
    # Plot 3: Result Size Class Histogram - BOTTOM
    # Create size classes based on the range of results
    num_classes = 20  # Number of size classes
    
    # Determine class boundaries
    class_min = min_bins
    class_max = max_bins
    class_range = class_max - class_min
    
    if class_range == 0:
        # All results are the same
        class_counts = {min_bins: len(bins_filled_list)}
        class_labels = [str(min_bins)]
        x_positions = [0]
        counts = [len(bins_filled_list)]
    else:
        class_width = class_range / num_classes
        class_counts = {}
        class_boundaries = []
        
        for i in range(num_classes):
            lower = class_min + i * class_width
            upper = class_min + (i + 1) * class_width
            class_boundaries.append((lower, upper))
            class_counts[i] = 0
        
        # Count results in each class
        for bins in bins_filled_list:
            for i, (lower, upper) in enumerate(class_boundaries):
                if i == num_classes - 1:  # Last class includes upper bound
                    if lower <= bins <= upper:
                        class_counts[i] += 1
                        break
                else:
                    if lower <= bins < upper:
                        class_counts[i] += 1
                        break
        
        # Create labels for x-axis
        class_labels = [f'{int(class_boundaries[i][0])}-{int(class_boundaries[i][1])}' 
                       for i in range(num_classes)]
        x_positions = range(num_classes)
        counts = [class_counts[i] for i in range(num_classes)]
    
    # Plot the histogram
    ax3.bar(x_positions, counts, color='coral', edgecolor='black', alpha=0.7)
    if class_range > 0:
        ax3.set_xticks(x_positions)
        ax3.set_xticklabels(class_labels, rotation=45, ha='right', fontsize=8)
    
    ax3.set_xlabel('Bins Filled (Size Classes)', fontsize=12)
    ax3.set_ylabel('Frequency', fontsize=12)
    ax3.set_title('Distribution of DNF Results (Size Classes)', fontsize=14)
    ax3.grid(True, alpha=0.3, axis='y')
    
    # Add statistics text
    class_stats = f'Classes: {num_classes}\nRange: [{min_bins}, {max_bins}]'
    ax3.text(0.98, 0.98, class_stats, transform=ax3.transAxes, fontsize=10,
            verticalalignment='top', horizontalalignment='right',
            bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.5))
    
    plt.tight_layout()
    
    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        print(f"Plot saved to: {output_path}")
    
    plt.show()


def run_true_uniform_permutation_experiment(num_items=1000, num_permutations=None, data_path="./data/"):
    """
    Run the DNF experiment with true uniform distribution using random permutations.
    
    Args:
        num_items: number of items to generate
        num_permutations: number of random permutations to test (default = 10 * num_items)
        data_path: path to store data files
        
    Returns:
        str: path to the generated CSV file
    """
    # Set num_permutations to 20 * number of items if not specified
    if num_permutations is None:
        num_permutations = num_items * 20
    
    print(f"\n{'='*60}")
    print(f"Running True Uniform DNF Experiment (Permutations)")
    print(f"Items: {num_items}, Permutations: {num_permutations}")
    print(f"{'='*60}\n")
    
    # Step 1: Generate items with true uniform distribution
    base_gen = UniformGenerator(path=data_path)
    print("Generating true uniform distribution data file...")
    print(base_gen.start(num_items))
    
    # Get the generated items for distribution analysis
    items_list = base_gen.get_items()
    
    print(f"Total items generated: {len(items_list)}")
    
    base_gen.stop()
    
    base_file = base_gen._filename
    base_path = base_gen._path
    print(f"Base file generated: {base_file}")
    
    # Create CSV filename
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    pid = os.getpid()
    csv_filename = f"true_uniform_permutation_results_{num_items}items_{timestamp}_{pid}.csv"
    csv_path = os.path.join(base_path, csv_filename)
    
    # Step 2: Run DNF for each permutation and log to CSV
    print(f"\nRunning {num_permutations} permutation experiments...")
    
    with open(csv_path, 'w', newline='') as csvfile:
        fieldnames = ['experiment_id', 'num_items', 'permutation_num', 'seed', 'bins_filled', 'timestamp']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for perm_num in range(num_permutations):
            # Use permutation number as seed for reproducibility
            seed = perm_num
            bins_filled = run_single_experiment(base_file, base_path, seed)
            
            writer.writerow({
                'experiment_id': perm_num,
                'num_items': num_items,
                'permutation_num': perm_num,
                'seed': seed,
                'bins_filled': bins_filled,
                'timestamp': datetime.datetime.now().isoformat()
            })
            
            # Progress update every 10%
            if perm_num % max(1, num_permutations // 10) == 0:
                progress = (perm_num / num_permutations) * 100
                print(f"Progress: {progress:.1f}% ({perm_num}/{num_permutations}) - Permutation: {perm_num}, Bins: {bins_filled}")
    
    print(f"\nResults saved to: {csv_path}")
    print(f"Total items: {num_items}")
    print(f"Total permutations: {num_permutations}")
    
    # Step 3: Generate plot
    if PLOTTING_AVAILABLE:
        plot_filename = f"true_uniform_permutation_plot_{num_items}items_{timestamp}_{pid}.png"
        plot_path = os.path.join(base_path, plot_filename)
        print("\nGenerating plot...")
        plot_results(csv_path, items_list, plot_path)
    
    return csv_path


def main():
    """Main entry point for the true uniform permutation DNF driver."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Run DNF strategy with true uniform distribution using random permutations'
    )
    parser.add_argument(
        '-n', '--num-items',
        type=int,
        default=1000,
        help='Number of items to generate (default: 1000)'
    )
    parser.add_argument(
        '-p', '--num-permutations',
        type=int,
        default=None,
        help='Number of random permutations to test (default: 10 * num-items)'
    )
    parser.add_argument(
        '--path',
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
        csv_path = run_true_uniform_permutation_experiment(
            num_items=args.num_items,
            num_permutations=args.num_permutations,
            data_path=args.path
        )
        
        print(f"\nExperiment complete!")
        print(f"CSV results: {csv_path}")


if __name__ == "__main__":
    main()
