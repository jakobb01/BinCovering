import random
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from generate import Generate

class BinGenerator(Generate):
    def __init__(self):
        self._numbers = []
        self._index = 0
        self._bins_requested = 0
        self._max_load = 1_000_000

    def _get_int_from_custom_range(self, start, end):
        return random.randint(start, end)

    def _generate_numbers(self, bins_covered):
        #"""Simulate bin loads and store numbers in memory instead of a file."""
        numbers = []
        bin_load = self._max_load
        i = 0

        while i < bins_covered:
            random_number = self._get_int_from_custom_range(
                int(0.4 * (self._max_load - 1)), self._max_load - 1
            )
            bin_load -= random_number
            threshold = 0.2  # fixed threshold

            if bin_load < (threshold * self._max_load):
                if bin_load < 0:
                    # Revert overflow and flush what's left
                    bin_load += random_number
                    numbers.append(bin_load)
                else:
                    numbers.append(random_number)
                    numbers.append(bin_load)
                bin_load = self._max_load
                i += 1
            else:
                numbers.append(random_number)

        return numbers

    def start(self, bins_requested):
        #"""Start the generator by generating numbers for a set number of bins."""
        self._bins_requested = bins_requested
        self._numbers = self._generate_numbers(bins_requested)
        self._index = 0
        return f"Generator will generate items up to total bins filled: {bins_requested}"

    def next(self):
        #"""Return the next number in sequence."""
        if self._index < len(self._numbers):
            number = self._numbers[self._index]
            self._index += 1
            return number
        else:
            raise StopIteration("No more numbers to generate")

    def stop(self):
        #"""Return the number of bins covered with the generated numbers."""
        total_bins_covered = 0
        load = self._max_load

        for i in range(self._index):
            load -= self._numbers[i]
            if load < (0.2 * self._max_load):
                total_bins_covered += 1
                load = self._max_load

        return total_bins_covered

# # Example usage
# if __name__ == "__main__":
#     gen = BinGenerator()
#     gen.start(5)

#     print("Generated numbers:")
#     try:
#         while True:
#             print(gen.next())
#     except StopIteration:
#         pass

#     print(f"\nBins covered: {gen.stop()}")
