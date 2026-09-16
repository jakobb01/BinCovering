"""
Enhanced CSV Analysis and Visualization for DNF Experiments.

This script reads CSV files from DNF experiments and creates detailed visualizations with:
1. Dynamic size classes based on actual data distribution
2. Median and quartile (Q1, Q3) annotations on item distribution
3. DNF performance shown as percentage of N/2 (optimal coverage)

Usage:
    # Single CSV file
    python3 custom_code/analyze_csv_results.py data/true_uniform_dnf_results_10000items_20251201_103556.csv
    
    # Multiple CSV files
    python3 custom_code/analyze_csv_results.py data/true_uniform_dnf_results_*.csv
    
    # All CSV files in data directory
    python3 custom_code/analyze_csv_results.py data/*.csv
"""

import sys
import os
import csv
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime


def calculate_statistics(items):
    """
    Calculate median and quartiles for item sizes.
    
    Args:
        items: list of item sizes
    
    Returns:
        dict with 'median', 'q1', 'q3'
    """
    sorted_items = sorted(items)
    median = np.median(sorted_items)
    q1 = np.percentile(sorted_items, 25)
    q3 = np.percentile(sorted_items, 75)
    
    return {
        'median': median,
        'q1': q1,
        'q3': q3
    }


def read_csv_data(csv_path):
    """
    Read experiment data from CSV file.
    
    Handles multiple CSV formats:
    1. Swap format: experiment_id,num_items,swaps,bins_filled,timestamp
    2. Permutation format: experiment_id,num_items,permutation_num,bins_filled,timestamp
    3. ThrowBin format: run_id,num_items,num_bins,bins_covered,coverage_pct,timestamp
    
    Args:
        csv_path: path to CSV file
    
    Returns:
        dict with 'metadata', 'items', 'results'
    """
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        
        # Read all rows
        rows = list(reader)
        
        if not rows:
            raise ValueError("CSV file is empty")
        
        # Extract metadata from first row
        first_row = rows[0]
        metadata = {
            'num_items': int(first_row['num_items'])
        }
        
        # Determine experiment type based on columns present
        if 'permutation_num' in first_row:
            metadata['experiment_type'] = 'permutation'
            x_key = 'permutation_num'
            bins_key = 'bins_filled'
        elif 'swaps' in first_row:
            metadata['experiment_type'] = 'swap'
            x_key = 'swaps'
            bins_key = 'bins_filled'
        elif 'run_id' in first_row and 'bins_covered' in first_row:
            # ThrowBin format
            metadata['experiment_type'] = 'throwbin'
            x_key = 'run_id'
            bins_key = 'bins_covered'
            if 'num_bins' in first_row:
                metadata['num_bins'] = int(first_row['num_bins'])
        else:
            raise ValueError("Unknown experiment type - no recognized column format")
        
        # Extract results
        results = []
        for row in rows:
            result = {
                'bins_filled': int(row[bins_key]),
                x_key: int(row[x_key])
            }
            results.append(result)
        
        # Items are not stored in the simple CSV format
        # We'll generate a placeholder since we can't show item distribution
        items = None
    
    return {
        'metadata': metadata,
        'items': items,
        'results': results
    }


def create_dynamic_size_classes(items, num_classes=None):
    """
    Create size classes dynamically based on the actual range of item sizes.
    
    Args:
        items: list of item sizes
        num_classes: number of classes (default: auto-calculate)
    
    Returns:
        tuple of (bin_edges, bin_counts)
    """
    min_size = min(items)
    max_size = max(items)
    
    # Auto-calculate number of classes if not specified
    if num_classes is None:
        # Use Sturges' rule: k = ceil(log2(n) + 1)
        num_classes = int(np.ceil(np.log2(len(items)) + 1))
        # Cap between 10 and 50 classes for readability
        num_classes = max(10, min(50, num_classes))
    
    # Create bins
    bins = np.linspace(min_size, max_size, num_classes + 1)
    counts, edges = np.histogram(items, bins=bins)
    
    return edges, counts


def plot_enhanced_results(csv_path, output_path=None):
    """
    Create enhanced visualization with vertical layout matching original script:
    1. Item size distribution (if items available)
    2. DNF performance vs swaps/permutations with median and quartile lines
    3. Distribution of DNF results (as % of N/2) with dynamic size classes
    
    Args:
        csv_path: path to CSV file
        output_path: path to save PNG (default: auto-generate)
    
    Returns:
        path to saved PNG file
    """
    print(f"\nProcessing: {csv_path}")
    
    # Read data
    data = read_csv_data(csv_path)
    metadata = data['metadata']
    items = data['items']
    results = data['results']
    
    num_items = metadata['num_items']
    optimal = num_items / 2  # N/2 is the optimal coverage
    
    # Determine experiment type and set appropriate labels
    exp_type = metadata['experiment_type']
    is_permutation = exp_type == 'permutation'
    is_throwbin = exp_type == 'throwbin'
    
    if is_throwbin:
        x_label = 'Run Number'
        x_key = 'run_id'
        strategy_name = 'ThrowBin'
    elif is_permutation:
        x_label = 'Permutation Number'
        x_key = 'permutation_num'
        strategy_name = 'DNF'
    else:
        x_label = 'Number of Swaps'
        x_key = 'swaps'
        strategy_name = 'DNF'
    
    # Create figure - vertical layout (3, 1) to match original script
    has_items = items is not None
    if has_items:
        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 14))
    else:
        fig, (ax2, ax3) = plt.subplots(2, 1, figsize=(12, 10))
    
    # --- PLOT 1: Item Size Distribution (if available) ---
    if has_items:
        n_bins_hist = min(50, len(items) // 10) if len(items) > 50 else 20
        ax1.hist(items, bins=n_bins_hist, color='steelblue', edgecolor='black', alpha=0.7)
        
        # Add reference line for uniform distribution
        uniform_expected = len(items) / n_bins_hist
        ax1.axhline(y=uniform_expected, color='r', linestyle='--', alpha=0.7, 
                   label=f'Expected if Uniform ({uniform_expected:.1f})')
        
        ax1.set_xlabel('Item Size', fontsize=12)
        ax1.set_ylabel('Frequency', fontsize=12)
        ax1.set_title(f'Item Size Distribution ({num_items} items)', fontsize=14)
        ax1.grid(True, alpha=0.3, axis='y')
        ax1.legend()
        
        # Calculate distribution statistics
        min_item = min(items)
        max_item = max(items)
        avg_item = sum(items) / len(items)
        import math
        variance_item = sum((x - avg_item) ** 2 for x in items) / len(items)
        std_item = math.sqrt(variance_item)
        
        dist_stats = f'Min: {min_item:.4f}\nMax: {max_item:.4f}\nAvg: {avg_item:.4f}\nStd: {std_item:.4f}'
        ax1.text(0.98, 0.98, dist_stats, transform=ax1.transAxes, fontsize=10,
                verticalalignment='top', horizontalalignment='left',
                bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.5))
    
    # --- PLOT 2: Strategy Performance vs X-axis with Median and Quartiles ---
    x_values = [r[x_key] for r in results]
    bins_filled = [r['bins_filled'] for r in results]
    
    # Plot the raw bins_filled data
    ax2.plot(x_values, bins_filled, 'b-', linewidth=0.5, alpha=0.7, label=f'{strategy_name} Bins Covered')
    ax2.scatter(x_values, bins_filled, s=1, c='blue', alpha=0.5)
    
    # Calculate statistics for bins_filled
    median_bins = np.median(bins_filled)
    q1_bins = np.percentile(bins_filled, 25)
    q3_bins = np.percentile(bins_filled, 75)
    min_bins = min(bins_filled)
    max_bins = max(bins_filled)
    avg_bins = sum(bins_filled) / len(bins_filled)
    import math
    variance_bins = sum((x - avg_bins) ** 2 for x in bins_filled) / len(bins_filled)
    std_bins = math.sqrt(variance_bins)
    
    # Add median line (solid, thin continuous)
    ax2.axhline(median_bins, color='red', linestyle='-', linewidth=1.5, alpha=0.8, label=f'Median: {median_bins:.0f}')
    
    # Add Q1 and Q3 lines (dashed - lines with gaps)
    ax2.axhline(q1_bins, color='red', linestyle='--', linewidth=1.5, alpha=0.6, label=f'Q1: {q1_bins:.0f}')
    ax2.axhline(q3_bins, color='red', linestyle='--', linewidth=1.5, alpha=0.6, label=f'Q3: {q3_bins:.0f}')
    
    ax2.set_xlabel(x_label, fontsize=12)
    ax2.set_ylabel(f'Bins Covered ({strategy_name})', fontsize=12)
    if is_throwbin:
        ax2.set_title(f'{strategy_name} Strategy Performance\n(Bins Covered vs {x_label})', fontsize=14)
    else:
        title_type = 'Permutations' if is_permutation else 'Swaps'
        ax2.set_title(f'{strategy_name} Strategy Performance with Random {title_type}\n(Bins Covered vs {x_label})', fontsize=14)
    ax2.grid(True, alpha=0.3)
    ax2.legend()
    
    stats_text = f'Min: {min_bins}\nMax: {max_bins}\nAvg: {avg_bins:.2f}\nStd: {std_bins:.2f}'
    ax2.text(0.98, 0.02, stats_text, transform=ax2.transAxes, fontsize=10,
            verticalalignment='bottom', horizontalalignment='left',
            bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.5))
    
    # --- PLOT 3: Distribution of Results (as % of N/2) ---
    # Convert bins_filled to percentage of N/2
    results_pct = [(bins / optimal) * 100 for bins in bins_filled]
    
    # Calculate median and quartiles for the percentage results
    median_pct = (median_bins / optimal) * 100
    q1_pct = (q1_bins / optimal) * 100
    q3_pct = (q3_bins / optimal) * 100
    
    # Create dynamic size classes for percentage results
    num_classes = min(20, len(set(results_pct)))
    if num_classes == 0:
        num_classes = 20
    
    class_min = min(results_pct)
    class_max = max(results_pct)
    class_width = (class_max - class_min) / num_classes if class_max > class_min else 1
    
    # Create class boundaries
    class_edges = [class_min + i * class_width for i in range(num_classes + 1)]
    
    # Count items in each class
    counts = [0] * num_classes
    for pct in results_pct:
        if pct == class_max:
            counts[-1] += 1
        else:
            class_idx = int((pct - class_min) / class_width)
            if 0 <= class_idx < num_classes:
                counts[class_idx] += 1
    
    # Create x positions and labels for bars
    x_positions = range(num_classes)
    
    # Plot histogram
    ax3.bar(x_positions, counts, color='coral', edgecolor='black', alpha=0.7)
    
    # Add vertical lines for median and quartiles
    # Convert percentage values to x-axis positions
    if class_max > class_min:
        median_x_pos = (median_pct - class_min) / class_width - 0.5
        q1_x_pos = (q1_pct - class_min) / class_width - 0.5
        q3_x_pos = (q3_pct - class_min) / class_width - 0.5
        
        ax3.axvline(median_x_pos, color='red', linestyle='-', linewidth=1.5, alpha=0.8, label=f'Median: {median_pct:.2f}%')
        ax3.axvline(q1_x_pos, color='red', linestyle='--', linewidth=1.5, alpha=0.6, label=f'Q1: {q1_pct:.2f}%')
        ax3.axvline(q3_x_pos, color='red', linestyle='--', linewidth=1.5, alpha=0.6, label=f'Q3: {q3_pct:.2f}%')
    
    # Create x-axis labels showing percentage ranges with more precision
    labels = [f'{class_edges[i]:.2f}' for i in range(num_classes)]
    ax3.set_xticks(x_positions)
    ax3.set_xticklabels(labels, rotation=45, ha='right', fontsize=8)
    
    ax3.set_xlabel(f'{strategy_name} Result (% of N/2)', fontsize=12)
    ax3.set_ylabel('Frequency', fontsize=12)
    ax3.set_title(f'Distribution of {strategy_name} Results (Size Classes)', fontsize=14)
    ax3.grid(True, alpha=0.3, axis='y')
    ax3.legend()
    
    # Add statistics text box
    range_text = f'Classes: {num_classes}\nRange: [{class_min:.2f}%, {class_max:.2f}%]'
    ax3.text(0.98, 0.98, range_text, transform=ax3.transAxes, fontsize=10,
            verticalalignment='top', horizontalalignment='left',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    # Overall title
    if is_throwbin:
        fig.suptitle(f'{strategy_name} analiza - N={num_items}', 
                     fontsize=16, fontweight='bold')
    else:
        experiment_type = 'Permutation' if is_permutation else 'Swap'
        fig.suptitle(f'{strategy_name} analiza ({experiment_type} Mode) - N={num_items}', 
                     fontsize=16, fontweight='bold')
    
    plt.tight_layout(rect=[0, 0, 1, 0.98])
    
    # Generate output path if not provided
    if output_path is None:
        base_name = os.path.basename(csv_path).replace('.csv', '')
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Create graphs directory if it doesn't exist
        csv_dir = os.path.dirname(csv_path)
        graphs_dir = os.path.join(csv_dir, 'graphs')
        os.makedirs(graphs_dir, exist_ok=True)
        
        output_path = os.path.join(graphs_dir, f"{base_name}_enhanced_{timestamp}.png")
    
    # Save figure
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"Saved: {output_path}")
    
    plt.close()
    
    return output_path


def main():
    """Main entry point for CSV analysis script."""
    if len(sys.argv) < 2:
        print("Usage: python3 analyze_csv_results.py <csv_file> [csv_file2 ...]")
        print("\nExamples:")
        print("  python3 analyze_csv_results.py data/true_uniform_dnf_results_10000items_*.csv")
        print("  python3 analyze_csv_results.py data/*.csv")
        sys.exit(1)
    
    # Get CSV files from arguments
    csv_files = sys.argv[1:]
    
    # Expand wildcards
    import glob
    expanded_files = []
    for pattern in csv_files:
        matches = glob.glob(pattern)
        if matches:
            expanded_files.extend(matches)
        else:
            # No wildcard match, treat as literal filename
            if os.path.exists(pattern):
                expanded_files.append(pattern)
            else:
                print(f"Warning: File not found: {pattern}")
    
    if not expanded_files:
        print("Error: No CSV files found")
        sys.exit(1)
    
    # Process each CSV file
    print(f"\n{'='*70}")
    print(f"ENHANCED CSV ANALYSIS")
    print(f"{'='*70}")
    print(f"Files to process: {len(expanded_files)}")
    print(f"{'='*70}\n")
    
    output_files = []
    for csv_path in expanded_files:
        try:
            output_path = plot_enhanced_results(csv_path)
            output_files.append(output_path)
        except Exception as e:
            print(f"Error processing {csv_path}: {e}")
    
    # Summary
    print(f"\n{'='*70}")
    print(f"SUMMARY")
    print(f"{'='*70}")
    print(f"Processed: {len(output_files)} / {len(expanded_files)} files")
    print(f"Output files:")
    for path in output_files:
        print(f"  - {path}")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
