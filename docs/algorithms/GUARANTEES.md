# Algorithm guarantees

This document describes the mathematical guarantees supported by the current
algorithm rules. It separates published results, conservative bounds derived
here, restricted-input results, and experimental strategies. Algorithm IDs and
historical identities are defined in [REGISTRY.md](REGISTRY.md).

## Model and interpretation

Let the covering threshold be `T > 0`. Normalize each item by T, so its size is in
`(0, 1]`. Let `A` be the number of bins covered by the algorithm, `S` the normalized
total input mass, and `OPT` the maximum number of bins that any feasible covering
can cover. Each input item may be placed only once. A bin is covered only when its
actual load reaches at least 1; virtual reservations are not actual load.

These proofs assume exact arithmetic and a successfully completed execution.
They do not count unfinished bins as covered. Overshoot remains part of its closed
bin; replacing a load slot means starting a new physical bin, not reusing items.

Since every covered bin requires at least unit mass, `OPT <= floor(S)`. The mass
upper bound can exceed OPT. A dashboard percentage relative to that bound is not
a measured percentage of OPT. The `big_items` and `complementary_pairs` generators
provide certified optima under their validated construction rules; the historical
`one_over_n` and `optimal_uniform_legacy` construction targets do not provide such
certificates. See [the migration guide](../MIGRATION.md#distribution-and-randomness-contracts).

An asymptotic lower bound has the form `A >= c * OPT - b`, where b is independent
of input length. Fix the algorithm parameters when interpreting this statement.
An additive term involving k or m is not a constant if that parameter grows with
the input. Such a bound is not a promise of exactly c times OPT on every small
instance, nor a prediction of the average result on a chosen distribution.

A bound that holds for **every placement path** also holds in expectation over
random choices. It does not determine the tight expected competitive ratio or a
distribution-specific guarantee. The published deterministic upper-bound results
are not automatically upper bounds for randomized algorithms.

## Guarantee matrix

All finite inequalities below use the exact-arithmetic model above. The baseline
1/2 results are established in the literature [1]; the finite inequalities and
other conservative bounds are proved below from the current placement rules.

| Algorithm ID | Supported claim | Scope |
| --- | --- | --- |
| `dual_next_fit` | Classical asymptotic 1/2; finite bound `A > (OPT - 1) / 2`. | One unfinished bin; any valid item sequence. |
| `dual_harmonic` | Classical asymptotic 1/2 for fixed k; finite bound `A > (OPT - k) / 2`. | At most k unfinished bins; k defaults to 5. |
| `throwbin_fixed_active` | Lower bound `A > (OPT - 10) / 2`, hence at least 1/2 asymptotically. | Every placement path; this is a conservative implementation-derived lower bound, not a tightness result. |
| `adaptive_covered` | At defaults, `A >= OPT / 3`. For general parameters, `A > (OPT - B0 - 1) / (1 + max(mu, 1))`. | `B0 = initial_bins`, `mu = multiplier`; defaults are B0=1, mu=2. Derived lower bounds, with no tightness claim. |
| `adaptive_items` | `A = floor(N / 2) = OPT` if every item is strictly between 1/2 and 1. | Restricted input only. No general competitive ratio is established here. |
| `throwbin_retire` | No general competitive ratio is established here. | Experimental; knows N, opens `floor(N * bin_ratio)` bins, and may discard later items. |
| `throwbin_replace` | No general competitive ratio is established here. | Experimental; knows N and maintains `floor(N * bin_ratio)` active slots. |
| `advice_reserved` | Conservative fallback `A > (OPT - m - 5) / 2`. | Fixed supplied m, k=5, and reservation fraction in [1/2,1]. Does not establish the paper's improved-advice theorem or a bit budget. |
| `advice_reserved_k4` | Conservative fallback `A > (OPT - m - 4) / 2`. | Same supplied-parameter limitation, with k=4. |
| Custom Builder algorithms | No automatic optimality or competitiveness claim. | The runtime enforces its interface and physical accounting; a sample preview does not prove a theorem. |

## Proofs and implementation mapping

### Bounded unfinished bins: DNF, harmonic, and fixed-ten ThrowBin

An ordinary closed bin has load below 2: before its final item the load was below
1, and the final item is at most 1. If the algorithm retains every item and has
at most q unfinished bins, each below 1, then

```text
OPT <= S < 2 * A + q
A > (OPT - q) / 2
```

For DNF, q=1. For harmonic, q=k. The registry performs next-fit independently in
each harmonic class: `[1/2,1]`, `[1/3,1/2)`, ..., `[1/k,1/(k-1))`, and `(0,1/k)`.
Each class has one load slot, reset only after coverage. The native baseline uses
the same placement rules. See [registry.py](../../src/bincovering/algorithms/registry.py)
and [baselines.hpp](../../cpp/include/bincovering/baselines.hpp). The lower-bound
proof uses the number of slots and immediate closure, independently of the class
in which a boundary item is placed. Classical DNF and fixed-k harmonic results
are discussed in [1], Section 2, Theorem 1.

[ThrowBin_DNF.py](../../src/bincovering/algorithms/ThrowBin_DNF.py) maintains ten
active slots, immediately replacing a covered bin with an empty bin. Thus q=10.
Random selection does not change the mass argument: the bound holds for every
sequence of selected slots. This proves an asymptotic lower bound of 1/2, without
establishing a matching upper bound for its expected behavior.

### AdaptiveBinCovered

[AdaptiveBinCovered.py](../../src/bincovering/algorithms/AdaptiveBinCovered.py)
retains covered bins and opens additional bins as the covered count grows. With
`B0 = initial_bins` and `mu = multiplier > 0`, its total bin count B follows

```text
B = max(B0, ceil(mu * A), A + 1)
```

The targets are nondecreasing, so retaining earlier opened bins preserves this
formula. There are A closed bins of load below 2 and `B - A` unfinished bins of
load below 1. Every item is retained, hence `S < 2*A + (B-A) = A+B`.

At defaults B0=1 and mu=2, if A>0 then B=2*A and `OPT <= S < 3*A`. If A=0, there
is one unfinished bin with load below 1, so OPT=0. Therefore `A >= OPT/3` in both
cases. This is a conservative lower bound, not a statement that 1/3 is tight.

For the general parameters, use

```text
B <= max(mu, 1) * A + B0 + 1
OPT <= S < (1 + max(mu, 1)) * A + B0 + 1
A > (OPT - B0 - 1) / (1 + max(mu, 1))
```

B0 and mu must stay fixed for the additive term to be an asymptotic constant.
With B0=1 and `0 < mu <= 1`, B=A+1, so there is exactly one active bin and the
strategy follows DNF. The general inequality above is deliberately weaker than
that special case.

### AdaptiveBin on big items

[AdaptiveBin.py](../../src/bincovering/algorithms/AdaptiveBin.py) grows total bins
to `ceil(items_received/2)` and opens a bin if none is active. Suppose all N items
are strictly between 1/2 and 1. One item cannot cover a bin, but any two can.

After each completed pair, all existing bins are covered. The next odd-indexed
item opens exactly one new bin; the next even-indexed item covers it. Inductively
the algorithm covers `floor(N/2)` bins, independently of randomness. OPT also
equals `floor(N/2)`, since every covered bin needs at least two items and any
pair suffices. This proves the restricted-input result, not a result for uniform
or complementary inputs.

### Supplied-parameter advice fallback

[advice.py](../../src/bincovering/algorithms/advice.py) keeps m reserved bins and
k harmonic slots (k=5 or k=4). Write x for the reservation fraction, with
`1/2 <= x <= 1`. Before a critical item arrives, small items of size below 1/k
are accepted only while the virtual load is below 1. Their accumulated real load
therefore stays below `1 - x + 1/k`, which is below 1 for these k values.

When a critical item arrives, it is at most 1, so the resulting real load is
below `2 - x + 1/k < 2`. If the bin still needs small items, it closes at the
first actual load of at least 1, also below 2. A reserved bin receives one critical
item at most; the small-item cursor skips it once filled, so a covered bin is
never counted twice. A virtual reservation alone is never counted as coverage.

The harmonic bins also close below 2. The code retains each real input item,
including the one that discovers all reservations are filled. At most m+k bins
remain unfinished, so

```text
OPT <= S < 2 * A + m + k
A > (OPT - m - k) / 2
```

For fixed m and k this gives an asymptotic fallback lower bound of 1/2. If m grows
with N, the additive term is no longer constant. This proof establishes neither
an improved-advice ratio nor an oracle or advice-bit complexity.

### Why length-scaled slots do not inherit the fixed-ten proof

Replacement ThrowBin has `q = floor(N * bin_ratio)` unfinished slots. Substituting
that q into the mass proof leaves an input-length-dependent additive term.
Retirement ThrowBin can also discard items once its bins cover, so its total input
mass must account for those discarded items. Neither argument establishes a
general positive competitive ratio for these variants. Their experimental status
does not mean their exact expected competitive ratios have been determined.

## The advice paper and the implemented variants

Brodnik, Nilsson and Vujovic [2], Theorem 2, establish for k=4, with exact
oracle-selected parameters and the paper's strategy,

```text
A >= (2/3) * OPT - 173/60
advice complexity: O(b + log N)
```

Here b describes the bits required to represent a rational input value. Section 3
selects m and the corresponding order-statistic value x_m using the entire input;
the advice model uses self-delimiting encoding. These requirements are part of
the theorem.

The registered variants accept supplied m/x_m. They do not implement that oracle,
encoded tape, or rational execution. Their default values m=103, x_m=0.8 are not
certified for each input. The paper's 2/3 theorem and bit bound are therefore not
guarantees of these variants. Matching k=4 alone is insufficient; the k=5 identity
also does not inherit the k=4 result. See [the corrected-advice migration notes](../MIGRATION.md#corrected-advice-variants).

## Numerical execution and input access

Python and native integer DNF/harmonic perform exact integer load addition within
the validated native limits. The migrated randomized and advice strategies run
with float64 and threshold 1.0. Floating-point addition or parameter calculations
can differ from the exact arithmetic used in these proofs. No implicit epsilon
or float-to-integer rescaling is applied.

The runner computes mass bounds from the exact representations of the supplied
numbers. When computed coverage exceeds its recorded reference, it records a
numerical warning and omits the ratio. That check does not identify every possible
rounding disagreement or certify each float64 placement as a real-arithmetic
covering. Backend parity and tolerant mass-conservation checks are useful
implementation evidence; they are not exact-arithmetic certificates.

Sorting an input ascending or descending uses the entire sequence. Length-scaled
ThrowBin receives N before processing. Record those facts when interpreting an
experiment as online, offline, or length-aware. A bound proved for every sequence
still applies to a sorted sequence in its stated arithmetic model, but observing
good sorted-input performance does not prove an unknown-future online guarantee.
Custom Builder access declarations describe the enforced interface, not a
competitiveness theorem. See [BUILDER_LANGUAGE.md](../BUILDER_LANGUAGE.md).

## Concrete limits of broader performance claims

These inputs have exactly representable sizes and certified optima. They describe
actual implementation behavior, not a tight asymptotic analysis.

- AdaptiveBin on descending `[0.875, 0.75, 0.25, 0.125]` covers one bin. OPT is two
  via `(0.875,0.125)` and `(0.75,0.25)`. There is only one active bin at each step,
  so the outcome is independent of randomness. This refutes a universal 100% claim
  on complementary inputs of the historical OneOverN form.
- On 4,096 items each of size `1/64`, OPT is 64. At defaults, AdaptiveBin and both
  length-scaled ThrowBin variants cover zero bins for each seed from 0 through 4.
  These adverse executions do not establish their exact expected competitive
  ratios. An observed uniform-input percentage is likewise not a general theorem.
- On 1,000 items `1/8` followed by 1,000 items `7/8`, OPT is 1,000. Both advice
  variants at defaults cover 650 bins. The paper's k=4 bound would require at least
  `2/3 * 1000 - 173/60`, or at least 664 bins. Arbitrary supplied parameters do not
  inherit that bound; physical mass accounting succeeds on this input.

Preserve stable algorithm identities, recorded parameters, input order and source
provenance when comparing these results with historical outputs. A finite test
suite can catch a disagreement with a proof's implementation assumptions, but it
does not replace a proof over all valid inputs.

## References

1. Marie G. Christ, Lene M. Favrholdt and Kim S. Larsen,
   [*Online bin covering: Expectations vs. guarantees*](https://imada.sdu.dk/u/kslarsen/Papers/Resources/CFL14j/paper.pdf),
   *Theoretical Computer Science* 556 (2014), 71–84.
   Section 2, Theorem 1, supplies the classical deterministic result; its standard
   input domain is `(0,1)`. The finite mass proofs above also allow unit items.
2. Andrej Brodnik, Bengt J. Nilsson and Gordana Vujovic,
   [*Online Bin Covering with Exact Parameter Advice*](https://arxiv.org/pdf/2309.13647),
   arXiv:2309.13647 (2023). Section 3 describes oracle parameter selection and
   Theorem 2 gives the k=4 ratio and advice bound.
