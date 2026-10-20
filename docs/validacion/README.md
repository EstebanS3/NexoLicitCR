# Memoria de validación y guion de exposición · NLC-10

**Ampliación posterior del mismo día:** [Docker Desktop, Atlas, Redis real y recorrido SICOP](docker-atlas.md). Esa memoria agrega las comprobaciones ejecutadas después de la revisión local descrita abajo y actualiza sus límites de infraestructura.

Fecha: 18 de octubre de 2026. Esta memoria satisface la entrega textual de NLC-10: explica el recorrido, sus resultados esperados, las comprobaciones ejecutadas y sus límites. No afirma que se haya realizado un único recorrido completo contra SICOP en vivo. La evidencia combina pruebas por componente, integración con MongoDB real y revisión visual controlada.

## Entorno y resultados ejecutados

macOS ARM64, Python 3.12.15 y MongoDB 8.0.32 autenticado, replica set local de un nodo. Bases temporales exclusivas, Redis desactivado y ejecución nativa sin Docker. Tesseract y Poppler disponibles para la integración de OCR. El corpus, las cuentas y los servicios de la aplicación personal permanecieron intactos durante esta validación.

- `PYTHONPATH=src .venv/bin/python -m pytest -m 'not integration' -q`: **346 aprobadas**, 9 deseleccionadas.
- Suite `pytest -m integration -q`, con `NEXO_TEST_LOCAL=1`, base exclusiva con prefijo `nexolicit_test_` y MongoDB temporal autenticado: **9 aprobadas**, 346 deseleccionadas, sin saltos.
- Las advertencias de deprecación de dependencias no fueron fallos. Estas cifras corresponden a esta revisión; los informes anteriores conservan sus resultados históricos.

La integración requiere una base vacía sin administrador. Los comandos de configuración y selección del entorno están en [operación](../operations.md#calidad-y-límites-de-evidencia). No se deben ejecutar estas pruebas sobre la base de la empresa.

## Recorrido explicado para la defensa

| Paso y explicación sugerida | Resultado esperado | Evidencia disponible y límite |
|---|---|---|
| 1. «La primera cuenta administra una instalación. Luego ingresamos con sesión.» | Registro inicial único; rutas protegidas; credenciales inválidas rechazadas; logout revoca acceso. | `test_registration.py`, `test_web.py` y reinicio real en `test_restart_integration.py`. Login/logout también revisados en navegador con cuenta sintética. |
| 2. «Elegimos nombre, sector y especialidades; revisamos antes de confirmar.» | El borrador permite regresar; confirmar guarda el perfil. El catálogo manual permanece independiente y evita sobrescrituras concurrentes. | Revisión visual descrita abajo; `test_onboarding.py`, `test_multi_specialties.py`, `test_storage.py` y persistencia real de catálogo/sesión tras reinicio. |
| 3. «El radar consulta primero datos guardados. Una actualización necesita una acción explícita.» | Job durable con rubro, límite y revisión del perfil; alcance limitado, progreso y errores visibles. | `test_jobs.py`, `test_ingestion.py`, `test_search_regressions.py` y `test_radar_freshness.py`. La vista vacía real se revisó sin lanzar consultas externas. La muestra histórica de fuente está en [source-validation.md](../source-validation.md). |
| 4. «El original se guarda en GridFS; el texto conserva su página y procedencia.» | Verificar hash/tamaño antes de publicar; extraer PDF/OCR con límites; advertir evidencia incompleta. | `test_atlas_integration.py` también admite MongoDB local y ejecutó OCR/GridFS/transacciones reales. `test_gridfs_recovery_integration.py` reparó una carga interrumpida y un documento previamente listo sin blob válido. Los anexos de prueba son sintéticos. |
| 5. «La afinidad explica coincidencias; la decisión la toma la persona.» | Radar/detalle comparten la advertencia de evidencia parcial. Seguir/descartar persiste al editar catálogo. | `test_radar_freshness.py` y `test_web.py::test_radar_filters_and_decision_survive_catalog_edit`. Son pruebas HTTP con dobles de almacenamiento; no se atribuye una revisión visual de todos los estados de concursos reales. |
| 6. «Un cierre cambia la vista sin depender de la caché.» | Al avanzar el reloj controlado, un concurso vencido deja de tratarse como abierto incluso con cálculo cacheado. | `test_cache_matching.py::test_expiration_computed_even_with_cached_rows`, con fecha controlada. No se alteró el cierre de un concurso de la instalación personal. |
| 7. «MongoDB conserva los avances cuando el proceso se interrumpe.» | Reiniciar API conserva catálogo/sesión y revocación; otro worker recupera el job con checkpoint; un token vencido no escribe. | `test_restart_integration.py` y `test_worker_recovery_integration.py`: procesos reales y transacciones con MongoDB local autenticado. |
| 8. «El arranque local incluye un worker supervisado.» | La API reemplaza a su worker caído y lo detiene al cerrar, respetando procesos ajenos. | Nueva prueba real `test_runtime_integration.py`; corrección de ciclo de vida explicada abajo. |

Para exponer, leer cada paso, mostrar su pantalla o prueba vinculada y explicar su límite. Si se desea además una demostración en vivo, usar datos sintéticos y una base exclusiva; la disponibilidad actual de SICOP no forma parte de esta memoria textual.

## Revisión visual y de formularios · NLC-03

Navegador integrado de Codex, escritorio **1366 × 900** y vista móvil **390 × 844**. API y MongoDB propios en puertos temporales; cuenta, empresa e ítem ficticios. API con `--no-worker` para evitar consultas a la fuente durante la revisión.

| Comprobación ejecutada | Resultado observado |
|---|---|
| Login vacío e incorrecto en escritorio; credenciales incorrectas en móvil | Campo obligatorio inválido; error «Credenciales inválidas» legible. |
| Teclado del login | Tab desde usuario llevó el foco a contraseña. |
| Empresa y borrador en escritorio | Nombre vacío inválido; sector y especialidad seleccionables; al regresar, la especialidad seguía seleccionada; confirmación mostró el perfil en el radar. |
| Catálogo en escritorio | Nombre vacío inválido; guardado de un ítem mostró su tarjeta. |
| Edición y cancelación móvil | Nombre/palabras clave precargados; cancelar un cambio sin guardar conservó el nombre original. |
| Validación y teclado móvil | Nombre vacío recibió foco y permaneció inválido; Tab avanzó a descripción; Enter sobre «Actividad» abrió la pantalla. Un límite de 501 concursos fue rechazado por rango. |
| Radar vacío en ambas vistas | Explica que no existe consulta exitosa y que el corpus no representa todo SICOP; no anuncia una actualización inexistente. |
| Composición visual | Capturas revisadas; radar y catálogo sin desbordamiento horizontal de la página (1366/1366 y 390/390 px). Navegación móvil horizontal accesible por teclado. Logout volvió al login. |

Evidencia sintética revisada antes de publicar:

- [Radar de escritorio](radar-escritorio.png).
- [Catálogo móvil](catalogo-movil.png).
- [Acceso inválido móvil](acceso-invalido-movil.png).

Es una revisión básica del entorno elegido. No certifica accesibilidad, todos los tamaños, todos los formularios ni todos los navegadores. Edge no estuvo disponible para control automatizado; no se atribuye una prueba en Edge.

## Supervisión local · NLC-05

La nueva prueba arranca una API real y un worker independiente con otra instalación en la misma base temporal. Comprueba salud, identifica el hijo de la API, lo termina con SIGKILL y observa un PID nuevo sin perder disponibilidad. Envía SIGTERM a la API, espera que desaparezcan sus workers y verifica que el independiente siga activo. Al terminar limpia únicamente sus procesos.

La prueba descubrió que Uvicorn retransmite SIGTERM antes de salir de `uvicorn.run`. La limpieza externa podía quedar sin ejecutar. El worker ahora pertenece al **lifespan de FastAPI**, que termina antes de esa retransmisión. Se conserva el comportamiento `--no-worker` y modo servidor; crear la app directamente no inicia procesos por defecto. La señal puede producir código de salida `-15` en POSIX aun con limpieza ordenada: la comprobación decisiva es que el worker propio desaparezca y el ajeno sobreviva.

```bash
# Modo local: API y worker supervisado. Ctrl+C cierra ambos.
uv run nexolicit api

# Alternativa nativa: ejecutar cada comando en una terminal distinta.
uv run nexolicit api --no-worker
uv run nexolicit worker
```

Detener cada proceso independiente con Ctrl+C en su terminal. Un SIGKILL a la API no permite ejecutar limpieza; los leases de MongoDB siguen protegiendo los jobs. La prueba demuestra apagado por SIGTERM y recuperación del worker, no limpieza garantizada frente a caída del sistema.

## Límites de la entrega

No se ejecutó una nueva consulta SICOP ni un E2E único de fuente viva. Las decisiones y el cambio de cierre se sustentan en pruebas controladas, no en una sesión visual con concursos reales. La memoria ofrece trazabilidad de esas comprobaciones sin convertirlas en evidencia de producción.

Docker, Atlas como segundo entorno, Redis real, evaluación humana por pares, estudios con empresas y comparables siguen siendo ampliaciones opcionales. El [benchmark académico](../benchmarks/matching-academic.json) usa un doble en memoria y 100/1.000 concursos; no mide latencia real de Redis ni el pipeline completo. Las historias verificadas siguen sujetas a revisión y aceptación del PR.
