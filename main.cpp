#include <iostream>
#include <random>

using namespace std;

// size of items will be int 1 to 1000 to not get weird float rounding
const int BIN_COVER_LOAD = 1000;
const int SEQ_LENGTH = 10000;

// M and X_M value that will be used as an advice and calculated in generator
const int M = 1000;
int X_M = 0.7*(BIN_COVER_LOAD);

// generator for random array for specific range def in const
// todo: calculate M and X_M in generator
int* generator() {
    static int p[SEQ_LENGTH];
    random_device rd; // obtain a random number from hardware
    mt19937 gen(rd()); // seed the generator
    uniform_int_distribution<> distr(1, 1000); // define the range
    for (int i = 0; i < SEQ_LENGTH; ++i) {
        p[i] =  distr(gen);
    }
    return p;
}

// DNF - Dual Next Fit -> 0 = error; 1 = 1 bin full; x = bin load
int DNF(int item, int bin) {
    if (bin < 0) {
        return 0;
    }
    if (bin < BIN_COVER_LOAD) {
        bin += item;
        return bin;
    } else {
        return 1;
    }
}

int pureDNF(int seq[SEQ_LENGTH]) {
    int bin = 0;
    int full_bins = 0;
    int val;

    for (int i = 0; i < SEQ_LENGTH; ++i) {
        val = DNF(seq[i], bin);
        if (val == 0) {
            return 0;
        } else if (val == 1) {
            full_bins++;
            bin = 0;
        } else {
            bin = val;
        }
        cout<<"BINS COVERED:"<<full_bins<<endl;
    }
    if (DNF(0, bin) == 1) {
        full_bins++;
    }
    return full_bins;
}

// harmonic - returns number of packets
// todo: check if items actualy follow harmonic distribution!
int harmonic(int seq[SEQ_LENGTH]) {

    int item;
    int full_bins=0;
    // k = 5
    int big_bin=0, bin3=0, bin4=0, bin5=0, small_bin=0;

    // iterate through each item in input sequence
    for (int i = 0; i < SEQ_LENGTH; ++i) {
        item = seq[i];

        // big items
        if (item > (0.5*BIN_COVER_LOAD)) {
            int rtrn = DNF(item, big_bin);
            if (rtrn == 1) {
                full_bins++;
                big_bin = 0;
            } else {
                big_bin = rtrn;
            }
        }
        // harmonic bins
        else if ((0.5*BIN_COVER_LOAD) > item > (1/3 * BIN_COVER_LOAD)) {
            int rtrn = DNF(item, bin3);
            if (rtrn == 1) {
                full_bins++;
                bin3 = 0;
            } else {
                bin3 = rtrn;
            }
        } else if ((1/3 * BIN_COVER_LOAD) > item > (1/4 * BIN_COVER_LOAD)) {
            int rtrn = DNF(item, bin4);
            if (rtrn == 1) {
                full_bins++;
                bin4 = 0;
            } else {
                bin4 = rtrn;
            }
        } else if (item > (1/5 * BIN_COVER_LOAD)) {
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
int advice(int seq[SEQ_LENGTH]) {

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


    for (int i = 0; i < SEQ_LENGTH; ++i) {
        //::printf("Full bins: %d \n", full_bins);

        item = seq[i];


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
        } else if ((BIN_COVER_LOAD / 4) > item && item >= (BIN_COVER_LOAD / 5)) {
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

int main() {

    int* ptr_p;
    ptr_p = generator();

    for(int i=0 ; i<SEQ_LENGTH; i++)
        cout<<ptr_p[i]<<endl;

    int count_bins = pureDNF(ptr_p);

    cout<<"BINS COVERED - DNF:"<<endl;
    cout<<count_bins<<endl;

    count_bins = harmonic(ptr_p);

    cout<<"BINS COVERED - HARMONIC:"<<endl;
    cout<<count_bins<<endl;

    count_bins = advice(ptr_p);

    cout<<"BINS COVERED - ADVICE:"<<endl;
    cout<<count_bins<<endl;


    return 0;
}

