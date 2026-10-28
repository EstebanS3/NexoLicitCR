"""Prepare a self-contained fictional demo, without reading the checkout's .env.

start --mongod PATH: start the private authenticated replica and seed it.
seed: restore the five fictional cases, preserving credentials and the initial date.
serve: expose the demo at http://localhost:8010; no SICOP worker is started.
stop: stop only the demo MongoDB process. Ctrl+C stops the foreground web server.

Runtime files and generated credentials live in ignored var/demo, with mode 0600.
The fixed database/port and ownership checks deliberately cannot be overridden.
"""

import argparse
import base64
import hashlib
import io
import json
import os
import secrets
import socket
import subprocess
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import gridfs
from dotenv import dotenv_values
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from nexolicitcr.config import Settings
from nexolicitcr.extractor import VERSION as EXTRACTOR_VERSION
from nexolicitcr.models import CatalogItem, CompanyProfile, Tender
from nexolicitcr.security import PASSWORDS
from nexolicitcr.storage import Store, connect

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "var/demo"
FIXTURE = ROOT / "data/demo/scenario.json"
DATABASE = "nexolicit_demo_v090"
PORT = 27019
OWNER = "nexolicitcr-fictional-demo-v1"
URI = f"mongodb://127.0.0.1:{PORT}/?directConnection=true"
REPLICA_URI = f"mongodb://127.0.0.1:{PORT}/?replicaSet=nexo-local"


def private_write(path, text):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        stream.write(text)


def prepare_files():
    RUNTIME.mkdir(parents=True, exist_ok=True, mode=0o700)
    marker = RUNTIME / "owner.json"
    if not marker.exists():
        if any(RUNTIME.iterdir()):
            raise ValueError("var/demo contiene archivos sin marcador de propiedad; preservados.")
        private_write(marker, json.dumps({"owner": OWNER, "database": DATABASE, "port": PORT}))
    if json.loads(marker.read_text()) != {"owner": OWNER, "database": DATABASE, "port": PORT}:
        raise ValueError("El directorio no pertenece a esta demo; no se modifica.")
    credentials = {
        "admin.json": {"username": "nexo_demo_bootstrap", "password": secrets.token_urlsafe(40)},
        "access.json": {
            "username": "demo.brujula",
            "password": secrets.token_urlsafe(24),
            "url": "http://localhost:8010",
            "notice": "Cuenta local ficticia; no publicar este archivo ni la contraseña.",
        },
    }
    for name, value in credentials.items():
        if not (RUNTIME / name).exists():
            private_write(RUNTIME / name, json.dumps(value, ensure_ascii=False, indent=2))
    if not (RUNTIME / "demo.env").exists():
        private_write(
            RUNTIME / "demo.env",
            "\n".join(
                [
                    "MONGO_MODE=local",
                    f"MONGO_LOCAL_URI={REPLICA_URI}",
                    "MONGO_LOCAL_USUARIO=nexo_demo_app",
                    f"MONGO_LOCAL_CLAVE={secrets.token_urlsafe(40)}",
                    f"MONGO_LOCAL_BASE={DATABASE}",
                    "APP_MODE=local",
                    "PUBLIC_ORIGIN=http://localhost:8010",
                    "SICOP_TIMEZONE=America/Costa_Rica",
                    "INSTALLATION_ID=nexolicit-demo-v090",
                    "ENVIRONMENT=development",
                    "REDIS_URL=",
                    "REDIS_NAMESPACE=nexolicit-demo",
                    "",
                ]
            ),
        )
    return load_settings()


def validate_settings(settings):
    if (
        settings.mongo_mode != "local"
        or not settings.database_name.startswith("nexolicit_demo_")
        or settings.database_name != DATABASE
        or settings.mongo_local_uri.get_secret_value() != REPLICA_URI
        or settings.public_origin != "http://localhost:8010"
        or settings.installation_id != "nexolicit-demo-v090"
        or settings.redis_url.get_secret_value()
    ):
        raise ValueError(
            "La demo solo admite su base, puerto y origen aislados; operación rechazada."
        )


def load_settings():
    path = RUNTIME / "demo.env"
    if not path.exists():
        raise ValueError("Primero ejecutá start --mongod RUTA.")
    # Explicit kwargs override inherited environment; the ordinary .env is never loaded.
    values = {key.lower(): value for key, value in dotenv_values(path).items()}
    settings = Settings(_env_file=None, **values)
    validate_settings(settings)
    return settings


def admin_client():
    credentials = json.loads((RUNTIME / "admin.json").read_text())
    return MongoClient(
        URI,
        username=credentials["username"],
        password=credentials["password"],
        authSource="admin",
        serverSelectionTimeoutMS=2000,
    )


def verify_server(client):
    options = client.admin.command("getCmdLineOpts")["parsed"]
    if (
        Path(options["storage"]["dbPath"]).resolve() != (RUNTIME / "data").resolve()
        or options["net"]["port"] != PORT
        or options["net"]["bindIp"] != "127.0.0.1"
    ):
        raise ValueError("El proceso MongoDB no pertenece a var/demo; operación rechazada.")


def start(binary):
    settings = prepare_files()
    binary = Path(binary).resolve()
    if not binary.is_file():
        raise ValueError("No se encontró el binario mongod indicado.")
    with socket.socket() as probe:
        running = probe.connect_ex(("127.0.0.1", PORT)) == 0
    if running:
        with admin_client() as client:
            verify_server(client)
    else:
        key = RUNTIME / "replica.key"
        if not key.exists():
            private_write(key, base64.b64encode(secrets.token_bytes(512)).decode("ascii"))
        (RUNTIME / "data").mkdir(exist_ok=True, mode=0o700)
        subprocess.run(  # noqa: S603 -- explicit local executable, no shell
            [
                str(binary),
                "--dbpath",
                str(RUNTIME / "data"),
                "--bind_ip",
                "127.0.0.1",
                "--port",
                str(PORT),
                "--replSet",
                "nexo-local",
                "--keyFile",
                str(key),
                "--auth",
                "--fork",
                "--logpath",
                str(RUNTIME / "mongod.log"),
                "--pidfilepath",
                str(RUNTIME / "mongod.pid"),
            ],
            check=True,
        )
        credentials = json.loads((RUNTIME / "admin.json").read_text())
        with MongoClient(URI, serverSelectionTimeoutMS=5000) as bootstrap:
            try:
                bootstrap.admin.command(
                    "replSetInitiate",
                    {"_id": "nexo-local", "members": [{"_id": 0, "host": f"127.0.0.1:{PORT}"}]},
                )
            except OperationFailure as exc:
                if exc.code not in (13, 23):
                    raise
            deadline = time.monotonic() + 30
            while not bootstrap.admin.command("hello").get("isWritablePrimary"):
                if time.monotonic() >= deadline:
                    raise ValueError(
                        "La réplica demo no eligió primary; revisá var/demo/mongod.log."
                    )
                time.sleep(0.5)
            try:
                bootstrap.admin.command(
                    "createUser",
                    credentials["username"],
                    pwd=credentials["password"],
                    roles=[{"role": "root", "db": "admin"}],
                )
            except OperationFailure as exc:
                if exc.code != 13:
                    raise
    with admin_client() as client:
        verify_server(client)
        username = settings.mongo_local_usuario.get_secret_value()
        if not client.admin.command("usersInfo", username)["users"]:
            client.admin.command(
                "createUser",
                username,
                pwd=settings.mongo_local_clave.get_secret_value(),
                roles=[{"role": "readWrite", "db": DATABASE}],
            )
    run_seed(settings)


def make_pdf(lines):
    """Small deterministic single-page fixture, generated with existing dependencies."""
    writer = PdfWriter()
    page = writer.add_blank_page(width=595, height=842)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
            NameObject("/Encoding"): NameObject("/WinAnsiEncoding"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})}
    )
    content = ["BT /F1 12 Tf 50 780 Td 25 TL"]
    for index, line in enumerate(lines):
        if index:
            content.append("T*")
        escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        content.append(f"({escaped}) Tj")
    content.append("ET")
    stream = DecodedStreamObject()
    stream.set_data("\n".join(content).encode("cp1252"))
    page[NameObject("/Contents")] = writer._add_object(stream)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def seed_database(store, settings, access, fixture=None, anchor=None):
    validate_settings(settings)
    if store.db.name != DATABASE:
        raise ValueError("La conexión no apunta a la base demo; no se modifica.")
    marker = store.db.metadata.find_one({"_id": "demo_owner"})
    if marker is None and store.db.list_collection_names():
        raise ValueError("La base tiene contenido sin marcador demo; preservada.")
    if marker and marker.get("owner") != OWNER:
        raise ValueError("La base no pertenece a esta demo; preservada.")
    anchor = (marker or {}).get("anchor") or anchor or datetime.now(UTC).replace(microsecond=0)
    fixture = fixture or json.loads(FIXTURE.read_text())
    store.db.metadata.update_one(
        {"_id": "demo_owner"},
        {"$setOnInsert": {"owner": OWNER, "anchor": anchor, "provenance": fixture["provenance"]}},
        upsert=True,
    )
    store.ensure_indexes()
    if not store.db.users.find_one({"_id": "administrator"}):
        store.create_admin(access["username"], PASSWORDS.hash(access["password"]))
    catalog = [
        {
            **CatalogItem.model_validate({k: v for k, v in item.items() if k != "id"}).model_dump(),
            "id": item["id"],
        }
        for item in fixture["catalog"]
    ]
    store.db.catalog.replace_one(
        {"_id": "company"},
        {
            "_id": "company",
            "revision": 1,
            "items": catalog,
            "profile": CompanyProfile.model_validate(fixture["company"]).model_dump(),
            "updated_at": anchor,
        },
        upsert=True,
    )
    fs = gridfs.GridFS(store.db)
    for entry in fixture["tenders"]:
        deadline = anchor + timedelta(days=entry["deadline_days"])
        date_value = lambda value: {  # noqa: E731 -- local fixture date converter
            "raw": value.astimezone(ZoneInfo("America/Costa_Rica")).strftime("%d/%m/%Y %H:%M"),
            "utc": value,
            "assumed_timezone": "America/Costa_Rica",
        }
        tender = Tender(
            source_id=entry["source_id"],
            sequence="00",
            procedure=entry["procedure"],
            title=entry["title"],
            institution=entry["institution"],
            category=entry["category"],
            status_raw="Escenario ficticio · recepción de ofertas",
            status="open",
            published=date_value(anchor - timedelta(days=10)),
            deadline=date_value(deadline),
            source_version="demo-v1",
            conditions={
                "generalCondsCont": "Ejemplo ficticio. Presentar propuesta técnica y económica.",
                "specCondsCont": "Revisar las líneas y el anexo sintético de este escenario.",
                "adminCondsCont": "La afinidad es orientativa y no acredita elegibilidad.",
            },
            lines=[
                {
                    "lot": "1",
                    "number": "1",
                    "product_code": entry["code"],
                    "description": entry["description"],
                    "quantity": entry["quantity"],
                    "unit": entry["unit"],
                    "currency": "CRC",
                    "budget_unit_price": entry["unit_price"],
                    "budget_total": entry["total"],
                }
            ],
            warnings=[
                "DEMO FICTICIA: institución, expediente, monto y código inventados. Sin vínculo con SICOP."
            ],
        )
        store.save_tender(tender, anchor)
        # Never send synthetic expediente identifiers to the real source.
        store.db.tenders.update_one({"_id": tender.key}, {"$set": {"source_url": "#demo-ficticia"}})
        if entry.get("document"):
            data = make_pdf(entry["document"])
            digest = hashlib.sha256(data).hexdigest()
            document_id = f"demo-document-{entry['source_id']}"
            if not fs.exists(digest):
                fs.put(
                    data,
                    _id=digest,
                    filename=f"{entry['procedure']}-ficticio.pdf",
                    contentType="application/pdf",
                    metadata={"sha256": digest, "demo": True},
                )
            page_text = PdfReader(io.BytesIO(data)).pages[0].extract_text()
            store.db.documents.replace_one(
                {"_id": document_id},
                {
                    "_id": document_id,
                    "tender_key": tender.key,
                    "source_identity": document_id,
                    "sha256": digest,
                    "size": len(data),
                    "media_type": "application/pdf",
                    "state": "partial" if entry.get("partial") else "ready",
                    "current": True,
                    "gridfs_id": digest,
                    "pages": 1,
                    "fetched_at": anchor,
                    "processed_at": anchor,
                    "extractor_version": EXTRACTOR_VERSION,
                    "error_code": "DEMO_ANNEX_NOT_PROVIDED" if entry.get("partial") else None,
                },
                upsert=True,
            )
            store.db.extracted_pages.replace_one(
                {"document_id": document_id, "page": 1},
                {
                    "document_id": document_id,
                    "page": 1,
                    "text": page_text,
                    "method": "digital",
                    "error": None,
                    "extractor_version": EXTRACTOR_VERSION,
                },
                upsert=True,
            )
        store.db.decisions.update_one(
            {"company": "company", "tender_key": tender.key},
            {
                "$set": {
                    "status": entry.get("decision", "none"),
                    "note": entry.get("note", ""),
                    "updated_at": anchor,
                }
            },
            upsert=True,
        )
    job = {
        "_id": "DEMO-CARGA-LOCAL",
        "installation_id": settings.installation_id,
        "idempotency_key": "demo-fixture-v1",
        "payload_hash": "synthetic-fixture",
        "payload": {"category": "all", "limit": 5, "since": "", "documents": True},
        "status": "succeeded",
        "progress": len(fixture["tenders"]),
        "attempt": 1,
        "created_at": anchor,
        "updated_at": anchor,
        "next_attempt_at": anchor,
        "checkpoint": [f"{row['source_id']}:00" for row in fixture["tenders"]],
        "errors": [],
        "cancel_requested": False,
        "demo_provenance": "Carga local del fixture, NO consulta ni ejecución del worker de SICOP.",
    }
    store.db.jobs.replace_one({"_id": job["_id"]}, job, upsert=True)
    # Seed also restores the catalog: invalidate previously calculated demo matches.
    store.db.matches.delete_many({"company": "company"})
    store.db.metadata.update_one({"_id": "corpus"}, {"$set": {"generation": 1}})
    return {
        "database": DATABASE,
        "tenders": len(fixture["tenders"]),
        "documents": 3,
        "anchor": anchor.isoformat(),
        "username": access["username"],
    }


def run_seed(settings=None):
    settings = settings or load_settings()
    with admin_client() as admin:
        verify_server(admin)
    with connect(settings) as client:
        result = seed_database(
            Store(client[DATABASE]), settings, json.loads((RUNTIME / "access.json").read_text())
        )
    (RUNTIME / "manifest.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("Demo lista: 5 concursos, 3 PDF, Brújula TI. Credenciales privadas: var/demo/access.json")
    print("Servidor: python scripts/prepare_demo.py serve · URL: http://localhost:8010")


def demo_app(settings):
    from fastapi.responses import HTMLResponse, Response

    from nexolicitcr.web import create_app

    validate_settings(settings)
    app = create_app(settings, with_worker=False)

    @app.middleware("http")
    async def identify_fictional_scenario(request, call_next):
        if request.method == "POST" and (
            request.url.path in {"/sync-runs", "/discover/search"}
            or request.url.path.endswith("/resume")
            or request.url.path == "/onboarding/sync"
        ):
            return HTMLResponse(
                "<p>DEMO LOCAL: las consultas externas están desactivadas.</p>"
                "<p>La actividad DEMO-CARGA-LOCAL representa la carga del escenario ficticio.</p>"
                '<a href="/jobs">Volver a sincronizaciones</a>',
                status_code=409,
            )
        response = await call_next(request)
        if response.headers.get("content-type", "").startswith("text/html"):
            content = b"".join([chunk async for chunk in response.body_iterator])
            banner = (
                '<div id="demo-ficticia" class="notice" role="note">'
                "<strong>DEMO LOCAL · Brújula TI</strong> · Datos totalmente ficticios. "
                "Sin conexión a SICOP. La actividad mostrada es una carga local de ejemplo.</div>"
            ).encode()
            content = content.replace(b"<main", banner + b"<main", 1)
            # Login uses a separate layout; label it too, without depending on a main tag.
            if banner not in content:
                closing = content.find(b">", content.find(b"<body")) + 1
                content = content[:closing] + banner + content[closing:]
            headers = dict(response.headers)
            headers.pop("content-length", None)
            return Response(
                content,
                status_code=response.status_code,
                headers=headers,
                background=response.background,
            )
        return response

    return app


def stop():
    load_settings()
    with admin_client() as client:
        verify_server(client)
        try:
            client.admin.command("shutdown", force=False)
        except ConnectionFailure:
            pass
    print("MongoDB de la demo detenido; archivos privados conservados.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["start", "seed", "serve", "stop"])
    parser.add_argument("--mongod", help="Ruta al ejecutable mongod oficial; solo para start")
    args = parser.parse_args()
    if args.action == "start":
        if not args.mongod:
            parser.error("start requiere --mongod RUTA")
        start(args.mongod)
    elif args.action == "seed":
        run_seed()
    elif args.action == "serve":
        import uvicorn

        uvicorn.run(
            demo_app(load_settings()),
            host="127.0.0.1",
            port=8010,
            access_log=False,
            proxy_headers=False,
        )
    else:
        stop()


if __name__ == "__main__":
    main()
