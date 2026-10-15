# Estado verificable del planning

Actualizado: 13 de octubre de 2026. Implementación propuesta para revisión, sin despliegue ni servicios permanentes iniciados. Los criterios con validación externa pendiente se mantienen abiertos; generar código no equivale a validar la fuente o la infraestructura.

| Issue | Implementación y evidencia | Pendiente para aceptación integral |
|---|---|---|
| [NLC-01](https://github.com/EstebanS3/NexoLicitCR/issues/1) | Contratos de concurso/línea/documento/página/oferta/job/match y contrato reservado Award. Cliente SICOP y fixtures sanitizadas; importes decimales y fechas inciertas preservados. | Zona horaria y relación entre secuencias; muestras reales digital/escaneada; adjudicación final por línea no validada. |
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
