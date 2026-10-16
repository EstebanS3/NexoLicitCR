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
    assert result[0]["error"] == "OCR_FAILED_OR_UNAVAILABLE"
    assert result[0]["method"] == "ocr"


def test_offers_not_awards_and_source_errors():
    assert presented_price("CRC 251.020,80") == ("CRC", "251020.80")
    html = '<h1>Precio presentado · Calificación</h1><table><tr><td>1</td><td>1</td><td>Normal</td><td>Base</td><td>95</td><td>CRC 251.020,80</td><td>En estudio</td></tr><tr><td>Proveedor sintético</td><td><a href="javascript:js_viewFile(1)">Archivo</a></td></tr></table>'
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
