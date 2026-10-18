## Historia
Como usuario avanzado, quiero consultar ofertas públicas históricas distinguiendo precio presentado de adjudicación final.

## Alcance de la entrega universitaria
Revisión autorizada el 18 de octubre de 2026. Historia opcional; no bloquea la entrega. MongoDB real puede ser local autenticado con replica set o Atlas. Redis es caché opcional; Docker es opcional.

## Criterios de aceptación de la extensión
- [x] Etiquetar el dato como precio presentado y separar la calificación del proveedor.
- [x] Conservar moneda, precio crudo/normalizado, partida, procedencia y desconocidos.
- [x] Distinguir fallo de fuente de una ausencia de ofertas validada.
- [x] Mostrar comparables adjudicados como indisponibles mientras no exista fuente final por línea validada.
- [ ] Revalidar el importador legado contra una muestra real antes de afirmar vigencia de esa fuente.

## Ampliaciones opcionales · no bloquean la entrega
- Toda esta historia es una extensión: su validación externa y los comparables adjudicados no bloquean la entrega universitaria.
- RF-16 requiere una fuente final compatible por producto, línea, unidad y moneda; nunca inferir adjudicación a partir de ofertas.

## Dependencias
#1, #4.

## Trazabilidad
RF-15 opcional; RF-16 fuera de la entrega obligatoria.

## Evidencia y estado
Parser y CLI existentes; no se afirma una revalidación externa nueva ni se habilitan comparables.

Las casillas verificadas describen evidencia técnica; no cierran automáticamente esta issue ni afirman que una propuesta esté fusionada. Los cambios de esta revisión se preparan en la rama `codex/entrega-universitaria` para revisión.

Alcance vigente: [docs/alcance-academico.md](https://github.com/EstebanS3/NexoLicitCR/blob/codex/entrega-universitaria/docs/alcance-academico.md). Se conserva el [texto anterior de las historias](https://github.com/EstebanS3/NexoLicitCR/blob/codex/entrega-universitaria/docs/historias/archivo/2026-10-18-antes-del-ajuste.json) como trazabilidad; los requisitos retirados no se dan por implementados.
