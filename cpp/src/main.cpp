#include <cmath>
#include <cstdint>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

template<class T> T number(const std::string& token) {
    std::istringstream input(token);
    T result{};
    if (!(input >> result) || input.peek() != EOF) throw std::runtime_error("Invalid number: " + token);
    return result;
}

template<class T> std::int64_t solve(const std::string& algorithm, T threshold, int k) {
    if (!(threshold > 0) || !std::isfinite(static_cast<double>(threshold)))
        throw std::runtime_error("Invalid threshold");
    std::vector<T> bins(algorithm == "dual_next_fit" ? 1 : k, 0);
    std::int64_t covered = 0;
    std::string token;
    while (std::cin >> token) {
        T item = number<T>(token);
        if (!(item > 0) || item > threshold || !std::isfinite(static_cast<double>(item)))
            throw std::runtime_error("Item outside (0, threshold]");
        int bucket = 0;
        if (algorithm == "dual_harmonic") {
            bucket = k - 1;
            for (int d = 2; d <= k; ++d) {
                if (item >= static_cast<double>(threshold) / d) { bucket = d - 2; break; }
            }
        }
        bins[bucket] += item;
        if (bins[bucket] >= threshold) { ++covered; bins[bucket] = 0; }
    }
    return covered;
}

int main(int argc, char** argv) {
    try {
        if (argc != 5) throw std::runtime_error("Usage: bincovering-native ALGORITHM DOMAIN THRESHOLD K < items.txt");
        const std::string algorithm = argv[1], domain = argv[2];
        if (algorithm != "dual_next_fit" && algorithm != "dual_harmonic") throw std::runtime_error("Unknown algorithm");
        int k = number<int>(argv[4]);
        if (k < 2 || k > 1000) throw std::runtime_error("k must be in [2,1000]");
        std::int64_t count;
        if (domain == "integer") {
            auto threshold = number<std::int64_t>(argv[3]);
            if (threshold > 1000000000) throw std::runtime_error("Integer threshold too large");
            count = solve(algorithm, threshold, k);
        } else if (domain == "float64") count = solve(algorithm, number<double>(argv[3]), k);
        else throw std::runtime_error("Unknown domain");
        std::cout << "{\"covered_bins\":" << count << ",\"discarded_items\":0}\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 2;
    }
}
