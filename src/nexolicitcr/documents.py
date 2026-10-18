"""Bounded downloads and immutable evidence in GridFS, with explicit partial states."""

import hashlib
import ipaddress
import json
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
from datetime import timedelta
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import gridfs
import httpx
from gridfs.errors import FileExists

from .extractor import VERSION as EXTRACTOR_VERSION
from .models import Document, ExtractionPage
from .sicop import BASE, HEADERS, SourceError, SourceRateLimited, retry_after_seconds
from .storage import utcnow


class DocumentError(SourceError):
    pass


def validate_url(url, allowed_hosts, resolver=socket.getaddrinfo):
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in allowed_hosts
        or parsed.username
        or parsed.password
        or parsed.fragment
        or parsed.port not in (None, 443)
    ):
        raise DocumentError("DOCUMENT_URL_REJECTED")
    try:
        addresses = resolver(parsed.hostname, 443, type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(x[4][0]).is_global for x in addresses):
            raise DocumentError("DOCUMENT_ADDRESS_REJECTED")
    except OSError:
        raise DocumentError("DOCUMENT_DNS_FAILED") from None


def download(url, target, settings, client=None):
    owned = client is None
    client = client or httpx.Client(
        timeout=httpx.Timeout(20, connect=5), follow_redirects=False, trust_env=False
    )
    allowed = {x.strip() for x in settings.document_hosts.split(",")}
    try:
        for _ in range(4):
            validate_url(url, allowed)
            with client.stream("GET", url) as response:
                if response.status_code in {301, 302, 303, 307, 308}:
                    location = response.headers.get("location")
                    if not location:
                        raise DocumentError("DOCUMENT_REDIRECT_INVALID")
                    url = urljoin(url, location)
                    continue
                if response.status_code != 200:
                    raise DocumentError("DOCUMENT_HTTP_FAILED")
                digest, size = hashlib.sha256(), 0
                with target.open("wb") as stream:
                    for chunk in response.iter_bytes(chunk_size=65536):
                        size += len(chunk)
                        if size > settings.document_max_bytes:
                            raise DocumentError("DOCUMENT_TOO_LARGE")
                        digest.update(chunk)
                        stream.write(chunk)
                signature = target.read_bytes()[:8]
                if signature.startswith(b"%PDF-"):
                    kind = "application/pdf"
                elif signature == b"\x89PNG\r\n\x1a\n":
                    kind = "image/png"
                elif signature.startswith(b"\xff\xd8\xff"):
                    kind = "image/jpeg"
                else:
                    raise DocumentError("DOCUMENT_UNSUPPORTED_OR_HTML")
                return {"sha256": digest.hexdigest(), "size": size, "media_type": kind}
        raise DocumentError("DOCUMENT_TOO_MANY_REDIRECTS")
    except httpx.HTTPError:
        raise DocumentError("DOCUMENT_NETWORK_FAILED") from None
    finally:
        if owned:
            client.close()


def metadata_get(path, params, text=False):
    try:
        return _metadata_get(path, params, text)
    except httpx.HTTPError:
        raise DocumentError("DOCUMENT_METADATA_NETWORK_FAILED") from None


def _metadata_get(path, params, text=False):
    with httpx.Client(timeout=20, follow_redirects=False, trust_env=False) as client:
        with client.stream(
            "GET",
            BASE + path,
            params=params,
            headers=HEADERS,
        ) as response:
            if response.status_code == 429:
                raise SourceRateLimited(retry_after_seconds(response.headers.get("retry-after")))
            if response.status_code != 200 or (
                not text and "json" not in response.headers.get("content-type", "")
            ):
                raise DocumentError("DOCUMENT_METADATA_UNAVAILABLE")
            data = bytearray()
            for chunk in response.iter_bytes():
                data.extend(chunk)
                if len(data) > 8 * 1024 * 1024:
                    raise DocumentError("DOCUMENT_METADATA_TOO_LARGE")
    try:
        if text:
            return data.decode().strip()
        return json.loads(data)
    except (ValueError, UnicodeError):
        raise DocumentError("DOCUMENT_METADATA_INVALID") from None


class DocumentService:
    def __init__(self, store, settings):
        self.store, self.settings = store, settings
        self.fs = gridfs.GridFS(store.db)
        self._last_metadata_request = None

    def _metadata(self, path, params, text=False):
        if self._last_metadata_request is not None:
            time.sleep(
                max(
                    0,
                    self.settings.sicop_request_delay_seconds
                    - (time.monotonic() - self._last_metadata_request),
                )
            )
        self._last_metadata_request = time.monotonic()
        return metadata_get(path, params, text)

    def ingest_tender(self, tender, guard=lambda session=None: None):
        refs = self._metadata(
            "/bid/api/v1/public/epCartelFile/getCartelFilesById",
            {"cartelNo": tender.source_id, "cartelSeq": tender.sequence},
        )
        if not isinstance(refs, list) or any(not isinstance(r, dict) for r in refs):
            raise DocumentError("DOCUMENT_REFERENCES_INVALID")
        states = []
        for position, ref in enumerate(refs):
            source_path, name = ref.get("fileServerPath"), ref.get("serverFileNm")
            if not isinstance(source_path, str) or not isinstance(name, str):
                raise DocumentError("DOCUMENT_REFERENCE_INVALID")
            identity = hashlib.sha256((source_path + "/" + name).encode()).hexdigest()
            marker = hashlib.sha256((tender.key + identity).encode()).hexdigest()
            guard()
            if position >= self.settings.document_max_files:
                self.store.db.documents.update_one(
                    {"_id": marker},
                    {
                        "$set": {
                            "tender_key": tender.key,
                            "source_identity": identity,
                            "sha256": "",
                            "state": "omitted",
                            "current": True,
                            "error_code": "FILE_COUNT_LIMIT",
                            "fetched_at": utcnow(),
                        }
                    },
                    upsert=True,
                )
                self.store.db.metadata.update_one({"_id": "corpus"}, {"$inc": {"generation": 1}})
                states.append("omitted")
                continue
            try:
                location = self._metadata(
                    "/comn/api/v1/public/comnFile/downloadWithPAR",
                    {"fileUrl": (source_path.rstrip("/") + "/" + name).lstrip("/")},
                    text=True,
                )
                if not isinstance(location, str):
                    raise DocumentError("DOCUMENT_DOWNLOAD_URL_INVALID")
                document_id = self.ingest(tender.key, identity, location, guard)
                guard()
                if self.store.db.documents.delete_one({"_id": marker}).deleted_count:
                    self.store.db.metadata.update_one(
                        {"_id": "corpus"}, {"$inc": {"generation": 1}}
                    )
                states.append(self.store.db.documents.find_one({"_id": document_id})["state"])
            except (DocumentError, httpx.HTTPError) as exc:
                guard()
                self.store.db.documents.update_one(
                    {"_id": marker},
                    {
                        "$set": {
                            "tender_key": tender.key,
                            "source_identity": identity,
                            "sha256": "",
                            "state": "failed",
                            "current": True,
                            "error_code": str(exc)
                            if isinstance(exc, DocumentError)
                            else "DOCUMENT_NETWORK_FAILED",
                            "fetched_at": utcnow(),
                        }
                    },
                    upsert=True,
                )
                self.store.db.metadata.update_one({"_id": "corpus"}, {"$inc": {"generation": 1}})
                states.append("failed")
        # References that disappeared must no longer contribute evidence.
        identities = [
            hashlib.sha256((r["fileServerPath"] + "/" + r["serverFileNm"]).encode()).hexdigest()
            for r in refs
        ]

        def retire_removed(session):
            guard(session)
            changed = self.store.db.documents.update_many(
                {
                    "tender_key": tender.key,
                    "current": {"$ne": False},
                    "source_identity": {"$nin": identities},
                },
                {"$set": {"current": False}},
                session=session,
            )
            if changed.modified_count:
                self.store.db.metadata.update_one(
                    {"_id": "corpus"}, {"$inc": {"generation": 1}}, upsert=True, session=session
                )

        with self.store.db.client.start_session() as session:
            session.with_transaction(retire_removed)
        return states

    def ingest(self, tender_key, identity, url, guard=lambda session=None: None):
        Path("var").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="nexo-", dir="var") as directory:
            path = Path(directory) / "source.bin"
            metadata = download(url, path, self.settings)
            Document(tender_key=tender_key, source_identity=identity, **metadata)
            document_id = hashlib.sha256(
                (tender_key + identity + metadata["sha256"]).encode()
            ).hexdigest()
            if self.store.db.documents.find_one(
                {
                    "_id": document_id,
                    "state": "ready",
                    "current": True,
                    "extractor_version": EXTRACTOR_VERSION,
                }
            ):
                return document_id
            guard()
            self.store.db.documents.update_one(
                {"_id": document_id},
                {
                    "$setOnInsert": {
                        "tender_key": tender_key,
                        "source_identity": identity,
                        **metadata,
                        "state": "processing",
                        "fetched_at": utcnow(),
                    }
                },
                upsert=True,
            )
            blob = metadata["sha256"]
            try:
                with path.open("rb") as source:
                    self.fs.put(source, _id=blob, filename=blob, contentType=metadata["media_type"])
            except FileExists:
                pass
            output = Path(directory) / "pages.json"
            try:
                command = [
                    sys.executable,
                    "-m",
                    "nexolicitcr.extractor",
                    str(path),
                    str(output),
                    "--pages",
                    str(self.settings.document_max_pages),
                ]
                with subprocess.Popen(  # noqa: S603 -- fixed Python module, bounded local paths
                    command,
                    start_new_session=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                ) as process:
                    try:
                        code = process.wait(timeout=self.settings.extraction_timeout_seconds)
                    except subprocess.TimeoutExpired:
                        if sys.platform == "win32":
                            process.kill()
                        elif hasattr(os, "killpg"):
                            os.killpg(process.pid, signal.SIGKILL)
                        else:
                            process.kill()
                        process.wait()
                        raise
                    if code:
                        raise ValueError("EXTRACTION_FAILED")
                if output.stat().st_size > 12 * 1024 * 1024:
                    raise ValueError("EXTRACTION_OUTPUT_LIMIT")
                pages = [
                    ExtractionPage.model_validate(page).model_dump()
                    for page in json.loads(output.read_text())
                ]
                state = "partial" if any(p["error"] for p in pages) else "ready"
                error = None
            except (subprocess.SubprocessError, ValueError, OSError):
                pages, state, error = [], "partial", "EXTRACTION_FAILED_OR_LIMIT"

            def publish(session):
                guard(session)
                self.store.db.documents.update_many(
                    {
                        "tender_key": tender_key,
                        "source_identity": identity,
                        "_id": {"$ne": document_id},
                    },
                    {"$set": {"current": False}},
                    session=session,
                )
                self.store.db.extracted_pages.delete_many(
                    {"document_id": document_id, "page": {"$nin": [p["page"] for p in pages]}},
                    session=session,
                )
                for page in pages:
                    self.store.db.extracted_pages.update_one(
                        {"document_id": document_id, "page": page["page"]},
                        {"$set": page},
                        upsert=True,
                        session=session,
                    )
                self.store.db.documents.update_one(
                    {"_id": document_id},
                    {
                        "$set": {
                            "state": state,
                            "current": True,
                            "gridfs_id": blob,
                            "error_code": error,
                            "pages": len(pages),
                            "processed_at": utcnow(),
                            "extractor_version": EXTRACTOR_VERSION,
                        }
                    },
                    session=session,
                )
                self.store.db.metadata.update_one(
                    {"_id": "corpus"}, {"$inc": {"generation": 1}}, upsert=True, session=session
                )

            with self.store.db.client.start_session() as session:
                session.with_transaction(publish)
            return document_id

    def orphan_report(self):
        # Read-only reconciliation: never delete a live/in-progress upload automatically.
        cutoff = utcnow() - timedelta(days=1)
        referenced = self.store.db.documents.distinct("gridfs_id")
        return [
            {"id": str(row["_id"]), "uploaded_at": row["uploadDate"].isoformat()}
            for row in self.store.db.fs.files.find(
                {"_id": {"$nin": referenced}, "uploadDate": {"$lt": cutoff}}
            )
        ]
