import sys
import os

# Add the parent folder of element_iterator.py to the system path
sys.path.append(os.path.abspath("./src/custom_code/"))

from element_iterator import ElementIterator

BIN_COVER_LOAD = 1_000_000  # max bin capacity


def DNF(item, bin_load):
    """Simulate Dual Next Fit bin logic."""
    if bin_load < 0:
        return 0
    bin_load += item
    if bin_load < BIN_COVER_LOAD:
        return bin_load
    else:
        return 1


def harmonic(filename_inp):
    """Harmonic bin packing with 5 size-based categories (k=5)."""
    iterator = ElementIterator(filename_inp)
    full_bins = 0

    # Initialize separate bins for size classes
    big_bin = 0
    bin3 = 0
    bin4 = 0
    bin5 = 0
    small_bin = 0

    while True:
        element = iterator.get_next_element()
        if element is None:
            break
        item = element

        # Classify and handle each item based on harmonic intervals
        if item >= 0.5 * BIN_COVER_LOAD:
            result = DNF(item, big_bin)
            if result == 1:
                full_bins += 1
                big_bin = 0
            else:
                big_bin = result

        elif item >= BIN_COVER_LOAD / 3:
            result = DNF(item, bin3)
            if result == 1:
                full_bins += 1
                bin3 = 0
            else:
                bin3 = result

        elif item >= BIN_COVER_LOAD / 4:
            result = DNF(item, bin4)
            if result == 1:
                full_bins += 1
                bin4 = 0
            else:
                bin4 = result

        elif item >= BIN_COVER_LOAD / 5:
            result = DNF(item, bin5)
            if result == 1:
                full_bins += 1
                bin5 = 0
            else:
                bin5 = result

        else:
            result = DNF(item, small_bin)
            if result == 1:
                full_bins += 1
                small_bin = 0
            else:
                small_bin = result

    return full_bins


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: harmonic <filename>")
        sys.exit(1)

    filename = sys.argv[1]
    bin_count = harmonic(filename)
    print(bin_count)
