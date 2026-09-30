# Visual algorithms and item generators

The dashboard's **Builder** page is a visual workspace for algorithms, item
generators, and reusable components. It uses the same Python execution backend
for previews and experiments. Custom blocks accept a documented subset of Simple
Python or defined pseudocode. Both notations describe the same validated operations.

## Local setup

Install the web extra with Python 3.11. Create the first administrator locally:

```sh
bincovering setup-admin --root outputs --username yourname
```

The command prompts for a password; there are no default shared credentials.
After the first active administrator is set up, visitors can choose **Create
account** on the sign-in page to register as researchers. Registration asks for an
account name, password of at least 12 characters, and matching confirmation; it
signs the new researcher in immediately. It cannot create an administrator. Public
registration is limited to ten attempts per direct client IP in five minutes, with
the limit retained across restarts.

Administrators see all users, including disabled accounts, on **Accounts**. They
can create researchers or administrators, disable/enable accounts, reset passwords,
and reassign experiment ownership. Reset a forgotten password locally with
`bincovering account-password --root outputs --username yourname`.

Builder execution requires rootless Podman, cgroup v2 CPU/memory/PID controllers,
and seccomp. Build the dedicated runtime image from the repository root:

```sh
podman build --pull=never -f tools/Containerfile.builder -t localhost/bincovering-builder:v1 .
bincovering web --root outputs --port 5000
```

Open http://127.0.0.1:5000, sign in, and choose **Builder**. The base image is pinned
in the Containerfile; a new machine must obtain that base before an offline build.
The dashboard checks the required capabilities and immutable image identity before
custom execution. An unavailable backend produces a labelled error.

Accounts, library revisions, job records, and the session key live under
`<root>/.dashboard/`; back up this directory together with experiment artifacts.
Output directories and user-created programs remain outside Git.
The user and library index is SQLite (`<root>/.dashboard/index.sqlite3`). Passwords
are stored as salted scrypt hashes through Werkzeug, not plaintext or reversible
encryption. Account/session API responses omit password hashes. Signup and admin
mutations require a session CSRF token; password/role/status changes invalidate
existing account sessions. Registration does not write plaintext credentials to files.

## Build and run

1. Choose **Algorithms** or **Item generators**, then a working starter. Each tab
   keeps its own draft and relevant building blocks. Algorithm starters support
   current-item or whole-sequence access; reusable component starters are in both
   tabs. The system supplies lifecycle entry points.
2. Add operations from the palette by drag/drop or **Add**. Connect an execution
   output circle to an input circle by dragging, or clicking/keyboard activation.
   Conditions require both Yes and No paths. **Value connections** reveals typed
   ports; existing value connections stay visible. They carry a value produced on
   that execution path. Drag the canvas background or use the wheel to pan; use
   **Fit**, zoom buttons, or Control/Command-wheel to zoom. There are no canvas scrollbars.
3. Select an operation to edit its settings. Small **Custom** fields offer both
   notations, a syntax guide, and insertable examples. Start with the supplied bin
   operations instead of writing imports, classes, or lifecycle methods.
4. **Remove** is visible on editable component cards and in the inspector. Delete
   works when the graph has focus. **Undo** restores the node and its connections;
   removing a node does not invent replacement execution paths. Entry points are fixed.
5. **Save draft** retains incomplete work. **Run preview** validates and executes
   the graph through the restricted runtime. Inspect its visible execution trace,
   graph highlights, state values, item placement, and bin loads.
6. **Make available** freezes a successfully tested revision. Select that revision
   and its parameters on Dashboard, alongside built-in algorithms if desired, then
   launch a normal experiment.

Saving a draft is different from making a revision available. Changing executable
logic requires another preview. Graph layout and equivalent notation spelling do
not change the execution hash. A passing preview checks the execution contract and
sample behavior; it does not prove an algorithm optimal or establish a theorem.

Graph and Python exports retain inspectable program definitions. The generated
Python adapter requires the matching installed builder runtime API. It is intended
for project workflows and does not create an unrestricted Python editor in the UI.

## Reusable components and privacy

Select a connected group and save it as a reusable component, with explicit typed
inputs, outputs, parameters, and local state. Components can be opened to edit their
inner graph. An instance's removal leaves its library definition intact. Library
definitions can be archived and restored; frozen experiment packages remain intact.

Definitions are private by default. The owner can share a particular immutable
revision read-only. Other accounts may run it or clone it into their own private
library. They cannot edit the original. Sharing a parent revision includes its
frozen component definitions. Revoking sharing prevents new access; earlier
authorized runs and private clones retain their frozen program evidence.

Experiments belong to an account. Owners and administrators can inspect artifacts,
plots, traces, exports, cancellation, and trash/restore actions. Administrators can
reassign an experiment through the ownership index without changing research data.
Existing local CLI studies that have no account assignment are visible to the
administrator, who can assign them to an account.

## Trace evidence

Every Builder verification preview records its execution trace automatically.
Capture cannot be disabled or shortened through a dashboard control or a request
setting. The server records up to 10,000 events and 4 MiB per preview, with bounded
state/bin snapshots. These are execution resource limits rather than user-selected
capture settings. The viewer labels truncation and shows recorded versus total
events when execution exceeds them. Older clients may still send `trace_limit`
or `trace_bytes`; preview requests ignore those obsolete values and always apply
the server policy. Queue admission checks the effective 4 MiB budget even when an
older request claims zero bytes.

Preview playback navigates recorded execution. Step by operation or item, pause
playback, reset, or revisit earlier events. Selecting an event highlights its node
and chosen branch; the state/bin view shows what happened at that step. Moving
backwards revisits evidence rather than executing the program in reverse. Editing
the graph makes an earlier preview stale. Backend cancellation stops queued or
running preview work.

Experiment configuration, provenance, results, and the progress/error `run.log`
are saved for every run. That log records trial progress and failures; it does not
replace detailed operation-by-operation execution evidence.

Detailed traces for full Dashboard experiments retain their separate capture
settings: an event budget, byte budget, and selected trials. A saved
result's **Trace** tab reopens captured evidence against its frozen program. Trace
events record phase, node, reusable-component context, item index, branch decisions,
bin operations, state snapshots, and errors. Events, snapshot detail, and bytes are
bounded; truncation is explicit. Built-in item/covered-count traces keep their
original schema and cannot supply unrecorded graph paths or bin histories.

## Research contracts

Online programs see the current input and past state. Offline programs explicitly
receive the whole ordered sequence and can use bounded iteration. An offline
component cannot be incorporated into an online-labelled program. Access labels
describe the enforced interface, not an algorithm's theoretical guarantees.

The managed bin ledger checks item identity and index, placement/discard exactly
once, physical loads, and coverage thresholds. Counts and masses cannot be written
as ordinary user state. Integer and float64 domains remain separate; there is no
automatic scaling or coverage epsilon. Unclosed bins retain their unfinished mass.
Custom generators must emit valid sizes and the requested count; the host computes
input hashes and reference bounds. User-written OPT claims are not accepted.

Data, ordering, and algorithm seeds use the shared runner's independent streams.
Every algorithm in a trial receives the same ordered input. Revision identities
remain distinct in saved rows and plot grouping. A run freezes graph, components,
parameters, content hashes, generated adapter, runtime API, and image identity.
Reruns require the recorded runtime image, rather than silently using a newer one.

Custom algorithm timing includes container startup, serialization, interpretation,
and trace collection when enabled. Artifact writes, generation, and plotting remain
outside the algorithm timing. Compare measurements with their recorded timing scope.

## Execution limits and shared hosting

Custom programs run in separate rootless containers with no network or host mounts,
a read-only image, private bounded scratch storage, no added capabilities, and no
privilege escalation. CPU, memory, processes, time, request size, and output size
are bounded. The container engine's own timeout remains active if a supervisor dies.

Default invocation limits are one CPU, 256 MiB memory, 64 processes, 32 MiB scratch,
30 seconds, and 16 MiB each for request and response. The server operator can set
`<root>/.dashboard/execution.json` with `image` and `limits` overrides. Image references
resolve to immutable IDs; submitted revisions retain the tested ID. This file is a
local operator setting, not a browser-controlled parameter.

The durable queue defaults to four worker slots globally and two per account, with
64 pending jobs globally and 16 per account. Previews use one slot; an experiment
reserves its configured trial-worker count. Operator overrides belong in
`<root>/.dashboard/queue.json` with `global_slots`, `account_slots`, `global_pending`,
and `account_pending`. Queued work survives a web restart. Surviving workers remain
owned; dead workers become interrupted. Completed evidence is retained.

Browser experiments also have default server budgets of 200000 requested items,
1000 trials, 2000000 items across trials, and 128 MiB of maximum trace capture per
job. Each Builder preview reserves its mandatory 4 MiB trace budget against the
same operator limit; a smaller server budget rejects the preview rather than
silently disabling its evidence. The job time budget is 600 seconds, followed by cooperative cancellation and
a bounded shutdown grace. These operator settings are `max_items`, `max_trials`,
`max_total_items`, `max_trace_bytes`, and `job_seconds` in the same queue file.
Large CLI studies remain an explicit local research workflow.

The built-in server command binds localhost. Shared hosting uses a production WSGI
server behind HTTPS; configure Flask's secure session-cookie setting there. Custom
execution needs a working rootless supervisor on that host. The ordinary application
image alone does not provide a nested container engine or engine socket to custom
programs. Public deployment is an operator action separate from local implementation.

## Verification commands

```sh
pytest -q
BINCOVERING_ISOLATION=1 pytest tests/test_builder_integration.py -q
BINCOVERING_BROWSER=1 BINCOVERING_BUILDER_ISOLATION=1 pytest tests/test_browser.py tests/test_builder_browser.py -q
```

Isolation checks exercise actual kernel/container controls and custom paired trials.
Browser checks require Chromium, its system dependencies, and the builder image.
For a browser running in a test container, set `BINCOVERING_BUILDER_URL` to a
temporary host QA server and supply its ephemeral account using
`BINCOVERING_BUILDER_USERNAME` and `BINCOVERING_BUILDER_PASSWORD`; custom programs
still execute through the host supervisor without an engine socket in the browser.
Generated verification
artifacts and screenshots stay under ignored outputs. See
[the language guide](BUILDER_LANGUAGE.md) for accepted syntax and helper operations.
