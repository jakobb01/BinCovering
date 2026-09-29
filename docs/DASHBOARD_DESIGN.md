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

The page has a lightweight brand/navigation bar, a title and real workspace counts,
then two columns: experiment configuration on the left, history and results on the
right. The maximum shell width is 1440px. Padding is 48px on wide screens, 28px at
intermediate widths, and 16px on phones.

At 900px and below, columns stack. At 600px and below, experiment table rows become
readable records with all actions reachable by touch. History remains bounded to
420px with its own scroll area. Experiment groups use exact saved names. Search
and selection stay visible above the list. Results open below history and receive
focus, with scrolling that respects reduced-motion preferences.

Do not put a sidebar or tabs in a view with no distinct destinations to navigate.
New screens can introduce them when the task actually needs them. Preserve a clear
path from configuration to history to result interpretation.

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

## Component rules

### Actions

- `.button-primary` is for **Run experiment**. Keep the other actions quieter.
- `.button-secondary` is for a main alternative such as **Compare selected**.
- `.button-ghost` is for toolbars and row actions. Give it an explicit hover/focus state.
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
Filtering must not lose selections from other groups. Preserve expanded group state,
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
Keep configuration/source details in **Settings and provenance**. Figures link to
the full-size image so small screens can inspect labels. Keep the scientific meaning
of percentages, OPT/upper bounds, paired comparisons, and uncertainty labels intact;
see `RESEARCH_PLOTS.md`. Do not change interpretation for visual simplicity.

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

Future ideas such as tabs, drawers, themes, or a full component gallery are proposals
until explicitly adopted. Extend the smallest component that serves the research task.
