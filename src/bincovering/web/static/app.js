const selected = new Set();
const message = document.querySelector('#message');
let refreshing = false;
let cachedRuns = [];
const groupState = new Map();
const historyMessage = document.querySelector('#history-message');

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

function button(label, action) {
  const element = document.createElement('button');
  element.textContent = label;
  element.onclick = async () => {
    element.disabled = true;
    try { await action(); } catch (error) { historyMessage.textContent = error.message; }
    finally { element.disabled = false; }
  };
  return element;
}

function show(data) {
  document.querySelector('#results').hidden = false;
  document.querySelector('#details').textContent = JSON.stringify(data, null, 2);
  const area = document.querySelector('#summary');
  area.replaceChildren();
  const groups = data.runs || [{path: '', summary: data.summary || []}];
  for (const group of groups) {
    if (group.path) {
      const title = document.createElement('p');
      title.textContent = group.path;
      area.append(title);
    }
    for (const row of group.summary) {
      const entry = document.createElement('p');
      entry.textContent = `${row.algorithm} (${row.backend}): ${row.mean_covered ?? '—'} mean covered bins; ${row.successful_trials} successful, ${row.failed_trials} failed trials`;
      area.append(entry);
    }
  }
  document.querySelector('#comparison-note').textContent = 'same_trial_inputs' in data
    ? (data.same_trial_inputs ? 'These runs use matching trial inputs.' : 'These runs use different trial inputs; this is not a paired comparison.') : '';
  document.querySelector('#figure').hidden = true;
  document.querySelector('#results').scrollIntoView({behavior: 'smooth', block: 'start'});
}

// Match substrings, abbreviated subsequences, and one-edit typos in words.
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
  body.replaceChildren();
  document.querySelector('#history-count').textContent = `${filtered.length} of ${cachedRuns.length} experiments · ${groups.size} groups · ${selected.size} selected`;
  for (const [name, runs] of groups) {
    const group = document.createElement('details');
    group.className = 'run-group';
    group.open = query.trim() ? true : (groupState.get(name) ?? groups.size === 1);
    group.ontoggle = () => { if (!document.querySelector('#run-search').value.trim()) groupState.set(name, group.open); };
    const title = document.createElement('summary');
    title.textContent = `${name} (${runs.length})`;
    group.append(title);
    const table = document.createElement('table');
    const tbody = document.createElement('tbody');
    table.append(tbody); group.append(table); body.append(group);
    for (const run of runs) {
      const tr = document.createElement('tr');
      const select = document.createElement('input');
      select.type = 'checkbox'; select.checked = selected.has(run.id);
      select.setAttribute('aria-label', 'Select ' + run.name + ' ' + run.id);
      select.onchange = () => {
        if (select.checked) selected.add(run.id); else selected.delete(run.id);
        document.querySelector('#history-count').textContent = `${filtered.length} of ${cachedRuns.length} experiments · ${groups.size} groups · ${selected.size} selected`;
      };
      const cell = document.createElement('td'); cell.append(select); tr.append(cell);
      for (const text of [run.id, run.status, `${run.completed_trials}/${run.total_trials}`]) {
        const td = document.createElement('td'); td.textContent = text; tr.append(td);
      }
      const actions = document.createElement('td');
      actions.append(button('Inspect', async () => show(await api(endpoint('inspect', run.id)))));
      if (['running', 'queued'].includes(run.status)) {
        actions.append(button('Cancel', async () => {
          await post(endpoint('cancel', run.id)); historyMessage.textContent = 'Cancellation requested';
        }));
      } else {
        actions.append(button('Plot', async () => {
          const data = await post(endpoint('plot', run.id));
          show(await api(endpoint('inspect', run.id)));
          const image = document.querySelector('#figure');
          image.src = data.url + '?t=' + Date.now(); image.hidden = false;
        }));
        actions.append(button(run.pinned ? 'Unpin' : 'Pin', async () => {
          await post(endpoint('pin', run.id), {pinned: !run.pinned}); await refresh();
        }));
        const download = document.createElement('a');
        download.href = endpoint('export', run.id); download.textContent = 'Export';
        actions.append(download);
        if (!run.pinned) actions.append(button('Remove', async () => {
          const removed = await post(endpoint('remove', run.id));
          selected.delete(run.id);
          historyMessage.replaceChildren(document.createTextNode('Experiment moved to trash. '), button('Undo', async () => {
            await post('/api/restore/' + removed.token);
            historyMessage.textContent = 'Experiment restored';
            await refresh();
          }));
          await refresh();
        }));
      }
      tr.append(actions); tbody.append(tr);
    }
  }
  if (!filtered.length) body.textContent = 'No matching experiments.';
  body.scrollTop = scrollTop;
}

async function refresh() {
  if (refreshing) return;
  refreshing = true;
  try {
    cachedRuns = await api('/api/runs');
    const ids = new Set(cachedRuns.map(r => r.id));
    for (const id of selected) if (!ids.has(id)) selected.delete(id);
    renderRuns();
  } finally { refreshing = false; }
}
document.querySelector('#run-search').addEventListener('input', renderRuns);
document.querySelector('#research-plots').onclick = async event => {
  const control = event.currentTarget;
  control.disabled = true;
  try {
    const data = await post('/api/comparison-plot', {ids: [...selected]});
    show({summary: []});
    document.querySelector('#comparison-note').textContent = 'Paired improvement over DNF and ordering sensitivity. Only matched input comparisons are used.';
    const image = document.querySelector('#figure');
    image.src = data.url + '?t=' + Date.now(); image.hidden = false;
  } catch (error) { historyMessage.textContent = error.message; }
  finally { control.disabled = false; }
};

document.querySelector('#experiment').onsubmit = async event => {
  event.preventDefault();
  const submit = event.target.querySelector('[type=submit]');
  submit.disabled = true;
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
    const result = await post('/api/runs', cfg);
    message.textContent = 'Started ' + result.id;
    await refresh();
  } catch (error) { message.textContent = error.message; }
  finally { submit.disabled = false; }
};

document.querySelector('#compare').onclick = async () => {
  try {
    show(await api('/api/compare?' + [...selected].map(id => 'id=' + encodeURIComponent(id)).join('&')));
  } catch (error) { message.textContent = error.message; }
};
refresh().catch(error => message.textContent = error.message);
setInterval(() => refresh().catch(error => message.textContent = error.message), 2500);
