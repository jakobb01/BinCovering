import matplotlib.pyplot as plt

# Function to read numbers from a file
def read_numbers_from_file(filename):
    with open(filename, 'r') as file:
        numbers = [int(line.strip()) for line in file]
    return numbers

# Function to plot the numbers
def plot_numbers(numbers, title):
    plt.figure(figsize=(10, 5))
    plt.plot(numbers, marker='o', linestyle='-', color='b')
    plt.title(title)
    plt.xlabel('Index')
    plt.ylabel('Number')
    plt.grid(True)
    plt.show()

# Main script
filename = '../output.txt'  # The file generated by the C++ program
numbers = read_numbers_from_file(filename)
plot_numbers(numbers, 'Random Numbers without Trend')
