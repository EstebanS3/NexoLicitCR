# Borrador de la presentación final

Presentación de **12 diapositivas**, en español, para la entrega **v0.9.0** de NexoLicitCR.

- [PowerPoint editable](NexoLicitCR_presentacion_final.pptx): texto, diagrama de arquitectura y notas del presentador editables. Las capturas conservan su imagen original.
- [Copia PDF](NexoLicitCR_presentacion_final.pdf): versión para lectura y proyección.
- [Notas para exponer](notas_exposicion.md): recorrido, tiempos sugeridos, límites y fuentes de cada diapositiva.
- [Fuente de la presentación](fuente_presentacion.mjs): composición reproducible con `@oai/artifact-tool`.
- [Video de demostración de 4:44](../demo/NexoLicitCR_demo.mp4) · [Demo de cliente con SICOP de 4:55](../demo-sicop/NexoLicitCR_cliente_SICOP.mp4).

El hilo conductor es **Brújula TI**, una empresa ficticia. Las capturas muestran la aplicación con datos preparados para la demostración. Los materiales distinguen los resultados actuales de lógica y HTTP de las comprobaciones históricas de integración. El roadmap contiene propuestas posteriores a la entrega.

## Uso durante la exposición

Abrir el PPTX en una aplicación compatible y activar la vista del presentador para leer las notas. La narración sugerida ocupa aproximadamente 10-12 minutos, más el video de 3-5 minutos. Ajustar esos tiempos al espacio asignado al grupo.

El enlace del video dentro de la presentación usa una ruta relativa al MP4 incluido en el repositorio. Conservar las carpetas `presentacion/` y `demo/` dentro de `docs/entrega/`. Si el visor bloquea enlaces a archivos locales, abrir el MP4 directamente.

## Regeneración

La fuente requiere el runtime de artefactos de Codex, `@oai/artifact-tool`, Python, LibreOffice headless y las herramientas de finalización de la habilidad Presentations. No requiere `python-pptx`.

1. Crear `var/presentation-build/` dentro del repositorio.
2. Copiar `fuente_presentacion.mjs` allí con el nombre `build.mjs`.
3. Hacer que `node_modules` de esa carpeta resuelva los paquetes del runtime de Codex.
4. Ejecutar `node build.mjs` para generar el borrador y las vistas PNG privadas.
5. Ejecutar `node build.mjs --final` para validar y exportar PPTX/PDF. Usar un valor nuevo de `NEXO_BUILD_REVISION` en cada revisión. El proceso conserva la salida validada en una carpeta privada y copia los archivos finales a la carpeta de entrega.

La fuente detecta la raíz cuando reside en `var/presentation-build/` o en `docs/entrega/presentacion/`. Las rutas predeterminadas corresponden al runtime empleado en esta entrega. Se pueden ajustar con `NEXO_PRESENTATION_SKILL`, `NEXO_RUNTIME_PYTHON` y `NEXO_RUNTIME_SOFFICE`. `NEXO_REPO_ROOT` permite indicar una raíz de repositorio diferente. `NEXO_BUILD_REVISION` identifica cada borrador privado.

La versión final exige que existan las capturas `03-catalogo.png`, `04-radar.png`, `06-documento.png` y `08-actividad.png` en `docs/assets/demo/`. Los borradores permiten imágenes temporales de la validación anterior para revisar la composición. La exportación final rechaza capturas faltantes.
