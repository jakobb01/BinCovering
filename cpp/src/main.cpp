#include "bincovering/baselines.hpp"
#include <charconv>
#include <iostream>
#include <iomanip>
#include <string>

template<class T> T number(const std::string& token) {
    T value{};
    const auto parsed = std::from_chars(token.data(), token.data() + token.size(), value);
    if (parsed.ec != std::errc{} || parsed.ptr != token.data() + token.size())
        throw std::runtime_error("Invalid number: " + token);
    return value;
}

template<class T> void run(bool harmonic, T threshold, int k) {
    bincovering::Baseline<T> algorithm(threshold, k, harmonic);
    std::string token;
    while (std::cin >> token) algorithm.add(number<T>(token));
    const auto useful = static_cast<long double>(algorithm.covered()) * threshold;
    const auto error = algorithm.input_mass() - useful - algorithm.overshoot_mass() - algorithm.unfinished_mass();
    const bool valid = std::abs(error) <= 1e-9L * std::max(1.0L, std::abs(algorithm.input_mass()));
    std::cout << std::setprecision(17) << "{\"covered_bins\":" << algorithm.covered()
        << ",\"discarded_items\":0,\"bin_statistics\":{\"schema_version\":1,\"input_mass\":" << algorithm.input_mass()
        << ",\"useful_mass\":" << useful << ",\"overshoot_mass\":" << algorithm.overshoot_mass()
        << ",\"unfinished_mass\":" << algorithm.unfinished_mass()
        << ",\"discarded_mass\":0,\"covered_bins\":" << algorithm.covered()
        << ",\"conservation_error\":" << error << ",\"conservation_ok\":" << (valid ? "true" : "false")
        << ",\"load_unit\":\"fraction_of_covering_threshold\",\"overshoot_edges\":[";
    for (int i = 0; i <= 20; ++i) { if (i) std::cout << ','; std::cout << i / 20.0; }
    std::cout << "],\"overshoot_counts\":[";
    for (int i = 0; i < 20; ++i) { if (i) std::cout << ','; std::cout << algorithm.overshoot_counts()[i]; }
    std::cout << "]}}\n";
}

int main(int argc, char** argv) {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);
    try {
        if (argc != 5) throw std::runtime_error("Usage: bincovering-native ALGORITHM DOMAIN THRESHOLD K < items.txt");
        const std::string algorithm = argv[1], domain = argv[2];
        if (algorithm != "dual_next_fit" && algorithm != "dual_harmonic") throw std::runtime_error("Unknown algorithm");
        int k = number<int>(argv[4]);
        if (k < 2 || k > 1000) throw std::runtime_error("k must be in [2,1000]");
        if (domain == "integer") {
            auto threshold = number<std::int64_t>(argv[3]);
            if (threshold > 1000000000) throw std::runtime_error("Integer threshold too large");
            run(algorithm == "dual_harmonic", threshold, k);
        } else if (domain == "float64") run(algorithm == "dual_harmonic", number<double>(argv[3]), k);
        else throw std::runtime_error("Unknown domain");
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 2;
    }
}
