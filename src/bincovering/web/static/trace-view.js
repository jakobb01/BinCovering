/* Read-only playback of backend evidence, shared by Verify and saved results. */
(() => {
  const el = (tag, cls, text) => {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined) node.textContent = text;
    return node;
  };
  const fmt = value => typeof value === 'number' ? String(value) : JSON.stringify(value);
  const svgEl = (tag, attrs) => {
    const node = document.createElementNS('http://www.w3.org/2000/svg', tag);
    for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
    return node;
  };
  const samePath = (left, right) => JSON.stringify(left || []) === JSON.stringify(right || []);
  let markerSequence = 0;

  function graphContext(graph, event) {
    let shown = graph;
    const path = [], names = [graph.name || (graph.kind === 'generator' ? 'Item generator' : graph.kind === 'component' ? 'Reusable component' : 'Algorithm')];
    for (const instance of event?.call_path || []) {
      const caller = shown.nodes?.find(node => node.id === instance);
      const reference = shown.components?.[caller?.config?.component_id];
      const nested = reference?.graph || reference;
      if (!nested?.nodes) break;
      names.push((caller.label || instance) + (reference.revision ? ' · revision ' + reference.revision : ''));
      path.push(instance);
      shown = nested;
    }
    const entries = shown.entries || {};
    let phase = event?.phase;
    // Component events retain their caller's lifecycle phase in the trace. The
    // frozen inner graph has a process entry, so map the view without altering it.
    if (!entries[phase]) {
      if (shown.kind === 'component' || (entries.process && Object.keys(entries).length === 1)) phase = 'process';
      else phase = shown.nodes?.find(node => node.id === event?.node_id)?.phase || Object.keys(entries)[0];
    }
    const reachable = new Set(), pending = entries[phase] ? [entries[phase]] : [];
    while (pending.length) {
      const id = pending.pop();
      if (reachable.has(id)) continue;
      reachable.add(id);
      for (const edge of shown.edges || []) {
        if (edge.source === id && edge.kind !== 'data') pending.push(edge.target);
      }
    }
    const nodes = shown.nodes.filter(node => reachable.has(node.id) || !node.phase || node.phase === phase);
    const labels = {start: 'Start', next: shown.kind === 'generator' ? 'Generate next' : 'Next item', process: shown.kind === 'component' ? 'Component' : 'Process sequence', stop: 'Stop'};
    let label = names.join(' → ') + ' / ' + (labels[phase] || phase || 'Graph');
    if (event?.phase === 'fixture') label += ' · recorded fixture setup';
    return {graph: shown, path, phase, nodes, label, key: JSON.stringify([path, phase])};
  }

  function mountGraph(parent, graph, onNode, onInteract) {
    const panel = el('section', 'trace-graph-panel');
    panel.setAttribute('aria-label', 'Recorded graph');
    const tools = el('div', 'trace-graph-tools'), contextLabel = el('p', 'trace-graph-context');
    tools.append(contextLabel);
    const makeButton = (label, text, action) => {
      const button = el('button', 'button button-ghost', text);
      button.type = 'button'; button.setAttribute('aria-label', label); button.onclick = action;
      tools.append(button); return button;
    };
    makeButton('Fit trace graph', 'Fit', () => { onInteract(); fit(active); });
    makeButton('Zoom out trace graph', '−', () => { onInteract(); zoomAt(0.8); });
    makeButton('Zoom in trace graph', '+', () => { onInteract(); zoomAt(1.25); });
    const scaleLabel = el('span', 'trace-graph-scale'); tools.append(scaleLabel);
    const viewport = el('div', 'trace-graph-mini');
    viewport.tabIndex = 0; viewport.setAttribute('role', 'region');
    viewport.setAttribute('aria-label', 'Frozen trace graph. Drag the background or use arrow keys to pan. Control or Command wheel zooms.');
    panel.append(tools, viewport); parent.append(panel);
    const scenes = new Map();
    let active = null, drag = null, destroyed = false;

    function transform(scene) {
      if (!scene || destroyed) return;
      scene.world.style.transform = `translate(${scene.view.x}px, ${scene.view.y}px) scale(${scene.view.scale})`;
      if (scene === active) scaleLabel.textContent = Math.round(scene.view.scale * 100) + '%';
    }
    function measure(scene) {
      const bounds = {left: Infinity, top: Infinity, right: -Infinity, bottom: -Infinity};
      for (const node of scene.context.nodes) {
        const position = scene.coords.get(node.id), card = scene.cards.get(node.id);
        bounds.left = Math.min(bounds.left, position.x);
        bounds.top = Math.min(bounds.top, position.y);
        bounds.right = Math.max(bounds.right, position.x + (card.offsetWidth || 190));
        bounds.bottom = Math.max(bounds.bottom, position.y + (card.offsetHeight || 100));
      }
      if (!scene.context.nodes.length) Object.assign(bounds, {left: 0, top: 0, right: 190, bottom: 100});
      // Include connection curves and focus outlines in the initial fit.
      bounds.left -= 35; bounds.top -= 35; bounds.right += 35; bounds.bottom += 40;
      scene.bounds = bounds;
      scene.world.style.width = Math.max(1, bounds.right) + 'px';
      scene.world.style.height = Math.max(1, bounds.bottom) + 'px';
      scene.svg.setAttribute('width', Math.max(1, bounds.right));
      scene.svg.setAttribute('height', Math.max(1, bounds.bottom));
      for (const [id, line] of scene.edges) {
        const edge = scene.edgeDefinitions.get(id), a = scene.coords.get(edge.source), b = scene.coords.get(edge.target);
        const source = scene.cards.get(edge.source), target = scene.cards.get(edge.target);
        const sourceWidth = source.offsetWidth || 190, targetWidth = target.offsetWidth || 190;
        const sourceHeight = source.offsetHeight || 100, targetHeight = target.offsetHeight || 100;
        const horizontal = b.x >= a.x + sourceWidth;
        const x = horizontal ? a.x + sourceWidth : a.x + sourceWidth / 2;
        const y = a.y + sourceHeight * (horizontal ? 0.5 : 1);
        const x2 = horizontal ? b.x : b.x + targetWidth / 2;
        const y2 = b.y + (horizontal ? targetHeight * 0.5 : 0);
        line.setAttribute('d', horizontal ? `M${x},${y} C${x + 35},${y} ${x2 - 35},${y2} ${x2},${y2}` : `M${x},${y} C${x},${y + 35} ${x2},${y2 - 35} ${x2},${y2}`);
        const label = scene.edgeLabels.get(id);
        if (label) { label.setAttribute('x', (x + x2) / 2); label.setAttribute('y', (y + y2) / 2 - 8); }
      }
    }
    function fit(scene) {
      if (!scene || !viewport.clientWidth || !viewport.clientHeight) return;
      measure(scene);
      const width = viewport.clientWidth, height = viewport.clientHeight, bounds = scene.bounds;
      const scale = Math.max(0.12, Math.min(1, (width - 32) / (bounds.right - bounds.left), (height - 32) / (bounds.bottom - bounds.top)));
      scene.view = {scale, x: (width - (bounds.right + bounds.left) * scale) / 2, y: (height - (bounds.bottom + bounds.top) * scale) / 2};
      scene.initialized = true; scene.autoFit = true; scene.viewportSize = {width, height};
      transform(scene);
    }
    function resize() {
      if (!active || !viewport.clientWidth || !viewport.clientHeight) return;
      if (!active.initialized) { fit(active); return; }
      const previous = active.viewportSize || {width: viewport.clientWidth, height: viewport.clientHeight};
      if (previous.width === viewport.clientWidth && previous.height === viewport.clientHeight) return;
      if (active.autoFit) { fit(active); return; }
      active.view.x += (viewport.clientWidth - previous.width) / 2;
      active.view.y += (viewport.clientHeight - previous.height) / 2;
      active.viewportSize = {width: viewport.clientWidth, height: viewport.clientHeight};
      measure(active); transform(active);
    }
    function zoomAt(factor, x = viewport.clientWidth / 2, y = viewport.clientHeight / 2) {
      if (!active) return;
      const old = active.view.scale, scale = Math.max(0.12, Math.min(3, old * factor));
      active.view.x = x - (x - active.view.x) * scale / old;
      active.view.y = y - (y - active.view.y) * scale / old;
      active.view.scale = scale; active.autoFit = false; transform(active);
    }
    function pan(x, y) {
      if (!active) return;
      active.view.x += x; active.view.y += y; active.autoFit = false; transform(active);
    }
    function build(context) {
      const world = el('div', 'trace-graph-world'), svg = svgEl('svg', {class: 'graph-edges', 'aria-hidden': 'true'});
      const markerId = 'trace-arrow-' + (++markerSequence), defs = svgEl('defs', {});
      const marker = svgEl('marker', {id: markerId, viewBox: '0 0 10 10', refX: 9, refY: 5, markerWidth: 6, markerHeight: 6, orient: 'auto-start-reverse'});
      marker.append(svgEl('path', {d: 'M0 0 L10 5 L0 10 z', fill: 'var(--border-strong)'})); defs.append(marker); svg.append(defs); world.append(svg);
      const cards = new Map(), edges = new Map(), edgeLabels = new Map(), edgeDefinitions = new Map();
      const coords = new Map(context.nodes.map((node, index) => [node.id, {x: Number.isFinite(node.x) ? node.x : (index % 3) * 235 + 25, y: Number.isFinite(node.y) ? node.y : Math.floor(index / 3) * 150 + 25}]));
      for (const edge of context.graph.edges || []) {
        if (!coords.has(edge.source) || !coords.has(edge.target)) continue;
        const line = svgEl('path', {class: 'graph-edge' + (edge.kind === 'data' ? ' data' : ''), 'marker-end': 'url(#' + markerId + ')'});
        line.dataset.edge = edge.id; svg.append(line); edges.set(edge.id, line); edgeDefinitions.set(edge.id, edge);
        const port = edge.port || edge.source_port;
        if (['yes', 'no', 'body'].includes(port)) {
          const label = svgEl('text', {class: 'graph-edge-label'}); label.textContent = port;
          svg.append(label); edgeLabels.set(edge.id, label);
        }
      }
      for (const node of context.nodes) {
        const card = el('div', 'graph-node'), position = coords.get(node.id);
        card.dataset.id = node.id; card.dataset.type = node.type;
        card.style.left = position.x + 'px'; card.style.top = position.y + 'px';
        const title = el('button', 'node-title', node.label || node.type);
        title.type = 'button'; title.setAttribute('aria-label', 'Show recorded events for ' + (node.label || node.type));
        title.onclick = () => { onInteract(); onNode(node.id, context.path); };
        card.append(title, el('p', 'node-description', node.type === 'custom' ? node.config?.source || '' : node.type));
        world.append(card); cards.set(node.id, card);
      }
      if (!context.nodes.length) world.append(el('p', 'field-help', 'No matching phase graph is available in this recorded package.'));
      return {context, world, svg, cards, edges, edgeLabels, edgeDefinitions, coords, view: {x: 0, y: 0, scale: 1}, initialized: false, autoFit: true};
    }
    function update(event, visited) {
      if (destroyed) return;
      const context = graphContext(graph, event);
      if (!active || active.context.key !== context.key) {
        releaseDrag();
        if (!scenes.has(context.key)) scenes.set(context.key, build(context));
        active = scenes.get(context.key);
        // Reattach the frozen context rather than reconstructing it on return.
        viewport.replaceChildren(active.world);
        contextLabel.textContent = context.label;
        if (!active.initialized) fit(active);
        else { resize(); transform(active); }
        if (scenes.size > 32) {
          const first = [...scenes.keys()].find(key => key !== context.key);
          if (first) scenes.delete(first);
        }
      } else {
        // Fixture/caller labels can change even when the effective component
        // process graph is unchanged. This has no effect on its transform.
        contextLabel.textContent = context.label;
      }
      const currentPathMatches = samePath(event?.call_path, active.context.path);
      for (const [id, card] of active.cards) {
        card.classList.toggle('executing', currentPathMatches && event?.node_id === id);
        card.classList.toggle('visited', visited.has(JSON.stringify([active.context.path, id])));
      }
      for (const [id, line] of active.edges) line.classList.toggle('taken', currentPathMatches && event?.edge_id === id);
    }
    function releaseDrag() {
      if (drag && viewport.hasPointerCapture?.(drag.id)) viewport.releasePointerCapture(drag.id);
      drag = null;
      viewport.classList.remove('panning');
    }
    const pointerDown = event => {
      if (event.button !== 0 || !active || event.target.closest('.graph-node,button')) return;
      event.preventDefault(); onInteract();
      drag = {id: event.pointerId, x: event.clientX, y: event.clientY};
      viewport.classList.add('panning');
      viewport.setPointerCapture?.(event.pointerId);
    };
    const pointerMove = event => {
      if (!drag || event.pointerId !== drag.id) return;
      pan(event.clientX - drag.x, event.clientY - drag.y);
      drag.x = event.clientX; drag.y = event.clientY;
    };
    const pointerEnd = event => { if (drag?.id === event.pointerId) releaseDrag(); };
    const wheel = event => {
      if (!active) return;
      event.preventDefault(); onInteract();
      const factor = event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? viewport.clientHeight : 1;
      if (event.ctrlKey || event.metaKey) {
        const rect = viewport.getBoundingClientRect();
        zoomAt(Math.exp(-event.deltaY * factor * 0.002), event.clientX - rect.left, event.clientY - rect.top);
      } else pan(-(event.shiftKey && !event.deltaX ? event.deltaY : event.deltaX) * factor, event.shiftKey && !event.deltaX ? 0 : -event.deltaY * factor);
    };
    const keyDown = event => {
      if (!active || !['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(event.key)) return;
      event.preventDefault(); onInteract();
      const amount = event.shiftKey ? 100 : 40;
      pan(event.key === 'ArrowLeft' ? amount : event.key === 'ArrowRight' ? -amount : 0, event.key === 'ArrowUp' ? amount : event.key === 'ArrowDown' ? -amount : 0);
    };
    viewport.addEventListener('pointerdown', pointerDown); viewport.addEventListener('pointermove', pointerMove);
    viewport.addEventListener('pointerup', pointerEnd); viewport.addEventListener('pointercancel', pointerEnd);
    viewport.addEventListener('wheel', wheel, {passive: false}); viewport.addEventListener('keydown', keyDown);
    const observer = typeof ResizeObserver === 'function' ? new ResizeObserver(resize) : null;
    observer?.observe(viewport);
    if (!observer) window.addEventListener('resize', resize);
    return {
      update,
      destroy() {
        destroyed = true; releaseDrag(); observer?.disconnect();
        if (!observer) window.removeEventListener('resize', resize);
        viewport.removeEventListener('pointerdown', pointerDown); viewport.removeEventListener('pointermove', pointerMove);
        viewport.removeEventListener('pointerup', pointerEnd); viewport.removeEventListener('pointercancel', pointerEnd);
        viewport.removeEventListener('wheel', wheel); viewport.removeEventListener('keydown', keyDown);
        for (const scene of scenes.values()) for (const card of scene.cards.values()) card.querySelector('button').onclick = null;
        for (const button of tools.querySelectorAll('button')) button.onclick = null;
        scenes.clear(); active = null;
      }
    };
  }

  function mount(target, payload = {}, options = {}) {
    target._traceDestroy?.(); target.replaceChildren();
    const trace = payload.trace || payload;
    let raw = Array.isArray(trace) ? trace : trace.events || [];
    if (!Array.isArray(raw) && typeof raw === 'object') raw = Object.entries(raw).map(([item_index, covered_bins]) => ({item_index: Number(item_index), covered_bins, label: 'Recorded covered count'}));
    if (!Array.isArray(raw)) raw = [];
    // Historical traces expose only what was recorded, without guessed graph or
    // bin state. Their original item indices and measured counts remain readable.
    const events = raw.map((event, index) => Array.isArray(event) ? {step: index, item_index: event[0], covered_bins: event[1], label: 'Recorded covered count'} : {step: index, ...event, item_index: event.item_index ?? event.index});
    const graph = payload.graph || options.graph || null;
    let index = -1, timer = null, filter = null, destroyed = false;
    const evidence = graph ? ' · exact frozen graph' : ' · graph and bin history were not recorded';
    const total = Number.isInteger(trace.total_events) && trace.total_events >= events.length ? trace.total_events : null;
    const count = trace.truncated && total !== null ? `${events.length} of ${total} recorded events` : `${events.length} recorded events`;
    const notice = el('p', 'field-help', trace.truncated ? `${count} · truncated at the recorded capture limit${evidence}.` : events.length ? count + evidence + '.' : 'No trace was recorded for this execution.');
    target.append(notice);
    const controls = el('div', 'trace-playback'), position = el('span', 'trace-position');
    const btn = (text, action) => {
      const button = el('button', 'button button-secondary', text); button.type = 'button';
      button.onclick = action; controls.append(button); return button;
    };
    const pause = () => { clearInterval(timer); timer = null; play.textContent = 'Play'; };
    const prev = btn('Previous', () => { pause(); show(index - 1); });
    const next = btn('Step operation', () => { pause(); show(index + 1); });
    const nextItem = btn('Next item', () => {
      pause(); const current = events[index]?.item_index;
      let nextIndex = index + 1;
      while (nextIndex < events.length && events[nextIndex].item_index === current) nextIndex++;
      show(nextIndex);
    });
    const play = btn('Play', () => {
      if (timer) { pause(); return; }
      if (index >= events.length - 1) show(-1);
      play.textContent = 'Pause';
      timer = setInterval(() => { if (index >= events.length - 1) pause(); else show(index + 1); }, 650);
    });
    btn('Reset', () => { pause(); show(-1); });
    const clearFilter = btn('Clear node filter', () => { filter = null; clearFilter.hidden = true; updateFilter(); });
    clearFilter.hidden = true; controls.append(position); target.append(controls);
    let graphViewer;
    if (graph && options.showGraph !== false) graphViewer = mountGraph(target, graph, (id, path) => controller.filterNode(id, path), pause);
    const cols = el('div', 'trace-columns'), timeline = el('ol', 'trace-events'), states = el('div', 'trace-states');
    timeline.setAttribute('aria-label', 'Recorded execution timeline'); timeline.tabIndex = 0;
    cols.append(timeline, states); target.append(cols);
    const stateContext = el('p', 'field-help trace-state-context'), currentItem = el('div', 'trace-current-item');
    const vars = el('div', 'trace-variable-list'), noVars = el('p', 'field-help'), bins = el('div', 'trace-bin-list'), noBins = el('p', 'field-help');
    const snapshotNotice = el('p', 'field-help', 'State snapshot truncated at its capture limit.');
    states.append(stateContext, el('h3', '', 'Current item and measured state'), currentItem, vars, noVars, el('h3', '', 'Bins and item placements'), bins, noBins, snapshotNotice);
    const output = el('pre', 'trace-output'); target.append(output);
    const eventRows = [], variableNodes = new Map(), binNodes = new Map();
    const matches = event => !filter || (event.node_id === filter.id && (!filter.path || samePath(event.call_path, filter.path))) || (event.call_path || []).some((id, at) => id === filter.id && (!filter.path || samePath(event.call_path.slice(0, at), filter.path)));
    for (const [at, event] of events.entries()) {
      const row = el('li'), button = el('button', 'trace-event'); button.type = 'button'; button.dataset.event = String(at);
      const operation = typeof event.operation === 'object' ? JSON.stringify(event.operation) : event.operation;
      button.textContent = `${event.step ?? at} · ${event.phase || 'item'}${event.item_index != null ? ' / item ' + event.item_index : ''} · ${event.label || operation || event.node_type || 'Recorded event'}${event.branch != null ? ' → ' + event.branch : ''}${event.line ? ' · line ' + event.line : ''}`;
      button.setAttribute('aria-current', 'false'); button.onclick = () => { pause(); show(at); };
      row.append(button); timeline.append(row); eventRows.push({row, button});
    }
    function updateFilter() {
      for (const [at, row] of eventRows.entries()) row.row.hidden = !matches(events[at]);
      const focused = document.activeElement;
      if (timeline.contains(focused) && focused?.classList.contains('trace-event') && focused.closest('li').hidden) clearFilter.focus({preventScroll: true});
    }
    function scrollTimeline() {
      const row = eventRows[index];
      if (!row || row.row.hidden || !timeline.clientHeight) return;
      const frame = timeline.getBoundingClientRect(), current = row.button.getBoundingClientRect();
      if (current.top < frame.top) timeline.scrollTop += current.top - frame.top;
      else if (current.bottom > frame.bottom) timeline.scrollTop += current.bottom - frame.bottom;
    }
    function updateVariables(recorded) {
      const names = new Set(Object.keys(recorded || {}));
      for (const [name, element] of variableNodes) if (!names.has(name)) element.remove();
      for (const [name, value] of Object.entries(recorded || {})) {
        if (!variableNodes.has(name)) variableNodes.set(name, el('span', 'trace-variable'));
        const element = variableNodes.get(name); element.textContent = `${name} = ${fmt(value)}`;
        if (element.parentNode !== vars) vars.append(element);
      }
      noVars.textContent = 'No state snapshot recorded for this event.'; noVars.hidden = names.size > 0;
    }
    function updateBins(recorded, event) {
      const ids = new Set((recorded || []).map(bin => String(bin.id)));
      for (const [id, record] of binNodes) if (!ids.has(id)) record.card.remove();
      for (const bin of recorded || []) {
        const id = String(bin.id);
        if (!binNodes.has(id)) {
          const card = el('div', 'trace-bin'), title = el('div'), load = el('div'), meter = el('div', 'trace-bin-meter'), fill = el('span'), items = el('div');
          meter.append(fill); card.append(title, load, meter, items); binNodes.set(id, {card, title, load, fill, items});
        }
        const record = binNodes.get(id); record.card.classList.toggle('closed', bin.status === 'covered'); record.card.classList.toggle('selected', event?.bin_id === bin.id);
        record.title.textContent = `Bin ${bin.id} · ${bin.status || 'active'}`; record.load.textContent = `load ${fmt(bin.load)}`;
        record.fill.style.width = Math.min(100, Math.max(0, Number(bin.load) / (options.threshold || payload.metadata?.threshold || graph?.threshold || 1) * 100)) + '%';
        record.items.textContent = `items ${(bin.item_indices || []).join(', ') || '—'}`;
        if (record.card.parentNode !== bins) bins.append(record.card);
      }
      noBins.textContent = Array.isArray(recorded) ? 'No bins in this recorded snapshot.' : 'No bin snapshot recorded for this event.';
      noBins.hidden = ids.size > 0;
    }
    function show(value) {
      if (destroyed) return;
      const previous = eventRows[index];
      if (previous) { previous.button.classList.remove('active'); previous.button.setAttribute('aria-current', 'false'); }
      index = Math.max(-1, Math.min(events.length - 1, value));
      const event = events[index], active = eventRows[index];
      if (active) { active.button.classList.add('active'); active.button.setAttribute('aria-current', 'step'); }
      position.textContent = index < 0 ? 'Before Start' : `Event ${index + 1} / ${events.length}`;
      prev.disabled = index < 0; next.disabled = index >= events.length - 1; nextItem.disabled = next.disabled; play.disabled = !events.length;
      stateContext.textContent = graph && event ? graphContext(graph, event).label : event?.phase || 'Recorded state';
      currentItem.textContent = event ? `Item ${event.item_index ?? '—'} · size ${event.item != null ? fmt(event.item) : '—'} · covered ${event.covered_bins ?? '—'}${event.operation ? ' · ' + (typeof event.operation === 'object' ? JSON.stringify(event.operation) : event.operation) : ''}` : 'Waiting for Start';
      updateVariables(event?.state); updateBins(event?.bins, event); snapshotNotice.hidden = !event?.snapshot_truncated;
      output.textContent = payload.error ? `${payload.error.message || payload.error}${payload.error.node_id ? '\nNode: ' + payload.error.node_id : ''}${payload.error.line ? ' · line ' + payload.error.line : ''}` : event?.output?.length ? 'Recorded output: ' + JSON.stringify(event.output) : payload.result ? 'Execution result: ' + JSON.stringify(payload.result, null, 2) : 'No output recorded for this event.';
      // Output remains mounted, so the playback controls and graph never change
      // their document position when a later event acquires output or an error.
      const recorded = events.slice(0, index + 1);
      graphViewer?.update(event, new Set(recorded.map(item => JSON.stringify([item.call_path || [], item.node_id]))));
      options.onEvent?.(event, new Set(recorded.map(item => item.call_path?.[0] || item.node_id)));
      scrollTimeline();
    }
    const controller = {
      show,
      filterNode(id, path) {
        if (destroyed) return;
        filter = id ? {id, path} : null; clearFilter.hidden = !id; updateFilter();
        const first = events.findIndex(matches); if (first >= 0) show(first);
      },
      destroy() {
        if (destroyed) return;
        pause(); destroyed = true; graphViewer?.destroy();
        for (const row of eventRows) row.button.onclick = null;
        for (const button of controls.querySelectorAll('button')) button.onclick = null;
        options.onEvent?.(null, new Set());
        if (target._traceDestroy === controller.destroy) delete target._traceDestroy;
      }
    };
    target._traceDestroy = controller.destroy; show(events.length ? 0 : -1); return controller;
  }
  window.BinCoveringTrace = {mount};
})();
