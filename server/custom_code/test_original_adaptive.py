import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../strategies/')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../generate_bins/')))

from AdaptiveBin import AdaptiveBinStrategy
from OneOverN import OneOverNGenerator

# Standard runner
def run():
    N = 1000
    print(f"Testing Original AdaptiveBin (Random) on OneOverN (N={N})")
    
    # Create generator
    gen_inst = OneOverNGenerator(path="/tmp")
    gen_inst.start(N)
    items = []
    while True:
        try:
           items.append(gen_inst.next())
        except StopIteration:
            break
    gen_inst.stop()
    
    # Wrapper
    class SeqGen:
        def __init__(self, items): self.items=items; self.idx=0
        def next(self):
            if self.idx<len(self.items):
                val = self.items[self.idx]; self.idx+=1; return val
            else: raise StopIteration
            
    gen = SeqGen(items)
    
    strat = AdaptiveBinStrategy()
    strat.start(gen)
    
    while True:
        if strat.next() is None: break
        
    print(f"Covered: {strat.get_covered_bins()}")
    print(f"Total Opened: {strat.get_total_bins()}")

if __name__ == "__main__":
    run()
