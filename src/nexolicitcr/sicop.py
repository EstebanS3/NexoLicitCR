import json
import time
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from email.utils import parsedate_to_datetime
from math import ceil
from zoneinfo import ZoneInfo

import httpx
from bs4 import BeautifulSoup

from .models import SourceDate, Tender, TenderLine

BASE = "https://prod-api.sicop.go.cr"
RUBROS = {"bienes": "1", "obras": "3", "servicios": "5"}
RETRY = {429, 500, 502, 503, 504}
# El firewall de SICOP responde una página de bloqueo (200, text/plain) a un User-Agent
# incompleto como "Mozilla/5.0"; todas las consultas deben parecer de navegador.
HEADERS = {
    "Origin": "https://www.sicop.go.cr",
    "Referer": "https://www.sicop.go.cr/",
    "Accept": "application/json, text/plain, */*",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0 Safari/537.36"
    ),
}


class SourceError(Exception):
    """Public, credential-free error suitable for a CLI or UI."""


class SourceRateLimited(SourceError):
    def __init__(self, retry_after=300):
        super().__init__("SICOP limitó la frecuencia de solicitudes")
        self.retry_after = min(86400, max(60, retry_after))


def retry_after_seconds(value):
    try:
        if value and value.strip().isdigit():
            return min(86400, max(60, int(value)))
        parsed = parsedate_to_datetime(value or "")
        if parsed.tzinfo is None:
            return 300
        return min(86400, max(60, ceil((parsed - datetime.now(UTC)).total_seconds())))
    except (TypeError, ValueError, OverflowError):
        return 300


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


def normalize(listing, detail, lines, category, timezone=""):
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
        warnings=warnings,
    )


class SicopClient:
    def __init__(self, client=None, delay=0.4, sleep=time.sleep):
        self.client = client or httpx.Client(timeout=30, follow_redirects=False, trust_env=False)
        self.sleep = sleep
        self.delay = delay

    def close(self):
        self.client.close()

    def post(self, path, payload):
        for attempt in range(3):
            self.sleep(self.delay)
            try:
                with self.client.stream(
                    "POST",
                    BASE + path,
                    json=payload,
                    headers={**HEADERS, "Content-Type": "application/json"},
                ) as response:
                    if response.status_code == 429:
                        raise SourceRateLimited(
                            retry_after_seconds(response.headers.get("Retry-After"))
                        )
                    if response.status_code in RETRY:
                        if attempt == 2:
                            raise SourceError("SICOP temporalmente indisponible")
                        self.sleep(2**attempt)
                        continue
                    if response.status_code != 200:
                        raise SourceError(f"SICOP respondió HTTP {response.status_code}")
                    if "application/json" not in response.headers.get("content-type", "").lower():
                        raise SourceError("SICOP no devolvió JSON; posible página de bloqueo")
                    data = bytearray()
                    for chunk in response.iter_bytes():
                        data.extend(chunk)
                        if len(data) > 8 * 1024 * 1024:
                            raise SourceError("Respuesta SICOP excede el límite de tamaño")
                result = json.loads(data, parse_float=Decimal)
                if not isinstance(result, dict):
                    raise SourceError("Esquema SICOP inesperado")
                return result
            except (httpx.TimeoutException, httpx.NetworkError):
                if attempt == 2:
                    raise SourceError("No fue posible conectar con SICOP") from None
                self.sleep(2**attempt)
            except (ValueError, UnicodeError):
                raise SourceError("Respuesta JSON SICOP inválida") from None
        raise SourceError("No fue posible consultar SICOP")

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
        return normalize(listing, detail, lines, category, timezone)
