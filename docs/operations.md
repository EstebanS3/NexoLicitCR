# Operación y validación

**Alcance vigente:** [entrega universitaria](alcance-academico.md). Docker/Compose y la validación de un segundo backend o servidor Redis son opcionales.

## Arranque bajo demanda

```bash
uv sync --frozen
uv run nexolicit init-db
uv run nexolicit api
# Primera cuenta desde /register, o por CLI antes del registro web:
# uv run nexolicit create-admin
# En local, api inicia y supervisa su propio worker. Para gestionarlo aparte:
uv run nexolicit api --no-worker
uv run nexolicit worker
# Sin proceso permanente:
uv run nexolicit sync --category servicios --limit 5 --once
uv run nexolicit sync --category bienes --limit 3 --documents --once
uv run nexolicit worker --once
```

En `APP_MODE=local`, `api` inicia automáticamente un worker del mismo entorno/configuración, lo reinicia si termina inesperadamente y detiene únicamente ese proceso al cerrar la API. `api --no-worker` permite gestionarlo manualmente. En `APP_MODE=server`, web y worker siguen separados (Compose). No es un servicio que se inicie al encender el equipo. Una interrupción recupera trabajos mediante sus leases.

Sin `--once`, `sync` solo encola. `--once` procesa un intento y devuelve error si no finaliza satisfactoriamente; los reintentos pendientes siguen en MongoDB. Cada rubro revisita hasta `limit` activos/fechas desconocidas empezando por la observación más antigua, además de hasta `limit` entradas del listado. No sustituye un barrido histórico completo. Se omiten duplicados del mismo intento. `since` filtra el listado reciente, no impide reconsultar activos.

Una interrupción deja un lease recuperable; otro worker lo reclama al vencer. Las escrituras transaccionales comprueban el token y lease vigente. Cancelación cooperativa en puntos de control; una descarga/OCR puede tardar hasta su límite antes de observarla. Guardar un checkpoint ocurre después de persistir; la reimportación es idempotente.

## Documentos

Límites por defecto: 20 MiB/archivo, 5 anexos/concurso, 30 páginas, 120 segundos de extracción total. PDF con menos de 40 caracteres por página usa OCR español; también páginas con menos de 250 caracteres y una imagen de al menos 800 × 800 píxeles. El OCR usa detección automática de orientación. Los PDF que superan el límite conservan las primeras páginas y quedan parciales (`PAGE_COUNT_LIMIT`). Fallos y páginas no procesadas quedan explícitos, no equivalen a “sin requisitos”. `DOCUMENT_HOSTS` solo admite hosts HTTPS exactos previamente verificados. El host Oracle verificado en `source-validation.md` está habilitado por defecto; un `DOCUMENT_HOSTS` explícito reemplaza esa lista. Otros hosts requieren verificar la procedencia antes de agregarlos. No guardar ni publicar esas URLs firmadas.

La extracción corre en un subproceso aislado (`python -m nexolicitcr.extractor`). En Linux/macOS aplica además `rlimit` de CPU (110 s) y tamaño de archivo (64 MiB), y en Linux memoria virtual (1 GiB). Windows no tiene el módulo `resource`: allí no hay `rlimit` y el único límite es el tiempo de extracción del proceso padre (`EXTRACTION_TIMEOUT_SECONDS`, 120 s por defecto), que termina el subproceso al vencer. Para servidores usar Linux.

```bash
uv run nexolicit document-orphans
uv run nexolicit import-offers CARTEL:SECUENCIA --lot 1
```

`document-orphans` reporta archivos completos sin referencia de más de un día y también fragmentos sin manifiesto, cuya carga podría estar activa. No elimina nada. GridFS verifica contenido/tamaño antes de publicar; un reintento de anexos repara un documento listo cuyo original falte usando otra identidad de carga. Ejecutar `init-db` para incorporar el índice de `fs.files.metadata.sha256` en instalaciones existentes.

El histórico es por partida y conserva importes presentados; una consulta inválida falla, no se convierte en “sin ofertas”. RF-16 (comparables adjudicados) permanece indisponible hasta validar una fuente final por línea/unidad/moneda.

## Servidor con Atlas externo y Docker · opcional

Configurar `.env` con `MONGO_MODE=atlas`, credenciales separadas, `APP_MODE=server`, `PUBLIC_ORIGIN=https://nombre-real`, `ENVIRONMENT=production` e `INSTALLATION_ID` exclusivo. Atlas debe permitir la IP saliente y el usuario debe limitarse a la base asignada. TLS Atlas obligatorio.

```bash
docker compose build
docker compose run --rm web /app/.venv/bin/nexolicit init-db
docker compose run --rm web /app/.venv/bin/nexolicit create-admin
docker compose up -d web worker
# Opcional: configurar REDIS_URL=redis://redis:6379/0 en .env para este Redis privado.
docker compose --profile cache up -d
# Detener sin eliminar la persistencia Atlas:
docker compose down
```

Web escucha solo en el loopback del host. Usar proxy HTTPS que preserve Host; no publicar directamente el backend. Redis del perfil no expone puertos, es caché descartable y tiene límite de memoria; para compartir un Redis existente usar usuario ACL restringido y otro namespace/instalación. No arrancar el perfil si se utiliza un Redis externo. `.dockerignore` excluye todo excepto código y archivos de dependencias; `.env` entra solo en runtime.

El Dockerfile y Compose están preparados; su construcción **no ha sido validada en este equipo**, donde Docker no está disponible.

## Calidad y límites de evidencia

```bash
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv run pytest -m 'not integration'
uv run python scripts/check_publishable.py
# Opt-in contra base EXCLUSIVA cuyo nombre empiece por nexolicit_test_:
NEXO_TEST_LOCAL=1 NEXO_TEST_DATABASE=nexolicit_test_local uv run pytest -m integration
# O Atlas, seleccionando previamente MONGO_MODE=atlas:
NEXO_TEST_ATLAS=1 NEXO_TEST_DATABASE=nexolicit_test_integration uv run pytest -m integration
```

Los tests con mongomock son evidencia de lógica, no de transacciones/recuperación física real. `tests/test_restart_integration.py` (marcado `integration`) levanta `nexolicit api` como proceso real, registra la cuenta, inicia sesión y guarda un ítem del catálogo; mata el proceso sin apagado ordenado, lo vuelve a levantar y comprueba con la misma cookie que la sesión y el catálogo persisten. Tras cerrar sesión y reiniciar otra vez, el token revocado se rechaza en el servidor. Requiere una base de prueba sin administrador y restaura el catálogo al terminar. La recuperación física está en `tests/test_worker_recovery_integration.py` (marcado `integration`): un worker real se ejecuta como proceso aparte, se termina a mitad de una consulta sin limpieza, otro worker recupera el job cuando vence su lease (15 s) conservando los checkpoints, y un worker vencido no logra confirmar ninguna escritura dentro de una transacción real. Usa sus propios `installation_id` y concursos, los borra al terminar, y falla si la base de prueba ya contiene concursos activos de obras. Pytest no inicia MongoDB; las pruebas de reinicio sí administran su propio proceso API. La evaluación humana mediante pares perfil/concurso y los estudios con empresas son ampliaciones opcionales; no se exige una muestra ni métricas de relevancia para aceptar la entrega técnica. La prueba de equivalencia de caché usa un doble Redis con caída/recuperación; la latencia real requiere un Redis de prueba.

### Mantenimiento automático de la cola

El worker ejecuta mantenimiento al consultar la cola (por defecto cada 2 segundos
cuando está libre) y al renovar el lease durante un trabajo (por defecto cada
30 segundos). No necesita cron ni Redis. Todas las reparaciones filtran por
`INSTALLATION_ID` y comprueban el estado actual en MongoDB de forma atómica:

- Recupera trabajos con lease vencido o ausente, preservando checkpoints y progreso.
- Resuelve cancelaciones pendientes sin interrumpir leases válidos.
- Finaliza trabajos abandonados o pendientes que agotaron `JOB_MAX_ATTEMPTS`.
- Repara fechas de ejecución ausentes en trabajos pendientes.
- Conserva el historial y registra `maintenance_at` y `maintenance_action` en los
  trabajos reparados, además de contadores en el log `queue_maintenance`.

Si MongoDB se interrumpe durante el procesamiento, el worker continuo vuelve a
intentar la conexión; `worker --once` mantiene su salida de error para scripts.
Los fallos definitivos permanecen visibles: no se reinician indefinidamente ni
se eliminan concursos automáticamente. Un fallo de la fuente no prueba que un
registro sea ficticio. El mantenimiento requiere un worker activo; en local lo
inicia y supervisa `api`, y en servidor debe estar activo el servicio worker.

La pantalla de Actividad distingue consulta completada, reintento pendiente y
consulta no completada. El número procesado incluye actualizaciones de concursos
existentes; no equivale al número de concursos nuevos. Los resultados ya
persistidos siguen disponibles aunque la fuente interrumpa el resto de la
consulta. Ampliar el alcance no garantiza agotar todos los concursos de SICOP.

### Frecuencia de SICOP

`SICOP_REQUEST_DELAY_SECONDS` configura la pausa mínima entre peticiones del
worker (predeterminado: 2 segundos). HTTP 429 detiene inmediatamente el intento,
sin continuar con otros concursos. La cola conserva checkpoints y el concurso
pendiente, respeta `Retry-After` numérico o fecha HTTP y espera cinco minutos si
la fuente no informa un plazo. La espera queda persistida y bloquea nuevos
trabajos SICOP de esa instalación, también después de reiniciar el worker.
Los plazos se acotan entre un minuto y un día; se mantiene el máximo de intentos.
La pantalla de actividad explica la pausa sin confundirla con datos inválidos.

### Reanudar una consulta interrumpida

Desde el detalle de una consulta fallida o cancelada, «Reanudar pendientes» crea
una continuación con los mismos filtros, documentos y revisión de perfil. Copia
los checkpoints exitosos y los errores todavía pendientes en una sola inserción;
el worker nunca puede reclamar una continuación sin su progreso inicial.
Doble clic o reenvío devuelve la misma continuación y no reinicia su avance.
La consulta original conserva estado e historial, y la continuación enlaza su origen.

También está disponible en CLI:

```bash
uv run nexolicit resume ID_DE_CONSULTA
```

La reanudación renueva el presupuesto de intentos únicamente por acción explícita;
no reactiva indefinidamente trabajos agotados. Respeta la pausa compartida de
la instalación. El alcance reciente se comprueba otra vez, por lo que el progreso
acumulado puede superar el límite por rubro si la ventana de SICOP cambió.
Los errores pendientes se cuentan por identidad única: ese número no incluye
concursos que todavía no llegaron a consultarse.

Ante HTTP 429 reiterado en un mismo trabajo, la espera mínima crece a 5, 10 y
20 minutos; un Retry-After mayor prevalece, con tope de un día. El último plazo
protege también las consultas nuevas aunque el trabajo agote sus intentos.
La pantalla de Actividad informa de la pausa general y el detalle muestra la
hora del siguiente intento en la zona horaria del navegador. Estos controles
reducen solicitudes y conservan avances; no garantizan que SICOP retire un bloqueo.


### Registro inicial de la empresa

Una instalación nueva y sin usuarios muestra el formulario de registro directamente
en `GET /`, ofrece «Crear mi cuenta» en el login y mantiene `GET /register`.
Si ya existe cuenta, `GET /` requiere iniciar sesión y conserva el recorrido habitual. La empresa elige usuario, contraseña de 14–256 caracteres y
confirmación. Se reutiliza el administrador único existente: `_id`, `username`,
`password_hash` Argon2 y `active`, sin campos, colecciones ni índices nuevos.
Después de registrar debe iniciar sesión y configurar su empresa; el formulario
no genera sesiones, perfiles, catálogos de ejemplo ni trabajos SICOP.

La primera cuenta cierra el registro, incluso si se desactiva después. GET muestra
una explicación y POST devuelve 409. La clave fija de administrador protege
creaciones concurrentes por CLI y web. La validación utiliza origen exacto,
cookie CSRF HttpOnly/SameSite, nonce de un solo uso con vencimiento y espacio de
claves separado del login, límites de intentos y errores sin contraseñas.

Una empresa distinta requiere otra instalación y base exclusiva. Este registro
inicial no incorpora recuperación de contraseña ni cuentas adicionales. El alta
CLI sigue disponible y no reemplaza una cuenta existente.


### Perfil con varias especialidades y evidencia OCR

El perfil admite de 1 a 8 especialidades, incluso de distintos sectores, y hasta
8 términos por especialidad (64 en total). Las sugerencias se combinan sin
duplicados y se revisan antes de confirmar. Los perfiles anteriores de una sola
especialidad continúan editables. Crear o editar el perfil no inicia consultas.

En el radar, «Revisar anexos y aplicar OCR cuando haga falta» está marcado de
forma predeterminada. Se puede desmarcar para consultar solo los datos del
concurso y la evidencia ya guardada. El límite de archivos y páginas sigue
siendo explícito; no se garantiza lectura completa de todos los anexos.

OCR local requiere `tesseract`, el modelo `spa`, el modelo de orientación `osd`
y `pdftoppm` en el PATH del proceso web/worker. En macOS:

```bash
brew install tesseract tesseract-lang poppler
tesseract --list-langs
```

Reiniciar web y worker después de instalar. Los errores de binario, idioma,
renderizado, texto vacío y límites se muestran en cada documento. Las páginas
legibles de un documento parcial siguen contribuyendo a la afinidad. Los
archivos fallidos u omitidos mantienen la evidencia como preliminar.

La extracción `pdf-ocr-v2` vuelve a procesar documentos de versiones anteriores
cuando se vuelven a consultar con anexos; no reescribe el corpus en segundo plano
ni inicia una descarga histórica ilimitada. Las palabras cortadas por guion al
final de línea pueden coincidir conservando el fragmento original de evidencia.

Prueba nativa reproducible de todos los sectores comerciales:

```bash
uv run python scripts/audit_ocr.py --output artifacts/ocr-audit.json
```

Esta prueba mide recuperación de frases conocidas en documentos sintéticos.
No mide precisión de clasificación ni calidad de OCR de todos los pliegos reales.
Ver el alcance y los resultados en [ocr-review.md](ocr-review.md).
