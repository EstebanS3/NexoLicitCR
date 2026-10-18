## Historia
Como usuario, quiero consultar primero los concursos guardados y pedir una actualización acotada, viendo cuándo se verificaron y si la consulta falló.

## Alcance de la entrega universitaria
Revisión autorizada el 18 de octubre de 2026. Los criterios siguientes delimitan la entrega obligatoria. MongoDB real puede ser local autenticado con replica set o Atlas. Redis es caché opcional; Docker es opcional.

## Criterios de aceptación
- [x] Reutilizar el corpus al confirmar el perfil; consultar SICOP solo mediante una acción explícita.
- [x] Conservar rubro, límite y revisión de perfil en un job idempotente; ofrecer consultas pequeñas de 10 o 25 concursos por rubro para la demo.
- [x] Distinguir bloqueo/403, límite/429, 5xx, esquema inválido y respuesta vacía; usar reintentos acotados.
- [x] Mantener versiones por hash, decimales y desconocidos; una reingesta idéntica no duplica y el cierre nunca se sustituye por la apertura.
- [x] Reconsultar activos guardados dentro del límite y conservar pendientes al reanudar.
- [x] Mostrar última consulta exitosa y su alcance; advertir un intento posterior incompleto o fallido sin ocultar el corpus existente.
- [x] Mostrar la última verificación de cada concurso, incluso con la caché caliente, y declarar cobertura acotada.

## Ampliaciones opcionales · no bloquean la entrega
- Barrido histórico completo, actualización continua, cobertura exhaustiva por especialidad y carga de 10.000 concursos.

## Dependencias
#1, #2, #3. Integración con la cola de #5.

## Trazabilidad
RF-03/04/10; RNF-03.

## Evidencia y estado
Cliente, jobs, versiones y pruebas de radar/actualidad. Los ensayos de regresión usan fixtures; las observaciones de SICOP real están documentadas en NLC-01.

Las casillas verificadas describen evidencia técnica; no cierran automáticamente esta issue ni afirman que una propuesta esté fusionada. Los cambios de esta revisión se preparan en la rama `codex/entrega-universitaria` para revisión.

Alcance vigente: [docs/alcance-academico.md](https://github.com/EstebanS3/NexoLicitCR/blob/codex/entrega-universitaria/docs/alcance-academico.md). Se conserva el [texto anterior de las historias](https://github.com/EstebanS3/NexoLicitCR/blob/codex/entrega-universitaria/docs/historias/archivo/2026-10-18-antes-del-ajuste.json) como trazabilidad; los requisitos retirados no se dan por implementados.
