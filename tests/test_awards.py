import json
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import httpx
import mongomock
import pytest

from nexolicitcr.ingestion import sync_awards, windows
from nexolicitcr.sicop import SicopClient, SourceError, normalize, normalize_files, parse_awards
from nexolicitcr.storage import utcnow

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def report():
    return (FIXTURES / "awards.csv").read_bytes()


@pytest.fixture
def sample():
    return json.loads((FIXTURES / "tender.json").read_text())


@pytest.fixture(autouse=True)
def bulk_write_shim(monkeypatch):
    # Logic-only: mongomock no acepta UpdateOne de pymongo>=4.11; se aplica operación por
    # operación. No verifica el comportamiento de bulk_write en un MongoDB real.
    def bulk_write(self, operations, ordered=True):
        for op in operations:
            self.update_one(op._filter, op._doc, upsert=op._upsert)

    monkeypatch.setattr(mongomock.collection.Collection, "bulk_write", bulk_write)


def api(handler):
    return SicopClient(httpx.Client(transport=httpx.MockTransport(handler)), sleep=lambda _: None)


def test_report_parsing_dedupes_and_rejects(report):
    awards, quality = parse_awards(report)
    assert quality == {"duplicates": 1, "rejected": 1}
    assert [a.procedure for a in awards] == ["DEMO-001", "DEMO-002"]
    first, second = awards
    assert first.title == "Servicio de mantenimiento de redes"  # sin espacios duros
    assert first.exchange_rate == Decimal("448.21")  # se conserva la última variante
    assert second.amount == Decimal("1000.5") and second.currency == "USD"
    assert (second.lot, second.number) == ("2", "3")


@pytest.mark.parametrize(
    "content",
    [
        b"<html>Acceso bloqueado</html>",
        b'"Datos abiertos concursos";\n"Otra";"Cabecera";\n',
        b"",
        b"\xff\xfe",
    ],
)
def test_unexpected_report_is_not_empty(content):
    with pytest.raises(SourceError):
        parse_awards(content)


def test_report_download_and_type_checks(report):
    sent = []

    def handler(request):
        sent.append(request)
        return httpx.Response(200, content=report, headers={"content-type": "text/csv"})

    awards, _ = api(handler).awards(date(2026, 9, 1), date(2026, 9, 30))
    assert len(awards) == 2
    body = sent[0].content.decode()
    assert "cmd=downloadCSV" in body and "bgnYmd=01%2F09%2F2026" in body
    blocked = api(lambda r: httpx.Response(200, text="<html>bloqueo</html>"))
    with pytest.raises(SourceError, match="bloqueo"):
        blocked.awards(date(2026, 9, 1), date(2026, 9, 30))
    with pytest.raises(SourceError, match="365"):
        api(handler).awards(date(2025, 1, 1), date(2026, 1, 2))


def test_windows_cover_range_without_overlap():
    start, end = date(2024, 1, 1), date(2026, 3, 1)
    parts = list(windows(start, end))
    assert parts[0][0] == start and parts[-1][1] == end
    assert all((b - a).days <= 365 for a, b in parts)
    assert all(parts[i][1] + timedelta(days=1) == parts[i + 1][0] for i in range(len(parts) - 1))
    assert list(windows(start, start)) == [(start, start)]


def test_awards_persist_idempotently_and_show_on_tender(store, report):
    awards, _ = parse_awards(report)
    assert store.save_awards(awards, utcnow()) == {"changed": 2, "unchanged": 0}
    assert store.save_awards(awards, utcnow()) == {"changed": 0, "unchanged": 2}
    changed = awards[0].model_copy(update={"status_raw": "Finiquitado"})
    assert store.save_awards([changed], utcnow()) == {"changed": 1, "unchanged": 0}
    rows = store.awards_for("DEMO-001")
    assert len(rows) == 1 and rows[0]["payload"]["status_raw"] == "Finiquitado"
    assert rows[0]["payload"]["amount"] == "250.70"  # decimal exacto como texto


def test_sync_awards_records_run(store, report):
    calls = []

    class Client:
        def awards(self, start, end):
            calls.append((start, end))
            return parse_awards(report)

    result = sync_awards(store, Client(), date(2025, 1, 1), date(2026, 6, 1))
    assert len(calls) == 2
    assert result["status"] == "partial" and result["rejected"] == 2
    assert result["changed"] == 2 and result["unchanged"] == 2
    run = store.db.sync_runs.find_one({"_id": result["run_id"]})
    assert run["kind"] == "awards" and run["status"] == "partial"
    with pytest.raises(ValueError):
        sync_awards(store, Client(), date(2026, 2, 1), date(2026, 1, 1))


def test_sync_awards_failure_marks_run(store):
    class Client:
        def awards(self, start, end):
            raise SourceError("Sin servicio")

    with pytest.raises(SourceError):
        sync_awards(store, Client(), date(2026, 1, 1), date(2026, 1, 31))
    assert store.db.sync_runs.find_one({"kind": "awards"})["status"] == "failed"


def test_tender_files_normalized_and_fetched(sample):
    tender = normalize(
        sample["listing"], sample["detail"], sample["lines"], "servicios", files=sample["files"]
    )
    assert tender.files[0].name == "Pliego de ejemplo.pdf"
    assert tender.files[0].size_mb == Decimal("0.44")
    with pytest.raises(SourceError):
        normalize_files(sample["files"] * 2)
    with pytest.raises(SourceError):
        normalize_files({"not": "a list"})

    def handler(request):
        path = request.url.path
        if path.endswith("findPublishedById"):
            return httpx.Response(200, json=sample["detail"])
        if path.endswith("findByEpCartelId"):
            return httpx.Response(200, json={"content": sample["lines"], "last": True})
        if path.endswith("getCartelFilesById"):
            assert request.url.params["cartelNo"] == "12345678901"
            return httpx.Response(200, json=sample["files"])
        return httpx.Response(404)

    fetched = api(handler).tender(sample["listing"], "servicios")
    assert [f.number for f in fetched.files] == ["1"]


def test_tender_page_lists_files_and_awards(client, store, sample, report):
    from test_web import login

    tender = normalize(
        sample["listing"], sample["detail"], sample["lines"], "servicios", files=sample["files"]
    )
    store.db.tenders.insert_one(
        {
            "_id": tender.key,
            "payload": tender.model_dump(mode="json"),
            "source_url": tender.source_url,
            "observed_at": utcnow(),
        }
    )
    store.save_awards(parse_awards(report)[0], utcnow())
    login(client)
    page = client.get(f"/tenders/{tender.key}").text
    assert "Pliego de ejemplo.pdf" in page
    assert "Proveedor Uno S.A." in page and "Proveedor Dos S.A." not in page
