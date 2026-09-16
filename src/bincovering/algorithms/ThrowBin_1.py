"""
ThrowBin_1 Strategy for Bin Covering Problem.

This strategy opens a configurable ratio of N bins at the start and randomly selects one to place each item.
When a bin reaches the max_cover threshold (1.0), it is counted as covered and REPLACED with a new empty bin.
This keeps the number of active bins constant throughout the process.

The items are expected to be sorted in descending order (largest first).
"""

from bincovering.algorithms.base import Strategy

BIN_COVER_LOAD = 1.0  # max bin capacity (threshold for "covered")


class ThrowBin_1_Strategy(Strategy):
    """
    ThrowBin_1 Strategy:
    - Opens a configurable ratio of N bins at the start (default 50% = N/2)
    - For each item, randomly selects one of the active bins and places the item
    - When a bin is covered, it's replaced with a new empty bin (keeps active bins constant)
    - Counts total bins covered throughout the process
    """

    def __init__(self, filename=None, path="./data/", bin_ratio=0.5):
        """
        Args:
            filename: optional log filename
            path: path for log files
            bin_ratio: ratio of N to use as number of bins (default 0.5 = 50% = N/2)
                       e.g., 0.3 means open 30% of N bins, 0.5 means 50% (N/2)
        """
        super().__init__(filename, path)
        self.gen = None
        self.bins = []  # List of bin loads
        self.num_bins = 0  # Number of active bins (constant)
        self.covered_bins = 0  # Total bins covered (can exceed num_bins)
        self.bin_ratio = bin_ratio
        self.next_bin_id = 0  # ID for tracking bins

    def start(self, generator, num_items, bin_ratio=None):
        """
        Start strategy with an external generator.

        Args:
            generator: must implement .next() that raises StopIteration when done
            num_items: total number of items (N)
            bin_ratio: optional override for bin ratio (default uses constructor value)
        """
        self.gen = generator
        if bin_ratio is not None:
            self.bin_ratio = bin_ratio
        self.num_bins = int(num_items * self.bin_ratio)

        # Initialize all bins with zero load
        self.bins = [0.0] * self.num_bins
        self.covered_bins = 0
        self.next_bin_id = self.num_bins  # Start IDs after initial bins

        if self.file:
            self.file.write(
                f"Starting ThrowBin_1 Strategy with {self.num_bins} bins (constant)\n"
            )

        return f"Strategy started with {self.num_bins} bins"

    def next(self):
        """Process the next item using ThrowBin_1 logic."""
        try:
            item = self.gen.next()
        except StopIteration:
            return None  # End of stream

        if self.file:
            self.file.write(f"Processing item: {item}\n")

        # Randomly select one of the active bins
        selected_idx = self.rng.randint(0, self.num_bins - 1)

        # Add item to the selected bin
        self.bins[selected_idx] += item

        if self.file:
            self.file.write(
                f"Placed item {item} in bin {selected_idx}, new load: {self.bins[selected_idx]}\n"
            )

        # Check if the bin is now covered
        if self.bins[selected_idx] >= BIN_COVER_LOAD:
            self.covered_bins += 1

            # Replace the covered bin with a new empty bin
            self.bins[selected_idx] = 0.0

            if self.file:
                self.file.write(
                    f"Bin {selected_idx} is now covered! Replaced with new empty bin. Total covered: {self.covered_bins}\n"
                )

            return f"Bin {selected_idx} covered after adding {item}. Replaced with new bin. Total covered: {self.covered_bins}"

        return f"Added {item} to bin {selected_idx}, load: {self.bins[selected_idx]}"

    def stop(self):
        """Close log and report result."""
        if self.file:
            self.file.write("\n--- Final Statistics ---\n")
            self.file.write(f"Active bins (constant): {self.num_bins}\n")
            self.file.write(f"Total bins covered: {self.covered_bins}\n")
            if self.num_bins > 0:
                self.file.write(
                    f"Covered/Active ratio: {self.covered_bins / self.num_bins:.2f}\n"
                )
            self.file.close()

        return f"ThrowBin_1 strategy stopped. Total bins covered: {self.covered_bins} (with {self.num_bins} active bins)"

    def get_covered_bins(self):
        """Return the total number of bins covered."""
        return self.covered_bins

    def get_total_bins(self):
        """Return the number of active bins (constant)."""
        return self.num_bins
