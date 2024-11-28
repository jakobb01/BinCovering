import calendar;
import os
import time;
import sys;
import subprocess;
# test libaries
from openpyxl import Workbook

wb = Workbook()
ws = wb.active

headers = ["num_OPT", "num_gen", "num_perm", "DNF_result"]
ws.append(headers)

# this main.py file is created to:
#           - have order in naming schemes, as a lot of data will be created
#           - can be run on WSL terminal, so change the paths
#           - create easy to read reports on tests done


# NAMING SECTION
# core names
algo = 'DNF'
unix_timestamp = calendar.timegm(time.gmtime())

# paths for accessing scripts
path_generator='/mnt/c/Users/jakob/CLionProjects/BinPacking/executables/generator.exe'
path_mixer='/mnt/c/Users/jakob/CLionProjects/BinPacking/python_graphs/mixer.py'
path_algo='/mnt/c/Users/jakob/CLionProjects/BinPacking/executables/dnf.exe'
path_graph='/mnt/c/Users/jakob/CLionProjects/BinPacking/python_graphs/graph.py'

# convention for all filenames
filename_core = 'binCovering'
filename_generated = filename_core+'_generated_on_'+str(unix_timestamp)+'.txt'
filename_mixer = filename_core+'_numbers_mixed_'+str(unix_timestamp)+'.txt'
filename_sorted = filename_core+'_numbers_sorted_'+str(unix_timestamp)+'.txt'
filename_output = algo+'_run_on_'+str(unix_timestamp)   #+'.png'


# INPUT SECTION get input params for this script

# generator
# optimal_bins_covered
#optimal_bins_covered = str(int(sys.argv[1]))

# mixer
# percent_of_mix
#percent_of_mix = (sys.argv[2])


# RUNNING SECTION

# run generator and collect generated file
# params:
#       optimal_bins_covered
#       filename_generated
def run_generator(optimal_bins_covered, filename_generated):
    command = [path_generator, filename_generated, optimal_bins_covered]
    subprocess.run(command, capture_output=True, text=True)

# run mixer with gen file and collect new file and graph
# params:
#       filename_generated      # where to get the data (from previous command - run generator)
#       filename_mixer          # items mixed according to percent_of_mix
#       filename_sorted
#       percent_of_mix
def run_mixer(percent_of_mix, filename_generated, filename_mixer):
    command = ['python3', path_mixer, filename_generated, filename_mixer, filename_sorted, percent_of_mix]
    subprocess.run(command, capture_output=True, text=True)

# run DNF and collect return integer
# params:
#       filename_mixer
# output:
#       return_int
def run_dnf(filename_mixer):
    command = [path_algo, filename_mixer]
    result = subprocess.run(command, capture_output=True, text=True)
    return int(result.stdout.strip())  # convert stdout to int


# DOCUMENTATION SECTION
# generate filename_output with sorted items graph and performance of algorithm
# params:
#       filename_sorted
#       return_int
#       optimal_bins_covered
#       filename_output
def create_png():
    command = ['python3', path_graph, filename_sorted, str(return_int), optimal_bins_covered, filename_output]
    subprocess.run(command)

def create_long_test():
    opt_array = [300, 400, 500, 600, 700, 800, 900, 1000, 1100, 1200]
    num_generator = 10
    num_permutation = 100

    for opt in opt_array:
        for generation in range(num_generator):
            file=str(opt)+str(generation)+'.txt'
            # run generator, change file name as we loop
            run_generator(str(opt), file)
            for permutation in range(num_permutation):
                file2 = str(opt) + str(generation) + str(permutation) + '.txt'
                # run mixer for every permutation
                run_mixer(str(100), file, file2)
                # run dnf and get return int
                return_int=run_dnf(file2)
                # add return int to output excell file
                row = [opt, generation, permutation, return_int]
                ws.append(row)




# TESTING SECTION
create_long_test()
wb.save(filename_output+".xlsx")
# tell user where he can find output of the test
print('Results can be found here: '+filename_output)