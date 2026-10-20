import hashlib
from contextlib import contextmanager

import pytest
from gridfs.errors import FileExists
from mongomock.gridfs import enable_gridfs_integration
from test_documents_history import digital_pdf

from nexolicitcr.documents import DocumentError, DocumentService
from nexolicitcr.extractor import VERSION


@pytest.fixture
def document_service(store, settings, tmp_path, monkeypatch):
    enable_gridfs_integration()
    path = tmp_path / "digital.pdf"
    digital_pdf(path)
    payload = path.read_bytes()
    metadata = {
        "sha256": hashlib.sha256(payload).hexdigest(),
        "size": len(payload),
        "media_type": "application/pdf",
    }

    def download(url, target, cfg):
        target.write_bytes(payload)
        return metadata

    @contextmanager
    def session():
        class Transaction:
            def with_transaction(self, callback):
                return callback(None)

        yield Transaction()

    monkeypatch.setattr("nexolicitcr.documents.download", download)
    monkeypatch.setattr(store.db.client, "start_session", session)
    return DocumentService(store, settings), payload, metadata


@pytest.mark.parametrize(
    "damage", ["chunks_only", "missing_file", "corrupt_file", "concurrent_upload"]
)
def test_retry_repairs_missing_or_incomplete_gridfs_without_deleting_other_uploads(
    document_service, monkeypatch, damage
):
    service, payload, metadata = document_service
    digest = metadata["sha256"]
    document_id = hashlib.sha256(("test:00" + "source" + digest).encode()).hexdigest()
    service.store.db.documents.insert_one(
        {
            "_id": document_id,
            "tender_key": "test:00",
            "source_identity": "source",
            **metadata,
            "state": "ready",
            "current": True,
            "gridfs_id": digest,
            "extractor_version": VERSION,
        }
    )
    if damage == "corrupt_file":
        service.fs.put(b"broken", _id=digest)
    if damage == "chunks_only":
        service.store.db.fs.chunks.insert_one({"files_id": digest, "n": 0, "data": payload})
    if damage == "concurrent_upload":
        original_put = service.fs.put
        calls = []

        def put(*args, **kwargs):
            calls.append(kwargs["_id"])
            if len(calls) == 1:
                service.store.db.fs.chunks.insert_one({"files_id": digest, "n": 0, "data": payload})
                raise FileExists("Another process is still uploading")
            return original_put(*args, **kwargs)

        monkeypatch.setattr(service.fs, "put", put)

    assert service.ingest("test:00", "source", "https://www.sicop.go.cr/fixture") == document_id
    document = service.store.db.documents.find_one({"_id": document_id})
    assert document["state"] == "ready"
    assert service.fs.get(document["gridfs_id"]).read() == payload
    if damage in {"chunks_only", "concurrent_upload"}:
        assert document["gridfs_id"] != digest
        assert service.store.db.fs.chunks.count_documents({"files_id": digest}) == 1
        assert not service.fs.exists(digest)
    if damage == "corrupt_file":
        assert service.fs.get(digest).read() == b"broken"
    # A second identical import reuses the healthy repair rather than adding another blob.
    count = service.store.db.fs.files.count_documents({})
    assert service.ingest("test:00", "source", "https://www.sicop.go.cr/fixture") == document_id
    assert service.store.db.fs.files.count_documents({}) == count


def test_blob_verification_failure_never_publishes_ready(document_service, monkeypatch):
    service, _, _ = document_service
    monkeypatch.setattr(service.fs, "put", lambda *args, **kwargs: None)
    with pytest.raises(DocumentError, match="DOCUMENT_STORAGE_INCOMPLETE"):
        service.ingest("test:00", "source", "https://www.sicop.go.cr/fixture")
    document = service.store.db.documents.find_one({"tender_key": "test:00"})
    assert document["state"] == "processing" and not document.get("gridfs_id")
    assert service.store.db.extracted_pages.count_documents({}) == 0


def test_orphan_report_identifies_uncommitted_chunks_without_removing_them(document_service):
    service, payload, metadata = document_service
    digest = metadata["sha256"]
    service.store.db.fs.chunks.insert_one({"files_id": digest, "n": 0, "data": payload})
    report = service.orphan_report()
    unfinished = next(row for row in report if row["id"] == digest)
    assert unfinished["kind"] == "chunks_without_file" and unfinished["chunks"] == 1
    assert unfinished["older_than_one_day"] is False
    assert service.store.db.fs.chunks.count_documents({"files_id": digest}) == 1


@pytest.mark.parametrize("damage", [None, "missing_chunk", "altered_content"])
def test_download_serves_only_verified_complete_original(client, store, damage):
    import gridfs
    from test_web import login

    enable_gridfs_integration()
    payload = b"%PDF-1.4\n" + bytes(range(256)) * 4
    digest = hashlib.sha256(payload).hexdigest()
    blob = f"{digest}-upload"
    stored = b"%PDF-1.4\n" + bytes(1024) if damage == "altered_content" else payload
    gridfs.GridFS(store.db).put(stored, _id=blob, chunkSize=256)
    if damage == "missing_chunk":
        # The manifest still exists, so a bare existence check would start a truncated 200.
        store.db.fs.chunks.delete_one({"files_id": blob, "n": 2})
    store.db.documents.insert_one(
        {
            "_id": "doc-1",
            "tender_key": "test:00",
            "source_identity": "source",
            "sha256": digest,
            "size": len(payload),
            "media_type": "application/pdf",
            "state": "ready",
            "current": True,
            "gridfs_id": blob,
            "pages": 0,
            "extractor_version": VERSION,
        }
    )
    login(client)
    view = client.get("/documents/doc-1")
    response = client.get("/documents/doc-1/download")
    if damage is None:
        assert "Descargar original" in view.text
        assert response.status_code == 200 and response.content == payload
        assert response.headers["content-type"] == "application/pdf"
        assert f'filename="anexo-{digest[:12]}.pdf"' in response.headers["content-disposition"]
        assert response.headers["x-content-type-options"] == "nosniff"
    else:
        assert "Descargar original" not in view.text and "no está completo" in view.text
        assert response.status_code == 409 and payload not in response.content
        # Diagnosis is read-only: nothing is deleted by viewing or downloading.
        assert store.db.fs.files.count_documents({"_id": blob}) == 1
