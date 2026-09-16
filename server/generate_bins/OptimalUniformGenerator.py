import random
import datetime
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))
from generate import Generate


class OptimalUniformGenerator(Generate):
    """
    Generates items with uniform distribution between 0 and max_size.
    Uses bin-filling approach: starts with full bin, generates uniform items,
    and when threshold is reached, forces a completion item.
    This guarantees exactly N bins can be covered optimally (OPT is known).
    """
    def __init__(self, max_size=1.0, path="./data/", min_size=0.0001, bin_capacity=1.0, threshold=0.15):
        """
        max_size: maximum item size for uniform generation (default 1.0)
        path: directory to save generated data
        min_size: minimum item size (default 0.0001 to avoid zero-size items)
        bin_capacity: capacity of each bin (default 1.0)
        threshold: when remaining capacity falls below this fraction, force completion (default 0.15)
        """
        self._numbers = []
        self._index = 0
        self._bins_requested = 0
        self._max_size = max_size
        self._min_size = min_size
        self._path = path
        self._file = None
        self._filename = None
        self._bin_capacity = bin_capacity
        self._threshold = threshold
        self._optimal_bins = 0  # Number of bins that can be covered (= bins_requested)

    def _open_log_file(self):
        """Create a timestamped file for logging generated items."""
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        pid = os.getpid()
        self._filename = f"OptimalUniform_{timestamp}_{pid}.txt"
        os.makedirs(self._path, exist_ok=True)
        self._file = open(os.path.join(self._path, self._filename), "w")

    def _close_log_file(self):
        """Safely close the log file."""
        if self._file:
            self._file.close()
            self._file = None

    def _generate_items_for_bins(self, bins_to_cover):
        """
        Generate items using bin-filling approach with uniform distribution.
        Starts with full bin, generates uniform items, when threshold is reached,
        forces a completion item. Guarantees exactly bins_to_cover bins.
        
        Returns: list of generated items
        """
        items = []
        bin_load = self._bin_capacity  # Start with full bin (remaining capacity)
        bins_covered = 0
        threshold_capacity = self._threshold * self._bin_capacity
        
        while bins_covered < bins_to_cover:
            # Generate a uniform random item
            random_item = random.uniform(self._min_size, self._max_size)
            
            # Subtract from current bin
            bin_load -= random_item
            
            if bin_load < threshold_capacity:
                # Threshold reached - need to complete this bin
                if bin_load < 0:
                    # Item overflowed - revert and add remaining capacity instead
                    bin_load += random_item
                    if bin_load > self._min_size:
                        items.append(bin_load)
                else:
                    # Add the random item and then add the remaining capacity
                    items.append(random_item)
                    if bin_load > self._min_size:
                        items.append(bin_load)
                
                # Reset for next bin
                bin_load = self._bin_capacity
                bins_covered += 1
            else:
                # Normal case - just add the item
                items.append(random_item)
        
        return items

    def get_optimal_bins(self):
        """Return the optimal number of bins that can be covered with generated items."""
        return self._optimal_bins
    
    def get_items(self):
        """Return the list of generated items (for distribution analysis)."""
        return self._numbers.copy()

    def start(self, bins_to_cover):
        """
        Initialize the generator to produce items that cover exactly bins_to_cover bins.
        
        Args:
            bins_to_cover: number of bins to cover (OPT)
        """
        self._open_log_file()
        self._bins_requested = bins_to_cover
        self._optimal_bins = bins_to_cover
        self._numbers = self._generate_items_for_bins(bins_to_cover)
        
        # Sort in descending order for the strategy
        self._numbers.sort(reverse=True)
        
        self._index = 0
        
        # Write items to log file
        if self._file:
            for val in self._numbers:
                self._file.write(f"{val}\n")

        msg = f"OptimalUniform Generator: {len(self._numbers)} items for {bins_to_cover} bins (OPT). Threshold: {self._threshold*100:.0f}%"
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
        return f"Generator stopped. Total items generated: {len(self._numbers)}, OPT bins: {self._optimal_bins}"


# Example usage
if __name__ == "__main__":
    gen = OptimalUniformGenerator()
    print(gen.start(500))  # Generate items for 500 bins
    print(f"Total items: {len(gen.get_items())}")
    print(f"OPT bins: {gen.get_optimal_bins()}")

    # Show first 10 items
    for i in range(min(10, len(gen.get_items()))):
        print(gen.next())

    print(gen.stop())
