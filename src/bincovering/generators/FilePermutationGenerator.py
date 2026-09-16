import random
import os
import sys
from bincovering.generators.base import Generate


class FilePermutationGenerator(Generate):
    """
    Generator that loads items from a file and applies a random permutation.
    Unlike swaps (which swap pairs), this fully shuffles the sequence randomly.
    """
    def __init__(self, filename, path="./data/", seed=None):
        """
        filename: name of the input file
        path: directory containing the file
        seed: random seed for reproducible permutations (None = random)
        """
        self._filename = filename
        self._path = path
        self._seed = seed
        self._numbers = []
        self._index = 0
        self._file_path = os.path.join(self._path, self._filename)

        if not os.path.exists(self._file_path):
            raise FileNotFoundError(f"File not found: {self._file_path}")

    def _load_file(self):
        """Read all numeric values from the input file into memory."""
        with open(self._file_path, "r") as f:
            # Parse floats from lines, ignoring blanks
            self._numbers = [
                float(line.strip()) for line in f if line.strip()
            ]

    def _apply_permutation(self):
        """Apply a random permutation to the list (full shuffle)."""
        if self._seed is not None:
            random.seed(self._seed)
        random.shuffle(self._numbers)

    def start(self):
        """Load file and apply random permutation."""
        self._load_file()
        self._apply_permutation()
        self._index = 0
        return (
            f"FilePermutationGenerator started with file '{self._filename}' "
            f"(seed={self._seed})"
        )

    def next(self):
        """Return the next number in the permuted list."""
        if self._index < len(self._numbers):
            val = self._numbers[self._index]
            self._index += 1
            return val
        else:
            raise StopIteration("No more items to generate")

    def stop(self):
        """Stop reading and return how many items were served."""
        return f"Generator stopped. Total items served: {self._index}"


# Example usage
if __name__ == "__main__":
    filename = "TrueUniform_20251201_105117_123456_12345.txt"
    gen = FilePermutationGenerator(filename, path="./data/", seed=42)
    print(gen.start())

    for i in range(10):
        print(gen.next())

    print(gen.stop())
