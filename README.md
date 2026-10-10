# NexoLicitCR

Aplicación Python para registrar el catálogo de una empresa y consultar concursos de SICOP. Monolito FastAPI/Jinja2 con persistencia MongoDB Atlas. La comparación automática de compatibilidad y los avisos son la siguiente etapa; esta versión no certifica elegibilidad para participar.

## Funcionalidad actual

- Administrador inicial, sesiones persistentes, protección CSRF y límite de intentos.
- Crear, editar y desactivar productos/servicios con capacidades, cobertura, términos y exclusiones.
- Ingesta manual de listado, detalle y líneas de SICOP; paginación y consultas acotadas por rubro.
- Concursos actuales e historial de versiones por contenido; reimportación idempotente.
- Pantallas de catálogo, búsqueda y detalle de concursos con condiciones textuales escapadas.
- Redis no es requerido ni utilizado por esta entrega. No se han implementado cola durable, OCR, ranking ni adjudicaciones comparables.

## Instalación

Requiere Python 3.12 o 3.13, uv y una base de desarrollo en Atlas con permisos de lectura/escritura e índices. La ejecución local también requiere Internet para Atlas.

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
| `REDIS_URL` | Reservado para la futura caché opcional. |

TLS Atlas siempre está habilitado. No se admiten opciones que relajen la validación de certificados. `.env` nunca debe versionarse.

```bash
uv run nexolicit init-db
uv run nexolicit create-admin
uv run nexolicit api
```

Abrir `http://localhost:8000`. Crear administrador solicita la contraseña por entrada oculta (14–256 caracteres), sin contraseña predeterminada. Solo permite un administrador; no reemplaza cuentas existentes. Inicializar índices es idempotente y no borra colecciones. Mantener credenciales y copias de seguridad fuera de Git.

Para servidor: configurar `APP_MODE=server`, origen HTTPS y un proxy TLS que preserve el Host; exponer exclusivamente el proxy y restringir el puerto del backend. El servidor no confía automáticamente en cabeceras reenviadas. Este repositorio no provisiona Atlas ni despliega servicios públicos.

## Importación manual

```bash
uv run nexolicit sync --category bienes --limit 10
uv run nexolicit sync --category all --limit 5 --since 2026-01-01
```

`limit` limita los concursos procesados por rubro, no el número de solicitudes necesarias para filtrar fechas. La corrida queda registrada; una importación parcial termina con código de error. Las fechas se filtran del lado del cliente y no se presupone orden descendente perfecto. No se usa una marca de agua que oculte actualizaciones: las corridas acotadas revisitan los registros consultados; para cobertura histórica/activos fuera de ese rango se requieren barridos adicionales. Máximo 100 páginas por recurso; alcanzar el límite se informa como consulta incompleta.

La fecha de cierre se toma del detalle (`biddocEndDt`), nunca de la apertura. Condiciones referidas a anexos no implican ausencia de requisitos. Precios de líneas son presupuestados, no adjudicados. El JSON se interpreta con decimales exactos y se guarda como texto decimal; unidades desconocidas permanecen desconocidas.

Las versiones y el estado actual se guardan en una transacción Atlas con mayoría; un fallo revierte la escritura. Un registro observado antes que el almacenado no lo reemplaza. Cada secuencia SICOP se conserva separada hasta validar su relación; no se mezclan expedientes arbitrariamente.

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

La prueba crea índices y catálogo inicial si faltan; limpia únicamente los documentos de concursos que ella creó, nunca toda la base. Usar una base descartable dedicada. Redis y OCR no se simulan como funcionalidades terminadas.

## Privacidad y límites

El catálogo y las sesiones se guardan en Atlas. `.gitignore` excluye credenciales, entornos, logs, descargas, datos de ejecución y planificación local. Lockfile, ejemplos sanitizados y fixtures sí se versionan. Revisar manualmente metadatos de archivos y autoría de commits antes de publicar; la comprobación automática complementa esa revisión.

No se han confirmado todos los requisitos necesarios para participar a partir de la API: varias condiciones remiten al pliego. Revisar el expediente original. La interpretación de fechas sin offset y las muestras de anexos digitales/escaneados siguen pendientes de validación integral. No confundir precios ofertados o presupuestados con adjudicaciones finales.
