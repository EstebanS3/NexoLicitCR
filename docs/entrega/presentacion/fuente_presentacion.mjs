import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { pathToFileURL } from 'node:url';
import { Presentation, PresentationFile } from '@oai/artifact-tool';

const ROOT = process.env.NEXO_REPO_ROOT || path.resolve(import.meta.dirname, import.meta.dirname.endsWith(path.join('docs', 'entrega', 'presentacion')) ? '../../..' : '../..');
const BUILD = path.join(ROOT, 'var/presentation-build');
const OUTPUT = path.join(ROOT, 'docs/entrega/presentacion');
const SKILL = process.env.NEXO_PRESENTATION_SKILL || path.join(os.homedir(), '.codex/plugins/cache/openai-primary-runtime/presentations/26.1020.11127/skills/presentations');
const PYTHON = process.env.NEXO_RUNTIME_PYTHON || path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3');
const SOFFICE = process.env.NEXO_RUNTIME_SOFFICE || path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/override/soffice');
process.env.RUNTIME_NODE_MODULES ||= path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules');
const FINAL = process.argv.includes('--final');
const REV = process.env.NEXO_BUILD_REVISION || 'r1';
const FONT = 'Arial';
const C = {navy:'#0B3043', ivory:'#F7F5EE', ink:'#173744', muted:'#557078', green:'#008F7B', pale:'#DBEAE3', white:'#FFFFFF'};
const p = Presentation.create({slideSize:{width:1280,height:720}});
const noteRecords = [];
let seq = 0;

await fs.mkdir(BUILD,{recursive:true});
await fs.mkdir(OUTPUT,{recursive:true});

function text(s, copy, x,y,w,h,size=28,color=C.ink,bold=false,align='left') {
  const shape=s.shapes.add({geometry:'textbox',name:`text-${++seq}`,position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0}});
  shape.text=copy;
  shape.text.style={typeface:FONT,fontSize:size,color,bold,alignment:align,verticalAlignment:'top',autoFit:'none',wrap:'square',insets:0};
  return shape;
}
function start(title,{dark=false}={}) {
  const s=p.slides.add(); s.background.fill=dark?C.navy:C.ivory;
  if(title) text(s,title,64,44,1152,95,45,dark?C.white:C.navy,true);
  text(s,`Borrador v0.9.0   /   ${String(p.slides.items.length).padStart(2,'0')}`,64,674,1152,22,15,dark?'#BBCACF':C.muted,false,'right');
  return s;
}
function notes(s,title,copy,source) {
  const n=`${copy}\n\nFuentes del repositorio: ${source}\nFecha editorial: 21 de octubre de 2026, Costa Rica. Escenario Brújula TI completamente ficticio.`;
  s.speakerNotes.text=n;
  noteRecords.push({title,copy:n});
}
async function image(s,rel,x,y,w,h,{fallback,fit='contain'}={}) {
  let file=path.join(ROOT,rel);
  try { await fs.access(file); } catch(e) {
    if(FINAL || !fallback) throw new Error(`Falta imagen requerida: ${rel}`);
    file=path.join(ROOT,fallback);
  }
  const b=await fs.readFile(file);
  s.images.add({blob:b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength),contentType:'image/png',alt:rel,fit,position:{left:x,top:y,width:w,height:h}});
}
function node(s,title,desc,x,y,w,h,{accent=false}={}) {
  const n=s.shapes.add({geometry:'rect',name:`architecture-${title}`,position:{left:x,top:y,width:w,height:h},fill:accent?C.pale:C.white,line:{fill:accent?C.green:'#B8C9C9',width:1.4}});
  text(s,title,x+20,y+16,w-40,36,25,C.navy,true);
  text(s,desc,x+20,y+57,w-40,h-66,21,C.muted);
  return n;
}
function connect(s,a,b,from='right',to='left') {
  s.shapes.connect(a,b,{kind:'straight',fromSide:from,toSide:to,line:{fill:C.green,width:2}});
}
function link(s,label,uri,x,y,w=1100,size=24,color=C.green) {
 const sh=text(s,label,x,y,w,42,size,color,true);
 sh.text.get(label).link={uri,isExternal:true};return sh;
}

// 01. The original logo remains intact and proportional.
{
 const s=start(null); s.background.fill=C.white;
 await image(s,'docs/assets/nexolicitcr-logo.png',84,126,1112,370);
 text(s,'Un radar de compras públicas para PYMES',100,495,1080,74,38,C.navy,false,'center');
 text(s,'Proyecto final de Bases de Datos Avanzadas',100,602,1080,36,23,C.muted,false,'center');
 notes(s,'NexoLicitCR','Presentar el proyecto como una herramienta para organizar la primera revisión de concursos públicos. La PYME ficticia Brújula TI sirve de hilo conductor. La promesa se limita a orientar la revisión con razones y conservar decisiones. Duración sugerida: 30 segundos.','README.md; docs/guia/00-vision-y-propuesta.md; docs/assets/nexolicitcr-logo.png.');
}
// 02. A user task rather than an unsupported market statistic.
{
 const s=start('La revisión de oportunidades en una PYME');
 text(s,'Brújula TI',64,186,580,64,48,C.green,true);
 text(s,'Una empresa ficticia de soporte técnico que busca concursos compatibles con su oferta.',64,267,570,155,31,C.ink);
 text(s,'Persona usuaria',740,193,465,38,25,C.muted,true);
 text(s,'Quien administra la empresa y revisa nuevas oportunidades.',740,247,450,105,31,C.navy);
 text(s,'Tarea que queremos facilitar',740,393,470,38,25,C.muted,true);
 text(s,'Relacionar el catálogo con un expediente y conservar la decisión.',740,448,460,142,31,C.navy);
 notes(s,'Problema y usuarios','Explicar que la revisión reúne capacidades de la empresa, metadatos de concursos, documentos y plazos. La persona necesita saber qué merece abrir y por qué. El proyecto plantea reducir esa revisión repetitiva, pero todavía no atribuye un ahorro de tiempo medido ni resultados comerciales. Una cuenta administradora controla una empresa por instalación. Duración sugerida: 50 segundos.','README.md; docs/guia/00-vision-y-propuesta.md; docs/architecture.md.');
}
// 03. Scope and limits are both part of the claim.
{
 const s=start('Alcance de la versión 0.9.0',{dark:true});
 text(s,'Recorrido disponible',64,181,560,45,30,'#A6D9CD',true);
 text(s,'Perfil y catálogo\nRadar con razones de coincidencia\nDocumentos con texto por página\nSeguimiento y actividad de consultas',64,252,570,305,32,C.white);
 text(s,'Límites del producto',754,181,460,45,30,'#A6D9CD',true);
 text(s,'Una empresa y una cuenta por instalación.\n\nLa revisión del expediente sigue a cargo de la persona.',754,252,448,270,30,C.white);
 text(s,'La afinidad orienta la revisión. La participación requiere verificar condiciones y fuente.',64,590,1135,55,25,'#C8D6DB');
 notes(s,'Alcance','Mencionar además las sesiones persistentes, protección CSRF y cambios del catálogo con revisión de concurrencia. La afinidad y las sugerencias usan reglas deterministas. El histórico conserva ofertas presentadas, no adjudicaciones finales. La ingesta cubre el corpus guardado y consultas acotadas. Duración sugerida: 50 segundos.','README.md; docs/alcance-academico.md; docs/architecture.md; src/nexolicitcr/matching.py.');
}
// 04. Real screenshot of synthetic data.
{
 const s=start('El catálogo explica qué ofrece Brújula TI');
 text(s,'1',64,178,70,72,52,C.green,true);
 text(s,'Confirmar el perfil',64,265,326,72,32,C.navy,true);
 text(s,'La empresa revisa sus capacidades y los términos que describen su oferta.',64,363,320,194,28,C.ink);
 await image(s,'docs/assets/demo/03-catalogo.png',430,169,786,454,{fallback:'docs/validacion/catalogo-movil.png'});
 notes(s,'Perfil y catálogo','La captura procede de la aplicación con datos ficticios de la demo. Mostrar que el perfil ayuda a proponer capacidades y que la persona confirma lo que realmente ofrece. El catálogo tiene su propia revisión y no debe perderse por sobrescrituras concurrentes. Enlazar la idea de capacidad comercial con términos y códigos que después usará el radar. Duración sugerida: 50 segundos.','docs/assets/demo/03-catalogo.png; docs/guided-discovery.md; src/nexolicitcr/storage.py; src/nexolicitcr/templates/catalog.html.');
}
// 05. Screenshot is evidence, never a background.
{
 const s=start('El radar muestra por qué aparece un concurso');
 await image(s,'docs/assets/demo/04-radar.png',64,166,823,464,{fallback:'docs/validacion/radar-escritorio.png'});
 text(s,'2',935,175,90,76,52,C.green,true);
 text(s,'Revisar afinidad',935,268,280,88,31,C.navy,true);
 text(s,'Términos y códigos aportan razones para abrir el expediente.',935,378,270,170,27,C.ink);
 notes(s,'Radar explicado','Abrir el concurso de redes de datos de la demo y señalar una razón visible. Los resultados derivan de reglas explícitas y versionadas. La afinidad no mide probabilidad de adjudicación ni acredita elegibilidad. Una consulta acotada tampoco demuestra cobertura de todo SICOP. El sistema conserva procedencia y estados desconocidos para que la persona pueda revisar. Duración sugerida: 60 segundos.','docs/assets/demo/04-radar.png; src/nexolicitcr/matching.py; docs/taxonomy.md; docs/source-validation.md.');
}
// 06. Independent decision as a data design consequence.
{
 const s=start('La evidencia acompaña la decisión');
 text(s,'3',64,177,80,72,52,C.green,true);
 text(s,'Abrir el documento',64,262,326,90,32,C.navy,true);
 text(s,'El texto conserva página y método de extracción.',64,371,323,100,28,C.ink);
 text(s,'Seguir o descartar deja una decisión independiente del cálculo.',64,496,323,116,27,C.ink);
 await image(s,'docs/assets/demo/06-documento.png',431,170,785,451,{fallback:'docs/validacion/radar-escritorio.png'});
 notes(s,'Documentos y seguimiento','Mostrar un anexo del escenario ficticio y su texto por página. El original reside en GridFS. La aplicación comprueba integridad y puede advertir extracción parcial. Luego explicar la acción de seguimiento que el video muestra: la colección decisions conserva la elección incluso si cambia el catálogo o se recalcula la afinidad. No equiparar texto extraído con comprensión completa del pliego. Duración sugerida: 60 segundos.','docs/assets/demo/06-documento.png; docs/assets/demo/07-seguimiento.png; src/nexolicitcr/documents.py; src/nexolicitcr/extractor.py; docs/architecture.md.');
}
// 07. Explicitly requested editable architecture diagram.
{
 const s=start('Arquitectura y responsabilidad de cada componente');
 const browser=node(s,'Navegador','HTML, CSS y JavaScript',64,180,285,118);
 const web=node(s,'Aplicación Python','FastAPI y Jinja2',474,180,325,118);
 const redis=node(s,'Redis opcional','Caché del radar',921,180,295,118);
 const worker=node(s,'Worker','Ingesta y extracción',64,448,285,135);
 const mongo=node(s,'MongoDB','Datos, versiones y trabajos',474,448,325,135,{accent:true});
 const grid=node(s,'GridFS','Originales y fragmentos',921,448,295,135,{accent:true});
 connect(s,browser,web);connect(s,web,redis);connect(s,web,mongo,'bottom','top');connect(s,worker,mongo);connect(s,mongo,grid);
 text(s,'SICOP y anexos alimentan el worker',64,354,330,60,23,C.muted);
 text(s,'Una base exclusiva por instalación',476,615,704,32,24,C.muted,false,'center');
 notes(s,'Arquitectura','Recorrer el diagrama desde la interfaz. La aplicación consulta MongoDB como fuente de verdad y puede reutilizar un cálculo en Redis. El worker procesa trabajos persistidos y obtiene metadatos y documentos desde la fuente. GridFS forma parte del almacenamiento MongoDB, aunque aparece como responsabilidad separada para explicar los binarios. Redis resulta opcional. INSTALLATION_ID separa trabajos y caché, pero no convierte una base compartida en un servicio multiempresa. Duración sugerida: 70 segundos.','docs/architecture.md; src/nexolicitcr/web.py; src/nexolicitcr/jobs.py; src/nexolicitcr/storage.py; src/nexolicitcr/cache.py.');
}
// 08. Native text, not a raster schema.
{
 const s=start('Versiones y transacciones conservan el contexto');
 text(s,'Concurso vigente',64,182,500,48,35,C.green,true);
 text(s,'tenders',64,253,500,43,31,C.navy,true);
 text(s,'Snapshot normalizado, hash y procedencia.',64,315,470,94,28,C.ink);
 text(s,'Historial de cambios',697,182,510,48,35,C.green,true);
 text(s,'tender_versions',697,253,510,43,31,C.navy,true);
 text(s,'Versiones inmutables identificadas por concurso y contenido.',697,315,500,117,28,C.ink);
 text(s,'Una transacción publica ambos estados',64,480,1148,58,38,C.navy,true);
 text(s,'Un fallo revierte la escritura. Los reintentos reutilizan identidades e índices únicos.',64,565,1115,65,28,C.muted);
 notes(s,'Datos y transacciones','Relacionar esta decisión con una necesidad humana: poder saber qué cambió sin dejar un estado vigente separado de su historial. MongoDB requiere un replica set o Atlas para estas transacciones. Los importes decimales se serializan como texto y las fechas desconocidas permanecen explícitas. El catálogo usa una revisión monotónica y las decisiones persisten en su propia colección. Los binarios se cargan antes de publicar su referencia y el sistema dispone de diagnóstico de huérfanos. Duración sugerida: 65 segundos.','docs/architecture.md; src/nexolicitcr/storage.py; src/nexolicitcr/ingestion.py; tests/test_atlas_integration.py.');
}
// 09. Reliability tied to an observable screen.
{
 const s=start('Las consultas conservan sus avances');
 await image(s,'docs/assets/demo/08-actividad.png',64,173,795,448,{fallback:'docs/validacion/radar-escritorio.png'});
 text(s,'Trabajos durables',913,181,300,81,31,C.navy,true);
 text(s,'Leases, checkpoints e intentos permiten recuperar el procesamiento.',913,289,289,150,27,C.ink);
 text(s,'Redis puede fallar',913,470,298,45,28,C.green,true);
 text(s,'El radar vuelve a calcular desde MongoDB.',913,536,280,90,26,C.ink);
 notes(s,'Jobs y caché','La pantalla de actividad muestra alcance y estado de las consultas. Los checkpoints preservan avance y los tokens del lease impiden que un worker vencido publique. HTTP 429 provoca una pausa de la fuente y las consultas fallidas o canceladas pueden reanudarse con sus límites. La caché usa revisión del catálogo, reglas y generación del corpus para invalidación. Las decisiones y los cierres se comprueban al responder. El video muestra estados preparados de demo y no fuerza caídas de infraestructura. Duración sugerida: 60 segundos.','docs/assets/demo/08-actividad.png; docs/operations.md; src/nexolicitcr/jobs.py; src/nexolicitcr/cache.py; tests/test_worker_recovery_integration.py.');
}
// 10. Dated historical evidence without benchmark inflation.
{
 const s=start('Evidencia técnica con alcance explícito',{dark:true});
 text(s,'21 de octubre de 2026',64,180,510,45,28,'#A6D9CD');
 text(s,'18 de octubre de 2026',729,180,484,45,28,'#A6D9CD');
 text(s,'365',64,260,430,117,92,C.white,true);
 text(s,'pruebas de lógica y HTTP\ncon dobles',64,397,480,100,30,C.white);
 text(s,'9',729,260,395,117,92,C.white,true);
 text(s,'pruebas nativas de integración\ncontra MongoDB Atlas',729,397,474,100,30,C.white);
 text(s,'La integración corresponde al informe histórico de Atlas. El escenario de demo usa datos ficticios.',64,559,1143,72,27,'#C8D6DB');
 notes(s,'Evidencia','La revisión actual del 21 de octubre de 2026 ejecutó pytest con la selección not integration: 365 aprobadas y 9 deseleccionadas. Las 9 pruebas nativas contra Atlas proceden del informe histórico del 18 de octubre de 2026. Ese informe registra además 8 pruebas dentro de Docker y una comprobación de fallback con Redis real. Las dos ejecuciones tienen fechas y entornos distintos. Ninguna constituye una medición del rendimiento de producción. El microbenchmark disponible usa datos sintéticos y un doble de caché en memoria, por eso la presentación no promete latencias de producción. Las pruebas no miden la precisión comercial del matching ni el ahorro de tiempo para empresas. Duración sugerida: 60 segundos.','Ejecución de pytest -m not integration, 21/10/2026; docs/validacion/docker-atlas.md; docs/validacion/README.md; docs/benchmarks/matching-academic.json.');
}
// 11. Roadmap stated as proposals, without dates invented.
{
 const s=start('Roadmap después de la entrega');
 text(s,'Próxima validación',64,184,500,47,34,C.green,true);
 text(s,'Observar tareas con PYMES y evaluar si comprenden las razones del radar.',64,260,500,153,31,C.ink);
 text(s,'Calidad documental',64,451,500,44,31,C.navy,true);
 text(s,'Ampliar muestras, referencias humanas y formatos compatibles.',64,521,500,107,28,C.ink);
 text(s,'Operación',724,184,486,47,34,C.green,true);
 text(s,'Medir el recorrido completo y ensayar respaldo y restauración.',724,260,480,137,31,C.ink);
 text(s,'Nuevas capacidades',724,451,486,44,31,C.navy,true);
 text(s,'Avisos y colaboración. Comparables sujetos a una fuente validada de adjudicaciones.',724,521,480,117,28,C.ink);
 notes(s,'Roadmap','Las prioridades son propuestas posteriores a v0.9.0 y no compromisos ya implementados. La siguiente evidencia de producto debe incluir tareas observadas con empresas y un protocolo de relevancia. Ampliar formatos requiere límites de recursos y regresiones. Antes de comparables económicos hace falta validar una fuente de adjudicaciones por línea. Una evolución multiempresa necesita un diseño explícito de usuarios y aislamiento. Duración sugerida: 50 segundos.','docs/guia/04-evolucion-y-evaluacion.md; docs/guided-discovery.md; docs/alcance-academico.md.');
}
// 12. Useful handoff links; local video location is filled by the root task.
{
 const s=start('Demostración y materiales');
 text(s,'Brújula TI revisa un concurso y conserva su decisión',64,180,1120,122,48,C.navy,true);
 text(s,'Escenario ficticio en una base exclusiva de demostración',64,332,1123,54,29,C.muted);
 link(s,'Repositorio y guía de instalación','https://github.com/EstebanS3/NexoLicitCR',64,446);
 link(s,'Video de demostración','../demo/NexoLicitCR_demo.mp4',64,508);
 text(s,'La empresa retoma su revisión con la evidencia y su decisión a mano.',64,591,1100,63,29,C.ink);
 notes(s,'Demo y cierre','Reproducir el video de la entrega, de 3 a 5 minutos, desde su carpeta local. El escenario y sus instituciones son ficticios. La demo usa una cuenta propia y una base exclusiva. Al cerrar, recordar el hilo completo: la empresa confirma su oferta, revisa una razón, abre evidencia y conserva la decisión. El repositorio incluye instrucciones para repetir el escenario. Reservar preguntas sobre transacciones, recuperación y límites de la fuente. Duración hablada sugerida: 25 segundos, además del video.','README.md; docs/entrega/demo/; docs/architecture.md.');
}

for(const [i,s] of p.slides.items.entries()) {
 const png=await p.export({slide:s,format:'png',scale:1});
 await fs.writeFile(path.join(BUILD,`slide-${String(i+1).padStart(2,'0')}.png`),new Uint8Array(await png.arrayBuffer()));
}
const candidate=path.join(BUILD,`candidate-${REV}.pptx`);
await(await PresentationFile.exportPptx(p)).save(candidate);
await fs.writeFile(path.join(BUILD,'presentation.json'),JSON.stringify(p.toProto()));
const notesMD='# Notas para la presentación final\n\nBorrador v0.9.0. 12 diapositivas. Duración hablada aproximada: 10-12 minutos, más el video de 3-5 minutos.\n\n'+noteRecords.map((n,i)=>`## ${i+1}. ${n.title}\n\n${n.copy}\n`).join('\n');
await fs.writeFile(path.join(OUTPUT,'notas_exposicion.md'),notesMD);
await fs.copyFile(import.meta.filename,path.join(OUTPUT,'fuente_presentacion.mjs'));
if(FINAL) {
 const {finalizePresentation}=await import(pathToFileURL(path.join(SKILL,'container_tools/artifact_tool_utils.mjs')).href);
 const validatedDir=path.join(ROOT,'var/presentation-validated'); await fs.mkdir(validatedDir,{recursive:true});
 const finalPath=path.join(validatedDir,`validated-${REV}.pptx`);
 await finalizePresentation({workspaceDir:ROOT,candidatePath:candidate,finalPath,pythonExecutable:PYTHON,integrityValidatorPath:path.join(SKILL,'container_tools/inspect_presentation_package_integrity.py'),layoutValidatorPath:path.join(SKILL,'container_tools/inspect_presentation_layout_geometry.py'),layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-bullet-geometry','--validate-heading-fit'],explicitTotalSlideCount:12,requiredNativeTableOwnerSlides:[],requiredNativeChartOwnerSlides:[],fontPolicy:{basis:'design',families:[FONT]},verifyArtifactToolImport:true,receiptPath:path.join(BUILD,`validation-${REV}.json`)});
 await fs.copyFile(finalPath,path.join(OUTPUT,'NexoLicitCR_presentacion_final.pptx'));
 // LibreOffice exports the validated PPTX and preserves selectable text in the PDF.
 await promisify(execFile)(SOFFICE,['-env:UserInstallation='+pathToFileURL(path.join(BUILD,'libreoffice-profile')).href,'--headless','--convert-to','pdf','--outdir',OUTPUT,path.join(OUTPUT,'NexoLicitCR_presentacion_final.pptx')],{timeout:120000});
}
console.log(JSON.stringify({slides:p.slides.items.length,candidate,final:FINAL,output:OUTPUT}));
