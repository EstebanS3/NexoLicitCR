<p align="center">
  <img src="docs/assets/nexolicitcr-logo.png" alt="NexoLicitCR: conexión y automatización para PYMES" width="680">
</p>

<h1 align="center">NexoLicitCR</h1>
<p align="center"><strong>Automatizamos la búsqueda. Tu PYME construye el futuro.</strong></p>
<p align="center">Catálogo empresarial · Concursos SICOP · Automatización progresiva</p>

---

NexoLicitCR busca acercar las compras públicas de Costa Rica a las pequeñas y medianas empresas. Su objetivo es conectar lo que tu empresa ofrece con lo que las instituciones necesitan, reducir la revisión repetitiva de concursos y ayudarte a decidir cuáles merecen atención.

**Catálogo, radar de afinidad, seguimiento y sincronizaciones durables** en un monolito Python. La UI combina azul profundo, marfil, jerarquía editorial y animaciones accesibles. Una coincidencia ayuda a revisar un expediente; no garantiza elegibilidad.

- Administrador, sesiones persistentes, CSRF y catálogo con revisión de concurrencia.
- Ingesta SICOP, versiones, reconsulta de activos y trabajos con leases/checkpoints.
- Radar con razones por término/código, evidencia documental y decisiones independientes.
- Descarga acotada a GridFS, extracción PDF/OCR español y estados parciales explícitos.
- Redis opcional con aislamiento por aplicación, entorno, instalación y base, invalidación versionada y fallback.
- Histórico de **ofertas presentadas**. Comparables adjudicados pendientes de fuente validada.

![Estructura de datos MongoDB](docs/assets/mongodb-schema.png)

Ver [arquitectura y librerías](docs/architecture.md), [operación y Docker](docs/operations.md) y [estado verificable de los issues](docs/planning-status.md).

## Instalación

Requiere Python 3.12 o 3.13, uv y MongoDB Atlas o un replica set local autenticado. OCR requiere Tesseract español y Poppler.

```bash
uv sync --frozen
cp .env.example .env
```

Completar `.env` localmente:

| Variable | Uso |
|---|---|
| `ATLAS_URI` | URI `mongodb+srv://...mongodb.net/` sin usuario ni contraseña. |
| `ATLAS_USUARIO`, `ATLAS_CLAVE` | Credenciales; se pasan a PyMongo sin concatenación. |
| `ATLAS_BASE` | Base exclusiva de esta instalación. |
| `ATLAS_AUTHDB` | Base de autenticación, normalmente `admin`. |
| `APP_MODE` | `local` o `server`. |
| `PUBLIC_ORIGIN` | Origen exacto del navegador; local: `http://localhost:8000`. |
| `SICOP_TIMEZONE` | Vacío conserva fechas sin zona como pendientes; configurar una zona IANA solo después de validar su significado. |
| `REDIS_URL` | Vacío deshabilita la caché; configurar un usuario Redis ACL propio en servidor. |

`MONGO_MODE=atlas` es el valor predeterminado. TLS Atlas siempre está habilitado. No se admiten opciones que relajen la validación de certificados. `.env` nunca debe versionarse.

```bash
uv run nexolicit init-db
uv run nexolicit api
```

En modo local, `nexolicit api` arranca también el worker; no requiere otra terminal. Para gestionarlo por separado: `nexolicit api --no-worker`.

En una instalación nueva, abrir `http://localhost:8000`: si no hay cuenta, la página inicial muestra directamente el registro y la empresa elige su usuario y contraseña (14–256 caracteres), inicia sesión y configura su actividad. El registro se cierra al crear la primera cuenta, incluso si después se desactiva; no hay registro adicional ni reinicio de credenciales desde ese formulario.

Como alternativa para quien administra el servidor, `uv run nexolicit create-admin` solicita la contraseña por entrada oculta (14–256 caracteres), sin contraseña predeterminada. Solo permite un administrador; no reemplaza cuentas existentes. Inicializar índices es idempotente y no borra colecciones. Mantener credenciales y copias de seguridad fuera de Git.

Para servidor: configurar `APP_MODE=server`, origen HTTPS y un proxy TLS que preserve el Host; exponer exclusivamente el proxy y restringir el puerto del backend. El servidor no confía automáticamente en cabeceras reenviadas. Este repositorio no provisiona Atlas ni despliega servicios públicos.

## Desarrollo con MongoDB local

La UI incluye login, catálogo, radar, seguimiento, sincronizaciones, documentos y detalle de concursos. Para probarla sin Atlas, usar MongoDB Community como **replica set de un nodo**; un servidor standalone no permite las transacciones utilizadas por la ingesta. Compass administra el servidor, pero no lo reemplaza.

Instalar el binario oficial `mongod` siguiendo la [guía de MongoDB](https://www.mongodb.com/docs/v8.0/tutorial/install-mongodb-on-os-x-tarball/). Se puede extraer dentro de `var/tools/`, que está ignorado. El helper utiliza el puerto 27017 y no reemplaza un `.env` existente:

```bash
uv sync --frozen
uv run python scripts/local_mongo.py start --mongod /ruta/al/binario/mongod
uv run nexolicit create-admin
uv run nexolicit api
```

El helper crea `.env` con permisos 0600, claves aleatorias, autenticación y un replica set `nexo-local` enlazado exclusivamente a `127.0.0.1`. Inicializa `nexolicit_local` e índices. El usuario de la aplicación tiene permisos `readWrite` exclusivamente en `nexolicit_local` y `nexolicit_test_local`. Las credenciales administrativas y la clave del replica set quedan en `var/mongodb/`, fuera de Git. No borrar esa carpeta si se desea conservar los datos. Los reinicios usan el mismo comando `start`.

`MONGO_MODE=local` utiliza exclusivamente las variables `MONGO_LOCAL_*` de [.env.local.example](.env.local.example); no requiere credenciales Atlas. Solo se admite con `APP_MODE=local`, URI `mongodb://127.0.0.1:27017/?replicaSet=nexo-local` (puerto explícito), sin credenciales embebidas ni opciones adicionales. TLS se mantiene obligatorio para Atlas. En local, el transporte sin TLS queda limitado a loopback y requiere autenticación.

Abrir `http://localhost:8000`. En Compass, conectar con la URI local del `.env` y configurar autenticación Username/Password, usuario y clave `MONGO_LOCAL_USUARIO` / `MONGO_LOCAL_CLAVE`, y Authentication Database `admin`. No pegar credenciales en capturas, commits ni el PR.

Prueba real con fixture sintético, sin consultar SICOP:

```bash
NEXO_TEST_LOCAL=1 NEXO_TEST_DATABASE=nexolicit_test_local uv run pytest -m integration
```

Verifica escritura transaccional, reimportación idempotente y rollback entre colecciones. La selección de pruebas debe coincidir con `MONGO_MODE`. Nunca usar una base compartida. Un solo nodo no comprueba tolerancia a fallos ni alta disponibilidad.

Para detener la API: Ctrl+C en su terminal. Para detener MongoDB conservando los datos:

```bash
uv run python scripts/local_mongo.py stop
```

## Importación manual

```bash
uv run nexolicit sync --category bienes --limit 10 --once
uv run nexolicit sync --category all --limit 5 --since 2026-01-01 --once
```

`sync` sin `--once` encola un trabajo; ejecutar `worker` para procesarlo. La UI devuelve 202 después de persistir. `--once` procesa un intento y devuelve error si queda parcial. `limit` limita entradas nuevas y, por separado, activos reconsultados por rubro. Los activos se revisitan empezando por los menos recientemente consultados; las fechas desconocidas permanecen explícitas. Más detalles de límites y recuperación en [operación](docs/operations.md).

La fecha de cierre se toma del detalle (`biddocEndDt`), nunca de la apertura. Condiciones referidas a anexos no implican ausencia de requisitos. Precios de líneas son presupuestados, no adjudicados. El JSON se interpreta con decimales exactos y se guarda como texto decimal; unidades desconocidas permanecen desconocidas.

Las versiones y el estado actual se guardan en una transacción MongoDB con mayoría; un fallo revierte la escritura. Un registro observado antes que el almacenado no lo reemplaza. Cada secuencia SICOP se conserva separada hasta validar su relación; no se mezclan expedientes arbitrariamente.

## Pruebas

```bash
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv run pytest -m 'not integration'
uv run python scripts/check_publishable.py
```

Fixtures sintéticas con estructura observada de SICOP; no contienen instituciones ni personas reales. Las pruebas con mongomock comprueban lógica y HTTP, no transacciones de MongoDB real. Las de integración están separadas y no consultan SICOP en CI.

Para verificar Atlas de forma explícita, configurar `.env` y una base de prueba cuyo nombre empiece por `nexolicit_test_`:

```bash
NEXO_TEST_ATLAS=1 NEXO_TEST_DATABASE=nexolicit_test_integration uv run pytest -m integration
```

La prueba crea índices y catálogo inicial si faltan; limpia únicamente los documentos de concursos que ella creó, nunca toda la base. Usar una base descartable dedicada. La lógica de Redis se prueba con un doble; OCR escaneado/mixto real, Redis real y Atlas requieren validación adicional.

## Privacidad y límites

El catálogo y las sesiones se guardan en la base MongoDB seleccionada. `.gitignore` excluye credenciales, entornos, logs, descargas, datos de ejecución y planificación local. Lockfile, ejemplos sanitizados y fixtures sí se versionan. Revisar manualmente metadatos de archivos y autoría de commits antes de publicar; la comprobación automática complementa esa revisión.

No se han confirmado todos los requisitos necesarios para participar a partir de la API: varias condiciones remiten al pliego. Revisar el expediente original. La interpretación de fechas sin offset y las muestras de anexos digitales/escaneados siguen pendientes de validación integral. No confundir precios ofertados o presupuestados con adjudicaciones finales.


## Identidad y licencia

El símbolo conecta módulos para formar una **N** y una dirección de avance: representa a una PYME que transforma información dispersa en oportunidades mediante automatización. El azul profundo aporta solidez y el verde identifica conexión y crecimiento.

Distribuido bajo la [licencia MIT](LICENSE).

## Evolución propuesta

[Descubrimiento guiado desde la actividad de la empresa](docs/guided-discovery.md): configuración de empresa, sector, especialidad y revisión de servicios en `/company` y `/discover`. Incluye 20 sectores y 65 especialidades editables, oportunidades explicadas y consultas acotadas de SICOP. Las sugerencias son deterministas y requieren confirmación; feedback asistido y evaluación humana siguen pendientes.

La cola conserva avances y respeta pausas de SICOP ante HTTP 429. Desde Actividad se pueden reanudar consultas fallidas o canceladas sin perder checkpoints ni duplicar continuaciones. También: `uv run nexolicit resume ID_DE_CONSULTA`. Ver [operación y límites](docs/operations.md).
