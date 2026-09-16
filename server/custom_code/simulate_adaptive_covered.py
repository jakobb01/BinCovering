
import sys
import os
import random

# Add paths

from bincovering.generators.BigItemsGenerator import BigItemsGenerator
from bincovering.generators.UniformGenerator import UniformGenerator
from bincovering.generators.OneOverN import OneOverNGenerator
from bincovering.algorithms.AdaptiveBinCovered import AdaptiveBinCoveredStrategy

class InMemorySequenceGenerator:
    def __init__(self, items):
        self._items = items.copy()
        self._index = 0
    
    def next(self):
        if self._index < len(self._items):
            item = self._items[self._index]
            self._index += 1
            return item
        else:
            raise StopIteration("No more items")


def run_test(generator_class, items_count, multiplier, initial_bins=1, runs=5):
    print(f"\n--- Testing {generator_class.__name__} (N={items_count}) ---")
    print(f"Strategy: Start {initial_bins}, Multiplier {multiplier}")
    
    total_covered = 0
    total_opened = 0
    
    for i in range(runs):
        # Create items
        if generator_class == BigItemsGenerator:
             gen_inst = BigItemsGenerator(path="/tmp") # dummy path
             gen_inst.start(items_count)
             items = gen_inst.get_items()
             gen_inst.stop()
        elif generator_class == OneOverNGenerator:
             gen_inst = OneOverNGenerator(path="/tmp")
             gen_inst.start(items_count)
             items = []
             while True:
                try:
                    items.append(gen_inst.next())
                except StopIteration:
                    break
             gen_inst.stop()
        else:
             gen_inst = UniformGenerator(path="/tmp")
             gen_inst.start(items_count)

             items = []
             while True:
                try:
                    items.append(gen_inst.next())
                except StopIteration:
                    break
             gen_inst.stop()
        
        # Use our wrapper to serve items
        gen = InMemorySequenceGenerator(items)
            
        strat = AdaptiveBinCoveredStrategy(multiplier=multiplier, initial_bins=initial_bins)
        strat.start(gen)
        
        while True:
            res = strat.next()
            if res is None:
                break
                
        covered = strat.get_covered_bins()
        opened = strat.get_total_bins()
        total_covered += covered
        total_opened += opened
        # print(f"Run {i+1}: Covered {covered}/{opened}")
        
    avg_covered = total_covered / runs
    avg_opened = total_opened / runs

    print(f"Average Covered: {avg_covered:.1f} | Average Opened: {avg_opened:.1f} | Ratio: {avg_covered/avg_opened:.2f}")

# Test Loop
N = 10000

print("=== SCENARIO 1: BigItems (The problematic case) ===")
# Big items fill bins fast. If we don't open fast enough, we might get stuck or inefficient?
# BigItems essentially allows 2 items to cover a bin (e.g. 0.6 + 0.6 = 1.2). 
# If we have 1000 items, max possible is 500 bins.

# # Test 1: M=1.5
# run_test(BigItemsGenerator, N, multiplier=1.5, initial_bins=1)

# # Test 2: M=2.0
# run_test(BigItemsGenerator, N, multiplier=2.0, initial_bins=1)

# # Test 3: M=2.5
# run_test(BigItemsGenerator, N, multiplier=2.5, initial_bins=1)



print("\n=== SCENARIO 2: Uniform Random (Standard case) ===")
# Uniform items avg 0.5. 2 items per bin. Max 500 bins.

# Test 1: M=1.5
run_test(UniformGenerator, N, multiplier=1.3, initial_bins=1)

# Test 2: M=2.0
run_test(UniformGenerator, N, multiplier=1.4, initial_bins=1)

# Test 3: M=2.5
run_test(UniformGenerator, N, multiplier=1.5, initial_bins=1)


print("\n=== SCENARIO 3: OneOverN (Use N=1000) ===")
# OneOverN: 500 Big (~0.99) then 500 Small (~0.01).
# Optimal: 500 bins.

N=10000
# Test 1: M=1.5
run_test(OneOverNGenerator, N, multiplier=1.2, initial_bins=1)

# Test 2: M=2.0
run_test(OneOverNGenerator, N, multiplier=1.5, initial_bins=1)

# Test 3: M=2.5
run_test(OneOverNGenerator, N, multiplier=1.6, initial_bins=1)

run_test(OneOverNGenerator, N, multiplier=1.8, initial_bins=1)

run_test(OneOverNGenerator, N, multiplier=5, initial_bins=1)