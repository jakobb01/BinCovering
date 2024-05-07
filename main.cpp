#include <iostream>
#include <vector>
#include <ctime>
#include <time.h>

using namespace std;

// size of items will be int 1 to 1000 to not get weird float rounding
const int BIN_COVER_LOAD = 1000;
const int SEQ_LENGTH = 1000;

// M and X_M value that will be used as an advice and calculated in generator
const int M = 10;
int X_M;

// generator for random array for specific range def in const
// todo: calculate M and X_M in generator
int* generator() {
    static int p[SEQ_LENGTH];
    srand(time(0));
    for (int i = 0; i < SEQ_LENGTH; ++i) {
        p[i] =  (rand() % 1000);
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
    Bin critical_bins[M] = {X_M, false};

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
        cout<<full_bins<<endl;

        item = seq[i];


        // critical items
        if (item >= X_M && !critical_items_STOP) {
            // flag if critical bin was found
            bool found_bin = false;
            while (!found_bin) {
                if (!critical_bins[pointer_i].present) {
                    critical_bins[pointer_i].load = critical_bins[pointer_i].load - X_M + item;
                    critical_bins[pointer_i].present = true;
                    pointer_i++;
                    found_bin = true;
                } else {
                    if (pointer_i == SEQ_LENGTH) {
                        break;
                    }
                    pointer_i++;
                }
            }
            if (!found_bin) {
                // error?
                // put it into harmonic?
                critical_items_STOP = true;
                cout<<"ERROR on critical bins!"<<endl;
            }
        }
            // harmonic items
        else if (X_M > item > (0.5 * BIN_COVER_LOAD)) {
            int rtrn = DNF(item, bin2);
            if (rtrn == 1) {
                full_bins++;
                bin2 = 0;
            } else {
                bin2 = rtrn;
            }
        }
        else if ((0.5 * BIN_COVER_LOAD) > item > (1 / 3 * BIN_COVER_LOAD)) {
            int rtrn = DNF(item, bin3);
            if (rtrn == 1) {
                full_bins++;
                bin3 = 0;
            } else {
                bin3 = rtrn;
            }
        } else if ((1 / 3 * BIN_COVER_LOAD) > item > (1 / 4 * BIN_COVER_LOAD)) {
            int rtrn = DNF(item, bin4);
            if (rtrn == 1) {
                full_bins++;
                bin4 = 0;
            } else {
                bin4 = rtrn;
            }
        } else if (item > (1 / 5 * BIN_COVER_LOAD)) {
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
                        cout<<"J:"<<j<<endl;
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

