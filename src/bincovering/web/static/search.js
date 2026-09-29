/* Saved-experiment search. Numeric filters use recorded values, never fuzzy edits. */
(function (root) {
  'use strict';

  const fieldAliases = {
    n: 'items', item: 'items', items: 'items', size: 'items',
    swap: 'swaps', swaps: 'swaps', trial: 'trials', trials: 'trials',
    seed: 'seed', worker: 'workers', workers: 'workers',
    order: 'ordering', ordering: 'ordering', shuffle: 'ordering',
    generator: 'generator', distribution: 'generator', dataset: 'dataset',
    dataset_mode: 'dataset', domain: 'domain', backend: 'backend',
    algorithm: 'algorithm', algo: 'algorithm', name: 'name', id: 'id', status: 'status',
    swap_mode: 'swap_mode', method: 'swap_mode',
  };
  const numericFields = new Set(['items', 'swaps', 'trials', 'seed', 'workers']);
  const orderLabels = {
    shuffle: ['shuffle', 'shuffled', 'random order', 'permutation'],
    swaps: ['swaps', 'pair swaps', 'partial mixing'],
    ascending: ['ascending', 'asc', 'increasing', 'sorted small first'],
    descending: ['descending', 'desc', 'decreasing', 'sorted large first'],
    original: ['original', 'unchanged', 'input order'],
  };
  const algorithmLabels = {
    dual_next_fit: ['dnf', 'dnf_1', 'dual next fit'],
    dual_harmonic: ['harmonic', 'dual harmonic'],
    throwbin_retire: ['throwbin', 'throw bin retirement'],
    throwbin_replace: ['throwbin_1', 'throwbin', 'throw bin replacement'],
    throwbin_fixed_active: ['throwbin_dnf', 'throwbin', 'throw bin fixed active'],
    adaptive_items: ['adaptivebin', 'adaptive items'],
    adaptive_covered: ['adaptivebincovered', 'adaptive covered'],
    advice_reserved: ['advice', 'advice reserved'],
    advice_reserved_k4: ['advice_k', 'advice reserved k4'],
  };

  function normalized(value) {
    return String(value).normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
  }

  function asNumber(value) {
    if (typeof value === 'number') return Number.isFinite(value) ? value : null;
    if (typeof value !== 'string') return null;
    const plain = /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?$/i;
    const grouped = /^[+-]?\d{1,3}(?:,\d{3})+(?:\.\d+)?$/;
    if (!plain.test(value) && !grouped.test(value)) return null;
    const result = Number(value.replaceAll(',', ''));
    return Number.isFinite(result) ? result : null;
  }

  function oneEdit(first, second) {
    if (Math.abs(first.length - second.length) > 1) return false;
    let a = 0, b = 0, edits = 0;
    while (a < first.length && b < second.length) {
      if (first[a] === second[b]) { a++; b++; continue; }
      if (++edits > 1) return false;
      if (first.length <= second.length) b++;
      if (first.length >= second.length) a++;
    }
    return edits + (a < first.length || b < second.length ? 1 : 0) <= 1;
  }

  function fuzzyText(term, text) {
    if (!term || text.includes(term)) return true;
    // Fuzzy matching belongs to words. Digits in names and parameters must not
    // make searches for 100 match 1000 or 1001.
    return text.split(/[^a-z0-9]+/).some(word => {
      let at = 0;
      for (const character of word) if (character === term[at]) at++;
      if (at === term.length) return true;
      return term.length >= 3 && !/\d/.test(term) && !/\d/.test(word) && oneEdit(term, word);
    });
  }

  function fieldsFor(run) {
    const fields = Object.create(null);
    function add(key, value) {
      if (value === undefined || value === null || typeof value === 'object') return;
      (fields[key] ||= []).push(normalized(value));
    }
    const cfg = run.config || {};
    for (const key of ['id', 'name', 'status']) add(key, run[key]);
    add('items', cfg.n);
    for (const key of ['trials', 'seed', 'workers', 'domain']) add(key, cfg[key]);
    add('dataset', cfg.dataset_mode);
    for (const label of orderLabels[cfg.ordering] || [cfg.ordering]) add('ordering', label);
    // Config files keep swap defaults even when another ordering is active.
    if (cfg.ordering === 'swaps') {
      add('swaps', cfg.swaps);
      add('swap_mode', cfg.swap_mode);
      if (cfg.swap_mode === 'with_replacement') add('swap_mode', 'with replacement repeated indices');
      if (cfg.swap_mode === 'distinct') add('swap_mode', 'distinct indices without replacement');
    }
    const generator = cfg.generator || {};
    add('generator', typeof generator === 'string' ? generator : generator.id);
    if (typeof generator === 'object') {
      // Include recorded source and relevant generator settings without indexing
      // inactive defaults such as a uniform generator's unused bins/path.
      if (generator.id === 'file') add('generator', generator.path);
      if (['uniform', 'big_items', 'optimal_uniform_legacy'].includes(generator.id)) {
        add('min', generator.min); add('max', generator.max);
      }
      if (generator.id === 'optimal_uniform_legacy') {
        add('bins', generator.bins); add('completion_fraction', generator.completion_fraction);
      }
    }
    for (const algorithm of cfg.algorithms || []) {
      if (typeof algorithm === 'string') { add('algorithm', algorithm); continue; }
      add('algorithm', algorithm.id);
      for (const label of algorithmLabels[algorithm.id] || []) add('algorithm', label);
      add('backend', algorithm.backend);
      if (algorithm.backend === 'cpp') add('backend', 'native c++');
      for (const [key, value] of Object.entries(algorithm.params || {})) add(key, value);
    }
    return fields;
  }

  function compare(actual, operation, wanted) {
    switch (operation) {
      case ':': case '=': return actual === wanted;
      case '>': return actual > wanted;
      case '>=': return actual >= wanted;
      case '<': return actual < wanted;
      case '<=': return actual <= wanted;
      default: return false;
    }
  }

  function matchesRun(query, run) {
    query = normalized(query || '').trim();
    if (!query) return true;
    // Accept "n >= 1000" as well as "n>=1000" and "items: 1000".
    query = query.replace(/([a-z][a-z0-9_]*)\s*([:<>]=?|=)\s*/g, '$1$2');
    const tokens = query.split(/\s+/);
    const fields = fieldsFor(run);
    const text = Object.entries(fields).flatMap(([key, values]) => [key, ...values]).join(' ');
    const numbers = Object.values(fields).flat().flatMap(value => {
      const exact = asNumber(value);
      // Preserve numeric execution-ID/name lookup, using complete numeric parts.
      return exact === null ? value.split(/[^0-9.]+/).map(asNumber).filter(v => v !== null) : [exact];
    });
    for (let index = 0; index < tokens.length; index++) {
      const token = tokens[index];
      let filter = token.match(/^([a-z][a-z0-9_]*)(:|>=|<=|=|>|<)(.*)$/);
      const field = fieldAliases[token] || token;
      if (!filter && numericFields.has(field) && index + 1 < tokens.length && asNumber(tokens[index + 1]) !== null) {
        filter = [null, field, ':', tokens[++index]];
      }
      if (filter) {
        const [, key, operation, value] = filter;
        const values = fields[fieldAliases[key] || key] || [];
        const numeric = asNumber(value);
        if (numeric !== null) {
          if (!values.some(actual => {
            const number = asNumber(actual);
            return number !== null && compare(number, operation, numeric);
          })) return false;
        } else {
          if (numericFields.has(fieldAliases[key] || key) || ![':', '='].includes(operation) || !value || !values.some(actual => fuzzyText(value, actual))) return false;
        }
      } else {
        const numeric = asNumber(token);
        if (numeric !== null ? !numbers.includes(numeric) : !fuzzyText(token, text)) return false;
      }
    }
    return true;
  }

  const api = {matchesRun};
  root.BinCoveringSearch = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(globalThis);
