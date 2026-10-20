# Revisión del perfil, radar y OCR

Revisión local del 17 de octubre de 2026. Las pruebas externas fueron acotadas;
no constituyen un barrido histórico completo ni una evaluación humana de
precisión de clasificación.

## Cambios implementados

- Selección de 1–8 especialidades de distintos sectores. Sugerencias combinadas
  sin duplicados, servicios editables y confirmación explícita. Se conservan
  borradores, cobertura, exclusiones y servicios personalizados al retroceder,
  reordenar selecciones o editar perfiles anteriores.
- La búsqueda desde el radar permite incluir anexos y lo propone por defecto.
  Antes siempre encolaba con `documents=False`: ese recorrido nunca ejecutaba OCR.
- El host de almacenamiento Oracle previamente verificado está permitido por
  defecto. Una configuración explícita de `DOCUMENT_HOSTS` sigue prevaleciendo.
- OCR español con orientación automática, detección de páginas con encabezado
  digital y cuerpo escaneado, y recuperación mediante OCR si falla la capa de
  texto de un PDF. Se conservan texto digital y evidencia visual útil.
- Los PDF de más de 30 páginas conservan las primeras 30 y se marcan parciales.
  Antes se descartaba toda su extracción. Se mantienen límites de tamaño,
  páginas, tiempo, memoria en Linux y ejecución en un proceso separado.
- Errores diferenciados de Tesseract, español, orientación, Poppler, texto vacío
  y límite de páginas. Los anexos omitidos o fallidos mantienen la afinidad
  como preliminar. Una recuperación exitosa retira el marcador de fallo anterior.
- Los documentos procesados con una versión anterior se reextraen al volver a
  consultarse con anexos. Se retiran páginas antiguas que ya no forman parte de
  la extracción publicada.
- La coincidencia reconoce palabras cortadas con guion al final de línea sin
  inventar un fragmento: conserva la ubicación y el texto original de evidencia.
- Las peticiones de metadatos de anexos respetan la pausa configurada. HTTP 429
  llega a la pausa persistente de la cola; los errores de conexión son controlados.

En este equipo faltaba Tesseract. Se instalaron Tesseract 5.5.3, los modelos
`spa`/`osd` y Poppler. Esos ejecutables deben estar en el PATH del worker.

## Pruebas controladas en todos los sectores

El comando reproducible es:

```bash
uv run python scripts/audit_ocr.py --output artifacts/ocr-audit-final.json
```

Se generaron documentos sintéticos con 65 frases conocidas de las especialidades
de los **19 sectores comerciales**, incluyendo tecnología, salud, educación,
alimentación, transporte, textiles, seguridad y construcción. «Otra actividad»
no tiene vocabulario predefinido y se valida mediante descripción y términos manuales.

| Variante | Casos | Frases recuperadas / esperadas |
|---|---:|---:|
| PDF digital | 19 | 65 / 65 |
| Imagen PNG | 19 | 65 / 65 |
| Imagen JPEG | 19 | 65 / 65 |
| PDF escaneado | 19 | 65 / 65 |
| PDF con encabezado digital y cuerpo escaneado | 19 | 65 / 65 |
| Imagen girada 90 grados | 19 | 65 / 65 |
| Imagen inclinada 3 grados | 19 | 65 / 65 |
| Imagen reducida a 850 × 1100 píxeles | 19 | 65 / 65 |
| **Total** | **152** | **520 / 520** |

Cada caso usa el módulo de extracción real en un proceso separado. Esta medida
es recuperación de frases conocidas en imágenes controladas; **no equivale a
100 % de precisión de OCR ni de clasificación en SICOP**. No cubre escritura
manual, todas las fuentes, todas las tablas, todas las resoluciones ni los
artefactos de compresión presentes en documentos reales.

## Muestra real de SICOP: los tres rubros

Se revisaron los primeros dos anexos disponibles de tres concursos por rubro,
seleccionados del corpus local, con pausas entre peticiones. Se descargaron
archivos a una carpeta temporal y se eliminaron al concluir; los reportes no
conservan texto, archivos originales ni URLs firmadas. No se modificó el corpus
ni el perfil de la empresa durante el diagnóstico.

| Rubro de SICOP | Anexos revisados | PDF compatibles | Páginas recuperadas | Páginas que usaron OCR |
|---|---:|---:|---:|---:|
| Bienes | 5 | 5 | 48 | 1 |
| Obras | 6 | 6 | 125 | 0 |
| Servicios | 5 | 3 | 44 | 4 |
| **Total** | **16** | **14** | **217** | **5** |

Tres PDF de obras tenían 44, 35 y 39 páginas. Antes fallaban completos; con el
cambio se recuperaron sus primeras 30 páginas (90 páginas adicionales), con
`PAGE_COUNT_LIMIT` explícito. Los otros 28 folios siguen pendientes de revisión.
Los dos anexos restantes de servicios no son compatibles con el descargador
PDF/PNG/JPEG; no se presentan como documentos leídos.

Las 5 páginas OCR reales produjeron texto sin error de ejecución. Esto confirma
funcionamiento del motor, pero no mide su tasa de error palabra por palabra:
no existe una transcripción humana de referencia para esta muestra.

## Radar y vocabulario de construcción

Se compararon las reglas anteriores y nuevas sobre los 75 concursos ya guardados,
con el mismo perfil de obra vial y sin cambiar sus servicios ni agregar OCR al
corpus. Las coincidencias pasaron de **2 a 6**. Cuatro casos pasaron de cero a
35 puntos gracias a frases de pavimento, colocación de mezcla asfáltica,
compactación de material granular y colocación de concreto permeable.

Las alternativas de vocabulario ambiguo están restringidas al rubro `obras`.
No se asigna afinidad a todos los concursos de obras por pertenecer al sector
construcción. Edificios, instalaciones eléctricas y otras capacidades se eligen
explícitamente como especialidades adicionales. Se agregó «Obra civil e
infraestructura pública» como opción propia.

## Validación y alcance pendiente

- 326 pruebas sin integración y 4 de integración local aprobadas (330 en total).
- Integración real: transacciones MongoDB, GridFS, OCR nativo y coincidencias con
  referencia a documento/página, con limpieza de los registros propios en una
  base de pruebas exclusiva.
- Ruff, formato, revisión de whitespace y control de archivos publicables aprobados.
- Validación visual en navegador: combinar sectores, editar servicios, volver
  atrás, guardar y editar de nuevo; límite de ocho elecciones y opción de anexos.
- La instalación y los binarios OCR se verificaron en macOS. Se retiró el import
  obligatorio de `resource` en Windows, pero no se ejecutó una prueba en Windows.
- La calidad real de clasificación sigue requiriendo casos etiquetados por humanos.
  La afinidad no confirma elegibilidad, y los formatos no compatibles o páginas
  fuera de los límites deben revisarse en el expediente original.

Reportes locales ignorados por Git: `artifacts/ocr-audit-final.json`,
`artifacts/ocr-real-source-audit.json`, `artifacts/radar-recall-audit.json`.
Para procesar anexos de concursos guardados, iniciar una nueva consulta desde
el radar con la opción de anexos activada. No se dispara una descarga histórica
ilimitada al editar el perfil.
