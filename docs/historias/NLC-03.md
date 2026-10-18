## Historia
Como usuario de la demo, quiero crear la cuenta inicial, describir mi actividad y confirmar mis servicios para consultar oportunidades sin perder mi catálogo ni mis decisiones.

## Alcance de la entrega universitaria
Revisión autorizada el 18 de octubre de 2026. Los criterios siguientes delimitan la entrega obligatoria. MongoDB real puede ser local autenticado con replica set o Atlas. Redis es caché opcional; Docker es opcional.

## Criterios de aceptación
- [x] Registro inicial/login/logout sin contraseña predeterminada ni secretos en argumentos; acceso cerrado tras crear la cuenta inicial.
- [x] Proteger rutas y formularios con sesión, CSRF, validación, escape HTML y cookies seguras en modo servidor.
- [x] Crear, editar y desactivar catálogo manual con revisión para evitar sobrescribir cambios concurrentes.
- [x] Mantener actividad o especialidades, servicios, cobertura y exclusiones editables en borrador hasta confirmación explícita.
- [x] Confirmar perfil de forma atómica, conservar ítems manuales y decisiones, y pedir precisión cuando la descripción sea ambigua.
- [x] Comprobar que catálogo, sesión y revocación sobreviven a un reinicio real de la API.
- [x] Recorrer manualmente formularios y errores en escritorio y una vista móvil del entorno elegido, con etiquetas y navegación por teclado.

## Ampliaciones opcionales · no bloquean la entrega
- Auditoría exhaustiva de accesibilidad, soporte de todos los navegadores y sistemas operativos, y evaluación con empresas reales.

## Dependencias
#2.

## Trazabilidad
RF-01/14; RNF-04/10.

## Evidencia y estado
Pruebas de web, registro, onboarding, múltiples especialidades y reinicio. Revisión básica ejecutada el 18 de octubre de 2026 en navegador integrado, escritorio 1366 × 900 y móvil 390 × 844: login/errores, perfil, catálogo, etiquetas y teclado. [Resultados y capturas](https://github.com/EstebanS3/NexoLicitCR/blob/codex/entrega-universitaria/docs/validacion/README.md); no constituye una auditoría exhaustiva ni una prueba en Edge.

Las casillas verificadas describen evidencia técnica; no cierran automáticamente esta issue ni afirman que una propuesta esté fusionada. Los cambios de esta revisión se preparan en la rama `codex/entrega-universitaria` para revisión.

Alcance vigente: [docs/alcance-academico.md](https://github.com/EstebanS3/NexoLicitCR/blob/codex/entrega-universitaria/docs/alcance-academico.md). Se conserva el [texto anterior de las historias](https://github.com/EstebanS3/NexoLicitCR/blob/codex/entrega-universitaria/docs/historias/archivo/2026-10-18-antes-del-ajuste.json) como trazabilidad; los requisitos retirados no se dan por implementados.
