# Example how to run different classes in one main script
import sys
import datetime
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../generate_bins/')))
from ItemGenerator import BinGenerator
# import DualNextFit.py
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../strategies/')))
from DualNextFit import DNFStrategy
from Harmonic import HarmonicStrategy

def run_custom_dnf_example():
    # Set up generator
    gen = BinGenerator()
    print(gen.start(bins_requested=30))

    # Set up strategy with logging
    log_filename = f"dnf_log_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    strat = DNFStrategy(filename=log_filename)
    strat.start(generator=gen)

    # Step through generator
    while True:
        result = strat.next()
        if result is None:
            break

    # Final summary
    print(strat.stop())

def run_harmonic_strategy_example():
    gen = BinGenerator()
    gen.start(bins_requested=30)

    log_filename = f"harmonic_log_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    strat = HarmonicStrategy(filename=log_filename)
    strat.start(generator=gen)

    while True:
        result = strat.next()
        if result is None:
            break

    print(strat.stop())

if __name__ == "__main__":
    run_custom_dnf_example()
    run_harmonic_strategy_example()

