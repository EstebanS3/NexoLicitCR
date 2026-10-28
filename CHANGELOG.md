# Changelog

Este archivo registra cambios verificables del repositorio y conserva los nombres de los tags históricos `semana-1` y `semana2`. Los commits intermedios no se presentan como versiones publicadas. La versión `0.1.0` del paquete anterior era metadato de desarrollo, no evidencia de una release homónima.

## [Sin publicar]

- Incorporación de los dos MP4, con enlaces desde el README y las guías de entrega, ficha provisional del portal y controles por SHA-256. La excepción de Git se limita a estos dos archivos; las grabaciones intermedias permanecen privadas.

- Segunda demo de cliente con empresa ficticia, consultas reales de SICOP, comentarios privados y seguimiento; esperas aceleradas con música original.
- Corrección de la columna de evidencia del expediente: textos largos con espacios no separables ya no estrechan las condiciones hasta volverlas ilegibles. Verificada a 1440, 1024 y 390 píxeles.
- Entorno de grabación adicional aislado en los puertos 8011/27020, sin precargar concursos.

## [0.9.0] — 2026-10-21

Versión de entrega académica. El tag local `v0.9.0` identifica el commit `86510cc` de los materiales iniciales validados. La segunda demo de SICOP y la integración posterior de `dev` quedan fuera de ese tag y se registran en esta rama; no se ha creado una release de GitHub.

### Agregado

- Perfil de empresa guiado, confirmación de sugerencias y varias especialidades; el catálogo manual permanece independiente.
- Registro web de la primera cuenta, cerrado después de crear el único administrador de la instalación.
- Radar con razones por términos/códigos, evidencia por página y decisiones de seguimiento con notas.
- Trabajos durables de SICOP con leases, checkpoints, cancelación, reanudación y pausas persistentes ante límites de la fuente.
- Descarga de anexos a GridFS, extracción digital/OCR español y estados de evidencia parcial.
- Caché Redis opcional con aislamiento por instalación y base, invalidación versionada y fallback.
- Docker Compose con web, worker e inicialización de índices contra Atlas externo; perfil Redis opcional.
- Guía integral de producto, arquitectura, instalación, operación, validación y evolución.
- Paquete de exposición: README reorganizado, escenario de demostración sintético, capturas, guion/video, borrador de presentación y ficha `portal.yml` provisional.
- Base de demostración autenticada y aislada, con usuario propio, empresa Brújula TI, cinco concursos ficticios y tres PDF; ocho pruebas de aislamiento y repetibilidad.
- Video de 4:44 con interacciones reales, narración en español y subtítulos, grabado en un navegador independiente con perfil temporal vacío.

### Corregido

- Persistencia y revocación de sesiones comprobadas a través de reinicios de la API.
- Recuperación de trabajos tras caída del worker, con comprobación de token y lease vigente antes de escribir.
- Supervisión del worker local durante el ciclo de vida de la API.
- Recuperación de documentos interrumpidos o con referencia a un original ausente; verificación de contenido y tamaño antes de publicar.
- Coherencia entre radar y detalle al señalar evidencia incompleta y consulta reciente.
- Compatibilidad del extractor con Windows y mejoras de OCR, orientación y coincidencias de texto cortado por guion.
- Falsos positivos del control de privacidad en cuentas de CI y endurecimiento de archivos publicables.

### Documentado y validado previamente

- La muestra de SICOP y sus límites se registraron en `docs/source-validation.md` el 17 de octubre.
- Las memorias del 18 de octubre registran pruebas con MongoDB real, revisión visual y el recorrido Docker/Atlas. Se conservan sus fechas y alcance; no equivalen a una ejecución nueva de toda la suite.
- El alcance académico distingue los requisitos obligatorios de Docker, segundo backend, Redis real y evaluación con empresas como ampliaciones opcionales.
- Las ofertas presentadas siguen separadas de las adjudicaciones finales; los comparables requieren una fuente validada.

### Trazabilidad

Los cambios de aplicación anteriores a esta preparación están respaldados, entre otros, por:

| Fecha | Commit | Cambio |
|---|---|---|
| 2026-10-13 | `94d6a65` | Radar, jobs durables, documentos y caché opcional. |
| 2026-10-14 | `75c6d2f` | Descubrimiento confirmado y worker local automático. |
| 2026-10-16 | `c9d7cc3` | Perfil guiado, reanudación de cola y backoff de SICOP. |
| 2026-10-16 | `205ed59` | Registro de cuenta inicial desde la página de entrada. |
| 2026-10-17 | `fa9eacf`, `12278a3`, `1c633ed` | Fuente SICOP, persistencia tras reinicio y recuperación del worker. |
| 2026-10-17 | `f3ed61f`, `feb144c` | Extracción documental, varias especialidades y radar. |
| 2026-10-18 | `d3eff3a`, `5a3fd19`, `118a54b` | Guía integral, recuperación GridFS, alcance y validación académica. |
| 2026-10-18 | `99ac5ae`, `325ed05` | Docker con Atlas y controles de publicación/privacidad. |

### Pendientes conocidos

- Validar los nombres y tipos de campos de `portal.yml` contra la plantilla oficial de la sección 7; la ficha actual es provisional.
- La demo académica utiliza datos sintéticos y no certifica precisión comercial, cobertura exhaustiva de SICOP ni rendimiento de producción.
- Evaluación con empresas, comparables adjudicados, colaboración multiusuario y avisos permanecen en el roadmap.

## [semana2] — 2026-10-20

Tag histórico en `b9d24d5`, incorporación de `dev` a `main` mediante el PR #30. Incluye las correcciones de documentos y de histórico SICOP integradas por los PR #28 y #29, además del trabajo previo de la rama de desarrollo. Se conserva como hito académico, sin convertirlo en una versión semántica.

- Verificación y recuperación de originales GridFS, con extracción de evidencia acotada y estados documentales visibles.
- Histórico de ofertas presentadas de SICOP, separado de adjudicaciones finales, con validación y memoria de resultados.

## [semana-1] — 2026-10-13

Tag histórico real en el commit `5e6afd5`. Se conserva su nombre original, sin atribuirle una versión semántica inventada.

### Agregado

- Base del monolito Python con FastAPI, Jinja2 y CLI.
- Catálogo empresarial e ingesta inicial de SICOP con MongoDB.
- Identidad visual, logotipo y presentación del proyecto para PYMES.
- Soporte de MongoDB local autenticado como replica set, junto con configuración Atlas.

### Corregido

- Reporte del backend MongoDB seleccionado en la comprobación de disponibilidad.
- Conservación del origen correcto al enviar formularios desde el navegador.

Historial de referencia: `cbe38c0`, `85a2dca`, `cd5f092`, `dac1d1d` y `4057c04`.

## Inicio del repositorio — 2026-10-06

El commit `f4577f2` registra el inicio del proyecto. No se identificó un tag de release para este hito.
