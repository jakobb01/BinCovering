"""
AdaptiveBinCovered Strategy for Bin Covering Problem.

This strategy opens bins based on the number of CORED bins, rather than items received.
This helps react to sequences with very large items (which cover bins quickly).

Algorithm:
1. Start with 'initial_bins' active bins.
2. Randomly select an active bin to place the item.
3. When a bin reaches the coverage threshold (>=1.0):
   - It is marked "covered" and removed from active set.
   - We calculate new Target Total Bins based on multiplier.
   - We open (Target - Current) new bins.

Formula:
Target Total Bins = ceil(Covered Bins * Multiplier) OR at least Covered + 1
"""
import sys
import os
import random
import math

from bincovering.algorithms.base import Strategy

BIN_COVER_LOAD = 1.0

class AdaptiveBinCoveredStrategy(Strategy):
    """
    AdaptiveBinCovered Strategy:
    - Opens bins based on COVERED count * Multiplier.
    - Randomly selects among open (active) bins.
    """
    
    def __init__(self, filename=None, path="./data/", multiplier=2.0, initial_bins=1):
        super().__init__(filename, path)
        self.gen = None
        self.bins = []  # List of bin loads
        self.items_received = 0
        self.covered_bins = 0
        self.active_bin_indices = []
        
        self.multiplier = multiplier
        self.initial_bins = initial_bins
    
    def _open_new_bins(self, count):
        for _ in range(count):
            new_bin_idx = len(self.bins)
            self.bins.append(0.0)
            self.active_bin_indices.append(new_bin_idx)
            if self.file:
                self.file.write(f"Opened new bin {new_bin_idx}. Total bins: {len(self.bins)}\n")

    def _update_bins_based_on_formula(self):
        """
        Ensure total bins >= ceil(covered * multiplier)
        And ensure at least 1 active bin.
        """
        target_total = math.ceil(self.covered_bins * self.multiplier)
        
        # Ensure at least 1 active bin (Total > Covered)
        if target_total <= self.covered_bins:
            target_total = self.covered_bins + 1
            
        current_total = len(self.bins)
        needed = target_total - current_total
        
        if needed > 0:
            if self.file:
                self.file.write(f"Formula update: Covered={self.covered_bins}, Mult={self.multiplier}, Target={target_total}, Current={current_total}, Opening={needed}\\n")
            self._open_new_bins(needed)

    def start(self, generator):
        self.gen = generator
        self.bins = []
        self.items_received = 0
        self.covered_bins = 0
        self.active_bin_indices = []
        
        if self.file:
            self.file.write(f"Starting AdaptiveBinCovered Strategy\\n")
            self.file.write(f"Initial bins: {self.initial_bins}, Multiplier: {self.multiplier}\\n")
        
        # Open initial bins
        self._open_new_bins(self.initial_bins)
        
        return "Strategy started"
    
    def next(self):
        try:
            item = self.gen.next()
        except StopIteration:
            return None
        
        self.items_received += 1
        
        if self.file:
            self.file.write(f"\\n--- Item #{self.items_received}: {item:.6f} ---\\n")
            self.file.write(f"Active: {len(self.active_bin_indices)}, Covered: {self.covered_bins}\\n")
        
        # Safety: If we somehow have no active bins
        if not self.active_bin_indices:
            self._open_new_bins(1)
            if self.file:
                self.file.write("Emergency bin opened (0 active).\\n")
        
        # Random logic
        selected_idx = random.choice(self.active_bin_indices)
        
        self.bins[selected_idx] += item
        
        if self.file:
            self.file.write(f"Placed in bin {selected_idx}, new load: {self.bins[selected_idx]:.6f}\\n")
        
        # Check coverage
        if self.bins[selected_idx] >= BIN_COVER_LOAD:
            self.covered_bins += 1
            self.active_bin_indices.remove(selected_idx)
            
            if self.file:
                self.file.write(f"Bin {selected_idx} COVERED! Total covered: {self.covered_bins}\\n")
            
            # TRIGGER FORMULA UPDATE
            self._update_bins_based_on_formula()
            
            return f"Bin {selected_idx} covered. Total covered: {self.covered_bins}"
            
        return f"Added {item:.6f} to bin {selected_idx}, load: {self.bins[selected_idx]:.6f}"

    def stop(self):
        if self.file:
            self.file.write(f"\n\n========== FINAL STATISTICS ==========\n")
            self.file.write(f"Total items received: {self.items_received}\n")
            self.file.write(f"Total bins opened: {len(self.bins)}\n")
            self.file.write(f"Covered bins: {self.covered_bins}\n")
            self.file.write(f"Active bins remaining: {len(self.active_bin_indices)}\n")
            if len(self.bins) > 0:
                self.file.write(f"Coverage rate: {self.covered_bins / len(self.bins) * 100:.2f}%\n")
            self.file.close()
        return f"Stopped. Items: {self.items_received}, Covered: {self.covered_bins}"

    def get_covered_bins(self):
        return self.covered_bins
    
    def get_total_bins(self):
        return len(self.bins)
    
    def get_items_received(self):
        return self.items_received
