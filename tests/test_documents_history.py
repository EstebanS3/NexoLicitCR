import httpx
import pytest
from PIL import Image
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from nexolicitcr.documents import DocumentError, download, validate_url
from nexolicitcr.extractor import extract
from nexolicitcr.history import parse_offers, presented_price
from nexolicitcr.sicop import SourceError


def test_download_rejects_private_hosts_redirects_and_html(settings, tmp_path, monkeypatch):
    import nexolicitcr.documents as documents

    with pytest.raises(DocumentError):
        validate_url("http://127.0.0.1/private", {"127.0.0.1"})
    with pytest.raises(DocumentError):
        validate_url(
            "https://www.sicop.go.cr/a",
            {"www.sicop.go.cr"},
            resolver=lambda *a, **k: [(0, 0, 0, "", ("127.0.0.1", 443))],
        )
    monkeypatch.setattr(documents, "validate_url", lambda url, hosts: None)
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, content=b"<html>blocked</html>")
        )
    ) as client:
        with pytest.raises(DocumentError, match="UNSUPPORTED"):
            download("https://www.sicop.go.cr/doc", tmp_path / "doc", settings, client)
    cfg = settings.model_copy(update={"document_max_bytes": 1024})
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, content=b"%PDF-" + b"x" * 2000)
        )
    ) as client:
        with pytest.raises(DocumentError, match="TOO_LARGE"):
            download("https://www.sicop.go.cr/doc", tmp_path / "doc", cfg, client)


def digital_pdf(path):
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})}
    )
    stream = DecodedStreamObject()
    stream.set_data(
        b"BT /F1 12 Tf 50 700 Td (Servicio de soporte de redes para prueba sintetica.) Tj ET"
    )
    page[NameObject("/Contents")] = writer._add_object(stream)
    writer.write(path)


def test_digital_pdf_and_limits(tmp_path):
    path = tmp_path / "digital.pdf"
    digital_pdf(path)
    pages = extract(path, 1)
    assert "soporte de redes" in pages[0]["text"]
    assert pages[0]["method"] == "digital" and pages[0]["error"] is None
    with pytest.raises(ValueError, match="LIMIT"):
        extract(path, 0)


def test_image_missing_ocr_is_explicit(tmp_path, monkeypatch):
    path = tmp_path / "scan.png"
    Image.new("RGB", (100, 100), "white").save(path)
    monkeypatch.setattr("nexolicitcr.extractor.shutil.which", lambda name: None)
    result = extract(path, 1)
    assert result[0]["error"] == "OCR_UNAVAILABLE"
    assert result[0]["method"] == "ocr"


def test_offers_not_awards_and_source_errors():
    assert presented_price("CRC 251.020,80") == ("CRC", "251020.80")
    from pathlib import Path

    html = (Path(__file__).parent / "fixtures/presented-offers.html").read_text(encoding="utf-8")
    offer = parse_offers(html, "1")[0]
    assert (
        offer["price_presented"] == "251020.80"
        and offer["awarded"] is None
        and offer["unit_price"] is None
    )
    with pytest.raises(SourceError):
        parse_offers("<html>Access denied</html>", "1")


def test_gridfs_publication_and_lease_fencing(store, settings, tmp_path, monkeypatch):
    import hashlib
    from contextlib import contextmanager

    from mongomock.gridfs import enable_gridfs_integration

    from nexolicitcr.documents import DocumentService
    from nexolicitcr.jobs import LeaseLost

    enable_gridfs_integration()
    source = tmp_path / "digital.pdf"
    digital_pdf(source)
    payload = source.read_bytes()

    def fake_download(url, target, cfg):
        target.write_bytes(payload)
        return {
            "sha256": hashlib.sha256(payload).hexdigest(),
            "size": len(payload),
            "media_type": "application/pdf",
        }

    @contextmanager
    def session():
        class Transaction:
            def with_transaction(self, callback):
                return callback(None)

        yield Transaction()

    monkeypatch.setattr("nexolicitcr.documents.download", fake_download)
    monkeypatch.setattr(store.db.client, "start_session", session)
    service = DocumentService(store, settings)
    document_id = service.ingest("test:1", "identity", "https://www.sicop.go.cr/fixture")
    document = store.db.documents.find_one({"_id": document_id})
    assert document["state"] == "ready"
    assert store.db.extracted_pages.find_one({"document_id": document_id})["method"] == "digital"
    assert service.fs.get(document["gridfs_id"]).read() == payload
    assert service.ingest("test:1", "identity", "https://www.sicop.go.cr/fixture") == document_id
    assert store.db.fs.files.count_documents({}) == 1

    def lost(session=None):
        raise LeaseLost()

    with pytest.raises(LeaseLost):
        service.ingest("test:2", "identity", "https://www.sicop.go.cr/fixture", lost)
    assert store.db.documents.count_documents({"tender_key": "test:2"}) == 0


def test_extractor_imports_and_runs_without_resource_module(monkeypatch):
    import importlib
    import sys

    monkeypatch.setitem(sys.modules, "resource", None)
    monkeypatch.delitem(sys.modules, "nexolicitcr.extractor", raising=False)
    extractor = importlib.import_module("nexolicitcr.extractor")
    extractor.apply_limits()


def test_extractor_applies_rlimits_when_resource_is_available(monkeypatch):
    import sys
    import types

    import nexolicitcr.extractor as extractor

    calls = []
    fake = types.SimpleNamespace(
        RLIMIT_CPU="cpu",
        RLIMIT_FSIZE="fsize",
        RLIMIT_AS="as",
        setrlimit=lambda kind, limits: calls.append((kind, limits)),
    )
    monkeypatch.setitem(sys.modules, "resource", fake)
    monkeypatch.setattr(extractor.sys, "platform", "linux")
    extractor.apply_limits()
    assert calls == [
        ("cpu", (110, 115)),
        ("fsize", (64 * 1024 * 1024, 64 * 1024 * 1024)),
        ("as", (1024 * 1024 * 1024, 1024 * 1024 * 1024)),
    ]


def test_reference_failure_recovers_without_stale_failure_or_removed_evidence(
    store, settings, tmp_path, monkeypatch
):
    import hashlib
    from contextlib import contextmanager
    from types import SimpleNamespace

    from mongomock.gridfs import enable_gridfs_integration

    from nexolicitcr.documents import DocumentService

    enable_gridfs_integration()
    source = tmp_path / "source.pdf"
    digital_pdf(source)
    payload = source.read_bytes()
    failing = [True]
    refs = [{"fileServerPath": "/files", "serverFileNm": "test.pdf"}]

    def metadata(path, params, text=False):
        return "https://www.sicop.go.cr/test" if text else refs

    def fetch(url, target, cfg):
        if failing[0]:
            raise DocumentError("DOCUMENT_HTTP_FAILED")
        target.write_bytes(payload)
        return {
            "sha256": hashlib.sha256(payload).hexdigest(),
            "size": len(payload),
            "media_type": "application/pdf",
        }

    @contextmanager
    def session():
        class Transaction:
            def with_transaction(self, callback):
                return callback(None)

        yield Transaction()

    monkeypatch.setattr(store.db.client, "start_session", session)
    monkeypatch.setattr("nexolicitcr.documents.time.sleep", lambda _: None)
    monkeypatch.setattr("nexolicitcr.documents.metadata_get", metadata)
    monkeypatch.setattr("nexolicitcr.documents.download", fetch)
    service = DocumentService(store, settings)
    tender = SimpleNamespace(key="test:recover", source_id="test", sequence="00")
    assert service.ingest_tender(tender) == ["failed"]
    assert (
        store.db.documents.find_one({"tender_key": tender.key})["error_code"]
        == "DOCUMENT_HTTP_FAILED"
    )
    failing[0] = False
    assert service.ingest_tender(tender) == ["ready"]
    assert store.db.documents.count_documents({"tender_key": tender.key}) == 1
    assert store.db.documents.find_one({"tender_key": tender.key})["current"] is True
    refs.clear()
    assert service.ingest_tender(tender) == []
    assert store.db.documents.find_one({"tender_key": tender.key})["current"] is False
