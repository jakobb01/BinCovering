# pure_dnf.py
import sys
import os

# Add the parent folder of element_iterator.py to the system path
sys.path.append(os.path.abspath("./src/custom_code/"))

from element_iterator import ElementIterator


BIN_COVER_LOAD = 1_000_000  # max bin capacity


def DNF(item, bin_load):
    """Simulate DNF bin logic with item addition and bin overflow check."""
    if bin_load < 0:
        return 0
    bin_load += item
    if bin_load < BIN_COVER_LOAD:
        return bin_load
    else:
        return 1


def pure_dnf(filename_inp):
    """Process items using DNF and count fully filled bins."""
    iterator = ElementIterator(filename_inp)
    bin_load = 0
    full_bins = 0

    while True:
        element = iterator.get_next_element()
        if element is None:
            break

        val = DNF(element, bin_load)
        if val == 0:
            return 0
        elif val == 1:
            full_bins += 1
            bin_load = 0
        else:
            bin_load = val

    return full_bins


if __name__ == "__main__":
    # Check arguments
    if len(sys.argv) != 2:
        print("Usage: python pure_dnf.py <filename>")
        sys.exit(1)

    filename = sys.argv[1]
    bin_count = pure_dnf(filename)
    print(bin_count)
