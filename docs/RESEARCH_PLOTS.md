# Research plots

## Implemented

`bincovering plot <run>` and the web Plot action produce the same three-panel
figure, plus SVG and machine-readable plot data under the run's `figures/` folder:

1. **Coverage each round**, as 100 × covered bins / reference. Each point is one
   trial, with algorithms evaluated on the same ordered input in that trial.
2. **Coverage distribution across rounds**, with median, quartiles, 1.5-IQR
   whiskers, outliers, and mean. These describe variability, not confidence intervals.
3. **Generated item-size histogram**, in 20 equal-width classes after division by
   the covering threshold. Heights are percentages of items, not probability density.
   Trials are pooled by item count and each input is counted once per trial, regardless
   of algorithm count. Fixed-input trials repeat the same multiset; they are not
   independent samples of the generator.

Reference means certified OPT when available, otherwise the mass upper bound
floor(sum(items)/threshold). A percentage of that bound is not a measured percentage
of OPT, nor a proof of a competitive ratio. The upper bound can be unattainable.
Failed observations, zero denominators, and numerical inconsistencies are excluded
and counted visibly. Trial numbers start at 1 in the figure (CSV IDs start at 0).

New runs retain compact per-trial histograms under `input-statistics/`, including
input hashes. Full sequences remain optional. Older runs use hash-checked saved
inputs when available; otherwise the figure explicitly reports missing input data.
Plotting never regenerates sequences using a possibly changed generator.

Here, "round" means a trial. The figure does not show individual bin loads or the
process of closing bins as each item arrives. Those require additional instrumentation.

## Recommended next plots (proposals, not implemented)

Research distinguishes worst-order, random-order, and distribution-dependent
performance; a single average cannot express all these questions. See
[Christ, Favrholdt and Larsen](https://arxiv.org/abs/1309.6477) and
[Fischer and Röglin](https://arxiv.org/abs/1512.04719).
The following are project-specific recommendations based on those distinctions.

| Priority | Plot | Research question / experimental design |
| --- | --- | --- |
| 1 | Paired advantage over DNF, in percentage points | On identical trial inputs, does the new algorithm improve coverage consistently? Plot the distribution of paired differences with a zero line. Keep backend and parameter identities separate. |
| 2 | Coverage versus swap count or input order | How much does performance depend on ordering? Hold the base multiset fixed, vary ordering, and repeat random permutations. Show median and quantile bands. Swap count is not percentage of items moved. |
| 3 | Coverage and runtime versus N, in separate panels | Does quality stabilize as inputs grow, and what does that cost? Use multiple independent inputs per N; report process/serialization overhead in native timings. |
| 4 | Empirical CDF of coverage | What fraction of trials falls below a chosen quality threshold? Useful for reliability and comparing lower tails without choosing histogram bins. |
| 5 | Overshoot and unfinished-bin mass per round | Why are bins lost? Requires recording actual loads at bin closure, residual mass, and discarded mass, consistently across Python and C++ backends. |

A box plot summarizes quartiles, spread, and outliers; the accompanying round points
keep individual results visible. See the [NIST box-plot guide](https://itl.nist.gov/div898/handbook/eda/section3/boxplot.htm).
Do not label quantile bands as confidence intervals. For fixed-input permutations,
conclusions are conditional on that input; multiple independently generated base
inputs are needed to generalize to a distribution.
