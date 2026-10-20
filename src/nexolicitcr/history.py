"""Presented offers are not awards. Unknown final prices remain unavailable."""

import hashlib
import re
from decimal import Decimal, InvalidOperation

import httpx
from bs4 import BeautifulSoup

from .models import Offer
from .sicop import HEADERS, SourceError
from .storage import utcnow

OPENING = "https://www.sicop.go.cr/moduloOferta/servlet/search/EP_SEV_COQ622"
MAX_BYTES = 4 * 1024 * 1024


def presented_price(raw):
    value = raw.replace("\xa0", " ").strip()
    currencies = re.findall(r"\b(?:CRC|USD|EUR)\b", value.upper())
    currency = currencies[0] if len(currencies) == 1 else None
    if not currency:
        return None, None
    number = re.sub(r"\[?\b(?:CRC|USD|EUR)\b\]?", "", value, flags=re.I).strip()
    # SICOP uses dots for grouping and a comma for decimals. Keep ambiguous
    # or malformed amounts unknown instead of silently changing their magnitude.
    if not re.fullmatch(r"(?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d+)?", number):
        return currency, None
    try:
        amount = Decimal(number.replace(".", "").replace(",", "."))
        return currency, str(amount) if amount.is_finite() else None
    except InvalidOperation:
        return currency, None


def parse_offers(html, lot):
    soup = BeautifulSoup(html, "html.parser")
    if any("La apertura no ha finalizado" in script.get_text() for script in soup.select("script")):
        raise SourceError("HISTORY_OPENING_PENDING")
    # Bind each value to its primary table heading. The real legacy source has
    # seven columns, two header rows and two rows per offer (several rowspans).
    # Attachment links are optional and must not determine the offer count.
    tables = []
    for table in soup.select("table"):
        for row in table.find_all("tr"):
            if row.find_parent("table") is not table:
                continue
            headings = [
                cell.get_text(" ", strip=True).rstrip("\u25bc\u25b2").strip()
                for cell in row.find_all("th", recursive=False)
            ]
            if "Precio presentado" in headings:
                tables.append((table, headings))
                break
    if len(tables) != 1:
        raise SourceError("HISTORY_SCHEMA_OR_BLOCKED")
    table, headings = tables[0]
    required = (
        "Posición de ofertas",
        "Calificación dada por el proveedor",
        "Precio presentado",
        "Estado de la oferta",
    )
    if len(headings) != 7 or any(headings.count(label) != 1 for label in required):
        raise SourceError("HISTORY_SCHEMA_OR_BLOCKED")
    result = []
    for row in table.find_all("tr"):
        if row.find_parent("table") is not table:
            continue
        cells = row.find_all("td", recursive=False)
        if not cells:
            continue
        values = [cell.get_text(" ", strip=True) for cell in cells]
        if len(cells) != len(headings):
            # Secondary rows contain supplier, submission and attachments.
            # A numeric first cell identifies a malformed primary row.
            if values[0].isdigit():
                raise SourceError("HISTORY_ROW_INVALID")
            continue
        fields = dict(zip(headings, values, strict=True))
        if not fields["Posición de ofertas"].isdigit():
            raise SourceError("HISTORY_ROW_INVALID")
        currency, value = presented_price(fields["Precio presentado"])
        result.append(
            Offer(
                position=len(result) + 1,
                lot=lot,
                price_presented=value,
                price_raw=fields["Precio presentado"],
                currency=currency,
                supplier_rating=fields["Calificación dada por el proveedor"],
                status=fields["Estado de la oferta"],
            ).model_dump()
        )
    text = table.get_text(" ", strip=True).casefold()
    empty = any(x in text for x in ("no se encontraron ofertas", "no hay ofertas", "sin ofertas"))
    if (not result and not empty) or (result and empty):
        raise SourceError("HISTORY_ROWS_UNVERIFIED")
    return result


def fetch_offers(source_id, sequence, lot, client=None):
    """Bounded read, shared by the importer and the database-free source probe."""
    if not all(re.fullmatch(r"[0-9]{1,30}", str(v)) for v in (source_id, sequence)):
        raise ValueError("Identificador SICOP inválido")
    if not isinstance(lot, str) or not re.fullmatch(r"[0-9]{1,5}", lot):
        raise ValueError("Partida inválida")
    if client is None:
        with httpx.Client(timeout=30, follow_redirects=False, trust_env=False) as owned:
            return fetch_offers(source_id, sequence, lot, owned)
    params = {
        "cartelNo": source_id,
        "cartelSeq": sequence,
        "cartelCate": lot,
        "cartelProgressCd": "30",
        "application": "new",
    }
    try:
        with client.stream("GET", OPENING, params=params, headers=HEADERS) as response:
            if response.status_code != 200:
                raise SourceError("HISTORY_HTTP_FAILED")
            content_type = response.headers.get("content-type", "").lower()
            if "text/html" not in content_type:
                raise SourceError("HISTORY_SCHEMA_OR_BLOCKED")
            raw = bytearray()
            for chunk in response.iter_bytes():
                raw.extend(chunk)
                if len(raw) > MAX_BYTES:
                    raise SourceError("HISTORY_TOO_LARGE")
            server_date = response.headers.get("date")
        offers = parse_offers(raw.decode("utf-8"), lot)
    except (httpx.HTTPError, UnicodeError):
        raise SourceError("HISTORY_UNAVAILABLE") from None
    return {
        "offers": offers,
        "source_hash": hashlib.sha256(raw).hexdigest(),
        "source_url": str(httpx.URL(OPENING, params=params)),
        "server_date": server_date,
        "fetched_at": utcnow(),
    }


def import_offers(store, tender_key, lot, client=None):
    tender = store.tender(tender_key)
    if not tender or not isinstance(lot, str) or not re.fullmatch(r"[0-9]{1,5}", lot):
        raise ValueError("Concurso o partida inválidos")
    payload = tender["payload"]
    identity = {"tender_key": tender_key, "lot": lot}
    try:
        observed = fetch_offers(payload["source_id"], payload["sequence"], lot, client)
    except SourceError as exc:
        store.db.offer_queries.update_one(
            identity,
            {"$set": {"status": "failed", "attempted_at": utcnow(), "error_code": str(exc)}},
            upsert=True,
        )
        raise
    for offer in observed["offers"]:
        store.db.offers.update_one(
            {
                **identity,
                "source_hash": observed["source_hash"],
                "position": offer["position"],
            },
            {
                "$set": {
                    **offer,
                    "source_url": observed["source_url"],
                    "fetched_at": observed["fetched_at"],
                }
            },
            upsert=True,
        )
    store.db.offer_queries.update_one(
        identity,
        {
            "$set": {
                "status": "succeeded",
                "attempted_at": observed["fetched_at"],
                "last_success_at": observed["fetched_at"],
                "count": len(observed["offers"]),
                "source_hash": observed["source_hash"],
                "source_url": observed["source_url"],
            },
            "$unset": {"error_code": ""},
        },
        upsert=True,
    )
    return len(observed["offers"])
