# Example how to run different classes in one main script
import sys
import datetime
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../generate_bins/')))
from OneOverN import OneOverNGenerator
from FileShuffleGenerator import FileShuffleGenerator
# import DualNextFit.py
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../strategies/')))
from DNF_1 import DNFStrategy

def run_dnf_randomization_test():
    # Loop through item counts: 10k, 20k, ... 100k
    # from 100k to 1.000k
    for NUM_OF_ITEMS in range(100_000, 1_000_001, 100_000):
        print(f"\n=== Running DNF randomization test for {NUM_OF_ITEMS} items ===")

        # Step 1: Generate base OneOverN file
        base_gen = OneOverNGenerator()
        print("Generating base data file...")
        print(base_gen.start(NUM_OF_ITEMS))
        base_gen.stop()

        # Find the file we just created
        base_file = base_gen._filename
        base_path = base_gen._path
        print(f"Base file generated: {base_file}")

        # Create a summary file for this NUM_OF_ITEMS
        summary_filename = f"dnf_summary_{NUM_OF_ITEMS}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        summary_path = os.path.join(base_path, summary_filename)

        # Step 2: Run DNF strategy for increasing number of swaps
        with open(summary_path, "w") as summary_file:
            summary_file.write(f"DNF Strategy Randomization Results\n")
            summary_file.write(f"Base file: {base_file}\n")
            summary_file.write(f"Date: {datetime.datetime.now()}\n")
            summary_file.write(f"Items: {NUM_OF_ITEMS}\n\n")
            summary_file.write(f"{'Swaps':>10} | {'Bins Filled':>12}\n")
            summary_file.write("-" * 28 + "\n")

            for swaps in range(0, NUM_OF_ITEMS + 1):
                file_gen = FileShuffleGenerator(
                    filename=base_file,
                    path=base_path,
                    num_swaps=swaps
                )
                file_gen.start()

                strat = DNFStrategy()
                strat.start(generator=file_gen)

                while True:
                    result = strat.next()
                    if result is None:
                        break

                strat.stop()
                bins_filled = strat.full_bins

                summary_file.write(f"{swaps:10d} | {int(bins_filled):12d}\n")

        print(f"Summary results saved to: {summary_filename}")

if __name__ == "__main__":
    run_dnf_randomization_test()

