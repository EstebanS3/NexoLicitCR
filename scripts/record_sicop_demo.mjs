/** Real customer workflow. Fresh Playwright context; private account; live backend SICOP. */
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const work=path.join(root,'var/demo-sicop-video');
process.env.PLAYWRIGHT_BROWSERS_PATH ??= path.join(root,'var/demo-video/browser-cache');
const {chromium}=createRequire(import.meta.url)(process.env.PLAYWRIGHT_MODULE || 'playwright');
const narration=JSON.parse(await fs.readFile(path.join(work,'audio/durations.json'),'utf8'));
const access=JSON.parse(await fs.readFile(path.join(root,'var/demo-sicop/access.json'),'utf8'));
await fs.mkdir(path.join(work,'raw'),{recursive:true});
await fs.mkdir(path.join(work,'screens'),{recursive:true});
const browser=await chromium.launch({headless:true});
const context=await browser.newContext({viewport:{width:1440,height:900},locale:'es-CR',timezoneId:'America/Costa_Rica',reducedMotion:'reduce',recordVideo:{dir:path.join(work,'raw'),size:{width:1440,height:900}}});
const page=await context.newPage();
const errors=[],responses=[],events=[];
page.on('pageerror',e=>errors.push(e.message));
page.on('response',r=>{if(r.status()>=400) responses.push({path:new URL(r.url()).pathname,status:r.status()});});
const wait=ms=>new Promise(r=>setTimeout(r,ms));
const origin='http://localhost:8011';
const nav=async url=>{await page.goto(origin+url);await page.locator('main').waitFor();};
const click=async name=>page.getByRole('button',{name,exact:false}).click();
const link=async name=>page.getByRole('link',{name,exact:true}).click();
const type=async(id,text,delay=28)=>{const e=page.locator(id);await e.fill('');await e.pressSequentially(text,{delay});};
let start=Date.now(),failed=null;
const scene=async(id,action,hold=5000)=>{
 const event={id,start:(Date.now()-start)/1000};events.push(event);
 console.log('Inicio: '+id);
 await action();event.actionEnd=(Date.now()-start)/1000;
 const audio=narration.find(x=>x.id===id)?.audio_seconds;
 const duration=event.actionEnd-event.start;
 await wait(audio ? Math.max(1000,(audio+0.5-duration)*1000) : hold);event.end=(Date.now()-start)/1000;event.path=new URL(page.url()).pathname;
 await page.screenshot({path:path.join(work,'screens',id+'.png')});
 await fs.writeFile(path.join(work,'progress.json'),JSON.stringify(events,null,2));
 console.log('Fin: '+id+' · '+(event.end-event.start).toFixed(1)+' s');
};
let mainJob,docsJob;
const waitForJob=async()=>{
 const id=await page.locator('[data-job-id]').getAttribute('data-job-id');
 const began=Date.now();let last='';
 while(Date.now()-began<600000){
  const response=await page.request.get(origin+'/jobs/'+id);
  const data=await response.json();
  const summary=data.status+' '+data.progress;
  if(summary!==last){console.log('SICOP: '+summary);last=summary;}
  if(['succeeded','failed','canceled'].includes(data.status)){
   await page.reload();await wait(1500);
   return {id,status:data.status,progress:data.progress,elapsed:(Date.now()-began)/1000};
  }
  if(data.error_code==='SOURCE_RATE_LIMITED') throw new Error('SICOP solicita pausa. Conservar trabajo y esperar Retry-After.');
  await wait(2000);
 }
 throw new Error('La consulta sigue pendiente; no fingir que terminó.');
};
const target='/tenders/20261002698:00';
const note='Revisión inicial · Mesa Norte Catering (empresa ficticia). Huetar Norte está dentro de nuestra cobertura. Validar opciones vegetarianas, menaje, transporte y aviso con 5 días naturales. No dar por acreditada la admisibilidad.';
const finalNote='Seguimiento · Mesa Norte Catering (empresa ficticia). Preparar menú de refrigerio y almuerzo con opción vegetariana; cotizar menaje, empaques y transporte. Verificar 3 eventos de más de 30 personas en los últimos 2 años, carnés y permisos vigentes. Confirmar cierre 26/10/2026 a las 10:00 en SICOP. Validar logística para la fecha potencial del 05/11 en Javillos de Florencia. PDF de 9 páginas disponible; cotejar la documentación vigente en SICOP. Responsable: coordinación comercial. Próximo paso: reunir evidencia; aún no presentar oferta.';
try {
 await nav('/register');start=Date.now();
 await scene('01-cuenta',async()=>{
  await wait(3000);await type('#username',access.username,65);
  await page.locator('#password').fill(access.password);await page.locator('#password-confirm').fill(access.password);
  await wait(1500);await click('Crear mi cuenta');await page.locator('#username').waitFor();
  await page.locator('#username').fill(access.username);await page.locator('#password').fill(access.password);
  await click('Entrar a mi espacio');await page.waitForURL(origin+'/');
 });
 await scene('02-empresa',async()=>{await link('Mi empresa');await type('#company_name','Mesa Norte Catering',75);await wait(2000);await click('Continuar');});
 await scene('03-especialidad',async()=>{
  await page.locator('#sector').selectOption('food');await click('Elegir especialidades');
  await page.locator('input[value="food:catering"]').check();
  await wait(3000);await click('Revisar mi perfil');
 });
 await scene('04-perfil',async()=>{
  await page.getByText('Más ajustes',{exact:false}).click();
  await page.locator('#activity').fill('Empresa ficticia de catering para talleres y eventos institucionales: refrigerios, almuerzos, opciones vegetarianas, menaje y transporte.');
  await type('#coverage','Región Huetar Norte y cantones cercanos',40);
  await page.locator('#category').selectOption('servicios');await wait(2000);
  await click('Confirmar perfil y abrir mi radar');await page.locator('#search-limit').waitFor();
 });
 await scene('05-catalogo',async()=>{
  await link('Mi catálogo');
  await type('#name','Catering para talleres y capacitaciones',35);
  await type('#description','Refrigerios y almuerzos con opción vegetariana, menaje, empaques y transporte.',24);
  await page.locator('#capabilities').fill('Planificación de menús, coordinación logística y servicio en el sitio. Capacidades ficticias para esta demostración.');
  await page.locator('#coverage').fill('Región Huetar Norte');
  await page.locator('#keywords').fill('catering, servicio de alimentación, refrigerio, almuerzo, vegetariana');
  await page.getByRole('button',{name:'Guardar',exact:true}).click();
  await page.getByRole('heading',{name:'Catering para talleres y capacitaciones',exact:true}).waitFor();
  await page.evaluate(()=>window.scrollTo(0,0));
 });
 await scene('06-consulta',async()=>{
  await link('Mi radar');await page.locator('#search-limit').selectOption('10');
  await page.locator('input[name="documents"]').uncheck();await wait(4000);
  await click('Buscar mis primeras oportunidades');await page.locator('[data-job-status]').waitFor();
 },2500);
 await scene('07-espera-sicop',async()=>{mainJob=await waitForJob();if(mainJob.status!=='succeeded')throw new Error('Consulta principal no completada');},2000);
} catch(error){failed=String(error).split('Call log:')[0];console.error(failed);await page.screenshot({path:path.join(work,'failure.png')});}
finally{
 const video=page.video();await context.close();
 await fs.writeFile(path.join(work,'take-prefix.json'),JSON.stringify({events,mainJob,docsJob,errors,responses,failed,videoPath:await video.path(),end:(Date.now()-start)/1000,recordedAt:new Date().toISOString()},null,2));
 await browser.close();
}
if(failed)process.exitCode=1;
