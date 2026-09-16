import random
import datetime
import sys
import os
from bincovering.generators.base import Generate


class BigItemsGenerator(Generate):
    """
    Generates items that are all "big" (above 0.5 but below 1.0).
    This is a potential worst-case for strategies that spread big items.
    
    The OPT for this sequence is: floor(sum_of_items / 1.0)
    Since each item is > 0.5, optimal pairing covers floor(N/2) bins if items sum to ~N/2.
    
    Example: 10 items of size 0.51 each
    - Sum = 5.1
    - OPT = 5 (5 bins covered, 0.1 leftover)
    - But if you spread them out, you might only cover 0 bins!
    """
    def __init__(self, min_size=0.51, max_size=0.99, path="./data/"):
        """
        min_size: minimum item size (default 0.51, just above 0.5)
        max_size: maximum item size (default 0.99, below 1.0)
        path: directory to save generated data
        """
        self._numbers = []
        self._index = 0
        self._num_items = 0
        self._min_size = min_size
        self._max_size = max_size
        self._path = path
        self._file = None
        self._filename = None
        self._optimal_bins = 0
        self._total_sum = 0.0

    def _open_log_file(self):
        """Create a timestamped file for logging generated items."""
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        pid = os.getpid()
        self._filename = f"BigItems_{timestamp}_{pid}.txt"
        os.makedirs(self._path, exist_ok=True)
        self._file = open(os.path.join(self._path, self._filename), "w")

    def _close_log_file(self):
        """Safely close the log file."""
        if self._file:
            self._file.close()
            self._file = None

    def _generate_big_items(self, num_items):
        """
        Generate num_items big items with uniform distribution in [min_size, max_size].
        
        Returns: list of generated items
        """
        items = []
        for _ in range(num_items):
            random_item = random.uniform(self._min_size, self._max_size)
            items.append(random_item)
        
        return items

    def get_optimal_bins(self):
        """
        Return the optimal number of bins that can be covered.
        OPT = floor(sum_of_items / 1.0)
        """
        return self._optimal_bins
    
    def get_total_sum(self):
        """Return the total sum of all items."""
        return self._total_sum
    
    def get_items(self):
        """Return the list of generated items (for distribution analysis)."""
        return self._numbers.copy()

    def start(self, num_items):
        """
        Initialize the generator to produce num_items big items.
        
        Args:
            num_items: number of big items to generate
        """
        self._open_log_file()
        self._num_items = num_items
        self._numbers = self._generate_big_items(num_items)
        
        # Calculate OPT based on sum
        self._total_sum = sum(self._numbers)
        self._optimal_bins = int(self._total_sum)  # floor of sum
        
        # Sort in descending order (worst case for spreading strategies)
        self._numbers.sort(reverse=True)
        
        self._index = 0
        
        # Write items to log file
        if self._file:
            for val in self._numbers:
                self._file.write(f"{val}\n")

        msg = (f"BigItems Generator: {len(self._numbers)} items in [{self._min_size:.2f}, {self._max_size:.2f}], "
               f"Sum={self._total_sum:.4f}, OPT={self._optimal_bins}")
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
        return f"Generator stopped. Items: {len(self._numbers)}, Sum: {self._total_sum:.4f}, OPT: {self._optimal_bins}"


# Example usage
if __name__ == "__main__":
    gen = BigItemsGenerator(min_size=0.51, max_size=0.51)  # All items exactly 0.51
    print(gen.start(10))
    
    print("\nItems:")
    items = gen.get_items()
    for i, item in enumerate(items):
        print(f"  {i+1}: {item:.6f}")
    
    print(f"\nTotal sum: {gen.get_total_sum():.4f}")
    print(f"OPT bins: {gen.get_optimal_bins()}")
    print(gen.stop())
