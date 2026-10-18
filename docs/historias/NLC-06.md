## Historia
Como usuario, quiero consultar texto por página y descargar el anexo original, incluso después de reintentar una carga interrumpida.

## Alcance de la entrega universitaria
Revisión autorizada el 18 de octubre de 2026. Los criterios siguientes delimitan la entrega obligatoria. MongoDB real puede ser local autenticado con replica set o Atlas. Redis es caché opcional; Docker es opcional.

## Criterios de aceptación
- [x] Validar URL/redirecciones, firma real, tamaño y hash; aceptar solo PDF/PNG/JPEG compatibles.
- [x] Extraer evidencia por página de PDF digital, escaneado y mixto en un entorno definido con Tesseract español y Poppler; conservar estados parciales.
- [x] Ejecutar OCR fuera del loop HTTP con límites de tiempo, páginas y recursos disponibles en el entorno elegido.
- [x] Verificar tamaño, contenido y disponibilidad completa de GridFS antes de publicar un documento listo o reutilizar uno existente.
- [x] Recuperar una carga con fragmentos sin manifiesto mediante un identificador de escritura independiente; no borrar fragmentos de otra carga activa.
- [x] Reparar documentos previamente marcados listos cuyo archivo falte; mantener idempotencia al repetir la reparación.
- [x] Reportar archivos sin referencia y fragmentos sin manifiesto sin borrado automático; distinguir antigüedad conocida de una posible carga activa.
- [x] Conservar el concurso ante fallo de anexos y no ejecutar adjuntos ni tratar HTML de bloqueo como documento.

## Ampliaciones opcionales · no bloquean la entrega
- Soporte nativo verificado en Windows y otros entornos, OCR de todos los formatos y medición exhaustiva de calidad sobre pliegos reales.

## Dependencias
#1, #5.

## Trazabilidad
RF-05/06; RNF-04/07.

## Evidencia y estado
Regresiones de recuperación GridFS y prueba de integración real, además de evidencia previa de OCR en docs/ocr-review.md. Los fragmentos reportados requieren inspección antes de cualquier limpieza.

Las casillas verificadas describen evidencia técnica; no cierran automáticamente esta issue ni afirman que una propuesta esté fusionada. Los cambios de esta revisión se preparan en la rama `codex/entrega-universitaria` para revisión.

Alcance vigente: [docs/alcance-academico.md](https://github.com/EstebanS3/NexoLicitCR/blob/codex/entrega-universitaria/docs/alcance-academico.md). Se conserva el [texto anterior de las historias](https://github.com/EstebanS3/NexoLicitCR/blob/codex/entrega-universitaria/docs/historias/archivo/2026-10-18-antes-del-ajuste.json) como trazabilidad; los requisitos retirados no se dan por implementados.
