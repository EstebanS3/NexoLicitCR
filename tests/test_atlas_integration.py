"""Opt-in MongoDB integration; never deletes an entire database."""

import json
import os
from pathlib import Path
from uuid import uuid4

import pytest

from nexolicitcr.config import Settings
from nexolicitcr.sicop import normalize
from nexolicitcr.storage import Store, connect, utcnow


@pytest.mark.integration
def test_real_mongo_transaction_and_reimport():
    local = os.getenv("NEXO_TEST_LOCAL") == "1"
    atlas = os.getenv("NEXO_TEST_ATLAS") == "1"
    if not local and not atlas:
        pytest.skip("Opt in with NEXO_TEST_LOCAL=1 or NEXO_TEST_ATLAS=1")
    if local and atlas:
        pytest.fail("Select only one MongoDB integration environment")
    database_name = os.environ.get("NEXO_TEST_DATABASE", "")
    if not database_name.startswith("nexolicit_test_"):
        pytest.fail("NEXO_TEST_DATABASE must start with nexolicit_test_")
    cfg = Settings()
    if cfg.mongo_mode != ("local" if local else "atlas"):
        pytest.fail("Integration opt-in does not match MONGO_MODE")
    data = json.loads((Path(__file__).parent / "fixtures/tender.json").read_text())
    tender = normalize(data["listing"], data["detail"], data["lines"], "servicios")
    tender = tender.model_copy(update={"source_id": str(uuid4().int)[:25]})
    with connect(cfg) as client:
        store = Store(client[database_name])
        store.ensure_indexes()
        marker = uuid4().hex
        # A real aborted transaction must leave neither collection partially written.
        with client.start_session() as session:
            with pytest.raises(RuntimeError, match="abort-test"):
                with session.start_transaction():
                    store.db.tenders.insert_one({"_id": marker}, session=session)
                    store.db.tender_versions.insert_one(
                        {"key": marker, "hash": marker}, session=session
                    )
                    raise RuntimeError("abort-test")
        assert store.db.tenders.find_one({"_id": marker}) is None
        assert store.db.tender_versions.find_one({"key": marker}) is None
        try:
            assert store.save_tender(tender, utcnow()) == "changed"
            assert store.save_tender(tender, utcnow()) == "unchanged"
            assert store.db.tender_versions.count_documents({"key": tender.key}) == 1
            assert store.tender(tender.key)["payload"]["title"] == tender.title
        finally:
            store.db.tenders.delete_one({"_id": tender.key})
            store.db.tender_versions.delete_many({"key": tender.key})


@pytest.mark.integration
@pytest.mark.parametrize("term", ["redes informáticas", "insumos médicos", "pavimentación"])
def test_real_ocr_gridfs_transaction_and_match(tmp_path, monkeypatch, term):
    import hashlib
    import shutil

    from PIL import Image, ImageDraw, ImageFont

    from nexolicitcr.documents import DocumentService
    from nexolicitcr.extractor import VERSION, ocr_executable
    from nexolicitcr.matching import score

    if os.getenv("NEXO_TEST_LOCAL") != "1":
        pytest.skip("Opt in with NEXO_TEST_LOCAL=1")
    database_name = os.environ.get("NEXO_TEST_DATABASE", "")
    if not database_name.startswith("nexolicit_test_"):
        pytest.fail("NEXO_TEST_DATABASE must start with nexolicit_test_")
    if not shutil.which("tesseract"):
        pytest.skip("Native Spanish Tesseract required")
    ocr_executable()
    cfg = Settings()
    assert cfg.mongo_mode == "local"
    marker = uuid4().hex
    source = tmp_path / "scan.png"
    image = Image.new("RGB", (1600, 1200), "white")
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", size=45)
    except OSError:
        font = ImageFont.truetype("DejaVuSans.ttf", size=45)
    ImageDraw.Draw(image).multiline_text(
        (80, 100),
        f"REQUISITOS TECNICOS DEL CONCURSO\n\nSuministro y servicios de {term}\npara instituciones del sector publico.\n\nReferencia de prueba {marker}",
        font=font,
        fill="black",
        spacing=15,
    )
    image.save(source)
    payload = source.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()

    def fake_download(url, target, settings):
        target.write_bytes(payload)
        return {"sha256": digest, "size": len(payload), "media_type": "image/png"}

    monkeypatch.setattr("nexolicitcr.documents.download", fake_download)
    with connect(cfg) as client:
        store = Store(client[database_name])
        store.ensure_indexes()
        service = DocumentService(store, cfg)
        try:
            document_id = service.ingest(marker, marker, "https://www.sicop.go.cr/test-fixture")
            document = store.db.documents.find_one({"_id": document_id})
            assert document["state"] == "ready" and document["extractor_version"] == VERSION
            pages = list(store.db.extracted_pages.find({"document_id": document_id}))
            assert len(pages) == 1 and pages[0]["method"] == "ocr" and pages[0]["error"] is None
            result = score(
                {"title": "Consulta", "lines": []},
                {"items": [{"id": marker, "name": term, "active": True, "keywords": [term]}]},
                pages,
            )
            assert result["score"] > 0
            assert result["products"][0]["reasons"][0]["document_id"] == document_id
            assert service.fs.get(document["gridfs_id"]).read() == payload
            store.db.documents.update_one(
                {"_id": document_id}, {"$set": {"extractor_version": "old-version"}}
            )
            assert (
                service.ingest(marker, marker, "https://www.sicop.go.cr/test-fixture")
                == document_id
            )
            assert store.db.documents.find_one({"_id": document_id})["extractor_version"] == VERSION
        finally:
            docs = list(store.db.documents.find({"tender_key": marker}))
            store.db.extracted_pages.delete_many({"document_id": {"$in": [d["_id"] for d in docs]}})
            store.db.documents.delete_many({"tender_key": marker})
            if service.fs.exists(digest):
                service.fs.delete(digest)
