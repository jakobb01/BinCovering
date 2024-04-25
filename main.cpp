#include <iostream>
#include <vector>

// size of items will be int 1 to 1000 to not get weird float rounding
const int BIN_COVER_LOAD = 1000;
const int SEQ_LENGTH = 100;
// todo: implement simple algorithms first, make them generic, as they will be used in algo w/ advice

// generator for random array for specific range def in const
int[] generator() {
    
}

// DNF - Dual Next Fit -> 0 = error; 1 = 1 bin full; x = bin load
int DNF(int item, int bin) {
    if (bin < 1) {
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
    int full_bins = -1;
    int val = 1;

    for (int i = 0; i < SEQ_LENGTH; ++i) {
        if (val == 0) {
            return 0;
        } else if (val == 1) {
            full_bins++;
            bin = seq[i];
        } else {
            bin = val;
        }
        val = DNF(seq[i], bin);
    }
    return full_bins;
}

int advice(int m, double x_m, int k, double seq[7]) {
    //all input in parameters

    //prepare bins

    // critical bins
    // todo: critical bins will be struct
    std::vector<double> critical_bins(m, x_m);
    // t-bins -> 2D vector
    // todo: t-bins & small bins - we will just count how many we will close, one variable needed
    std::vector<double> t(1, 0.0);
    std::vector<std::vector<double> > t_bins(k, t);
    // small bins
    std::vector<double> small_bins(1, 0);


    // todo: iterator for feeding 'items' one-by-one
    for (int i = 0; i < ( 7 ); ++i) {

        double v = seq[i];
        std::cout<<v<<" ";

        if (v >= x_m) {
            for (int j = 0; j < critical_bins.size(); ++j) {
                // todo: when item is put in critical bin, mark that this bin cannot be used anymore and correctly update load
                if (critical_bins[j] == x_m) {
                    critical_bins[j] = critical_bins[j]-x_m;
                    critical_bins[j] = v;
                    break;
                }
            }
            continue;
        }

        // t-bins
        if (x_m > v >= 1/k) {
            // todo -> place v in correct container (1/2 - 1/3; 1/3 - 1/4; 1/4 - 1/k   etc...)

            // find t-bin for 1/2, fill it
            for (int j = 0; j < t_bins[0].size(); ++j) {
                if (t_bins[0][j] < 1) {
                    t_bins[0][j] += v;
                }
            }
        }

        // small
        if (v < (1/k)) {
            int check = 0;
            for (int j = 0; j < critical_bins.size(); ++j) {
                if (critical_bins[j] < 1) {
                    critical_bins[j] += v;
                    check = 1;
                }
            }
            // if critical bins are all covered
            if (check == 0) {
                // todo: implement DNF for small bins
                small_bins[0] = v;
            }
        }
    }

    std::cout<< "CRITICAL BINS"<<std::endl;
    for (int i = 0; i < critical_bins.size(); ++i) {
        std::cout<<critical_bins[i]<<" "<<std::endl;
    }
    std::cout<< "T BINS"<<std::endl;
    for(int i=0;i<t_bins.size();i++){
        for(int j=0;j<t_bins[i].size();j++)
            std::cout<<t_bins[i][j]<<" ";
        std::cout<<std::endl;
    }
    std::cout<< "SMALL BINS"<<std::endl;
    for (int i = 0; i < small_bins.size(); ++i) {
        std::cout<<small_bins[i]<<" "<<std::endl;
    }

    return 0;
}


int main() {

    double seq[] = {0.1, 0.23, 0.4, 0.5, 0.6, 0.01, 0.34};

    advice(2, 0.5, 4, seq);

    return 0;
}

