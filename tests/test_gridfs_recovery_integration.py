"""Real GridFS recovery against an explicitly isolated MongoDB database."""

import hashlib
import os
from uuid import uuid4

import pytest
from test_documents_history import digital_pdf

from nexolicitcr.config import Settings
from nexolicitcr.documents import DocumentService
from nexolicitcr.extractor import VERSION
from nexolicitcr.storage import Store, connect


@pytest.mark.integration
def test_real_gridfs_repairs_interrupted_upload_and_previously_published_missing_blob(
    tmp_path, monkeypatch
):
    local, atlas = os.getenv("NEXO_TEST_LOCAL") == "1", os.getenv("NEXO_TEST_ATLAS") == "1"
    if not local and not atlas:
        pytest.skip("Opt in with NEXO_TEST_LOCAL=1 or NEXO_TEST_ATLAS=1")
    database = os.environ.get("NEXO_TEST_DATABASE", "")
    if local == atlas or not database.startswith("nexolicit_test_"):
        pytest.fail("Choose one backend and an isolated nexolicit_test_ database")
    cfg = Settings()
    if cfg.mongo_mode != ("local" if local else "atlas"):
        pytest.fail("Integration opt-in does not match MONGO_MODE")
    marker = uuid4().hex
    source = tmp_path / "digital.pdf"
    digital_pdf(source)
    content = source.read_bytes()
    # Include a unique valid PDF comment so this probe cannot collide with another test blob.
    content += f"\n% {marker}\n".encode()
    digest = hashlib.sha256(content).hexdigest()

    def download(url, target, settings):
        target.write_bytes(content)
        return {"sha256": digest, "size": len(content), "media_type": "application/pdf"}

    monkeypatch.setattr("nexolicitcr.documents.download", download)
    with connect(cfg) as connection:
        store = Store(connection[database])
        store.ensure_indexes()
        service = DocumentService(store, cfg)
        document_id = hashlib.sha256((marker + marker + digest).encode()).hexdigest()
        owned_blobs = {digest}
        try:
            # State left by a process dying after writing chunks but before fs.files.
            store.db.fs.chunks.insert_one({"files_id": digest, "n": 0, "data": content})
            store.db.documents.insert_one(
                {
                    "_id": document_id,
                    "tender_key": marker,
                    "source_identity": marker,
                    "sha256": digest,
                    "size": len(content),
                    "media_type": "application/pdf",
                    "state": "ready",
                    "current": True,
                    "gridfs_id": digest,
                    "extractor_version": VERSION,
                }
            )
            assert (
                service.ingest(marker, marker, "https://www.sicop.go.cr/test-fixture")
                == document_id
            )
            repaired = store.db.documents.find_one({"_id": document_id})
            owned_blobs.add(repaired["gridfs_id"])
            assert repaired["state"] == "ready" and repaired["gridfs_id"] != digest
            assert service.fs.get(repaired["gridfs_id"]).read() == content
            assert not service.fs.exists(digest)
            assert store.db.fs.chunks.count_documents({"files_id": digest}) == 1
            assert any(
                row["id"] == digest and row["kind"] == "chunks_without_file"
                for row in service.orphan_report()
            )
            assert (
                service.ingest(marker, marker, "https://www.sicop.go.cr/test-fixture")
                == document_id
            )
            assert (
                store.db.documents.find_one({"_id": document_id})["gridfs_id"]
                == repaired["gridfs_id"]
            )
        finally:
            docs = list(store.db.documents.find({"tender_key": marker}))
            owned_blobs.update(d["gridfs_id"] for d in docs if d.get("gridfs_id"))
            store.db.extracted_pages.delete_many({"document_id": document_id})
            store.db.documents.delete_many({"tender_key": marker})
            for blob in owned_blobs:
                if service.fs.exists(blob):
                    service.fs.delete(blob)
                store.db.fs.chunks.delete_many({"files_id": blob})
