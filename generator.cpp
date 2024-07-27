#include <iostream>
#include <fstream>
#include <random>

using namespace std;

void generateRandomNumbers(const std::string& filename, int n, int max_val) {
    ofstream outFile(filename);
    if (!outFile) {
        cerr << "Failed to open file for writing.\n";
        return;
    }

    // completely randomly generating numbers
    // obtain a random number from hardware
    random_device rd;
    // seed generator
    mt19937 gen(rd());
    // define the range
    uniform_int_distribution<> distrib(1, max_val);

    for (int i = 0; i < n; ++i) {
        int random_number = distrib(gen);
        //outFile << i << " " << random_number << "\n";
        outFile << random_number << "\n";
    }

    outFile.close();
    cout << "Random numbers generated and written to " << filename << "\n";
}

int getIntFromCustomRange(int from, int to) {
    random_device rd;
    mt19937 gen(rd());
    uniform_int_distribution<int> dist(from, to);
    return dist(gen);
}

double getDoubleFromCustomRange(double from, double to) {
    random_device rd;
    mt19937 gen(rd());
    uniform_real_distribution<> dist(from, to);
    return dist(gen);
}

void generateNumbersFromOptimum(const std::string& filename, int bins_covered, int max_val) {
    ofstream outFile(filename);
    if (!outFile) {
        cerr << "Failed to open file for writing.\n";
        return;
    }

    int random_number = getIntFromCustomRange(1, (max_val-1));
    int i = 0;
    int bin_load = max_val;
    double random_bin_load_index;

    while (i!=bins_covered) {

        //cout << "random number: " << random_number << "\n";
        bin_load = bin_load - random_number;
        //cout << "bin load: " << bin_load << "\n";

        random_bin_load_index = (getDoubleFromCustomRange(0.35, 0.6));
        //cout << "i: " << i << "\n";

        if (bin_load < (random_bin_load_index * max_val)) {
            outFile << random_number << "\n";
            outFile << bin_load << "\n";
            random_number = getIntFromCustomRange(1, (max_val-1));

            bin_load = max_val;
            i++;
        } else {
            outFile << random_number << "\n";
            random_number = getIntFromCustomRange(350000, bin_load);
        }
    }
    outFile.close();
    cout << "Random numbers generated and written to " << filename << "\n";
}

void generateTrendingRandomNumbers(const std::string& filename, int n, bool upward) {
    ofstream outFile(filename);
    if (!outFile) {
        std::cerr << "Failed to open file for writing.\n";
        return;
    }

    // Seed with a real random value, if available
    random_device rd;
    // Initialize the random number generator with a seed
    mt19937 gen(rd());
    // Define a distribution range for random bounces
    uniform_int_distribution<> bounce(-100000, 100000);
    // Define the range for the trend line
    int trend_start = upward ? 1 : 1000000;
    int trend_end = upward ? 1000000 : 1;

    // Calculate the trend step
    double trend_step = (trend_end - trend_start) / static_cast<double>(n);

    for (int i = 0; i < n; ++i) {
        // Calculate the trend value
        double trend_value = trend_start + i * trend_step;
        // Add a random bounce to the trend value
        int random_number = static_cast<int>(trend_value) + bounce(gen);
        // Ensure the random number is within bounds
        if (random_number < 1) random_number = 1;
        if (random_number > 1000000) random_number = 1000000;
        //outFile << i << " " << random_number << "\n";
        outFile << random_number << "\n";
    }

    outFile.close();
    cout << "Optimum strategy numbers generated to: " << filename << "\n";
}


int main() {
    // length of array of numbers
    int n;
    string filename;
    int max_load = 1000000;

    n = 100000;
    filename = "output.txt";
    string filename_up = "output_upwards.txt";

    //generateRandomNumbers(filename, n, max_load);

    //generateTrendingRandomNumbers(filename_up, n, true);

    generateNumbersFromOptimum("opt_output.txt", 300, max_load);

    return 0;
}
