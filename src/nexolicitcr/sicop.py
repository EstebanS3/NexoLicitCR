import csv
import io
import json
import time
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

import httpx
from bs4 import BeautifulSoup
from pydantic import ValidationError

from .models import Award, SourceDate, Tender, TenderFile, TenderLine

BASE = "https://prod-api.sicop.go.cr"
# Reporte de datos abiertos del portal anterior; es la única fuente pública de adjudicaciones.
AWARDS_URL = "https://www.sicop.go.cr/moduloBid/servlet/report/RE_DatosAbiertosConcursos_CONTROLLER"
AWARDS_MAX_DAYS = 365
AWARD_COLUMNS = {
    "Descripcion": "title",
    "Numero procedimiento": "procedure",
    "Institucion": "institution",
    "Tipo Procedimiento": "procedure_type",
    "Tipo modalidad": "modality",
    "Clasificacion objeto": "object_class",
    "Partida": "lot",
    "Numero de línea": "number",
    "Adjudicatario": "supplier",
    "Moneda": "currency",
    "Monto": "amount",
    "Tipo de cambio adjudicación": "exchange_rate",
    "Monto adjudicado en colones": "amount_crc",
    "Estado de procedimiento": "status_raw",
}
RUBROS = {"bienes": "1", "obras": "3", "servicios": "5"}
RETRY = {429, 500, 502, 503, 504}
HEADERS = {
    "Origin": "https://www.sicop.go.cr",
    "Referer": "https://www.sicop.go.cr/",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0 Safari/537.36"
    ),
}


class SourceError(Exception):
    """Public, credential-free error suitable for a CLI or UI."""


def plain_text(value):
    if value is None:
        return ""
    if not isinstance(value, str):
        raise SourceError("Condiciones SICOP con formato inesperado")
    soup = BeautifulSoup(value, "html.parser")
    for element in soup(["script", "style"]):
        element.decompose()
    return " ".join(soup.get_text(" ").split())


def source_date(value, timezone):
    if value in (None, ""):
        return SourceDate()
    if not isinstance(value, str):
        raise SourceError("Fecha SICOP inválida")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise SourceError("Fecha SICOP inválida") from None
    assumed = None
    if parsed.tzinfo is None:
        if not timezone:
            return SourceDate(raw=value)
        parsed = parsed.replace(tzinfo=ZoneInfo(timezone))
        assumed = timezone
    return SourceDate(raw=value, utc=parsed.astimezone(UTC), assumed_timezone=assumed)


def amount(value):
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        raise SourceError("Importe SICOP inválido")
    try:
        parsed = Decimal(str(value))
    except InvalidOperation:
        raise SourceError("Importe SICOP inválido") from None
    if not parsed.is_finite() or parsed < 0:
        raise SourceError("Importe SICOP inválido")
    return parsed


def required(record, key):
    value = record.get(key)
    if value is None or str(value).strip() == "":
        raise SourceError(f"Campo SICOP obligatorio ausente: {key}")
    return str(value).strip()


def normalize_files(files):
    if not isinstance(files, list) or any(not isinstance(x, dict) for x in files):
        raise SourceError("Archivos SICOP con formato inesperado")
    normalized, numbers = [], set()
    for item in files:
        number = required(item, "docFileSeqno")
        if number in numbers:
            raise SourceError("Archivo SICOP repetido")
        numbers.add(number)
        normalized.append(
            TenderFile(
                number=number,
                name=required(item, "clientFileNm"),
                document=str(item.get("docNm") or ""),
                file_type=str(item.get("fileTypeNm") or ""),
                size_mb=amount(item.get("fileSizeMb")),
            )
        )
    return sorted(normalized, key=lambda x: (len(x.number), x.number))


def parse_awards(content: bytes):
    """Interpretar el CSV de datos abiertos: título en la 1.ª fila, encabezado en la 2.ª, ';'."""
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise SourceError("CSV de adjudicaciones con codificación inválida") from None
    rows = list(csv.reader(io.StringIO(text.replace("\xa0", " ")), delimiter=";"))
    if len(rows) < 2 or not rows[0] or "Datos abiertos" not in rows[0][0]:
        raise SourceError("SICOP no devolvió el reporte de adjudicaciones; posible bloqueo")
    header = [x.strip() for x in rows[1]]
    if header[-1:] == [""]:
        header = header[:-1]  # cada fila termina en ';'
    if header != list(AWARD_COLUMNS):
        raise SourceError("Columnas del reporte de adjudicaciones inesperadas")
    awards, duplicates, rejected = {}, 0, 0
    for row in rows[2:]:
        if not any(x.strip() for x in row):
            continue
        if len(row) < len(header) or row[len(header) :] not in ([], [""]):
            rejected += 1
            continue
        record = {AWARD_COLUMNS[h]: " ".join(v.split()) for h, v in zip(header, row, strict=False)}
        try:
            for field in ("amount", "exchange_rate", "amount_crc"):
                record[field] = amount(record[field])
            record["currency"] = record["currency"] or None
            award = Award(**record)
        except (SourceError, ValidationError):
            rejected += 1
            continue
        # Filas idénticas o variantes de la misma línea: se conserva la última del reporte.
        duplicates += award.key in awards
        awards[award.key] = award
    return list(awards.values()), {"duplicates": duplicates, "rejected": rejected}


def normalize(listing, detail, lines, category, timezone="", files=()):
    for key in ("cartelNo", "cartelSeq"):
        if required(listing, key) != required(detail, key):
            raise SourceError("El detalle no corresponde al concurso solicitado")
    status_raw = str(detail.get("cartelStatStr") or listing.get("cartelStatStr") or "")
    statuses = {
        "En recepción de ofertas": "open",
        "Publicado": "published",
        "Sin efecto": "canceled",
        "Nulidad absoluta": "canceled",
        "En evaluación": "closed",
        "Contrato": "closed",
        "Adjudicado": "closed",
        "Acto Final en Firme": "closed",
        "Desierto": "closed",
        "Infructuoso": "closed",
        "Finiquitado": "closed",
    }
    normalized_lines = []
    identities = set()
    for line in lines:
        identity = line.get("id")
        if not isinstance(identity, dict):
            raise SourceError("Línea SICOP sin identificador")
        if any(str(identity.get(k)) != str(detail[k]) for k in ("cartelNo", "cartelSeq")):
            raise SourceError("Línea SICOP de otro concurso")
        lot, number = required(identity, "cartelCate"), required(identity, "cateSeqno")
        if (lot, number) in identities:
            raise SourceError("Línea SICOP repetida")
        identities.add((lot, number))
        normalized_lines.append(
            TenderLine(
                lot=lot,
                number=number,
                product_code=line.get("prodId"),
                description=required(line, "prodNm"),
                quantity=amount(line.get("prodQty")),
                unit=None if line.get("prodUnit") in (None, "", "NA") else line["prodUnit"],
                currency=line.get("currencyType"),
                budget_unit_price=amount(line.get("prodPrc")),
                budget_total=amount(line.get("budgetAmt")),
            )
        )
    conditions = {
        k: plain_text(detail.get(k))
        for k in ("generalCondsCont", "specCondsCont", "adminCondsCont")
    }
    warnings = ["Los requisitos completos pueden estar en el pliego y sus anexos."]
    deadline = source_date(detail.get("biddocEndDt"), timezone)
    if deadline.raw and deadline.utc is None:
        warnings.append("Zona horaria de la fecha de cierre pendiente de confirmar.")
    if not deadline.raw:
        warnings.append("Fecha de cierre desconocida.")
    return Tender(
        source_id=required(detail, "cartelNo"),
        sequence=required(detail, "cartelSeq"),
        procedure=required(detail, "instCartelNo"),
        title=required(detail, "cartelNm"),
        institution=required(detail, "cartelInstNm"),
        category=category,
        status_raw=status_raw,
        status=statuses.get(status_raw, "unknown"),
        published=source_date(detail.get("regDt"), timezone),
        deadline=deadline,
        source_version=str(detail["cartelVersion"]) if detail.get("cartelVersion") else None,
        conditions=conditions,
        lines=sorted(normalized_lines, key=lambda x: (x.lot, x.number)),
        files=normalize_files(list(files)),
        warnings=warnings,
    )


class SicopClient:
    def __init__(self, client=None, delay=0.4, sleep=time.sleep):
        self.client = client or httpx.Client(timeout=30, follow_redirects=False, trust_env=False)
        self.sleep = sleep
        self.delay = delay

    def close(self):
        self.client.close()

    def _fetch(self, method, url, expected_type, max_bytes, **kwargs):
        """Bytes de una respuesta 200 del tipo esperado; HTML de bloqueo nunca pasa por vacío."""
        for attempt in range(3):
            self.sleep(self.delay)
            try:
                with self.client.stream(method, url, **kwargs) as response:
                    if response.status_code in RETRY:
                        if attempt == 2:
                            raise SourceError("SICOP temporalmente indisponible")
                        self.sleep(2**attempt)
                        continue
                    if response.status_code != 200:
                        raise SourceError(f"SICOP respondió HTTP {response.status_code}")
                    if expected_type not in response.headers.get("content-type", "").lower():
                        raise SourceError("SICOP devolvió un tipo inesperado; posible bloqueo")
                    data = bytearray()
                    for chunk in response.iter_bytes():
                        data.extend(chunk)
                        if len(data) > max_bytes:
                            raise SourceError("Respuesta SICOP excede el límite de tamaño")
                return bytes(data)
            except (httpx.TimeoutException, httpx.NetworkError):
                if attempt == 2:
                    raise SourceError("No fue posible conectar con SICOP") from None
                self.sleep(2**attempt)
        raise SourceError("No fue posible consultar SICOP")

    def _json(self, method, path, kind, **kwargs):
        headers = dict(HEADERS, Accept="application/json, text/plain, */*")
        data = self._fetch(
            method, BASE + path, "application/json", 8 * 1024 * 1024, headers=headers, **kwargs
        )
        try:
            result = json.loads(data, parse_float=Decimal)
        except (ValueError, UnicodeError):
            raise SourceError("Respuesta JSON SICOP inválida") from None
        if not isinstance(result, kind):
            raise SourceError("Esquema SICOP inesperado")
        return result

    def post(self, path, payload):
        return self._json("POST", path, dict, json=payload)

    def get_list(self, path, params):
        return self._json("GET", path, list, params=params)

    def pages(self, path, filters, max_pages=100, size=100):
        seen = set()
        for page in range(max_pages):
            data = self.post(
                path,
                {
                    "pageNumber": page,
                    "pageSize": size,
                    "tableSorter": {"sorter": "", "order": "desc"},
                    "tableFilters": [],
                    "formFilters": [{"field": k, "value": v} for k, v in filters.items()],
                },
            )
            content, last = data.get("content"), data.get("last")
            if not isinstance(content, list) or type(last) is not bool:
                raise SourceError("Paginación SICOP inválida")
            if any(not isinstance(x, dict) for x in content) or (not content and not last):
                raise SourceError("Contenido de página SICOP inválido")
            signature = json.dumps(content, sort_keys=True, default=str)
            if content and signature in seen:
                raise SourceError("SICOP repitió una página")
            seen.add(signature)
            yield from content
            if last:
                return
        raise SourceError("Límite de páginas alcanzado; consulta incompleta")

    def listings(self, category):
        if category not in RUBROS:
            raise SourceError("Rubro inválido")
        return self.pages(
            "/bid/api/v1/public/epCartel/searchEpCartelsByPpsType", {"ppsType": RUBROS[category]}
        )

    def tender(self, listing, category, timezone=""):
        ids = {k: required(listing, k) for k in ("cartelNo", "cartelSeq")}
        detail = self.post("/bid/api/v1/public/epCartel/findPublishedById", ids)
        lines = list(self.pages("/bid/api/v1/public/epCartelProd/findByEpCartelId", ids))
        files = self.get_list(
            "/bid/api/v1/public/epCartelFile/getCartelFilesById", dict(ids, docFileSeqno="")
        )
        return normalize(listing, detail, lines, category, timezone, files)

    def awards(self, start: date, end: date):
        """Adjudicaciones del reporte de datos abiertos; SICOP limita el rango a un año."""
        if start > end or (end - start).days > AWARDS_MAX_DAYS:
            raise SourceError("Rango de adjudicaciones inválido (máximo 365 días)")
        content = self._fetch(
            "POST",
            AWARDS_URL,
            "text/csv",
            128 * 1024 * 1024,
            data={
                "cmd": "downloadCSV",
                "bgnYmd": start.strftime("%d/%m/%Y"),
                "endYmd": end.strftime("%d/%m/%Y"),
                "item_sn": "",
                "seq_hist_sn": "",
            },
            headers=dict(HEADERS, Accept="text/csv, */*"),
        )
        return parse_awards(content)
