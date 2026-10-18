## Historia
Como estudiante, quiero ejecutar una aplicación reproducible con MongoDB real para demostrar índices, validación y transacciones.

## Alcance de la entrega universitaria
Revisión autorizada el 18 de octubre de 2026. Los criterios siguientes delimitan la entrega obligatoria. MongoDB real puede ser local autenticado con replica set o Atlas. Redis es caché opcional; Docker es opcional.

## Criterios de aceptación
- [x] Mantener FastAPI/Jinja2 y CLI del mismo paquete, dependencias bloqueadas y ejemplos de configuración sin secretos.
- [x] Ejecutar en localhost con un MongoDB autenticado que soporte transacciones: replica set local o Atlas; no sustituir persistencia por mongomock en la demo.
- [x] Crear índices idempotentes y separar la base de aplicación de la base descartable de pruebas.
- [x] Mostrar salud y errores de persistencia sin credenciales; Redis puede estar ausente.
- [x] Instalar desde fuentes limpias, ejecutar lint y suite sin integración y documentar un entorno de demostración.

## Ampliaciones opcionales · no bloquean la entrega
- Validar un segundo backend si ya se demuestra uno; aprovisionamiento cloud, alta disponibilidad y despliegue público.
- Docker y Compose son una forma opcional de ejecución; no condicionan la aceptación.

## Dependencias
#1.

## Trazabilidad
RF-13; RNF-02/05/06.

## Evidencia y estado
Config, índices, CLI y CI versionados. El entorno obligatorio puede ser MongoDB local autenticado; Atlas continúa disponible sin ser requisito adicional.

Las casillas verificadas describen evidencia técnica; no cierran automáticamente esta issue ni afirman que una propuesta esté fusionada. Los cambios de esta revisión se preparan en la rama `codex/entrega-universitaria` para revisión.

Alcance vigente: [docs/alcance-academico.md](https://github.com/EstebanS3/NexoLicitCR/blob/codex/entrega-universitaria/docs/alcance-academico.md). Se conserva el [texto anterior de las historias](https://github.com/EstebanS3/NexoLicitCR/blob/codex/entrega-universitaria/docs/historias/archivo/2026-10-18-antes-del-ajuste.json) como trazabilidad; los requisitos retirados no se dan por implementados.
