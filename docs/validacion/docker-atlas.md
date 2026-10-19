# Docker Desktop y MongoDB Atlas: validación real

18 de octubre de 2026, hora de Costa Rica. Entorno: macOS ARM64, Docker Engine 29.8.2, Compose 5.6.0 y Python 3.12 dentro de la imagen. Se reutilizaron las credenciales del ejemplo mediante un archivo privado; las pruebas emplearon bases `nexolicit_test_` independientes. El `.env` de MongoDB local y los datos del ejemplo se conservaron.

## Resultados

| Comprobación ejecutada | Resultado |
|---|---|
| Construcción real de `nexolicitcr:local` | Correcta; dependencias fijadas con `uv.lock`, paquete instalado sin modo editable. |
| Arranque de Compose | `init-db` terminó con código 0; web saludable y worker separado en ejecución. |
| HTTP desde el host a Docker → Atlas | `/health/ready` devolvió 200 y `mongodb=available`, `mongo_mode=atlas`. |
| Suite de lógica/HTTP con dobles | 350 aprobadas; 9 de integración excluidas de esa ejecución. |
| Integración nativa contra Atlas | 9 aprobadas en 133,45 s: transacciones, reimportación, OCR español, GridFS, reinicio de API, supervisión y recuperación del worker. |
| Integración dentro de la imagen Docker contra Atlas | 8 aprobadas en 128,82 s: transacciones, OCR, GridFS, reinicio de API y caída/recuperación del worker. La supervisión nativa de procesos se comprobó en macOS; Compose usa un worker independiente. |
| Flujo HTTP sobre los contenedores | Registro, login, perfil, catálogo, CSRF inválido rechazado, páginas protegidas, recursos estáticos y logout correctos. |
| Consulta real SICOP mediante la cola Docker | Job aceptado con HTTP 202, procesado por el worker y guardado en Atlas al primer intento; estado `succeeded`, sin errores pendientes. |
| Reinicio del contenedor web | La misma cookie de sesión y el catálogo siguieron funcionando tras `docker compose restart web`. |
| Caída del Redis real de prueba | `/opportunities` siguió devolviendo HTTP 200 y salud informó `cache=fallback`. Redis se inició de nuevo y el estado volvió a `configured`. No es un benchmark de caché. |
| PDF público real de SICOP procesado dentro de Docker | Documento `ready`, 2 páginas extraídas por OCR, original recuperable desde GridFS Atlas y sin código de error. |
| Restricciones del contenedor | UID 10001, raíz de solo lectura, temporales escribibles, sin `.env` en la imagen y sin pytest/mongomock en runtime. Puerto publicado exclusivamente en loopback. |
| Calidad | Ruff, formato, revisión automatizada de archivos publicables, Compose `config --quiet` y `git diff --check` correctos. |

Los informes automáticos y logs de cada ejecución quedan en `artifacts/` y `logs/`, fuera de Git. Esta memoria conserva únicamente resultados resumidos. Las dependencias de prueba del contenedor se instalaron únicamente en su `/tmp`; el contenedor temporal se eliminó al terminar.

## Cambio aplicado

El Compose anterior forzaba `APP_MODE=server`, incompatible con el origen HTTP local del ejemplo. Ahora carga `.env.atlas` y conserva el modo configurado; únicamente fuerza Atlas. La CLI admite `--host` explícito para escuchar dentro del contenedor sin cambiar el valor loopback del arranque nativo. La web de Compose usa `--no-worker` para evitar iniciar un segundo worker.

La imagen se construye en dos etapas y copia al runtime únicamente el entorno instalado. Tesseract español y Poppler están disponibles. La inicialización de índices es un servicio previo y el healthcheck consulta la API con el Host permitido. Los archivos de credenciales siguen excluidos por `.gitignore` y `.dockerignore`.

## Límite observado con anexos

Una consulta adicional con anexos habilitados terminó en `SOURCE_PARTIAL` después de tres intentos. Se confirmó un anexo `.docx`, que el descargador rechaza con `DOCUMENT_UNSUPPORTED_OR_HTML`; también se registraron omisiones por el límite de archivos. El extractor admite PDF, PNG y JPEG. El fallo queda visible y no se interpreta como ausencia de requisitos. La sincronización de metadatos sin anexos y la extracción de un PDF real se verificaron por separado.

No se implementó extracción de Word/ZIP ni se amplió la lista de hosts para hacer pasar esa consulta. Los resultados no certifican todos los concursos, formatos ni disponibilidad futura de SICOP.

## Uso al terminar

La instancia principal queda ejecutándose en [http://localhost:8000](http://localhost:8000), conectada a `nexolicit_docker` en Atlas, lista para registrar la primera cuenta. La instancia temporal, su Redis y los contenedores de pruebas se retiraron. Las bases de prueba conservan la evidencia SICOP; no se borraron bases completas.

```bash
# Desde la raíz del proyecto, con Docker Desktop abierto:
docker compose up --build -d --wait
docker compose ps --all
curl http://localhost:8000/health/ready

# Detener la aplicación; Atlas conserva sus datos:
docker compose down
```

[Configuración y repetición del flujo](../operations.md#docker-desktop-con-atlas-externo). Este trabajo valida una aplicación local en Docker con base de datos cloud; no crea un sitio público ni un despliegue de producción.
