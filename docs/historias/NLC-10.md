## Historia
Como estudiante, quiero presentar una demo reproducible y evidencia honesta del comportamiento de la base de datos y de los límites del radar.

## Alcance de la entrega universitaria
Revisión autorizada el 18 de octubre de 2026. Los criterios siguientes delimitan la entrega obligatoria. MongoDB real puede ser local autenticado con replica set o Atlas. Redis es caché opcional; Docker es opcional.

## Criterios de aceptación
- [ ] Ejecutar un recorrido completo: cuenta/login → perfil confirmado y catálogo → consulta acotada → evidencia → decisión → cambio de cierre controlado → reinicio, conservando datos.
- [x] Usar MongoDB real aislado para demostrar transacciones, rollback, GridFS íntegro y recuperación física del worker; un replica set local es suficiente.
- [x] Mantener pruebas automáticas de ambigüedad, revisión concurrente, idempotencia y fallo de dependencias controlado.
- [ ] Revisar manualmente formularios y errores en escritorio y una vista móvil del entorno elegido.
- [x] Registrar mediciones reproducibles de 100 y 1.000 concursos con/sin caché de cálculo, identificar memoria/doble/servidor y reportar misses o bypass sin presentarlos como mejora; OCR se mide aparte.
- [ ] Revisar manualmente 10–20 pares perfil/concurso y registrar etiqueta, justificación y métricas exploratorias de precisión/exhaustividad, sin generalizar esa muestra.
- [x] Documentar instalación, variables, versiones, comandos de prueba, guion de demo, evidencia y limitaciones; no incluir secretos ni anexos originales.

## Ampliaciones opcionales · no bloquean la entrega
- Docker/Compose: disponibles como alternativa opcional; construir o ejecutar contenedores no es condición de aceptación.
- Atlas como segundo entorno, Redis real, despliegue público, alta disponibilidad, validación extensa de infraestructura y soporte multiplataforma completo.
- Evaluación formal con empresas y conjunto de 30–50 o más pares humanos; no sustituir la muestra obligatoria por etiquetas generadas.
- Comparables adjudicados, recomendaciones automáticas y benchmarking de 10.000 concursos.

## Dependencias
#1–8. #9 es opcional y no bloquea esta historia.

## Trazabilidad
RNF-01–10 ajustados al entorno académico; RF-16 opcional.

## Evidencia y estado
Las casillas de ejecución manual y evaluación humana permanecen pendientes hasta adjuntar resultados reales. Tener código o reducir alcance no equivale a completar esas validaciones.

Las casillas verificadas describen evidencia técnica; no cierran automáticamente esta issue ni afirman que una propuesta esté fusionada. Los cambios de esta revisión se preparan en la rama `codex/entrega-universitaria` para revisión.

Alcance vigente: [docs/alcance-academico.md](https://github.com/EstebanS3/NexoLicitCR/blob/codex/entrega-universitaria/docs/alcance-academico.md). Se conserva el [texto anterior de las historias](https://github.com/EstebanS3/NexoLicitCR/blob/codex/entrega-universitaria/docs/historias/archivo/2026-10-18-antes-del-ajuste.json) como trazabilidad; los requisitos retirados no se dan por implementados.
