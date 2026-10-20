# NexoLicitCR: de la búsqueda a la oportunidad

**Automatizamos la búsqueda. Tu PYME construye el futuro.**

Documentación integral de producto, experiencia, arquitectura y operación. Esta edición combina una propuesta comercial para presentar el proyecto con una referencia técnica para entenderlo y mantenerlo.

- **Base documentada:** rama `dev`, commit `4c91af4`, paquete `0.1.0`.
- **Fecha editorial:** 18 de octubre de 2026, Costa Rica.
- **Fuentes:** código del repositorio, pruebas y documentos de validación existentes. No se realizó una nueva consulta a SICOP para redactar la documentación.

**Alcance de entrega vigente:** [entrega universitaria](alcance-academico.md) e [historias revisadas](historias/README.md). Docker es opcional; la evaluación con empresas, los comparables y la validación extensa de infraestructura son ampliaciones. La evidencia de esta revisión se registra en [planning-status.md](planning-status.md); las cifras editoriales de abajo conservan su contexto histórico.

## Recorrido de lectura

| Capítulo | Contenido | Lectura recomendada para |
|---|---|---|
| [00. Visión y propuesta de valor](guia/00-vision-y-propuesta.md) | Problema, promesa, público, diferenciación y presentación comercial. | Presentación, evaluación y conversación con empresas. |
| [01. Producto y experiencia](guia/01-producto-y-experiencia.md) | Casos de uso, recorrido funcional, estados y demostración. | Personas usuarias y quienes presentan la demo. |
| [02. Arquitectura y datos](guia/02-arquitectura-y-datos.md) | Módulos, MongoDB, consistencia, jobs, documentos, matching, Redis y seguridad. | Desarrollo y defensa de Bases de Datos Avanzadas. |
| [03. Instalación, operación y validación](guia/03-instalacion-operacion-y-validacion.md) | Entornos, configuración, comandos, rutas, recuperación y pruebas. | Instalación, mantenimiento y diagnóstico. |
| [04. Evolución y evaluación](guia/04-evolucion-y-evaluacion.md) | Roadmap propuesto, métricas, hipótesis comerciales y guion de exposición. | Planificación de la próxima etapa y defensa académica. |

## Cómo interpretar la documentación

Las funciones disponibles se describen a partir del código de la revisión indicada. Los ejemplos de empresas son ficticios. Las posibilidades comerciales, fases y métricas futuras son propuestas. Los reportes de validación previos conservan sus fechas, muestras y límites; no se presentan como pruebas ejecutadas nuevamente para esta edición.

La afinidad ayuda a priorizar una revisión y no establece elegibilidad. La consulta a SICOP tiene alcance acotado. La aplicación registra ofertas presentadas; no importa adjudicaciones finales verificadas. La instalación actual corresponde a una empresa y una cuenta administradora.

## Validación de esta entrega

El pull de `origin/dev` se completó por fast-forward desde `7f333bd` hasta `4c91af4`. La documentación se redactó después de esa actualización.

Verificaciones del 18 de octubre de 2026:

| Comprobación | Resultado y alcance |
|---|---|
| Suite local sin integración | **329 aprobadas, 7 excluidas**, Python 3.12.15; 6,84 segundos. |
| Comando utilizado | `PYTHONPATH=src .venv/bin/python -m pytest -m 'not integration'`. El entorno existente necesitó la ruta de fuentes porque el paquete no estaba instalado en él. |
| Avisos de pruebas | 1.565 avisos de deprecación de dependencias; no fueron fallos. |
| Ruff del proyecto | Lint y formato correctos en los 45 archivos de aplicación, pruebas y scripts. |
| Enlaces Markdown | Destinos relativos de los cinco capítulos y de este índice comprobados. |
| Archivos publicables | Comprobación automatizada del repositorio aprobada. |

No se ejecutaron las siete pruebas de integración ni nuevas consultas a SICOP, Atlas o Redis real en esta entrega.

## Mantener la documentación

Los cinco capítulos se mantienen en [guia/](guia/). Al actualizar una capacidad, contrastar el texto con su implementación, conservar la distinción entre funciones disponibles y propuestas, y registrar la revisión de código utilizada.

Los diagramas están escritos en Mermaid dentro de los capítulos. Revisar su representación, los enlaces relativos y los ejemplos de comandos junto con los cambios. La evidencia histórica conserva sus fechas; una nueva medición debe indicar su entorno y alcance.

## Referencias complementarias

- [README del proyecto](../README.md).
- [Arquitectura original](architecture.md).
- [Operación original](operations.md).
- [Descubrimiento guiado](guided-discovery.md).
- [Taxonomía comercial](taxonomy.md).
- [Validación de SICOP](source-validation.md).
- [Revisión de OCR](ocr-review.md).
- [Estado histórico del planning](planning-status.md).

Los documentos históricos son evidencia de su fecha. Ante diferencias sobre el comportamiento actual, contrastar con el código de la revisión documentada y con esta guía.
