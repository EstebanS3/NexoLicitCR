"""Source-shaped synthetic regression cases: no live requests and no real suppliers."""

from pathlib import Path

import httpx
import pytest
from test_cache_matching import tender_payload
from test_discovery import authenticated

from nexolicitcr.history import (
    MAX_BYTES,
    fetch_offers,
    import_offers,
    parse_offers,
    presented_price,
)
from nexolicitcr.sicop import HEADERS, SourceError

HTML = (Path(__file__).parent / "fixtures/presented-offers.html").read_text(encoding="utf-8")


def response(html=HTML):
    return httpx.Response(200, text=html, headers={"Content-Type": "text/html; charset=UTF-8"})


def empty_html():
    return (
        HTML[: HTML.index('<tr><td rowspan="2">')]
        + '<tr><td colspan="7">No hay ofertas</td></tr></table>'
    )


def test_real_column_order_separates_price_rating_and_conversion_without_requiring_files():
    offers = parse_offers(HTML, "1")
    assert len(offers) == 2  # Two files in offer 1, none in offer 2.
    assert offers[0]["price_raw"] == "251.020,80 [CRC]"
    assert offers[0]["price_presented"] == "251020.80"
    assert offers[0]["supplier_rating"] == "100"
    assert offers[0]["currency"] == "CRC"
    assert offers[1]["price_presented"] is None and offers[1]["currency"] is None
    assert all(o["awarded"] is None and o["unit_price"] is None for o in offers)


def test_columns_are_mapped_by_heading_and_unknown_schema_is_rejected():
    from bs4 import BeautifulSoup

    # A changed/missing heading is rejected even if the surrounding text mentions it.
    with pytest.raises(SourceError, match="SCHEMA"):
        parse_offers(HTML.replace("Calificación dada por el proveedor", "Otra columna"), "1")
    # Reorder price and rating in the primary header and data rows.
    soup = BeautifulSoup(HTML, "html.parser")
    for row in soup.select("tr"):
        cells = row.find_all(["th", "td"], recursive=False)
        if len(cells) == 7:
            fourth, fifth = cells[3], cells[4]
            fourth.insert_before(fifth.extract())
    assert parse_offers(str(soup), "1")[0]["price_presented"] == "251020.80"


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("CRC 251.020,80", ("CRC", "251020.80")),
        ("27.921.807,43 [CRC]", ("CRC", "27921807.43")),
        ("USD 61.549,228", ("USD", "61549.228")),
        ("CRC 0,00", ("CRC", "0.00")),
        ("CRC 12.34,56", ("CRC", None)),
        ("USD 1,234.56", ("USD", None)),
        ("CRC -10,00", ("CRC", None)),
        ("USD NaN", ("USD", None)),
        ("CRC 10 USD", (None, None)),
        ("Desconocido", (None, None)),
    ],
)
def test_presented_prices_preserve_exact_decimals_and_unknowns(raw, expected):
    assert presented_price(raw) == expected


def test_only_explicit_empty_result_in_verified_table_means_no_offers():
    assert parse_offers(empty_html(), "1") == []
    with pytest.raises(SourceError, match="ROWS_UNVERIFIED"):
        parse_offers(HTML[: HTML.index('<tr><td rowspan="2">')] + "</table>", "1")
    with pytest.raises(SourceError, match="SCHEMA"):
        parse_offers("<h1>Precio presentado Calificación</h1><p>No hay ofertas</p>", "1")
    with pytest.raises(SourceError, match="ROW_INVALID"):
        parse_offers(HTML.replace("<td>OFERTA-SINTETICA-1</td>", ""), "1")
    with pytest.raises(SourceError, match="ROWS_UNVERIFIED"):
        parse_offers(
            HTML.replace("</table>", '<tr><td colspan="7">Sin ofertas</td></tr></table>'), "1"
        )


@pytest.mark.parametrize(
    "reply,code",
    [
        (httpx.Response(403), "HTTP_FAILED"),
        (httpx.Response(429), "HTTP_FAILED"),
        (httpx.Response(503), "HTTP_FAILED"),
        (httpx.Response(302, headers={"Location": "/login"}), "HTTP_FAILED"),
        (httpx.Response(200, text="blocked", headers={"Content-Type": "text/plain"}), "SCHEMA"),
        (response("<html>Access denied</html>"), "SCHEMA"),
        (
            response("<script>alert('La apertura no ha finalizado.');history.back();</script>"),
            "OPENING_PENDING",
        ),
        (
            httpx.Response(200, content=bytes([255]), headers={"Content-Type": "text/html"}),
            "UNAVAILABLE",
        ),
        (response("x" * (MAX_BYTES + 1)), "TOO_LARGE"),
    ],
)
def test_http_and_schema_failures_never_become_empty_offers(reply, code):
    with httpx.Client(transport=httpx.MockTransport(lambda request: reply)) as client:
        with pytest.raises(SourceError, match=code):
            fetch_offers("20261000696", "00", "1", client)


def test_timeout_is_sanitized_and_request_uses_shared_browser_headers():
    def handler(request):
        assert request.headers["user-agent"] == HEADERS["User-Agent"]
        assert request.url.params["cartelCate"] == "2"
        raise httpx.ReadTimeout("private diagnostics")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(SourceError, match="^HISTORY_UNAVAILABLE$"):
            fetch_offers("20261000696", "00", "2", client)


def test_import_retries_preserve_prior_offers_and_repair_legacy_column_values(store, client):
    authenticated(client, store)
    payload = tender_payload()
    store.db.tenders.insert_one({"_id": "sample:00", "payload": payload, "hash": "v1"})
    replies = [response(), response(), response("<html>blocked</html>"), response(empty_html())]
    with httpx.Client(transport=httpx.MockTransport(lambda request: replies.pop(0))) as source:
        assert import_offers(store, "sample:00", "1", source) == 2
        store.db.offers.update_one(
            {"position": 1}, {"$set": {"supplier_rating": "legacy bad value"}}
        )
        assert import_offers(store, "sample:00", "1", source) == 2
        assert store.db.offers.count_documents({}) == 2
        assert store.db.offers.find_one({"position": 1})["supplier_rating"] == "100"
        query = store.db.offer_queries.find_one()
        assert query["status"] == "succeeded" and query["count"] == 2
        with pytest.raises(SourceError):
            import_offers(store, "sample:00", "1", source)
        page = client.get("/tenders/sample:00").text
        assert "Un fallo no confirma ausencia de ofertas" in page
        assert "Observaciones guardadas" in page
        assert store.db.offer_queries.find_one()["last_success_at"] == query["last_success_at"]
        assert import_offers(store, "sample:00", "1", source) == 0
    page = client.get("/tenders/sample:00").text
    assert "Sin ofertas en la última consulta validada" in page
    assert "Observaciones guardadas" in page and "Comparables adjudicados no disponibles" in page
    assert store.db.offers.count_documents({}) == 2
    assert "error_code" not in store.db.offer_queries.find_one()


def test_invalid_lot_is_rejected_before_any_network_or_write(store):
    store.db.tenders.insert_one({"_id": "sample:00", "payload": tender_payload()})
    for lot in ("", "1&other=2", "１２", "123456", "-1", None):
        with pytest.raises(ValueError):
            import_offers(store, "sample:00", lot)
    assert store.db.offer_queries.count_documents({}) == 0


def test_lots_have_separate_query_results(store):
    store.db.tenders.insert_one({"_id": "sample:00", "payload": tender_payload()})
    with httpx.Client(transport=httpx.MockTransport(lambda request: response())) as source:
        import_offers(store, "sample:00", "1", source)
        import_offers(store, "sample:00", "2", source)
    assert store.db.offer_queries.count_documents({}) == 2
    assert store.db.offers.count_documents({}) == 4


def test_offer_indexes_migrate_without_losing_data(store):
    from pymongo.errors import DuplicateKeyError

    store.db.offers.drop_indexes()
    legacy = store.db.offers.create_index(
        [("tender_key", 1), ("source_hash", 1), ("position", 1)], unique=True
    )
    record = {"tender_key": "sample:00", "lot": "1", "source_hash": "same", "position": 1}
    store.db.offers.insert_one(dict(record))
    store.ensure_indexes()
    store.ensure_indexes()
    assert legacy not in store.db.offers.index_information()
    assert store.db.offers.count_documents({}) == 1
    store.db.offers.insert_one({**record, "lot": "2"})
    with pytest.raises(DuplicateKeyError):
        store.db.offers.insert_one(dict(record))
