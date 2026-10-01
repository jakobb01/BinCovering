# Release notes

## 1.0.0

Prepared and verified on 2026-10-01. Release tagging and publishing are pending.

Version 1.0.0 brings the migrated research tools into one Python package, shared
experiment runner, and dashboard. These notes describe the current workflow and
changes from the earlier script-based checkouts.

### Reproducible experiments

- CLI, Hydra configurations and dashboard jobs use the same validated runner.
  Nine built-in algorithms have stable IDs and documented historical aliases.
  DNF and harmonic also support native C++ execution.
- Source distributions include setup and release documentation, dependency pins,
  research presets, native build sources, container definitions and test helpers.
- Trials support fresh or fixed inputs, explicit ordering and swap methods,
  independent data/order/algorithm RNG streams, and process workers. Algorithms
  in a trial receive the same ordered input; seeds are independent of scheduling.
- Saved runs retain configuration, trial results, logs, input hashes, package and
  source provenance, and native binary evidence when applicable. File inputs are
  frozen. Optional input files, traces and plots stay with their experiment.
- Inspection, comparison, plotting, export, reruns, pinning and cancellation are
  available through the shared workflow. Restart recovery retains completed
  evidence and marks abandoned work interrupted. Dashboard removal supports Undo;
  cleanup preserves raw results and provenance.

### Dashboard, Builder and accounts

- Home, Saved experiments, Builder and administrator Accounts share navigation
  and interface components. Saved experiments supports grouped history, search,
  selection and result dialogs with plot, summary and provenance views.
- Research views include input/trial distributions, adjustable target achievement,
  paired improvement over DNF, controlled ordering studies, ThrowBin parameter
  sweeps and physical mass accounting. Figures and their data export together.
  See [research plot definitions](RESEARCH_PLOTS.md) for pairing and reference rules.
- Builder has separate algorithm and item-generator workspaces, drag/drop graphs,
  execution branches, typed value connections, working starters and reusable
  components. Small Custom blocks use the documented Simple Python or pseudocode
  subset with built-in bin operations.
- Private drafts become immutable available revisions after successful previews.
  Owners can share read-only revisions that other researchers can run or clone.
  Experiments freeze program graphs, dependencies, parameters and runtime identity.
- Builder previews automatically capture bounded execution traces with explicit
  truncation. Detailed traces for full experiments remain configurable; run logs,
  results and provenance are always retained.
- Visitors can register as researchers after initial administrator setup. Accounts
  lets administrators manage all users and reassign experiment ownership. Accounts
  and the library index use SQLite; passwords use salted scrypt hashes. Account
  changes invalidate existing sessions, and dashboard mutations require CSRF tokens.
- Custom execution uses rootless Podman with bounded resources, no network or host
  mounts, and an immutable runtime image. A durable queue limits global and
  per-account work. See [Builder setup and workflows](BUILDER.md).

### Correctness and research interpretation

- Corrected baseline completion/accounting, harmonic integer boundary behavior,
  big-item optimum calculation and corrected-advice physical accounting are
  covered by regressions. Retirement and replacement ThrowBin remain distinct;
  corrected advice identities remain distinct from historical implementations.
- References explicitly distinguish certified OPT, mass upper bounds and historical
  construction targets. Big-item and complementary-pair constructions provide
  certificates under their validated rules. Historical OneOverN and OptimalUniform
  retain their distributions and report construction targets separately.
- The [guarantee matrix and proofs](algorithms/GUARANTEES.md) separate published
  baseline results, conservative implementation-derived bounds, restricted-input
  optimality and experimental strategies. Algorithm choices identify their research
  status and stream, length-aware or supplied-advice input access.
- Regression coverage now checks all nine built-ins against independent exact OPT
  on 3,906 small ordered inputs at three seeds. Parameterized finite-bound checks,
  larger certified instances, strict-big-item optimality, documented counterexamples
  and native integer oracle checks supplement existing integration tests.

### Upgrading an earlier checkout

Use Python 3.11 and reinstall the package from the repository root to refresh its
distribution metadata and selected extras:

```sh
python -m pip install -c requirements.lock -e '.[test,dev,plot,web,build]'
```

The old `server/`, `python_graphs/`, `web_interface/` and hardcoded study entry points
have been retired. Use `bincovering run`, named configurations and `bincovering web`.
The [migration guide](MIGRATION.md) maps historical studies and documents corrected
behavior, generator identities and RNG changes. Old seeds alone do not promise
identical histories after independent RNG streams were introduced.

Back up the entire output root, including its `.dashboard/` directory, experiment
artifacts and required recorded Builder runtime images. If the workspace has no
administrator, initialize one locally:

```sh
bincovering setup-admin --root outputs --username yourname
```

Custom execution also requires the dedicated Builder image and host capabilities
described in [Builder setup](BUILDER.md#local-setup). Existing frozen revisions and
reruns retain their recorded runtime image identity. The package version change
does not migrate research data or rewrite historical manifests. Unassigned local
CLI experiments are available to administrators for ownership assignment.

Older results can lack input histograms, bin-load measurements or detailed traces.
Views identify unavailable evidence; a new experiment records the measurements
needed for those views. Plotting uses saved evidence without rerunning algorithms.

### Limits and release verification

The guarantees assume exact arithmetic. Float64 execution uses ordinary additions
without an implicit coverage epsilon or numeric-domain conversion. Numerical
warnings and conservation checks do not certify every placement against real
arithmetic. A finite regression suite or passing Builder preview does not prove
optimality or a competitive ratio.

The supplied-parameter advice variants provide the documented conservative fallback
bound. A faithful paper oracle, encoded advice budget and full historical-study
reproduction remain research work after v1. Improved-advice theorems are not claimed
for arbitrary supplied parameters.

The dashboard command runs locally. Shared hosting requires operator-managed HTTPS,
a production WSGI server and a working isolated execution supervisor, as described
in [shared hosting](BUILDER.md#execution-limits-and-shared-hosting).

The final default suite passed 306 tests with 12 opt-in checks skipped. All twelve
opt-in checks were subsequently exercised in separate isolation and browser passes.
Fresh native builds and installed-wheel workflows also passed. See the
[release verification record](RELEASE_VERIFICATION.md) for results, scope and
reproduction commands. Release tagging and publishing await the user's instruction.
