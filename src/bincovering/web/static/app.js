const selected = new Set();
const groupState = new Map();
const message = document.querySelector('#message');
const historyMessage = document.querySelector('#history-message');
let refreshing = false;
let cachedRuns = [];
let lastRecords = '';

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function feedback(target, text, error = false) {
  target.textContent = text;
  target.classList.toggle('feedback-error', error);
}

async function api(url, options) {
  const response = await fetch(url, options);
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
    busy(control, true);
    try { await action(); }
    catch (error) { feedback(historyMessage, error.message, true); }
    finally { busy(control, false); }
  };
  return control;
}

function setFigure(url) {
  const image = document.querySelector('#figure');
  const link = document.querySelector('#figure-link');
  image.src = url + '?t=' + Date.now();
  link.href = image.src;
  image.hidden = false;
  link.hidden = false;
}

function show(data) {
  const results = document.querySelector('#results');
  results.hidden = false;
  document.querySelector('#results-placeholder').hidden = true;
  document.querySelector('#result-context').textContent = data.manifest?.name || (data.runs ? `${data.runs.length} selected runs` : 'Selected experiments');
  document.querySelector('#details').textContent = JSON.stringify(data, null, 2);
  const area = document.querySelector('#summary');
  area.replaceChildren();
  const groups = data.runs || [{path: '', summary: data.summary || []}];
  for (const group of groups) {
    if (group.path) area.append(element('p', 'result-run-title', group.path));
    for (const row of group.summary) {
      const card = element('article', 'result-card');
      card.append(element('h3', '', `${row.algorithm.replaceAll('_', ' ')} · ${row.backend}`));
      const value = row.mean_covered == null ? '—' : new Intl.NumberFormat(undefined, {maximumFractionDigits: 2}).format(row.mean_covered);
      card.append(element('strong', 'result-value', value));
      card.append(element('p', '', 'Mean covered bins'));
      card.append(element('p', '', `${row.successful_trials} successful · ${row.failed_trials} failed trials`));
      area.append(card);
    }
  }
  document.querySelector('#comparison-note').textContent = 'same_trial_inputs' in data
    ? (data.same_trial_inputs ? 'These runs use matching trial inputs.' : 'These runs use different trial inputs; this is not a paired comparison.') : '';
  document.querySelector('#figure').hidden = true;
  document.querySelector('#figure-link').hidden = true;
  results.focus({preventScroll: true});
  results.scrollIntoView({behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'start'});
}

// Substrings, abbreviated subsequences, and one-edit typos in words.
function fuzzyMatch(query, text) {
  text = text.toLowerCase();
  return query.toLowerCase().trim().split(/\s+/).every(term => {
    if (!term || text.includes(term)) return true;
    const words = text.split(/[^a-z0-9]+/);
    return words.some(word => {
      let at = 0;
      for (const char of word) if (char === term[at]) at++;
      if (at === term.length) return true;
      if (term.length < 3 || Math.abs(word.length - term.length) > 1) return false;
      let previous = Array.from({length: term.length + 1}, (_, i) => i);
      for (let i = 0; i < word.length; i++) {
        const current = [i + 1];
        for (let j = 0; j < term.length; j++) current.push(Math.min(current[j] + 1, previous[j + 1] + 1, previous[j] + (word[i] === term[j] ? 0 : 1)));
        previous = current;
      }
      return previous[term.length] <= 1;
    });
  });
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

function renderRuns() {
  const query = document.querySelector('#run-search').value;
  const filtered = cachedRuns.filter(run => fuzzyMatch(query, [run.name, run.id, run.status, ...(run.config?.algorithms || []).map(a => a.id)].join(' ')));
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
      const actions = element('div', 'row-actions');
      const inspect = button('Inspect', async () => show(await api(endpoint('inspect', run.id))));
      actions.append(inspect);
      if (['running', 'queued'].includes(run.status)) {
        actions.append(button('Cancel', async () => {
          await post(endpoint('cancel', run.id)); feedback(historyMessage, 'Cancellation requested');
        }));
      } else {
        actions.append(button('Plot', async () => {
          const data = await post(endpoint('plot', run.id));
          show(await api(endpoint('inspect', run.id)));
          setFigure(data.url);
        }));
        const menu = element('details', 'row-menu');
        menu.open = openMenus.has(run.id);
        const menuTitle = element('summary', '', 'More');
        menuTitle.dataset.action = 'more';
        menuTitle.append(element('span', 'visually-hidden', ' actions for ' + run.id));
        const extra = element('div', 'action-list');
        extra.append(button(run.pinned ? 'Unpin' : 'Pin', async () => {
          await post(endpoint('pin', run.id), {pinned: !run.pinned}); await refresh();
        }));
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
    document.querySelector('#stat-experiments').textContent = cachedRuns.length;
    document.querySelector('#stat-groups').textContent = new Set(cachedRuns.map(r => r.name)).size;
    document.querySelector('#stat-running').textContent = cachedRuns.filter(r => ['queued', 'running'].includes(r.status)).length;
    const records = JSON.stringify(cachedRuns);
    if (records !== lastRecords) { renderRuns(); lastRecords = records; }
  } finally { refreshing = false; }
}
document.querySelector('#run-search').addEventListener('input', renderRuns);
document.querySelector('#clear-selection').onclick = () => { selected.clear(); renderRuns(); };
document.querySelector('#runs').addEventListener('keydown', event => {
  if (event.key === 'Escape') {
    const menu = event.target.closest('.row-menu');
    if (menu) { menu.open = false; menu.querySelector('summary').focus(); }
  }
});

document.querySelector('#research-plots').onclick = async event => {
  const control = event.currentTarget;
  if (control.disabled) return;
  busy(control, true);
  try {
    if (!selected.size) throw Error('Select at least one experiment for DNF / ordering plots.');
    const data = await post('/api/comparison-plot', {ids: [...selected]});
    show({summary: []});
    document.querySelector('#comparison-note').textContent = 'Paired improvement over DNF and ordering sensitivity. Only matched input comparisons are used.';
    setFigure(data.url);
  } catch (error) { feedback(historyMessage, error.message, true); }
  finally { busy(control, false); }
};

document.querySelector('#experiment').onsubmit = async event => {
  event.preventDefault();
  const submit = event.target.querySelector('[type=submit]');
  if (submit.disabled) return;
  busy(submit, true);
  try {
    const data = new FormData(event.target);
    const cfg = {name: data.get('name'), ordering: data.get('ordering'),
      dataset_mode: data.get('dataset_mode'), swap_mode: data.get('swap_mode')};
    for (const key of ['n', 'trials', 'seed', 'workers', 'swaps']) cfg[key] = Number(data.get(key));
    const generator = data.get('generator');
    cfg.generator = {id: generator, bins: Number(data.get('bins')),
      ...(generator === 'big_items' ? {min: 0.51, max: 0.99} : {})};
    cfg.algorithms = data.getAll('algorithm').map(id => {
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

document.querySelector('#compare').onclick = async event => {
  const control = event.currentTarget;
  if (control.disabled) return;
  busy(control, true);
  try {
    if (selected.size < 2) throw Error('Select at least two experiments to compare.');
    show(await api('/api/compare?' + [...selected].map(id => 'id=' + encodeURIComponent(id)).join('&')));
  } catch (error) { feedback(historyMessage, error.message, true); }
  finally { busy(control, false); }
};
refresh().catch(error => feedback(historyMessage, error.message, true));
setInterval(() => refresh().catch(error => feedback(historyMessage, error.message, true)), 2500);
