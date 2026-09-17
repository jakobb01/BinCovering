#include "bincovering/baselines.hpp"
#include <charconv>
#include <iostream>
#include <string>

template<class T> T number(const std::string& token) {
    T value{};
    const auto parsed = std::from_chars(token.data(), token.data() + token.size(), value);
    if (parsed.ec != std::errc{} || parsed.ptr != token.data() + token.size())
        throw std::runtime_error("Invalid number: " + token);
    return value;
}

template<class T> std::int64_t run(bool harmonic, T threshold, int k) {
    bincovering::Baseline<T> algorithm(threshold, k, harmonic);
    std::string token;
    while (std::cin >> token) algorithm.add(number<T>(token));
    return algorithm.covered();
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
        std::int64_t count;
        if (domain == "integer") {
            auto threshold = number<std::int64_t>(argv[3]);
            if (threshold > 1000000000) throw std::runtime_error("Integer threshold too large");
            count = run(algorithm == "dual_harmonic", threshold, k);
        } else if (domain == "float64") count = run(algorithm == "dual_harmonic", number<double>(argv[3]), k);
        else throw std::runtime_error("Unknown domain");
        std::cout << "{\"covered_bins\":" << count << ",\"discarded_items\":0}\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 2;
    }
}
