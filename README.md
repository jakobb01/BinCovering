# BinCovering

Academic research tools for **bin covering**: maximize the number of bins whose
item load reaches the covering threshold. The project has a shared Python
experiment runner, Hydra configuration, a local web interface, and C++ baselines.

## Repository layout

```text
src/bincovering/   algorithms, generators, runner, CLI, and web application
configs/          versioned experiment configurations
cpp/              native implementation, headers, and historical C++ references
tests/            automated tests and small regression references
tools/            application and browser-test container definitions
docs/             algorithm definitions and migration documentation
outputs/          ignored results, figures, exports, and retained historical files
```

`build/`, `.venv/`, and `.tools/` are ignored local build/environment directories.
The old `server/`, `python_graphs/`, `web_interface/`, `executables/`, and `archive/`
trees are consolidated locally under `outputs/historical/layout-cleanup-20260917/`.
Their relocation manifest records original paths, retained paths, and file hashes.
New checkouts obtain historical source from Git; local research data needs its own backup.

## Install

Use Python 3.11. From the repository root:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -c requirements.lock -e '.[test,dev,plot,web,build]'
```

`requirements.lock` pins the tested dependencies. The minimal installation is
`pip install -c requirements.lock -e .`; web, plotting, tests and build tools are
optional extras. A C++ compiler is needed for native execution.

## Run experiments

```bash
# Same seeded inputs for DNF and harmonic; no graphs or item logs by default.
bincovering run n=1000 trials=5 workers=2 seed=42

# Parameter sweep: six separate jobs, under one ignored sweep directory.
bincovering run --multirun n=1000,5000 seed=1,2,3 trials=5

# Saved configurations for randomized strategies and fixed-input permutations.
bincovering run --config-dir configs --config-name throwbin n=1000 trials=5
bincovering run --config-dir configs --config-name adaptive n=1000 trials=5
bincovering run --config-dir configs --config-name permutations n=1000 trials=100
bincovering run --config-dir configs --config-name advice n=1000 trials=5
bincovering run --config-dir configs --config-name one_over_n n=1000 trials=5
bincovering run --config-dir configs --config-name optimal_uniform generator.bins=100

# Explicit configuration overrides.
bincovering run 'algorithms=[{id:ThrowBin_1,params:{bin_ratio:0.3}}]' ordering=descending
bincovering run generator.id=complementary_pairs save_inputs=true trace_limit=100
```

`python -m bincovering` works in place of `bincovering`. `dataset_mode=fresh`
generates a new base input per trial; `dataset_mode=fixed` reuses one base input
and varies the trial's order/algorithm seed. Every algorithm in a trial receives
the same ordered input. `ordering=swaps swaps=50` performs 50 random pair swaps
starting from descending order; it does not promise 50 distinct moved items.
Use `swap_mode=distinct` for two distinct positions per swap, as in the old server
studies. The default `with_replacement` allows the same position twice.

Hydra runs sweep jobs serially; `workers` controls the process pool within each
job. Seeds do not depend on process scheduling. Neither float experiments nor
native execution silently convert items to another numeric domain.

## Inspect and compare

Replace `outputs/<run>` with the directory printed by a completed experiment.

```bash
bincovering list
bincovering inspect outputs/<run>
bincovering plot outputs/<run>
bincovering compare outputs/<run-a> outputs/<run-b>
bincovering export outputs/<run>
bincovering pin outputs/<run>
bincovering rerun outputs/<run>  # new record, current Python code, archived input/binary
bincovering cancel outputs/<run> # cooperative cancellation
bincovering cleanup             # preview disposable figures and traces
bincovering cleanup --apply     # removes those only; skips pinned/active runs
```

Plots use saved trials and do not rerun algorithms. Comparisons report whether the
ordered trial inputs match. Cleanup never deletes raw trials, saved inputs, logs,
or source provenance. Export creates a zip under the run's `exports/` directory
unless a destination is supplied; it refuses to overwrite an existing export.

All new outputs live under **`outputs/`**, which Git ignores. Configure an external
storage root with `output_root=/path/to/research-results`; use `--root` for listing,
cleanup, or the web interface. Ignored files still need backup outside Git.

Each run contains `config.json`, `manifest.json`, `trials.csv`, `summary.json`,
`run.log`, and a source snapshot. Hydra jobs additionally include `.hydra/` settings.
Inputs, bounded traces, and figures are optional. Imported file inputs are always
saved; use `generator.id=file generator.path=/absolute/path/to/items.txt`.
A failed algorithm or generator produces failed trial rows. Cancellation preserves
completed trials; abandoned processes are marked interrupted when runs are listed.
Failed/cancelled CLI runs exit nonzero. Imported files are frozen before trials,
and native runs retain the executable and available source/build settings.

`construction_target` is not an optimum certificate: historical OneOverN and
OptimalUniform generators retain their old distributions but use a mass bound.
If float rounding produces coverage above the real-arithmetic bound, the trial
records a numerical warning and omits the ratio. See the migration guide for details.

## Web interface

```bash
bincovering web
# Open http://127.0.0.1:5000
```

Configure experiments, inspect progress, cancel jobs, compare selected runs,
create plots, pin results, and export them. The web interface reads the same output
directories as the CLI. Background workers continue if a browser tab closes or the
server restarts. Run locks distinguish live workers from abandoned runs; listing
reconciles abandoned records without discarding evidence. Cancellation is cooperative.

The old web entry point and script editor are retired; use `bincovering web`. Build and run the container from the repository root:

```bash
podman build -f tools/Containerfile -t bincovering:dev .
podman run --rm -p 5000:5000 -v "$PWD/outputs:/app/outputs" bincovering:dev
```

The image includes the native baselines. Container runs with multiple workers,
plotting, and native comparison have been validated.

## Native baselines

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j 2
bincovering run --config-dir configs --config-name integer n=1000 trials=5
```

The native runner supports DNF and harmonic in integer or float64 mode. Native
results include subprocess/serialization time; compare timings with that overhead
in mind. Native source/binary provenance is saved with the run. Independent trials run in
separate worker processes.
`bincovering benchmark --items 1000 10000 100000 --trials 3` records paired
Python/native timings under ignored outputs. Native startup and serialization
dominate small inputs; profiling supported faster parsing, not a blanket speedup
claim or adding native threads. The reusable native state is in `cpp/include/`;
historical executables are in `cpp/reference/`.

## Development

```bash
pytest -q
ruff check src tests
ruff format --check src tests
```

The tests cover algorithm boundaries, a tiny exhaustive optimum oracle, private
random streams, serial/parallel repeatability, Python/C++ agreement, failure and
cancellation handling, restart recovery, advice accounting, historical generator
semantics, and web/CLI interoperability. Native checks skip if `g++` is unavailable.

For the opt-in browser test, install `.[browser]` and Chromium with its system
dependencies, then run `BINCOVERING_BROWSER=1 pytest tests/test_browser.py -q`.
Alternatively build `tools/Containerfile.test` after the application image; it
installs browser system dependencies and expects Chromium at `/browsers`:

```bash
PLAYWRIGHT_BROWSERS_PATH="$PWD/.tools/browsers" python -m playwright install chromium
podman build -f tools/Containerfile.test -t bincovering-test:dev .
mkdir -p outputs/browser-validation
podman run --rm -v "$PWD/.tools/browsers:/browsers:ro" -v "$PWD/outputs/browser-validation:/screenshots" bincovering-test:dev
```

Browser validation covers actual jobs, comparison, plots, pinning, export, and mobile layout.

See [algorithm identities](docs/algorithms/REGISTRY.md) and the historical
[artifact inventory](docs/ARTIFACT_INVENTORY.json).
See the [study migration guide](docs/MIGRATION.md) for replacement commands and
changes in result interpretation. Old directory trees and compatibility drivers have been removed from the active
layout; original implementations remain in Git history. Advice variants are experimental
implementations with explicit supplied parameters, not validated theoretical guarantees.
The historical research reference is https://arxiv.org/pdf/2309.13647.
