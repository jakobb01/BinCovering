# Dashboard design guide

This is the shared visual and interaction contract for the BinCovering dashboard.
Read it before adding or changing dashboard components. The implementation lives
in `src/bincovering/web/templates/index.html`, `web/static/style.css`, and
`web/static/app.js`. CSS custom properties are the source of truth for visual tokens.

## Direction and reference

Jakob requested the visual direction and component guidance of
[02UI Components](https://02ui.com/components/) on 2026-09-29. The dashboard adapts
its warm neutral surfaces, restrained dark typography, orange accents, soft borders,
and clear action hierarchy to an academic experiment workspace.

This is our own HTML/CSS implementation. The reference's logo, webfont,
and demo assets are not bundled. System fonts keep the local dashboard usable offline.
These project-specific rules are informed by the following component guides:

- [Buttons](https://02ui.com/components/button/): distinguish the launch action from
  alternatives and row actions; keep labels explicit and show request feedback.
- [Tables](https://02ui.com/components/table/): meaningful headers, selection feedback,
  stable columns, accessible row context, and a way to clear selected records.
- [Accordions](https://02ui.com/components/accordion/): disclose groups and optional
  settings without breaking the reader's place in the page.
- [Badges](https://02ui.com/components/badge-and-tag/): express state with text and
  color together.

## Layout

The workspace navigation is rendered by the shared `_site_header.html` template,
used on every dashboard page. Keep Builder's plain **BinCovering** text wordmark
on the left, the menu centered, and the account name / Log out on the right. The
menu shows **Accounts** (`/admin`) only to administrators, beside the other tabs;
never inject it next to the account name from page scripts. The active page has
`aria-current="page"`, dark text and an orange underline with stable label widths.
On smaller screens the centered menu occupies its own row. Long account names
truncate visually with the full name available in a title. Sign-in and registration
reuse the wordmark portion of the same template.

The navigation has three research pages. **Dashboard** (`/`) owns experiment configuration,
workspace counts, all active jobs, and six recent completed/failed results. **Saved
experiments** (`/experiments`) owns the full history, search, grouping, selection,
comparison, and study plots. **Builder** (`/builder`) owns the C visual graph workspace,
saved component library, compact Custom logic, previews, and integrated traces.
Keep the history heading compact and use the toolbar counts;
do not repeat the home hero, workspace metrics, or a second large panel heading.
The first saved row should start within 500px of the page top on desktop. Both pages
use the same result viewer. Do not duplicate
launch controls on the history page or turn navigation into in-page anchors.

The home page uses two columns: configuration and recent activity. At 900px and
below they stack. History spans the available page width and uses normal page
scrolling; never restore the old 420px nested list. Search and selection controls
stay sticky within history. At 600px and below table rows become compact records.
Experiment groups use exact saved names. Maximum shell width is 1440px, with 48px
wide-screen padding, 28px at intermediate widths, and 16px on phones.

Results open in a native modal viewer with a fixed header and tabs. Closing restores
keyboard focus and the page scroll position. Preserve a clear path from launching a
study to reviewing its recorded evidence.

## Visual tokens

Use existing tokens rather than hardcoding a new color or spacing for each component.
If a new token is needed, add it to `:root` and update this guide.

| Token | Value | Purpose |
| --- | --- | --- |
| `--canvas` | `#f7f7f4` | Warm page background |
| `--surface` | `#ffffff` | Form and workspace panels |
| `--surface-soft` | `#f1f0ec` | Group headers and supporting surfaces |
| `--surface-hover` | `#eae9e3` | Quiet hover treatment |
| `--ink` | `#26251d` | Primary text and launch button |
| `--ink-muted` | `#65645c` | Supporting text |
| `--border` | `#deddd5` | Panel and row divisions |
| `--border-strong` | `#c2c0b5` | Input outlines |
| `--accent` | `#f45100` | Small decorative accents and selection edge |
| `--accent-ink` | `#b43c00` | Accessible orange links/focus on light surfaces |
| `--accent-soft` | `#fff0e6` | Checked algorithm cards |
| `--success-ink` / `--success-soft` | `#216448` / `#e4f1e9` | Completed state |
| `--warning-ink` / `--warning-soft` | `#865313` / `#fbf0dc` | Running and queued states |
| `--danger-ink` / `--danger-soft` | `#a6313e` / `#fbe9eb` | Failures and removal |
| `--radius-control` | `8px` | Controls and quiet disclosures |
| `--radius-panel` | `16px` | Main workspace panels |
| `--space-1` … `--space-7` | `4, 8, 12, 16, 24, 32, 48px` | Spacing scale |

Panel padding is 28px on wide screens and 20–24px elsewhere. Use 10px corner rounding
for inset groups and result cards. Avoid decorative gradients and large shadows;
structure should come from spacing, borders, and surface contrast.

Typography uses `--font-sans` (Segoe UI / Helvetica Neue / Arial / sans-serif) and
`--font-mono` (SFMono-Regular / Consolas / Liberation Mono / monospace). Use the mono
stack for metadata and execution IDs. The title is 34–58px, section headings 24px,
body text 15px, controls 12–13px, and supporting metadata 10–12px. Headings have
moderate weight and slightly tight tracking. Numbers use tabular figures where useful.
Saved experiments, Builder and Accounts use the shared `.page-header-compact`
rules: 36px titles on desktop and 30px on phones, 14px / 13px introductions, and
the same compact eyebrow and spacing. Every page title keeps its orange full stop;
Builder mode switching changes only the title text, preserving the accent span.

## Component rules

### Actions

- `.button-primary` is for **Run experiment**. Keep the other actions quieter.
- `.button-secondary` is for a main alternative such as **Compare selected**.
- `.button-plot` uses accessible orange (`--accent-ink`) with white text for **Plot**.
- **Inspect** uses the neutral bordered `.button-secondary`; **More** uses a quiet
  outlined disclosure. Keep row targets at least 40px on desktop and 44px on phones.
  Use compact horizontal padding so Inspect, Plot, and More stay in one aligned row.
  More opens a small anchored menu; it must not expand the table row or wrap the
  primary actions. Escape and clicking outside dismiss it.
- `.button-ghost` is for quiet toolbar actions. Give it an explicit hover/focus state.
- The shared `.button-accent`, `.button-accent-soft`, and `.button-accent-outline`
  variants provide filled, soft, and outlined orange actions. Use them with the
  `.button` base class, which supplies spacing, rounding, focus and request states.
  Sign in, Create account and Save password use the filled variant; account password
  reset uses the outline, Enable and Reassign use the soft variant, and Disable
  retains a restrained red outline. Account actions have 44px minimum targets.
- `.button-danger` is for **Remove**, with a visible verb and restrained red text.
- Use `<button type="button">` for actions and real links for navigation/downloads.
  Form submission alone uses `type="submit"`.
- Keep Inspect and Plot visible in a finished row. Put Pin/Unpin, Export, and Remove
  in the native **More** disclosure. Active rows expose Cancel. Native disclosure
  behavior provides keyboard operation; Escape closes a row's expanded actions.
- During a request, prevent duplicate submissions and set `aria-busy`. Keep the label
  and dimensions steady. Let an incomplete form explain errors when submitted.
- The row context must be available to assistive technology; current controls use
  `aria-describedby` referencing the execution ID.

### Forms

Visible labels are required. Place hints below their input; placeholders are examples,
not replacements for labels. Numeric research parameters use number fields, discrete
choices use selects, and algorithm choices use checkboxes. Do not use switches for
choices that only apply when a study is launched.

Separate study identity/counts, input sequence, and algorithms. Less-used parameters
belong in **Algorithm settings**. Preserve the actual defaults and numeric constraints.
The orange checked-card treatment highlights selected algorithms without replacing
native checkbox state. Controls have 40px height, with larger touch targets on phones.

### History and tables

Keep fuzzy search, matched/total counts, selected count, and **Clear selection** together.
Filtering must not lose selections from other groups. Use `static/search.js` for
query semantics instead of adding page-local matchers; see `SEARCH.md`. Keep the
ordering/count examples visible near the search input. Preserve expanded group state,
scroll position, open row actions, and keyboard focus during background refreshes.
Unchanged polls must not rebuild the list.

Use a real table with a caption and scoped column headers. Keep execution, status,
trial progress, and actions aligned. Full execution IDs remain available even when
visually truncated. A selected row has both a checked box and an orange edge;
hover and selection must remain distinguishable.

Use labelled badges for completed/running/queued/failed states. A dot alone is not a
status. Show progress only from recorded completed/total trial counts. Workspace
counts must also come from saved records; never add decorative or invented metrics.

### Feedback and empty states

Keep validation feedback near the experiment form and history actions near history.
Inline messages persist until superseded. Removal feedback includes Undo. Removal
is reversible local trash behavior; the UI must not describe it as permanent deletion.

Distinguish an empty workspace from an empty search. An empty workspace directs the
researcher toward a first run. No matches offers **Clear search**. Loading has its
own labelled state. Failure feedback uses both explanatory text and color.

### Results

Use compact cards for algorithm summaries, with explicit units and trial counts.
Keep configuration/source details in **Settings and provenance**. Use the native result dialog for Plot, Inspect, and Compare. Its Plot, Summary,
Settings and provenance, and Trace tabs must support arrows/Home/End, visible focus, Escape,
and a labelled Close action. Preserve the opener and scroll position on close.

Open immediately with a loading state; do not wait for figure generation before
showing the viewer. A new request invalidates earlier responses, including responses
after closing. Keep errors inside the viewer, and hide stale figure/download links.

Figures initially fit the viewport. Offer **Zoom to full size** with a scrollable
image region, **Fit to view**, **Open PNG**, and **Download SVG**. For the three-panel
overview offer individual panels, so labels remain readable on small screens.
The overview algorithm selector includes backend and parameter values, using the
same unique groups as the plot data. Mass accounting compares all recorded algorithm
groups and hides the overview-only selector. Never combine distinct identities into
one choice.

Single-run choices are Research overview, Coverage targets, Paired comparison with
DNF, and Mass accounting. Selected-run studies offer Ordering sensitivity, ThrowBin
parameter study, and Paired comparison with DNF.

Coverage targets has a labelled 0–100% numeric control, initially 70%. Changing it
updates both the plotted guide and an accessible disclosure containing the table of
reached/valid trial counts and empirical shares. Keep the disclosure closed initially
so the target plot fits on phones; preserve its open state when the target changes. Explain the recorded OPT/upper-bound denominator and avoid
calling observed frequencies future guarantees. Paired charts explain the sign of
differences and compare identical ordered inputs. Keep the scientific meaning
of percentages, OPT/upper bounds, paired comparisons, and uncertainty labels intact;
see `RESEARCH_PLOTS.md`. Do not change interpretation for visual simplicity.

### Builder and accounts

Reuse the same page shell, tokens, navigation, and labelled actions on Builder,
login, and account administration. The graph is the primary workspace: palette,
canvas, inspector, and a visible test/trace panel. Custom logic is a small field
with Simple Python/defined pseudocode, contextual help, and insertable examples.
Keep parameter/state/typed-port declarations in the advanced disclosure.
Use separate **Algorithms** and **Item generators** tabs with independent drafts
and palettes. Keep the name/starter/save toolbar compact; domain and coverage
threshold are graph metadata, with no toolbar fields. Match proposal C's simple
symbol/name cards and circular execution handles. Value connections are an explicit
advanced toggle; already wired values remain visible.
Give **Run preview** a filled accessible orange button, **Save draft** a soft orange
button, and **Make available** an orange outline. Use `--accent-ink` for readable
action text/fill and `--accent-soft` for the supporting action surface.

Every editable graph card exposes **Remove** visibly; keep it labelled on Custom
and reusable-component instances. Removal and affected wiring are reversible with
Undo/Redo. Fixed lifecycle entry points explain which connected operations can be
changed. Library archival is a separate reversible action and does not change
frozen experiment revisions.

Control connections use directional arrows and labelled condition branches. Typed
data connections are visually distinct and attach to their declared ports. Provide
keyboard addition, socket connection, inspection, movement, and removal alongside
drag/drop. Preserve title/socket/edge focus when graph rendering refreshes.
The dotted canvas fills its column with no unused bottom region or native scrollbars.
Drag its background to pan; wheel pans and Control/Command-wheel zooms. Fit and
zoom controls stay inside the canvas. Circular handles support live drag wiring and
click/keyboard wiring, with lines anchored at the circle centres. On phones the palette,
graph, and inspector stack without page-level horizontal overflow; graph controls
use the same touch-target rules as the rest of the dashboard.

Traces show actual recorded execution and link events to graph nodes, branch edges,
current items, state, and bin loads. Playback navigates that evidence by operation
or item. Label stale previews, fixture setup, errors, missing capture, and truncated
streams/snapshots. Saved results reopen the frozen graph; old item/count traces
retain their original meaning. Never add graph/bin details absent from the record.
**Verify on a small sequence** is its own panel alongside the editing workspace.
Verification captures its trace automatically with server-owned resource budgets;
there is no user trace-limit/disable control. Full experiment traces retain their
optional settings; run logs and provenance remain mandatory. Keep the read-only
verification graph spacious (600px desktop, 520px phone), with Fit/zoom/pan controls
and a labelled lifecycle/component context. Cache its graph and timeline while
stepping in the same context; update highlights without rebuilding, centring or
scrolling the graph or editing canvas on every event. Preserve the verification
view when returning from a nested component. Timeline/state panes have stable
heights, and event scrolling stays inside the timeline.

Available algorithm/generator choices show revision, input access, and numerical
domain, with typed parameter controls and an **Open in Builder** link. Use the
existing main form for experiment launch. Account labels and logout belong in the
site bar; administration is a separate administrator page. Draft recovery is scoped
to the signed-in account, and logout clears cached private drafts.
Login links to **Create account**, a separate form with account name, password and
confirmation. Registration grants researcher access without a role selector. Keep
errors inline and preserve the account name after an error; never refill passwords.
The administrator's **All workspace accounts** panel lists every database account,
including self-registered and disabled accounts, with a real count, role, status,
join date, and labelled Enable/Disable and Reset password actions. Reset opens an
inline form with Save password and Cancel, restoring focus when closed or saved.

## Accessibility and motion

Use native controls, visible keyboard focus, a skip link, labelled scroll regions,
and polite live regions for status feedback. Decorative icons use `aria-hidden`.
Do not introduce icon-only controls without an accessible name. Color must never
be the sole indication of state. Quiet text and active labels should meet 4.5:1
contrast against their surface; focus/meaningful control outlines need clear contrast.

Avoid page-level horizontal overflow at 390px. Interactive mobile actions should be
at least 40px high, with primary/toolbar targets around 44px. Respect
`prefers-reduced-motion` and forced-color modes. This guide does not claim a formal
accessibility certification; keyboard and responsive behavior must be checked as
components evolve.

## Validation for future changes

1. Reuse the documented classes and tokens. Add new variants explicitly here.
2. Exercise the real workflow: launch, inspect, plot, select, search, expand More,
   pin, export, remove/undo, and compare.
3. Verify keyboard focus survives background polling and disclosures are operable.
4. Review screenshots at desktop width and 390px, including populated, selected,
   empty, loading, and error states. Check long names and execution IDs.
5. Run applicable web tests. The opt-in Playwright workflow in `tests/test_browser.py`
   covers the actual browser; screenshots stay in ignored `outputs/`.

Future ideas such as drawers, themes, or a full component gallery are proposals
until explicitly adopted. Extend the smallest component that serves the research task.
