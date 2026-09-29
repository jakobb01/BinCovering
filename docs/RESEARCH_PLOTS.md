# Research plots

## Approved dashboard views

Jakob's September 29 review selected research overview, ordering sensitivity,
ThrowBin parameter sweeps, and mass accounting. The follow-up review approved
target achievement/reliability and paired DNF, including an adjustable minimum
coverage target. Size/runtime and distribution robustness were skipped.

Open **Plot** beside a saved experiment. Results open in a dialog with Plot,
Summary, and Provenance tabs. Choose a plot, algorithm, and overview panel without
scrolling through the experiment list. Use zoom/fit or download PNG/SVG. Closing
it restores the previous position and focus.

**Research overview** restores the historical three-panel layout for one selected
algorithm:

1. Input size histogram, in 20 classes after division by the covering threshold.
   Heights are percentages of items. Fixed inputs are counted once; fresh inputs
   are pooled by item count, independently of the number of algorithms.
2. Coverage in each trial, with median and the middle 50% of observations.
3. Frequency distribution of coverage across trials, with quartiles and median.
   For a constant reference, boundaries align to covered-bin counts, with wider
   classes when the range would otherwise exceed 50 classes.

Each panel can also be opened on its own. `bincovering plot outputs/<run>` produces
an overview for the default algorithm. PNG, SVG, and JSON are saved under `figures/`.

Coverage is `100 × covered bins / reference`. The recorded reference is certified
OPT when available, otherwise the mass upper bound `floor(sum(items)/threshold)`.
A percentage of an upper bound is not a measured percentage of OPT or proof of a
competitive ratio. Failed observations, zero denominators, and numerical warnings
are excluded and counted. Figure trial numbers start at 1; CSV IDs start at 0.

New runs retain compact hash-tagged input histograms under `input-statistics/`.
Older runs use verified saved inputs, or explicitly show missing input data.
Plotting never regenerates inputs or reruns algorithms.

## Target achievement and paired DNF

**Target achievement** answers: how often did this algorithm reach my minimum
coverage target? Choose a target from 0 to 100%. The table gives the number and
percentage of valid observed trials with coverage **at least** that target. A
descending curve in each algorithm's panel shows how the answer changes as the
target rises. The target guide and table update together; downloaded figures retain
the chosen target. This describes observed results, not a forecast or confidence
interval. Fixed-input permutations remain conditional on their saved multiset.
Distinct algorithm parameters, backends, and experiment contexts stay separate.

**Paired improvement over DNF** shows `candidate covered bins − DNF covered bins`
for each pair on identical inputs. Negative values are losses (red), zero is a
tie (gray), and positive values are improvements (blue). Each panel identifies the
candidate and DNF backend, and reports loss/tie/gain counts. Bar heights are the
percentage of valid pairs in each class; the horizontal axis counts extra bins,
not percentage points of coverage.

Pairs require matching ordered input hashes, trial IDs, domain, threshold, and
reference. DNF from the same experiment is preferred, then matching selected
experiments; a matching backend is preferred. Conflicting DNF counts and invalid
or unmatched observations are excluded and reported. A similar name or matching
trial number alone cannot establish a pair. Select multiple experiments to pair
saved candidates with compatible DNF runs; no algorithms are rerun.

## Controlled studies

Select saved experiments, choose **Ordering sensitivity** or **ThrowBin parameter
sweep** in the Study plots control, and open the plot. Files are saved under the
ignored `outputs/.comparisons/` directory. Algorithms, parameters, and backends
remain separate; ranges show descriptive IQR, not confidence intervals.

**Ordering sensitivity** requires at least two ordering/swap settings with matching
base input hashes for every trial. Swap-only studies use a numeric swap-count axis
when the swap method agrees. Other orderings are categorical, without interpolated
lines. For example:

```bash
bincovering run --multirun name=order-study dataset_mode=fixed ordering=swaps swaps=0,100,1000 n=1000 trials=30 seed=42
```

Fixed-input results are conditional on that input; many permutations do not provide
independent samples of the generator. Use independently generated base inputs to
support claims about a distribution. Swap count is not a percentage of items moved.

**ThrowBin parameter sweeps** compare `bin_ratio` for retirement and replacement
variants, separately. They show median coverage heatmaps over N and ratio, and
ratio sensitivity with IQR. Every displayed N requires at least two ratios on
identical recorded trial inputs and references. Other algorithm settings, backend,
generator, domain, and ordering must agree within each comparison family. Different
seeds or missing trial pairs are rejected. Missing cells are masked, never zero.
Multiple ratio variants may be saved in one experiment, which naturally gives them
identical trial inputs:

```bash
bincovering run name=throwbin-ratios n=1000 trials=30 seed=42 'algorithms=[{id:ThrowBin_1,params:{bin_ratio:0.2}},{id:ThrowBin_1,params:{bin_ratio:0.4}},{id:ThrowBin_1,params:{bin_ratio:0.6}}]'
```

The existing CLI `bincovering compare <run-a> <run-b> --plot <path>` remains
available for earlier paired-DNF/ordering figures. Its difference axis uses
percentage points; the newly approved dashboard paired view uses extra bins.

## Mass accounting

New runs retain compact `bin-statistics/<trial>-<algorithm-index>.json` records:
actual input mass, useful covered mass, closure overshoot, unfinished-bin mass,
discarded mass, and a 20-class closure-overshoot histogram. Input hash, algorithm,
parameters, backend, and trial identity tie each record to its trial CSV row.
Python algorithms and native DNF/harmonic record these measurements during solving.
Artifact writes occur outside the measured solve duration; instrumentation remains
part of that duration and is described in the manifest.

**Mass accounting** shows each component as a percentage of actual input mass,
pooled across the recorded trials. Useful mass is covered bins × threshold;
overshoot is the excess above the threshold at closure. Retirement ThrowBin
discards items directed to retired bins; replacement ThrowBin keeps accepting into
replacement bins. These are distinct algorithms and are labelled separately.
The second panel shows closure overshoot as percentages of covered bins, normalized
by the threshold. Its upper edge represents one threshold of excess.

The reader independently checks conservation and record identity. Invalid,
incomplete, or inconsistent measurements are excluded and counted. Older runs
without measurements display an explanation; saved input sequences alone cannot
recover historical placements. Create a new run to obtain these measurements.

## Follow-up review

The original gallery was repurposed to the two **Adjust** examples, now both
approved in the saved follow-up review. The first uses separate
curves and an interactive table explaining how often coverage reaches a chosen
target. The second shows extra covered bins on identical inputs, with red losses,
gray ties, and blue improvements in separate panels.

```bash
python -m bincovering.web.review --root outputs/plot-proposals-20260929 --port 5001
# Open http://127.0.0.1:5001
```

**Submit notes** now explicitly writes `user-review.json` on the local server;
browser drafts alone are not submitted. Other decisions are preserved. The initial
eight decisions are retained in `approved-review.json`. QA captures are never
imported as researcher decisions. Gallery artifacts and submissions remain ignored
research outputs; the service implementation is versioned.
