# Example how to run different classes in one main script
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../generate_bins/')))
from ItemGenerator import BinGenerator

def run_generator_example():
    gen = BinGenerator()
    gen.start(20)
    print(gen.next())
    print(gen.next())
    print(gen.stop())

    print("Generated numbers:")
    try:
        while True:
            print(gen.next())
    except StopIteration:
        pass

    print(f"\nBins covered: {gen.stop()}")

run_generator_example()
