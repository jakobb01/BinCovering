import random
import sys

# import matplotlib.pyplot as plt


# Function to read numbers from a file
def read_numbers_from_file(filename):
    with open(filename, 'r') as file:
        numbers = [int(line.strip()) for line in file]
    return numbers


# Function to plot the numbers
# def plot_numbers(numbers, title):
#     plt.figure(figsize=(10, 5))
#     plt.plot(numbers, marker='o', linestyle=' ', color='b')
#     plt.title(title)
#     plt.xlabel('Index')
#     plt.ylabel('Number')
#     plt.grid(True)
#     plt.show()

def randomizeSort(numbers, amount):
    for i in range(0, amount):
        first_ind = random.randint(0, len(numbers)-1)
        second_ind = random.randint(0, len(numbers)-1)
        tmp = numbers[first_ind]
        numbers[first_ind] = numbers[second_ind]
        numbers[second_ind] = tmp
    return numbers

def reorder_numbers(numbers, filename, sortOrShuffle, percent_of_mix):
    if sortOrShuffle == 1:
        numbers.sort()
        # filename = "../sort_" + filename_core
    elif sortOrShuffle == 2:
        random.shuffle(numbers)
        random.shuffle(numbers)
        # filename = "../rand_" + filename_core
    elif sortOrShuffle == 3:
        numbers.sort()
        numbers.reverse()
        # filename = "../revSort_" + filename_core
    elif sortOrShuffle == 4:
        numbers.sort()
        mid = len(numbers) // 2
        first_half = numbers[:mid]
        second_half = numbers[mid:]
        second_half.reverse()
        numbers = first_half + second_half
        # filename = "../middleBig_" + filename_core
    elif sortOrShuffle == 5:
        numbers.sort()
        numbers.reverse()
        numbers = randomizeSort(numbers, (int(len(numbers)*percent_of_mix)))
        # filename = "../MixrevSort_" + filename_core


    with open(filename, "w") as txt_file:
        for number in numbers:
            txt_file.write(str(number) + "\n")


# Main script
filename = sys.argv[1]                  # The file generated by the C++ program (generator.exe)
filename_output = sys.argv[2]           # output name of the file
percent_of_mix = int(sys.argv[3])       # what percent of items should be switched

numbers = read_numbers_from_file(filename)
# sort
print(int(len(numbers)*(percent_of_mix*0.01)))
reorder_numbers(numbers, filename_output, 5, percent_of_mix)
# shuffle
#reorder_numbers(numbers, filename, 4)

#numbers.sort()
# plot_numbers(numbers, 'Random Numbers from Optimal')
