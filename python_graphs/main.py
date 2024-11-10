import calendar;
import os
import time;
import sys;
import subprocess;

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
filename_output = algo+'_run_on_'+str(unix_timestamp)+'.png'


# INPUT SECTION get input params for this script

# generator
# optimal_bins_covered
optimal_bins_covered = str(int(sys.argv[1]))

# mixer
# percent_of_mix
percent_of_mix = (sys.argv[2])


# RUNNING SECTION

# run generator and collect generated file
# params:
#       optimal_bins_covered
#       filename_generated
command = [path_generator, filename_generated, optimal_bins_covered]
subprocess.run(command, capture_output=True, text=True)

# run mixer with gen file and collect new file and graph
# params:
#       filename_generated      # where to get the data (from previous command - run generator)
#       filename_mixer          # items mixed according to percent_of_mix
#       filename_sorted
#       percent_of_mix
command = ['python3', path_mixer, filename_generated, filename_mixer, filename_sorted, percent_of_mix]
subprocess.run(command, capture_output=True, text=True)

# run DNF and collect return integer
# params:
#       filename_mixer
# output:
#       return_int
command = [path_algo, filename_mixer]
result = subprocess.run(command, capture_output=True, text=True)
return_int = int(result.stdout.strip())  # convert stdout to int


# DOCUMENTATION SECTION
# generate filename_output with sorted items graph and performance of algorithm
# params:
#       filename_sorted
#       return_int
#       optimal_bins_covered
#       filename_output
command = ['python3', path_graph, filename_sorted, str(return_int), optimal_bins_covered, filename_output]
subprocess.run(command)


# TESTING SECTION
# tell user where he can find output of the test
print('Results can be found here: '+filename_output)