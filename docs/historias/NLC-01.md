## Historia
Como estudiante, quiero validar una muestra acotada de SICOP y modelar sus datos para justificar la procedencia y las decisiones de persistencia.

## Alcance de la entrega universitaria
Revisión autorizada el 18 de octubre de 2026. Los criterios siguientes delimitan la entrega obligatoria. MongoDB real puede ser local autenticado con replica set o Atlas. Redis es caché opcional; Docker es opcional.

## Criterios de aceptación
- [x] Registrar una consulta real pequeña con fecha, endpoints y límites; admitir evidencia previa reproducible.
- [x] Conservar fixtures sanitizadas para respuestas válidas, vacías y bloqueadas, sin credenciales ni anexos crudos.
- [x] Documentar identificadores, secuencia vigente, zona horaria asumida y campos desconocidos; conservar importes con Decimal.
- [x] Distinguir precios presupuestados, presentados y adjudicados; indicar explícitamente que RF-16 no se implementa en la entrega obligatoria.

## Ampliaciones opcionales · no bloquean la entrega
- Validación exhaustiva del proveedor, cobertura histórica completa y fuente final de adjudicación por línea.

## Dependencias
Ninguna.

## Trazabilidad
RF-03–06, RF-15/16 condicionado.

## Evidencia y estado
Cliente y modelos en src/nexolicitcr/sicop.py y models.py; muestras del 17/10 en docs/source-validation.md. Esta entrega no repite ni convierte esas observaciones en cobertura total.

Las casillas verificadas describen evidencia técnica; no cierran automáticamente esta issue ni afirman que una propuesta esté fusionada. Los cambios de esta revisión se preparan en la rama `codex/entrega-universitaria` para revisión.

Alcance vigente: [docs/alcance-academico.md](https://github.com/EstebanS3/NexoLicitCR/blob/codex/entrega-universitaria/docs/alcance-academico.md). Se conserva el [texto anterior de las historias](https://github.com/EstebanS3/NexoLicitCR/blob/codex/entrega-universitaria/docs/historias/archivo/2026-10-18-antes-del-ajuste.json) como trazabilidad; los requisitos retirados no se dan por implementados.
