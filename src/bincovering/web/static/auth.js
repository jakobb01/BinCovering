(() => {
  'use strict';
  const busy = (button, value) => {
    button.disabled = value;
    if (value) button.setAttribute('aria-busy', 'true');
    else button.removeAttribute('aria-busy');
  };
  document.querySelectorAll('[data-account-entry]').forEach(form => {
    form.addEventListener('submit', () => {
      form.setAttribute('aria-busy', 'true');
      busy(form.querySelector('button[type="submit"]'), true);
    });
  });
  if (!document.getElementById('create-account')) return;
  const token = document.querySelector('meta[name="csrf-token"]').content;
  const feedback = document.getElementById('account-feedback');
  function report(message, error = false) {
    feedback.textContent = message;
    feedback.classList.toggle('feedback-error', error);
  }
  async function api(path, options = {}) {
    const response = await fetch(path, {...options, headers: {'Content-Type': 'application/json', 'X-CSRF-Token': token, ...options.headers}});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Request failed');
    return data;
  }
  function element(tag, text, className) {
    const item = document.createElement(tag); item.textContent = text;
    if (className) item.className = className;
    return item;
  }
  async function refresh(focus = null) {
    const [usersResult, runsResult] = await Promise.allSettled([api('/api/admin/users'), api('/api/runs')]);
    if (usersResult.status === 'rejected') throw usersResult.reason;
    const accounts = usersResult.value.users;
    document.getElementById('account-count').textContent = `${accounts.length} ${accounts.length === 1 ? 'account' : 'accounts'}`;
    const list = document.getElementById('account-list'); list.replaceChildren();
    accounts.forEach(user => {
      const row = element('article', '', 'account-row'); row.dataset.userId = user.id;
      const label = element('div');
      const title = element('h3', user.username); title.id = `account-${user.id}`;
      row.setAttribute('aria-labelledby', title.id);
      const meta = element('div', '', 'account-meta');
      meta.append(element('span', user.role === 'admin' ? 'Administrator' : 'Researcher', 'account-role'));
      meta.append(element('span', user.active ? 'Active' : 'Disabled', `account-status${user.active ? '' : ' account-status-disabled'}`));
      label.append(title, meta);
      const created = new Date(user.created_at);
      if (!Number.isNaN(created.getTime())) {
        const date = element('time', `Joined ${created.toLocaleDateString(undefined, {year: 'numeric', month: 'short', day: 'numeric'})}`, 'account-created');
        date.dateTime = user.created_at; label.append(date);
      }
      const actions = element('div', '', 'account-actions');
      const toggle = element('button', user.active ? 'Disable' : 'Enable', `button ${user.active ? 'button-danger' : 'button-accent-soft'}`); toggle.type = 'button'; toggle.dataset.action = 'toggle';
      toggle.setAttribute('aria-label', `${user.active ? 'Disable' : 'Enable'} ${user.username}`);
      toggle.addEventListener('click', async () => {
        busy(toggle, true);
        try {
          await api(`/api/admin/users/${user.id}`, {method:'PATCH', body:JSON.stringify({active:!user.active})});
          report(`${user.username} ${user.active ? 'disabled' : 'enabled'}.`);
          await refresh({id:user.id, action:'toggle'});
        } catch (error) { report(error.message, true); }
        finally { busy(toggle, false); }
      });
      const reset = element('button', 'Reset password', 'button button-accent-outline'); reset.type = 'button'; reset.dataset.action = 'reset';
      reset.setAttribute('aria-label', `Reset password for ${user.username}`); reset.setAttribute('aria-expanded', 'false');
      reset.addEventListener('click', () => {
        if (row.querySelector('form')) return;
        reset.setAttribute('aria-expanded', 'true');
        const form = element('form', '', 'account-form');
        const field = element('label', `New password for ${user.username}`);
        const input = document.createElement('input'); input.type='password'; input.minLength=12; input.maxLength=1024; input.required=true; input.autocomplete='new-password'; field.append(input);
        const save = element('button', 'Save password', 'button button-accent'); save.type='submit';
        const cancel = element('button', 'Cancel', 'button button-secondary'); cancel.type='button';
        const formActions = element('div', '', 'account-reset-actions'); formActions.append(save, cancel);
        form.append(field,formActions); row.append(form); input.focus();
        cancel.addEventListener('click', () => { form.remove(); reset.setAttribute('aria-expanded', 'false'); reset.focus(); });
        form.addEventListener('submit', async event => {
          event.preventDefault(); busy(save, true); cancel.disabled = true; form.setAttribute('aria-busy', 'true');
          try {
            await api(`/api/admin/users/${user.id}`, {method:'PATCH',body:JSON.stringify({password:input.value})});
            input.value = ''; report(`Password changed for ${user.username}.`); await refresh({id:user.id, action:'reset'});
          } catch(error) { report(error.message, true); }
          finally { busy(save, false); cancel.disabled = false; form.removeAttribute('aria-busy'); }
        });
      });
      actions.append(toggle,reset); row.append(label,actions); list.append(row);
    });
    const owner = document.getElementById('reassign-owner'); const selectedOwner = owner.value; owner.replaceChildren();
    accounts.filter(user=>user.active).forEach(user=>owner.append(new Option(user.username,user.id)));
    if (accounts.some(user => user.active && user.id === selectedOwner)) owner.value = selectedOwner;
    const run = document.getElementById('reassign-run'); const selectedRun = run.value; run.replaceChildren();
    const runs = runsResult.status === 'fulfilled' ? runsResult.value : [];
    runs.forEach(item=>run.append(new Option(`${item.name} · ${item.id}`,item.id)));
    if (!runs.length) run.append(new Option('No saved experiments',''));
    else if (runs.some(item => item.id === selectedRun)) run.value = selectedRun;
    document.querySelector('#reassign-experiment button[type="submit"]').disabled = !runs.length || !owner.options.length;
    if (runsResult.status === 'rejected') report(runsResult.reason.message, true);
    if (focus) list.querySelector(`[data-user-id="${focus.id}"] [data-action="${focus.action}"]`)?.focus();
  }
  function handle(formId, path, message) {
    const form = document.getElementById(formId);
    form.addEventListener('submit', async event => {
      event.preventDefault(); const button=form.querySelector('button[type="submit"]'); busy(button,true); form.setAttribute('aria-busy','true');
      try { await api(path,{method:'POST',body:JSON.stringify(Object.fromEntries(new FormData(form)))}); report(message); if(formId==='create-account') form.reset(); await refresh(); }
      catch(error) { report(error.message,true); }
      finally { busy(button,false); form.removeAttribute('aria-busy'); }
    });
  }
  handle('create-account','/api/admin/users','Account created.');
  handle('reassign-experiment','/api/admin/reassign','Experiment reassigned. Its research records are unchanged.');
  document.getElementById('account-logout').addEventListener('submit', async event => {
    event.preventDefault(); const form = event.currentTarget; const button = form.querySelector('button'); busy(button,true);
    try {
      await api('/api/logout', {method:'POST'});
      try {
        for (let i = localStorage.length - 1; i >= 0; i--) {
          const key = localStorage.key(i);
          if (key?.startsWith(`bincovering:builder:${form.dataset.userId}:`)) localStorage.removeItem(key);
        }
      } catch { /* Browser storage may be unavailable. */ }
      location.href = '/login';
    } catch(error) { report(error.message,true); busy(button,false); }
  });
  refresh().catch(error=>report(error.message,true));
})();
