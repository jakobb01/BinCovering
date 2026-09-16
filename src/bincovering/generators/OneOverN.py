import random
import datetime
import sys
import os
from bincovering.generators.base import Generate


class OneOverNGenerator(Generate):
    def __init__(self, max_load=1.0, path="./data/"):
        self._numbers = []
        self._index = 0
        self._items_requested = 0
        self._max_load = max_load
        self._path = path
        self._file = None
        self._filename = None

    def _open_log_file(self):
        """Create a timestamped file for logging generated items."""
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self._filename = f"OneOverN_{timestamp}.txt"
        os.makedirs(self._path, exist_ok=True)
        self._file = open(os.path.join(self._path, self._filename), "w")
        #self._file.write("Starting OneOverN Generator\n")
        #self._file.write(f"Max load: {self._max_load}\n\n")

    def _close_log_file(self):
        """Safely close the log file."""
        if self._file:
            #self._file.write("\nGenerator finished.\n")
            self._file.close()
            self._file = None

    def _generate_complementary_pairs(self, m):
        """Generate m/2 small items and m/2 big complementary items."""
        if m % 2 != 0:
            raise ValueError("m must be an even number (half small, half big).")

        n = m // 2  # number of small and big items
        small_items = []

        # Generate small items between 0 and 1/n
        for _ in range(n):
            size = random.uniform(0.0001, 1 / n)
            small_items.append(size)

        # Generate big items as complements
        big_items = [self._max_load - s for s in small_items]

        combined = small_items + big_items
        combined.sort(reverse=True)

        # Write sorted items to log file
        if self._file:
            for val in combined:
                self._file.write(f"{val}\n")

        return combined

    def start(self, m):
        """Initialize the generator, log items, and prepare for iteration."""
        self._open_log_file()
        self._items_requested = m
        self._numbers = self._generate_complementary_pairs(m)
        self._index = 0

        msg = f"Generator will generate {m} total items (half small, half big)."
        #if self._file:
        #    self._file.write(f"\n{msg}\n\n")
        return msg

    def next(self):
        """Return the next generated item."""
        if self._index < len(self._numbers):
            val = self._numbers[self._index]
            self._index += 1
            return val
        else:
            self._close_log_file()
            raise StopIteration("No more items to generate")

    def stop(self):
        """Stop the generator and close the log file."""
        self._close_log_file()
        return f"Generator stopped. Total items generated: {len(self._numbers)}"


# Example usage
if __name__ == "__main__":
    gen = OneOverNGenerator()
    print(gen.start(1000))  # 10 total items → 5 small + 5 big

    try:
        while True:
            print(gen.next())
    except StopIteration:
        pass

    print(gen.stop())

