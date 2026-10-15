# Operación y validación

## Arranque bajo demanda

```bash
uv sync --frozen
uv run nexolicit init-db
uv run nexolicit create-admin
uv run nexolicit api
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

Límites por defecto: 20 MiB/archivo, 5 anexos/concurso, 30 páginas, 120 segundos de extracción total. PDF con menos de 40 caracteres por página usa OCR español. Fallos y páginas no procesadas quedan explícitos, no equivalen a “sin requisitos”. `DOCUMENT_HOSTS` solo admite hosts HTTPS exactos previamente verificados. Los hosts Oracle de URLs firmadas **no están habilitados automáticamente**; comprobar la procedencia antes de agregarlos. No guardar ni publicar esas URLs firmadas.

```bash
uv run nexolicit document-orphans
uv run nexolicit import-offers CARTEL:SECUENCIA --lot 1
```

El histórico es por partida y conserva importes presentados; una consulta inválida falla, no se convierte en “sin ofertas”. RF-16 (comparables adjudicados) permanece indisponible hasta validar una fuente final por línea/unidad/moneda.

## Servidor con Atlas externo

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

Los tests con mongomock son evidencia de lógica, no de transacciones/recuperación física real. No se inicia MongoDB ni API automáticamente desde pytest. Para evaluar calidad se necesitan 30–50 pares catálogo/concurso etiquetados por humanos; no sustituirlos por etiquetas generadas. La prueba de equivalencia de caché usa un doble Redis con caída/recuperación; la latencia real requiere un Redis de prueba.
