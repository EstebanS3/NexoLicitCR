## Historia
Como usuario, quiero entender por qué aparece un concurso y registrar mi decisión, sabiendo si falta evidencia por revisar.

## Alcance de la entrega universitaria
Revisión autorizada el 18 de octubre de 2026. Los criterios siguientes delimitan la entrega obligatoria. MongoDB real puede ser local autenticado con replica set o Atlas. Redis es caché opcional; Docker es opcional.

## Criterios de aceptación
- [x] Combinar perfil confirmado y catálogo manual sin sustituir los ítems existentes.
- [x] Explicar coincidencias mediante términos, producto/servicio, fragmento, documento/página cuando exista y versión de reglas.
- [x] Aplicar exclusiones con cautela ante OCR; comparar códigos solo dentro del mismo sistema, sin equiparar CIIU con SICOP.
- [x] No presentar vencidos/cancelados como abiertos y mostrar fechas desconocidas.
- [x] Mostrar la misma advertencia de evidencia incompleta en radar y detalle si un anexo actual falla, se omite, está en proceso o queda parcial.
- [x] Conservar interés, descarte, seguimiento y notas al cambiar perfil, reingerir y recalcular.
- [x] Ofrecer afinar perfil, filtros o consultar novedades ante cero resultados, sin afirmar ausencia total en SICOP.
- [x] Explicar que la afinidad es orientativa y no demuestra elegibilidad ni probabilidad de ganar.

## Ampliaciones opcionales · no bloquean la entrega
- Generar propuestas de ajustes al perfil a partir del feedback; requerirán diseño, revisión y confirmación explícita.
- IA externa, recomendaciones comerciales y evaluación de utilidad con empresas reales.

## Dependencias
#3, #4, #5, #6.

## Trazabilidad
RF-07/08/09.

## Evidencia y estado
Matching, decisiones y pruebas que comparan completitud entre radar y detalle. El feedback obligatorio se limita a estado y nota; no se presenta como aprendizaje automático.

Las casillas verificadas describen evidencia técnica; no cierran automáticamente esta issue ni afirman que una propuesta esté fusionada. Los cambios de esta revisión se preparan en la rama `codex/entrega-universitaria` para revisión.

Alcance vigente: [docs/alcance-academico.md](https://github.com/EstebanS3/NexoLicitCR/blob/codex/entrega-universitaria/docs/alcance-academico.md). Se conserva el [texto anterior de las historias](https://github.com/EstebanS3/NexoLicitCR/blob/codex/entrega-universitaria/docs/historias/archivo/2026-10-18-antes-del-ajuste.json) como trazabilidad; los requisitos retirados no se dan por implementados.
