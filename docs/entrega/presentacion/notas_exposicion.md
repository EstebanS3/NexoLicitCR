# Notas para la presentación final

Borrador v0.9.0. 12 diapositivas. Duración hablada aproximada: 10-12 minutos, más el video de 3-5 minutos.

## 1. NexoLicitCR

Presentar el proyecto como una herramienta para organizar la primera revisión de concursos públicos. La PYME ficticia Brújula TI sirve de hilo conductor. La promesa se limita a orientar la revisión con razones y conservar decisiones. Duración sugerida: 30 segundos.

Fuentes del repositorio: README.md; docs/guia/00-vision-y-propuesta.md; docs/assets/nexolicitcr-logo.png.
Fecha editorial: 21 de octubre de 2026, Costa Rica. Escenario Brújula TI completamente ficticio.

## 2. Problema y usuarios

Explicar que la revisión reúne capacidades de la empresa, metadatos de concursos, documentos y plazos. La persona necesita saber qué merece abrir y por qué. El proyecto plantea reducir esa revisión repetitiva, pero todavía no atribuye un ahorro de tiempo medido ni resultados comerciales. Una cuenta administradora controla una empresa por instalación. Duración sugerida: 50 segundos.

Fuentes del repositorio: README.md; docs/guia/00-vision-y-propuesta.md; docs/architecture.md.
Fecha editorial: 21 de octubre de 2026, Costa Rica. Escenario Brújula TI completamente ficticio.

## 3. Alcance

Mencionar además las sesiones persistentes, protección CSRF y cambios del catálogo con revisión de concurrencia. La afinidad y las sugerencias usan reglas deterministas. El histórico conserva ofertas presentadas, no adjudicaciones finales. La ingesta cubre el corpus guardado y consultas acotadas. Duración sugerida: 50 segundos.

Fuentes del repositorio: README.md; docs/alcance-academico.md; docs/architecture.md; src/nexolicitcr/matching.py.
Fecha editorial: 21 de octubre de 2026, Costa Rica. Escenario Brújula TI completamente ficticio.

## 4. Perfil y catálogo

La captura procede de la aplicación con datos ficticios de la demo. Mostrar que el perfil ayuda a proponer capacidades y que la persona confirma lo que realmente ofrece. El catálogo tiene su propia revisión y no debe perderse por sobrescrituras concurrentes. Enlazar la idea de capacidad comercial con términos y códigos que después usará el radar. Duración sugerida: 50 segundos.

Fuentes del repositorio: docs/assets/demo/03-catalogo.png; docs/guided-discovery.md; src/nexolicitcr/storage.py; src/nexolicitcr/templates/catalog.html.
Fecha editorial: 21 de octubre de 2026, Costa Rica. Escenario Brújula TI completamente ficticio.

## 5. Radar explicado

Abrir el concurso de redes de datos de la demo y señalar una razón visible. Los resultados derivan de reglas explícitas y versionadas. La afinidad no mide probabilidad de adjudicación ni acredita elegibilidad. Una consulta acotada tampoco demuestra cobertura de todo SICOP. El sistema conserva procedencia y estados desconocidos para que la persona pueda revisar. Duración sugerida: 60 segundos.

Fuentes del repositorio: docs/assets/demo/04-radar.png; src/nexolicitcr/matching.py; docs/taxonomy.md; docs/source-validation.md.
Fecha editorial: 21 de octubre de 2026, Costa Rica. Escenario Brújula TI completamente ficticio.

## 6. Documentos y seguimiento

Mostrar un anexo del escenario ficticio y su texto por página. El original reside en GridFS. La aplicación comprueba integridad y puede advertir extracción parcial. Luego explicar la acción de seguimiento que el video muestra: la colección decisions conserva la elección incluso si cambia el catálogo o se recalcula la afinidad. No equiparar texto extraído con comprensión completa del pliego. Duración sugerida: 60 segundos.

Fuentes del repositorio: docs/assets/demo/06-documento.png; docs/assets/demo/07-seguimiento.png; src/nexolicitcr/documents.py; src/nexolicitcr/extractor.py; docs/architecture.md.
Fecha editorial: 21 de octubre de 2026, Costa Rica. Escenario Brújula TI completamente ficticio.

## 7. Arquitectura

Recorrer el diagrama desde la interfaz. La aplicación consulta MongoDB como fuente de verdad y puede reutilizar un cálculo en Redis. El worker procesa trabajos persistidos y obtiene metadatos y documentos desde la fuente. GridFS forma parte del almacenamiento MongoDB, aunque aparece como responsabilidad separada para explicar los binarios. Redis resulta opcional. INSTALLATION_ID separa trabajos y caché, pero no convierte una base compartida en un servicio multiempresa. Duración sugerida: 70 segundos.

Fuentes del repositorio: docs/architecture.md; src/nexolicitcr/web.py; src/nexolicitcr/jobs.py; src/nexolicitcr/storage.py; src/nexolicitcr/cache.py.
Fecha editorial: 21 de octubre de 2026, Costa Rica. Escenario Brújula TI completamente ficticio.

## 8. Datos y transacciones

Relacionar esta decisión con una necesidad humana: poder saber qué cambió sin dejar un estado vigente separado de su historial. MongoDB requiere un replica set o Atlas para estas transacciones. Los importes decimales se serializan como texto y las fechas desconocidas permanecen explícitas. El catálogo usa una revisión monotónica y las decisiones persisten en su propia colección. Los binarios se cargan antes de publicar su referencia y el sistema dispone de diagnóstico de huérfanos. Duración sugerida: 65 segundos.

Fuentes del repositorio: docs/architecture.md; src/nexolicitcr/storage.py; src/nexolicitcr/ingestion.py; tests/test_atlas_integration.py.
Fecha editorial: 21 de octubre de 2026, Costa Rica. Escenario Brújula TI completamente ficticio.

## 9. Jobs y caché

La pantalla de actividad muestra alcance y estado de las consultas. Los checkpoints preservan avance y los tokens del lease impiden que un worker vencido publique. HTTP 429 provoca una pausa de la fuente y las consultas fallidas o canceladas pueden reanudarse con sus límites. La caché usa revisión del catálogo, reglas y generación del corpus para invalidación. Las decisiones y los cierres se comprueban al responder. El video muestra estados preparados de demo y no fuerza caídas de infraestructura. Duración sugerida: 60 segundos.

Fuentes del repositorio: docs/assets/demo/08-actividad.png; docs/operations.md; src/nexolicitcr/jobs.py; src/nexolicitcr/cache.py; tests/test_worker_recovery_integration.py.
Fecha editorial: 21 de octubre de 2026, Costa Rica. Escenario Brújula TI completamente ficticio.

## 10. Evidencia

La revisión actual del 21 de octubre de 2026 ejecutó pytest con la selección not integration: 365 aprobadas y 9 deseleccionadas. Las 9 pruebas nativas contra Atlas proceden del informe histórico del 18 de octubre de 2026. Ese informe registra además 8 pruebas dentro de Docker y una comprobación de fallback con Redis real. Las dos ejecuciones tienen fechas y entornos distintos. Ninguna constituye una medición del rendimiento de producción. El microbenchmark disponible usa datos sintéticos y un doble de caché en memoria, por eso la presentación no promete latencias de producción. Las pruebas no miden la precisión comercial del matching ni el ahorro de tiempo para empresas. Duración sugerida: 60 segundos.

Fuentes del repositorio: Ejecución de pytest -m not integration, 21/10/2026; docs/validacion/docker-atlas.md; docs/validacion/README.md; docs/benchmarks/matching-academic.json.
Fecha editorial: 21 de octubre de 2026, Costa Rica. Escenario Brújula TI completamente ficticio.

## 11. Roadmap

Las prioridades son propuestas posteriores a v0.9.0 y no compromisos ya implementados. La siguiente evidencia de producto debe incluir tareas observadas con empresas y un protocolo de relevancia. Ampliar formatos requiere límites de recursos y regresiones. Antes de comparables económicos hace falta validar una fuente de adjudicaciones por línea. Una evolución multiempresa necesita un diseño explícito de usuarios y aislamiento. Duración sugerida: 50 segundos.

Fuentes del repositorio: docs/guia/04-evolucion-y-evaluacion.md; docs/guided-discovery.md; docs/alcance-academico.md.
Fecha editorial: 21 de octubre de 2026, Costa Rica. Escenario Brújula TI completamente ficticio.

## 12. Demo y cierre

Reproducir el video de la entrega, de 3 a 5 minutos, desde su carpeta local. El escenario y sus instituciones son ficticios. La demo usa una cuenta propia y una base exclusiva. Al cerrar, recordar el hilo completo: la empresa confirma su oferta, revisa una razón, abre evidencia y conserva la decisión. El repositorio incluye instrucciones para repetir el escenario. Reservar preguntas sobre transacciones, recuperación y límites de la fuente. Duración hablada sugerida: 25 segundos, además del video.

Fuentes del repositorio: README.md; docs/entrega/demo/; docs/architecture.md.
Fecha editorial: 21 de octubre de 2026, Costa Rica. Escenario Brújula TI completamente ficticio.
