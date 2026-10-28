# Registro de decisiones de arquitectura (ADR)

Este documento reúne las decisiones técnicas más relevantes de NexoLicitCR. Para cada una se indica el contexto, las alternativas evaluadas, la decisión tomada y sus consecuencias. El formato sigue la convención de *Architecture Decision Records* (Michael Nygard): una decisión aceptada no se edita; si cambia, se agrega una nueva entrada que la reemplaza.

| Estado | Significado |
|---|---|
| **Aceptada** | Vigente e implementada en `main`. |
| **Propuesta** | En discusión; todavía no condiciona el código. |
| **Reemplazada** | Sustituida por otra entrada, que se indica. |

## Índice

| ID | Decisión | Estado |
|---|---|---|
| [ADR-001](#adr-001-monolito-modular-en-python) | Monolito modular en Python | Aceptada |
| [ADR-002](#adr-002-python-312313-y-uv-como-gestor-de-dependencias) | Python 3.12/3.13 y uv como gestor de dependencias | Aceptada |
| [ADR-003](#adr-003-fastapi--uvicorn-como-capa-http) | FastAPI + Uvicorn como capa HTTP | Aceptada |
| [ADR-004](#adr-004-renderizado-en-servidor-con-jinja2-sin-framework-spa) | Renderizado en servidor con Jinja2, sin framework SPA | Aceptada |
| [ADR-005](#adr-005-mongodb-como-fuente-de-verdad) | MongoDB como fuente de verdad | Aceptada |
| [ADR-006](#adr-006-una-base-de-datos-exclusiva-por-instalación) | Una base de datos exclusiva por instalación | Aceptada |
| [ADR-007](#adr-007-gridfs-para-anexos-íntegros-deduplicados-por-sha-256) | GridFS para anexos íntegros, deduplicados por SHA-256 | Aceptada |
| [ADR-008](#adr-008-historial-inmutable-de-concursos-por-hash-de-contenido) | Historial inmutable de concursos por hash de contenido | Aceptada |
| [ADR-009](#adr-009-cola-de-trabajos-durable-en-mongodb-con-leases) | Cola de trabajos durable en MongoDB con leases | Aceptada |
| [ADR-010](#adr-010-redis-opcional-como-caché-desechable) | Redis opcional como caché desechable | Aceptada |
| [ADR-011](#adr-011-motor-de-afinidad-basado-en-reglas-versionadas) | Motor de afinidad basado en reglas versionadas | Aceptada |
| [ADR-012](#adr-012-extracción-documental-pypdf-primero-ocr-tesseract-como-respaldo) | Extracción documental: pypdf primero, OCR Tesseract como respaldo | Aceptada |
| [ADR-013](#adr-013-ingesta-sicop-con-httpx-y-beautifulsoup) | Ingesta SICOP con HTTPX y BeautifulSoup | Aceptada |
| [ADR-014](#adr-014-autenticación-propia-con-argon2-y-sesiones-persistentes) | Autenticación propia con Argon2 y sesiones persistentes | Aceptada |
| [ADR-015](#adr-015-configuración-tipada-con-pydantic-settings) | Configuración tipada con pydantic-settings | Aceptada |
| [ADR-016](#adr-016-cli-operativa-con-typer) | CLI operativa con Typer | Aceptada |
| [ADR-017](#adr-017-docker-endurecido-y-opcional) | Docker endurecido y opcional | Aceptada |
| [ADR-018](#adr-018-calidad-pytest-mongomock-ruff-y-pip-audit) | Calidad: pytest, mongomock, Ruff y pip-audit | Aceptada |
| [ADR-019](#adr-019-manejo-explícito-de-zona-horaria-de-sicop) | Manejo explícito de zona horaria de SICOP | Aceptada |
| [ADR-020](#adr-020-importes-monetarios-como-decimal-serializado) | Importes monetarios como decimal serializado | Aceptada |

---

## Principios rectores

Estas restricciones del dominio guiaron todas las decisiones posteriores:

1. **Equipo pequeño, plazo académico.** Cada componente adicional debe justificar su costo de operación. Menos piezas móviles significa menos puntos de fallo y menos documentación.
2. **El usuario objetivo es una PYME, no un equipo de TI.** La instalación tiene que funcionar en una laptop con Windows, sin clúster ni orquestador.
3. **La fuente (SICOP) es externa, lenta e inestable.** El sistema no puede depender de que responda; toda sincronización debe poder interrumpirse y reanudarse.
4. **Una coincidencia es una sugerencia, no un dictamen.** El sistema debe explicar *por qué* sugiere un concurso y nunca afirmar elegibilidad legal.
5. **Trazabilidad.** Cualquier resultado tiene que poder reconstruirse: qué versión del concurso, qué revisión del catálogo y qué versión de las reglas lo produjeron.
6. **Seguro por defecto.** Ninguna opción de configuración relaja TLS, credenciales ni aislamiento de datos.

---

## ADR-001: Monolito modular en Python

**Estado:** Aceptada

### Contexto

El producto combina cinco responsabilidades: interfaz web, ingesta desde SICOP, descarga y extracción de documentos, cálculo de afinidad y tareas en segundo plano. Una arquitectura de microservicios permitiría escalarlas por separado, pero el volumen esperado (una empresa por instalación, cientos a pocos miles de concursos activos) no lo requiere.

### Alternativas evaluadas

| Opción | Ventajas | Desventajas |
|---|---|---|
| Microservicios (API, ingesta, OCR, matching) | Escalado independiente, aislamiento de fallos | Red entre servicios, contratos versionados, despliegue coordinado, observabilidad distribuida. Costo desproporcionado para el volumen. |
| Monolito sin separación interna | Mínimo esfuerzo inicial | Acoplamiento creciente; difícil de probar por partes. |
| **Monolito modular** | Un solo artefacto y despliegue; módulos con límites claros (`ingestion`, `documents`, `extractor`, `matching`, `jobs`, `storage`) | El escalado es por proceso completo. |

### Decisión

Un único paquete Python (`nexolicitcr`) con módulos de responsabilidad única. El mismo binario se ejecuta en dos roles: `nexolicit api` (web) y `nexolicit worker` (trabajos). En modo local, `api` levanta también el worker para que el usuario solo abra una terminal.

### Consecuencias

- Las llamadas entre módulos son funciones Python, sin serialización ni latencia de red.
- La separación web/worker por proceso conserva la principal ventaja de los microservicios: el OCR pesado no bloquea la interfaz.
- Si en el futuro una parte necesita escalar sola (por ejemplo, OCR), los límites de módulo permiten extraerla sin reescribir el resto.

---

## ADR-002: Python 3.12/3.13 y uv como gestor de dependencias

**Estado:** Aceptada

### Contexto

El dominio está dominado por procesamiento de texto, parsing de HTML y PDF, y OCR. El ecosistema de Python es el más maduro para esas tareas y es el lenguaje que domina el equipo.

### Decisión

- **Versión:** `>=3.12,<3.14`. 3.12 trae mejoras de rendimiento del intérprete (≈5 % respecto a 3.11 en cargas generales), mensajes de error más precisos y la sintaxis de tipos genéricos de PEP 695. El techo `<3.14` evita adoptar una versión que las dependencias nativas todavía no soportan.
- **Gestor:** `uv` en lugar de pip + venv o Poetry.

### Justificación de uv

| Criterio | pip + requirements | Poetry | **uv** |
|---|---|---|---|
| Lockfile reproducible multiplataforma | No (solo `pip freeze`) | Sí | Sí (`uv.lock`) |
| Velocidad de resolución e instalación | Lenta | Media | Muy rápida (Rust, caché global) |
| Instala la versión de Python | No | No | Sí |
| Estándar `pyproject.toml` (PEP 621) | Parcial | Formato propio en versiones antiguas | Sí |
| Grupos de dependencias (PEP 735) | No | Propio | Sí |

`uv sync --frozen` garantiza que CI, Docker y las máquinas del equipo instalen exactamente el mismo árbol de dependencias. La versión de uv está fijada (`0.12.24`) en CI y Dockerfile para que el propio gestor no introduzca variación.

### Consecuencias

- Rangos de versión semánticos en `pyproject.toml` (`>=x,<siguiente-mayor`) y versiones exactas en `uv.lock`: se aceptan parches de seguridad sin aceptar cambios incompatibles.
- `tzdata` se declara explícitamente porque Windows no incluye la base IANA de zonas horarias (ver [ADR-019](#adr-019-manejo-explícito-de-zona-horaria-de-sicop)).

---

## ADR-003: FastAPI + Uvicorn como capa HTTP

**Estado:** Aceptada

### Contexto

Se necesita un framework web que sirva HTML, procese formularios, exponga endpoints de salud y se integre con validación de datos.

### Alternativas evaluadas

- **Django:** ORM relacional, admin y autenticación incluidos. Su ORM no aporta valor con MongoDB y obliga a cargar un framework grande del que se usaría una fracción.
- **Flask:** liviano y conocido, pero la validación, la inyección de dependencias y el tipado quedan a cargo de extensiones de terceros.
- **FastAPI:** inyección de dependencias nativa, integración directa con Pydantic, tipado de extremo a extremo y servidor ASGI.

### Decisión

FastAPI como framework y Uvicorn como servidor ASGI.

### Consecuencias

- Las dependencias de FastAPI (`Depends`) centralizan sesión, CSRF y acceso a la base en un solo punto, lo que reduce la posibilidad de olvidar una verificación en una ruta.
- Los mismos modelos Pydantic validan formularios, documentos de MongoDB y configuración.
- El soporte asíncrono queda disponible, aunque PyMongo es síncrono; las rutas que usan la base se declaran síncronas y FastAPI las ejecuta en su pool de hilos, sin bloquear el event loop.

---

## ADR-004: Renderizado en servidor con Jinja2, sin framework SPA

**Estado:** Aceptada

### Contexto

La interfaz consiste en formularios, listados filtrables y fichas de concurso. No hay colaboración en tiempo real ni interacciones que requieran estado complejo en el cliente.

### Alternativas evaluadas

| Opción | Costo |
|---|---|
| React/Vue + API JSON | Segundo proyecto (npm, bundler, build), duplicación de validaciones, manejo de tokens en el cliente, superficie mayor de dependencias de terceros. |
| **HTML renderizado en servidor (Jinja2) + JS nativo puntual** | Un solo lenguaje de backend, sin paso de build, escape automático contra XSS. |

### Decisión

Plantillas Jinja2 con autoescape, CSS propio y JavaScript nativo solo para mejoras progresivas. Sin npm, sin CDN y sin fuentes externas.

### Consecuencias

- **Seguridad:** sin scripts de terceros, la política de contenido puede ser estricta y no hay riesgo de cadena de suministro de paquetes npm.
- **Privacidad:** ningún recurso se carga desde dominios externos, por lo que el navegador del usuario no filtra su actividad a terceros.
- **Rendimiento:** la primera pintura llega con el HTML; no hay bundle que descargar ni hidratar.
- **Accesibilidad:** los formularios funcionan sin JavaScript; las animaciones respetan `prefers-reduced-motion`.

---

## ADR-005: MongoDB como fuente de verdad

**Estado:** Aceptada

### Contexto

Los datos de SICOP son heterogéneos: un concurso tiene partidas, líneas, anexos, fechas y estructuras que varían entre modalidades de contratación y que cambian sin aviso. El catálogo de la empresa es un agregado con ítems, términos, exclusiones y capacidades que siempre se lee y se escribe completo.

### Alternativas evaluadas

- **PostgreSQL:** integridad referencial fuerte y JSONB para datos semiestructurados. Modelar el concurso como tablas normalizadas exigiría migraciones cada vez que SICOP agregue un campo; usarlo solo como JSONB desaprovecha el modelo relacional.
- **SQLite:** ideal para escritorio, pero sin transacciones concurrentes entre procesos web y worker con la robustez necesaria, y sin almacenamiento de binarios grandes adecuado.
- **MongoDB:** modelo de documentos alineado con la forma de los datos, transacciones multidocumento sobre replica set, índices TTL, GridFS y servicio gestionado (Atlas) con capa gratuita.

### Decisión

MongoDB es la única fuente de verdad. Se exige replica set (Atlas o local) porque las transacciones lo requieren.

### Consecuencias

- El snapshot de un concurso se guarda tal como se normalizó, sin traducción a tablas.
- El catálogo es un documento con `revision` monotónica; las actualizaciones usan control de concurrencia optimista (`revision` esperada en el filtro) en vez de bloqueos.
- No hay claves foráneas: las referencias son lógicas y la aplicación es responsable de su consistencia. Para compensarlo, las escrituras que deben ser atómicas (snapshot + versión, texto documental) usan transacciones.
- Índices TTL eliminan sesiones y tokens vencidos sin tareas programadas; la aplicación verifica igualmente la expiración, porque el TTL de MongoDB se ejecuta cada ~60 s y no es instantáneo.
- TLS siempre activo contra Atlas; no existe opción para desactivar la validación de certificados.

---

## ADR-006: Una base de datos exclusiva por instalación

**Estado:** Aceptada

### Contexto

Diseñar un sistema multiempresa (multi-tenant) desde el inicio implica filtrar por empresa en cada consulta, índices compuestos por inquilino y un riesgo permanente de fuga de datos entre clientes por un filtro olvidado.

### Decisión

Una empresa por instalación y una base MongoDB exclusiva por instalación. `INSTALLATION_ID` identifica workers y claves de caché, pero **no** convierte una base compartida en un sistema multiempresa.

### Consecuencias

- El aislamiento lo garantiza la infraestructura (credenciales y base distintas), no la disciplina del código.
- Respaldar, restaurar o eliminar los datos de una empresa equivale a operar sobre una sola base.
- El registro web se cierra al crear la primera cuenta: no existe flujo para que un tercero se registre en una instalación ajena.
- Si el producto evoluciona a SaaS, será necesario un ADR nuevo con estrategia de *tenancy*.

---

## ADR-007: GridFS para anexos íntegros, deduplicados por SHA-256

**Estado:** Aceptada

### Contexto

Los carteles de SICOP incluyen anexos (PDF, imágenes) que contienen la mayor parte de la información útil para decidir. Hay que conservarlos para extraer texto, reprocesarlos si mejora el extractor y demostrar qué documento originó una evidencia.

### Alternativas evaluadas

| Opción | Evaluación |
|---|---|
| Sistema de archivos local | Simple, pero se pierde con el contenedor (Docker con `read_only`), no se respalda junto con la base y no es transaccional respecto a los metadatos. |
| Almacenamiento de objetos (S3, Azure Blob) | Escalable, pero agrega un proveedor, credenciales y costo; excesivo para el volumen. |
| Binario embebido en el documento | Límite de 16 MiB por documento BSON. |
| **GridFS** | Sin límite práctico de tamaño (fragmentos de 255 KiB), mismo respaldo, mismas credenciales y misma red que el resto de los datos. |

### Decisión

Los anexos se descargan íntegros con límite de tamaño y se guardan en GridFS. La identidad del binario es su **SHA-256**: si dos concursos publican el mismo archivo, se almacena una sola vez.

### Consecuencias

- Integridad verificable: el hash detecta corrupción y permite comprobar que el documento no cambió.
- La carga a GridFS ocurre antes de la transacción de metadatos (GridFS no participa de forma práctica en transacciones). Si el proceso se interrumpe entre ambos pasos pueden quedar binarios huérfanos; el comando `document-orphans` los reporta en modo de solo lectura en lugar de borrarlos automáticamente, para no perder datos por un falso positivo.
- Los binarios nunca se exponen por URL pública.

---

## ADR-008: Historial inmutable de concursos por hash de contenido

**Estado:** Aceptada

### Contexto

SICOP modifica concursos ya publicados (prórrogas, aclaraciones, enmiendas). Si solo se guardara el último estado, una sugerencia no podría explicarse con los datos que la produjeron.

### Decisión

- `tenders` contiene el snapshot vigente con `_id = cartelNo:cartelSeq`.
- `tender_versions` guarda cada versión distinta, identificada por concurso + hash del contenido normalizado.
- Ambos se escriben en la misma transacción.

### Consecuencias

- Reingestar un concurso sin cambios no genera escrituras (mismo hash): la operación es idempotente.
- Cada `match` registra el hash del concurso, la revisión del catálogo y la versión de reglas; un resultado siempre es reproducible.
- `metadata.corpus.generation` se incrementa con cada cambio real del corpus y sirve como clave de invalidación de caché ([ADR-010](#adr-010-redis-opcional-como-caché-desechable)).

---

## ADR-009: Cola de trabajos durable en MongoDB con leases

**Estado:** Aceptada

### Contexto

La ingesta y la extracción documental pueden tardar minutos u horas, y SICOP puede limitar o cortar la conexión. Los trabajos deben sobrevivir a reinicios, no ejecutarse dos veces en paralelo y reanudarse desde el último punto confirmado.

### Alternativas evaluadas

| Opción | Evaluación |
|---|---|
| Celery + RabbitMQ/Redis | Estándar de la industria, pero añade un broker obligatorio, otro proceso de monitoreo y semántica de reintento que hay que ajustar. Redis como broker además contradice [ADR-010](#adr-010-redis-opcional-como-caché-desechable), que lo define como desechable. |
| RQ / Dramatiq | Más simples, pero igualmente dependientes de un broker. |
| Tareas en segundo plano de FastAPI | Se pierden si el proceso termina; sin reintentos ni estado. |
| **Cola propia sobre MongoDB** | Reutiliza la base existente; estado consultable con las mismas herramientas; transaccional con los datos que el trabajo modifica. |

### Decisión

Colección `jobs` con:

- **Clave de idempotencia** por instalación: encolar dos veces el mismo trabajo no lo duplica.
- **Lease con token (fencing):** el worker que reclama un trabajo recibe un `lease_token` aleatorio y un `lease_until`. Toda escritura posterior incluye el token en el filtro; si el lease venció y otro worker lo reclamó, las escrituras del worker anterior no tienen efecto.
- **Heartbeat** que renueva el lease mientras el trabajo avanza.
- **Checkpoints** para reanudar desde el último elemento procesado.
- **Mantenimiento idempotente** que repara trabajos con lease vencido sin reclamar leases vigentes ni borrar historial.

### Consecuencias

- Se evita el problema clásico del *split brain* en workers (dos procesos que creen poseer el mismo trabajo) gracias al token de fencing.
- Una pausa de la fuente (`source_pause_until`) frena a todos los workers cuando SICOP indica sobrecarga, respetando a la fuente.
- El throughput es menor que el de un broker dedicado, pero varios órdenes de magnitud superior al que exige el dominio.

---

## ADR-010: Redis opcional como caché desechable

**Estado:** Aceptada

### Contexto

El radar de afinidad recalcula coincidencias entre catálogo y corpus. Es la vista más costosa y la más consultada.

### Decisión

Redis se usa **solo** como caché de lectura, nunca como fuente de verdad. `REDIS_URL` vacío lo desactiva y el sistema funciona igual.

- **Claves versionadas, sin invalidación activa:** la clave incluye aplicación, entorno, instalación, hash de la base, revisión del catálogo, versión de reglas, generación del corpus y hash de filtros. Cualquier cambio produce otra clave; la anterior expira sola por TTL (120 s). No se recorren claves ni se ejecuta `FLUSHDB`/`FLUSHALL`.
- **Fallo rápido:** timeouts de 150 ms, sin reintentos inmediatos y *circuit breaker* de 30 s. Una caché lenta es peor que no tener caché.
- **Límite de 4 MiB por valor:** resultados más grandes se calculan desde MongoDB.
- **Datos dinámicos fuera de caché:** decisiones del usuario y vencimientos se calculan en cada respuesta.
- **Mínimo privilegio:** usuario ACL propio limitado al prefijo de la instalación y a `GET`/`SET`.

### Consecuencias

- Es imposible servir un resultado obsoleto respecto a catálogo, reglas o corpus: la clave cambia antes de que el dato quede viejo.
- Una caída de Redis degrada la latencia, no la funcionalidad.
- Varias aplicaciones pueden compartir un servidor Redis sin colisiones ni riesgo de borrado cruzado.

---

## ADR-011: Motor de afinidad basado en reglas versionadas

**Estado:** Aceptada

### Contexto

El núcleo del producto es responder "¿este concurso es relevante para mi empresa?". La opción de moda sería un modelo de lenguaje o búsqueda por *embeddings*.

### Alternativas evaluadas

| Opción | Evaluación |
|---|---|
| LLM (clasificación por prompt) | Alta cobertura semántica, pero no determinista, costoso por consulta, difícil de auditar y con riesgo de afirmar elegibilidad que no existe. Envía datos de la empresa a un tercero. |
| Embeddings + similitud vectorial | Buena recuperación semántica, pero el "por qué" es una distancia numérica, no una razón comprensible; requiere índice vectorial y un modelo. |
| **Reglas léxicas versionadas** | Deterministas, explicables, rápidas y ejecutables sin red. |

### Decisión

Reglas de afinidad deterministas con versión explícita (`RULES_VERSION`):

- Normalización de texto: minúsculas, eliminación de tildes, reunión de palabras cortadas por saltos de línea de PDF/OCR y eliminación de guiones discrecionales.
- Coincidencia por término y por código de clasificación, con exclusiones definidas por la empresa.
- Alias explícitos por categoría (por ejemplo, "pavimentación" ↔ "colocación de mezcla asfáltica" solo dentro de Obras), para ampliar cobertura sin inferir capacidades que la empresa no declaró.
- Cada coincidencia guarda la razón (qué término, qué producto, qué evidencia documental).

### Consecuencias

- **Explicabilidad:** el usuario ve exactamente qué palabra de qué documento disparó la sugerencia.
- **Reproducibilidad:** cambiar las reglas incrementa `RULES_VERSION`, lo que recalcula coincidencias e invalida la caché.
- **Medición:** los conjuntos de referencia en `docs/benchmarks/` permiten comparar precisión y exhaustividad entre versiones de reglas antes de publicarlas.
- Menor cobertura semántica que un modelo; se compensa con alias curados y con la taxonomía de sectores. Un modelo semántico podría incorporarse como *señal adicional* en un ADR futuro, nunca como sustituto de las razones explícitas.

---

## ADR-012: Extracción documental: pypdf primero, OCR Tesseract como respaldo

**Estado:** Aceptada

### Contexto

Los anexos son una mezcla de PDF con texto digital y documentos escaneados. El OCR es entre uno y dos órdenes de magnitud más lento que leer la capa de texto de un PDF.

### Decisión

Estrategia escalonada por página:

1. **pypdf** extrae el texto digital.
2. Si la página no tiene texto útil, se rasteriza con **Poppler (`pdftoppm`)** y se reconoce con **Tesseract** usando el modelo de idioma español (`spa`).
3. **Pillow** valida y convierte imágenes PNG/JPEG.

Cada página guarda su texto, el método (digital u OCR), la versión del extractor y, si falló, el error explícito.

### Alternativas descartadas

- **PyMuPDF:** más rápido, pero su licencia AGPL impone obligaciones incompatibles con la distribución prevista del proyecto.
- **OCR en la nube (Google Vision, AWS Textract):** mejor precisión en escaneos de baja calidad, pero con costo por página y envío de documentos a terceros.

### Consecuencias

- Las herramientas nativas se invocan con lista de argumentos (sin shell, sin inyección de comandos), en un proceso separado con límite de tiempo y, en Linux, de memoria.
- Un solo OCR concurrente por worker evita que un lote de escaneos agote la memoria del equipo.
- Los estados parciales son explícitos: un documento puede tener páginas extraídas y páginas con error, y la interfaz lo muestra en lugar de ocultarlo.

---

## ADR-013: Ingesta SICOP con HTTPX y BeautifulSoup

**Estado:** Aceptada

### Contexto

SICOP no ofrece una API pública documentada para todo lo necesario; parte de la información se obtiene de respuestas HTML.

### Decisión

- **HTTPX** como cliente HTTP: timeouts explícitos por fase, límites de tamaño de respuesta, soporte HTTP/2 y API compatible con `requests`.
- **BeautifulSoup4** para el parsing HTML, por su tolerancia a marcado mal formado.
- La validación de la fuente (formatos de fecha, campos, códigos) se documenta en `docs/source-validation.md`.

### Consecuencias

- Toda petición tiene tiempo máximo y tamaño máximo: un servidor lento o una respuesta enorme no bloquea al worker.
- El parsing está aislado en `sicop.py`; si SICOP cambia su HTML, el impacto se limita a un módulo con pruebas propias.
- La ingesta es respetuosa con la fuente: pausas ante señales de sobrecarga y reconsulta solo de concursos activos.

---

## ADR-014: Autenticación propia con Argon2 y sesiones persistentes

**Estado:** Aceptada

### Contexto

Cada instalación tiene un único administrador. Integrar un proveedor de identidad externo (OAuth, Keycloak, Auth0) agregaría dependencia de red y configuración desproporcionada para un solo usuario.

### Decisión

- Contraseñas con **Argon2id** (vía `pwdlib`), ganador de la *Password Hashing Competition* y recomendación actual de OWASP, resistente a ataques con GPU por su consumo de memoria.
- Longitud de contraseña de 14 a 256 caracteres, sin reglas de composición arbitrarias (alineado con NIST SP 800-63B).
- Sesiones persistentes en MongoDB; en la base solo se guarda el **hash** del token, nunca el token.
- Protección **CSRF** en todos los formularios que modifican estado.
- Limitación de intentos de inicio de sesión (`login_limits`).
- Alta del administrador sin contraseña por defecto, ya sea desde la web (solo si no existe ninguna cuenta) o por CLI con entrada oculta.

### Consecuencias

- Una filtración de la base no permite secuestrar sesiones ni recuperar contraseñas en tiempo práctico.
- En modo servidor se exige HTTPS y origen exacto (`PUBLIC_ORIGIN`); no se confía automáticamente en cabeceras `X-Forwarded-*`, lo que evita suplantación de origen detrás de proxies mal configurados.

---

## ADR-015: Configuración tipada con pydantic-settings

**Estado:** Aceptada

### Decisión

Toda la configuración se lee de variables de entorno o `.env` mediante `pydantic-settings`, con tipos y validaciones. Las credenciales de Atlas se pasan a PyMongo como parámetros separados, nunca concatenadas en la URI.

### Consecuencias

- Una configuración inválida (zona horaria inexistente, URI mal formada, modo desconocido) falla al arrancar, no en mitad de una sincronización.
- Las credenciales no aparecen en la URI, por lo que no se filtran en logs ni en mensajes de error.
- `.env` está excluido de Git y un script de CI (`check_publishable.py`) verifica que no se publiquen secretos.

---

## ADR-016: CLI operativa con Typer

**Estado:** Aceptada

### Decisión

Un único punto de entrada `nexolicit` (Typer) agrupa todas las operaciones: `api`, `worker`, `init-db`, `create-admin`, ingesta y diagnósticos como `document-orphans`.

### Consecuencias

- Las mismas órdenes funcionan en local, en Docker y en CI; no hay scripts sueltos con comportamientos distintos.
- `init-db` es idempotente: crea índices sin borrar colecciones y puede ejecutarse en cada arranque.
- Typer genera la ayuda (`--help`) a partir de las firmas tipadas, de modo que la documentación de la CLI no se desactualiza.

---

## ADR-017: Docker endurecido y opcional

**Estado:** Aceptada

### Contexto

Docker facilita reproducir el entorno, especialmente las dependencias nativas de OCR. Pero exigirlo excluiría a usuarios sin Docker Desktop.

### Decisión

Docker es opcional. La imagen y `compose.yaml` aplican defensa en profundidad:

- *Build* multietapa: la imagen final no contiene `uv`, compiladores ni dependencias de desarrollo.
- Usuario sin privilegios (`uid 10001`).
- Sistema de archivos de solo lectura, con `tmpfs` acotado para temporales.
- `cap_drop: [ALL]` y `no-new-privileges`.
- Límites de memoria y CPU.
- Puerto publicado solo en `127.0.0.1`.
- `init-db` como servicio previo; `web` y `worker` arrancan solo si terminó correctamente.
- Redis en un perfil aparte (`cache`), sin persistencia y con política `allkeys-lru`.

### Consecuencias

- Un compromiso de la aplicación tiene un radio de impacto reducido: sin root, sin escritura en disco y sin capacidades del kernel.
- La instalación sin Docker sigue siendo de primera clase, documentada en el README.

---

## ADR-018: Calidad: pytest, mongomock, Ruff y pip-audit

**Estado:** Aceptada

### Decisión

| Herramienta | Propósito |
|---|---|
| **pytest** | Pruebas unitarias e integración; las de integración se marcan (`integration`) y solo corren contra una base aislada configurada explícitamente. |
| **mongomock** | Doble de MongoDB en memoria para pruebas rápidas sin infraestructura. |
| **Ruff** | Lint y formato en una sola herramienta (sustituye flake8, isort, pyupgrade y black), con reglas de seguridad (`S`, derivadas de Bandit) y de errores probables (`B`). |
| **pip-audit** | Auditoría de vulnerabilidades conocidas en dependencias. |

CI en GitHub Actions ejecuta lint, formato, pruebas y verificación de publicabilidad en cada *push* y *pull request*. Las acciones están fijadas por SHA de commit, no por etiqueta, para evitar ataques de cadena de suministro mediante etiquetas reasignadas. El token de CI tiene permisos de solo lectura.

### Consecuencias

- Las pruebas que dependen de transacciones reales no pueden validarse con mongomock; por eso existe la capa de integración contra un replica set real.
- Un cambio que rompe formato o reglas de seguridad no llega a `main`.

---

## ADR-019: Manejo explícito de zona horaria de SICOP

**Estado:** Aceptada

### Contexto

SICOP publica fechas sin desplazamiento horario, en hora local de Costa Rica. Interpretarlas como UTC adelantaría o atrasaría seis horas los cierres de recepción de ofertas: un error que puede hacer perder un concurso.

### Decisión

- `SICOP_TIMEZONE=America/Costa_Rica` convierte las fechas a instantes absolutos.
- Si la variable está vacía, las fechas se conservan como **pendientes de interpretación** en lugar de asumir una zona.
- Internamente se almacena todo en UTC.
- `tzdata` es dependencia explícita para que la base IANA exista también en Windows.

### Consecuencias

- Los vencimientos son correctos independientemente de la zona del servidor o del navegador.
- Nunca se muestra una fecha con una zona inventada.

---

## ADR-020: Importes monetarios como decimal serializado

**Estado:** Aceptada

### Contexto

Los montos de ofertas y presupuestos pueden tener muchos dígitos y varias monedas. `float` introduce errores de redondeo binario (`0.1 + 0.2 != 0.3`), inaceptables en información financiera.

### Decisión

Los importes se procesan con `decimal.Decimal` y se serializan como texto en MongoDB, junto con su moneda. Nunca se convierten a `float`.

### Consecuencias

- Precisión exacta y sin pérdida en el ida y vuelta a la base.
- Las comparaciones y ordenamientos numéricos se hacen en la aplicación, no en consultas de MongoDB.
- El histórico guarda **ofertas presentadas**, no adjudicaciones: el sistema no presenta un precio ofertado como precio ganador mientras no exista una fuente de adjudicación validada.

