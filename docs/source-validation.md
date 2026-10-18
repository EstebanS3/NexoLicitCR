# Validación de SICOP como fuente (NLC-01)

Consultas reales del 17 de octubre de 2026. Reproducible con:

```bash
uv run python scripts/sicop_probe.py --output artifacts/sicop-probe.json
```

El script no usa MongoDB ni guarda contenido: solo identificadores públicos, conteos,
clasificaciones y la procedencia de cada consulta (`started_at`, `server_date`, endpoints).
El reporte queda en `artifacts/`, que Git ignora.

| Consulta | Fecha (UTC) | Muestra |
|---|---|---|
| Listado por rubro, horas de publicación | 2026-10-17 16:06 | 600 concursos (2 páginas por rubro) |
| Detalle, cierres y versiones | 2026-10-17 16:07 | 30 detalles al azar |
| Cadena de secuencias | 2026-10-17 16:08 | 3 concursos modificados, secuencias 00–02 |
| Anexos | 2026-10-17 16:10 | 15 PDF de 14 concursos |
| `sicop_probe.py` completo | 2026-10-17 16:13 | 150 concursos, 12 detalles, 10 anexos |

## Zona horaria: hora local de Costa Rica

Las fechas de la API (`regDt`, `biddocEndDt`, `openbidDt`) no traen offset y están en
**hora local de Costa Rica (UTC−6, sin horario de verano)**. `SICOP_TIMEZONE=America/Costa_Rica`.

- El 98,7 % de 600 publicaciones ocurre entre las 06:00 y las 18:59, con picos a las 14:00
  y 15:00: horario de oficina local. Si fueran UTC, las instituciones publicarían entre la
  medianoche y el mediodía local.
- Los cierres caen entre las 07:00 y las 14:00, o a las **23:59** (fin del día local), con
  minutos :00, :30 o :59.
- `cartelVersion` es una marca `ddMMyyyyHHmmss` con la misma hora local que `regDt`.
- La comparación con la cabecera `Date` (UTC) del servidor no fue concluyente: la consulta
  fue un sábado y no había publicaciones recientes.

## Identificadores y secuencias

- `cartelNo` (11 dígitos) e `instCartelNo` (`2026LD-000123-0001234567`) son únicos y van
  1 a 1 en 600 concursos. La clave `cartelNo:cartelSeq` sigue siendo válida.
- Los listados solo devuelven `cartelSeq = "00"`, que es siempre la **versión vigente**:
  la `cartelVersion` más reciente y el cierre actualizado.
- Una modificación del pliego **no cambia la secuencia** `00`: marca `cartelModYn = "Y"` y
  actualiza `cartelVersion`. Las secuencias `01`, `02`… son **versiones anteriores
  archivadas**, enlazadas por `preCartelSeq` y con estados históricos ("En apertura").

  | Concurso | Secuencia | `preCartelSeq` | Versión | Cierre |
  |---|---|---|---|---|
  | 20260903525 | 00 | — | 08/10/2026 14:47 | 20/10/2026 10:00 |
  | 20260903525 | 01 | 00 | 28/09/2026 12:34 | 13/10/2026 10:00 |
  | 20260903525 | 02 | 01 | 28/09/2026 16:30 | 06/10/2026 10:00 |

- Una secuencia inexistente responde **HTTP 401** (no 404).
- Consecuencia: la ingesta, que parte del listado, siempre guarda la versión vigente. No
  hace falta fusionar secuencias; las archivadas no se consultan.

## Importes y unidades

- `cartelBudget` llega como entero o con decimales; `SicopClient` lo interpreta con
  `Decimal` exacto.
- Unidades observadas en las líneas: `NA`, `c/u`, `kg`. `NA` se conserva como desconocida.

## Anexos: digitales, escaneados y procedencia

- Ruta: `epCartelFile/getCartelFilesById` → `comnFile/downloadWithPAR`, que devuelve una
  URL firmada (*pre-authenticated request*) de Oracle Cloud.
- Las 37 URLs observadas usan el mismo host `objectstorage.us-ashburn-1.oraclecloud.com`.
  En las 22 en que se revisó la ruta, todas usan el namespace `idfvqxo5pzbv` y el bucket
  **`bkt-ash-sicop-edocs-pr`**, y el objeto coincide con el `serverFileNm` informado por
  SICOP. Se agregó ese host exacto a `DOCUMENT_HOSTS` en
  `.env.example`; sin él no se descarga ningún anexo.
- Los archivos llegan como `application/octet-stream`; el descargador identifica el tipo
  por firma (`%PDF-`).
- Clasificación con el mismo umbral que `extractor.py` (menos de 40 caracteres por página):

  | Muestra | Digital | Mixto | Escaneado |
  |---|---|---|---|
  | 15 PDF (16:10) | 14 | 0 | 1 |
  | 10 PDF (`sicop_probe.py`) | 7 | 3 | 0 |

- También hay anexos `.zip` y `.doc`; el descargador los rechaza como no compatibles.

## Error corregido

`documents.metadata_get` enviaba `User-Agent: Mozilla/5.0`. El firewall de SICOP responde
a ese valor con una página de bloqueo (HTTP 200, `text/plain`), así que **toda descarga de
anexos fallaba** con `DOCUMENT_METADATA_UNAVAILABLE` contra la fuente real. Ahora
`SicopClient` y `documents.py` comparten `sicop.HEADERS`, y
`test_every_sicop_request_looks_like_a_browser` lo protege.

## Pendiente

- Fuente final de adjudicación por línea (RF-16): sigue pendiente.
- OCR real de anexos escaneados y mixtos (NLC-06): `extractor.py` importa `resource`, que
  no existe en Windows.
