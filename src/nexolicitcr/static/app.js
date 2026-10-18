'use strict';
// No external scripts, HTML injection or inline handlers. Forms work without JS.
const form = document.querySelector('[data-job-form]');
if (form) form.addEventListener('submit', async event => {
  event.preventDefault();
  const button = form.querySelector('button[type="submit"],button');
  const message = form.querySelector('[data-form-message]');
  button.disabled = true;
  message.textContent = 'Guardando tu consulta…';
  try {
    const response = await fetch(form.action, {method:'POST', body:new FormData(form), headers:{Accept:'application/json'}, credentials:'same-origin'});
    if (response.redirected && new URL(response.url).pathname === '/login') { location.assign('/login'); return; }
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'No se pudo guardar el trabajo.');
    location.assign(data.url);
  } catch (error) {
    message.textContent = error.message || 'No hay conexión. Podés reintentar sin duplicar el trabajo.';
    button.disabled = false;
  }
});
const job = document.querySelector('[data-job-id]');
if (job) {
  let failures = 0;
  const statuses = {queued:'En cola', running:'Consultando', retry_wait:'Reintento pendiente', succeeded:'Completada', failed:'No completada', canceled:'Cancelada'};
  const jobMessage = data => {
    if (data.status === 'succeeded') return 'La consulta terminó. Podés revisar las coincidencias en tu radar.';
    if (data.status === 'canceled') return 'La consulta se canceló.';
    if (data.cancel_requested) return 'Cancelación solicitada. Se aplicará al terminar el paso actual.';
    if (data.status === 'queued' && data.source_pause_until) return 'SICOP está limitando las consultas. Tu trabajo está guardado y esperará a que termine la pausa.';
    if (data.status === 'queued') return 'Tu consulta está en cola. Se iniciará cuando el sistema esté disponible.';
    if (data.status === 'running') return 'Estamos consultando SICOP. Podés salir de esta pantalla; el progreso se conserva.';
    if (data.error_code === 'SOURCE_RATE_LIMITED') return data.status === 'retry_wait' ? 'SICOP pidió reducir la frecuencia. La consulta se pausó y se retomará automáticamente.' : 'SICOP limitó las consultas. Se agotaron los intentos; podés volver a consultar más tarde.';
    if (data.status === 'retry_wait') return 'La consulta se interrumpió. El sistema volverá a intentarlo automáticamente.';
    if (data.error_code === 'DEPENDENCY_UNAVAILABLE') return 'La consulta no pudo completarse por una interrupción de conexión. Se agotaron los intentos automáticos.';
    if (data.error_code === 'SOURCE_PARTIAL') return 'Consulta parcial: algunos concursos no pudieron actualizarse. Se agotaron los intentos automáticos.';
    return 'La consulta terminó sin completarse.';
  };
  const showRetry = data => {
    const notice = job.querySelector('[data-job-retry]');
    const time = job.querySelector('[data-job-retry-time]');
    const waiting = data.status === 'retry_wait' || data.status === 'queued' && (data.source_pause_until || new Date(data.next_attempt_at).getTime() > Date.now());
    notice.hidden = !waiting || !(data.next_attempt_at || data.source_pause_until);
    if (!notice.hidden) {
      const dates = [data.next_attempt_at, data.source_pause_until].filter(Boolean).map(value => new Date(value));
      const date = new Date(Math.max(...dates.map(value => value.getTime())));
      if (!Number.isNaN(date.getTime())) {
        time.dateTime = date.toISOString();
        time.textContent = new Intl.DateTimeFormat('es-CR', {hour:'2-digit', minute:'2-digit', timeZoneName:'short'}).format(date);
      }
    }
  };
  const initialTime = job.querySelector('[data-job-retry-time]');
  if (initialTime?.dateTime && !job.querySelector('[data-job-retry]').hidden) showRetry({status:'retry_wait', next_attempt_at:initialTime.dateTime});
  const poll = async () => {
    try {
      const response = await fetch(`/jobs/${encodeURIComponent(job.dataset.jobId)}`, {headers:{Accept:'application/json'}, credentials:'same-origin'});
      if (response.redirected) { location.assign('/login'); return; }
      if (!response.ok) throw new Error('No se pudo consultar el progreso.');
      const data = await response.json();
      const status = job.querySelector('[data-job-status]');
      showRetry(data);
      job.querySelector('[data-source-pause]').hidden = !data.source_pause_until;
      const pending = job.querySelector('[data-job-pending]');
      pending.hidden = !data.pending_count;
      job.querySelector('[data-job-pending-count]').textContent = data.pending_count || 0;
      job.querySelector('[data-resume-form]').hidden = !['failed','canceled'].includes(data.status);
      status.textContent = statuses[data.status] || 'Estado pendiente';
      status.className = `badge ${Object.hasOwn(statuses, data.status) ? data.status : ''}`;
      job.querySelector('[data-job-progress]').textContent = data.progress;
      job.querySelector('[data-job-attempt]').textContent = data.attempt;
      job.querySelector('[data-job-message]').textContent = jobMessage(data);
      job.querySelector('[data-job-retained]').textContent = data.progress > 0 ? `Los ${data.progress} concursos procesados se conservan en tu espacio. Revisá sus coincidencias en el radar.` : 'Los concursos guardados anteriormente se conservan en tu espacio.';
      failures = 0;
      if (['succeeded','failed','canceled'].includes(data.status)) { job.querySelector('[data-cancel-form] button').disabled = true; return; }
    } catch (_) {
      failures++;
      job.querySelector('[data-job-message]').textContent = 'Conexión interrumpida. Reintentando; el trabajo permanece guardado.';
    }
    window.setTimeout(poll, Math.min(30000, 2500 * (failures + 1)));
  };
  poll();
}
document.querySelectorAll('[data-go-back]').forEach(button => button.addEventListener('click', () => {
  if (history.length > 1) history.back(); else location.assign('/company');
}));
// Native checkboxes remain usable without JavaScript, across all sectors.
const flow = document.querySelector('[data-specialty-flow]');
if (flow) {
  const sector = flow.querySelector('[data-sector]');
  const groups = [...flow.querySelectorAll('[data-sector-group]')];
  const choices = [...flow.querySelectorAll('[name=specialties]')];
  const panels = [...flow.querySelectorAll('[data-choice-panel]')];
  const activity = flow.querySelector('[name=activity]');
  const detail = flow.querySelector('[data-activity-details]');
  const next = flow.querySelector('[data-next-choice]');
  const previous = flow.querySelector('[data-previous-choice]');
  const all = flow.querySelector('[data-show-all]');
  let edited = false;
  activity.addEventListener('input', () => { edited = true; });
  const update = () => {
    const selected = choices.filter(choice => choice.checked);
    flow.querySelector('[data-selection-count]').textContent = `${selected.length} de 8 especialidades seleccionadas.`;
    choices.forEach(choice => {
      choice.disabled = !choice.checked && selected.length >= 8;
      choice.setCustomValidity('');
      if (choice.checked) choice.closest('details').open = true;
    });
    const custom = selected.some(choice => choice.value === 'other:custom');
    activity.required = custom;
    activity.minLength = custom ? 12 : 0;
    if (custom) detail.open = true;
  };
  const filter = () => {
    groups.forEach(group => {
      group.hidden = Boolean(sector.value && group.dataset.sectorGroup !== sector.value);
      if (!group.hidden && sector.value) group.open = true;
    });
    all.hidden = !sector.value;
  };
  const show = (name, focus = true) => {
    panels.forEach(panel => { panel.hidden = panel.dataset.choicePanel !== name; });
    flow.querySelector(`[data-choice-panel="${name}"] h1`)?.focus({preventScroll: !focus});
    document.querySelectorAll('[data-progress-step]').forEach(item => {
      const number = Number(item.dataset.progressStep);
      const current = name === 'sector' ? 2 : 3;
      item.classList.toggle('is-complete', number < current);
      if (number === current) item.setAttribute('aria-current', 'step'); else item.removeAttribute('aria-current');
      item.querySelector('span').textContent = number < current ? '✓' : String(number);
    });
  };
  sector.addEventListener('change', filter);
  all.hidden = false;
  all.addEventListener('click', () => { sector.value = ''; filter(); });
  choices.forEach(choice => choice.addEventListener('change', () => {
    if (!edited) activity.value = '';
    update();
  }));
  next.hidden = false; previous.hidden = false;
  next.addEventListener('click', () => { filter(); show('specialty'); });
  previous.addEventListener('click', () => show('sector'));
  flow.addEventListener('submit', event => {
    if (!panels[0].hidden) { event.preventDefault(); filter(); show('specialty'); return; }
    if (!choices.some(choice => choice.checked)) {
      event.preventDefault(); sector.value = ''; filter();
      choices[0].closest('details').open = true;
      choices[0].setCustomValidity('Elegí al menos una especialidad.');
      choices[0].reportValidity();
    }
  });
  flow.addEventListener('invalid', event => {
    show('specialty', false);
    const details = event.target.closest('details'); if (details) details.open = true;
  }, true);
  update(); filter(); show('sector', false);
}
// Service chips are an enhancement of the editable, server-validated text field.
const profileForm = document.querySelector('[data-confirm-profile]');
if (profileForm) {
  const terms = profileForm.querySelector('[name=services]');
  const picker = profileForm.querySelector('[data-service-picker]');
  const chips = picker.querySelector('.service-chips');
  const details = profileForm.querySelector('[data-services-details]');
  const rebuild = () => {
    const values = [...new Set(terms.value.split(',').map(term => term.trim()).filter(Boolean))];
    chips.replaceChildren();
    values.forEach(value => {
      const label = document.createElement('label');
      const checkbox = document.createElement('input');
      checkbox.type = 'checkbox'; checkbox.checked = true; checkbox.value = value;
      checkbox.dataset.serviceChoice = '';
      const span = document.createElement('span');
      const check = document.createElement('b'); check.setAttribute('aria-hidden', 'true'); check.textContent = '✓';
      span.append(check, document.createTextNode(value));
      label.append(checkbox, span); chips.append(label);
    });
    picker.hidden = !values.length;
  };
  rebuild();
  terms.addEventListener('input', rebuild);
  chips.addEventListener('change', () => {
    terms.value = Array.from(chips.querySelectorAll('input:checked')).map(input => input.value).join(', ');
    if (!terms.value) details.open = true;
  });
  profileForm.addEventListener('invalid', event => {
    const parent = event.target.closest('details'); if (parent) parent.open = true;
  }, true);
  profileForm.addEventListener('submit', async event => {
    if (event.submitter?.hasAttribute('formaction')) return;
    event.preventDefault();
    const button = event.submitter;
    const feedback = profileForm.querySelector('[data-save-feedback]');
    const count = terms.value.split(',').map(term => term.trim()).filter(Boolean).length;
    if (count < 1 || count > Number(profileForm.dataset.serviceLimit)) { details.open = true; feedback.textContent = `Elegí entre 1 y ${profileForm.dataset.serviceLimit} servicios para continuar.`; terms.focus(); return; }
    button.disabled = true; profileForm.setAttribute('aria-busy', 'true'); feedback.textContent = 'Guardando tu perfil…';
    try {
      const response = await fetch(profileForm.action, {method:'POST', body:new FormData(profileForm), headers:{Accept:'application/json'}, credentials:'same-origin'});
      if (response.redirected) { location.assign(response.url); return; }
      const result = await response.json();
      throw new Error(result.detail || 'No pudimos guardar el perfil. Revisá e intentá de nuevo.');
    } catch (error) {
      feedback.textContent = error.message || 'No hay conexión. Tus datos siguen aquí; podés reintentar.';
      button.disabled = false; profileForm.removeAttribute('aria-busy');
    }
  });
}
