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
const resumeIndex=process.argv.indexOf('--resume-job');
const resumeJob=resumeIndex>=0?process.argv[resumeIndex+1]:null;
if(resumeJob&&!/^[a-f0-9]{32}$/.test(resumeJob))throw new Error('Identificador de trabajo inválido.');
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
const get=async(url)=>{for(let attempt=0;attempt<4;attempt++){try{return await page.request.get(url,{timeout:30000});}catch{if(attempt===3)throw new Error('La conexión local se interrumpió repetidamente.');await wait(1000*(attempt+1));}}};
const waitForJob=async()=>{
 const id=await page.locator('[data-job-id]').getAttribute('data-job-id');
 const began=Date.now();let last='';
 while(Date.now()-began<600000){
  const response=await get(origin+'/jobs/'+id);
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
 await nav('/login');await page.locator('#username').fill(access.username);await page.locator('#password').fill(access.password);await click('Entrar a mi espacio');await page.waitForURL(origin+'/');
 await nav(resumeJob?'/jobs/'+resumeJob+'/view':'/opportunities?q=alimentaci%C3%B3n&minimum=1');start=Date.now();
 if(!resumeJob) await scene('08-ampliar',async()=>{
  await page.locator('.filter-bar').scrollIntoViewIfNeeded();await wait(5000);
  await page.locator('#search-limit').selectOption('50');await page.locator('input[name="documents"]').check();
  await wait(3000);await click('Consultar novedades en SICOP');await page.locator('[data-job-status]').waitFor();
 });
 await scene('08-espera-ampliada',async()=>{
  const id=await page.locator('[data-job-id]').getAttribute('data-job-id');
  const began=Date.now();let last='';
  while(Date.now()-began<2400000){
   const response=await get(origin+'/jobs/'+id);const data=await response.json();
   const status=data.status+' '+data.progress;
   if(status!==last){console.log('Consulta ampliada: '+status);last=status;}
   if(data.error_code==='SOURCE_RATE_LIMITED')throw new Error('SICOP solicita pausa; respetar Retry-After.');
   const targetResponse=await get(origin+target);
   const html=await targetResponse.text();
   if(targetResponse.ok() && html.includes('class="badge ready"')){
    docsJob={id,status:data.status,progress:data.progress,elapsed:(Date.now()-began)/1000};mainJob=docsJob;break;
   }
   if(['succeeded','failed','canceled'].includes(data.status)) {docsJob={id,status:data.status,progress:data.progress,elapsed:(Date.now()-began)/1000};mainJob=docsJob;break;}
   await wait(5000);
  }
  if(!mainJob)throw new Error('La consulta ampliada continúa pendiente.');
 },2000);
 await scene('08-detener',async()=>{
  await page.reload();await wait(2000);
  if(!['succeeded','failed','canceled'].includes(docsJob.status)){
   await click('Solicitar cancelación');docsJob=await waitForJob();mainJob=docsJob;
  }
 });
 await scene('08-resultados',async()=>{
  await link('Revisar oportunidades guardadas ↗');await page.locator('.filter-bar').scrollIntoViewIfNeeded();
  await page.locator('#q').fill('alimentación');await page.getByRole('button',{name:'Filtrar',exact:true}).click();
  await page.locator('.filter-bar').scrollIntoViewIfNeeded();await page.locator(`a[href="${target}"]`).first().waitFor();
 });
 await scene('09-expediente',async()=>{
  await page.locator(`a[href="${target}"]`).first().click();await page.locator('#decision').waitFor();
  await wait(6000);await page.getByRole('heading',{name:'Líneas solicitadas',exact:true}).scrollIntoViewIfNeeded();
  await wait(4000);await page.getByRole('heading',{name:'Condiciones técnicas',exact:true}).scrollIntoViewIfNeeded();
  await wait(5000);await page.getByRole('heading',{name:'Admisibilidad',exact:true}).scrollIntoViewIfNeeded();
 });
 await scene('10-comentario',async()=>{
  await page.locator('#decision').selectOption('relevant');await type('#note',note,26);
  await click('Guardar decisión');await page.locator('#decision').scrollIntoViewIfNeeded();
  if(await page.locator('#note').inputValue()!==note)throw new Error('Nota no persistida');
 });
 await scene('13-documento',async()=>{
  await nav(target);const doc=page.locator('a.document-link[href^="/documents/"]');
  if(await doc.count()){
   await doc.first().click();await page.getByRole('heading',{name:'Del documento al contexto.'}).waitFor();
   await wait(4000);if(await page.locator('.evidence-page').count())await page.locator('.evidence-page').first().scrollIntoViewIfNeeded();
  }else{await page.getByRole('heading',{name:'Documentos',exact:true}).scrollIntoViewIfNeeded();}
 });
 await scene('14-seguimiento',async()=>{
  await nav(target);await page.locator('#decision').selectOption('following');await type('#note',finalNote,22);
  await click('Guardar decisión');await page.locator('#decision').scrollIntoViewIfNeeded();
  if(await page.locator('#decision').inputValue()!=='following'||await page.locator('#note').inputValue()!==finalNote)throw new Error('Seguimiento no persistido');
  const box=await page.locator('#note').boundingBox();
  await page.mouse.move(box.x+box.width-4,box.y+box.height-4);await page.mouse.down();await page.mouse.move(box.x+box.width-4,box.y+box.height+220,{steps:20});await page.mouse.up();
  await page.locator('#note').scrollIntoViewIfNeeded();
 });
 await scene('15-descartar',async()=>{
  await nav('/tenders/20261002756:00');await page.locator('#decision').selectOption('discarded');
  await type('#note','Descartado: reparación de excavadora fuera del giro de Mesa Norte Catering. Priorizamos alimentación para eventos.',25);
  await click('Guardar decisión');await page.locator('#decision').scrollIntoViewIfNeeded();
 });
 await scene('16-mi-cartera',async()=>{
  await link('Mi radar');await page.locator('#status').selectOption('following');await page.locator('#minimum').fill('0');
  await page.getByRole('button',{name:'Filtrar',exact:true}).click();await page.locator('.filter-bar').scrollIntoViewIfNeeded();
  await page.locator(`a[href="${target}"]`).first().waitFor();
 });
 await scene('17-regresar',async()=>{
  await click('Cerrar sesión');await page.locator('#username').fill(access.username);await page.locator('#password').fill(access.password);
  await click('Entrar a mi espacio');await page.waitForURL(origin+'/');await wait(2500);
  await nav(target);await page.locator('#decision').scrollIntoViewIfNeeded();
  if(await page.locator('#note').inputValue()!==finalNote)throw new Error('Nota perdida tras iniciar sesión');
 });
 await scene('18-resumen',async()=>{await link('Inicio');await page.getByRole('heading',{name:/Mesa Norte Catering/}).waitFor();},10000);
} catch(error){failed=String(error).split('Call log:')[0];console.error(failed);await page.screenshot({path:path.join(work,'failure.png')});}
finally{
 const video=page.video();await context.close();
 await fs.writeFile(path.join(work,resumeJob?'take-resume.json':'take-expand.json'),JSON.stringify({events,mainJob,docsJob,errors,responses,failed,videoPath:await video.path(),end:(Date.now()-start)/1000,recordedAt:new Date().toISOString()},null,2));
 await browser.close();
}
if(failed)process.exitCode=1;
