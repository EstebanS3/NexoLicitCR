# Datos y componentes

![Estructura MongoDB](assets/mongodb-schema.png)

Una empresa por instalación y **una base MongoDB exclusiva por instalación**. `INSTALLATION_ID` separa workers y caché; no convierte una base compartida en un sistema multiempresa.

| Colección | Identidad y finalidad |
|---|---|
| `users` | Administrador único, hash Argon2, estado activo. |
| `sessions`, `login_tokens`, `login_limits` | Tokens hash y vencimientos; índices TTL. La aplicación comprueba expiración. |
| `catalog` | `_id=company`, revisión monotónica, ítems embebidos con términos, exclusiones y capacidades. |
| `tenders` | `_id=cartelNo:cartelSeq`, snapshot normalizado, hash y procedencia; importes decimales serializados como texto. |
| `tender_versions` | Histórico inmutable identificado por concurso y hash. Escritura transaccional junto al snapshot. |
| `documents` | Concurso, identidad del anexo, SHA-256, estado, versión vigente y referencia GridFS. |
| `fs.files`, `fs.chunks` | Binarios GridFS deduplicados por SHA-256. No se exponen públicamente. |
| `extracted_pages` | Documento + página únicos; texto, método digital/OCR, versión y error explícito. |
| `matches` | Empresa, revisión de catálogo, hash de concurso, reglas y generación documental. Razones por producto. |
| `decisions` | Empresa + concurso; seguimiento, descarte y nota independientes del recálculo. |
| `offers` | Concurso + hash fuente + posición; precio presentado, partida, moneda, calificación y URL. **No adjudicación**. |
| `jobs` | Instalación + idempotencia; estado, token de lease, heartbeat, intentos, checkpoints y errores. |
| `sync_runs` | Resumen de trabajos terminales y corridas anteriores. |
| `metadata` | `_id=corpus`, generación durable incrementada con cambios de concursos/documentos. |

Referencias lógicas, sin claves foráneas. La publicación de concursos y texto documental usa transacciones MongoDB; GridFS se carga antes y los huérfanos se reportan con `document-orphans`. El reporte es deliberadamente de solo lectura. Solo una página OCR por proceso de worker a la vez; escalar workers también escala ese consumo.

## Redis opcional y aislamiento

```text
{REDIS_NAMESPACE}:{ENVIRONMENT}:{INSTALLATION_ID}:{db_hash}:v1:
company:company:radar:catalog:{revision}:rules:{rules_version}:corpus:{generation}:{filter_hash}
```

`db_hash` deriva del endpoint MongoDB sin credenciales y nombre de base. Configurar un `INSTALLATION_ID` único y estable. Cambiar catálogo, reglas o corpus genera otra clave; no se recorren claves ni se ejecuta FLUSHDB/FLUSHALL. TTL predeterminado: 120 segundos. Timeout de conexión/lectura: 150 ms, sin reintentos inmediatos. Circuit breaker: 30 segundos. Límite por valor: 4 MiB; resultados mayores se calculan desde MongoDB.

`REDIS_URL` vacío desactiva Redis. Un fallo o contenido ilegible activa fallback. Las decisiones y el vencimiento se consultan/calculan en cada respuesta, incluso con caché. Una lectura comprueba la versión antes de devolver el snapshot, con hasta tres intentos ante cambios concurrentes.

El prefijo evita colisiones accidentales; la separación de permisos requiere **un usuario Redis ACL propio**, restringido a `~nexolicitcr:production:mi-instalacion:*`, comandos GET/SET y comandos de conexión que use el cliente (PING, CLIENT SETNAME/SETINFO). No otorgar FLUSHDB, FLUSHALL, KEYS ni permisos de otras aplicaciones. Usar `rediss://` para transporte remoto. No incluir credenciales reales en ejemplos ni comandos guardados.

## Dependencias Python directas

Las versiones resueltas están en `uv.lock`; los rangos están en `pyproject.toml`.

| Componente | Librería | Uso |
|---|---|---|
| API y web | FastAPI, Uvicorn | Rutas, formularios, salud y servidor ASGI. |
| Vistas | Jinja2 | HTML del lado servidor con escape automático. |
| Configuración/contratos | pydantic-settings, Pydantic (transitiva) | `.env` privado y validación de modelos. |
| Persistencia/documentos | PyMongo, GridFS (incluido) | MongoDB, índices, transacciones y binarios. |
| Fuente SICOP | HTTPX, BeautifulSoup4 | HTTP acotado y parsing HTML. |
| Autenticación | pwdlib[argon2], python-multipart | Hash de contraseñas y formularios. |
| Operación | Typer | API, worker, inicialización, ingesta y diagnóstico por CLI. |
| Caché | redis | Cliente opcional, timeouts y recuperación. |
| Documentos | pypdf, Pillow | Texto PDF y validación/conversión de PNG/JPEG. |
| Desarrollo | pytest, mongomock, Ruff, pip-audit | Pruebas, dobles MongoDB, lint/formato y auditoría. |

Dependencias nativas OCR: **Tesseract + idioma español (`spa`) y Poppler (`pdftoppm`)**. Python las invoca por argumentos, sin shell, en un proceso separado con límite de tiempo; en Linux también memoria. Docker incluye ambas. No se usa PyMuPDF ni se copia código externo. Stack de interfaz: HTML, CSS y JavaScript nativo; sin npm, React ni fuentes/CDN externas.

## Origen de la imagen

Imagen generada con ImageGen, revisada visualmente e incluida en `docs/assets/mongodb-schema.png`. Prompt resumido reproducible: “Infografía editorial horizontal en marfil, azul oscuro y oliva, titulada NexoLicitCR · Estructura de datos. MongoDB fuente de verdad y Redis caché opcional. Seis bloques: acceso (users/sessions/login_tokens/login_limits), empresa (catalog/revision/items), concursos (tenders/tender_versions/offers presentadas), documentos (documents/extracted_pages/GridFS), análisis (matches/decisions), operación (jobs/sync_runs/metadata corpus.generation). Flechas de referencias lógicas y pie de claves Redis por aplicación, entorno, instalación, base, versión, empresa, recurso, revisión, reglas, generación y filtros. Sin datos personales ni credenciales.” La tabla anterior es la especificación precisa del esquema.
