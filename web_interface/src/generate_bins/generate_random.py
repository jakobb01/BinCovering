import random
import sys

def get_int_from_custom_range(start, end):
    """Return a random integer between start and end, inclusive."""
    return random.randint(start, end)

def get_double_from_custom_range(start, end):
    """Return a random float between start and end."""
    return random.uniform(start, end)

def generate_custom_range_from_optimum(filename, bins_covered, max_val):
    """Generate numbers simulating bin loads and write to a file."""
    with open(filename, 'w') as out_file:
        bin_load = max_val
        i = 0

        while i != bins_covered:
            # Randomly pick a number from the upper range
            random_number = get_int_from_custom_range(int(0.7 * (max_val - 1)), max_val - 1)

            # Subtract it from current bin load
            bin_load -= random_number

            # Threshold to determine whether to reset the bin
            random_bin_load_index = 0.2  # fixed threshold

            if bin_load < (random_bin_load_index * max_val):
                if bin_load < 0:
                    # Revert and flush the overflowed load
                    bin_load += random_number
                    out_file.write(f"{bin_load}\n")
                else:
                    # Write last number and what's left in the bin
                    out_file.write(f"{random_number}\n")
                    out_file.write(f"{bin_load}\n")
                bin_load = max_val
                i += 1
            else:
                out_file.write(f"{random_number}\n")

    print(f"Random numbers generated and written to {filename}")

if __name__ == "__main__":
    # Check for valid arguments
    if len(sys.argv) != 3:
        print("Usage: python script.py <filename> <bins_covered>")
        sys.exit(1)

    filename_INP = sys.argv[1]
    filename = "./src/data/" + filename_INP
    bins_covered_INP = int(sys.argv[2])
    max_load = 1_000_000

    generate_custom_range_from_optimum(filename, bins_covered_INP, max_load)
