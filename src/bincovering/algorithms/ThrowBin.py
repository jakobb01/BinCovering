"""
ThrowBin Strategy for Bin Covering Problem.

This strategy opens N/2 bins at the start and randomly selects one to place each item.
When a bin reaches the max_cover threshold (1.0), it is counted as covered.

The items are expected to be sorted in descending order (largest first).
"""
import sys
import os
import random

from bincovering.algorithms.base import Strategy

BIN_COVER_LOAD = 1.0  # max bin capacity (threshold for "covered")


class ThrowBinStrategy(Strategy):
    """
    ThrowBin Strategy:
    - Opens a configurable ratio of N bins at the start (default 50% = N/2)
    - For each item, randomly selects one of the non-covered bins and places the item
    - Counts bins that reach or exceed BIN_COVER_LOAD as "covered"
    """
    
    def __init__(self, filename=None, path="./data/", bin_ratio=0.5):
        """
        Args:
            filename: optional log filename
            path: path for log files
            bin_ratio: ratio of N to use as number of bins (default 0.5 = 50% = N/2)
                       e.g., 0.3 means open 30% of N bins, 0.5 means 50% (N/2)
        """
        super().__init__(filename, path)
        self.gen = None
        self.bins = []  # List of bin loads
        self.num_bins = 0
        self.covered_bins = 0
        self.active_bins = []  # Indices of bins that are still open (not covered)
        self.bin_ratio = bin_ratio
    
    def start(self, generator, num_items, bin_ratio=None):
        """
        Start strategy with an external generator.
        
        Args:
            generator: must implement .next() that raises StopIteration when done
            num_items: total number of items (N)
            bin_ratio: optional override for bin ratio (default uses constructor value)
        """
        self.gen = generator
        if bin_ratio is not None:
            self.bin_ratio = bin_ratio
        self.num_bins = int(num_items * self.bin_ratio)
        
        # Initialize all bins with zero load
        self.bins = [0.0] * self.num_bins
        self.active_bins = list(range(self.num_bins))  # All bins are active initially
        self.covered_bins = 0
        
        if self.file:
            self.file.write(f"Starting ThrowBin Strategy with {self.num_bins} bins\n")
        
        return f"Strategy started with {self.num_bins} bins"
    
    def next(self):
        """Process the next item using ThrowBin logic."""
        try:
            item = self.gen.next()
        except StopIteration:
            return None  # End of stream
        
        if self.file:
            self.file.write(f"Processing item: {item}\n")
        
        # If no active bins left, we can't place the item
        if not self.active_bins:
            if self.file:
                self.file.write(f"No active bins left, item {item} discarded\n")
            return f"No bins available for item {item}"
        
        # Randomly select one of the active (non-covered) bins
        selected_idx = random.choice(self.active_bins)
        
        # Add item to the selected bin
        self.bins[selected_idx] += item
        
        if self.file:
            self.file.write(f"Placed item {item} in bin {selected_idx}, new load: {self.bins[selected_idx]}\n")
        
        # Check if the bin is now covered
        if self.bins[selected_idx] >= BIN_COVER_LOAD:
            self.covered_bins += 1
            self.active_bins.remove(selected_idx)
            
            if self.file:
                self.file.write(f"Bin {selected_idx} is now covered! Total covered: {self.covered_bins}\n")
            
            return f"Bin {selected_idx} covered after adding {item}. Covered bins: {self.covered_bins}"
        
        return f"Added {item} to bin {selected_idx}, load: {self.bins[selected_idx]}"
    
    def stop(self):
        """Close log and report result."""
        if self.file:
            self.file.write(f"\n--- Final Statistics ---\n")
            self.file.write(f"Total bins: {self.num_bins}\n")
            self.file.write(f"Covered bins: {self.covered_bins}\n")
            self.file.write(f"Coverage rate: {self.covered_bins / self.num_bins * 100:.2f}%\n")
            self.file.close()
        
        return f"ThrowBin strategy stopped. Covered bins: {self.covered_bins}/{self.num_bins}"
    
    def get_covered_bins(self):
        """Return the number of covered bins."""
        return self.covered_bins
    
    def get_total_bins(self):
        """Return the total number of bins."""
        return self.num_bins
