"""
Test script for AdaptiveBin strategy with different generators.
Tests worst-case scenarios and compares against known OPT.
"""
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../generate_bins/')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../strategies/')))

from UniformGenerator import UniformGenerator
from OneOverN import OneOverNGenerator
from OptimalUniformGenerator import OptimalUniformGenerator
from BigItemsGenerator import BigItemsGenerator
from AdaptiveBin import AdaptiveBinStrategy


class InMemoryGenerator:
    """Simple generator from a list of items."""
    def __init__(self, items):
        self.items = items
        self.idx = 0
    
    def start(self):
        self.idx = 0
        return f"InMemoryGenerator ready with {len(self.items)} items"
    
    def next(self):
        if self.idx < len(self.items):
            item = self.items[self.idx]
            self.idx += 1
            return item
        raise StopIteration()
    
    def stop(self):
        return f"Served {self.idx} items"


def run_strategy(items):
    """Run AdaptiveBin on items and return covered bins."""
    gen = InMemoryGenerator(items)
    gen.start()
    
    strat = AdaptiveBinStrategy()
    strat.start(gen)
    
    while True:
        result = strat.next()
        if result is None:
            break
    
    strat.stop()
    return strat.get_covered_bins(), strat.get_total_bins()


def test_optimal_uniform():
    """Test with OptimalUniformGenerator where OPT is known exactly."""
    print("\n" + "="*70)
    print("TEST 1: OptimalUniform Generator (Known OPT)")
    print("="*70)
    
    for opt_bins in [100, 500, 1000]:
        gen = OptimalUniformGenerator()
        gen.start(opt_bins)
        
        items = gen.get_items()
        opt = gen.get_optimal_bins()
        gen.stop()
        
        covered, total = run_strategy(items)
        ratio = covered / opt if opt > 0 else 0
        
        print(f"\nOPT={opt_bins}: {len(items)} items, Sum={sum(items):.2f}")
        print(f"  Result: {covered}/{opt} bins covered = {ratio:.2%}")


def test_oneovern():
    """Test with OneOverN where OPT = N/2."""
    print("\n" + "="*70)
    print("TEST 2: OneOverN Generator (OPT = N/2)")
    print("="*70)
    
    for n_items in [100, 1000, 10000]:
        gen = OneOverNGenerator()
        gen.start(n_items)
        
        items = []
        while True:
            try:
                items.append(gen.next())
            except StopIteration:
                break
        gen.stop()
        
        opt = n_items // 2
        covered, total = run_strategy(items)
        ratio = covered / opt if opt > 0 else 0
        
        print(f"\nN={n_items}: OPT={opt}")
        print(f"  Result: {covered}/{opt} bins covered = {ratio:.2%}")


def test_big_items_worst_case():
    """Test WORST CASE: all items just above 0.5."""
    print("\n" + "="*70)
    print("TEST 3: Big Items (Worst Case for Spreading Strategy)")
    print("="*70)
    
    # Test 1: Items exactly 0.51 - two items cover a bin (1.02)
    print("\n--- All items = 0.51 (two items cover a bin) ---")
    for n_items in [10, 100, 1000]:
        gen = BigItemsGenerator(min_size=0.51, max_size=0.51)
        gen.start(n_items)
        
        items = gen.get_items()
        opt = gen.get_optimal_bins()
        total_sum = gen.get_total_sum()
        gen.stop()
        
        covered, total_bins = run_strategy(items)
        ratio = covered / opt if opt > 0 else 0
        
        print(f"\nN={n_items}: Sum={total_sum:.2f}, OPT={opt}")
        print(f"  Result: {covered}/{opt} bins covered = {ratio:.2%}")
        print(f"  Total bins opened: {total_bins}")
    
    # Test 2: Items in range [0.51, 0.6] - still pairwise coverable
    print("\n--- Items in [0.51, 0.60] ---")
    for n_items in [100, 1000]:
        gen = BigItemsGenerator(min_size=0.51, max_size=0.60)
        gen.start(n_items)
        
        items = gen.get_items()
        opt = gen.get_optimal_bins()
        total_sum = gen.get_total_sum()
        gen.stop()
        
        covered, total_bins = run_strategy(items)
        ratio = covered / opt if opt > 0 else 0
        
        print(f"\nN={n_items}: Sum={total_sum:.2f}, OPT={opt}")
        print(f"  Result: {covered}/{opt} bins covered = {ratio:.2%}")
    
    # Test 3: Items around 0.67 - three items needed to cover (0.67*3 = 2.01)
    print("\n--- Items = 0.34 (three items cover a bin, 1.02) ---")
    # Note: 0.34 is < 0.5, so our algorithm treats it as "small"
    # Let's use 0.67 instead - two items = 1.34 covers, three items = 2.01 covers two bins
    
    # Actually, let's test items of 0.4 - these are "small" by our definition
    # Two 0.4 items = 0.8, three = 1.2 (covers 1), five = 2.0 (covers 2)
    print("\n--- Items = 0.40 (small items, five cover 2 bins) ---")
    for n_items in [100, 1000]:
        items = [0.40] * n_items
        opt = int(sum(items))  # floor of sum
        
        covered, total_bins = run_strategy(items)
        ratio = covered / opt if opt > 0 else 0
        
        print(f"\nN={n_items}: Sum={sum(items):.2f}, OPT={opt}")
        print(f"  Result: {covered}/{opt} bins covered = {ratio:.2%}")


def test_mixed_worst_case():
    """Test a deliberately adversarial sequence."""
    print("\n" + "="*70)
    print("TEST 4: Adversarial Sequences")
    print("="*70)
    
    # Test: Alternating 0.51 items in worst order
    # Our algorithm spreads big items, so if all are 0.51, none pair up
    print("\n--- Sequence of 0.51 items (sorted descending) ---")
    items = [0.51] * 100
    opt = int(sum(items))  # 51
    
    covered, total_bins = run_strategy(items)
    ratio = covered / opt if opt > 0 else 0
    
    print(f"N=100: Sum={sum(items):.2f}, OPT={opt}")
    print(f"  Result: {covered}/{opt} bins covered = {ratio:.2%}")
    print(f"  Total bins opened: {total_bins}")
    
    # What if we had a smarter ordering? Let's test random permutation
    print("\n--- Same items but randomly permuted ---")
    import random
    for seed in [1, 2, 3]:
        random.seed(seed)
        shuffled = items.copy()
        random.shuffle(shuffled)
        
        covered, total_bins = run_strategy(shuffled)
        ratio = covered / opt if opt > 0 else 0
        print(f"  Seed {seed}: {covered}/{opt} = {ratio:.2%}")


def test_boundary_cases():
    """Test items exactly at the 0.5 boundary."""
    print("\n" + "="*70)
    print("TEST 5: Boundary Cases (items near 0.5)")
    print("="*70)
    
    # Items exactly 0.5 - treated as "small" by our algorithm
    print("\n--- Items = 0.50 exactly (small by our definition) ---")
    items = [0.50] * 100
    opt = int(sum(items))  # 50
    
    covered, total_bins = run_strategy(items)
    ratio = covered / opt if opt > 0 else 0
    
    print(f"N=100: Sum={sum(items):.2f}, OPT={opt}")
    print(f"  Result: {covered}/{opt} bins covered = {ratio:.2%}")
    
    # Items 0.501 - treated as "big" by our algorithm
    print("\n--- Items = 0.501 (big by our definition) ---")
    items = [0.501] * 100
    opt = int(sum(items))  # 50
    
    covered, total_bins = run_strategy(items)
    ratio = covered / opt if opt > 0 else 0
    
    print(f"N=100: Sum={sum(items):.2f}, OPT={opt}")
    print(f"  Result: {covered}/{opt} bins covered = {ratio:.2%}")
    print(f"  Total bins opened: {total_bins}")


if __name__ == "__main__":
    test_optimal_uniform()
    test_oneovern()
    test_big_items_worst_case()
    test_mixed_worst_case()
    test_boundary_cases()
    
    print("\n" + "="*70)
    print("ALL TESTS COMPLETED")
    print("="*70)
