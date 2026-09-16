# BinCovering

Academic research tools for **bin covering**: maximize the number of bins whose
item load reaches the covering threshold. The project has a shared Python
experiment runner, Hydra configuration, a local web interface, and C++ baselines.

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

# Explicit configuration overrides.
bincovering run 'algorithms=[{id:ThrowBin_1,params:{bin_ratio:0.3}}]' ordering=descending
bincovering run generator.id=complementary_pairs save_inputs=true trace_limit=100
```

`python -m bincovering` works in place of `bincovering`. `dataset_mode=fresh`
generates a new base input per trial; `dataset_mode=fixed` reuses one base input
and varies the trial's order/algorithm seed. Every algorithm in a trial receives
the same ordered input. `ordering=swaps swaps=50` performs 50 random pair swaps
starting from descending order; it does not promise 50 distinct moved items.

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
A failed algorithm produces a failed trial row; an interrupted run keeps completed
trial records and a cancelled status. Failed/cancelled CLI runs exit nonzero.

## Web interface

```bash
bincovering web
# Open http://127.0.0.1:5000
```

Configure experiments, inspect progress, cancel jobs, compare selected runs, and
create plots. The web interface reads the same output directories as the CLI.
Background workers continue if a browser tab closes. On server restart, persisted
results remain available; this first version does not recover supervision of
previously launched workers. Cancellation is cooperative and may wait for input
generation or the current processing chunk.

The compatibility command `python web_interface/app.py` opens the same interface.
The previous script editor assets remain historical and are not served by it.
The container builds from the repository root using `web_interface/Containerfile`;
mount `/app/outputs` to retain results. Container execution has not been validated
in this development environment.

## Native baselines

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j 2
bincovering run --config-dir configs --config-name integer n=1000 trials=5
```

The native runner supports DNF and harmonic in integer or float64 mode. Native
results include subprocess/serialization time; compare timings with that overhead
in mind. Native source/binary provenance is saved with the run. C++ threading is
not introduced: independent trials already run in separate worker processes.

## Development

```bash
pytest -q
ruff check src tests
ruff format --check src tests
```

The tests cover algorithm boundaries, a tiny exhaustive optimum oracle, private
random streams, serial/parallel repeatability, Python/C++ agreement, failure and
cancellation handling, and web/CLI interoperability. Native checks skip if `g++`
is unavailable.

See [algorithm identities](docs/algorithms/REGISTRY.md) and the historical
[artifact inventory](docs/ARTIFACT_INVENTORY.json).
Older server drivers remain for historical studies; their configuration semantics
and performance claims are not automatically equivalent to the new runner.
The historical research reference is https://arxiv.org/pdf/2309.13647.
