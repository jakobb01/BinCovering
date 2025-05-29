import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from strategy import Strategy

BIN_COVER_LOAD = 1_000_000  # max bin capacity

class DNFStrategy(Strategy):
    def __init__(self, filename=None, path="./src/data/"):
        super().__init__(filename, path)
        self.gen = None
        self.bin_load = 0
        self.full_bins = 0

    def start(self, generator):
        # """
        # Start strategy with an external generator.
        # `generator` must implement .next() that raises StopIteration when done.
        # """
        self.gen = generator
        self.bin_load = 0
        self.full_bins = 0
        if self.file:
            self.file.write("Starting DNF Strategy\n")
        return "Strategy started"

    def next(self):
        #"""Process the next item using DNF bin-packing logic."""
        try:
            item = self.gen.next()
        except StopIteration:
            return None  # End of stream

        if self.file:
            self.file.write(f"Processing item: {item}\n")

        self.bin_load += item
        if self.bin_load < BIN_COVER_LOAD:
            return f"Added {item}, current bin load: {self.bin_load}"
        else:
            self.full_bins += 1
            self.bin_load = 0
            return f"Bin full after adding {item}. Bins filled: {self.full_bins}"

    def stop(self):
        #"""Close log and report result."""
        if self.file:
            self.file.write(f"Total bins filled: {self.full_bins}\n")
            self.file.close()
        return f"DNF strategy stopped. Total bins filled: {self.full_bins}"
