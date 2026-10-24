# Validación de entrega · v0.9.0

Fecha: 21 de octubre de 2026, Costa Rica. Entorno: macOS ARM64, Python 3.12.15, MongoDB Community 8.0.32 como replica set autenticado de un nodo. El alcance es una entrega local reproducible con materiales de exposición; no una certificación de producción.

## Instalación en entorno nuevo

Se copió el código publicable a una carpeta limpia, sin `.env`, datos ni entorno virtual anterior. Se instaló `uv.lock` usando la caché disponible, sin resolver otras versiones. No se presenta como clon de una release remota aún no publicada.

`uv sync --frozen --offline` instaló las dependencias y el paquete 0.9.0. La instalación editable encontró una particularidad de este macOS: los archivos `.pth` quedaban marcados como ocultos y Python los omitía. La alternativa comprobada fue:

```bash
uv sync --frozen --no-editable --offline
uv run --no-sync nexolicit --help
uv run --no-sync pytest -m 'not integration' -q
```

`--offline` es apropiado únicamente si las dependencias ya están en caché; omitirlo en la primera instalación. La ejecución real utilizó los ejecutables del entorno nuevo después de sincronizar, equivalente a `uv run --no-sync`.

Resultado en esa copia: **365 pruebas aprobadas, 9 de integración deseleccionadas**, sin fallos. Se emitieron advertencias de deprecación de dependencias; se conservaron en los logs privados. La CLI del paquete instalado respondió correctamente. Estas pruebas verifican lógica/HTTP y dobles; no sustituyen la integración física histórica.

## Escenario y recorrido real

- Base exclusiva `nexolicit_demo_v090`, MongoDB autenticado en `127.0.0.1:27019` y API en `http://localhost:8010`.
- Cuenta de demostración creada con contraseña aleatoria guardada únicamente en `var/demo/access.json`.
- Empresa Brújula TI, tres ítems de catálogo, cinco concursos ficticios y tres PDF almacenados en GridFS.
- El script comprueba la propiedad de directorio, proceso y base antes de escribir. Rechaza la base o los puertos de la instalación existente.
- Ocho pruebas nuevas verifican repetibilidad, límites de aislamiento, evidencia PDF y bloqueo de consultas externas.
- Navegador Playwright 1.62.1 descargado para esta tarea, con perfil temporal vacío. No se utilizó el perfil personal de Chrome ni sesiones del usuario.
- Peticiones del navegador limitadas a `localhost:8010`; el servidor demo bloquea los endpoints de consulta externa y no inicia el worker.
- Recorrido: login → perfil → catálogo → radar → filtro → detalle → documento → guardar seguimiento y nota → comprobar persistencia → actividad.

El ensayo terminó sin errores JavaScript, respuestas HTTP fallidas ni desbordamiento horizontal en la resolución revisada de 1440 × 900. La decisión registrada se comprobó en el detalle y en el filtro de seguimiento. La primera toma sufrió una interrupción y se descartó; el proceso de montaje rechaza tomas cuyas escenas difieran más de tres segundos del guion.

## Materiales y controles

- README, CHANGELOG, escenario, guion, video, subtítulos, capturas, presentación y ficha enlazados desde [el índice](README.md).
- Presentación editable de 12 diapositivas con notas; PDF con texto seleccionable. Diagramas conservados como objetos editables en el PPTX.
- Revisión visual de las 12 páginas del PDF y de las capturas de la aplicación.
- `ruff check src tests scripts`, `ruff format --check src tests scripts` y `git diff --check` aprobados.
- `scripts/check_publishable.py` aprobado: los medios revisados se registran por SHA-256 exacto; cualquier modificación requiere una nueva revisión.
- MP4 H.264 de **284,4 segundos**, 1440 × 900, audio AAC y subtítulos españoles. Decodificación completa sin errores; 11 escenas con desviación máxima de **0,002 segundos** frente al guion.
- YAML válido y enlaces locales de la documentación comprobados. El [registro estructurado](VALIDACION.json) conserva resultados y hashes de los entregables revisados.
- Los intermedios, credenciales, datos MongoDB y perfiles del navegador permanecen en `var/`, fuera de Git.

## Límites

La actividad `DEMO-CARGA-LOCAL` representa una carga preparada, no una consulta real a SICOP. Los códigos con prefijo 999, instituciones y montos del escenario son inventados. El video muestra extracción digital ya preparada; no ejecuta OCR ni provoca una caída de Redis durante la grabación. La afinidad no mide elegibilidad ni precisión comercial.

Las nueve pruebas de integración se conservan como evidencia histórica fechada en las [memorias previas](../validacion/README.md); no se afirma que hayan vuelto a ejecutarse en esta entrega. El recorrido de demo sí utiliza una base MongoDB física.

`portal.yml` es provisional por decisión acordada y debe contrastarse con la plantilla oficial de la sección 7 antes de enviarlo al portal. Al realizar esta validación inicial, el tag de entrega era local y todavía no se había efectuado push, despliegue ni publicación remota. Esta memoria conserva los resultados de ese momento.
