#pragma once
#include <algorithm>
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
        input_mass_ += item;
        bins_[bucket] += item;
        if (bins_[bucket] >= threshold_) {
            ++covered_;
            const auto excess = static_cast<long double>(bins_[bucket]) - threshold_;
            overshoot_mass_ += excess;
            // Use float64 classification in both backends; long-double arithmetic
            // at a class edge can otherwise move a closure to an adjacent class.
            const double normalized_excess = static_cast<double>(excess) / static_cast<double>(threshold_);
            const int slot = std::min(19, std::max(0, static_cast<int>(normalized_excess * 20)));
            ++overshoot_counts_[slot];
            bins_[bucket] = 0;
        }
    }
    std::int64_t covered() const { return covered_; }
    long double input_mass() const { return input_mass_; }
    long double overshoot_mass() const { return overshoot_mass_; }
    long double unfinished_mass() const {
        long double result = 0;
        for (const auto load : bins_) result += load;
        return result;
    }
    const std::vector<std::int64_t>& overshoot_counts() const { return overshoot_counts_; }
private:
    T threshold_;
    int k_;
    bool harmonic_;
    std::vector<T> bins_;
    std::int64_t covered_ = 0;
    long double input_mass_ = 0;
    long double overshoot_mass_ = 0;
    std::vector<std::int64_t> overshoot_counts_ = std::vector<std::int64_t>(20, 0);
};
}
