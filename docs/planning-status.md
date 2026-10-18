# Estado verificable de la entrega universitaria

Actualizado el 18 de octubre de 2026. Rige [alcance-academico.md](alcance-academico.md) y las [historias revisadas](historias/README.md). Docker/Compose son opcionales. Cambios propuestos para revisión sobre dev; las issues permanecen abiertas hasta aceptación.

## Evidencia de esta revisión

- Suite sin integración: **346 pruebas aprobadas**, 8 de integración deseleccionadas, Python 3.12.15.
- Suite con MongoDB real: **8 pruebas aprobadas**, 346 deseleccionadas, sin saltos. Servidor MongoDB 8.0.32 autenticado y replica set de un nodo en una base temporal aislada; API/worker y servidor temporal detenidos al terminar.
- Integración comprueba transacciones/rollback, reinicio físico de API y sesión/catálogo, recuperación física de worker, OCR/GridFS y recuperación de un documento previamente marcado listo con fragmentos sin manifiesto.
- Nuevas regresiones: archivo inexistente/corrupto, conflicto de carga, reparación idempotente, rechazo de publicación sin blob íntegro y reporte de fragmentos sin borrado; completitud igual en radar/detalle y actualidad de concursos con caché caliente.
- Microbenchmark de cinco muestras con doble en memoria: a 100 concursos, cálculo p50 3,605 ms y lectura p50 0,244 ms; a 1.000, 36,387 ms y 2,809 ms. Ambos almacenan caché y producen resultados equivalentes. [Resultado completo](benchmarks/matching-academic.json).
- El benchmark no mide Redis real, MongoDB, HTTP ni OCR. Un bypass deja la lectura de caché nula; `--counts 100 10000` es la ampliación opcional.
- No se consultó SICOP ni se modificó el corpus, perfil, credenciales o servicios existentes del usuario para estas pruebas.

## Matriz actual

| Historia | Evidencia técnica disponible | Pendiente obligatorio |
|---|---|---|
| NLC-01 | Contratos, fixtures y muestra SICOP fechada en source-validation.md. | Aceptación de la evidencia y sus límites. |
| NLC-02 | Monolito, configuración, índices, MongoDB local real y dependencias bloqueadas. | Aceptación del entorno documentado. |
| NLC-03 | Auth/perfil/catálogo, concurrencia, errores y persistencia tras reinicio real. | Recorrido manual de escritorio/móvil y teclado. |
| NLC-04 | Ingesta limitada, versiones, reintentos y radar con consulta exitosa, alcance, parcial/fallo y última verificación. | Aceptación del recorrido completo. |
| NLC-05 | Claim, leases, fencing, checkpoints, cancelación y recuperación física probada. | Demo manual de inicio/cierre del worker local con la API. |
| NLC-06 | Verificación íntegra de GridFS, identidad por carga, reparación de referencias antiguas y reporte sin borrado. OCR en entorno definido. | Aceptación de evidencia/descarga en la demo. |
| NLC-07 | Razones, decisiones persistentes y completitud compartida por radar y detalle. | Aceptación visual de las explicaciones. |
| NLC-08 | Invalidación/fallback, tres modos con doble Redis y microbenchmark 100/1.000. | Aceptación de los resultados y sus límites. |
| NLC-09 | Parser y CLI de ofertas presentadas, con comparables bloqueados. | Ninguno para la entrega obligatoria: historia opcional. |
| NLC-10 | Suite automática e integración real; documentación y benchmark. | E2E completo documentado, revisión básica de UI y 10–20 pares revisados por humanos con métricas exploratorias. |

Quedan fuera de la aceptación obligatoria Docker, un segundo backend Atlas/local, Redis real, operación de producción, cobertura multiplataforma completa, estudio con empresas, 30–50 pares y comparables adjudicados. No se consideran implementados por haberlos movido a ampliaciones.

## Cómo reproducir

```bash
uv sync --frozen
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv run pytest -m 'not integration'
uv run python scripts/check_publishable.py
uv run python scripts/benchmark_matching.py --output artifacts/matching-academic.json
# Solo con MongoDB local configurado y una base descartable exclusiva:
NEXO_TEST_LOCAL=1 NEXO_TEST_DATABASE=nexolicit_test_local uv run pytest -m integration
```

Actualizar índices con `uv run nexolicit init-db` en instalaciones existentes. Para reparar un documento antiguo, volver a consultar con anexos; no se ejecuta una descarga histórica masiva. `document-orphans` reporta posibles cargas activas y nunca las elimina.

## Registro histórico hasta el 17 de octubre

Los apartados siguientes conservan los resultados y pendientes de entregas previas. Sus cifras y requisitos anteriores no reemplazan el alcance académico vigente.

# Estado verificable del planning

Actualizado: 13 de octubre de 2026. Implementación propuesta para revisión, sin despliegue ni servicios permanentes iniciados. Los criterios con validación externa pendiente se mantienen abiertos; generar código no equivale a validar la fuente o la infraestructura.

| Issue | Implementación y evidencia | Pendiente para aceptación integral |
|---|---|---|
| [NLC-01](https://github.com/EstebanS3/NexoLicitCR/issues/1) | Contratos de concurso/línea/documento/página/oferta/job/match y contrato reservado Award. Cliente SICOP y fixtures sanitizadas; importes decimales y fechas inciertas preservados. | Zona horaria (hora local CR), secuencias (00 vigente, 01+ archivadas), identificadores y anexos reales digital/mixto/escaneado validados el 17/10 en [source-validation.md](source-validation.md). Pendiente: adjudicación final por línea (RF-16). |
| [NLC-02](https://github.com/EstebanS3/NexoLicitCR/issues/2) | Monolito, `.env` privado, lockfile, índices, salud, CLI y CI. Instalación de copia limpia con Python 3.13 y construcción de wheel comprobadas. | Integración Atlas real registrada en NLC-10. |
| [NLC-03](https://github.com/EstebanS3/NexoLicitCR/issues/3) | Login/logout, Argon2, CSRF, revisión de catálogo, expiración y revocación. Regresiones HTTP; UI responsive con movimiento reducido. | Revisión visual/manual completa y E2E con reinicio real en NLC-10. |
| [NLC-04](https://github.com/EstebanS3/NexoLicitCR/issues/4) | Paginación, errores, hash/versiones, idempotencia, cierre del detalle y reconsulta de activos fuera del filtro `since`. Tests de reintento/reconsulta. | No equivale a cobertura histórica total; consulta acotada por rubro. |
| [NLC-05](https://github.com/EstebanS3/NexoLicitCR/issues/5) | 202 después de persistir, idempotencia, claim atómico, lease/heartbeat/fencing, checkpoints, reintentos, cancelación, progreso y CLI one-shot con códigos coherentes. | Test de caída física con MongoDB/Atlas real en NLC-10. |
| [NLC-06](https://github.com/EstebanS3/NexoLicitCR/issues/6) | URL/redirect/bytes/firma/hash, GridFS, texto por página y proceso OCR limitado. PDF digital y publicación idempotente/fencing probados; errores OCR explícitos y reporte de huérfanos. | OCR español real escaneado/mixto; hosts firmados de almacenamiento verificados antes de habilitarlos. |
| [NLC-07](https://github.com/EstebanS3/NexoLicitCR/issues/7) | Razones, códigos SICOP separados de CIIU, exclusiones fiables/OCR, cierre vencido/cancelado, radar y decisiones persistentes. Tests de catálogo/corpus/decisiones. | Calidad de relevancia con etiquetas humanas en NLC-10. |
| [NLC-08](https://github.com/EstebanS3/NexoLicitCR/issues/8) | Redis opcional, prefijos por aplicación/entorno/instalación/base, TTL, timeout, breaker y generación durable. Equivalencia, invalidación y recuperación probadas con doble Redis. | Equivalencia y latencia con servidor Redis real en NLC-10. |
| [NLC-09](https://github.com/EstebanS3/NexoLicitCR/issues/9) | Parser de ofertas presentadas, moneda/partida/procedencia y fallo distinto de vacío. CLI y vista; adjudicación/comparables explícitamente indisponibles. | Revalidación del importador contra fuente real y fuente final por línea para RF-16. |
| [NLC-10](https://github.com/EstebanS3/NexoLicitCR/issues/10) | Dockerfile/Compose con Atlas externo y Redis opt-in, docs, wheel, copia limpia y microbenchmark reproducible. | Docker no disponible; Atlas no configurado; Redis real, OCR real, E2E con recuperación física, 30–50 pares humanos y benchmark extremo a extremo. |

## Evidencia de esta entrega

- Suite offline: **73 pruebas pasan en Python 3.12**, una prueba de integración real excluida explícitamente. Python 3.13: 70 pruebas iniciales y regresiones finales de CLI/matching verificadas por separado.
- Copia de fuentes publicables sin `.env`, datos, planning ni entorno anterior: `uv sync --frozen` y suite offline pasan en Python 3.13. No se presenta como clon remoto de un commit aún no publicado.
- Ruff check/formato, `git diff --check` y auditor de archivos publicables pasan.
- Wheel generado con plantillas y recursos incluidos. CLI `--help` comprobada.
- `pip-audit` sobre dependencias de ejecución bloqueadas: **sin vulnerabilidades conocidas** en la consulta realizada. No es una garantía de ausencia de defectos.
- Seis vistas renderizadas con TestClient y datos sintéticos. Revisión visual en navegador no completada: la política del navegador bloqueó URLs `file://`. No se eludió esa restricción.
- API y MongoDB locales permanecen detenidos por solicitud del usuario.

## Medición reproducible

```bash
uv run python scripts/benchmark_matching.py --output artifacts/matching-benchmark.json
```

Resultados conservados en [matching-offline.json](benchmarks/matching-offline.json): cinco muestras, un ítem de catálogo. A 100 concursos: cálculo p50 2,066 ms / p95 2,190 ms; lectura del doble de caché p50 0,189 ms / p95 0,262 ms. A 10.000: cálculo p50 236,577 ms / p95 296,923 ms; caché p50 26,319 ms / p95 26,803 ms. Igualdad comprobada en ambos tamaños.

Es un **microbenchmark de cálculo/serialización en memoria**. No incluye queries MongoDB, red Redis, HTTP, autenticación ni OCR, y no permite atribuir esa mejora a producción. Radar calcula el conjunto y luego pagina; conjuntos grandes todavía requieren medición y optimización de consultas. Valores de caché de más de 4 MiB se omiten de forma segura. No existe una medición de precisión/exhaustividad sin etiquetas humanas.

## Demo guiada · 14 de octubre de 2026

Alcance ajustado en issues 3, 4, 7, 8 y 10. Demo `/discover`: actividad, sugerencias deterministas editables, confirmación con revisión, perfil en MongoDB sin reemplazar catálogo, matching y consulta acotada/idempotente con revisión del perfil en el job. Worker automático supervisado en modo local. 81 pruebas offline pasan y el recorrido login → actividad → borrador fue comprobado por HTTP contra MongoDB local sin guardar un perfil ficticio. API y MongoDB están iniciados por solicitud del usuario, sustituyendo el estado detenido indicado en la entrega anterior. Feedback que propone cambios, evaluación humana y validaciones externas siguen pendientes.

## Experiencia guiada y recuperación · 16 de octubre de 2026

Configuración de empresa con sector, especialidad y revisión explícita, tutoriales,
20 sectores y 65 especialidades comerciales editables; vocabulario y límites en
[taxonomy.md](taxonomy.md). Menú responsive, contraste corregido y movimiento
opcional con respeto a la preferencia de movimiento reducido. El radar filtra por
rubro y permite consultas de 10–100 concursos recientes por rubro seleccionado,
además de activos guardados. Confirmar el perfil no inicia consultas.

La cola repara trabajos abandonados, mantiene checkpoints y recupera identidades
fallidas aunque cambie el listado. HTTP429 pausa la instalación y respeta
Retry-After, con esperas mínimas crecientes de 5/10/20 minutos. Reanudación explícita
por web y CLI, conservando filtros e historial, sin duplicación por doble envío.

Evidencia: **197 pruebas offline aprobadas**, 1 integración deseleccionada; Ruff
check/formato, comprobador de privacidad y diff-check correctos. Navegador real:
login, configuración por pasos, radar, filtro por rubro, móvil a 390 px sin
desborde, navegación y mensajes de error/reanudación sin errores de consola.
El corpus local llegó a 130 concursos reales (90 bienes, 20 obras, 20 servicios).
La última ampliación quedó no completada por HTTP429 tras los intentos limitados;
no acredita cobertura exhaustiva ni que haya un concurso vigente por especialidad.
Las pruebas de reanudación usan dobles Mongo; no sustituyen recuperación física.
Permanecen los pendientes de infraestructura y evaluación enumerados arriba.
