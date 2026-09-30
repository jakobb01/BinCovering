const isHistoryPage = document.body.dataset.page === 'experiments';
const selected = new Set();
const groupState = new Map();
const message = document.querySelector('#message');
const historyMessage = document.querySelector('#history-message');
let refreshing = false;
let cachedRuns = [];
let lastRecords = '';
let dashboardSession;
let availableBuilders = {algorithms: [], generators: []};
const dashboardSessionReady = fetch('/api/session').then(async response => {
  const value = await response.json();
  if (!response.ok || !value.user) { location.href = '/login?next=' + encodeURIComponent(location.pathname); throw Error('Please sign in.'); }
  dashboardSession = value;
  document.querySelector('#account-name').textContent = value.user.username;
  return value;
});

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function feedback(target, text, error = false) {
  if (!target) return;
  target.textContent = text;
  target.classList.toggle('feedback-error', error);
}

async function api(url, options) {
  const session = await dashboardSessionReady;
  const headers = {...(options?.headers || {})};
  if (options?.method && options.method !== 'GET') headers['X-CSRF-Token'] = session.csrf_token;
  const response = await fetch(url, {...options, headers});
  if (response.status === 401) { location.href = '/login?next=' + encodeURIComponent(location.pathname); throw Error('Please sign in again.'); }
  const data = await response.json();
  if (!response.ok) throw Error(data.error || response.statusText);
  return data;
}
const post = (url, body) => api(url, {
  method: 'POST', headers: {'Content-Type': 'application/json'},
  body: JSON.stringify(body || {})
});
const endpoint = (action, id) => '/api/' + action + '/' + id.split('/').map(encodeURIComponent).join('/');

function busy(control, value) {
  control.disabled = value;
  control.setAttribute('aria-busy', String(value));
}

function button(label, action, variant = 'ghost') {
  const control = element('button', 'button button-' + variant, label);
  control.type = 'button';
  control.onclick = async () => {
    if (control.disabled) return;
    const ownedFocus = document.activeElement === control;
    const focusedRun = control.closest('[data-run]')?.dataset.run;
    const focusedAction = control.dataset.action;
    busy(control, true);
    try { await action(); }
    catch (error) { feedback(historyMessage, error.message, true); }
    finally {
      busy(control, false);
      if (ownedFocus && (document.activeElement === document.body || document.activeElement === control)) {
        const row = [...document.querySelectorAll('#runs [data-run]')].find(node => node.dataset.run === focusedRun);
        const next = control.isConnected ? control : [...(row?.querySelectorAll('[data-action]') || [])].find(node => node.dataset.action === focusedAction);
        next?.focus({preventScroll: true});
      }
    }
  };
  return control;
}

const viewer = document.querySelector('#results');
const viewerStatus = document.querySelector('#viewer-status');
let view = {ids: [], mode: 'single', data: null};
let viewRequest = 0;
let returnFocus = null;
let returnRun = null;
let returnAction = null;
let pagePosition = 0;
let historyPosition = 0;
let previousBodyOverflow = '';
let savedTraceController = null;
let savedTraceRows = [];
let savedTraceRequest = 0;

function switchTab(name, focus = false) {
  for (const tab of viewer.querySelectorAll('[role=tab]')) {
    const active = tab.id === 'tab-' + name;
    tab.setAttribute('aria-selected', String(active));
    tab.tabIndex = active ? 0 : -1;
    document.querySelector('#' + tab.getAttribute('aria-controls')).hidden = !active;
    if (active && focus) tab.focus();
  }
  if (name === 'plot' && view.data && !document.querySelector('#figure').getAttribute('src')) requestPlot();
  if (name === 'trace') void loadSavedTraces();
}
for (const tab of viewer.querySelectorAll('[role=tab]')) {
  tab.onclick = () => switchTab(tab.id.slice(4));
  tab.onkeydown = event => {
    const tabs = [...viewer.querySelectorAll('[role=tab]')];
    const index = tabs.indexOf(tab);
    let next;
    if (event.key === 'ArrowRight') next = (index + 1) % tabs.length;
    else if (event.key === 'ArrowLeft') next = (index + tabs.length - 1) % tabs.length;
    else if (event.key === 'Home') next = 0;
    else if (event.key === 'End') next = tabs.length - 1;
    else return;
    event.preventDefault();
    switchTab(tabs[next].id.slice(4), true);
  };
}

function zoomFigure(zoomed) {
  const stage = document.querySelector('#figure-stage');
  stage.classList.toggle('is-zoomed', zoomed);
  document.querySelector('#plot-fit').setAttribute('aria-pressed', String(!zoomed));
  document.querySelector('#plot-zoom').setAttribute('aria-pressed', String(zoomed));
  stage.scrollTo(0, 0);
}
document.querySelector('#plot-fit').onclick = () => zoomFigure(false);
document.querySelector('#plot-zoom').onclick = () => { zoomFigure(true); document.querySelector('#figure-stage').focus(); };
document.querySelector('#viewer-close').onclick = () => viewer.close();
viewer.addEventListener('close', () => {
  ++viewRequest;
  ++savedTraceRequest;
  savedTraceController?.destroy();
  document.body.style.overflow = previousBodyOverflow;
  const replacement = [...document.querySelectorAll('#runs [data-run]')]
    .find(row => row.dataset.run === returnRun);
  const control = returnFocus?.isConnected ? returnFocus
    : [...(replacement?.querySelectorAll('[data-action]') || [])].find(node => node.dataset.action === returnAction);
  control?.focus({preventScroll: true});
  window.scrollTo(0, pagePosition);
  document.querySelector('#runs').scrollTop = historyPosition;
});

function clearFigure() {
  const image = document.querySelector('#figure');
  image.onload = null;
  image.onerror = null;
  image.hidden = true;
  image.removeAttribute('src');
  document.querySelector('#figure-stage').hidden = true;
  document.querySelector('#plot-tools').hidden = true;
  document.querySelector('#target-results').hidden = true;
  for (const selector of ['#figure-link', '#figure-svg']) document.querySelector(selector).removeAttribute('href');
  zoomFigure(false);
}

function setFigure(data, request) {
  const image = document.querySelector('#figure');
  image.onload = () => {
    if (request !== viewRequest || !viewer.open) return;
    image.hidden = false;
    document.querySelector('#figure-stage').hidden = false;
    document.querySelector('#plot-tools').hidden = false;
    document.querySelector('#figure-link').href = data.url;
    document.querySelector('#figure-svg').href = data.svg_url;
    document.querySelector('#figure-svg').hidden = !data.svg_url;
    feedback(viewerStatus, '');
    document.querySelector('#panel-plot').setAttribute('aria-busy', 'false');
  };
  image.onerror = () => {
    if (request !== viewRequest || !viewer.open) return;
    feedback(viewerStatus, 'The plot image could not be loaded. Choose a plot type or panel to try again.', true);
    document.querySelector('#panel-plot').setAttribute('aria-busy', 'false');
  };
  image.alt = ({overview: 'Input distribution, trial coverage, and outcome frequencies', mass: 'Covered mass, excess bin load, and unfinished mass', ordering: 'Coverage by input ordering and swaps', parameters: 'ThrowBin coverage by parameter and input size', reliability: 'Share of trials reaching each coverage target', paired: 'Algorithm differences compared with DNF on identical trial inputs'})[data.kind] || 'Research plot';
  if (data.target_data) showTargetResults(data.target_data);
  image.src = data.url + (data.url.includes('?') ? '&' : '?') + 't=' + Date.now();
}

function algorithmLabel(algorithm, configured = []) {
  const id = algorithm.algorithm || algorithm.id || String(algorithm);
  if (!id.startsWith('custom:')) return id.replaceAll('_', ' ');
  const match = configured.find(spec => spec.id === id || spec.id + '@' + spec.revision === id);
  const name = algorithm.algorithm_name || algorithm.frozen?.name || match?.frozen?.name || 'Custom algorithm';
  const revision = algorithm.revision || algorithm.algorithm_revision || match?.revision || id.split('@')[1];
  const access = algorithm.input_access || algorithm.access || algorithm.frozen?.graph?.access || match?.frozen?.graph?.access;
  return name + (revision ? ' · revision ' + revision : '') + (access ? ' · ' + access : '');
}
function show(data) {
  view.data = data;
  document.querySelector('#result-context').textContent = data.manifest?.name || (data.runs ? `${data.runs.length} selected runs` : `${view.ids.length} selected runs`);
  document.querySelector('#details').textContent = JSON.stringify(data, null, 2);
  const area = document.querySelector('#summary');
  area.replaceChildren();
  const groups = data.runs || [{path: '', summary: data.summary || []}];
  for (const group of groups) {
    if (group.path) area.append(element('p', 'result-run-title', group.path));
    for (const row of group.summary) {
      const card = element('article', 'result-card');
      card.append(element('h3', '', `${algorithmLabel(row, data.manifest?.config?.algorithms || [])} · ${row.backend}`));
      const value = row.mean_covered == null ? '—' : new Intl.NumberFormat(undefined, {maximumFractionDigits: 2}).format(row.mean_covered);
      card.append(element('strong', 'result-value', value));
      card.append(element('p', '', 'Mean covered bins'));
      card.append(element('p', '', `${row.successful_trials} successful · ${row.failed_trials} failed trials`));
      area.append(card);
    }
  }
  if (!area.childElementCount) area.append(element('p', 'field-help', 'No completed algorithm summaries are available for this selection.'));
  document.querySelector('#comparison-note').textContent = 'same_trial_inputs' in data
    ? (data.same_trial_inputs ? 'These runs use matching trial inputs.' : 'These runs use different trial inputs; this is not a paired comparison.') : '';
  if (view.mode === 'single') {
    // Summary and plotting share the same unique algorithm/backend/parameter groups.
    const configured = data.manifest?.config?.algorithms || [];
    const seen = new Set();
    const algorithms = data.summary?.length ? data.summary : configured.filter(algorithm => {
      const params = algorithm.params || {};
      const key = JSON.stringify([algorithm.id, algorithm.revision, algorithm.backend || 'python', Object.keys(params).sort().map(key => [key, params[key]])]);
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
    const select = document.querySelector('#plot-algorithm');
    select.replaceChildren();
    algorithms.forEach((algorithm, index) => {
      const params = algorithm.parameters || algorithm.params || {};
      const settings = Object.entries(params).map(([key, value]) => `${key}=${value}`).join(', ');
      const label = algorithmLabel(algorithm, configured) + ` · ${algorithm.backend || 'python'}` + (settings ? ` · ${settings}` : '');
      const option = element('option', '', label);
      option.value = index;
      select.append(option);
    });
  }
}

function showTargetResults(data) {
  const area = document.querySelector('#target-results');
  area.replaceChildren();
  area.append(element('summary', '', `Trials reaching at least ${data.target}% coverage · ${(data.groups || []).length} algorithm groups`));
  const table = element('table', 'target-table');
  table.append(element('caption', 'visually-hidden', 'Observed trials reaching the selected coverage target'));
  const header = element('tr');
  for (const text of ['Algorithm / settings', 'Reached / valid trials', 'Share of trials']) {
    const th = element('th', '', text); th.scope = 'col'; header.append(th);
  }
  const head = element('thead'); head.append(header); table.append(head);
  const body = element('tbody');
  for (const group of data.groups || []) {
    const row = element('tr');
    row.append(element('td', '', group.label + (group.reference_label ? ` · ${group.reference_label}` : '')), element('td', '', `${group.reached} / ${group.total}`), element('td', '', group.percentage == null ? 'Unavailable' : `${Number(group.percentage).toFixed(1)}%`));
    body.append(row);
  }
  table.append(body); area.append(table);
  area.hidden = false;
}

function plotDescription() {
  const kind = document.querySelector('#plot-kind').value;
  viewer.dataset.kind = kind;
  document.querySelector('#overview-control').hidden = kind !== 'overview';
  document.querySelector('#target-control').hidden = kind !== 'reliability';
  document.querySelector('#algorithm-control').hidden = view.mode !== 'single' || kind !== 'overview';
  document.querySelector('#plot-description').textContent = ({
    overview: 'Input sizes, coverage in each trial, and the frequency of outcomes. Choose one panel for larger labels.',
    mass: 'Where the input mass went: useful covered mass, excess load in covered bins, unfinished bins, and discarded items. Older runs may not contain this evidence.',
    ordering: 'Select related runs with different ordering or swap settings. Each algorithm is shown separately; input and study settings must match.',
    parameters: 'Select ThrowBin runs with varying bin ratio and input size. Fixed settings and algorithm variants remain separate.',
    reliability: 'How often does an algorithm reach at least your chosen coverage target? Adjust the target to update the guide and observed trial counts. These are empirical frequencies, not future guarantees.',
    paired: 'Compare each algorithm with DNF on the identical ordered trial input. Positive differences favor the other algorithm; negative differences favor DNF. Distinct settings stay separate.'
  })[kind] || '';
}

async function requestPlot() {
  const request = ++viewRequest;
  clearFigure();
  plotDescription();
  feedback(viewerStatus, 'Generating plot…');
  document.querySelector('#panel-plot').setAttribute('aria-busy', 'true');
  const kind = document.querySelector('#plot-kind').value;
  try {
    const targetInput = document.querySelector('#coverage-target');
    if (kind === 'reliability' && !targetInput.reportValidity()) throw Error('Choose a coverage target from 0 to 100%.');
    const data = view.mode === 'single'
      ? await post(endpoint('plot', view.ids[0]), {kind, algorithm: Number(document.querySelector('#plot-algorithm').value), panel: document.querySelector('#plot-panel').value, ...(kind === 'reliability' ? {target: Number(targetInput.value)} : {})})
      : await post('/api/study-plot', {ids: view.ids, kind});
    if (request !== viewRequest || !viewer.open) return;
    setFigure(data, request);
  } catch (error) {
    if (request !== viewRequest || !viewer.open) return;
    feedback(viewerStatus, error.message, true);
    document.querySelector('#panel-plot').setAttribute('aria-busy', 'false');
  }
}
for (const id of ['#plot-kind', '#plot-algorithm', '#plot-panel', '#coverage-target']) document.querySelector(id).onchange = requestPlot;

async function openViewer(ids, mode = 'single', tab = 'plot') {
  const request = ++viewRequest;
  view = {ids: [...ids], mode, data: null};
  ++savedTraceRequest;
  savedTraceController?.destroy();
  document.querySelector('#saved-trace-view').replaceChildren();
  document.querySelector('#trace-run').replaceChildren(...ids.map(id => { const option = element('option', '', id); option.value = id; return option; }));
  document.querySelector('#trace-run').closest('label').hidden = ids.length < 2;
  savedTraceRows = [];
  returnFocus = document.activeElement;
  returnRun = returnFocus?.closest('[data-run]')?.dataset.run;
  returnAction = returnFocus?.dataset.action;
  pagePosition = window.scrollY;
  historyPosition = document.querySelector('#runs').scrollTop;
  previousBodyOverflow = document.body.style.overflow;
  clearFigure();
  document.querySelector('#summary').replaceChildren(element('p', 'field-help', 'Loading results…'));
  document.querySelector('#details').textContent = 'Loading saved settings…';
  document.querySelector('#comparison-note').textContent = '';
  document.querySelector('#result-context').textContent = mode === 'single' ? ids[0] : `${ids.length} selected runs`;
  document.querySelector('#results-title').textContent = mode === 'single' ? 'Experiment results' : 'Study results';
  const kind = document.querySelector('#plot-kind');
  kind.replaceChildren();
  for (const [value, label] of (mode === 'single' ? [['overview', 'Research overview'], ['reliability', 'Coverage targets'], ['paired', 'Paired comparison with DNF'], ['mass', 'Mass accounting']] : [['ordering', 'Ordering sensitivity'], ['parameters', 'ThrowBin parameter study'], ['paired', 'Paired comparison with DNF']])) {
    const option = element('option', '', label); option.value = value; kind.append(option);
  }
  document.querySelector('#algorithm-control').hidden = mode !== 'single';
  document.querySelector('#plot-panel').value = 'all';
  for (const control of viewer.querySelectorAll('.viewer-controls select, .viewer-controls input')) control.disabled = true;
  plotDescription();
  feedback(viewerStatus, 'Loading saved experiment evidence…');
  switchTab(tab);
  viewer.showModal();
  document.body.style.overflow = 'hidden';
  try {
    const data = mode === 'single' ? await api(endpoint('inspect', ids[0]))
      : await api('/api/compare?' + ids.map(id => 'id=' + encodeURIComponent(id)).join('&'));
    if (request !== viewRequest || !viewer.open) return;
    show(data);
    for (const control of viewer.querySelectorAll('.viewer-controls select, .viewer-controls input')) control.disabled = false;
    if (tab === 'plot') await requestPlot();
    else feedback(viewerStatus, 'Choose a plot type to generate a figure.');
  } catch (error) {
    if (request !== viewRequest || !viewer.open) return;
    feedback(viewerStatus, error.message, true);
    document.querySelector('#summary').replaceChildren(element('p', 'feedback feedback-error', error.message));
    document.querySelector('#details').textContent = error.message;
  }
}
function updateSelectionCount(filteredCount, groupCount) {
  document.querySelector('#history-count').textContent = `${filteredCount} of ${cachedRuns.length} experiments · ${groupCount} groups · ${selected.size} selected`;
  document.querySelector('#clear-selection').hidden = selected.size === 0;
}

function emptyState(body, searching) {
  const state = element('div', 'empty-state');
  state.append(element('h3', '', searching ? 'No matching experiments' : 'Your workspace starts here.'));
  state.append(element('p', '', searching ? 'Try a shorter name, or clear your search.' : 'Run your first experiment to start comparing results.'));
  if (searching) state.append(button('Clear search', async () => {
    document.querySelector('#run-search').value = '';
    renderRuns();
    document.querySelector('#run-search').focus();
  }));
  body.append(state);
}

function runActions(run, runLabel, open = false) {
  const actions = element('div', 'row-actions');
  const inspect = button('Inspect', () => { void openViewer([run.id], 'single', 'summary'); }, 'secondary');
  actions.append(inspect);
  if (['running', 'queued'].includes(run.status)) {
    actions.append(button('Cancel', async () => {
      await post(endpoint('cancel', run.id)); feedback(historyMessage, 'Cancellation requested');
    }));
  } else {
    actions.append(button('Plot', () => { void openViewer([run.id]); }, 'plot'));
    const menu = element('details', 'row-menu');
    menu.open = open;
    const menuTitle = element('summary', '', 'More');
    menuTitle.dataset.action = 'more';
    menuTitle.append(element('span', 'visually-hidden', ' actions for ' + run.id));
    const extra = element('div', 'action-list');
    const pin = button(run.pinned ? 'Unpin' : 'Pin', async () => {
      await post(endpoint('pin', run.id), {pinned: !run.pinned}); await refresh();
    });
    pin.dataset.action = 'pin';
    extra.append(pin);
    const download = element('a', 'button button-ghost', 'Export');
    download.href = endpoint('export', run.id);
    extra.append(download);
    if (!run.pinned) extra.append(button('Remove', async () => {
      const removed = await post(endpoint('remove', run.id));
      selected.delete(run.id);
      historyMessage.classList.remove('feedback-error');
      historyMessage.replaceChildren(document.createTextNode('Experiment moved to trash. '), button('Undo', async () => {
        await post('/api/restore/' + removed.token);
        feedback(historyMessage, 'Experiment restored');
        await refresh();
      }));
      await refresh();
    }, 'danger'));
    menu.append(menuTitle, extra); actions.append(menu);
  }
  for (const control of actions.querySelectorAll('button, a, summary')) {
    control.setAttribute('aria-describedby', runLabel.id);
    if (!control.dataset.action) control.dataset.action = control.textContent;
  }
  return actions;
}

function renderRecent() {
  const body = document.querySelector('#runs');
  const active = document.activeElement;
  const focusedRun = active?.closest('[data-run]')?.dataset.run;
  const focusedAction = active?.dataset.action;
  const openMenus = new Set([...body.querySelectorAll('.row-menu[open]')].map(menu => menu.closest('[data-run]').dataset.run));
  const activeRuns = cachedRuns.filter(run => ['running', 'queued'].includes(run.status));
  const recent = cachedRuns.filter(run => !['running', 'queued'].includes(run.status)).slice(0, 6);
  body.replaceChildren();
  for (const [index, run] of [...activeRuns, ...recent].entries()) {
    const card = element('article', 'recent-run'); card.dataset.run = run.id;
    const heading = element('div', 'recent-heading');
    heading.append(element('h3', '', run.name), element('span', 'status-badge status-' + (['completed', 'running', 'queued', 'failed', 'cancelled', 'interrupted'].includes(run.status) ? run.status : 'unknown'), run.status));
    const label = element('span', 'run-id', run.id); label.id = 'recent-label-' + index;
    card.append(heading, label, element('p', 'run-meta', `${(run.config?.n ?? '—').toLocaleString()} items · ${run.config?.ordering ?? '—'} · ${run.completed_trials ?? 0}/${run.total_trials ?? '—'} trials`));
    card.append(runActions(run, label, openMenus.has(run.id)));
    body.append(card);
    if (run.id === focusedRun && focusedAction) [...card.querySelectorAll('[data-action]')].find(node => node.dataset.action === focusedAction)?.focus({preventScroll: true});
  }
  if (!body.childElementCount) emptyState(body, false);
}

function renderRuns() {
  const pageY = window.scrollY;
  if (isHistoryPage) renderHistory(); else renderRecent();
  window.scrollTo(0, pageY);
}

function renderHistory() {
  const query = document.querySelector('#run-search').value;
  const filtered = cachedRuns.filter(run => globalThis.BinCoveringSearch.matchesRun(query, run));
  const groups = new Map();
  for (const run of filtered) {
    if (!groups.has(run.name)) groups.set(run.name, []);
    groups.get(run.name).push(run);
  }
  const body = document.querySelector('#runs');
  const scrollTop = body.scrollTop;
  const active = document.activeElement;
  const focusedRun = active?.closest('[data-run]')?.dataset.run;
  const focusedGroup = active?.parentElement?.classList.contains('run-group') ? active.parentElement.dataset.group : null;
  const focusedAction = active?.dataset.action;
  const openMenus = new Set([...body.querySelectorAll('.row-menu[open]')].map(menu => menu.closest('[data-run]').dataset.run));
  body.replaceChildren();
  updateSelectionCount(filtered.length, groups.size);
  let rowNumber = 0;
  for (const [name, runs] of groups) {
    const group = element('details', 'run-group');
    group.dataset.group = name;
    group.open = query.trim() ? true : (groupState.get(name) ?? groups.size === 1);
    group.addEventListener('toggle', () => {
      if (group.isConnected && !document.querySelector('#run-search').value.trim()) groupState.set(name, group.open);
    });
    const title = element('summary');
    title.append(element('span', 'group-name', name), element('span', 'group-count', `${runs.length} ${runs.length === 1 ? 'run' : 'runs'}`));
    const chevron = element('span', 'disclosure-chevron');
    chevron.setAttribute('aria-hidden', 'true');
    title.append(chevron); group.append(title);
    const table = element('table', 'run-table');
    table.append(element('caption', 'visually-hidden', 'Experiments in ' + name));
    const thead = element('thead');
    const header = element('tr');
    for (const [text, className] of [['Select', 'column-select'], ['Execution', 'column-execution'], ['Status', 'column-status'], ['Trials', 'column-trials'], ['Actions', 'column-actions']]) {
      const th = element('th', className, text);
      th.scope = 'col';
      header.append(th);
    }
    if (name === focusedGroup) title.focus({preventScroll: true});
    thead.append(header); table.append(thead);
    const tbody = element('tbody');
    table.append(tbody); group.append(table); body.append(group);
    for (const run of runs) {
      const tr = element('tr', selected.has(run.id) ? 'is-selected' : '');
      tr.dataset.run = run.id;
      const select = element('input');
      select.type = 'checkbox'; select.checked = selected.has(run.id);
      select.dataset.action = 'select';
      select.setAttribute('aria-label', 'Select ' + run.name + ' ' + run.id);
      select.onchange = () => {
        if (select.checked) selected.add(run.id); else selected.delete(run.id);
        tr.classList.toggle('is-selected', select.checked);
        updateSelectionCount(filtered.length, groups.size);
      };
      const selectCell = element('td', 'select-cell'); selectCell.append(select); tr.append(selectCell);
      const execution = element('td', 'execution-cell');
      const runLabel = element('span', 'run-id', run.id);
      runLabel.id = 'run-label-' + rowNumber++;
      runLabel.title = run.id;
      execution.append(runLabel, element('span', 'run-meta', `${(run.config?.n ?? '—').toLocaleString()} items · ${run.config?.ordering ?? '—'}`));
      tr.append(execution);
      const statusCell = element('td', 'status-cell');
      const knownStatus = ['completed', 'running', 'queued', 'failed', 'cancelled', 'interrupted'].includes(run.status) ? run.status : 'unknown';
      statusCell.append(element('span', 'status-badge status-' + knownStatus, run.status));
      tr.append(statusCell);
      const trialsCell = element('td', 'trials-cell');
      trialsCell.append(element('span', 'trial-count', `${run.completed_trials ?? 0}/${run.total_trials ?? '—'}`));
      if (run.total_trials > 0) {
        const progress = element('progress', 'run-progress');
        progress.max = run.total_trials; progress.value = run.completed_trials ?? 0;
        progress.setAttribute('aria-label', 'Completed trials for ' + run.name);
        trialsCell.append(progress);
      }
      tr.append(trialsCell);
      const actionsCell = element('td', 'actions-cell');
      const actions = runActions(run, runLabel, openMenus.has(run.id));
      actionsCell.append(actions); tr.append(actionsCell); tbody.append(tr);
      if (run.id === focusedRun && focusedAction) {
        [...tr.querySelectorAll('[data-action]')].find(node => node.dataset.action === focusedAction)?.focus({preventScroll: true});
      }
    }
  }
  if (!filtered.length) emptyState(body, Boolean(query.trim()));
  body.scrollTop = scrollTop;
}

async function refresh() {
  if (refreshing) return;
  refreshing = true;
  try {
    cachedRuns = await api('/api/runs');
    const ids = new Set(cachedRuns.map(r => r.id));
    for (const id of selected) if (!ids.has(id)) selected.delete(id);
    for (const [id, value] of [['stat-experiments', cachedRuns.length], ['stat-groups', new Set(cachedRuns.map(r => r.name)).size], ['stat-running', cachedRuns.filter(r => ['queued', 'running'].includes(r.status)).length]]) {
      const counter = document.getElementById(id);
      if (counter) counter.textContent = value;
    }
    const records = JSON.stringify(cachedRuns);
    if (records !== lastRecords) { renderRuns(); lastRecords = records; }
  } finally { refreshing = false; }
}
document.querySelector('#run-search')?.addEventListener('input', renderRuns);
const clearSelection = document.querySelector('#clear-selection');
if (clearSelection) clearSelection.onclick = () => { selected.clear(); renderRuns(); };
document.addEventListener('click', event => {
  for (const menu of document.querySelectorAll('.row-menu[open]')) if (!menu.contains(event.target)) menu.open = false;
});
document.querySelector('#runs').addEventListener('keydown', event => {
  if (event.key === 'Escape') {
    const menu = event.target.closest('.row-menu');
    if (menu) { menu.open = false; menu.querySelector('summary').focus(); }
  }
});

const studyPlots = document.querySelector('#research-plots');
if (studyPlots) studyPlots.onclick = async () => {
  if (!selected.size) { feedback(historyMessage, 'Select related experiments for an ordering or ThrowBin parameter study.', true); return; }
  await openViewer([...selected], 'study');
};

const experimentForm = document.querySelector('#experiment');
function customChoice(key, kind) {
  return availableBuilders[kind].find(choice => choice.id + '@' + choice.revision === key);
}
function customParameterValues(choice, kind) {
  const parameters = {};
  const root = document.querySelector('#custom-' + (kind === 'algorithms' ? 'algorithm' : 'generator') + '-parameters');
  for (const input of root?.querySelectorAll('[data-custom-id]') || []) {
    if (input.dataset.customId !== choice.id + '@' + choice.revision) continue;
    const definition = choice.parameters[input.dataset.parameter];
    parameters[input.dataset.parameter] = definition.type === 'boolean' ? input.value === 'true'
      : ['number', 'integer'].includes(definition.type || 'number') ? Number(input.value)
      : definition.type === 'list' ? JSON.parse(input.value) : input.value;
  }
  return parameters;
}
function renderCustomParameters(kind) {
  const root = document.querySelector('#custom-' + (kind === 'algorithms' ? 'algorithm' : 'generator') + '-parameters');
  if (!root) return;
  const chosen = kind === 'algorithms' ? [...experimentForm.querySelectorAll('input[name=algorithm]:checked')].map(input => customChoice(input.value, kind)).filter(Boolean)
    : [customChoice(experimentForm.elements.generator.value, kind)].filter(Boolean);
  const previous = new Map([...root.querySelectorAll('input,select')].map(input => [input.dataset.customId + ':' + input.dataset.parameter, input.value]));
  root.replaceChildren();
  for (const choice of chosen) {
    const group = element('fieldset', 'builder-selection-params');
    group.append(element('legend', '', choice.name + ' · revision ' + choice.revision));
    const link = element('a', 'field-help', 'Open in Builder →');
    link.href = '/builder?id=' + encodeURIComponent(choice.id) + '&revision=' + encodeURIComponent(choice.revision);
    group.append(link);
    const fields = element('div', 'grid');
    for (const [name, definition] of Object.entries(choice.parameters || {})) {
      const label = element('label', '', name);
      const control = element(definition.type === 'boolean' ? 'select' : 'input');
      control.dataset.customId = choice.id + '@' + choice.revision; control.dataset.parameter = name;
      if (definition.type === 'boolean') control.append(new Option('No', 'false'), new Option('Yes', 'true'));
      else if (['number', 'integer'].includes(definition.type || 'number')) {
        control.type = 'number'; control.step = definition.type === 'integer' ? '1' : 'any';
        if (definition.min != null) control.min = definition.min;
        if (definition.max != null) control.max = definition.max;
      }
      control.value = previous.get(control.dataset.customId + ':' + name) ?? (definition.type === 'list' ? JSON.stringify(definition.default ?? []) : definition.default ?? '');
      label.append(control); fields.append(label);
    }
    group.append(fields); root.append(group);
  }
}
async function loadAvailableBuilders() {
  if (!experimentForm) return;
  availableBuilders = await api('/api/builder/available');
  const algorithms = document.querySelector('.algorithm-options');
  for (const choice of availableBuilders.algorithms || []) {
    const label = element('label', 'check'), input = element('input'), description = element('span', '', choice.name);
    input.type = 'checkbox'; input.name = 'algorithm'; input.value = choice.id + '@' + choice.revision;
    description.append(element('small', 'custom-option-meta', `revision ${choice.revision} · ${choice.access} · ${choice.domain}`));
    input.onchange = () => renderCustomParameters('algorithms'); label.append(input, description); algorithms.append(label);
  }
  const select = experimentForm.elements.generator;
  for (const choice of availableBuilders.generators || []) select.append(new Option(`${choice.name} · revision ${choice.revision} · ${choice.domain}`, choice.id + '@' + choice.revision));
  select.addEventListener('change', () => renderCustomParameters('generators'));
  renderCustomParameters('algorithms'); renderCustomParameters('generators');
}
if (experimentForm) experimentForm.onsubmit = async event => {
  event.preventDefault();
  const submit = event.target.querySelector('[type=submit]');
  if (submit.disabled) return;
  busy(submit, true);
  try {
    const data = new FormData(event.target);
    const cfg = {name: data.get('name'), ordering: data.get('ordering'),
      dataset_mode: data.get('dataset_mode'), swap_mode: data.get('swap_mode')};
    for (const key of ['n', 'trials', 'seed', 'workers', 'swaps']) cfg[key] = Number(data.get(key));
    cfg.domain = data.get('domain');
    cfg.threshold = Number(data.get('threshold'));
    cfg.trace_limit = data.get('capture_trace') ? Number(data.get('trace_limit')) : 0;
    cfg.trace_bytes = Number(data.get('trace_bytes'));
    cfg.trace_trials = data.get('capture_trace') && data.get('trace_trials').trim() ? data.get('trace_trials').split(/[\s,]+/).filter(Boolean).map(Number) : null;
    const generator = data.get('generator');
    const customGenerator = customChoice(generator, 'generators');
    cfg.generator = customGenerator ? {id: customGenerator.id, revision: customGenerator.revision, params: customParameterValues(customGenerator, 'generators'), backend: 'python'}
      : {id: generator, bins: Number(data.get('bins')), ...(generator === 'big_items' ? {min: cfg.threshold * 0.51, max: cfg.threshold * 0.99} : cfg.domain === 'integer' ? {min: 1, max: cfg.threshold} : {})};
    cfg.algorithms = data.getAll('algorithm').map(id => {
      const custom = customChoice(id, 'algorithms');
      if (custom) return {id: custom.id, revision: custom.revision, params: customParameterValues(custom, 'algorithms'), backend: 'python'};
      let params = {};
      if (id === 'dual_harmonic') params = {k: Number(data.get('k'))};
      else if (['throwbin_retire', 'throwbin_replace'].includes(id)) params = {bin_ratio: Number(data.get('bin_ratio'))};
      else if (id === 'adaptive_covered') params = {multiplier: Number(data.get('multiplier')), initial_bins: Number(data.get('initial_bins'))};
      else if (id.startsWith('advice_reserved')) params = {m: Number(data.get('m')), x_m: Number(data.get('x_m'))};
      return {id, params};
    });
    if (!cfg.algorithms.length) throw Error('Choose at least one algorithm to run.');
    const result = await post('/api/runs', cfg);
    feedback(message, 'Started ' + cfg.name + ' · ' + result.id);
    await refresh();
  } catch (error) { feedback(message, error.message, true); }
  finally { busy(submit, false); }
};

const compare = document.querySelector('#compare');
if (compare) compare.onclick = async event => {
  const control = event.currentTarget;
  if (control.disabled) return;
  busy(control, true);
  try {
    if (selected.size < 2) throw Error('Select at least two experiments to compare.');
    void openViewer([...selected], 'study', 'summary');
  } catch (error) { feedback(historyMessage, error.message, true); }
  finally { busy(control, false); }
};
async function loadSavedTraces() {
  if (!viewer.open || !view.ids.length) return;
  const request = ++savedTraceRequest;
  const run = document.querySelector('#trace-run').value || view.ids[0];
  const target = document.querySelector('#saved-trace-view');
  savedTraceController?.destroy(); target.replaceChildren();
  feedback(document.querySelector('#saved-trace-status'), 'Loading recorded traces…');
  try {
    const data = await api(endpoint('traces', run));
    if (request !== savedTraceRequest || !viewer.open) return;
    savedTraceRows = data.traces || [];
    const algorithms = document.querySelector('#trace-algorithm'); algorithms.replaceChildren();
    const groups = new Map(savedTraceRows.map(row => [String(row.algorithm), row]));
    for (const [index, row] of groups) algorithms.append(new Option(`${row.label}${row.revision ? ' · revision ' + row.revision : ''}`, index));
    document.querySelector('#trace-trial').replaceChildren();
    if (!savedTraceRows.length) { feedback(document.querySelector('#saved-trace-status'), data.message || 'No trace was captured. Historical execution paths and bin state cannot be reconstructed.'); return; }
    updateTraceTrials(); await loadSavedTraceDetail();
  } catch (error) { if (request === savedTraceRequest) feedback(document.querySelector('#saved-trace-status'), error.message, true); }
}
function updateTraceTrials() {
  const algorithm = document.querySelector('#trace-algorithm').value;
  const trials = document.querySelector('#trace-trial'); trials.replaceChildren();
  for (const row of savedTraceRows.filter(row => String(row.algorithm) === algorithm)) trials.append(new Option(`Trial ${row.trial}${row.truncated ? ' · truncated' : ''}`, row.trial));
}
async function loadSavedTraceDetail() {
  const request = ++savedTraceRequest, run = document.querySelector('#trace-run').value;
  const algorithm = document.querySelector('#trace-algorithm').value, trial = document.querySelector('#trace-trial').value;
  savedTraceController?.destroy(); document.querySelector('#saved-trace-view').replaceChildren();
  if (algorithm === '' || trial === '') return;
  feedback(document.querySelector('#saved-trace-status'), 'Loading frozen execution evidence…');
  try {
    const data = await api(endpoint('trace', run) + '?algorithm=' + encodeURIComponent(algorithm) + '&trial=' + encodeURIComponent(trial));
    if (request !== savedTraceRequest || !viewer.open) return;
    savedTraceController = window.BinCoveringTrace.mount(document.querySelector('#saved-trace-view'), data, {threshold: data.metadata?.threshold});
    feedback(document.querySelector('#saved-trace-status'), data.metadata?.legacy ? 'Historical item/count trace. Node paths and bin snapshots were not recorded.' : 'Recorded trace against the exact frozen graph and revision.' + (data.metadata?.kind === 'generator' ? ' Generation events precede input ordering.' : ''));
  } catch (error) { if (request === savedTraceRequest) feedback(document.querySelector('#saved-trace-status'), error.message, true); }
}
document.querySelector('#trace-run').onchange = () => void loadSavedTraces();
document.querySelector('#trace-algorithm').onchange = () => { updateTraceTrials(); void loadSavedTraceDetail(); };
document.querySelector('#trace-trial').onchange = () => void loadSavedTraceDetail();
document.querySelector('#logout').onclick = async event => {
  event.preventDefault();
  try {
    await post('/api/logout');
    for (let i = localStorage.length - 1; i >= 0; i--) { const key = localStorage.key(i); if (key?.startsWith(`bincovering:builder:${dashboardSession.user.id}:`)) localStorage.removeItem(key); }
    location.href = '/login';
  } catch (error) { feedback(historyMessage, error.message, true); }
};
if (experimentForm) experimentForm.elements.domain.onchange = () => {
  const integer = experimentForm.elements.domain.value === 'integer';
  experimentForm.elements.threshold.value = integer ? '100' : '1';
  experimentForm.elements.threshold.step = integer ? '1' : 'any';
};
loadAvailableBuilders().catch(error => feedback(message, error.message, true));
refresh().catch(error => feedback(historyMessage, error.message, true));
setInterval(() => refresh().catch(error => feedback(historyMessage, error.message, true)), 2500);
