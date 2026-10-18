# Alcance de la entrega universitaria

Vigente desde el 18 de octubre de 2026, por solicitud del usuario. Esta revisión reemplaza el alcance de aceptación anterior de NLC-01–10; no cambia los hechos registrados en reportes históricos.

## Propósito

Demostrar una aplicación útil y reproducible de Bases de Datos Avanzadas: modelado documental, índices, transacciones, versiones, almacenamiento GridFS, jobs durables y caché opcional. La entrega no pretende acreditar un servicio de producción ni la calidad comercial del ranking.

## Entrega obligatoria

- Monolito FastAPI/Jinja2 y CLI del mismo paquete, con cuenta inicial, autenticación y catálogo/perfil confirmado.
- Un entorno de MongoDB real autenticado con transacciones: replica set local o Atlas. Basta demostrar uno; mongomock solo cubre pruebas de lógica.
- Consulta pequeña de SICOP, normalmente 10 o 25 concursos por rubro. Preservar procedencia, decimales, incertidumbre y límites; no prometer cobertura total.
- Versiones por hash y reingesta idempotente; recuperación del worker mediante lease y fencing, con una interrupción física comprobada.
- Anexos compatibles en GridFS íntegro, extracción digital/OCR español por página y estados parciales. Un documento listo debe tener un original completo y descargable.
- Radar con razones, fecha de verificación, alcance/resultado de consultas y avisos coherentes de evidencia incompleta. Decisiones y notas sobreviven a los cambios del perfil.
- Caché opcional con invalidación y fallback. El ensayo obligatorio puede usar un doble controlado en memoria, identificado explícitamente.
- Microbenchmark de cálculo/serialización para 100 y 1.000 concursos, con equivalencia de resultados, muestras, tamaños y límites. Un miss/bypass nunca se presenta como mejora. No atribuir tiempos del doble a Redis o al sistema completo.
- Un recorrido reproducible completo que conserve datos tras reinicio, un caso de fallo controlado y revisión manual de formularios en escritorio y una vista móvil del entorno elegido.
- README, configuración sin secretos, comandos de instalación/prueba, evidencia, guion de demo y pendientes honestos.

La demo acredita comportamientos técnicos; no declara precisión o exhaustividad del ranking sin una evaluación específica.

## Ampliaciones opcionales

| Extensión | Tratamiento |
|---|---|
| Docker y Compose | Se conservan disponibles; construir o ejecutar contenedores no bloquea la aceptación. |
| Segundo entorno de persistencia | Validar Atlas además de MongoDB local, o viceversa, es opcional. |
| Redis real | Red, caídas físicas y benchmark de servidor son ampliaciones; la lógica cliente y sus dobles siguen siendo parte de la demostración. |
| Producción e infraestructura | Despliegue público, alta disponibilidad, múltiples nodos, pruebas extensas de particiones y SLA no son entrega obligatoria. |
| Multiplataforma y accesibilidad exhaustiva | Se elige y documenta un entorno. La revisión básica de interacción se mantiene; no se exige una matriz completa de plataformas. |
| Evaluación humana o con empresas | Etiquetado de pares y medición de relevancia quedan como ampliación opcional, sin una muestra mínima para la entrega. |
| Feedback que propone cambios | El mínimo guarda estado y nota; propuestas automáticas revisables requieren otro incremento. |
| Histórico y comparables | NLC-09 es opcional; RF-16 no se implementa sin fuente final por línea validada. Nunca inferir adjudicación de ofertas. |
| Escala adicional | 10.000 concursos y mediciones extremo a extremo son ampliaciones, sin promesas de rendimiento. |

## Cambios de alcance por historia

| Historia | Decisión |
|---|---|
| NLC-01 | Muestra SICOP acotada y contratos; fuente final de adjudicación opcional. |
| NLC-02 | Un entorno MongoDB real reproducible; Docker y otro backend opcionales. |
| NLC-03 | Autenticación/perfil y revisión básica de UI; matriz exhaustiva opcional. |
| NLC-04 | Consulta explícita acotada y actualidad del corpus visibles. |
| NLC-05 | Jobs durables, recuperación física y demo local; operación distribuida opcional. |
| NLC-06 | Integridad y recuperación de archivos obligatorias; un entorno OCR definido. |
| NLC-07 | Coincidencias explicadas y decisiones; propuestas de perfil desde feedback opcionales. |
| NLC-08 | Correctitud de caché y microbenchmark 100/1.000; servidor real y escala mayor opcionales. |
| NLC-09 | Extensión opcional completa; conservar etiquetas y bloqueos honestos. |
| NLC-10 | Demo académica y evidencia técnica; no exige evaluación por pares, producción ni empresas. |

Los textos vigentes por issue están en [historias/](historias/README.md). El [snapshot anterior](historias/archivo/2026-10-18-antes-del-ajuste.json) permite auditar lo retirado. Los estados abiertos se conservan; cambiar el alcance no equivale a cerrar una historia o a completar una validación pendiente.

## Correcciones incluidas

1. GridFS verifica contenido/tamaño y reutiliza únicamente archivos completos. Las escrituras nuevas usan identificadores independientes por carga; un reintento no necesita borrar fragmentos posiblemente activos. Se reparan documentos antiguos marcados listos cuyo blob falte. La consulta por SHA en metadatos tiene índice.
2. Radar y detalle usan la misma selección de evidencia actual y el mismo indicador de completitud.
3. El radar muestra última consulta exitosa y alcance, resultados parciales/fallos o ejecución en curso y última verificación por concurso. Las fechas se leen fuera de la caché de matching para reflejar reingestas idénticas.

`nexolicit document-orphans` es solo un reporte: distingue `unreferenced_file` (archivos completos sin referencia con más de un día) y `chunks_without_file` (fragmentos sin manifiesto, que pueden pertenecer a una carga activa). La edad de estos últimos se infiere del ObjectId del fragmento cuando existe; puede ser desconocida. No borra ni declara segura una limpieza.

Las instalaciones existentes reciben el índice con `nexolicit init-db`, operación idempotente que no borra datos. Los documentos incompletos se reparan cuando se vuelven a consultar con anexos; esta entrega no inicia una descarga histórica masiva.

## Evidencia y pendientes

Consultar [planning-status.md](planning-status.md) para los resultados de pruebas de esta entrega y sus pendientes. Los reportes anteriores conservan sus cifras y contexto histórico; este documento define el alcance actual y no reescribe sus resultados.
