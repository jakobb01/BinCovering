/* Production C workspace. Execution is exclusively delegated to the server. */
(() => {
  'use strict';
  const $ = selector => document.querySelector(selector), copy = value => JSON.parse(JSON.stringify(value));
  const node = (tag, cls, text) => {
    const n = document.createElement(tag);
    if (cls)
      n.className = cls;
    if (text !== undefined)
      n.textContent = text;
    return n;
  };
  const button = (text, action, variant = 'ghost') => {
    const b = node('button', 'button button-' + variant, text);
    b.type = 'button';
    b.onclick = event => runAction(() => action(event));
    return b;
  };
  const uid = prefix => prefix + '_' + crypto.randomUUID().replaceAll('-', '').slice(0, 12);
  let session, templates = [], library = [], program = null, itemId = null, owned = true, phase = 'next', selected = null, selectedEdge = null, selection = new Set(), pending = null;
  let undo = [], redo = [], zoom = 1, dirty = false, parents = [], currentJob = null, preview = null, previewSignature = null, previewGraph = null, submittingPreview = false, traceController = null, pollSerial = 0, saving = false, typingSnapshot = null;
  let currentTraceEvent = null, visitedNodes = new Set();
  let activeMode = 'algorithm', modeDrafts = {}, pan = {x: 0, y: 0}, showDataPorts = false;
  let canvasGeometry = null, suppressClickUntil = 0;
  const symbols = {entry: '▶', assign: '=', condition: '◇', loop: '↻', create_bin: '□', select_bin: '◎', place: '+', cover: '✓', discard: '−', custom: '{}', random: '~', emit: '→', return: '↗', component: '⊞'};
  const nodeInputs = {
    place: {
      item: 'number',
      bin: 'bin',
      index: 'integer'
    },
    cover: { bin: 'bin' },
    select_bin: { bin: 'bin' },
    discard: { index: 'integer' },
    emit: { value: 'number' },
    condition: { value: 'boolean' },
    assign: { value: 'any' }
  };
  const nodeOutputs = {
    create_bin: {
      bin: 'bin',
      value: 'bin'
    },
    assign: { value: 'any' },
    random: { value: 'number' },
    condition: { value: 'boolean' },
    place: {
      load: 'number',
      bin: 'bin'
    },
    cover: { covered: 'integer' },
    emit: { value: 'number' }
  };
  const palette = [
    [
      'State and decisions',
      'assign',
      'Update state',
      {
        variable: 'count',
        expression: 'count + 1'
      }
    ],
    [
      'State and decisions',
      'condition',
      'Condition',
      { expression: 'bin_load(active_bin) >= threshold' }
    ],
    [
      'State and decisions',
      'loop',
      'Bounded loop',
      {
        variable: 'i',
        values: 'range(len(sequence))'
      }
    ],
    [
      'Bin operations',
      'create_bin',
      'Create bin',
      { variable: 'new_bin' }
    ],
    [
      'Bin operations',
      'select_bin',
      'Select bin',
      { expression: 'active_bin' }
    ],
    [
      'Bin operations',
      'place',
      'Place item',
      {
        item: 'item',
        bin: 'active_bin',
        index: 'index'
      }
    ],
    [
      'Bin operations',
      'cover',
      'Close covered bin',
      { bin: 'active_bin' }
    ],
    [
      'Bin operations',
      'discard',
      'Discard item',
      { index: 'index' }
    ],
    [
      'Custom and generators',
      'custom',
      'Custom',
      {
        source: 'if bin_load(active_bin) >= threshold:\n    cover(active_bin)',
        notation: 'python'
      }
    ],
    [
      'Custom and generators',
      'random',
      'Seeded random choice',
      {
        variable: 'pick',
        min: '0',
        max: '1',
        integer: false
      }
    ],
    [
      'Custom and generators',
      'emit',
      'Emit item',
      { expression: 'uniform(0.1, 0.9)' }
    ],
    [
      'Custom and generators',
      'return',
      'Return',
      {}
    ]
  ];
  const signature = () => JSON.stringify(program);
  const draftKey = () => `bincovering:builder:${ session?.user?.id }:recovery`;
  let recoveryEnabled = true;
  const previewFields = ['preview-items', 'preview-count', 'preview-seed', 'preview-component-values', 'preview-component-context'];
  const capturePreviewSettings = () => Object.fromEntries(previewFields.map(id => [id, $('#' + id).value]));
  const restorePreviewSettings = values => {
    for (const [id, value] of Object.entries(values || {}))
      if (previewFields.includes(id)) $('#' + id).value = value;
  };
  function captureWorkspace() {
    return {
      ...snapshot(), dirty, name: $('#builder-name').value,
      parents: copy(parents), undo: copy(undo), redo: copy(redo),
      previewSettings: capturePreviewSettings(), zoom, pan: {...pan}, showDataPorts,
      starter: $('#builder-starter').value
    };
  }
  function restoreWorkspace(saved) {
    parents = saved.parents || [];
    load(saved.program, saved.itemId, saved.name || saved.program.name, saved.owned);
    phase = saved.phase;
    selected = saved.selected;
    selection = new Set(saved.selection || (selected ? [selected] : []));
    undo = saved.undo || [];
    redo = saved.redo || [];
    dirty = !!saved.dirty;
    zoom = saved.zoom || 1;
    pan = saved.pan || {x: 0, y: 0};
    showDataPorts = !!saved.showDataPorts;
    restorePreviewSettings(saved.previewSettings);
    if (saved.starter) $('#builder-starter').value = saved.starter;
    $('#draft-status').textContent = dirty ? 'Unsaved draft' : itemId ? 'Saved draft' : 'Starter draft';
    renderAll();
    recover();
  }
  function renderModes() {
    for (const mode of ['algorithm', 'generator']) {
      const tab = $('#builder-' + mode + '-tab');
      tab.setAttribute('aria-selected', String(activeMode === mode));
      tab.tabIndex = activeMode === mode ? 0 : -1;
    }
    $('#builder-workspace').setAttribute('aria-labelledby', 'builder-' + activeMode + '-tab');
    $('#builder-page-title-text').textContent = activeMode === 'generator' ? 'Build your generator' : 'Build your algorithm';
    $('#builder-page-intro').textContent = 'Connect components, add small custom logic, and test each step before running an experiment.';
    const chooser = $('#builder-starter'), previous = chooser.value;
    chooser.replaceChildren(new Option('Choose a starter…', ''));
    for (const t of templates.filter(t => t.graph.kind === activeMode || t.graph.kind === 'component'))
      chooser.append(new Option(t.name, t.id));
    chooser.value = [...chooser.options].some(o => o.value === previous) ? previous : '';
    $('#data-wiring').setAttribute('aria-pressed', String(showDataPorts));
  }
  function switchMode(mode) {
    if (mode === activeMode) return;
    modeDrafts[activeMode] = captureWorkspace();
    activeMode = mode;
    renderModes();
    if (modeDrafts[mode]) restoreWorkspace(modeDrafts[mode]);
    else {
      parents = [];
      const t = templates.find(t => t.graph.kind === mode);
      load(starterGraph(t), null, t.name);
      $('#builder-starter').value = t.id;
      fit();
    }
    recover();
  }
  // Starter layout is presentation only. Imported and saved graphs keep their positions.
  function starterGraph(template) {
    const g = copy(template.graph);
    const online = {next: [45, 30], place: [45, 180], check: [45, 370], close: [305, 575], done: [45, 775]};
    const offline = {process: [45, 30], items: [45, 170], place: [305, 310], check: [305, 470], close: [565, 600], item_done: [305, 765], finished: [45, 470]};
    function arrange(graphValue) {
      const counters = {};
      for (const n of graphValue.nodes) {
        const index = counters[n.phase] || 0;
        counters[n.phase] = index + 1;
        const position = graphValue.kind === 'algorithm' ? (graphValue.access === 'offline' ? offline : online)[n.id] : null;
        [n.x, n.y] = position || [45, 30 + index * 165];
      }
      for (const def of Object.values(graphValue.components || {})) arrange(def.graph);
    }
    arrange(g);
    return g;
  }
  async function api(url, options = {}) {
    const headers = {
      ...options.body ? { 'Content-Type': 'application/json' } : {},
      ...options.method && options.method !== 'GET' ? { 'X-CSRF-Token': session?.csrf_token } : {},
      ...options.headers
    };
    const response = await fetch(url, {
      ...options,
      headers
    });
    if (response.status === 401) {
      location.href = '/login?next=' + encodeURIComponent(location.pathname);
      throw Error('Please sign in again.');
    }
    const data = await response.json();
    if (!response.ok) {
      const error = Error(data.error || response.statusText);
      error.detail = data.detail;
      throw error;
    }
    return data;
  }
  const post = (url, body = {}) => api(url, {
    method: 'POST',
    body: JSON.stringify(body)
  });
  const libraryUrl = (id = itemId) => '/api/builder/library/' + encodeURIComponent(id);
  function feedback(text, error = false, target = $('#builder-feedback')) {
    target.textContent = text;
    target.classList.toggle('feedback-error', error);
  }
  async function runAction(action) {
    try {
      await action();
    } catch (error) {
      feedback(error.message, true);
      if (error.detail?.node_id) {
        preview = {
          ok: false,
          error: error.detail
        };
        selected = error.detail.node_id;
        selection = new Set([selected]);
        const located = currentNode();
        if (located)
          phase = located.phase;
        renderAll();
        feedback(error.message, true, $('#preview-status'));
      }
    }
  }
  function snapshot() {
    return {
      program: copy(program),
      phase,
      selected,
      selection: [...selection],
      itemId,
      owned
    };
  }
  function record() {
    if (!program)
      return;
    undo.push(snapshot());
    if (undo.length > 100)
      undo.shift();
    redo = [];
    typingSnapshot = null;
  }
  function recover() {
    if (!recoveryEnabled)
      return;
    try {
      localStorage.setItem(draftKey(), JSON.stringify({
        program,
        itemId,
        owned,
        phase,
        dirty,
        activeMode,
        modeDrafts: Object.fromEntries(Object.entries(modeDrafts).map(([mode, saved]) => [mode, {...saved, undo: [], redo: []}])),
        zoom, pan, showDataPorts, selected, selection: [...selection],
        parents: parents.map(({undo, redo, ...parent}) => ({...parent, undo: [], redo: []})),
        previewSettings: capturePreviewSettings(),
        time: Date.now()
      }));
    } catch {
      feedback('Browser draft recovery is unavailable. Save your draft to the library.');
    }
  }
  function changed(render = true) {
    dirty = true;
    currentTraceEvent = null;
    visitedNodes = new Set();
    $('#draft-status').textContent = 'Unsaved draft';
    $('#available').disabled = true;
    if (preview) {
      $('#preview-status').textContent = 'Preview is stale. Run this edited graph again before making it available.';
    }
    recover();
    if (render)
      renderAll();
    else
      renderCanvas();
  }
  function mutate(action, render = true) {
    record();
    action();
    changed(render);
  }
  function graph() {
    return program;
  }
  function phaseNodes() {
    return (graph()?.nodes || []).filter(n => n.phase === phase || !n.phase && graph().kind === 'component');
  }
  function currentNode() {
    return graph()?.nodes.find(n => n.id === selected);
  }
  function restoreHistory(stack, destination) {
    if (!stack.length)
      return;
    destination.push(snapshot());
    const s = stack.pop();
    program = s.program;
    phase = s.phase;
    selected = s.selected;
    selection = new Set(s.selection);
    itemId = s.itemId;
    owned = s.owned;
    changed();
    const restored = [...$('#canvas-world').querySelectorAll('.graph-node')].find(card => card.dataset.id === selected);
    (restored?.querySelector('.node-title') || $('#canvas-viewport')).focus({preventScroll: true});
  }
  function normalize(graphValue) {
    const g = copy(graphValue);
    g.nodes = g.nodes || [];
    g.edges = g.edges || [];
    g.components = g.components || {};
    g.parameters = g.parameters || {};
    g.state = g.state || {};
    const byPhase = {};
    for (const n of g.nodes) {
      const p = n.phase || Object.keys(g.entries || {})[0] || 'process';
      n.phase = p;
      n.config = n.config || {};
      const i = byPhase[p] || 0;
      byPhase[p] = i + 1;
      if (!Number.isFinite(n.x))
        n.x = 40 + i % 3 * 245;
      if (!Number.isFinite(n.y))
        n.y = 40 + Math.floor(i / 3) * 180;
    }
    return g;
  }
  function load(graphValue, id = null, name = null, canEdit = true) {
    ++pollSerial;
    if (currentJob)
      void post('/api/builder/jobs/' + encodeURIComponent(currentJob) + '/cancel').catch(() => {
      });
    $('#canvas-viewport').scrollLeft = 0;
    $('#canvas-viewport').scrollTop = 0;
    program = normalize(graphValue);
    if (program.kind !== 'component') activeMode = program.kind;
    else if (parents.length) activeMode = parents[0].program.kind === 'generator' ? 'generator' : 'algorithm';
    zoom = 1;
    pan = {x: 20, y: 20};
    showDataPorts = false;
    itemId = id;
    owned = canEdit;
    phase = program.entries?.next ? 'next' : program.entries?.process ? 'process' : Object.keys(program.entries || {})[0] || 'start';
    selected = phaseNodes().find(n => n.type !== 'entry')?.id || phaseNodes()[0]?.id;
    selection = new Set(selected ? [selected] : []);
    selectedEdge = null;
    pending = null;
    undo = [];
    redo = [];
    dirty = false;
    preview = null;
    previewSignature = null;
    currentJob = null;
    traceController?.destroy();
    $('#preview-trace').replaceChildren();
    $('#preview-status').textContent = 'Run a small preview to inspect actual execution.';
    $('#builder-name').value = name || program.name || 'Untitled builder';
    $('#draft-status').textContent = id ? 'Saved draft' : 'Starter draft';
    $('#available').disabled = true;
    $('#component-breadcrumb').hidden = !parents.length;
    if (program.kind === 'component') {
      $('#preview-component-values').value = JSON.stringify(Object.fromEntries(Object.entries(program.inputs || {}).map(([name, spec]) => [
        name,
        spec.default ?? (spec.type === 'boolean' ? false : spec.type === 'list' ? [] : spec.type === 'text' ? '' : (spec.type === 'integer' || spec.type === 'bin') ? 0 : 0.5)
      ])));
      $('#preview-component-context').value = '{}';
      $('#preview-items').value = '';
    }
    renderAll();
    if (program.kind === 'component' && $('#canvas-viewport').clientWidth < 600) fit();
    recover();
  }
  function renderAll() {
    if (!program)
      return;
    renderModes();
    renderPhases();
    renderPalette();
    renderCanvas();
    renderInspector();
    $('#undo').disabled = !undo.length || !owned;
    $('#redo').disabled = !redo.length || !owned;
    $('#save-draft').disabled = !owned;
    $('#run-preview').disabled = !owned || !!currentJob;
    $('#builder-name').disabled = !owned;
    $('#builder-params').value = JSON.stringify(program.parameters || {}, null, 2);
    for (const control of [
        '#builder-params',
        '#builder-state',
        '#builder-inputs',
        '#builder-outputs'
      ])
      $(control).disabled = !owned;
    $('#builder-state').value = JSON.stringify(program.state || {}, null, 2);
    $('#builder-inputs').value = JSON.stringify(program.inputs || {}, null, 2);
    $('#builder-outputs').value = JSON.stringify(program.outputs || {}, null, 2);
    $('#component-inputs-declaration').hidden = program.kind !== 'component';
    $('#component-outputs-declaration').hidden = program.kind !== 'component';
    $('#component-preview-inputs').hidden = program.kind !== 'component';
    $('#sequence-label').hidden = program.kind === 'generator';
    $('#component-fixture').hidden = program.kind !== 'component';
    $('#count-label').hidden = program.kind !== 'generator';
  }
  function switchPhase(next) {
    phase = next;
    selected = phaseNodes().find(n => n.type !== 'entry')?.id || phaseNodes()[0]?.id;
    selection = new Set(selected ? [selected] : []);
    selectedEdge = null;
    pending = null;
    renderPhases();
    renderCanvas();
    renderInspector();
    fit();
  }
  function renderPhases() {
    const tabs = $('#phase-tabs');
    tabs.replaceChildren();
    const labels = {
      start: 'Start',
      next: program.kind === 'generator' ? 'Generate next' : 'Next item',
      process: program.kind === 'component' ? 'Component' : 'Process sequence',
      stop: 'Stop'
    };
    const lifecycleOrder = ['start', 'process', 'next', 'stop'];
    for (const p of Object.keys(program.entries || {}).sort((a, b) => lifecycleOrder.indexOf(a) - lifecycleOrder.indexOf(b))) {
      const b = button(labels[p] || p, () => switchPhase(p));
      b.append(node('span', 'phase-caption', p === 'next' ? 'each item' : 'once'));
      b.className = '';
      b.setAttribute('role', 'tab');
      b.setAttribute('aria-selected', String(phase === p));
      b.tabIndex = phase === p ? 0 : -1;
      b.dataset.phase = p;
      b.onkeydown = event => {
        const choices = [...tabs.children], i = choices.indexOf(b);
        let idx;
        if (event.key === 'ArrowRight')
          idx = (i + 1) % choices.length;
        else if (event.key === 'ArrowLeft')
          idx = (i + choices.length - 1) % choices.length;
        else if (event.key === 'Home')
          idx = 0;
        else if (event.key === 'End')
          idx = choices.length - 1;
        else
          return;
        event.preventDefault();
        switchPhase(choices[idx].dataset.phase);
        [...tabs.children][idx].focus();
      };
      tabs.append(b);
    }
    $('#phase-help').textContent = phase === 'start' ? 'Start runs once. Initialize your state and bins.' : phase === 'stop' ? 'Stop runs once. Unfinished bins remain measured in the ledger.' : phase === 'process' ? program.kind === 'component' ? `This reusable graph runs inside its caller with explicit inputs and local state. Input access: ${program.access || 'online'}.` : 'This graph can inspect the entire ordered sequence. Iteration is explicit and bounded.' : program.kind === 'generator' ? 'Generate next runs once for each requested item. Emit the item through the managed helper.' : 'Next item sees only the incoming item and past state. The system calls it once per item.';
  }
  function renderPalette() {
    const target = $('#component-palette');
    target.replaceChildren();
    if (!program) return;
    const descriptions = {assign: 'Remember a value', place: 'Add the current item to a bin', cover: 'Finish a covered bin', condition: 'Choose Yes or No', loop: 'Repeat a bounded set of steps', custom: 'A few simple statements', return: 'Finish this step', random: 'Choose a seeded value', emit: 'Output the next item', create_bin: 'Open a new bin', select_bin: 'Choose a working bin', discard: 'Skip an item'};
    const groups = activeMode === 'generator' ? [
      ['State', ['assign']], ['Items', ['random', 'emit']], ['Logic', ['condition', 'loop']], ['Custom', ['custom']], ['Results', ['return']]
    ] : [
      ['State', ['assign']], ['Bins', ['place', 'cover']], ['Logic', ['condition', 'loop']], ['Custom', ['custom']], ['Results', ['return']]
    ];
    const labels = {assign: 'Set state', cover: 'Close bin', custom: 'Custom logic', return: 'End step', random: 'Random value', loop: 'Repeat'};
    function addRow(parent, type, label, config, description, action, drag) {
      const row = node('div', 'palette-component');
      row.draggable = owned;
      row.dataset.type = type;
      const text = node('span', 'palette-copy');
      text.append(node('span', 'palette-name', label), node('span', 'palette-description', description));
      const add = button('Add', action || (() => addNode(type, label, config)));
      add.disabled = !owned;
      row.append(node('span', 'palette-symbol', symbols[type]), text, add);
      row.ondragstart = e => {
        if (drag) drag(e);
        else e.dataTransfer.setData('application/bincovering-node', JSON.stringify({type, label, config}));
        e.dataTransfer.effectAllowed = 'copy';
      };
      parent.append(row);
    }
    function basicRow(parent, type) {
      const [, , oldLabel, defaults] = palette.find(spec => spec[1] === type);
      const config = copy(defaults);
      if (activeMode === 'generator') {
        if (type === 'custom') config.source = 'emit(uniform(0.1, 0.9))';
        if (type === 'condition') config.expression = 'index % 2 == 0';
        if (type === 'loop') config.values = 'range(2)';
      }
      if (program.kind === 'component' && type === 'custom') config.source = 'value = incoming';
      addRow(parent, type, labels[type] || oldLabel, config, descriptions[type]);
    }
    for (const [group, types] of groups) {
      target.append(node('h3', 'palette-group', group));
      types.forEach(type => basicRow(target, type));
    }
    if (activeMode === 'algorithm') {
      const more = node('details', 'palette-more');
      more.append(node('summary', '', 'More operations'));
      ['create_bin', 'select_bin', 'discard', 'random'].forEach(type => basicRow(more, type));
      target.append(more);
    }
    const components = library.filter(item => item.kind === 'component' && item.revision && !item.archived);
    const inline = Object.entries(program.components || {}).filter(([id]) => !id.startsWith('custom:'));
    if (components.length || inline.length) target.append(node('h3', 'palette-group', 'My components'));
    for (const [id, def] of inline)
      addRow(target, 'component', def.graph.name || 'Reusable logic', {}, 'Open and reuse this graph', () => addInline(id), e => e.dataTransfer.setData('application/bincovering-inline', id));
    for (const component of components) {
      addRow(target, 'component', component.name, {}, 'Saved · revision ' + component.revision, () => addReusable(component), e => e.dataTransfer.setData('application/bincovering-component', component.id));
    }
  }
  function addInline(id, position) {
    const component = program.components[id].graph;
    addNode('component', component.name || 'Reusable logic', {
      component_id: id,
      inputs: Object.fromEntries(Object.keys(component.inputs || {}).map(name => [name, name])),
      outputs: Object.fromEntries(Object.keys(component.outputs || {}).map(name => [name, name])),
      params: {}
    }, position);
  }
  function addNode(type, label, config, position) {
    if (!owned)
      throw Error('Clone this shared revision to edit it.');
    if (type === 'loop' && program.access === 'online' && program.kind !== 'generator')
      config = {
        variable: 'i',
        values: 'range(2)'
      };
    const prev = currentNode(), nodes = phaseNodes(), p = position || {
        x: prev ? prev.x + 280 : 45,
        y: prev?.y ?? 30 + nodes.length * 165
      };
    mutate(() => {
      const n = {
        id: uid(type),
        type,
        label,
        phase,
        x: p.x,
        y: p.y,
        config: copy(config)
      };
      program.nodes.push(n);
      selected = n.id;
      selection = new Set([n.id]);
      selectedEdge = null;
    });
    ensureVisible(selected);
    feedback(`Added ${ label }. Connect its execution sockets to include it in the flow.`);
  }
  async function addReusable(item, position) {
    const record = await api(libraryUrl(item.id) + '?revision=' + encodeURIComponent(item.revision));
    const component = record.frozen?.graph || record.draft;
    mutate(() => {
      program.components[item.id] = {
        revision: Number(item.revision),
        graph: component
      };
    });
    const inputs = {}, outputs = {};
    for (const name of Object.keys(component.inputs || {}))
      inputs[name] = name;
    for (const name of Object.keys(component.outputs || {}))
      outputs[name] = name;
    addNode('component', item.name, {
      component_id: item.id,
      inputs,
      outputs,
      params: {}
    }, position);
  }
  function outputsFor(n) {
    if (n.type === 'return')
      return [];
    if (n.type === 'condition')
      return [
        'yes',
        'no'
      ];
    if (n.type === 'loop')
      return [
        'body',
        'next'
      ];
    return ['next'];
  }
  function dataPorts(n, direction) {
    const component = program.components?.[n.config.component_id]?.graph;
    if (n.type === 'component')
      return Object.entries(component?.[direction] || {}).map(([name, spec]) => ({
        name,
        type: typeof spec === 'string' ? spec : spec.type || 'number'
      }));
    return Object.entries({
      ...(direction === 'inputs' ? nodeInputs : nodeOutputs)[n.type] || {},
      ...n[direction] || {}
    }).map(([name, spec]) => ({
      name,
      type: typeof spec === 'string' ? spec : spec.type || 'number'
    }));
  }
  function describe(n) {
    const c = n.config || {};
    if (n.type === 'entry')
      return phase === 'next' ? activeMode === 'generator' ? 'Generate one item' : 'Current item + past state' : phase === 'process' ? 'Begin this graph' : 'Called once';
    if (n.type === 'return')
      return phase === 'next' ? 'Finish this item' : 'Finish this step';
    if (n.type === 'custom')
      return c.source || 'Write a few statements';
    if (n.type === 'condition')
      return c.expression;
    if (n.type === 'assign')
      return c.variable + ' = ' + c.expression;
    if (n.type === 'place')
      return `${ c.item || 'item' } → ${ c.bin || 'active_bin' }`;
    if (n.type === 'cover')
      return 'Close ' + (c.bin || 'active_bin') + ' when covered';
    if (n.type === 'create_bin')
      return 'Open a bin for incoming items';
    if (n.type === 'select_bin')
      return 'Work with ' + (c.expression || 'active_bin');
    if (n.type === 'random')
      return `${c.min} to ${c.max} → ${c.variable}`;
    if (n.type === 'emit')
      return c.expression + ' → next item';
    if (n.type === 'discard')
      return 'Skip item ' + (c.index || 'index');
    if (n.type === 'loop')
      return `${ c.variable } in ${ c.values }`;
    if (n.type === 'component')
      return `Reusable logic · revision ${ program.components?.[c.component_id]?.revision || '\u2014' }`;
    return Object.entries(c).filter(([k]) => k !== 'notation').map(([k, v]) => k + ': ' + (typeof v === 'object' ? JSON.stringify(v) : v)).join('\n') || n.type;
  }
  function canvasPoint(clientX, clientY) {
    const r = $('#canvas-viewport').getBoundingClientRect();
    return {x: (clientX - r.left - pan.x) / zoom, y: (clientY - r.top - pan.y) / zoom};
  }
  function ensureVisible(id) {
    const card = canvasGeometry?.cards.get(id);
    if (!card) return;
    const r = card.getBoundingClientRect(), viewport = $('#canvas-viewport').getBoundingClientRect(), margin = 25;
    if (r.left < viewport.left + margin) pan.x += viewport.left + margin - r.left;
    else if (r.right > viewport.right - margin) pan.x -= r.right - viewport.right + margin;
    if (r.top < viewport.top + margin) pan.y += viewport.top + margin - r.top;
    else if (r.bottom > viewport.bottom - margin) pan.y -= r.bottom - viewport.bottom + margin;
    applyViewportTransform();
  }
  function applyViewportTransform() {
    const inner = $('#canvas-world .builder-world'), viewport = $('#canvas-viewport');
    if (inner) inner.style.transform = `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`;
    viewport.style.backgroundPosition = `${pan.x}px ${pan.y}px`;
    viewport.style.backgroundSize = `${18 * zoom}px ${18 * zoom}px`;
    $('#zoom-label').textContent = Math.round(zoom * 100) + '%';
  }
  function zoomAt(value, clientX, clientY) {
    const r = $('#canvas-viewport').getBoundingClientRect();
    clientX ??= r.left + r.width / 2;
    clientY ??= r.top + r.height / 2;
    const anchor = canvasPoint(clientX, clientY);
    zoom = Math.min(2, Math.max(0.2, value));
    pan = {x: clientX - r.left - anchor.x * zoom, y: clientY - r.top - anchor.y * zoom};
    applyViewportTransform();
    recover();
  }
  function socketPoint(control) {
    const r = control.getBoundingClientRect(), origin = $('#canvas-world .builder-world').getBoundingClientRect();
    return {x: (r.left + r.width / 2 - origin.left) / zoom, y: (r.top + r.height / 2 - origin.top) / zoom};
  }
  function curve(a, b) {
    const bend = Math.max(45, Math.min(160, Math.abs(b.y - a.y) / 2));
    return `M${a.x},${a.y} C${a.x},${a.y + bend} ${b.x},${b.y - bend} ${b.x},${b.y}`;
  }
  function updateEdgeGeometry() {
    if (!canvasGeometry) return;
    const {svg, cards} = canvasGeometry;
    for (const e of program.edges) {
      const find = (id, direction, port) => [...(cards.get(id)?.querySelectorAll('.node-socket') || [])]
        .find(b => b.dataset.direction === direction && b.dataset.kind === (e.kind || 'control') && b.dataset.port === port);
      const source = find(e.source, 'output', e.kind === 'data' ? e.source_port : e.port || 'next');
      const target = find(e.target, 'input', e.kind === 'data' ? e.target_port : 'in');
      if (!source || !target) continue;
      const a = socketPoint(source), b = socketPoint(target);
      for (const path of svg.querySelectorAll('path[data-edge]'))
        if (path.dataset.edge === e.id) path.setAttribute('d', curve(a, b));
      const label = [...svg.querySelectorAll('text[data-edge]')].find(l => l.dataset.edge === e.id);
      if (label) { label.setAttribute('x', (a.x + b.x) / 2 + 8); label.setAttribute('y', (a.y + b.y) / 2); }
    }
  }
  function renderCanvas() {
    const world = $('#canvas-world'), nodes = phaseNodes(), focused = document.activeElement;
    const focusedNode = focused?.closest('.graph-node')?.dataset.id;
    const focusedEdge = focused?.classList.contains('graph-edge') ? focused.dataset.edge : null;
    const focusedSocket = focused?.classList.contains('node-socket') ? {...focused.dataset} : null;
    world.replaceChildren();
    world.style.width = '100%';
    world.style.height = '100%';
    const width = Math.max(700, ...nodes.map(n => n.x + 350)), height = Math.max(600, ...nodes.map(n => n.y + 300));
    const inner = node('div', 'builder-world');
    inner.style.width = width + 'px';
    inner.style.height = height + 'px';
    inner.style.transformOrigin = 'top left';
    const ns = 'http://www.w3.org/2000/svg', svg = document.createElementNS(ns, 'svg');
    svg.setAttribute('width', width);
    svg.setAttribute('height', height);
    svg.classList.add('graph-edges');
    svg.setAttribute('aria-label', 'Graph connections');
    const defs = document.createElementNS(ns, 'defs');
    for (const [name, color] of [['control', 'var(--border-strong)'], ['selected', 'var(--accent-ink)'], ['taken', 'var(--success-ink)']]) {
      const marker = document.createElementNS(ns, 'marker');
      marker.id = 'builder-arrow-' + name;
      for (const [key, value] of Object.entries({viewBox: '0 0 10 10', refX: 9, refY: 5, markerWidth: 6, markerHeight: 6, orient: 'auto-start-reverse'})) marker.setAttribute(key, value);
      const arrow = document.createElementNS(ns, 'path');
      arrow.setAttribute('d', 'M 0 0 L 10 5 L 0 10 z'); arrow.setAttribute('fill', color);
      marker.append(arrow); defs.append(marker);
    }
    svg.append(defs);
    const map = new Map(nodes.map(n => [n.id, n]));
    for (const e of program.edges) {
      const a = map.get(e.source), b = map.get(e.target);
      if (!a || !b) continue;
      const path = document.createElementNS(ns, 'path'), hit = document.createElementNS(ns, 'path');
      path.setAttribute('class', 'graph-edge' + (selectedEdge === e.id ? ' selected' : '') + (e.kind === 'data' ? ' data' : '') + (currentTraceEvent?.edge_id === e.id ? ' taken' : ''));
      path.setAttribute('marker-end', 'url(#builder-arrow-' + (currentTraceEvent?.edge_id === e.id ? 'taken' : selectedEdge === e.id ? 'selected' : 'control') + ')');
      path.setAttribute('role', 'button'); path.setAttribute('tabindex', '0');
      path.setAttribute('aria-label', `${e.kind || 'control'} connection ${e.port || e.source_port || 'next'} from ${a.label || a.type} to ${b.label || b.type}`);
      path.dataset.edge = hit.dataset.edge = e.id;
      hit.classList.add('graph-edge-hit');
      hit.setAttribute('aria-hidden', 'true');
      path.onclick = hit.onclick = event => {
        event.stopPropagation();
        selectedEdge = e.id; selected = null; selection.clear();
        renderCanvas(); renderInspector();
      };
      path.onkeydown = event => {
        if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); path.onclick(event); }
        if (event.key === 'Delete') { event.preventDefault(); removeEdge(e.id); }
      };
      svg.append(hit, path);
      if (e.port && e.port !== 'next') {
        const label = document.createElementNS(ns, 'text');
        label.classList.add('graph-edge-label'); label.dataset.edge = e.id; label.textContent = e.port;
        svg.append(label);
      }
    }
    inner.append(svg);
    const cards = new Map();
    for (const n of nodes) {
      const card = node('article', 'graph-node' + (selection.has(n.id) ? ' selected' : '') + ((currentTraceEvent?.call_path?.[0] || currentTraceEvent?.node_id) === n.id ? ' executing' : visitedNodes.has(n.id) ? ' visited' : ''));
      card.dataset.id = n.id; card.dataset.type = n.type;
      card.style.left = n.x + 'px'; card.style.top = n.y + 'px';
      const title = node('button', 'node-title');
      title.append(node('span', 'node-symbol', symbols[n.type] || '⊞'), node('span', 'node-name', n.label || n.type));
      title.type = 'button'; title.setAttribute('aria-label', `Inspect ${n.label || n.type}`);
      title.onclick = event => { if (performance.now() >= suppressClickUntil) selectNode(n.id, event.shiftKey); };
      title.onpointerdown = event => startNodeDrag(event, n, title);
      card.append(title, node('p', 'node-description', describe(n)));
      const actions = node('div', 'node-actions');
      if (n.type !== 'entry') actions.append(button('Remove', () => removeNode(n.id), 'danger'));
      if (n.type === 'component') actions.append(button('Open graph', () => openComponent(n)));
      card.append(actions);
      if (n.type !== 'entry') card.append(socket(n, 'in', 'control', 'input'));
      const sockets = node('div', 'node-sockets');
      for (const port of outputsFor(n)) {
        const group = node('span', 'socket-group');
        group.append(socket(n, port, 'control', 'output'));
        if (n.type === 'condition' || n.type === 'loop') group.append(node('span', 'socket-label', port === 'next' ? 'Done' : port[0].toUpperCase() + port.slice(1)));
        sockets.append(group);
      }
      card.append(sockets);
      const data = node('div', 'node-data-ports');
      const connectedData = program.edges.some(e => e.kind === 'data' && (e.source === n.id || e.target === n.id));
      data.hidden = !showDataPorts && !connectedData;
      if (!data.hidden)
        for (const direction of ['inputs', 'outputs'])
          for (const port of dataPorts(n, direction)) {
            const group = node('span', 'socket-group');
            group.append(socket(n, port.name, 'data', direction === 'inputs' ? 'input' : 'output', port.type), node('span', 'socket-label', (direction === 'inputs' ? '← ' : '→ ') + port.name));
            data.append(group);
          }
      if (data.children.length) card.append(data);
      inner.append(card); cards.set(n.id, card);
    }
    world.append(inner);
    canvasGeometry = {svg, cards};
    applyViewportTransform(); updateEdgeGeometry();
    if (focusedNode) {
      const card = cards.get(focusedNode);
      const replacement = focusedSocket ? [...(card?.querySelectorAll('.node-socket') || [])]
        .find(b => b.dataset.port === focusedSocket.port && b.dataset.kind === focusedSocket.kind && b.dataset.direction === focusedSocket.direction)
        : card?.querySelector('.node-title');
      (replacement || $('#canvas-viewport')).focus({preventScroll: true});
    }
    if (focusedEdge) [...svg.querySelectorAll('.graph-edge')].find(path => path.dataset.edge === focusedEdge)?.focus?.({preventScroll: true});
    $('#graph-summary').textContent = `${nodes.length} components · ${program.edges.filter(e => map.has(e.source) && map.has(e.target)).length} connections · ${program.access || 'online'}`;
    $('#connection-help').textContent = pending ? `Connect ${pending.port} → choose an input circle` : 'Drag between circles to connect · drag the background to pan';
  }
  function socket(n, port, kind, direction, type) {
    const b = node('button', 'node-socket' + (pending?.node === n.id && pending.port === port && pending.kind === kind ? ' pending' : ''));
    b.type = 'button';
    Object.assign(b.dataset, {node: n.id, port, kind, direction});
    if (type) b.dataset.valueType = type;
    b.setAttribute('aria-label', `${n.label || n.type} ${direction} ${kind} socket ${port}${type ? ' type ' + type : ''}`);
    b.title = direction === 'input' ? 'Connect an output to this input' : 'Drag to an input, or click then choose an input';
    b.onclick = () => { if (performance.now() >= suppressClickUntil) runAction(() => connectSocket(n, port, kind, direction, type)); };
    b.onpointerdown = event => {
      event.stopPropagation();
      if (!owned || direction !== 'output' || event.button !== 0) return;
      event.preventDefault();
      const startX = event.clientX, startY = event.clientY;
      let started = false, path = null, candidate = null;
      const move = e => {
        if (!started && Math.hypot(e.clientX - startX, e.clientY - startY) < 6) return;
        if (!started) {
          started = true;
          pending = {node: n.id, port, kind, type}; b.classList.add('pending');
          path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
          path.classList.add('connection-preview'); canvasGeometry.svg.append(path);
          $('#connection-help').textContent = 'Release on an input circle to connect';
        }
        candidate?.classList.remove('connect-target');
        const target = document.elementFromPoint(e.clientX, e.clientY)?.closest('.node-socket');
        candidate = target?.dataset.direction === 'input' && target.dataset.kind === kind && target.dataset.node !== n.id ? target : null;
        candidate?.classList.add('connect-target');
        path.setAttribute('d', curve(socketPoint(b), candidate ? socketPoint(candidate) : canvasPoint(e.clientX, e.clientY)));
      };
      const end = e => {
        document.removeEventListener('pointermove', move);
        document.removeEventListener('pointerup', end);
        document.removeEventListener('pointercancel', cancel);
        candidate?.classList.remove('connect-target'); path?.remove();
        if (!started) return;
        suppressClickUntil = performance.now() + 200;
        const target = document.elementFromPoint(e.clientX, e.clientY)?.closest('.node-socket');
        if (e.type === 'pointerup' && target?.dataset.direction === 'input')
          runAction(() => connectSocket(program.nodes.find(v => v.id === target.dataset.node), target.dataset.port, target.dataset.kind, 'input', target.dataset.valueType));
        else { pending = null; renderCanvas(); }
      };
      const cancel = e => end(e);
      document.addEventListener('pointermove', move);
      document.addEventListener('pointerup', end);
      document.addEventListener('pointercancel', cancel);
    };
    return b;
  }
  function connectSocket(n, port, kind, direction, type) {
    if (!owned)
      throw Error('Clone this revision to change its connections.');
    if (direction === 'output') {
      pending = {
        node: n.id,
        port,
        kind,
        type
      };
      renderCanvas();
      return;
    }
    if (!pending)
      throw Error('Choose an output socket first.');
    if (pending.kind !== kind)
      throw Error('Execution sockets connect to execution sockets; data sockets connect to data sockets.');
    if (pending.node === n.id)
      throw Error('Self connections are not supported. Use a bounded-loop component.');
    if (kind === 'data' && pending.type && type && pending.type !== type && !['any'].includes(pending.type) && !['any'].includes(type) && !(pending.type === 'integer' && type === 'number'))
      throw Error(`Cannot connect ${ pending.type } to ${ type }.`);
    const source = pending;
    mutate(() => {
      if (kind === 'control')
        program.edges = program.edges.filter(e => !(e.source === source.node && (e.port || 'next') === source.port && e.kind !== 'data'));
      else
        program.edges = program.edges.filter(e => !(e.target === n.id && e.target_port === port && e.kind === 'data'));
      program.edges.push({
        id: uid('edge'),
        source: source.node,
        target: n.id,
        port: source.port,
        kind,
        ...kind === 'data' ? {
          source_port: source.port,
          target_port: port
        } : {}
      });
      pending = null;
    });
    feedback('Connection added. The server validates lifecycle, branch completion, and data types in your preview.');
  }
  function selectNode(id, multiple = false) {
    if (multiple) {
      if (selection.has(id))
        selection.delete(id);
      else
        selection.add(id);
    } else
      selection = new Set([id]);
    selected = id;
    selectedEdge = null;
    renderCanvas();
    renderInspector();
    [...$('#canvas-world').querySelectorAll('.graph-node')].find(card => card.dataset.id === id)?.querySelector('.node-title')?.focus({preventScroll: true});
    if (preview && traceController)
      traceController.filterNode(id);
  }
  function removeNode(id) {
    const n = program.nodes.find(n => n.id === id);
    if (!n || !owned)
      return;
    if (n.type === 'entry')
      throw Error('Lifecycle entries are fixed. Change or remove the operations connected to them.');
    const count = program.edges.filter(e => e.source === id || e.target === id).length;
    mutate(() => {
      program.nodes = program.nodes.filter(n => n.id !== id);
      program.edges = program.edges.filter(e => e.source !== id && e.target !== id);
      selection.delete(id);
      if (selected === id)
        selected = null;
    });
    feedback(`Removed ${ n.label || n.type } and ${ count } affected connection${ count === 1 ? '' : 's' }. Undo restores both. Reconnect any incomplete path.`);
  }
  function removeEdge(id) {
    if (!owned)
      return;
    mutate(() => {
      program.edges = program.edges.filter(e => e.id !== id);
      selectedEdge = null;
    });
    feedback('Connection removed. Undo restores it.');
  }
  function startNodeDrag(event, n, title) {
    if (!owned || event.button !== 0 || event.target.closest('.node-socket'))
      return;
    event.stopPropagation();
    const x = event.clientX, y = event.clientY, original = {
        x: n.x,
        y: n.y
      };
    let started = false;
    const move = e => {
      if (!started && Math.abs(e.clientX - x) + Math.abs(e.clientY - y) < 6)
        return;
      if (!started) {
        record();
        started = true;
        title.setPointerCapture?.(event.pointerId);
        selected = n.id;
        selection = new Set([n.id]);
      }
      n.x = original.x + (e.clientX - x) / zoom;
      n.y = original.y + (e.clientY - y) / zoom;
      const card = title.closest('.graph-node');
      card.style.left = n.x + 'px';
      card.style.top = n.y + 'px';
      updateEdgeGeometry();
    };
    const end = () => {
      document.removeEventListener('pointermove', move);
      document.removeEventListener('pointerup', end);
      document.removeEventListener('pointercancel', end);
      if (started) {
        suppressClickUntil = performance.now() + 200;
        changed();
        renderInspector();
      }
    };
    document.addEventListener('pointermove', move);
    document.addEventListener('pointerup', end);
    document.addEventListener('pointercancel', end);
  }
  function inputField(parent, label, value, onChange, options = {}) {
    const wrap = node('label', '', label), input = node(options.multiline ? 'textarea' : options.select ? 'select' : 'input');
    if (options.select)
      for (const [v, text] of options.select) {
        const option = node('option', '', text);
        option.value = v;
        input.append(option);
      }
    if (options.type)
      input.type = options.type;
    input.value = value ?? '';
    input.setAttribute('aria-label', label);
    input.disabled = !owned;
    input.spellcheck = false;
    if (options.multiline)
      input.rows = options.rows || 5;
    input.onfocus = () => {
      typingSnapshot = signature();
    };
    input.onchange = () => runAction(() => {
      if (typingSnapshot !== signature())
        typingSnapshot = null;
      record();
      onChange(input.value);
      changed(false);
      renderInspector();
    });
    wrap.append(input);
    parent.append(wrap);
    return input;
  }
  function renderInspector() {
    const target = $('#inspector');
    target.replaceChildren();
    const n = currentNode();
    if (selectedEdge) {
      const edge = program.edges.find(e => e.id === selectedEdge);
      target.append(node('p', 'field-help', edge ? `${ edge.kind || 'control' } connection: ${ edge.source } → ${ edge.target }` : 'Select a connection.'), button('Remove connection', () => removeEdge(selectedEdge), 'danger'));
      return;
    }
    if (!n) {
      target.append(node('p', 'field-help', 'Select a component to configure it. Shift-click a group to make it reusable.'));
      return;
    }
    const kindLabels = {entry: 'Lifecycle', assign: 'Set state', condition: 'Condition', place: 'Place item', cover: 'Close bin', create_bin: 'Create bin', select_bin: 'Select bin', discard: 'Discard item', loop: 'Repeat', custom: 'Custom logic', component: 'Reusable component', random: 'Random value', emit: 'Emit item', return: 'End step'};
    target.append(node('span', 'selected-kind', kindLabels[n.type] || n.type));
    inputField(target, 'Label', n.label || n.type, value => n.label = value);
    if (n.type === 'entry') {
      target.append(node('p', 'field-help', 'This fixed entry is called by the system. Its connected operations are yours to change or remove.'));
      return;
    }
    target.append(button('Remove component', () => removeNode(n.id), 'danger'));
    const c = n.config;
    if (n.type === 'custom') {
      const selector = inputField(target, 'Notation', c.notation || 'python', () => {
      }, {
        select: [
          [
            'python',
            'Simple Python'
          ],
          [
            'pseudocode',
            'Defined pseudocode'
          ]
        ]
      });
      selector.onchange = async () => {
        const previous = c.notation || 'python';
        const requested = selector.value;
        selector.disabled = true;
        try {
          const translated = await post('/api/builder/translate', {
            source: c.source || '',
            from_notation: previous,
            to_notation: requested
          });
          mutate(() => {
            c.source = translated.source;
            c.notation = requested;
          });
          feedback('Notation changed without replacing your statements.');
        } catch (error) {
          selector.value = previous;
          feedback(error.message + ' Your original draft is preserved.', true);
        } finally {
          selector.disabled = !owned;
        }
      };
      const code = inputField(target, 'Statements', c.source, value => c.source = value, {
        multiline: true,
        rows: 7
      });
      code.id = 'custom-source';
      code.setAttribute('aria-describedby', 'custom-syntax-help');
      code.onkeydown = e => {
        if (e.key === 'Tab' && !e.shiftKey) {
          e.preventDefault();
          const start = code.selectionStart, end = code.selectionEnd;
          code.setRangeText('    ', start, end, 'end');
        }
      };
      const exLabel = node('label', '', 'Insert example'), examples = node('select');
      examples.setAttribute('aria-label', 'Insert example');
      examples.append(new Option('Choose an example\u2026', ''));
      for (const [name, key] of [
          [
            'Close a covered bin',
            'cover'
          ],
          [
            'Update a state value',
            'state'
          ],
          [
            'Seeded random choice',
            'random'
          ],
          [
            'Emit a generated item',
            'emit'
          ],
          [
            'Offline bounded loop',
            'loop'
          ]
        ]) {
        if (activeMode === 'generator' && ['cover', 'loop'].includes(key)) continue;
        if (activeMode === 'algorithm' && key === 'emit') continue;
        examples.append(new Option(name, key));
      }
      examples.disabled = !owned;
      examples.onchange = () => {
        const python = {
          cover: 'if bin_load(active_bin) >= threshold:\n    cover(active_bin)',
          state: 'count = count + 1',
          random: 'pick = uniform(0, 1)',
          emit: 'emit(uniform(0.1, 0.9))',
          loop: 'for i in range(len(sequence)):\n    place(sequence[i], active_bin, i)\n    if bin_load(active_bin) >= threshold:\n        cover(active_bin)'
        };
        runAction(async () => {
          let source = python[examples.value];
          if (!source)
            return;
          if (c.notation === 'pseudocode')
            source = (await post('/api/builder/translate', {
              source,
              from_notation: 'python',
              to_notation: 'pseudocode'
            })).source;
          mutate(() => {
            c.source = source;
          });
        });
      };
      exLabel.append(examples);
      target.append(exLabel);
      const help = node('details', 'custom-help');
      help.open = false;
      help.id = 'custom-syntax-help';
      help.append(node('summary', '', 'Syntax guide and available helpers'), node('p', '', 'Write statements only. The graph supplies Start, Next item, and Stop. Variables come from state, parameters, and this phase.'));
      const list = node('ul');
      for (const text of [
          'Numbers, booleans, variables, assignments, arithmetic, comparisons, if / else, and bounded for loops.',
          'place(item, active_bin, index) records an item placement; cover(active_bin) closes only a bin that reaches threshold.',
          'create_bin(), select_bin(bin), bin_load(bin), discard(index), emit(size), uniform(low, high), randint(low, high).',
          'Online: item, index and past state. Offline: sequence and indices. Generator: index, parameters and seeded helpers.',
          'No imports, classes, attributes, filesystem or network. Measured coverage and bin accounting are managed by the runtime.'
        ])
        list.append(node('li', '', text));
      help.append(list, node('pre', '', c.notation === 'pseudocode' ? 'SET count = count + 1\nIF BIN_LOAD(active_bin) >= threshold THEN\n    COVER active_bin\nEND' : 'count = count + 1\nif bin_load(active_bin) >= threshold:\n    cover(active_bin)'));
      target.append(help);
      renderTypedPorts(target, n);
      if (preview?.error?.node_id === n.id)
        target.append(node('p', 'feedback feedback-error', `${ preview.error.line ? 'Line ' + preview.error.line + ': ' : '' }${ preview.error.message }`));
      return;
    }
    if (n.type === 'component') {
      target.append(node('p', 'field-help', 'A reusable group of steps. Open its graph to inspect or edit the logic inside.'), button('Open component graph', () => openComponent(n), 'secondary'));
      const mappings = node('details', 'custom-help');
      mappings.append(node('summary', '', 'Inputs and parameters'));
      inputField(mappings, 'Input expressions (JSON)', JSON.stringify(c.inputs || {}, null, 2), v => c.inputs = parseObject(v), {
        multiline: true,
        rows: 3
      });
      inputField(mappings, 'Output variables (JSON)', JSON.stringify(c.outputs || {}, null, 2), v => c.outputs = parseObject(v), {
        multiline: true,
        rows: 3
      });
      inputField(mappings, 'Parameter overrides (JSON)', JSON.stringify(c.params || {}, null, 2), v => c.params = parseObject(v), {
        multiline: true,
        rows: 3
      });
      target.append(mappings);
      target.append(node('p', 'field-help', 'The instance references an immutable revision. Edit its definition in a new draft, test it, and make the new revision available before updating this instance.'));
      return;
    }
    const names = {
      variable: 'State variable',
      expression: 'Expression',
      item: 'Item expression',
      bin: 'Bin expression',
      index: 'Item index',
      min: 'Minimum expression',
      max: 'Maximum expression',
      integer: 'Integer random choice',
      values: 'Loop values expression'
    };
    for (const [key, value] of Object.entries(c)) {
      if (typeof value === 'boolean')
        inputField(target, names[key] || key, String(value), v => c[key] = v === 'true', {
          select: [
            [
              'false',
              'No'
            ],
            [
              'true',
              'Yes'
            ]
          ]
        });
      else
        inputField(target, names[key] || key, typeof value === 'object' ? JSON.stringify(value) : value, v => c[key] = typeof value === 'object' ? parseObject(v) : v);
    }
    if (n.type === 'condition')
      target.append(node('p', 'field-help', 'Connect both yes and no outputs. Branches are recorded in the execution trace.'));
    if (n.type === 'loop')
      target.append(node('p', 'field-help', 'Connect body to the loop operations and next to the continuation. The runtime bounds iteration and rejects arbitrary cycles.'));
    if (n.type === 'return')
      target.append(node('p', 'field-help', 'Ends this lifecycle phase or returns to the enclosing bounded loop/component.'));
    const ports = node('details', 'custom-help');
    ports.append(node('summary', '', 'Typed data ports'));
    inputField(ports, 'Inputs (JSON)', JSON.stringify(n.inputs || {}, null, 2), v => n.inputs = parseObject(v), {
      multiline: true,
      rows: 3
    });
    inputField(ports, 'Outputs (JSON)', JSON.stringify(n.outputs || {}, null, 2), v => n.outputs = parseObject(v), {
      multiline: true,
      rows: 3
    });
    ports.append(node('p', 'field-help', 'Example: {"value":{"type":"number"}}. Data edges must match types; execution connections determine order.'));
    target.append(ports);
  }
  function renderTypedPorts(target, n) {
    const ports = node('details', 'custom-help');
    ports.append(node('summary', '', 'Typed data ports'));
    inputField(ports, 'Inputs (JSON)', JSON.stringify(n.inputs || {}, null, 2), v => n.inputs = parseObject(v), {
      multiline: true,
      rows: 3
    });
    inputField(ports, 'Outputs (JSON)', JSON.stringify(n.outputs || {}, null, 2), v => n.outputs = parseObject(v), {
      multiline: true,
      rows: 3
    });
    inputField(ports, 'Output expressions (JSON)', JSON.stringify(n.config.exports || {}, null, 2), v => n.config.exports = parseObject(v), {
      multiline: true,
      rows: 3
    });
    ports.append(node('p', 'field-help', 'Declare a typed port, then map its output name to an expression: {"value":"count"}. Data sockets are distinct from execution order.'));
    target.append(ports);
  }
  function parseObject(text) {
    const value = JSON.parse(text);
    if (!value || typeof value !== 'object' || Array.isArray(value))
      throw Error('Enter a JSON object.');
    return value;
  }
  async function saveDraft() {
    if (!owned)
      throw Error('Clone the shared revision to create your own draft.');
    if (saving)
      return;
    const name = $('#builder-name').value.trim();
    if (!name)
      throw Error('Give this builder a name.');
    saving = true;
    $('#save-draft').disabled = true;
    try {
      const result = itemId ? await api(libraryUrl(), {
        method: 'PUT',
        body: JSON.stringify({
          name,
          graph: program
        })
      }) : await post('/api/builder/library', {
        name,
        kind: program.kind,
        graph: program
      });
      itemId = result.id;
      dirty = false;
      $('#draft-status').textContent = 'Saved draft';
      recover();
      feedback('Draft saved. Incomplete graphs can be kept here while you finish them.');
      await refreshLibrary();
      return result;
    } finally {
      saving = false;
      $('#save-draft').disabled = !owned;
    }
  }
  async function refreshLibrary() {
    const response = await api('/api/builder/library' + ($('#library-filter').value === 'archived' ? '?archived=true' : ''));
    library = response.items || [];
    renderPalette();
    return library;
  }
  async function runPreview() {
    if (currentJob || submittingPreview)
      return;
    submittingPreview = true;
    $('#run-preview').disabled = true;
    try {
      await saveDraft();
      const items = $('#preview-items').value.split(/[\s,]+/).filter(Boolean).map(Number);
      if (items.some(v => !Number.isFinite(v)))
        throw Error('Item sizes must be finite numbers.');
      const seed = Number($('#preview-seed').value), n = Number($('#preview-count').value);
      if (!Number.isInteger(seed) || seed < 0)
        throw Error('Seed must be a nonnegative integer.');
      previewSignature = signature();
      previewGraph = copy(program);
      preview = null;
      $('#available').disabled = true;
      traceController?.destroy();
      $('#preview-trace').replaceChildren();
      $('#preview-status').textContent = 'Submitting the current draft for an isolated preview…';
      const result = await post(libraryUrl() + '/preview', {
        graph: program,
        settings: {
          items,
          n,
          seed,
          params: Object.fromEntries(Object.entries(program.parameters || {}).map(([k, v]) => [
            k,
            v?.default ?? v
          ])),
          ...(program.kind === 'component' ? {
            inputs: parseObject($('#preview-component-values').value),
            component_context: parseObject($('#preview-component-context').value)
          } : {}),
          domain: program.domain,
          threshold: program.threshold ?? 1
        }
      });
      currentJob = result.id;
      $('#run-preview').disabled = true;
      $('#cancel-preview').hidden = false;
      $('#available').disabled = true;
      $('#preview-status').textContent = 'Preview queued in the isolated runtime\u2026';
      traceController?.destroy();
      $('#preview-trace').replaceChildren();
      const serial = ++pollSerial;
      pollPreview(serial);
    } finally {
      submittingPreview = false;
      $('#run-preview').disabled = !owned || !!currentJob;
    }
  }
  async function pollPreview(serial) {
    if (serial !== pollSerial || !currentJob)
      return;
    try {
      const job = await api('/api/builder/jobs/' + encodeURIComponent(currentJob));
      if (serial !== pollSerial)
        return;
      if ([
          'queued',
          'running'
        ].includes(job.status)) {
        $('#preview-status').textContent = `Preview ${ job.status }…`;
        setTimeout(() => pollPreview(serial), 500);
        return;
      }
      const jobId = currentJob;
      currentJob = null;
      $('#run-preview').disabled = !owned;
      $('#cancel-preview').hidden = true;
      preview = job.result || {
        ok: false,
        error: { message: job.error?.message || job.error || `Preview ${ job.status }` }
      };
      preview.jobId = jobId;
      const stale = signature() !== previewSignature;
      $('#available').disabled = stale || !preview.ok || job.status !== 'completed';
      $('#preview-status').textContent = stale ? 'Preview finished for an older draft. Run this edited graph again.' : preview.ok ? 'Preview completed. Follow the actual recorded operations below.' : `Preview ${ job.status }: ${ preview.error?.message || job.error || 'Execution failed' }`;
      $('#preview-status').classList.toggle('feedback-error', !preview.ok);
      traceController = window.BinCoveringTrace.mount($('#preview-trace'), {
        ...preview,
        graph: previewGraph
      }, {
        showGraph: true,
        threshold: previewGraph.threshold || 1
      });
      if (preview.error?.node_id) {
        selected = preview.error.node_id;
        selection = new Set([selected]);
        const errorNode = currentNode();
        if (errorNode)
          phase = errorNode.phase;
        renderAll();
      }
    } catch (error) {
      currentJob = null;
      $('#cancel-preview').hidden = true;
      $('#run-preview').disabled = !owned;
      feedback(error.message, true, $('#preview-status'));
    }
  }
  async function cancelPreview() {
    if (!currentJob)
      return;
    await post('/api/builder/jobs/' + encodeURIComponent(currentJob) + '/cancel');
    $('#preview-status').textContent = 'Cancelling isolated preview\u2026';
  }
  async function makeAvailable() {
    if ($('#available').disabled)
      return;
    $('#available').disabled = true;
    try {
      if (!preview?.ok || previewSignature !== signature())
        throw Error('Run a successful preview of this exact draft first.');
      if (dirty)
        await saveDraft();
      const result = await post(libraryUrl() + '/available', { job_id: preview.jobId });
      $('#draft-status').textContent = 'Available revision ' + (result.frozen?.revision || result.item?.revision || '');
      feedback('Immutable revision is available on Dashboard. Future draft edits will not change it.');
      await refreshLibrary();
    } finally {
      $('#available').disabled = !preview?.ok || previewSignature !== signature();
    }
  }
  function download(data, filename, type) {
    const url = URL.createObjectURL(new Blob([data], { type }));
    const a = node('a');
    a.href = url;
    a.download = filename;
    document.body.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  async function exportGraph() {
    download(JSON.stringify(program, null, 2), ($('#builder-name').value || 'builder') + '.json', 'application/json');
  }
  async function exportPython() {
    if (!itemId)
      await saveDraft();
    const item = library.find(i => i.id === itemId) || await api(libraryUrl());
    if (!item.revision)
      throw Error('Make a successfully tested revision available before exporting its Python adapter. Graph drafts can be exported at any time.');
    location.href = libraryUrl() + '/export?revision=' + encodeURIComponent(item.revision) + '&format=python';
  }
  async function renderLibrary() {
    const items = await refreshLibrary(), target = $('#library-items');
    target.replaceChildren();
    const archived = $('#library-filter').value === 'archived';
    const shown = items.filter(i => archived ? i.archived : !i.archived);
    if (!shown.length)
      target.append(node('p', 'field-help', archived ? 'No archived components.' : 'Save a draft to start your library. Shared read-only revisions appear here too.'));
    for (const item of shown) {
      const card = node('article', 'library-card');
      card.append(node('h3', '', item.name), node('p', '', `${ item.kind } · ${ item.draft?.access || 'online' } · ${ item.draft?.domain || 'float64' } · ${ item.owned ? 'Private draft' : 'Shared read-only' }${ item.revision ? ' \xB7 revision ' + item.revision : '' }`));
      const actions = node('div', 'builder-actions');
      if (!item.archived)
        actions.append(button(item.owned ? 'Open draft' : 'View shared revision', () => {
          load(item.draft, item.id, item.name, item.owned);
          $('#library-dialog').close();
        }, 'secondary'));
      if (item.revision) {
        const select = node('select');
        select.className = 'library-revision';
        select.setAttribute('aria-label', 'Revision of ' + item.name);
        for (const r of item.revisions || [])
          select.append(new Option(`Revision ${ r.revision }${ r.shared ? ' \xB7 shared' : '' }`, r.revision));
        select.value = item.revision;
        card.append(select);
        actions.append(button('Clone revision', async () => {
          const cloned = await post(libraryUrl(item.id) + '/clone', {
            revision: select.value,
            name: item.name + ' copy'
          });
          load(cloned.draft, cloned.id, cloned.name, true);
          $('#library-dialog').close();
          feedback('Created your private editable copy.');
        }, 'secondary'));
        actions.append(button('Download graph', () => {
          location.href = libraryUrl(item.id) + '/export?revision=' + select.value + '&format=graph';
        }));
        if (item.owned)
          actions.append(button('Share / revoke', async () => {
            const r = item.revisions.find(r => String(r.revision) === select.value);
            await post(libraryUrl(item.id) + '/share', {
              revision: select.value,
              shared: !r.shared
            });
            feedback(r.shared ? 'Sharing revoked for new access.' : 'This immutable revision is shared read-only; others can run or clone it.', false, $('#library-feedback'));
            await renderLibrary();
          }));
      }
      if (item.owned)
        actions.append(button(item.archived ? 'Restore' : 'Archive', async () => {
          await post(libraryUrl(item.id) + (item.archived ? '/restore' : '/archive'));
          const wasArchived = item.archived;
          feedback(wasArchived ? 'Definition restored.' : 'Definition archived. Existing experiment evidence is preserved.', false, $('#library-feedback'));
          if (!wasArchived) {
            const undo = button('Undo archive', async () => {
              await post(libraryUrl(item.id) + '/restore');
              await renderLibrary();
            });
            $('#library-feedback').append(' ', undo);
          }
          await renderLibrary();
        }, item.archived ? 'secondary' : 'danger'));
      card.append(actions);
      target.append(card);
    }
  }
  async function openComponent(n) {
    const def = program.components?.[n.config.component_id];
    if (!def)
      throw Error('No reusable definition is attached.');
    parents.push({
      program: copy(program),
      itemId,
      owned,
      phase,
      selected,
      name: $('#builder-name').value,
      instanceId: n.id,
      componentId: n.config.component_id,
      previewSettings: capturePreviewSettings(),
      undo: copy(undo),
      redo: copy(redo),
      dirty
    });
    if (!n.config.component_id.startsWith('custom:')) {
      parents[parents.length - 1].inlineId = n.config.component_id;
      load(def.graph, null, n.label, owned);
      feedback('Editing the inline component. Return to the parent graph to retain these changes.');
      return;
    }
    let item;
    try {
      item = await api(libraryUrl(n.config.component_id));
      if (!item.owned) item = await api(libraryUrl(n.config.component_id) + '?revision=' + def.revision);
    } catch {
      // A shared root revision includes its evidence even if the original private
      // dependency has never been separately shared with this reader.
      load(def.graph, null, n.label || 'Frozen component', false);
      feedback('Viewing the frozen component inside this shared revision. Clone the parent revision to edit its bundled definitions.');
      return;
    }
    load(item.draft, item.id, item.name, item.owned && !item.archived);
    feedback(item.owned ? 'Editing this component draft. Make its new revision available, then return to update the instance.' : 'This shared definition is read-only. Clone it in the library to edit your own copy.');
  }
  async function closeComponent() {
    if (!parents.length)
      return;
    const parent = parents.pop();
    const inlineGraph = parent.inlineId ? copy(program) : null;
    const componentId = itemId;
    const updated = library.find(i => i.id === componentId);
    let frozen;
    if (updated?.revision)
      frozen = await api(libraryUrl(componentId) + '?revision=' + updated.revision);
    load(parent.program, parent.itemId, parent.name, parent.owned);
    restorePreviewSettings(parent.previewSettings);
    phase = parent.phase;
    selected = parent.selected;
    selection = new Set(selected ? [selected] : []);
    undo = parent.undo;
    redo = parent.redo;
    dirty = parent.dirty;
    if (inlineGraph && owned && JSON.stringify(inlineGraph) !== JSON.stringify(program.components[parent.inlineId]?.graph)) {
      mutate(() => {
        program.components[parent.inlineId] = {
          ...program.components[parent.inlineId],
          revision: Number(program.components[parent.inlineId]?.revision || 1) + 1,
          graph: inlineGraph
        };
      });
      feedback('Inline component updated. Test the parent graph again.');
      return;
    }
    if (owned && frozen && componentId === parent.componentId && Number(frozen.revision) > Number(program.components[componentId]?.revision)) {
      mutate(() => {
        program.components[componentId] = {
          revision: Number(frozen.revision),
          graph: frozen.frozen.graph
        };
      });
      feedback('Parent instance now uses the newly available component revision. Test the parent again.');
    } else {
      renderAll();
      feedback('Returned to the parent graph. Its immutable component revision is preserved.');
    }
  }
  function selectedComponentGraph() {
    if (!owned)
      throw Error('Clone this shared revision before creating an editable component.');
    const selectedNodes = program.nodes.filter(n => selection.has(n.id) && n.type !== 'entry');
    if (!selectedNodes.length)
      throw Error('Select one or more editable connected operations.');
    const ids = new Set(selectedNodes.map(n => n.id)), internal = program.edges.filter(e => ids.has(e.source) && ids.has(e.target)), incoming = program.edges.filter(e => !ids.has(e.source) && ids.has(e.target) && e.kind !== 'data');
    const roots = selectedNodes.filter(n => !internal.some(e => e.target === n.id && e.kind !== 'data'));
    const root = incoming[0]?.target || roots[0]?.id;
    if (!root || new Set([
        ...incoming.map(e => e.target),
        ...roots.map(n => n.id)
      ]).size > 1)
      throw Error('Choose a connected group with one execution entry.');
    const exitTargets = new Set(program.edges.filter(e => ids.has(e.source) && !ids.has(e.target) && e.kind !== 'data').map(e => e.target));
    if (exitTargets.size > 1)
      throw Error('Choose a group with one continuation, or include the branch merge in your selection.');
    const start = uid('component_entry'), end = uid('component_return');
    const nodes = selectedNodes.map(n => ({
      ...copy(n),
      phase: 'process'
    }));
    nodes.push({
      id: start,
      type: 'entry',
      label: 'Component input',
      phase: 'process',
      x: 20,
      y: 20,
      config: {}
    }, {
      id: end,
      type: 'return',
      label: 'Component output',
      phase: 'process',
      x: 40,
      y: Math.max(...nodes.map(n => n.y)) + 190,
      config: {}
    });
    const edges = copy(internal);
    edges.push({
      id: uid('edge'),
      source: start,
      target: root,
      port: 'next',
      kind: 'control'
    });
    for (const n of selectedNodes)
      for (const port of outputsFor(n))
        if (!internal.some(e => e.source === n.id && (e.port || 'next') === port && e.kind !== 'data'))
          edges.push({
            id: uid('edge'),
            source: n.id,
            target: end,
            port,
            kind: 'control'
          });
    return {
      schema_version: 1,
      kind: 'component',
      access: program.access,
      domain: program.domain,
      threshold: program.threshold,
      entries: { process: start },
      nodes,
      edges,
      components: copy(program.components),
      state: copy(program.state),
      parameters: parseObject($('#component-params').value),
      inputs: parseObject($('#component-inputs').value),
      outputs: parseObject($('#component-outputs').value)
    };
  }
  async function saveComponent(event) {
    event.preventDefault();
    try {
      const g = selectedComponentGraph(), name = $('#component-name').value.trim();
      if (!name)
        throw Error('Give your reusable component a name.');
      const item = await post('/api/builder/library', {
        name,
        kind: 'component',
        graph: g
      });
      parents.push({
        program: copy(program),
        itemId,
        owned,
        phase,
        selected,
        name: $('#builder-name').value,
        undo: copy(undo),
        redo: copy(redo),
        dirty,
        componentId: item.id,
        previewSettings: capturePreviewSettings()
      });
      $('#component-dialog').close();
      load(item.draft, item.id, item.name, true);
      feedback('Component draft saved. Test and make it available to add it from the palette.');
    } catch (error) {
      feedback(error.message, true, $('#component-feedback'));
    }
  }
  function fit() {
    const nodes = phaseNodes();
    if (!nodes.length)
      return;
    const viewport = $('#canvas-viewport'), cards = canvasGeometry?.cards;
    const minX = Math.min(...nodes.map(n => n.x)) - 20, minY = Math.min(...nodes.map(n => n.y)) - 25;
    const maxX = Math.max(...nodes.map(n => n.x + (cards?.get(n.id)?.offsetWidth || 190))) + 20;
    const maxY = Math.max(...nodes.map(n => n.y + (cards?.get(n.id)?.offsetHeight || 120))) + 25;
    zoom = Math.min(1, Math.max(0.2, Math.min(viewport.clientWidth / (maxX - minX), viewport.clientHeight / (maxY - minY))));
    pan = {x: (viewport.clientWidth - (maxX + minX) * zoom) / 2, y: (viewport.clientHeight - (maxY + minY) * zoom) / 2};
    applyViewportTransform();
  }
  function setup() {
    $('#fixture-bin').onclick = () => {
      $('#preview-items').value = '0.4, 0.7';
      $('#preview-component-context').value = JSON.stringify({
        kind: 'algorithm',
        bins: [[
            0,
            1
          ]],
        current_index: 1
      });
    };
    $('#fixture-generator').onclick = () => {
      $('#preview-items').value = '';
      $('#preview-component-context').value = JSON.stringify({ kind: 'generator' });
    };
    $('#fixture-none').onclick = () => {
      $('#preview-component-context').value = '{}';
    };
    $('#save-draft').onclick = () => runAction(saveDraft);
    $('#available').onclick = () => runAction(makeAvailable);
    $('#run-preview').onclick = () => runAction(runPreview);
    $('#cancel-preview').onclick = () => runAction(cancelPreview);
    $('#export-graph').onclick = () => runAction(exportGraph);
    $('#export-python').onclick = () => runAction(exportPython);
    $('#undo').onclick = () => restoreHistory(undo, redo);
    $('#redo').onclick = () => restoreHistory(redo, undo);
    $('#fit').onclick = fit;
    $('#zoom-in').onclick = () => zoomAt(zoom + 0.1);
    $('#zoom-out').onclick = () => zoomAt(zoom - 0.1);
    $('#data-wiring').onclick = () => {
      showDataPorts = !showDataPorts;
      pending = null;
      renderModes(); renderCanvas(); recover();
    };
    for (const mode of ['algorithm', 'generator']) {
      const tab = $('#builder-' + mode + '-tab');
      tab.onclick = () => switchMode(mode);
      tab.onkeydown = event => {
        if (['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) {
          event.preventDefault();
          const next = event.key === 'Home' ? 'algorithm' : event.key === 'End' ? 'generator' : activeMode === 'algorithm' ? 'generator' : 'algorithm';
          switchMode(next);
          $('#builder-' + next + '-tab').focus();
        }
      };
    }
    $('#builder-name').onchange = () => mutate(() => {
      program.name = $('#builder-name').value;
    });
    $('#builder-params').onchange = () => runAction(() => {
      const value = parseObject($('#builder-params').value);
      mutate(() => program.parameters = value);
    });
    $('#builder-state').onchange = () => runAction(() => {
      const value = parseObject($('#builder-state').value);
      mutate(() => program.state = value);
    });
    $('#builder-inputs').onchange = () => runAction(() => {
      const value = parseObject($('#builder-inputs').value);
      mutate(() => program.inputs = value);
    });
    $('#builder-outputs').onchange = () => runAction(() => {
      const value = parseObject($('#builder-outputs').value);
      mutate(() => program.outputs = value);
    });
    $('#builder-starter').onchange = () => {
      const t = templates.find(t => t.id === $('#builder-starter').value);
      if (t) {
        parents = [];
        load(starterGraph(t), null, t.name);
        feedback('Working starter loaded. Save it as your own draft.');
      }
    };
    $('#import-graph').onchange = () => runAction(async () => {
      const file = $('#import-graph').files[0];
      if (!file)
        return;
      if (file.size > 1000000)
        throw Error('Graph import exceeds 1 MB.');
      const value = JSON.parse(await file.text());
      const imported = value.graph || value;
      if (imported.schema_version !== 1 || !Array.isArray(imported.nodes) || !Array.isArray(imported.edges) || !imported.entries)
        throw Error('Choose a version 1 builder graph.');
      parents = [];
      load(imported, null, file.name.replace(/\.json$/, ''));
      dirty = true;
      changed();
      feedback('Imported a private draft. Server validation is required before execution.');
      $('#import-graph').value = '';
    });
    $('#open-library').onclick = () => runAction(async () => {
      await renderLibrary();
      $('#library-dialog').showModal();
    });
    $('#library-filter').onchange = () => runAction(renderLibrary);
    document.querySelectorAll('[data-close-dialog]').forEach(b => b.onclick = () => b.closest('dialog').close());
    $('#save-component').onclick = () => runAction(() => {
      selectedComponentGraph();
      $('#component-dialog').showModal();
    });
    $('#component-form').onsubmit = saveComponent;
    $('#close-component').onclick = () => runAction(closeComponent);
    const viewport = $('#canvas-viewport');
    // Keyboard focus can request native scrolling even on overflow:hidden. Keep
    // the view in the same pan coordinate system used by dragging and wiring.
    viewport.onscroll = () => {
      if (!viewport.scrollLeft && !viewport.scrollTop) return;
      pan.x -= viewport.scrollLeft; pan.y -= viewport.scrollTop;
      viewport.scrollLeft = 0; viewport.scrollTop = 0;
      applyViewportTransform();
    };
    viewport.ondragover = e => {
      if (e.dataTransfer.types.some(t => t.startsWith('application/bincovering'))) {
        e.preventDefault();
        e.dataTransfer.dropEffect = 'copy';
      }
    };
    viewport.ondrop = e => {
      e.preventDefault();
      const position = canvasPoint(e.clientX, e.clientY);
      const raw = e.dataTransfer.getData('application/bincovering-node'), component = e.dataTransfer.getData('application/bincovering-component');
      if (raw)
        runAction(() => {
          const spec = JSON.parse(raw);
          addNode(spec.type, spec.label, spec.config, position);
        });
      if (component)
        runAction(() => addReusable(library.find(i => i.id === component), position));
      const inline = e.dataTransfer.getData('application/bincovering-inline');
      if (inline) runAction(() => addInline(inline, position));
    };
    viewport.onkeydown = e => {
      if ([
          'INPUT',
          'TEXTAREA',
          'SELECT'
        ].includes(e.target.tagName))
        return;
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') {
        e.preventDefault();
        restoreHistory(e.shiftKey ? redo : undo, e.shiftKey ? undo : redo);
        return;
      }
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'y') {
        e.preventDefault();
        restoreHistory(redo, undo);
        return;
      }
      if (e.key === 'Escape') {
        pending = null;
        selection.clear();
        selected = null;
        selectedEdge = null;
        renderCanvas();
        renderInspector();
      }
      if (e.key === 'Delete' || e.key === 'Backspace') {
        e.preventDefault();
        runAction(() => selectedEdge ? removeEdge(selectedEdge) : selected && removeNode(selected));
      }
      const n = currentNode();
      if (n && owned && [
          'ArrowLeft',
          'ArrowRight',
          'ArrowUp',
          'ArrowDown'
        ].includes(e.key)) {
        e.preventDefault();
        const amount = e.shiftKey ? 30 : 10;
        mutate(() => {
          n.x += e.key === 'ArrowRight' ? amount : e.key === 'ArrowLeft' ? -amount : 0;
          n.y += e.key === 'ArrowDown' ? amount : e.key === 'ArrowUp' ? -amount : 0;
        });
      }
    };
    viewport.onpointerdown = e => {
      if (e.button !== 0 || e.target.closest('.graph-node,.graph-edge,.graph-edge-hit'))
        return;
      e.preventDefault();
      const x = e.clientX, y = e.clientY, original = {...pan};
      viewport.setPointerCapture?.(e.pointerId);
      viewport.classList.add('panning');
      const move = p => {
        pan = {x: original.x + p.clientX - x, y: original.y + p.clientY - y};
        applyViewportTransform();
      };
      const end = () => {
        document.removeEventListener('pointermove', move);
        document.removeEventListener('pointerup', end);
        document.removeEventListener('pointercancel', end);
        viewport.classList.remove('panning');
        recover();
      };
      document.addEventListener('pointermove', move);
      document.addEventListener('pointerup', end);
      document.addEventListener('pointercancel', end);
    };
    viewport.addEventListener('wheel', e => {
      e.preventDefault();
      if (e.ctrlKey || e.metaKey) zoomAt(zoom * Math.exp(-e.deltaY * 0.004), e.clientX, e.clientY);
      else {
        const unit = e.deltaMode === 1 ? 18 : e.deltaMode === 2 ? viewport.clientHeight : 1;
        pan.x -= e.deltaX * unit; pan.y -= e.deltaY * unit;
        applyViewportTransform(); recover();
      }
    }, {passive: false});
    $('#logout').onclick = event => {
      event.preventDefault();
      return runAction(async () => {
        await post('/api/logout');
        recoveryEnabled = false;
        for (let i = localStorage.length - 1; i >= 0; i--) {
          const key = localStorage.key(i);
          if (key?.startsWith(`bincovering:builder:${ session.user.id }:`))
            localStorage.removeItem(key);
        }
        location.href = '/login';
      });
    };
    window.addEventListener('beforeunload', () => {
      if (program)
        recover();
    });
  }
  async function start() {
    session = await api('/api/session');
    if (!session.user) {
      location.href = '/login?next=/builder';
      return;
    }
    $('#account-name').textContent = session.user.username;
    const response = await api('/api/builder/templates');
    templates = response.templates || [];
    if (!templates.length)
      throw Error('Builder starter templates are unavailable.');
    setup();
    await refreshLibrary();
    const query = new URLSearchParams(location.search), id = query.get('id');
    if (id) {
      const item = await api(libraryUrl(id) + (query.get('revision') ? '?revision=' + encodeURIComponent(query.get('revision')) : ''));
      load(item.draft, item.id, item.name, item.owned && !item.archived && !query.get('revision'));
      return;
    }
    let recovered;
    try {
      recovered = JSON.parse(localStorage.getItem(draftKey()) || 'null');
    } catch {
    }
    if (recovered?.program && (recovered.dirty || Object.keys(recovered.modeDrafts || {}).length)) {
      activeMode = recovered.activeMode || (recovered.program.kind === 'generator' ? 'generator' : 'algorithm');
      modeDrafts = recovered.modeDrafts || {};
      restoreWorkspace(recovered);
      if (dirty) feedback('Recovered your unsaved draft for this account. Save it to keep it in the library.');
    } else {
      load(starterGraph(templates[0]), null, templates[0].name);
      $('#builder-starter').value = templates[0].id;
    }
  }
  start().catch(error => feedback(error.message, true));
})();
