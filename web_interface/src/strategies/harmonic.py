import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from strategy import Strategy

BIN_COVER_LOAD = 1_000_000  # max bin capacity

class HarmonicStrategy(Strategy):
    def __init__(self, filename=None, path=""):
        super().__init__(filename, path)
        self.gen = None
        self.full_bins = 0
        self.bins = {
            "big": 0,
            "class3": 0,
            "class4": 0,
            "class5": 0,
            "small": 0,
        }

    def start(self, generator):
        self.gen = generator
        self.full_bins = 0
        for key in self.bins:
            self.bins[key] = 0
        if self.file:
            self.file.write("Starting Harmonic Strategy\n")
        return "Harmonic strategy started"

    def next(self):
        try:
            item = self.gen.next()
        except StopIteration:
            return None

        if self.file:
            self.file.write(f"Processing item: {item}\n")

        # Categorize item
        if item >= 0.5 * BIN_COVER_LOAD:
            bin_name = "big"
        elif item >= BIN_COVER_LOAD / 3:
            bin_name = "class3"
        elif item >= BIN_COVER_LOAD / 4:
            bin_name = "class4"
        elif item >= BIN_COVER_LOAD / 5:
            bin_name = "class5"
        else:
            bin_name = "small"

        self.bins[bin_name] += item

        # Check if current bin is full
        if self.bins[bin_name] >= BIN_COVER_LOAD:
            self.full_bins += 1
            self.bins[bin_name] = 0
            msg = f"{bin_name} bin full. Total full bins: {self.full_bins}"
        else:
            msg = f"Added {item} to {bin_name} bin. Current load: {self.bins[bin_name]}"

        if self.file:
            self.file.write(msg + "\n")

        return msg

    def stop(self):
        if self.file:
            self.file.write(f"Total bins filled: {self.full_bins}\n")
            self.file.close()
        return f"Harmonic strategy stopped. Total bins filled: {self.full_bins}"
