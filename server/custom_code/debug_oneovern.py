"""Debug script to trace what happens with OneOverN sequence."""
import sys
import os
from bincovering.algorithms.AdaptiveBin import AdaptiveBinStrategy
from bincovering.generators.OneOverN import OneOverNGenerator


def trace_strategy(n_items, max_trace=30):
    """Run strategy and trace first max_trace items."""
    gen = OneOverNGenerator(path="/tmp/")
    gen.start(n_items)
    
    items = gen._numbers  # Get the generated items
    
    print(f"Total items: {len(items)}")
    print(f"First 10 items: {[f'{x:.4f}' for x in items[:10]]}")
    print(f"Last 10 items: {[f'{x:.4f}' for x in items[-10:]]}")
    print(f"Sum of items: {sum(items):.4f}")
    print(f"OPT: {n_items // 2}")
    print()
    
    # Manually step through
    strat = AdaptiveBinStrategy()
    strat.gen = gen
    strat.bins = []
    strat.items_received = 0
    strat.covered_bins = 0
    strat.active_bin_indices = []
    
    gen._index = 0  # Reset generator
    
    for i in range(min(len(items), max_trace)):
        try:
            item = gen.next()
        except StopIteration:
            break
        
        strat.items_received += 1
        target_bins = strat._calculate_target_bins()
        
        # Open bins if needed
        while len(strat.bins) < target_bins:
            new_idx = len(strat.bins)
            strat.bins.append(0.0)
            strat.active_bin_indices.append(new_idx)
        
        # Ensure at least one active bin
        if not strat.active_bin_indices:
            new_idx = len(strat.bins)
            strat.bins.append(0.0)
            strat.active_bin_indices.append(new_idx)
        
        # Select bin
        selected = strat._select_best_bin(item)
        old_load = strat.bins[selected]
        strat.bins[selected] += item
        new_load = strat.bins[selected]
        
        # Check if covered
        was_covered = new_load >= 1.0
        if was_covered and selected in strat.active_bin_indices:
            strat.active_bin_indices.remove(selected)
            strat.covered_bins += 1
        
        print(f"Item {i+1}: {item:.4f} -> Bin {selected} ({old_load:.4f} + {item:.4f} = {new_load:.4f})"
              f" {'COVERED!' if was_covered else ''}")
        print(f"  Target: {target_bins}, Open: {len(strat.bins)}, Active: {len(strat.active_bin_indices)}, Covered: {strat.covered_bins}")
        print(f"  Loads: {[f'{x:.3f}' for x in strat.bins[:min(10, len(strat.bins))]]}")
        print()
    
    # Finish remaining items
    while True:
        try:
            item = gen.next()
        except StopIteration:
            break
        
        strat.items_received += 1
        target_bins = strat._calculate_target_bins()
        
        while len(strat.bins) < target_bins:
            new_idx = len(strat.bins)
            strat.bins.append(0.0)
            strat.active_bin_indices.append(new_idx)
        
        if not strat.active_bin_indices:
            new_idx = len(strat.bins)
            strat.bins.append(0.0)
            strat.active_bin_indices.append(new_idx)
        
        selected = strat._select_best_bin(item)
        strat.bins[selected] += item
        
        if strat.bins[selected] >= 1.0 and selected in strat.active_bin_indices:
            strat.active_bin_indices.remove(selected)
            strat.covered_bins += 1
    
    gen.stop()
    
    print("="*60)
    print(f"FINAL: {strat.covered_bins} covered out of {len(strat.bins)} bins")
    print(f"Ratio vs OPT ({n_items//2}): {strat.covered_bins / (n_items//2):.2%}")
    
    # Show bin distribution
    loads = sorted(strat.bins, reverse=True)
    print(f"\nTop 10 bin loads: {[f'{x:.3f}' for x in loads[:10]]}")
    print(f"Bottom 10 bin loads: {[f'{x:.3f}' for x in loads[-10:]]}")


if __name__ == "__main__":
    print("="*60)
    print("TRACING OneOverN with N=20")
    print("="*60)
    trace_strategy(20, max_trace=30)
