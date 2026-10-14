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
  const poll = async () => {
    try {
      const response = await fetch(`/jobs/${encodeURIComponent(job.dataset.jobId)}`, {headers:{Accept:'application/json'}, credentials:'same-origin'});
      if (response.redirected) { location.assign('/login'); return; }
      if (!response.ok) throw new Error('No se pudo consultar el progreso.');
      const data = await response.json();
      job.querySelector('[data-job-status]').textContent = data.status;
      job.querySelector('[data-job-progress]').textContent = data.progress;
      job.querySelector('[data-job-attempt]').textContent = data.attempt;
      job.querySelector('[data-job-message]').textContent = data.error_code || (data.cancel_requested ? 'Cancelación solicitada; se aplicará en el próximo punto seguro.' : data.status === 'queued' ? 'En cola. Esperando un worker disponible.' : 'El progreso se conserva aunque cierres esta pantalla.');
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
