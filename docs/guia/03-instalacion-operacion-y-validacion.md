# 03 · Instalación, operación y validación

> **De una idea prometedora a una herramienta que se puede operar.** NexoLicitCR conserva el trabajo realizado, explica cuándo necesita atención y permite retomar una consulta sin reconstruir el catálogo de la empresa. Esta guía convierte esas capacidades en un procedimiento reproducible.

**Base documental:** código de la rama `dev`, revisión `4c91af4`; edición del 18 de octubre de 2026. Los ejemplos se ejecutan desde la raíz del repositorio. Las credenciales mostradas son marcadores de posición; este documento no necesita leer el archivo privado `.env`. Los comandos que consultan SICOP o utilizan una base real son instrucciones para el operador, no evidencia de que se hayan ejecutado durante la redacción.

## 1. Qué se necesita para ponerlo en marcha

La instalación tiene tres piezas esenciales: una aplicación Python, una base MongoDB con transacciones y un proceso que atienda la cola de consultas. En modo local, el comando de la aplicación también administra su worker. En servidor, ambos procesos se ejecutan por separado. Redis mejora el acceso a resultados calculados, pero no conserva el estado de negocio ni es requisito para trabajar.

| Componente | Requisito del proyecto | Función |
|---|---|---|
| Python | `>=3.12,<3.14`; versiones 3.12 o 3.13 | Ejecutar aplicación, CLI, worker y extracción. |
| uv | Gestor utilizado por los comandos del repositorio | Resolver el entorno mediante `uv.lock`; `--frozen` conserva la resolución versionada. |
| MongoDB Atlas | Conexión SRV a un host terminado en `.mongodb.net`, autenticación y TLS | Persistencia externa, sesiones, catálogo, concursos, cola y documentos. |
| MongoDB local, alternativa a Atlas | Replica set autenticado `nexo-local`, enlazado a `127.0.0.1` | Desarrollo local con transacciones reales. Un MongoDB standalone no cubre esta necesidad. |
| Tesseract | Ejecutable `tesseract`, idiomas `spa` y `osd` disponibles en el `PATH` | OCR español y detección de orientación. |
| Poppler | Ejecutable `pdftoppm` en el `PATH` | Convertir páginas PDF a imágenes cuando se requiere OCR. |
| Docker y Compose | Solo para el despliegue descrito en el archivo Compose | Ejecutar web y worker con Atlas externo. |
| Redis | Opcional; el perfil incluido usa `redis:7.4-alpine` | Caché descartable de resultados. |

Las dependencias Python, rangos y herramientas de desarrollo están en [pyproject.toml](../../pyproject.toml). La imagen usa Python 3.12, instala Tesseract español y Poppler, y fija `uv==0.12.24` en el [Dockerfile](../../Dockerfile). El proyecto incluye FastAPI, Uvicorn, Jinja2, PyMongo, Pydantic Settings, HTTPX, Beautiful Soup, pwdlib/Argon2, Typer, Redis, pypdf, Pillow y tzdata; no necesita un compilador de frontend para servir la interfaz existente.

### Elegir una modalidad

| Modalidad | Base | Aplicación | Uso esperado |
|---|---|---|---|
| Local con Atlas | `MONGO_MODE=atlas` | `APP_MODE=local` | Abrir la interfaz en el equipo y mantener la persistencia en Atlas. |
| Local con MongoDB propio | `MONGO_MODE=local` | `APP_MODE=local` | Desarrollo y pruebas con base local autenticada. |
| Servidor con Compose | `MONGO_MODE=atlas` | `APP_MODE=server` | Web detrás de proxy HTTPS y worker separado. |

La combinación MongoDB local + aplicación en servidor es rechazada por la configuración. El [Compose incluido](../../compose.yaml) usa `.env.atlas`, admite `APP_MODE=local` para Docker Desktop y conserva `APP_MODE=server` cuando se configura HTTPS. Impone `MONGO_MODE=atlas` y no incluye un servicio MongoDB.

**Entrega universitaria:** [alcance-academico.md](../alcance-academico.md). Basta un entorno MongoDB real; Docker, Atlas como segundo entorno y Redis real son opcionales. Los procedimientos de servidor siguientes se conservan como ampliación.

## 2. Primer arranque con Atlas

### Preparar el entorno

```bash
uv sync --frozen
# Crear el archivo solo si todavía no existe.
cp -n .env.example .env
```

Editar `.env` localmente usando [.env.example](../../.env.example) como referencia. Una configuración mínima tiene esta forma:

```dotenv
MONGO_MODE=atlas
ATLAS_URI=mongodb+srv://cluster.example.mongodb.net/
ATLAS_USUARIO=usuario_exclusivo_de_la_instalacion
ATLAS_CLAVE=REEMPLAZAR_LOCALMENTE
ATLAS_BASE=nexolicit_dev
ATLAS_AUTHDB=admin
APP_MODE=local
PUBLIC_ORIGIN=http://localhost:8000
SICOP_TIMEZONE=America/Costa_Rica
INSTALLATION_ID=empresa-demo
ENVIRONMENT=development
REDIS_URL=
```

`cluster.example.mongodb.net` y los valores de acceso son ilustrativos: deben sustituirse por los datos de la instalación. Atlas debe aceptar la IP saliente del equipo y el usuario debe poder operar sobre la base seleccionada. La aplicación pasa usuario y contraseña a PyMongo por separado; no se incrustan dentro de `ATLAS_URI`.

### Inicializar e ingresar

```bash
uv run nexolicit init-db
uv run nexolicit api
```

Abrir `http://localhost:8000`. Cuando la base no contiene usuarios, la página inicial presenta el registro. La primera cuenta utiliza un nombre de usuario de 3 a 64 caracteres y una contraseña de 14 a 256 caracteres. Después del registro se inicia sesión y se configura la empresa. Crear el perfil o editarlo no inicia una descarga de SICOP: esa acción se solicita después desde el radar o desde la CLI.

Como alternativa al formulario inicial, antes de crear la primera cuenta:

```bash
uv run nexolicit create-admin
```

El comando solicita contraseña y confirmación mediante entrada oculta. El administrador tiene una identidad fija que impide crear dos administradores concurrentemente. Una instalación admite una empresa y un administrador; el registro se cierra al existir cualquier usuario, incluso si posteriormente se desactiva. No hay recuperación de contraseña ni gestión de cuentas adicionales implementada en esta versión.

`init-db` prepara índices y documentos iniciales de forma idempotente. No reemplaza las credenciales, no borra colecciones y no inicia un barrido de concursos. El arranque web no sustituye este paso de preparación.

### Cambiar el puerto

```bash
# Establecer también PUBLIC_ORIGIN=http://localhost:8080 en .env.
uv run nexolicit api --port 8080
```

El rango admitido es 1024–65535. El origen del navegador debe coincidir con `PUBLIC_ORIGIN`, incluido el puerto: utilizar `127.0.0.1` en el navegador cuando se configuró `localhost` puede provocar rechazo del Host o del origen. La sesión se relaciona con el origen y las cookies del navegador.

## 3. Primer arranque con MongoDB local

El helper [scripts/local_mongo.py](../../scripts/local_mongo.py) administra un replica set de un nodo para este checkout. Requiere que el ejecutable oficial `mongod` ya esté instalado. El helper usa `--fork`, por lo que su recorrido está orientado a sistemas Unix; no debe presentarse como un instalador universal de MongoDB para Windows.

### Instalación nueva mediante el helper

En un checkout que todavía no tenga `.env` ni configuración local previa:

```bash
uv sync --frozen
uv run python scripts/local_mongo.py start --mongod /ruta/al/binario/mongod
uv run nexolicit api
```

El primer comando `start` realiza las siguientes acciones:

1. Crea `var/mongodb/`, credenciales administrativas aleatorias y una clave privada del replica set.
2. Genera `.env` desde [.env.local.example](../../.env.local.example), con contraseña aleatoria para el usuario de aplicación.
3. Arranca `mongod` en `127.0.0.1:27017` con autenticación y replica set `nexo-local`.
4. Inicializa el replica set y espera a que el nodo sea primario.
5. Crea un usuario de aplicación con `readWrite` en `nexolicit_local` y `nexolicit_test_local`.
6. Comprueba conexión y prepara índices en la base de trabajo.

Los archivos privados creados por el helper usan permisos `0600`; los directorios de datos se crean con `0700`. `var/mongodb/data/` conserva la base; `var/mongodb/admin.json` y `var/mongodb/replica.key` contienen material sensible de administración. La exclusión de Git evita versionarlos, pero no sustituye un respaldo seguro del equipo.

### Si ya existe `.env`

El helper se detiene si encuentra `.env` y todavía no existe su archivo administrativo. Es una protección contra sustituir una configuración previa. Conservar ese archivo y configurar manualmente la base, o preparar otro checkout para el entorno local. No borrar una configuración existente para hacer que el helper continúe.

La forma admitida para una instalación local administrada manualmente es:

```dotenv
MONGO_MODE=local
MONGO_LOCAL_URI=mongodb://127.0.0.1:27017/?replicaSet=nexo-local
MONGO_LOCAL_USUARIO=nexo_local
MONGO_LOCAL_CLAVE=REEMPLAZAR_LOCALMENTE
MONGO_LOCAL_BASE=nexolicit_local
APP_MODE=local
PUBLIC_ORIGIN=http://localhost:8000
SICOP_TIMEZONE=America/Costa_Rica
```

La URI debe tener un puerto explícito, hostname `127.0.0.1`, esquema `mongodb` y exactamente la opción `replicaSet=nexo-local`. No admite credenciales embebidas ni parámetros adicionales. El nombre de la base empieza por `nexolicit_`. La aplicación autentica contra `admin`. La conexión local no usa TLS y queda restringida a loopback; Atlas siempre usa TLS.

El helper se limita a `nexolicit_local` y al puerto 27017. La clase de configuración permite otros puertos explícitos y otras bases con el prefijo permitido, pero eso requiere administrar MongoDB por otro procedimiento.

### Reinicio y cierre

```bash
# Reutiliza datos y credenciales del helper.
uv run python scripts/local_mongo.py start --mongod /ruta/al/binario/mongod

# Detiene MongoDB sin eliminar sus archivos.
uv run python scripts/local_mongo.py stop
```

Cerrar la API con Ctrl+C antes de detener MongoDB permite un cierre más predecible. Si se usa Compass, debe conectarse al servidor existente: Compass es una herramienta de administración, no el proceso `mongod`.

## 4. Variables de configuración: contrato operativo

La fuente de verdad es [config.py](../../src/nexolicitcr/config.py). Pydantic Settings lee `.env` y variables del entorno; las variables exportadas en el proceso tienen prioridad. Los errores de configuración de la CLI ocultan los valores y terminan con código 2. La tabla distingue valores predeterminados del código de los ejemplos incluidos en Git.

### Persistencia, identidad y acceso

| Variable | Predeterminado del código | Restricción o efecto |
|---|---|---|
| `MONGO_MODE` | `atlas` | `atlas` o `local`. |
| `ATLAS_URI` | Vacío | URI SRV Atlas; requiere un host `.mongodb.net`. No acepta usuario, contraseña ni fragmento en la URI. |
| `ATLAS_USUARIO`, `ATLAS_CLAVE` | Vacíos | Ambos obligatorios en modo Atlas. |
| `ATLAS_BASE` | `nexolicit_dev` | Nombre de 1–63 caracteres: empieza con letra y continúa con letras, números, `_` o `-`. |
| `ATLAS_AUTHDB` | `admin` | Mismas reglas de nombre que la base Atlas. |
| `MONGO_LOCAL_URI` | `mongodb://127.0.0.1:27017/?replicaSet=nexo-local` | Solo URI local conforme a las reglas anteriores. |
| `MONGO_LOCAL_USUARIO`, `MONGO_LOCAL_CLAVE` | Vacíos | Ambos obligatorios en modo local. |
| `MONGO_LOCAL_BASE` | `nexolicit_local` | Prefijo `nexolicit_` más 1–50 caracteres alfanuméricos, `_` o `-`. |
| `MONGO_TIMEOUT_MS` | `5000` | 500–30000 ms para conexión y selección del servidor. El socket tiene un timeout de 10000 ms en `connect()`. |
| `APP_MODE` | `local` | `local` enlaza la API a loopback; `server` enlaza a `0.0.0.0` y exige origen HTTPS. |
| `PUBLIC_ORIGIN` | `http://localhost:8000` | Origen sin ruta adicional, credenciales, query ni fragmento. En local exige loopback. |
| `INSTALLATION_ID` | `nexolicit` | Identificador estable de 1–48 caracteres: minúsculas, números, `_` y `-`; empieza con letra o número. Delimita la cola. |
| `ENVIRONMENT` | `development` | `development`, `test` o `production`; participa en las claves de caché. |
| `SESSION_HOURS` | `8` | Sesión de 1–24 horas. |

El ejemplo de Atlas usa `INSTALLATION_ID=nexolicit-demo`, distinto del predeterminado de código. Elegir un identificador único y mantenerlo al reiniciar. Cambiarlo hace que el worker y la pantalla de actividad atiendan otro ámbito de cola; no migra los trabajos previos. La separación real entre empresas se realiza con instalaciones y bases exclusivas, no solamente con ese identificador.

`ATLAS_URI` admite únicamente las opciones `retryWrites`, `w` y `appName`, sin distinguir mayúsculas para la validación. La conexión de [storage.py](../../src/nexolicitcr/storage.py) establece TLS, `w="majority"`, decodificación consciente de zona horaria y `appname="NexoLicitCR"` explícitamente.

### Cola y fuente

| Variable | Predeterminado | Intervalo / significado |
|---|---|---|
| `SICOP_TIMEZONE` | Vacío | Zona IANA válida; el ejemplo usa `America/Costa_Rica`. Vacío deja pendientes las fechas sin offset. |
| `SICOP_REQUEST_DELAY_SECONDS` | `2` | 0,4–30 segundos; pausa mínima entre peticiones del cliente del worker a SICOP. |
| `JOB_LEASE_SECONDS` | `90` | 15–600 segundos; vigencia de la propiedad temporal del trabajo. |
| `JOB_MAX_ATTEMPTS` | `3` | 1–10 intentos por trabajo. |
| `WORKER_POLL_SECONDS` | `2` | 0,1–60 segundos entre revisiones de una cola sin trabajo disponible. |

La zona de SICOP tiene validación documentada en [source-validation.md](../source-validation.md). No confundir el valor vacío por defecto de la clase con la recomendación de despliegue del archivo de ejemplo. Una fecha desconocida no demuestra que el concurso esté abierto ni cerrado.

### Documentos y caché

| Variable | Predeterminado | Límite o efecto |
|---|---|---|
| `DOCUMENT_MAX_BYTES` | `20971520` | 20 MiB por archivo; configurable entre 1024 bytes y 50 MiB. |
| `DOCUMENT_MAX_PAGES` | `30` | 1–100 páginas por documento. |
| `DOCUMENT_MAX_FILES` | `5` | 1–20 anexos por concurso. |
| `EXTRACTION_TIMEOUT_SECONDS` | `120` | 5–600 segundos para el subproceso de extracción. |
| `DOCUMENT_HOSTS` | Los tres hosts indicados debajo | Lista separada por comas; reemplaza la lista completa si se configura. |
| `REDIS_URL` | Vacío | Vacío deshabilita caché. Si se usa, esquema `redis` o `rediss`, host obligatorio, sin query ni fragmento. |
| `REDIS_NAMESPACE` | `nexolicitcr` | Prefijo con las mismas reglas de caracteres que `INSTALLATION_ID`. |
| `CACHE_TTL_SECONDS` | `120` | 5–900 segundos de vida de una entrada. |
| `CACHE_TIMEOUT_MS` | `150` | 20–1000 ms para operaciones y conexión Redis. |
| `CACHE_BREAKER_SECONDS` | `30` | 1–300 segundos de espera después de una falla de caché. |

Los hosts predeterminados son `www.sicop.go.cr`, `prod-api.sicop.go.cr` y `objectstorage.us-ashburn-1.oraclecloud.com`. Son nombres exactos, no patrones de subdominio. La descarga valida HTTPS, puerto 443, ausencia de credenciales y resolución a direcciones públicas, también cuando sigue una redirección. Las URLs firmadas no deben copiarse en documentación pública.

## 5. Operación diaria: una consulta que conserva su avance

### Iniciar web y worker

En modo local, basta con:

```bash
uv run nexolicit api
```

El contexto [local_worker()](../../src/nexolicitcr/runtime.py) inicia un worker como subproceso, supervisa sus salidas inesperadas y vuelve a iniciarlo con espera creciente de 2 a 30 segundos. Al cerrar la API detiene el proceso que le pertenece. No instala un servicio del sistema ni activa el proyecto al encender el equipo.

Para operar los procesos por separado, usar dos terminales en la misma raíz y con la misma configuración:

```bash
# Terminal 1
uv run nexolicit api --no-worker

# Terminal 2
uv run nexolicit worker
```

En `APP_MODE=server`, `api` siempre requiere un worker separado. Importar `create_app()` desde otro servidor ASGI tampoco arranca por sí mismo el supervisor local: ese comportamiento pertenece al comando CLI `api`.

### Crear consultas

```bash
# Encolar; lo atiende un worker de la misma instalación.
uv run nexolicit sync --category bienes --limit 20

# Procesar un intento en este proceso.
uv run nexolicit sync --category servicios --limit 5 --once

# Incluir descarga y extracción de anexos dentro de los límites configurados.
uv run nexolicit sync --category bienes --limit 3 --documents --once

# Rubros: bienes, obras, servicios o all.
uv run nexolicit sync --category all --limit 5 --since 2026-01-01
```

`sync` imprime el identificador persistido del trabajo. Sin `--once`, termina tras encolar. Con `--once`, intenta reclamar ese trabajo y procesa como máximo un intento; si no llega a `succeeded`, termina con error. Una pausa compartida de SICOP o un trabajo reclamado por otro worker puede impedir que ese intento empiece inmediatamente.

`--since` admite fecha ISO `AAAA-MM-DD`. Filtra el listado reciente y no evita reconsultar concursos activos ya almacenados. El límite se aplica por rubro al listado y, por separado, a la revisión de hasta ese mismo número de activos o fechas desconocidas. Además se atienden errores pendientes conservados de un intento anterior. Por eso `progress` puede superar `limit`; la cifra tampoco equivale a «concursos nuevos».

Los activos se revisitan por antigüedad de observación. Dentro de un intento se evitan duplicados por identidad `rubro:cartel:secuencia`. Cada expediente conserva su secuencia: una similitud de título no basta para fusionar identidades.

### Interpretar estados

| Estado | Significado | Acción habitual |
|---|---|---|
| `queued` | Guardado y pendiente de reclamación. | Verificar worker y hora programada. |
| `running` | Un worker posee un lease vigente. | Consultar progreso; evitar lanzar copias de la misma intención. |
| `retry_wait` | Conserva avance y espera otro intento. | Respetar `next_attempt_at` y cualquier pausa de la fuente. |
| `succeeded` | El recorrido del trabajo terminó sin errores de concurso registrados en ese intento. | Revisar resultados y estados documentales. No prueba un barrido total de SICOP. |
| `failed` | Error definitivo o presupuesto agotado. | Corregir la causa y reanudar explícitamente si corresponde. |
| `canceled` | Cancelación atendida por el worker o mantenimiento. | Conservar resultados previos; reanudar si se desea continuar. |

Un estado exitoso del job no garantiza lectura completa de los anexos. Los archivos fuera del límite quedan `omitted`; esa omisión es explícita, pero por sí sola no cambia el trabajo a fallido. Los estados documentales `failed` y `partial` sí generan un intento parcial cuando la consulta incluye documentos.

### Recuperación después de interrupciones

El worker reclama mediante una actualización atómica, genera un token y renueva el lease cada tercio de `JOB_LEASE_SECONDS`: 30 segundos con la configuración estándar. La escritura del concurso comprueba ese token dentro de la transacción. Un worker que perdió el lease no puede confirmar esa escritura como propietario vigente.

El checkpoint se guarda después de persistir el resultado. Una caída entre persistencia y checkpoint puede provocar relectura del concurso, pero la importación versionada está diseñada para ser idempotente. Este enfoque permite conservar el avance sin prometer que cada petición a la fuente ocurra una sola vez.

Al consultar la cola y al renovar un trabajo, el mantenimiento:

- Recupera leases vencidos o ausentes, conserva progreso y programa reintento.
- Resuelve cancelaciones pendientes cuando corresponde.
- Marca como fallidos los trabajos abandonados o pendientes que agotaron intentos.
- Repara la fecha de ejecución de pendientes que no la tengan.
- Registra `maintenance_at`, `maintenance_action` y contadores `queue_maintenance`.

Todas esas acciones se filtran por `INSTALLATION_ID`. Requieren un worker activo y MongoDB disponible. Si la conexión falla mientras el worker continuo ya está ejecutándose, vuelve a revisar la cola; si falla el `ping` inicial del comando, la CLI sale y necesita relanzarse. En local el supervisor puede hacerlo; en Compose interviene la política `restart: unless-stopped`.

### Reanudar y cancelar

```bash
uv run nexolicit resume ID_DE_CONSULTA
```

La reanudación solo admite trabajos `failed` o `canceled`. Crea una continuación con los mismos filtros, selección de documentos y revisión de perfil; conserva checkpoints y errores pendientes. El origen sigue visible y la continuación registra `resume_of`. Enviar otra vez la reanudación del mismo origen devuelve la misma continuación mediante su clave de idempotencia; no crea una serie ilimitada de copias.

La continuación renueva el presupuesto de intentos porque hubo una acción explícita, pero respeta la pausa común de SICOP. Vuelve a comprobar el alcance reciente, de modo que una ventana de listado cambiante puede aumentar el progreso acumulado. Para continuar nuevamente una continuación fallida, se utiliza el identificador de esa continuación.

La cancelación se solicita en la pantalla de detalle de actividad. Es cooperativa: el worker la observa en sus controles. Una descarga o extracción que ya empezó puede tardar en alcanzar el siguiente control; la acción no equivale a borrar concursos ni a terminar instantáneamente un OCR.

### Qué hacer ante HTTP 429 de SICOP

Un 429 atendido por el cliente de SICOP o la consulta de metadatos detiene el intento y guarda una pausa por instalación. El plazo considera `Retry-After` como segundos o fecha HTTP y está acotado entre un minuto y un día. Sin plazo válido se usa una espera base de cinco minutos. Los 429 reiterados de un mismo trabajo elevan el mínimo a 5, 10 y 20 minutos con los tres intentos predeterminados; un plazo mayor de la fuente prevalece.

La pausa queda persistida, bloquea la reclamación de nuevos jobs de esa instalación y se mantiene después de reiniciar el worker, incluso si el trabajo que originó el 429 agotó sus intentos. La interfaz muestra la pausa general y la fecha del siguiente intento. No cambiar el identificador de instalación ni crear consultas repetidas para saltarse ese control.

El descargador de archivos binarios trata una respuesta distinta de 200 como error documental `DOCUMENT_HTTP_FAILED`; no todos los errores HTTP de descarga se convierten en una pausa compartida de la cola. Esta distinción ayuda a interpretar fallos de anexos sin atribuirles un comportamiento que el código no implementa.

## 6. Documentos: conservar evidencia y declarar sus límites

El servicio acepta archivos reconocidos por firma como PDF, PNG o JPEG. Una página HTML recibida por error no se interpreta como un pliego. Los originales se guardan en GridFS, el contenido se identifica con SHA-256 y las páginas extraídas se almacenan aparte para consulta y afinidad. El directorio `var/` se utiliza temporalmente durante la extracción.

| Estado documental | Interpretación |
|---|---|
| `processing` | Existe registro en proceso; una interrupción puede dejarlo para revisión posterior. |
| `ready` | Extracción finalizada sin errores de página registrados. |
| `partial` | Solo una parte pudo procesarse o se alcanzó algún límite. Las páginas legibles siguen siendo útiles. |
| `failed` | Descarga o referencias del documento no pudieron completarse. |
| `omitted` | Anexo fuera del número de archivos autorizado para la consulta. |

Una página PDF activa OCR si tiene menos de 40 caracteres extraídos o si tiene menos de 250 caracteres y contiene una imagen de al menos 800 × 800 píxeles. Tesseract usa español y `--psm 1` para orientación y estructura. Las páginas posteriores al máximo quedan señaladas mediante `PAGE_COUNT_LIMIT`; superar el límite no equivale a afirmar que el documento no contiene requisitos.

El extractor trabaja en un subproceso. En Unix aplica un límite de CPU de 110 segundos con límite duro de 115, y de archivo de 64 MiB; Linux agrega 1 GiB de memoria virtual. En Windows no existe ese mecanismo `resource`: queda el timeout del padre. Aumentar `EXTRACTION_TIMEOUT_SECONDS` no cambia los límites internos fijos de CPU, archivo o memoria. El JSON de salida aceptado por el padre se limita a 12 MiB.

En macOS, el procedimiento de OCR documentado por el repositorio es:

```bash
brew install tesseract tesseract-lang poppler
tesseract --list-langs
```

Confirmar que aparezcan `spa` y `osd`, y reiniciar web y worker para que hereden el `PATH` correcto. El contenedor incluye los paquetes de extracción. Una futura actualización debe comprobar también la presencia efectiva de ambos modelos en la imagen construida.

La versión del extractor es `pdf-ocr-v2`. Un documento guardado con otra versión se vuelve a procesar cuando se consulta de nuevo con anexos; no existe un reprocesamiento histórico ilimitado en segundo plano.

```bash
uv run nexolicit document-orphans
```

Este comando informa archivos completos de GridFS con más de un día y sin referencias `gridfs_id`, y también fragmentos sin manifiesto. Estos últimos pueden ser cargas activas: se reportan sin borrado, con edad estimada cuando el ObjectId lo permite. No declara segura ninguna limpieza. Un reintento de anexos usa una identidad nueva y verifica el blob completo antes de publicar; también repara referencias antiguas marcadas listas sin archivo disponible.

## 7. Despliegue con Docker y Atlas externo · opcional

Para Docker Desktop, configurar `.env.atlas` a partir de `.env.atlas.example` con credenciales Atlas separadas, `APP_MODE=local` y `PUBLIC_ORIGIN=http://localhost:8000`. El archivo no reemplaza `.env`. También puede generarse con `scripts/configure_atlas.py`; ver [operación](../operations.md#docker-desktop-con-atlas-externo).

```bash
docker compose up --build -d --wait

# Opcional si se desea crear la primera cuenta por consola.
docker compose run --rm --no-deps web /app/.venv/bin/nexolicit create-admin

docker compose ps --all
docker compose logs --tail=100 worker
```

`init-db` prepara índices y termina antes de iniciar web y worker separados. El servicio web publica `127.0.0.1:8000:8000`; en Docker Desktop puede abrirse directamente con HTTP local. Para un servidor público, configurar `APP_MODE=server`, `PUBLIC_ORIGIN=https://nombre-real`, `ENVIRONMENT=production` e `INSTALLATION_ID` exclusivo; se requiere un proxy HTTPS que preserve Host. Uvicorn tiene `proxy_headers=False`; no se debe asumir que confía en `X-Forwarded-For` o que reconstruye la IP del visitante. Los límites por dirección observan la dirección que recibe la aplicación, que puede ser la del proxy.

El repositorio no incluye configuración de proxy, certificados, balanceador, dominio o aprovisionamiento Atlas. Esas piezas deben prepararse en el entorno del despliegue. Para verificar el backend por loopback con un dominio configurado, conservar el Host esperado:

```bash
# Sustituir nombre-real por el hostname de PUBLIC_ORIGIN.
curl -H 'Host: nombre-real' http://127.0.0.1:8000/health/live
curl -H 'Host: nombre-real' http://127.0.0.1:8000/health/ready
```

Compose define usuario sin privilegios en la imagen, raíz del contenedor de solo lectura, capacidades eliminadas, `no-new-privileges`, `/tmp` temporal de 64 MiB, `/app/var` temporal de 256 MiB, 1536 MiB de límite de memoria y 2 CPU por servicio de aplicación. Esos límites pueden afectar anexos grandes o muchas páginas renderizadas; no equivalen a una garantía de capacidad de producción. Los datos permanentes viven en Atlas, incluidos los blobs GridFS.

### Habilitar la caché opcional

Para el Redis privado incluido, establecer en `.env.atlas`:

```dotenv
REDIS_URL=redis://redis:6379/0
```

Después:

```bash
docker compose --profile cache up -d
```

El servicio Redis no publica puertos, limita sus datos a 128 MiB con `allkeys-lru` y deshabilita RDB/AOF. Perder la caché no elimina catálogo, sesiones ni concursos. Si ya se usa Redis externo, configurar ese acceso y no iniciar el servicio adicional. Para un servidor Redis compartido se recomienda un usuario ACL exclusivo y privilegios restringidos a las claves del proyecto.

Los estados de caché son `disabled`, `configured` y `fallback`. `configured` significa que hay un cliente configurado y que no está en el intervalo de recuperación, no que un chequeo de salud haya comprobado conectividad a Redis. La lectura vuelve a MongoDB y al cálculo normal cuando Redis falla.

### Detener y actualizar

```bash
docker compose down
```

Detiene los contenedores y elimina sus áreas temporales; Atlas conserva la persistencia. Para actualizar, revisar el cambio de código y dependencias, preparar respaldo de la base, reconstruir la imagen y recrear web y worker. La continuación de los jobs depende de conservar base, configuración e `INSTALLATION_ID`.

La existencia de Dockerfile y Compose no demuestra que una construcción concreta haya pasado. Esta guía describe su configuración revisada en código; una aceptación de despliegue exige construir y probar en el entorno objetivo.

## 8. Referencia completa de CLI

La entrada instalada es `nexolicit = nexolicitcr.cli:app`. Typer convierte los nombres `init_db` y `create_admin` a `init-db` y `create-admin`. La definición está en [cli.py](../../src/nexolicitcr/cli.py).

| Comando | Opciones o argumentos | Efecto |
|---|---|---|
| `nexolicit --help` | — | Ayuda general; no ejecuta un trabajo de negocio. |
| `nexolicit init-db` | — | Prepara índices y documentos iniciales. |
| `nexolicit create-admin` | Prompts interactivos | Crea la primera cuenta sin contraseña en argumentos. |
| `nexolicit api` | `--port 8000`, `--worker / --no-worker` | Inicia Uvicorn; worker automático solo en modo local. |
| `nexolicit sync` | `--category bienes`, `--limit 20`, `--since FECHA`, `--once`, `--documents` | Encola una consulta durable; opcionalmente procesa un intento. Límite 1–500. |
| `nexolicit resume JOB_ID` | Identificador obligatorio | Crea o devuelve una continuación de un job fallido o cancelado. |
| `nexolicit worker` | `--once` | Atiende trabajos de la instalación; con `--once`, reclama como máximo uno disponible. |
| `nexolicit import-offers TENDER_KEY` | `--lot 1` | Consulta ofertas públicas presentadas de una partida; escribe el histórico correspondiente. |
| `nexolicit document-orphans` | — | Reporte JSON de candidatos GridFS huérfanos; solo lectura. |

Ejemplo de histórico:

```bash
uv run nexolicit import-offers CARTEL:SECUENCIA --lot 1
```

La clave del concurso debe existir y la partida debe ser válida. Este comando consulta la fuente externa y conserva precios **presentados**. No obtiene por ello un precio adjudicado comparable ni demuestra adjudicación final.

La CLI no incluye comandos propios de backup, restauración, borrado de trabajos, reinicio de contraseñas, programación periódica ni limpieza destructiva de GridFS. `worker --once` puede salir correctamente sin trabajo disponible; ese resultado no demuestra que haya sincronizado datos. La CLI usa código 1 para varias fallas de persistencia o intentos no exitosos, y código 2 para configuración o argumentos inválidos.

## 9. Referencia HTTP: interfaz, operaciones y salud

Las rutas se implementan en [web.py](../../src/nexolicitcr/web.py). FastAPI se configura con `/docs`, `/redoc` y `/openapi.json` deshabilitados. La mayoría de las rutas sirven HTML y formularios; no existe una API REST pública con autenticación por token independiente.

En la tabla, «sesión» significa cookie `nexo_session` válida. Todas las mutaciones exigen `Origin` idéntico a `PUBLIC_ORIGIN`; los formularios autenticados agregan CSRF. Registro e ingreso usan sus propias cookies y nonces de un uso. Los cuerpos POST/PUT/PATCH están limitados a 32768 bytes antes del parseo.

| Método y ruta | Acceso | Resultado principal |
|---|---|---|
| `GET /` | Registro abierto o sesión | Registro inicial, bienvenida sin perfil o panel de empresa. |
| `GET /register` | Público | Formulario inicial o explicación de registro cerrado. |
| `POST /register` | Nonce de registro + origen | Crea la primera cuenta y redirige a login; 409 si ya existe. |
| `GET /login` | Público | Formulario y nonce de ingreso. |
| `POST /login` | Nonce de login + origen | Valida credenciales y crea cookie de sesión. |
| `POST /logout` | Sesión + CSRF | Revoca la sesión almacenada y elimina cookie. |
| `GET /health/live` | Público, Host válido | JSON `{"status":"ok"}`; indica que responde el proceso. |
| `GET /health/ready` | Público, Host válido | Hace `ping` a MongoDB; muestra modo y estado de caché. |
| `GET /company` | Sesión | Formulario de empresa y revisión actual del catálogo. |
| `POST /company/draft` | Sesión + CSRF | Avanza al borrador de descubrimiento; no persiste aún el perfil final. |
| `GET /discover` | Sesión | Flujo de perfil y especialidades. |
| `POST /discover/draft` | Sesión + CSRF | Construye borrador y sugerencias deterministas. |
| `POST /discover/revise` | Sesión + CSRF | Revisa el borrador y conserva entradas del recorrido. |
| `POST /discover/confirm` | Sesión + CSRF | Persiste perfil confirmado con revisión; redirige a oportunidades. |
| `POST /discover/search` | Sesión + CSRF | Encola según categoría y revisión del perfil; redirige al job. Alcance 10–100, predeterminado 25. |
| `GET /catalog` | Sesión | Catálogo; `edit` selecciona un ítem existente. |
| `POST /catalog` | Sesión + CSRF | Crea o edita un ítem con revisión optimista; redirige al catálogo. |
| `GET /tenders` | Sesión | Lista paginada; `page` 1–1000 y `q` de hasta 120 caracteres. |
| `GET /tenders/{key}` | Sesión | Concurso, afinidad, documentos, histórico y decisión. |
| `GET /opportunities` | Sesión | Radar filtrado por estado, texto, categoría y afinidad mínima. |
| `POST /decisions/{key}` | Sesión + CSRF | Guarda `relevant`, `following`, `discarded` o `none`, con nota opcional. |
| `GET /jobs` | Sesión | Últimos 50 trabajos de la instalación y pausa de fuente. |
| `POST /sync-runs` | Sesión + CSRF | Encola; JSON 202 o redirección 303 si `Accept` incluye `text/html`. |
| `GET /jobs/{job_id}` | Sesión | JSON de estado, progreso, intento, errores, próxima fecha y pausa compartida. |
| `GET /jobs/{job_id}/view` | Sesión | Detalle HTML del trabajo. |
| `POST /jobs/{job_id}/resume` | Sesión + CSRF | Continúa un trabajo fallido o cancelado y redirige al nuevo detalle. |
| `POST /jobs/{job_id}/cancel` | Sesión + CSRF | Solicita cancelación cooperativa. |
| `GET /documents/{document_id}` | Sesión | Estado del documento y páginas extraídas. |
| `GET /documents/{document_id}/download` | Sesión | Descarga binaria desde GridFS como `documento.bin`; 404 si falta. |
| `/static/...` | Público, Host válido | Archivos estáticos servidos por el montaje de Starlette. |

El radar admite `status=active|all|following|discarded|unknown|closed`, `category=all|bienes|servicios|obras`, `minimum` entre 0 y 100, `page` entre 1 y 1000 y texto `q` de hasta 120 caracteres. Presenta 25 filas por página. El listado de concursos también muestra 25. La puntuación es afinidad explicable, no un porcentaje de probabilidad de ganar ni una certificación de elegibilidad.

`POST /sync-runs` acepta formularios con `category`, `limit` 1–500, `since`, `idempotency_key` de 1–128 caracteres y `documents`. La respuesta JSON 202 confirma que el trabajo quedó persistido, no que SICOP respondió. Una misma clave con otros filtros se rechaza. Una solicitud HTML recibe una redirección después del guardado.

La consulta JSON de job incluye `pending_count`, calculado por identidades de error aún sin checkpoint. No cuenta concursos que todavía no se han descubierto. La falta de sesión devuelve redirección 303 a `/login`; para clientes automatizados hay que contemplar esa respuesta, cookies, origen y CSRF. No se proporciona aquí una receta para eludir el flujo de autenticación.

## 10. Diagnóstico: de la señal a la acción

| Señal | Qué comprobar | Recuperación apropiada |
|---|---|---|
| «Configuración inválida» en CLI | Variables obligatorias, modo, URI, origen y rangos. | Comparar con los ejemplos sanitizados y reiniciar el proceso. El mensaje evita exponer secretos. |
| «MongoDB no disponible o sin permisos» | Base seleccionada, credenciales, acceso de red Atlas o estado del replica set. | Restaurar conectividad/permisos y relanzar si falló el arranque inicial. |
| HTTP 503 | `ping` o alguna operación MongoDB falló. | Revisar MongoDB; conservar la cola y datos existentes. |
| Host inválido / HTTP 400 | Navegador o proxy usa hostname diferente al configurado. | Alinear Host y `PUBLIC_ORIGIN`. |
| «Origen inválido» / HTTP 403 | Esquema, hostname y puerto de `Origin`; nonce o CSRF vencido. | Abrir la URL configurada y recargar el formulario. |
| HTTP 409 al guardar | La revisión cambió en otra ventana. | Recargar, revisar el cambio concurrente y volver a guardar conscientemente. |
| Job `queued` sin avance | Worker activo, misma base e instalación, `next_attempt_at`, pausa de SICOP. | Iniciar el worker correcto y respetar la programación. |
| `WORKER_INTERRUPTED` | Lease recuperado tras una caída. | Mantener el worker activo; revisar el progreso conservado. |
| `LEASE_EXHAUSTED` | Se agotaron intentos en un trabajo pendiente o abandonado. | Corregir causa y usar reanudación explícita. |
| `SOURCE_RATE_LIMITED` | Fuente indicó 429; existe pausa compartida. | Esperar el plazo persistido; no multiplicar consultas. |
| `SOURCE_PARTIAL` / `SOURCE_INVALID` | Uno o más concursos/documentos fallaron. | Abrir detalle y revisar identidades; conservar éxitos y reanudar si procede. |
| `DEPENDENCY_UNAVAILABLE` | Error de fuente o persistencia durante un intento. | Recuperar dependencia y esperar reintento dentro del presupuesto. |
| `DOCUMENT_URL_REJECTED` | Host, HTTPS o puerto fuera de la política. | Verificar procedencia antes de ajustar `DOCUMENT_HOSTS`. |
| `DOCUMENT_TOO_LARGE` / `FILE_COUNT_LIMIT` | Archivo o cantidad supera el alcance configurado. | Revisar manualmente y ajustar límites solo si capacidad y necesidad lo justifican. |
| `OCR_UNAVAILABLE`, `OCR_SPANISH_UNAVAILABLE`, `OCR_ORIENTATION_UNAVAILABLE` | Ejecutable o modelos ausentes. | Instalar dependencias, comprobar idiomas y reiniciar procesos. |
| `EXTRACTION_FAILED_OR_LIMIT` | Timeout, proceso fallido, salida inválida o límite interno. | Revisar documento y recursos; consultar de nuevo con anexos tras corregir la causa. |
| Caché `fallback` | Operación Redis falló o devolvió contenido inválido. | Revisar Redis; el negocio sigue apoyado en MongoDB. |
| Registro cerrado | Ya existe una cuenta en la base. | Usar la cuenta existente; el formulario no restablece contraseñas. |

`/health/live` no comprueba base, worker, extracción ni disponibilidad de SICOP. `/health/ready` comprueba MongoDB, pero no reclama jobs, no extrae archivos y no hace ping activo a Redis. Por eso la aceptación operativa necesita además revisar actividad y ejecutar un caso controlado en un entorno autorizado.

## 11. Seguridad y continuidad

### Controles implementados

Las contraseñas se almacenan con Argon2 mediante pwdlib. La base guarda hash del token de sesión; la vigencia se comprueba en la consulta, además del índice TTL. El cierre de sesión borra su registro, y un usuario inactivo deja de satisfacer la validación de sesión.

Las cookies usan `HttpOnly` y `SameSite=Strict`; `Secure` se activa cuando `PUBLIC_ORIGIN` usa HTTPS. Registro e ingreso generan nonces de 15 minutos y un solo uso. Los intentos se limitan en MongoDB por dirección y nombre: 30 por dirección y 10 por usuario en ventanas de 15 minutos. La política usa hashes de identificadores y persiste límites entre procesos.

La aplicación agrega CSP, `X-Content-Type-Options: nosniff`, `Referrer-Policy: same-origin`, `Cache-Control: no-store` y HSTS cuando corresponde. El catálogo y el perfil usan control de revisión para evitar sobrescribir silenciosamente una edición concurrente. Las descargas validan destino y tamaño; los errores públicos de persistencia no muestran detalles de conexión.

[.gitignore](../../.gitignore) excluye `.env`, credenciales, `var/`, logs, descargas, entorno virtual y artefactos de ejecución. [.dockerignore](../../.dockerignore) limita el contexto de construcción al código y dependencias necesarias; `.env` se suministra en runtime. Estas exclusiones no protegen un secreto que ya se hubiera agregado a Git de forma forzada o se hubiera publicado por otro medio.

### Prácticas recomendadas, no funciones automatizadas

El proyecto no implementa un gestor de backups. Un procedimiento de operación debe definir quién respalda, qué datos incluye, con qué frecuencia, dónde se cifra y cuánto tarda una restauración. La estrategia debe cubrir conjuntamente las colecciones de negocio y GridFS (`fs.files` y `fs.chunks`), ya que guardar solo metadatos documentales no recupera el archivo original.

Para Atlas, utilizar las funciones de respaldo disponibles en el entorno contratado o un procedimiento oficial de copia lógica verificado para esa instalación. Para MongoDB local, usar herramientas oficiales de respaldo/restauración compatibles con el despliegue y evitar asumir que copiar archivos de un servidor activo produce una copia consistente. Las credenciales de administración del helper también necesitan custodia separada y acceso restringido.

Antes de aceptar un respaldo, restaurarlo en una base aislada y verificar catálogo, versiones, documentos descargables, cola y acceso de la aplicación. Definir expresamente el tratamiento de sesiones restauradas y credenciales. El objetivo de recuperación y la pérdida máxima tolerable de datos son decisiones operativas; el código no declara valores de RTO o RPO ni alta disponibilidad.

Mantener instalación y base exclusivas por empresa, rotar secretos por un procedimiento administrado, restringir la salida y entrada de red según el entorno y conservar TLS en el proxy y en Atlas son prácticas recomendadas. No se afirma que el repositorio las aprovisione automáticamente. El replica set local de un nodo habilita transacciones, pero no demuestra tolerancia a la pérdida de ese nodo.

## 12. Validación reproducible y alcance de la evidencia

### Comprobaciones sin infraestructura externa

```bash
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv run pytest -m 'not integration'
uv run python scripts/check_publishable.py
```

La suite normal usa fixtures y dobles, incluido mongomock para persistencia y un doble Redis. No necesita una consulta a SICOP ni demuestra por sí misma transacciones físicas, disponibilidad Atlas, tiempos de red o comportamiento del servidor MongoDB real. Algunos casos de OCR dependen de los binarios nativos; el resumen de pytest debe conservar sus saltos junto con los aprobados.

| Grupo / archivo de prueba | Evidencia que aporta |
|---|---|
| [test_config.py](../../tests/test_config.py) | Reglas de configuración, orígenes y modos de persistencia. |
| [test_registration.py](../../tests/test_registration.py), [test_web.py](../../tests/test_web.py) | Registro, autenticación, formularios, rutas y controles HTTP. |
| [test_jobs.py](../../tests/test_jobs.py), [test_cli_jobs.py](../../tests/test_cli_jobs.py) | Cola, reintentos, cancelación, reanudación y comandos relacionados. |
| [test_ingestion.py](../../tests/test_ingestion.py), [test_sicop.py](../../tests/test_sicop.py) | Normalización, importación y manejo de respuestas de la fuente con datos controlados. |
| [test_cache_matching.py](../../tests/test_cache_matching.py), [test_search_regressions.py](../../tests/test_search_regressions.py) | Afinidad, filtros y equivalencia de resultados ante caché. |
| [test_documents_history.py](../../tests/test_documents_history.py), [test_ocr_quality.py](../../tests/test_ocr_quality.py) | Documentos, histórico y extracción con las condiciones previstas por cada prueba. |
| [test_multi_specialties.py](../../tests/test_multi_specialties.py), [test_onboarding.py](../../tests/test_onboarding.py) | Perfiles y recorridos con especialidades múltiples. |

`check_publishable.py` inspecciona archivos versionados y nuevos no ignorados; busca patrones de datos privados y exige revisión de binarios desconocidos. Su lista de permitidos registra la ruta y la huella SHA-256 exacta de cada binario revisado. Un PDF nuevo puede producir «binary requires manual review»: eso exige revisar el artefacto, no prueba automáticamente que contenga un secreto. Después de revisar contenido, metadatos y presentación, se puede registrar su huella exacta; cualquier cambio posterior vuelve a exigir revisión. No desactivar la auditoría para convertir esa señal en un resultado ficticio de aprobación.

### Resultado ejecutado durante esta edición

El 18 de octubre de 2026 se ejecutó la suite sin integración sobre Python 3.12.15, con acceso directo al código fuente:

```bash
PYTHONPATH=src .venv/bin/python -m pytest -m 'not integration'
```

Resultado: **329 pruebas aprobadas, 7 deseleccionadas, 1565 advertencias de deprecación, en 6,84 segundos**. Las siete deseleccionadas pertenecen al alcance excluido por el marcador; no son siete pruebas fallidas. Una primera invocación sin `PYTHONPATH` no pudo importar el paquete porque ese entorno no lo tenía instalado; la segunda invocación resolvió explícitamente `src/` y completó la suite. Las advertencias se conservan como deuda de compatibilidad, no se presentan como errores funcionales.

Esta ejecución no inició MongoDB, no comprobó Atlas, no construyó Docker ni consultó SICOP. Tampoco convierte los comandos de integración, OCR nativo o microbenchmark descritos más adelante en resultados recién medidos. El propósito es dejar una evidencia precisa y reproducible de la regresión local que sí se comprobó.

### Integración contra una base dedicada

Estas pruebas requieren consentimiento operativo sobre una base exclusiva cuyo nombre empiece por `nexolicit_test_`. Preparar MongoDB y su configuración antes de ejecutarlas. No usar la base cotidiana ni marcar simultáneamente ambas modalidades.

```bash
# MONGO_MODE=local debe estar configurado.
NEXO_TEST_LOCAL=1 NEXO_TEST_DATABASE=nexolicit_test_local uv run pytest -m integration

# Alternativa: MONGO_MODE=atlas debe estar configurado.
NEXO_TEST_ATLAS=1 NEXO_TEST_DATABASE=nexolicit_test_integration uv run pytest -m integration
```

Las pruebas de [test_atlas_integration.py](../../tests/test_atlas_integration.py) comprueban transacciones, idempotencia y rollback con MongoDB real. Algunos casos de ese archivo son específicos de MongoDB local y OCR español; pueden saltarse en Atlas o sin herramientas nativas. El nombre del archivo no significa que todos sus casos usen exclusivamente Atlas.

[test_restart_integration.py](../../tests/test_restart_integration.py) sí inicia una API como subproceso, la termina sin apagado ordenado y la vuelve a levantar. Comprueba persistencia de catálogo y sesión, además de rechazo del token revocado. Requiere una base de prueba sin administrador previo y conserva/restaura el catálogo según su fixture.

[test_worker_recovery_integration.py](../../tests/test_worker_recovery_integration.py) ejecuta workers reales como subprocesos, provoca una caída y comprueba recuperación con lease de 15 segundos y protección transaccional frente a un propietario vencido. Usa instalación y registros propios; exige ausencia de concursos activos de obras que interfieran con la prueba y limpia los datos que creó.

Pytest no inicia un servidor MongoDB. Las pruebas de integración de reinicio y recuperación sí administran procesos API/worker contra la base ya disponible. Las fixtures de integración evitan consultar SICOP y no borran una base completa, pero escriben y limpian datos: la exigencia de aislamiento sigue siendo necesaria.

### Medir sin exagerar resultados

```bash
uv run python scripts/benchmark_matching.py --output artifacts/matching-benchmark.json
uv run python scripts/audit_ocr.py --output artifacts/ocr-audit.json
```

El primer script usa por defecto 100 y 1.000 concursos; `--counts 100 10000` conserva la ampliación de escala. Si hay miss/bypass, el tiempo de lectura de caché se deja nulo y no se presenta como mejora. Es un microbenchmark sin conexión de cálculo y serialización; no mide red MongoDB, Redis real, latencia de SICOP ni capacidad concurrente del servidor. El segundo genera documentos sintéticos y mide recuperación de frases conocidas mediante OCR a través de los sectores comerciales; requiere los binarios y una fuente compatible. No mide calidad universal de pliegos reales ni precisión comercial del ranking.

Para evaluar la utilidad del radar hacen falta pares de catálogo/concurso etiquetados por personas y criterios de aceptación acordados. La evaluación humana por pares y los estudios con empresas son ampliaciones opcionales, sin muestra mínima para la entrega universitaria. Las etiquetas inventadas automáticamente no sustituyen esa referencia humana. Un benchmark rápido y una suite aprobada son evidencias distintas de una validación con usuarios.

### Registro sugerido de una validación

Guardar fecha, revisión Git, versión de Python, modalidad de base, comando exacto, cantidad de pruebas aprobadas/saltadas, duración, resultado y limitaciones. Para la documentación generada en esta revisión, separar los resultados realmente ejecutados de los comandos propuestos; no trasladar cifras de una máquina o commit anterior como si fueran una medición nueva.

## 13. Recorrido de aceptación para una demostración

Una demostración convincente debe permitir que la persona que observa entienda tanto el valor como la evidencia que respalda cada paso:

1. Arrancar con base e índices preparados, comprobar salud y abrir la URL configurada.
2. Registrar la primera cuenta, iniciar sesión y describir una empresa concreta con varias especialidades si corresponde.
3. Revisar y confirmar las capacidades sugeridas; explicar que la empresa conserva control sobre su perfil.
4. En un entorno autorizado para consultar la fuente, lanzar una búsqueda acotada y mostrar que queda registrada en Actividad.
5. Abrir una oportunidad y relacionar su afinidad con términos, códigos o fragmentos documentales.
6. Mostrar fecha, estado y evidencia parcial cuando exista; consultar el expediente original para requisitos pendientes.
7. Marcar seguimiento o descarte y agregar una nota de decisión.
8. Explicar recuperación y reanudación con fixtures o un entorno de prueba, sin provocar interrupciones en una base de trabajo real.
9. Cerrar sesión y comprobar que el acceso vuelve a requerir autenticación.

El argumento de venta se sostiene en una experiencia observable: la empresa convierte su actividad en una búsqueda repetible, recibe razones para priorizar y conserva la memoria de sus decisiones. La honestidad operativa —progreso durable, límites visibles y evidencia rastreable— es parte del producto.

## 14. Fuentes y notas de consistencia

Esta guía prioriza el contrato observado en [config.py](../../src/nexolicitcr/config.py), [cli.py](../../src/nexolicitcr/cli.py), [jobs.py](../../src/nexolicitcr/jobs.py), [runtime.py](../../src/nexolicitcr/runtime.py), [web.py](../../src/nexolicitcr/web.py), [documents.py](../../src/nexolicitcr/documents.py), [extractor.py](../../src/nexolicitcr/extractor.py) y [storage.py](../../src/nexolicitcr/storage.py). Como contexto complementario: [operación existente](../operations.md), [validación de fuente](../source-validation.md), [revisión OCR](../ocr-review.md) y [README](../../README.md).

Al contrastar documentación y código conviene conservar estas precisiones:

- El `README` contiene una reserva general sobre fechas sin offset; la configuración de ejemplo y el documento de validación especifican `America/Costa_Rica`. El código deja fechas pendientes únicamente cuando la zona no está configurada.
- Una frase de la guía operativa anterior indica que pytest no inicia API; los tests de reinicio sí lo hacen como subproceso. MongoDB sigue siendo una precondición externa.
- No todas las respuestas web de sincronización son 202: el formulario HTML y el recorrido de descubrimiento redirigen con 303; el endpoint de sincronización devuelve 202 cuando responde JSON.
- Un job exitoso no asegura que todos los anexos se hayan leído: los documentos omitidos por el límite conservan su estado explícito.
- `cache=configured` describe configuración y ventana de recuperación, no disponibilidad medida mediante ping.
- Los fallos durante el bucle continuo del worker permiten recuperación; un fallo del `ping` inicial requiere relanzamiento por operador o supervisor.

Estas distinciones evitan promesas que la implementación no hace y permiten enseñar el sistema con precisión técnica.
