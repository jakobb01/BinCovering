# Example how to run different classes in one main script
import sys
import datetime
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../generate_bins/')))
from ItemGenerator import BinGenerator
# import DualNextFit.py
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../strategies/')))
from DualNextFit import DNFStrategy


def run_custom_dnf_example():
    # Set up generator
    gen = BinGenerator()
    gen.start(bins_requested=5)

    # Set up strategy with logging
    log_filename = f"dnf_log_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    strat = DNFStrategy(filename=log_filename)
    print(strat.start(generator=gen))

    # Step through generator
    while True:
        result = strat.next()
        if result is None:
            break
        print(result)

    # Final summary
    print(strat.stop())

if __name__ == "__main__":
    run_custom_dnf_example()

