# if you will be writting a strategy, you need to use ElementIterator to get the elements from file.
import sys
import os

# Add the parent folder of element_iterator.py to the system path
sys.path.append(os.path.abspath("./src/custom_code/"))

from element_iterator import ElementIterator


def function(filename, custom_input_int):
    print("Do something fun here!")


if __name__ == "__main__":
    # Check for valid arguments
    if len(sys.argv) != 3:
        print("Usage: script_name <filename> <custom_input>")
        sys.exit(1)

    custom_input_file = sys.argv[1]
    filename = "./src/data/" + custom_input_file
    custom_input_int = int(sys.argv[2])

    function(filename, custom_input_int)
