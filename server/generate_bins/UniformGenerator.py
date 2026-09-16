import random
import datetime
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))
from generate import Generate


class UniformGenerator(Generate):
    """
    Generates items with TRUE uniform distribution between min_size and max_size.
    No bin-filling constraints - purely random uniform items.
    OPT is NOT known in advance.
    """
    def __init__(self, max_size=1.0, path="./data/", min_size=0.0001):
        """
        max_size: maximum item size (default 1.0)
        path: directory to save generated data
        min_size: minimum item size (default 0.0001 to avoid zero-size items)
        """
        self._numbers = []
        self._index = 0
        self._num_items = 0
        self._max_size = max_size
        self._min_size = min_size
        self._path = path
        self._file = None
        self._filename = None

    def _open_log_file(self):
        """Create a timestamped file for logging generated items."""
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        pid = os.getpid()
        self._filename = f"TrueUniform_{timestamp}_{pid}.txt"
        os.makedirs(self._path, exist_ok=True)
        self._file = open(os.path.join(self._path, self._filename), "w")

    def _close_log_file(self):
        """Safely close the log file."""
        if self._file:
            self._file.close()
            self._file = None

    def _generate_uniform_items(self, num_items):
        """
        Generate num_items items with true uniform distribution.
        
        Returns: list of generated items
        """
        items = []
        for _ in range(num_items):
            random_item = random.uniform(self._min_size, self._max_size)
            items.append(random_item)
        
        return items

    def get_items(self):
        """Return the list of generated items (for distribution analysis)."""
        return self._numbers.copy()

    def start(self, num_items):
        """
        Initialize the generator to produce num_items uniformly distributed items.
        
        Args:
            num_items: number of items to generate
        """
        self._open_log_file()
        self._num_items = num_items
        self._numbers = self._generate_uniform_items(num_items)
        
        # Sort in descending order for the strategy
        self._numbers.sort(reverse=True)
        
        self._index = 0
        
        # Write items to log file
        if self._file:
            for val in self._numbers:
                self._file.write(f"{val}\n")

        msg = f"True Uniform Generator: {len(self._numbers)} items in [{self._min_size}, {self._max_size}]"
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
    gen = UniformGenerator()
    print(gen.start(1000))  # Generate 1000 uniform items
    print(f"Total items: {len(gen.get_items())}")

    # Show first 10 items
    for i in range(min(10, len(gen.get_items()))):
        print(gen.next())

    print(gen.stop())
