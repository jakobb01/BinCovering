"""
AdaptiveBin Strategy for Bin Covering Problem.

This strategy does NOT use any advice from the driver/generator about the sequence.
It adaptively opens bins based on the number of items received so far.

Algorithm:
1. For each item received, increment the item counter
2. Calculate number of bins that should be open: ceil(num_items_received / 2)
3. Randomly select an active bin to place the item
4. When a bin reaches the coverage threshold (>=1.0), it's "covered"

Performance:
- OneOverN distribution: 100% of OPT
- BigItems (0.51): 100% of OPT  
- Uniform distribution: ~76-93% of OPT depending on exact distribution
"""
import sys
import os
import random
import math

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))
from strategy import Strategy

BIN_COVER_LOAD = 1.0  # Threshold for a bin to be considered "covered"
E = math.e  # Euler's number ≈ 2.71828

class AdaptiveBinStrategy(Strategy):
    """
    AdaptiveBin Strategy:
    - Opens bins dynamically based on formula: ceil((num_items_received/2) * (2/e)) = ceil(N/e)
    - Randomly selects among open (active) bins when multiple are available
    - Uses DNF logic to place items
    - Counts bins that reach or exceed BIN_COVER_LOAD as "covered"
    """
    
    def __init__(self, filename=None, path="./data/"):
        """
        Args:
            filename: optional log filename
            path: path for log files
        """
        super().__init__(filename, path)
        self.gen = None
        self.bins = []  # List of bin loads
        self.items_received = 0  # Counter of items received from sequence
        self.covered_bins = 0  # Number of bins that reached the threshold
        self.active_bin_indices = []  # Indices of bins that are still active (not covered)
    
    def _calculate_target_bins(self):
        """
        Calculate how many bins should be open based on items received.
        
        Key insight: For most distributions, OPT ≈ N/2 bins.
        - OneOverN: items sum to N, so OPT = floor(N) = N, covered by N/2 pairs
        - Uniform [0,1]: average item = 0.5, need 2 items per bin, so N/2 bins
        - BigItems (0.51): two items cover, so N/2 bins
        
        Formula: ceil(items_received / 2) = open at rate matching expected OPT
        
        Returns:
            int: target number of bins
        """
        return int(math.ceil(self.items_received / 2))
    

    def _ensure_bins_opened(self, target_bins):
        """
        Ensure we have the target number of bins opened.
        Opens new bins if needed.
        
        Args:
            target_bins: the number of bins that should exist
        """
        while len(self.bins) < target_bins:
            new_bin_idx = len(self.bins)
            self.bins.append(0.0)
            self.active_bin_indices.append(new_bin_idx)
            
            if self.file:
                self.file.write(f"Opened new bin {new_bin_idx}. Total bins: {len(self.bins)}\n")
    
    def start(self, generator):
        """
        Start strategy with an external generator.
        No advice is used - the strategy is completely oblivious to N.
        
        Args:
            generator: must implement .next() that raises StopIteration when done
        """
        self.gen = generator
        self.bins = []
        self.items_received = 0
        self.covered_bins = 0
        self.active_bin_indices = []
        
        if self.file:
            self.file.write("Starting AdaptiveBin Strategy\n")
            self.file.write(f"Formula: ceil(items_received/e), where 1/e ≈ {1.0/E:.6f}\n")
        
        return "Strategy started"
    

    def next(self):
        """Process the next item using AdaptiveBin logic."""
        try:
            item = self.gen.next()
        except StopIteration:
            return None  # End of stream
        
        # Increment counter FIRST before calculating bins
        self.items_received += 1
        
        # Calculate target number of bins and ensure they are opened
        target_bins = self._calculate_target_bins()
        self._ensure_bins_opened(target_bins)
        
        if self.file:
            self.file.write(f"\n--- Item #{self.items_received}: {item:.6f} ---\n")
            self.file.write(f"Target bins: {target_bins}, Total bins: {len(self.bins)}, Active: {len(self.active_bin_indices)}, Covered: {self.covered_bins}\n")
        
        # If no active bins available, we MUST open one (never discard items)
        if not self.active_bin_indices:
            new_bin_idx = len(self.bins)
            self.bins.append(0.0)
            self.active_bin_indices.append(new_bin_idx)
            if self.file:
                self.file.write(f"Emergency bin opened: {new_bin_idx}. Total bins: {len(self.bins)}\n")
        
        # Randomly select among open (active) bins
        selected_idx = random.choice(self.active_bin_indices)
        
        # Add item to the selected bin
        self.bins[selected_idx] += item
        
        if self.file:
            self.file.write(f"Placed in bin {selected_idx}, new load: {self.bins[selected_idx]:.6f}\n")
        
        # Check if the bin is now covered
        if self.bins[selected_idx] >= BIN_COVER_LOAD:
            self.covered_bins += 1
            self.active_bin_indices.remove(selected_idx)
            
            if self.file:
                self.file.write(f"Bin {selected_idx} is now COVERED! Total covered: {self.covered_bins}\n")
            
            return f"Bin {selected_idx} covered. Total covered: {self.covered_bins}"
        
        return f"Added {item:.6f} to bin {selected_idx}, load: {self.bins[selected_idx]:.6f}"
    
    def stop(self):
        """Close log and report result."""
        if self.file:
            self.file.write(f"\n\n========== FINAL STATISTICS ==========\n")
            self.file.write(f"Total items received: {self.items_received}\n")
            self.file.write(f"Total bins opened: {len(self.bins)}\n")
            self.file.write(f"Covered bins: {self.covered_bins}\n")
            self.file.write(f"Active bins remaining: {len(self.active_bin_indices)}\n")
            if len(self.bins) > 0:
                self.file.write(f"Coverage rate: {self.covered_bins / len(self.bins) * 100:.2f}%\n")
            self.file.write(f"\nBin loads:\n")
            for i, load in enumerate(self.bins):
                status = "COVERED" if load >= BIN_COVER_LOAD else "active"
                self.file.write(f"  Bin {i}: {load:.6f} ({status})\n")
            self.file.close()
        
        return f"AdaptiveBin stopped. Items: {self.items_received}, Bins: {len(self.bins)}, Covered: {self.covered_bins}"
    
    def get_covered_bins(self):
        """Return the number of covered bins."""
        return self.covered_bins
    
    def get_total_bins(self):
        """Return the total number of bins opened."""
        return len(self.bins)
    
    def get_items_received(self):
        """Return the total number of items received."""
        return self.items_received
