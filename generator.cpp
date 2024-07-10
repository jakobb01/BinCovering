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
        outFile << random_number << "\n";
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
    // Define a small distribution range for random bounces
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
        outFile << random_number << "\n";
    }

    outFile.close();
    cout << "Trending random numbers generated and written to " << filename << "\n";
}


int main() {
    // length of array of numbers
    int n;
    string filename;

    n = 1000;
    filename = "output.txt";
    string filename_up = "output_upwards.txt";

    generateRandomNumbers(filename, n, 1000000);

    generateTrendingRandomNumbers(filename_up, n, true);

    return 0;
}
