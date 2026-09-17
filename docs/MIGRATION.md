# Study migration and compatibility

The pre-reorganization checkout is `65e0180`; the first packaged checkpoint is
`0da1672`. Use Git to inspect those implementations and historical output formats.
Source copies retired during local migration were retained under ignored
`outputs/historical/layout-cleanup-20260917/archive/retired-source/`. No research outputs were deleted.

## Study entry points

Use the commands below from the repository root. All new results stay under
`outputs/`. The former `server/custom_code/main_*.py` entry points and compatibility import
folders have been removed from the active tree. Use the replacements below; old
command-line flags are not silently reinterpreted.

| Old entry point | Replacement |
| --- | --- |
| `main_TrueUniform_DNF.py` | `bincovering run --config-dir configs --config-name swaps` |
| `main_TrueUniform_Permutation_DNF.py` | `bincovering run --config-dir configs --config-name permutations` |
| `main_TrueUniform_Parallel.py` | Either configuration above with `--multirun n=1000,5000 workers=2` |
| `main_Uniform_DNF.py` | `optimal_uniform` configuration; override `ordering=swaps swap_mode=distinct swaps=100` |
| `main_DNF.py` | `one_over_n` configuration; select only DNF and set `dataset_mode=fixed ordering=swaps swap_mode=distinct` |
| `main_ThrowBin.py`, `main_ThrowBin_1.py`, `main_ThrowBin_DNF.py` | `throwbin` configuration; select the desired stable algorithm ID |
| Both ThrowBin parallel drivers | `throwbin` plus `--multirun n=1000,5000 workers=2`; set repetitions explicitly |
| `main_AdaptiveBin.py` | `one_over_n` for fresh descending sequences; `permutations` with `algorithms=[{id:adaptive_items}]` for fixed uniform permutations |
| `python_graphs/main.py`, `graph.py` | Shared run, plot, and compare commands; the old integer generator is retained in `cpp/reference/generator.cpp` for historical studies |

Flag mapping: `-n/--num-items` becomes `n=`, `-r/--runs` becomes `trials=`,
`--workers` becomes `workers=`, `--seed` becomes `seed=`, and `--path/--output-dir`
becomes `output_root=`. `--opt-bins` becomes `generator.bins=` with
`generator.id=optimal_uniform_legacy`. Bin ratio is an algorithm parameter, e.g.:

```bash
bincovering run 'algorithms=[{id:throwbin_replace,params:{bin_ratio:0.3}}]' n=1000 trials=10 ordering=descending dataset_mode=fixed
bincovering run --config-dir configs --config-name swaps --multirun 'swaps=range(0,1001,100)' n=1000 trials=1
```

The old drivers sometimes set repetitions equal to N and silently launched very
large sweeps. New configurations use small explicit defaults. The full historical
study is obtained by setting the corresponding N, trial count, swap range, bin
ratios, and ordering. Hydra sweeps jobs; the runner parallelizes trials within a job.

## Distribution and randomness contracts

- Uniform generation uses the same `random.uniform(min,max)` rule. Sorting is now
  explicit; the old generator sorted descending automatically.
- `one_over_n` reproduces historical small sizes from `uniform(0.0001, 2/N)`,
  complements, and initial descending order. For N>20000 the endpoints are reversed,
  as in the old code; this behavior is preserved rather than silently changing the
  distribution. Even N is required. Its pair count is a construction target, not a
  real-arithmetic optimum certificate for rounded float inputs.
- `optimal_uniform_legacy` reproduces the old fill/overflow procedure, including its
  omission of remainders <= the minimum size. That omission can invalidate the old
  claim of a known optimum. New records expose `construction_target` separately and
  use the mass bound for comparison. The generator is not renamed to "uniform".
- `complementary_pairs` is a distinct, certified generator using exact dyadic or
  integer complements. It is not a replacement alias for OneOverN.
- `swap_mode=distinct` matches the server's two-distinct-position swaps.
  `with_replacement` permits selecting the same position, matching the older mixer
  operation. The new `swaps` setting is an operation count, not a claimed percentage
  of distinct items moved.
- Private data, ordering, and algorithm RNG streams replace global RNG coupling.
  Distributions and algorithm rules are preserved where stated; old numerical seeds
  do not promise identical end-to-end histories across that change. New run metadata
  records the independent seeds and actual input hashes.

The old CSV analyzer and adaptive diagnostics are retained in Git history and the
local historical archive; they are not supported entry points. The new reporter
consumes run directories. Import strategies and generators from `bincovering`,
not the removed `server` wrappers.

## Corrected advice variants

`advice_reserved` and `advice_reserved_k4` preserve the two distinct class layouts,
with supplied `m` reserved bins and `x_m` reservation fraction. They correct phantom
coverage from missing critical items, coverage omitted at end-of-input, and the
small item lost when switching out of the reservation phase. Inputs are never
counted twice. The actual covering load is separate from the temporary reservation.

These implementations are experimental interpretations of the repository's rules.
They are not a claim of equivalence to a particular paper's advice tape or theorem.
Advice values and their origin must be reported in research; the runner does not
infer an oracle or compute a theoretical advice bit budget.

## Output and source preservation

The old web editor is retired; its assets are preserved in Git history. The `bincovering web`
entry point uses the shared experiment runner. Its container definition lives in
`tools/Containerfile`. Old C++ research prototypes are now
in `cpp/reference/`; their build targets retain the `legacy-` names. Only the new
native library is used by the shared runner.

Agent context/planning files, generated artifacts, local archives, screenshots,
benchmark output, wheels, environments, and caches are ignored. Human-facing
documentation, code, test fixtures, configurations, and dependency pins are tracked.

## Final directory cleanup

The old top-level `server/`, `python_graphs/`, `web_interface/`, `executables/`, and
`archive/` directories were consolidated under ignored
`outputs/historical/layout-cleanup-20260917/`. All files were retained byte-for-byte;
`relocation.json` there maps original paths to retained paths with SHA-256 hashes.
The original artifact inventory continues to describe the original paths at its
baseline revision; use the relocation manifest to locate those files locally.

The percentage-mixer regression reference is retained in `tests/reference/mixer.py`.
Historical C++ sources remain in `cpp/reference/` because the build and differential
tests still exercise them. The active Python/web application is in `src/bincovering/`.
