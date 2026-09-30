# Builder operations and Custom statements

Builder programs are graphs with supplied lifecycle entry points. Online algorithms
run Start once, Next item for each ordered input, then Stop. Offline algorithms run
Start, Process sequence, then Stop. Generators run Start, bounded Generate next
steps, then Stop. Reusable components have a Process entry and run inside the
caller with their own persistent state, typed inputs/outputs, and parameters.

The compact Custom field accepts **Simple Python** or **defined pseudocode**.
Both are parsed into the same restricted program representation and interpreted
by the same Python runtime used in previews and experiments. Pseudocode is a
documented notation, not free-form prose. Switching notation preserves supported
statements; comments and formatting are not execution data. An invalid draft must
be corrected before it can be converted.

## Variables and state

Use short names such as `count`, `selected`, or `loads`. Assignments create local
state; declare initial values in the graph's State field or initialize them in
Start. Component state persists between calls to that particular instance and
is separate from its caller and other instances.

```python
count = 0
loads = []
```

```text
SET count = 0
SET loads = []
```

Parameters are declared separately with a type, default, and optional bounds.
They are read-only. A parameter named `min_size` is available as `min_size` or
`params['min_size']`. Component inputs are also read-only. Outputs are state
variables whose names and types match the component's output declarations.

The runtime supplies these read-only values:

| Name | Meaning |
| --- | --- |
| `item` | Current ordered input item; unavailable before an item exists |
| `index`, `item_index` | Its immutable zero-based input index |
| `threshold` | Covering threshold in the selected numerical domain |
| `n` | Actual input count for an algorithm, requested output count for a generator |
| `active_bin` | Currently selected bin ID; create a bin first |
| `covered_bins` | Measured closed-bin count |
| `discarded_items` | Measured discarded-input count |
| `sequence` | Full ordered immutable sequence, available only to offline programs |
| `output` | Read-only generated items emitted so far |

These names cannot be used for user parameters, state declarations, or component
inputs. Assigning counters such as `covered_bins` cannot manufacture results.

## Conditions, arithmetic, and lists

Numbers, booleans, short text, lists, list indexing, `+ - * / // %`, comparisons,
`and/or/not`, and conditional expressions are supported. Powers require an integer
exponent from -16 to 16. There is no implicit covering epsilon or float/integer
rescaling. Numeric values must be finite and have magnitude at most `1e100`.

```python
if bin_load(active_bin) >= threshold:
    cover(active_bin)
else:
    count += 1
```

```text
IF BIN_LOAD(active_bin) >= threshold THEN
    COVER active_bin
ELSE
    ADD 1 TO count
END
```

The pseudocode keywords are case-insensitive. Expressions use the same operators
as Simple Python; helper names can use either case. Lowercase variable names avoid
confusion with reserved keywords. `SET x = value`, `ADD value TO x`, `IF ... THEN`,
`ELSE IF ... THEN`, `ELSE`, and `END` are fixed forms.

Use `len`, `min`, `max`, `sum`, `abs`, `int`, `float`, `round`, `sorted`, and
`reversed` for bounded values. `append(values, value)` and `pop(values)` modify
a state list; they cannot change inputs, parameters, or the bin ledger. State
lists have at most 10,000 elements and eight levels of nesting. There are at most
100 state variables per graph/component instance.

## Bounded iteration and offline access

Use `for variable in values` or `range(stop)`, `range(start, stop)`, or
`range(start, stop, step)`. `break` and `continue` are permitted inside these loops.
The visual Loop node offers the same bounded iteration without Custom text.
There are no arbitrary control cycles or `while` loops.

An offline algorithm can inspect or reorder an index list, while immutable input
indices still identify every original item. The straightforward starter is:

```python
for i in range(len(sequence)):
    place(sequence[i], active_bin, i)
    if bin_load(active_bin) >= threshold:
        cover(active_bin)
```

```text
FOR i IN RANGE(LEN(sequence)) DO
    CALL PLACE(sequence[i], active_bin, i)
    IF BIN_LOAD(active_bin) >= threshold THEN
        COVER active_bin
    END
END
```

Online programs cannot read `sequence`, place another input index, or incorporate
an offline component. An online declaration records input access; it does not
claim an online competitiveness theorem.

## Bin ledger helpers

| Helper | Effect |
| --- | --- |
| `create_bin()` | Create an empty bin, select it, return its ID |
| `select_bin(id)` | Select an existing active bin |
| `active_bins()` | Return the active bin IDs |
| `bin_load(id)` | Read its measured load; omitted ID uses `active_bin` |
| `is_covered(id)` | Test measured load against the threshold |
| `place(item, bin_id, index)` | Place that exact immutable input once; omitted arguments use current item/bin/index |
| `cover(id)` | Close an active bin whose load reaches the threshold; omitted ID uses active bin |
| `discard(index)` | Discard an unconsumed input exactly once; omitted index uses current index |

Covering the currently selected bin creates and selects a fresh empty bin.
Closing any other bin leaves the current selection unchanged. Closed bins cannot
be reused. To choose randomly among previously created active bins:

```python
select_bin(choice(active_bins()))
```

```text
SELECT BIN CHOICE(ACTIVE_BINS())
```

In pseudocode, `CREATE BIN AS selected` assigns a fresh ID, `COVER selected`
closes it, `DISCARD` uses the current input, and `CALL place(item, selected, index)`
performs a placement. `CLOSE BIN` is equivalent to `COVER` with the active bin.

Every algorithm input must be placed or discarded. An online algorithm must
consume the current item before advancing. Duplicate use, altered input values,
invalid indices, premature closure, and writes to measured counters are errors.
Unclosed bins retain unfinished mass even if their physical load exceeds the
threshold. Results contain measured useful, overshoot, unfinished, and discarded
mass, including the numerical conservation residual.

## Generator helpers and seeds

`uniform(minimum, maximum)`, `randint(minimum, maximum)`, and `choice(values)` use
the interpreter's private `random.Random(seed)` stream. Experiments supply the
runner's independent data or algorithm seed; preview and experiment execution
use the same implementation.

```python
emit(uniform(min_size, max_size))
```

```text
EMIT UNIFORM(min_size, max_size)
```

Integer-domain generators use `randint` and integer parameters. Every emitted
item must be finite and in `(0, threshold]`, with no float conversion in integer
domain. A generator must emit exactly the requested count. It may emit a bounded
pair in one step, but cannot exceed that count. Generated values go through the
normal host ordering, hashing, and mass-bound calculation; generator statements
cannot assert an exact optimum.

## Typed connections and reusable components

Execution connections define order and Yes/No/Loop branches. Data connections
carry named typed outputs into named inputs. Supported types are `number`,
`integer`, `boolean`, `list`, `bin`, `text`, and `any`. An integer can feed a number
input, while a bin ID stays a bin port rather than an arbitrary numeric port.
Values are checked at runtime as well as connections being checked during
validation.

A data source must run before its consumer on every execution path in the same
lifecycle phase. Store cross-phase values in state. This prevents a consumer from
reading a skipped branch or a stale output from an earlier item. Custom nodes
declare input/output ports and export expressions such as `{"value": "count"}`.
Their exported expressions cannot have side effects. Component nodes bind their
explicit input expressions and map typed outputs into caller state.

Reusable graphs are embedded with frozen revisions. They cannot recurse and
nesting is limited to eight levels. Instance removal and library archival do not
change previously frozen experiments.

## Standalone component preview fixtures

Pure components accept explicit typed preview inputs, for example
`{"incoming": 0.5}` for the Scale a value starter.

Bin-operation components need explicit fixtures. A fixture with items `[0.4, 0.7]`
and `{"kind":"algorithm","bins":[[0,1]],"current_index":1}` creates a measured
bin containing those two immutable input indices before calling the component.
A close component can then cover its load of 1.1. To test placement of a pending
item, leave its index out of the fixture bins. Fixture input indices cannot appear
twice. Fixtures have at most 100 bins and 10,000 input items.

The setup is labelled `fixture` in the trace and recorded in execution metadata.
It is preview context rather than a claim about an algorithm's research execution.
Generator helper components use `{"kind":"generator"}` fixture context and
show the emitted values from one component call.

## Traces, limits, and exports

Events record the actual phase/node/call path, chosen branch and edge, statement
line, immutable input index, bin operation and load changes, state, and generated
output. Source lines refer to the displayed notation. Python/pseudocode produce
the same executed operations; line numbers can differ with notation formatting.
Operation playback reads these recorded snapshots; it does not reverse execution.

Builder verification always captures a trace with the server-owned budget of
10,000 events and 4 MiB; users cannot disable it or choose a smaller capture.
Direct runtime calls default to 1,000 events and 2 MiB, with hard caps of 10,000
events and 4 MiB. State snapshots default to 256 values (maximum 1,000),
four displayed nesting levels, the last 100 bins, and 30 item indices per bin.
Snapshots and event streams carry explicit truncation markers. Limits do not
change the computed result. Full experiment trace capture remains optional;
disabled experiment traces collect no event snapshots. Run logs and provenance
are always stored.

Custom source is limited to 32,000 characters/4,000 parsed syntax nodes. Inputs and
generated counts are limited to 200,000, with a total budget of 2,000,000
interpreter operations. The shared execution supervisor separately enforces
container CPU, memory, processes, time, input/output size, and cancellation limits.
Resource failures are reported, rather than silently executing on the host.

Imports, classes, functions, filesystem/network operations, attributes, arbitrary
Python calls, comprehensions, and unrestricted `eval`/`exec` are unsupported.
The AST parser is an allowlist, not the outer isolation boundary.

Graph exports preserve the frozen representation. The Python export contains
inspectable frozen graph data and a small `run(...)` adapter requiring builder
runtime API version 1. It calls the same interpreter; it is not a whole-file
editor or arbitrary Python execution entry point. An execution hash ignores node
layout, display labels, and equivalent Custom notation spelling. Research source
packages preserve the original displayed graph/source and runtime image identity.
