import sys
import matplotlib.pyplot as plt


# Function to read numbers from file
def read_numbers_from_file(filename):
    with open(filename, 'r') as file:
        numbers = [int(line.strip()) for line in file]
    return numbers

# Function to plot the numbers
def plot_numbers(numbers, algo_result, opt_result, output_filename):
    plt.figure(figsize=(10, 5))
    plt.plot(numbers, marker='o', linestyle=' ', color='b')
    plt.title(algo_result+' covered bins out of '+opt_result+' optimal')
    plt.xlabel('Index of item')
    plt.ylabel('Size of item')
    plt.grid(True)
    plt.savefig(output_filename)


# Main script
filename_numbers = sys.argv[1]
algo_result = sys.argv[2]
opt_result = sys.argv[3]
output_filename = sys.argv[4]

plot_numbers(read_numbers_from_file(filename_numbers), algo_result, opt_result, output_filename)