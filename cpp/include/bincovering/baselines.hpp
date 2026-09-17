#pragma once
#include <cmath>
#include <cstdint>
#include <stdexcept>
#include <vector>

namespace bincovering {
// Algorithm state is independent of command-line parsing and file I/O.
template<class T> class Baseline {
public:
    Baseline(T threshold, int k, bool harmonic)
        : threshold_(threshold), k_(k), harmonic_(harmonic) {
        if (!(threshold > 0) || !std::isfinite(static_cast<double>(threshold)))
            throw std::runtime_error("Invalid threshold");
        if (k < 2 || k > 1000) throw std::runtime_error("k must be in [2,1000]");
        bins_.assign(harmonic ? k : 1, 0);
    }
    void add(T item) {
        if (!(item > 0) || item > threshold_ || !std::isfinite(static_cast<double>(item)))
            throw std::runtime_error("Item outside (0, threshold]");
        int bucket = 0;
        if (harmonic_) {
            bucket = k_ - 1;
            for (int d = 2; d <= k_; ++d) {
                if (item >= static_cast<double>(threshold_) / d) { bucket = d - 2; break; }
            }
        }
        bins_[bucket] += item;
        if (bins_[bucket] >= threshold_) { ++covered_; bins_[bucket] = 0; }
    }
    std::int64_t covered() const { return covered_; }
private:
    T threshold_;
    int k_;
    bool harmonic_;
    std::vector<T> bins_;
    std::int64_t covered_ = 0;
};
}
