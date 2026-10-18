## Historia
Como estudiante, quiero presentar una memoria escrita de validación y evidencia honesta del comportamiento de la base de datos y de los límites del radar.

## Alcance de la entrega universitaria
Revisión autorizada el 18 de octubre de 2026. Los criterios siguientes delimitan la entrega obligatoria. MongoDB real puede ser local autenticado con replica set o Atlas. Redis es caché opcional; Docker es opcional.

## Criterios de aceptación
- [x] Entregar una memoria textual y guion de exposición del recorrido cuenta/login → perfil y catálogo → consulta acotada → evidencia → decisión → cierre controlado → reinicio; vincular resultados esperados, pruebas ejecutadas y límites. No se exige un único E2E en vivo contra SICOP.
- [x] Usar MongoDB real aislado para demostrar transacciones, rollback, GridFS íntegro y recuperación física del worker; un replica set local es suficiente.
- [x] Mantener pruebas automáticas de ambigüedad, revisión concurrente, idempotencia y fallo de dependencias controlado.
- [x] Revisar manualmente formularios y errores en escritorio y una vista móvil del entorno elegido.
- [x] Registrar mediciones reproducibles de 100 y 1.000 concursos con/sin caché de cálculo, identificar memoria/doble/servidor y reportar misses o bypass sin presentarlos como mejora; OCR se mide aparte.
- [x] Documentar instalación, variables, versiones, comandos de prueba, guion de demo, evidencia y limitaciones; no incluir secretos ni anexos originales.

## Ampliaciones opcionales · no bloquean la entrega
- Docker/Compose: disponibles como alternativa opcional; construir o ejecutar contenedores no es condición de aceptación.
- Atlas como segundo entorno, Redis real, despliegue público, alta disponibilidad, validación extensa de infraestructura y soporte multiplataforma completo.
- Evaluación humana de relevancia, etiquetado de pares y estudios con empresas; no se exige una muestra mínima ni esas métricas para la entrega.
- Comparables adjudicados, recomendaciones automáticas y benchmarking de 10.000 concursos.

## Dependencias
#1–8. #9 es opcional y no bloquea esta historia.

## Trazabilidad
RNF-01–10 ajustados al entorno académico; RF-16 opcional.

## Evidencia y estado
[Memoria escrita, guion y resultados](https://github.com/EstebanS3/NexoLicitCR/blob/codex/entrega-universitaria/docs/validacion/README.md), con capturas sintéticas de escritorio/móvil. 346 pruebas sin integración y 9 con MongoDB real aprobadas. Se distingue revisión visual, pruebas por componente y guion narrado; no se afirma un E2E único con SICOP en vivo. La evaluación humana por pares es opcional.

Las casillas verificadas describen evidencia técnica; no cierran automáticamente esta issue ni afirman que una propuesta esté fusionada. Los cambios de esta revisión se preparan en la rama `codex/entrega-universitaria` para revisión.

Alcance vigente: [docs/alcance-academico.md](https://github.com/EstebanS3/NexoLicitCR/blob/codex/entrega-universitaria/docs/alcance-academico.md). Se conserva el [texto anterior de las historias](https://github.com/EstebanS3/NexoLicitCR/blob/codex/entrega-universitaria/docs/historias/archivo/2026-10-18-antes-del-ajuste.json) como trazabilidad; los requisitos retirados no se dan por implementados.
