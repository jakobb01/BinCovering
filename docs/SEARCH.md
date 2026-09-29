# Searching saved experiments

Search matches saved names and execution IDs, status, input ordering, generator,
dataset mode, item count, trial count, seed, workers, domain, algorithm, backend,
and algorithm parameters. All words or filters must match the same experiment.
Words support abbreviations and one-character typos. Numbers match exactly.

| Search | Finds |
| --- | --- |
| `shuffle 1000` | Shuffled experiments containing the recorded number 1000. |
| `shuffle items:1000` | Shuffled experiments configured for exactly 1,000 items. |
| `swaps 100` or `swaps:100` | Experiments using swaps ordering with exactly 100 pair swaps. |
| `n>=1000 trials:30` | At least 1,000 configured items and exactly 30 trials. |
| `seed:42 workers:2` | The recorded seed and worker count. |
| `generator:uniform dataset:fixed` | Uniform inputs using a fixed base dataset. |
| `backend:cpp domain:integer` | Integer experiments containing a native algorithm. |
| `throwbin bin_ratio:0.3` | A ThrowBin algorithm with that recorded parameter. |

`n:` and `items:` are equivalent. Numeric filters accept `:`, `=`, `>`, `>=`, `<`,
and `<=`; spaces around operators are allowed. Unqualified numbers can also match
trial counts, seeds, parameters, or complete numeric parts of names and IDs. Use a
field filter when its meaning matters. Searching `100` does not match `1000`.

Ordering aliases include `shuffled` and `permutation` for shuffle, `asc` for
ascending, and `desc` for descending. `dnf`, `harmonic`, and historical ThrowBin
names are searchable aliases; they do not change the saved algorithm identity.
Swap counts and methods are searchable only when swaps ordering is active.
Unused defaults retained in a configuration are not presented as performed swaps.

Item filters use the saved configuration’s `n`, also displayed in history. For
file inputs and historical constructed-uniform inputs, consult saved trial records
for the actual input length; it may differ from that configured number. Search does
not infer missing metadata.
