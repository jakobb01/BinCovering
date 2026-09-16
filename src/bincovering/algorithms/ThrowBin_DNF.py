"""
ThrowBin_DNF Strategy for Bin Covering Problem.

This strategy maintains exactly 10 active bins at all times:
- Always has 10 bins open (constant)
- Randomly selects one of the 10 bins for each item
- When a bin is covered (≥1.0), it's replaced with a new empty bin
- Counts total bins covered throughout the process

The items are expected to be sorted in descending order (largest first).
"""
import sys
import os
import random

from bincovering.algorithms.base import Strategy

BIN_COVER_LOAD = 1.0  # max bin capacity (threshold for "covered")
NUM_ACTIVE_BINS = 10  # constant number of active bins


class ThrowBinDNFStrategy(Strategy):
    """
    ThrowBin_DNF Strategy:
    - Maintains exactly 10 active bins at all times
    - For each item, randomly selects one of the 10 bins and places the item
    - When a bin is covered, it's replaced with a new empty bin
    - Counts total bins covered throughout the process
    """
    
    def __init__(self, filename=None, path="./data/"):
        """
        Args:
            filename: optional log filename
            path: path for log files
        """
        super().__init__(filename, path)
        self.gen = None
        self.bins = []  # List of bin loads (always 10 bins)
        self.num_active_bins = NUM_ACTIVE_BINS  # Always 10
        self.covered_bins = 0  # Total bins covered (can exceed 10)
    
    def start(self, generator):
        """
        Start strategy with an external generator.
        
        Args:
            generator: must implement .next() that raises StopIteration when done
        """
        self.gen = generator
        
        # Initialize 10 bins with zero load
        self.bins = [0.0] * NUM_ACTIVE_BINS
        self.covered_bins = 0
        
        if self.file:
            self.file.write(f"Starting ThrowBin_DNF Strategy with {NUM_ACTIVE_BINS} active bins (constant)\n")
        
        return f"Strategy started with {NUM_ACTIVE_BINS} bins"
    
    def next(self):
        """Process the next item using ThrowBin_DNF logic."""
        try:
            item = self.gen.next()
        except StopIteration:
            return None  # End of stream
        
        if self.file:
            self.file.write(f"Processing item: {item}\n")
        
        # Randomly select one of the 10 active bins
        selected_idx = random.randint(0, NUM_ACTIVE_BINS - 1)
        
        # Add item to the selected bin
        self.bins[selected_idx] += item
        
        if self.file:
            self.file.write(f"Placed item {item} in bin {selected_idx}, new load: {self.bins[selected_idx]}\n")
        
        # Check if the bin is now covered
        if self.bins[selected_idx] >= BIN_COVER_LOAD:
            self.covered_bins += 1
            
            # Replace the covered bin with a new empty bin
            self.bins[selected_idx] = 0.0
            
            if self.file:
                self.file.write(f"Bin {selected_idx} is now covered! Replaced with new empty bin. Total covered: {self.covered_bins}\n")
            
            return f"Bin {selected_idx} covered after adding {item}. Replaced with new bin. Total covered: {self.covered_bins}"
        
        return f"Added {item} to bin {selected_idx}, load: {self.bins[selected_idx]}"
    
    def stop(self):
        """Close log and report result."""
        if self.file:
            self.file.write(f"\n--- Final Statistics ---\n")
            self.file.write(f"Active bins (constant): {NUM_ACTIVE_BINS}\n")
            self.file.write(f"Total bins covered: {self.covered_bins}\n")
            self.file.write(f"Covered/Active ratio: {self.covered_bins / NUM_ACTIVE_BINS:.2f}\n")
            self.file.close()
        
        return f"ThrowBin_DNF strategy stopped. Total bins covered: {self.covered_bins} (with {NUM_ACTIVE_BINS} active bins)"
    
    def get_covered_bins(self):
        """Return the total number of bins covered."""
        return self.covered_bins
    
    def get_active_bins(self):
        """Return the number of active bins (always 10)."""
        return NUM_ACTIVE_BINS
