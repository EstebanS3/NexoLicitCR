"""Presented offers are not awards. Unknown final prices remain unavailable."""

import hashlib
import re
from decimal import Decimal, InvalidOperation

import httpx
from bs4 import BeautifulSoup

from .models import Offer
from .sicop import SourceError
from .storage import utcnow

OPENING = "https://www.sicop.go.cr/moduloOferta/servlet/search/EP_SEV_COQ622"


def presented_price(raw):
    value = raw.replace("\xa0", " ").strip()
    currency = next((c for c in ("CRC", "USD", "EUR") if c in value.upper()), None)
    number = re.sub(r"[^0-9,.]", "", value)
    if not currency or not number or "-" in value:
        return currency, None
    if "," in number:
        number = number.replace(".", "").replace(",", ".")
    elif number.count(".") > 1:
        return currency, None
    try:
        amount = Decimal(number)
        return currency, str(amount) if amount.is_finite() else None
    except InvalidOperation:
        return currency, None


def parse_offers(html, lot):
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)
    if "Precio presentado" not in text or "Calificación" not in text:
        raise SourceError("HISTORY_SCHEMA_OR_BLOCKED")
    result = []
    for anchor in soup.select('a[href*="js_viewFile"]'):
        row = anchor.find_parent("tr")
        previous = row.find_previous_sibling("tr") if row else None
        cells = previous.find_all("td", recursive=False) if previous else []
        if len(cells) < 7:
            raise SourceError("HISTORY_ROW_INVALID")
        values = [cell.get_text(" ", strip=True) for cell in cells]
        currency, value = presented_price(values[5])
        result.append(
            {
                "position": len(result) + 1,
                "lot": lot,
                "price_presented": value,
                "price_raw": values[5],
                "currency": currency,
                "supplier_rating": values[4],
                "status": values[-1],
                "price_kind": "presented",
                "unit_price": None,
                "awarded": None,
            }
        )
    if not result and not any(
        x in text.lower() for x in ("no se encontraron", "no hay ofertas", "sin ofertas")
    ):
        raise SourceError("HISTORY_ROWS_UNVERIFIED")
    return [Offer.model_validate(row).model_dump() for row in result]


def import_offers(store, tender_key, lot):
    tender = store.tender(tender_key)
    if not tender or not lot.isdigit() or len(lot) > 5:
        raise ValueError("Concurso o partida inválidos")
    payload = tender["payload"]
    params = {
        "cartelNo": payload["source_id"],
        "cartelSeq": payload["sequence"],
        "cartelCate": lot,
        "cartelProgressCd": "30",
        "application": "new",
    }
    try:
        with httpx.Client(timeout=30, follow_redirects=False, trust_env=False) as client:
            with client.stream(
                "GET",
                OPENING,
                params=params,
                headers={
                    "Referer": "https://www.sicop.go.cr/",
                    "User-Agent": "Mozilla/5.0",
                    "Accept-Language": "es-CR,es;q=0.9",
                },
            ) as response:
                if response.status_code != 200:
                    raise SourceError("HISTORY_HTTP_FAILED")
                raw = bytearray()
                for chunk in response.iter_bytes():
                    raw.extend(chunk)
                    if len(raw) > 4 * 1024 * 1024:
                        raise SourceError("HISTORY_TOO_LARGE")
        offers = parse_offers(raw.decode("utf-8"), lot)
    except (httpx.HTTPError, UnicodeError):
        raise SourceError("HISTORY_UNAVAILABLE") from None
    digest = hashlib.sha256(raw).hexdigest()
    for offer in offers:
        store.db.offers.update_one(
            {"tender_key": tender_key, "source_hash": digest, "position": offer["position"]},
            {
                "$setOnInsert": {
                    **offer,
                    "source_url": str(httpx.URL(OPENING, params=params)),
                    "fetched_at": utcnow(),
                }
            },
            upsert=True,
        )
    return len(offers)
