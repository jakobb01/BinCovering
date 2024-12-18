#include <iostream>
#include <fstream>

using namespace std;

//filename where algorithms will read pre-generated elements
// put the absolute path in
const string FILENAME = "C:\\Users\\jakob\\CLionProjects\\BinPacking\\MixrevSort_optRan_output.txt";

// size of items will be int 1 to 1000 to not get weird float rounding
const int BIN_COVER_LOAD = 1000000;

// M and X_M value that will be used as an advice and calculated in generator
// M is 6k in a 100k element list -> 6%
const int M = 103;
int X_M = 0.8*(BIN_COVER_LOAD);
// todo: calculate M and X_M


// general iterator to feed elements into algorithms one-by-one
class ElementIterator {
public:
    explicit ElementIterator(const string& filename) : inFile(filename) {
        if (!inFile) {
            cerr << "Failed to open file for reading.\n";
            throw runtime_error("File open error");
        }
    }

    bool getNextElement(int& element) {
        if (inFile >> element) {
            return true;
        }
        return false;
    }

private:
    ifstream inFile;
};

// DNF - Dual Next Fit -> 0 = error; 1 = 1 bin full; x = bin load
int DNF(int item, int bin) {
    if (bin < 0) {
        return 0;
    }
    // crucial to first put the item in and then check bin coverage
    bin += item;
    if (bin < BIN_COVER_LOAD) {
        return bin;
    } else {
        return 1;
    }
}

int pureDNF(string filename_inp) {

    //call universal iterator to get elements from file
    ElementIterator iterator(filename_inp);

    int bin = 0;
    int full_bins = 0;
    int val;
    int element;

    while (iterator.getNextElement(element)) {
        //cout<<element<<'\n';
        val = DNF(element, bin);
        if (val == 0) {
            return 0;
        } else if (val == 1) {
            full_bins++;
            bin = 0;
        } else {
            bin = val;
        }
    }
    return full_bins;
}

// harmonic -> k is a number in how many "classes" we divide elements
int harmonic() {

    ElementIterator iterator(FILENAME);
    int item;
    int full_bins=0;
    // todo: develop a solution that automaticly works with any k
    // k = 5
    int big_bin=0, bin3=0, bin4=0, bin5=0, small_bin=0;
    int element;

    // iterate through each item in input sequence
    while (iterator.getNextElement(element)) {
        item = element;

        // big items
        if (item >= (0.5*BIN_COVER_LOAD)) {
            int rtrn = DNF(item, big_bin);
            if (rtrn == 1) {
                full_bins++;
                big_bin = 0;
            } else {
                big_bin = rtrn;
            }
        }
        // harmonic bins
        else if ((0.5*BIN_COVER_LOAD) > item && item >= (BIN_COVER_LOAD / 3)) {
            int rtrn = DNF(item, bin3);
            if (rtrn == 1) {
                full_bins++;
                bin3 = 0;
            } else {
                bin3 = rtrn;
            }
        } else if ((BIN_COVER_LOAD / 3) > item && item >= (BIN_COVER_LOAD / 4)) {
            int rtrn = DNF(item, bin4);
            if (rtrn == 1) {
                full_bins++;
                bin4 = 0;
            } else {
                bin4 = rtrn;
            }
        } else if ((BIN_COVER_LOAD / 4) > item && item >= (BIN_COVER_LOAD / 5)) {
            int rtrn = DNF(item, bin5);
            if (rtrn == 1) {
                full_bins++;
                bin5 = 0;
            } else {
                bin5 = rtrn;
            }
        }
        // small bins
        else {
            int rtrn = DNF(item, small_bin);
            if (rtrn == 1) {
                full_bins++;
                small_bin = 0;
            } else {
                small_bin = rtrn;
            }
        }

    }
    return full_bins;
}


// algorithm with advice
int advice() {

    ElementIterator iterator(FILENAME);
    // critical bins
    int pointer_i = 0;
    struct Bin{
        int load;
        bool present;
    };
    // initialize array for critical bins with all the same values
    Bin critical_bins[M] = { };
    for (auto & critical_bin : critical_bins) {
        critical_bin = { X_M, false};
    }



    // counter + harmonic bins
    int item;
    int full_bins=0;
    // k = 5
    int bin2=0, bin3=0, bin4=0, bin5=0, small_bin=0;

    //flag for small items if we fill critical bins or small bins
    bool fill_critical = true;

    // flag when all critical bins will be filled to switch the flag "fill_critical" AND count how many critical bins were filled to be added to counter "full_bins"
    int filled_critical = 0;

    // flag when to stop filling critical bins
    bool critical_items_STOP = false;

    int element;

    while (iterator.getNextElement(element)) {
        //::printf("Full bins: %d \n", full_bins);

        item = element;


        // critical items
        if (item >= X_M && !critical_items_STOP) {
            // flag if critical bin was found
            bool found_bin = false;
            while (!found_bin) {
                if (!critical_bins[pointer_i].present) {
                    //::printf("Bin is loaded: %d \n", critical_bins[pointer_i].present);
                    critical_bins[pointer_i].load = critical_bins[pointer_i].load - X_M + item;
                    critical_bins[pointer_i].present = true;
                    //::printf("At index: %d inputing a critical item: %d into critical bin: %d that is loaded: %d \n", pointer_i, item, critical_bins[pointer_i].load, critical_bins[pointer_i].present);
                    pointer_i++;
                    found_bin = true;
                    if (pointer_i >= M) {
                        critical_items_STOP = true;
                        ::printf("Critical bins FULL! \n");
                        break;
                    }
                } else {
                    //error occurred!
                    ::printf("ERROR! -> pointer in CRITICAL BINS: %d \n", pointer_i);
                }
            }
        }
            // harmonic items
        else if (item >= (0.5 * BIN_COVER_LOAD)) {
            int rtrn = DNF(item, bin2);
            if (rtrn == 1) {
                full_bins++;
                bin2 = 0;
            } else {
                bin2 = rtrn;
            }
        }
        else if ((0.5 * BIN_COVER_LOAD) > item && item >= (BIN_COVER_LOAD / 3)) {
            int rtrn = DNF(item, bin3);
            if (rtrn == 1) {
                full_bins++;
                bin3 = 0;
            } else {
                bin3 = rtrn;
            }
        } else if ((BIN_COVER_LOAD / 3) > item && item >= (BIN_COVER_LOAD / 4)) {
            int rtrn = DNF(item, bin4);
            if (rtrn == 1) {
                full_bins++;
                bin4 = 0;
            } else {
                bin4 = rtrn;
            }
        }

        else if ((BIN_COVER_LOAD / 4) > item && item >= (BIN_COVER_LOAD / 5)) {
            int rtrn = DNF(item, bin5);
            if (rtrn == 1) {
                full_bins++;
                bin5 = 0;
            } else {
                bin5 = rtrn;
            }
        }

            // small items
        else {
            if (fill_critical) {
                filled_critical = 0;

                for (int j = 0; j < M; ++j) {
                    if (critical_bins[j].load < BIN_COVER_LOAD) {
                        critical_bins[j].load += item;
                        break;
                    } else {
                        filled_critical++;
                        //printf("FILLED CRITICAL: %d with load: %d \n", j, critical_bins[j].load);
                    }
                }
                if (filled_critical==M) {
                    fill_critical=false;
                }
            } else {
                int rtrn = DNF(item, small_bin);
                if (rtrn == 1) {
                    full_bins++;
                    small_bin = 0;
                } else {
                    small_bin = rtrn;
                }
            }
        }
    }

    ::printf("Full critical bins: %d \n", filled_critical);


    // add count of all covered critical bins
    full_bins += filled_critical;

    return full_bins;
}

// TESTING k=3, just for test
int advice_k() {

    ElementIterator iterator(FILENAME);
    // critical bins
    int pointer_i = 0;
    struct Bin{
        int load;
        bool present;
    };
    // initialize array for critical bins with all the same values
    Bin critical_bins[M] = { };
    for (auto & critical_bin : critical_bins) {
        critical_bin = { X_M, false};
    }



    // counter + harmonic bins
    int item;
    int full_bins=0;
    // k = 5
    int bin2=0, bin3=0, bin4=0, bin5=0, small_bin=0;

    //flag for small items if we fill critical bins or small bins
    bool fill_critical = true;

    // flag when all critical bins will be filled to switch the flag "fill_critical" AND count how many critical bins were filled to be added to counter "full_bins"
    int filled_critical = 0;

    // flag when to stop filling critical bins
    bool critical_items_STOP = false;

    int element;

    while (iterator.getNextElement(element)) {
        //::printf("Full bins: %d \n", full_bins);

        item = element;


        // critical items
        if (item >= X_M && !critical_items_STOP) {
            // flag if critical bin was found
            bool found_bin = false;
            while (!found_bin) {
                if (!critical_bins[pointer_i].present) {
                    //::printf("Bin is loaded: %d \n", critical_bins[pointer_i].present);
                    critical_bins[pointer_i].load = critical_bins[pointer_i].load - X_M + item;
                    critical_bins[pointer_i].present = true;
                    //::printf("At index: %d inputing a critical item: %d into critical bin: %d that is loaded: %d \n", pointer_i, item, critical_bins[pointer_i].load, critical_bins[pointer_i].present);
                    pointer_i++;
                    found_bin = true;
                    if (pointer_i >= M) {
                        critical_items_STOP = true;
                        ::printf("Critical bins FULL! \n");
                        break;
                    }
                } else {
                    //error occurred!
                    ::printf("ERROR! -> pointer in CRITICAL BINS: %d \n", pointer_i);
                }
            }
        }
            // harmonic items
        else if (item >= (0.5 * BIN_COVER_LOAD)) {
            int rtrn = DNF(item, bin2);
            if (rtrn == 1) {
                full_bins++;
                bin2 = 0;
            } else {
                bin2 = rtrn;
            }
        }
        else if ((0.5 * BIN_COVER_LOAD) > item && item >= (BIN_COVER_LOAD / 3)) {
            int rtrn = DNF(item, bin3);
            if (rtrn == 1) {
                full_bins++;
                bin3 = 0;
            } else {
                bin3 = rtrn;
            }

        } else if ((BIN_COVER_LOAD / 3) > item && item >= (BIN_COVER_LOAD / 4)) {
            int rtrn = DNF(item, bin4);
            if (rtrn == 1) {
                full_bins++;
                bin4 = 0;
            } else {
                bin4 = rtrn;
            }
        }

            // small items
        else {
            if (fill_critical) {
                filled_critical = 0;

                for (int j = 0; j < M; ++j) {
                    if (critical_bins[j].load < BIN_COVER_LOAD) {
                        critical_bins[j].load += item;
                        break;
                    } else {
                        filled_critical++;
                        //printf("FILLED CRITICAL: %d with load: %d \n", j, critical_bins[j].load);
                    }
                }
                if (filled_critical==M) {
                    fill_critical=false;
                }
            } else {
                int rtrn = DNF(item, small_bin);
                if (rtrn == 1) {
                    full_bins++;
                    small_bin = 0;
                } else {
                    small_bin = rtrn;
                }
            }
        }
    }

    ::printf("Full critical bins: %d \n", filled_critical);


    // add count of all covered critical bins
    full_bins += filled_critical;

    return full_bins;
}

int main(int argc, char** argv) {

    // TEMP REWORK FOR AUTOMATED WORKING
    // Debug: Print the arguments received
//    std::cout << "Arguments received to dnf:\n";
//    for (int i = 0; i < argc; ++i) {
//        std::cout << "arg[" << i << "]: " << (argv[i] ? argv[i] : "null") << std::endl;
//    }

    // params input - INP
    // 1st param: filename
    if (argc != 1) {
        exit;
    }
    string var1 = argv[1]; // path to txt file
    string var1_concentrated = "/mnt/c/Users/jakob/CLionProjects/BinPacking/python_graphs/"+var1; // full WSL path

    int count_bins;

    //Dual Next Fit (DNF) only
    count_bins = pureDNF(var1_concentrated);
//    cout<<"BINS COVERED - DNF:"<<endl;
    cout<<count_bins<<endl;

    /*
    //harmonic only
    count_bins = harmonic();
    cout<<"BINS COVERED - HARMONIC:"<<endl;
    cout<<count_bins<<endl;

    //with advice
    count_bins = advice();
    cout<<"BINS COVERED - ADVICE:"<<endl;
    cout<<count_bins<<endl;

    //with advice K=4
    count_bins = advice_k();
    cout<<"BINS COVERED - ADVICE k=4:"<<endl;
    cout<<count_bins<<endl;
    */
    return 0;
}

