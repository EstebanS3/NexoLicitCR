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
// Dependent native selects; without JS every labeled choice remains available.
const sectorSelect = document.querySelector('[data-sector]');
const specialtySelect = document.querySelector('[data-specialty]');
if (sectorSelect && specialtySelect) {
  const groups = Array.from(specialtySelect.querySelectorAll('optgroup')).map(group => group.cloneNode(true));
  const flow = document.querySelector('[data-specialty-flow]');
  const activity = document.querySelector('#activity');
  const activityDetails = document.querySelector('[data-activity-details]');
  let activityEdited = false;
  activity.addEventListener('input', () => { activityEdited = true; });
  const discardStaleDescription = () => { if (!activityEdited) activity.value = ''; };
  const updateActivity = () => {
    const custom = specialtySelect.value === 'custom';
    activity.required = custom;
    activity.minLength = custom ? 12 : 0;
    if (custom) activityDetails.open = true;
    document.querySelector('[data-activity-summary]').firstChild.textContent = custom ? 'Describí tu especialidad ' : 'Agregar un detalle ';
  };
  const updateSpecialties = (preserve) => {
    const selected = preserve ? specialtySelect.value : '';
    specialtySelect.replaceChildren(new Option('Elegí tu especialidad', ''));
    groups.filter(group => group.dataset.sectorGroup === sectorSelect.value).forEach(group => specialtySelect.append(group.cloneNode(true)));
    specialtySelect.value = selected;
    specialtySelect.disabled = !sectorSelect.value;
    const label = sectorSelect.selectedOptions[0]?.textContent || 'Tu especialidad';
    document.querySelector('[data-sector-caption]').textContent = label;
    document.querySelector('#specialty-help').textContent = sectorSelect.value ? 'Elegí lo que mejor describe tu actividad principal.' : 'Elegí primero un sector para ver sus especialidades.';
    updateActivity();
  };
  sectorSelect.addEventListener('change', () => { discardStaleDescription(); updateSpecialties(false); });
  specialtySelect.addEventListener('change', () => { discardStaleDescription(); updateActivity(); });
  updateSpecialties(true);
  if (flow) {
    const panels = Array.from(flow.querySelectorAll('[data-choice-panel]'));
    const next = flow.querySelector('[data-next-choice]');
    const previous = flow.querySelector('[data-previous-choice]');
    const show = (name, focus = true) => {
      panels.forEach(panel => { panel.hidden = panel.dataset.choicePanel !== name; });
      document.querySelectorAll('[data-progress-step]').forEach(item => {
        const number = Number(item.dataset.progressStep);
        const current = name === 'sector' ? 2 : 3;
        item.classList.toggle('is-complete', number < current);
        if (number === current) item.setAttribute('aria-current', 'step'); else item.removeAttribute('aria-current');
        item.querySelector('span').textContent = number < current ? '✓' : String(number);
      });
      if (focus) flow.querySelector(`[data-choice-panel="${name}"] h1`).focus();
    };
    flow.classList.add('choice-enhanced');
    next.hidden = false;
    previous.hidden = false;
    next.addEventListener('click', () => { if (sectorSelect.reportValidity()) show('specialty'); });
    previous.addEventListener('click', () => show('sector'));
    flow.addEventListener('submit', event => {
      if (!panels[0].hidden) { event.preventDefault(); if (sectorSelect.reportValidity()) show('specialty'); }
    });
    flow.addEventListener('invalid', event => {
      const panel = event.target.closest('[data-choice-panel]');
      if (panel?.hidden) show(panel.dataset.choicePanel, false);
      const details = event.target.closest('details');
      if (details) details.open = true;
    }, true);
    show('sector', false);
  }
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
    if (count < 1 || count > 8) { details.open = true; feedback.textContent = 'Elegí entre 1 y 8 servicios para continuar.'; terms.focus(); return; }
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
