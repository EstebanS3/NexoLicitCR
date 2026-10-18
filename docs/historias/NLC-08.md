## Historia
Como estudiante, quiero demostrar que una caché acelera cálculos sin convertirse en la autoridad ni alterar decisiones o resultados.

## Alcance de la entrega universitaria
Revisión autorizada el 18 de octubre de 2026. Los criterios siguientes delimitan la entrega obligatoria. MongoDB real puede ser local autenticado con replica set o Atlas. Redis es caché opcional; Docker es opcional.

## Criterios de aceptación
- [x] Funcionar sin REDIS_URL y recuperar resultados desde MongoDB si la caché falla.
- [x] Mantener timeout corto, circuit breaker y fallback ante errores.
- [x] Aislar claves por aplicación, entorno, instalación, base, empresa, revisión de catálogo/perfil, reglas y generación del corpus.
- [x] Invalidar ante cambios confirmados de perfil/catálogo/corpus; un borrador no cambia el perfil confirmado.
- [x] Comparar resultados y decisiones con caché activa, ausente y caída mediante un doble controlado.
- [x] Mantener fechas de verificación actualizadas aunque los matches vengan de caché.
- [x] Registrar el microbenchmark académico de 100 y 1.000 concursos con equivalencia y tipo de backend explícitos; un miss o bypass no cuenta como lectura acelerada.

## Ampliaciones opcionales · no bloquean la entrega
- Servidor Redis real, benchmark de red/extremo a extremo, carga de 10.000 concursos, escalabilidad y SLA de producción.

## Dependencias
#7.

## Trazabilidad
RF-12; RNF-01.

## Evidencia y estado
Cache y pruebas de matching/descubrimiento. El microbenchmark con un doble en memoria debe etiquetarse como tal; no acredita latencia de Redis real.

Las casillas verificadas describen evidencia técnica; no cierran automáticamente esta issue ni afirman que una propuesta esté fusionada. Los cambios de esta revisión se preparan en la rama `codex/entrega-universitaria` para revisión.

Alcance vigente: [docs/alcance-academico.md](https://github.com/EstebanS3/NexoLicitCR/blob/codex/entrega-universitaria/docs/alcance-academico.md). Se conserva el [texto anterior de las historias](https://github.com/EstebanS3/NexoLicitCR/blob/codex/entrega-universitaria/docs/historias/archivo/2026-10-18-antes-del-ajuste.json) como trazabilidad; los requisitos retirados no se dan por implementados.
