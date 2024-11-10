import calendar;
import os
import time;
import sys;
import subprocess;

# this main.py file is created to:
#           - have order in naming schemes, as a lot of data will be created
#           - can be run on WSL terminal, so change the paths

# NAMING SECTION
# core names
algo = 'DNF'
unix_timestamp = calendar.timegm(time.gmtime())

# paths for accessing scripts
path_generator='/mnt/c/Users/jakob/CLionProjects/BinPacking/executables/generator.exe'
path_mixer='/mnt/c/Users/jakob/CLionProjects/BinPacking/python_graphs/graphs.py'
path_algo='/mnt/c/Users/jakob/CLionProjects/BinPacking/executables/dnf.exe'

# convention for all filenames
filename_core = 'binCovering'
filename_generated = filename_core+'_generated_on_'+str(unix_timestamp)+'.txt'
filename_mixer = filename_core+'_numbers_mixed_'+str(unix_timestamp)+'.txt'
filename_output = algo+'_run_on_'+str(unix_timestamp)



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
#       percent_of_mix
command = ['python3', path_mixer, filename_generated, filename_mixer, percent_of_mix]
subprocess.run(command, capture_output=True, text=True)

# run DNF and collect return integer
# params:
#       filename_mixer
# output:
#       return_int
command = [path_algo, filename_mixer]
result = subprocess.run(command, capture_output=True, text=True)
return_int = int(result.stdout.strip())  # Convert stdout to int after stripping whitespace



# DOCUMENTATION SECTION
# generate some file with input graph and performance



# TESTING SECTION

#print(str(optimal_bins_covered) + ' ' + str(percent_of_mix))
#print(filename_output)