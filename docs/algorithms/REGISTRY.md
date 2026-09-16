# Algorithm identities and numerical semantics

Names in the registry are stable IDs. Parameters and backends are stored separately
in every trial; filenames and timestamps never identify an algorithm variant.

| ID | Historical alias | Behavior / parameters |
| --- | --- | --- |
| `dual_next_fit` | `dnf`, `DNF_1` | One active bin; discard overshoot after covering. Python and C++ baselines. |
| `dual_harmonic` | `harmonic` | Separate next-fit states for classes with lower bounds 1/2, 1/3, …, 1/k and a small-item class; default k=5. |
| `throwbin_retire` | `ThrowBin` | Open floor(N × bin_ratio) bins; randomly choose active bins; remove covered bins; discard remaining items if all bins cover. |
| `throwbin_replace` | `ThrowBin_1` | Same initial bin count; replace covered bins with empty bins. |
| `throwbin_fixed_active` | `ThrowBin_DNF` | Ten active bins, random placement, replacement after coverage. |
| `adaptive_items` | `AdaptiveBin` | Grow total bins to ceil(items_received/2); ensure an active bin; random placement. |
| `adaptive_covered` | `AdaptiveBinCovered` | Initial bins (default 1); after covering, grow total bins to max(ceil(covered × multiplier), covered+1); default multiplier 2. |

The adaptive-items implementation uses division by 2. Some historical comments
claimed division by e or performance guarantees; those claims are not adopted.
The ThrowBin variants that allocate bins from N know the input length in advance;
this differs from adaptive-items. Ordering is always explicit in configuration.
Descending-order experiments have access to the input for sorting, which must be
accounted for when interpreting online-algorithm claims.

Randomized server variants remain experimental research strategies, not newly
proven approximation guarantees. All use float64 inputs with threshold 1.0. DNF
and harmonic also support integer inputs; harmonic boundaries use non-truncated
division. Exactly threshold-sized items are allowed; larger and nonpositive items
are rejected by the shared input layer. The native integer threshold is bounded
by 10^9 to keep its sums well inside signed 64-bit arithmetic.

Legacy `advice` and `advice_k` remain outside the registry pending validation.
The archived source revision and each run's source snapshot distinguish old
behavior from corrected implementations. Do not compare historical outputs by
algorithm label alone.
