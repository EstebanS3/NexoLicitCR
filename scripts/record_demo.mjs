/** Record a local demo using a downloaded Playwright browser and a fresh profile.
 * Requires Node.js and Playwright. Never connects to a personal browser profile.
 * PLAYWRIGHT_MODULE may point at an existing Playwright package installation.
 * Use --screenshots for a quick rehearsal; otherwise records the narrated timing.
 */
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const work = path.join(root, 'var/demo-video');
process.env.PLAYWRIGHT_BROWSERS_PATH ??= path.join(work, 'browser-cache');
const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const screenshotsOnly = process.argv.includes('--screenshots');
const access = JSON.parse(await fs.readFile(path.join(root, 'var/demo/access.json'), 'utf8'));
const timeline = JSON.parse(await fs.readFile(path.join(work, 'timeline.json'), 'utf8'));
const images = path.join(root, 'docs/assets/demo');
await fs.mkdir(images, { recursive: true });
await fs.mkdir(path.join(work, 'raw'), { recursive: true });

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 1,
  locale: 'es-CR',
  timezoneId: 'America/Costa_Rica',
  reducedMotion: 'reduce',
  ...(screenshotsOnly ? {} : { recordVideo: { dir: path.join(work, 'raw'), size: { width: 1440, height: 900 } } }),
});
// A strict allowlist makes the recording independent of outside websites.
await context.route('**/*', async route => {
  const url = new URL(route.request().url());
  if (url.origin === 'http://localhost:8010') await route.continue();
  else await route.abort();
});
const page = await context.newPage();
const errors = [];
const responses = [];
page.on('pageerror', error => errors.push(error.message));
page.on('response', response => {
  if (response.status() >= 400) responses.push({ path: new URL(response.url()).pathname, status: response.status() });
});
const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
const navigate = async url => { await page.goto(`http://localhost:8010${url}`); await page.locator('main').waitFor(); };
const capture = async name => {
  await page.screenshot({ path: path.join(images, `${name}.png`) });
  const width = await page.evaluate(() => ({ body: document.documentElement.scrollWidth, viewport: innerWidth }));
  if (width.body > width.viewport) errors.push(`Horizontal overflow at ${name}`);
};
let start;
const events = [];
const atScene = async (id, action) => {
  const scene = timeline.find(item => item.id === id);
  if (!screenshotsOnly && start) await wait(Math.max(0, start + scene.start * 1000 - Date.now()));
  const began = Date.now();
  if (!screenshotsOnly && start && Math.abs((began - start) / 1000 - scene.start) > 3) {
    throw new Error('La grabación fue interrumpida; repetir desde el inicio.');
  }
  await action();
  events.push({ id, targetStart: scene.start, actualStart: start ? (began - start) / 1000 : 0, url: new URL(page.url()).pathname });
  console.log(`Escena: ${id}`);
};
try {
  await navigate('/login');
  await page.locator('#username').fill(access.username);
  await page.locator('#password').fill(access.password);
  await capture('00-acceso');
  start = Date.now();
  await atScene('inicio', async () => {
    if (!screenshotsOnly) await wait(6500);
    await page.getByRole('button', { name: /Entrar a mi espacio/ }).click();
    await page.getByRole('heading', { name: /Brújula TI/ }).waitFor();
    await capture('01-inicio');
  });
  await atScene('perfil', async () => {
    await page.getByRole('link', { name: 'Mi empresa', exact: true }).click();
    await page.locator('#company_name').waitFor();
    await capture('02-perfil');
    if (!screenshotsOnly) {
      await wait(6500);
      await page.getByRole('button', { name: /Continuar/ }).click();
      await page.locator('#sector').waitFor();
    }
  });
  await atScene('catalogo', async () => {
    await page.getByRole('link', { name: 'Salir de la configuración', exact: true }).click();
    await page.getByRole('link', { name: 'Mi catálogo', exact: true }).click();
    await page.getByRole('heading', { name: 'Mi catálogo', exact: true }).waitFor();
    await capture('03-catalogo');
  });
  await atScene('radar', async () => {
    await page.getByRole('link', { name: 'Mi radar', exact: true }).click();
    await page.locator('article.opportunity').first().waitFor();
    await page.locator('.filter-bar').scrollIntoViewIfNeeded();
    await capture('04-radar');
  });
  await atScene('filtros', async () => {
    await page.locator('#q').fill('soporte');
    await page.getByRole('button', { name: 'Filtrar', exact: true }).click();
    await page.locator('.filter-bar').scrollIntoViewIfNeeded();
    await page.getByRole('link', { name: 'DEMO · Soporte informático para centro cultural', exact: true }).first().waitFor();
    await capture('09-filtros');
  });
  await atScene('detalle', async () => {
    // Open another relevant case so the decision in the next scene is new.
    await navigate('/opportunities');
    await page.getByRole('link', { name: 'DEMO · Redes de datos y cableado estructurado para biblioteca', exact: true }).first().click();
    await page.locator('#decision').waitFor();
    await capture('05-detalle');
    if (!screenshotsOnly) { await wait(7000); await page.locator('.detail-grid').scrollIntoViewIfNeeded(); }
  });
  await atScene('documento', async () => {
    await page.locator('a.document-link[href^="/documents/"]').first().click();
    await page.getByRole('heading', { name: 'Del documento al contexto.' }).waitFor();
    await capture('06-documento');
  });
  await atScene('decision', async () => {
    await page.getByRole('link', { name: '← Expediente', exact: true }).click();
    await page.locator('#decision').scrollIntoViewIfNeeded();
    if (!screenshotsOnly) await wait(3500);
    await page.locator('#decision').selectOption('following');
    await page.locator('#note').fill('');
    await page.locator('#note').pressSequentially('Revisar experiencia y preparar la propuesta técnica.', { delay: screenshotsOnly ? 0 : 65 });
    if (!screenshotsOnly) await wait(2500);
    await page.getByRole('button', { name: 'Guardar decisión', exact: true }).click();
    await page.locator('#note').waitFor();
    if (await page.locator('#decision').inputValue() !== 'following') throw new Error('La decisión no se conservó.');
    await page.locator('#decision').scrollIntoViewIfNeeded();
    await capture('10-decision');
  });
  await atScene('seguimiento', async () => {
    await page.getByRole('link', { name: 'Mi radar', exact: true }).click();
    await page.locator('#status').selectOption('following');
    await page.getByRole('button', { name: 'Filtrar', exact: true }).click();
    await page.locator('.filter-bar').scrollIntoViewIfNeeded();
    await page.getByRole('link', { name: 'DEMO · Redes de datos y cableado estructurado para biblioteca', exact: true }).first().waitFor();
    await capture('07-seguimiento');
  });
  await atScene('actividad', async () => {
    await page.getByRole('link', { name: 'Actividad', exact: true }).click();
    await page.locator('.job-row').first().waitFor();
    await capture('08-actividad');
  });
  await atScene('cierre', async () => {
    await page.getByRole('link', { name: 'Inicio', exact: true }).click();
    await page.getByRole('heading', { name: /Brújula TI/ }).waitFor();
    await capture('11-resumen');
  });
  if (!screenshotsOnly) {
    const duration = timeline.at(-1).start + timeline.at(-1).duration;
    await wait(Math.max(0, start + duration * 1000 - Date.now()));
  }
  const video = page.video();
  await context.close();
  const result = { browser: 'Chromium de Playwright, perfil temporal vacío', viewport: { width: 1440, height: 900 }, isolatedOrigin: 'http://localhost:8010', events, errors, responses, ...(video ? { videoPath: await video.path() } : {}) };
  await fs.writeFile(path.join(work, screenshotsOnly ? 'rehearsal.json' : 'recording.json'), JSON.stringify(result, null, 2) + '\n');
  if (errors.length || responses.length) throw new Error('Revisar incidencias en el manifiesto privado de grabación.');
  console.log(screenshotsOnly ? 'Ensayo y capturas completados.' : 'Grabación terminada.');
} finally {
  await browser.close();
}
