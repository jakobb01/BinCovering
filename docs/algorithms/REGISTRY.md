# Algorithm identities and numerical semantics

Names in the registry are stable IDs. Parameters and backends are stored separately
in every trial; filenames and timestamps never identify an algorithm variant.

See [GUARANTEES.md](GUARANTEES.md) for the guarantee matrix, arithmetic and
input-access assumptions, citations, finite bounds, and implementation proofs.

| ID | Historical alias | Behavior / parameters |
| --- | --- | --- |
| `dual_next_fit` | `dnf`, `DNF_1` | One active bin; discard overshoot after covering. Python and C++ baselines. |
| `dual_harmonic` | `harmonic` | Separate next-fit states for classes with lower bounds 1/2, 1/3, …, 1/k and a small-item class; default k=5. |
| `throwbin_retire` | `ThrowBin` | Open floor(N × bin_ratio) bins; randomly choose active bins; remove covered bins; discard remaining items if all bins cover. |
| `throwbin_replace` | `ThrowBin_1` | Same initial bin count; replace covered bins with empty bins. |
| `throwbin_fixed_active` | `ThrowBin_DNF` | Ten active bins, random placement, replacement after coverage. |
| `adaptive_items` | `AdaptiveBin` | Grow total bins to ceil(items_received/2); ensure an active bin; random placement. |
| `advice_reserved` | `advice` | Reservation advice, k=5 layout; supplied reserved-bin count m=103 and fraction x_m=0.8. Actual loads determine coverage. |
| `advice_reserved_k4` | `advice_k` | Distinct k=4 layout with the same explicit advice parameters. |
| `adaptive_covered` | `AdaptiveBinCovered` | Initial bins (default 1); after covering, grow total bins to max(ceil(covered × multiplier), covered+1); default multiplier 2. |

The adaptive-items implementation uses division by 2. Some historical comments
claimed division by e or performance guarantees; those claims are not adopted.
The ThrowBin variants that allocate bins from N know the input length in advance;
this differs from adaptive-items. Ordering is always explicit in configuration.
Descending-order experiments have access to the input for sorting, which must be
accounted for when interpreting online-algorithm claims.

`bincovering algorithms` reports catalog metadata alongside the existing parameter
defaults and aliases. The dashboard displays the same research status and input
access for each built-in choice:

- **Baseline** identifies DNF and harmonic. Other built-ins are **Experimental**,
  including those with conservative or restricted-input bounds in GUARANTEES.md.
- **Stream** uses current and past items, without future sizes or advance N.
- **Length-aware** processes a stream with N supplied before processing.
- **Supplied advice** processes a stream with configured m/x_m. Their origin and
  suitability are not certified by the program.
- **Custom** identifies a Builder revision; its online/offline access declaration
  is shown separately and does not establish a competitiveness guarantee.

The catalog's machine-readable `input_access` values are `stream`,
`stream_with_length`, and `stream_with_supplied_advice`. These labels describe the
placement rule. Ascending/descending sorting still uses the full sequence, and
research status does not forecast performance. Metadata is descriptive and does
not alter normalized configurations, identities, or historical trial records.

Randomized server variants remain research strategies. Conservative lower bounds
for fixed-ten ThrowBin and AdaptiveBinCovered, and restricted-input optimality for
AdaptiveBin, are documented in [GUARANTEES.md](GUARANTEES.md); they do not establish
tight expected ratios or broader distribution-specific claims. All migrated
randomized strategies use float64 inputs with threshold 1.0. DNF
and harmonic also support integer inputs; harmonic boundaries use non-truncated
division. Exactly threshold-sized items are allowed; larger and nonpositive items
are rejected by the shared input layer. The native integer threshold is bounded
by 10^9 to keep its sums well inside signed 64-bit arithmetic.

The advice variants correct the historical accounting errors described in
[MIGRATION.md](../MIGRATION.md). Their supplied advice values are not inferred from
an oracle. The conservative fixed-parameter fallback bound in GUARANTEES.md does
not establish the paper's improved-advice guarantee or advice-bit complexity.
Historical advice results are not correctness references.
The archived source revision and each run's source snapshot distinguish old
behavior from corrected implementations. Do not compare historical outputs by
algorithm label alone.
