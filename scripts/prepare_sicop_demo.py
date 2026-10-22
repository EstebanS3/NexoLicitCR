"""Isolated live SICOP demo. Creates no synthetic tender data or preloaded user.

start --mongod PATH; serve; stop. Runtime secrets stay in ignored var/demo-sicop.
The web server owns a worker with the same explicit private settings.
"""

import argparse
import base64
import json
import os
import secrets
import socket
import subprocess
import time
from pathlib import Path

from dotenv import dotenv_values
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure

from nexolicitcr.config import Settings
from nexolicitcr.storage import Store, connect

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "var/demo-sicop"
DATABASE = "nexolicit_demo_sicop"
PORT = 27020
OWNER = "nexolicitcr-live-sicop-demo-v1"
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
            raise ValueError(
                "var/demo-sicop contiene archivos sin marcador de propiedad; preservados."
            )
        private_write(marker, json.dumps({"owner": OWNER, "database": DATABASE, "port": PORT}))
    if json.loads(marker.read_text()) != {"owner": OWNER, "database": DATABASE, "port": PORT}:
        raise ValueError("El directorio no pertenece a esta demo; no se modifica.")
    credentials = {
        "admin.json": {"username": "nexo_demo_bootstrap", "password": secrets.token_urlsafe(40)},
        "access.json": {
            "username": "demo.mesanorte",
            "password": secrets.token_urlsafe(24),
            "url": "http://localhost:8011",
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
                    "PUBLIC_ORIGIN=http://localhost:8011",
                    "SICOP_TIMEZONE=America/Costa_Rica",
                    "INSTALLATION_ID=nexolicit-demo-sicop",
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
        or settings.public_origin != "http://localhost:8011"
        or settings.installation_id != "nexolicit-demo-sicop"
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
        raise ValueError("El proceso MongoDB no pertenece a var/demo-sicop; operación rechazada.")


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
                        "La réplica demo no eligió primary; revisá var/demo-sicop/mongod.log."
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
    with connect(settings) as client:
        Store(client[DATABASE]).ensure_indexes()
    print("Base aislada lista, sin cuenta ni concursos precargados.")


def serve():
    import uvicorn
    from fastapi.responses import Response

    from nexolicitcr.web import create_app

    app = create_app(load_settings(), with_worker=False)

    @app.middleware("http")
    async def scenario_label(request, call_next):
        response = await call_next(request)
        if response.headers.get("content-type", "").startswith("text/html"):
            content = b"".join([chunk async for chunk in response.body_iterator])
            banner = (
                '<div class="notice" role="note" style="margin:0;padding:8px 20px;text-align:center">'
                "<strong>DEMO · Mesa Norte Catering (empresa ficticia)</strong>"
                " · Concursos reales consultados en SICOP · Notas privadas de ejemplo</div>"
            ).encode()
            content = content.replace(b"<main", banner + b"<main", 1)
            headers = dict(response.headers)
            headers.pop("content-length", None)
            return Response(
                content,
                status_code=response.status_code,
                headers=headers,
                background=response.background,
            )
        return response

    import sys

    worker = subprocess.Popen(  # noqa: S603 -- fixed local script, no shell
        [sys.executable, str(Path(__file__).resolve()), "worker"], stdin=subprocess.DEVNULL
    )
    try:
        uvicorn.run(app, host="127.0.0.1", port=8011, access_log=False, proxy_headers=False)
    finally:
        worker.terminate()
        try:
            worker.wait(timeout=10)
        except subprocess.TimeoutExpired:
            worker.kill()
            worker.wait()


def worker_loop():
    from uuid import uuid4

    from nexolicitcr.jobs import JobQueue, execute

    settings = load_settings()
    with connect(settings) as client:
        queue = JobQueue(Store(client[DATABASE]), settings)
        owner = uuid4().hex
        while True:
            queue.maintain()
            job = queue.claim(owner)
            if job:
                execute(queue, job)
            time.sleep(settings.worker_poll_seconds)


def stop():
    load_settings()
    with admin_client() as client:
        verify_server(client)
        try:
            client.admin.command("shutdown", force=False)
        except ConnectionFailure:
            pass
    print("MongoDB de la demo SICOP detenido.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["start", "serve", "worker", "stop"])
    parser.add_argument("--mongod")
    args = parser.parse_args()
    if args.action == "start":
        if not args.mongod:
            parser.error("start requiere --mongod RUTA")
        start(args.mongod)
    elif args.action == "serve":
        serve()
    elif args.action == "worker":
        try:
            worker_loop()
        except KeyboardInterrupt:
            pass
    else:
        stop()
