## Historia
Como estudiante, quiero compartir el pipeline entre web, CLI y worker, y demostrar que una interrupción no pierde avances ni permite escrituras de un worker vencido.

## Alcance de la entrega universitaria
Revisión autorizada el 18 de octubre de 2026. Los criterios siguientes delimitan la entrega obligatoria. MongoDB real puede ser local autenticado con replica set o Atlas. Redis es caché opcional; Docker es opcional.

## Criterios de aceptación
- [x] Persistir un job antes de devolver 202 al cliente JSON; formularios HTML pueden redirigir a su progreso.
- [x] Evitar duplicados por idempotencia y reclamar jobs atómicamente mediante token, lease y heartbeat en MongoDB.
- [x] Matar un worker en una prueba aislada, recuperar el job tras vencer el lease y conservar checkpoints sin repetir trabajo confirmado.
- [x] Rechazar publicaciones, checkpoints y finalizaciones de un worker vencido, incluyendo rollback de una transacción real.
- [x] Mantener reintentos acotados, cancelación cooperativa y reanudación con filtros y avances; Redis no aporta durabilidad.
- [x] Mantener códigos de salida coherentes en CLI one-shot.
- [x] Demostrar con procesos reales que el modo local inicia, supervisa y detiene su worker con la API; documentar cómo ejecutarlos separados.

## Ampliaciones opcionales · no bloquean la entrega
- Múltiples nodos, alta disponibilidad, pruebas exhaustivas de particiones de red y operación continua de producción.

## Dependencias
#2, #4.

## Trazabilidad
RF-02/11/13.

## Evidencia y estado
Pruebas de jobs/CLI y tests/test_worker_recovery_integration.py con MongoDB real. Nueva tests/test_runtime_integration.py aprobada: arranque, reemplazo tras SIGKILL, apagado por SIGTERM y conservación de un worker independiente. Gestión movida al lifespan para limpiar antes de la retransmisión de señales de Uvicorn. [Evidencia y comandos separados](https://github.com/EstebanS3/NexoLicitCR/blob/codex/entrega-universitaria/docs/validacion/README.md); entorno nativo POSIX, sin promesa de limpieza ante SIGKILL de la API.

Las casillas verificadas describen evidencia técnica; no cierran automáticamente esta issue ni afirman que una propuesta esté fusionada. Los cambios de esta revisión se preparan en la rama `codex/entrega-universitaria` para revisión.

Alcance vigente: [docs/alcance-academico.md](https://github.com/EstebanS3/NexoLicitCR/blob/codex/entrega-universitaria/docs/alcance-academico.md). Se conserva el [texto anterior de las historias](https://github.com/EstebanS3/NexoLicitCR/blob/codex/entrega-universitaria/docs/historias/archivo/2026-10-18-antes-del-ajuste.json) como trazabilidad; los requisitos retirados no se dan por implementados.
