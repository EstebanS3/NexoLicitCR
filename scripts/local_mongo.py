"""Start/stop a private, authenticated single-node replica set for this checkout."""

import argparse
import base64
import json
import os
import secrets
import subprocess
import time
from pathlib import Path

from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "var/mongodb"
ADMIN = RUNTIME / "admin.json"
URI = "mongodb://127.0.0.1:27017/?directConnection=true"


def private_write(path, text):
    # Exclusive creation prevents overwriting existing credentials or configuration.
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        stream.write(text)


def admin_client(credentials):
    return MongoClient(
        URI,
        username=credentials["username"],
        password=credentials["password"],
        authSource="admin",
        serverSelectionTimeoutMS=2000,
    )


def start(binary):
    env = ROOT / ".env"
    if env.exists() and not ADMIN.exists():
        raise SystemExit("Ya existe .env; preservado. Configurá MongoDB manualmente según README.")
    RUNTIME.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not ADMIN.exists():
        private_write(
            ADMIN,
            json.dumps({"username": "nexo_bootstrap", "password": secrets.token_urlsafe(40)}),
        )
    credentials = json.loads(ADMIN.read_text())
    if not env.exists():
        password = secrets.token_urlsafe(40)
        private_write(
            env,
            (ROOT / ".env.local.example")
            .read_text()
            .replace("MONGO_LOCAL_CLAVE=", f"MONGO_LOCAL_CLAVE={password}"),
        )
    from nexolicitcr.config import Settings

    cfg = Settings(_env_file=env)
    if cfg.mongo_mode != "local" or cfg.mongo_local_base != "nexolicit_local":
        raise SystemExit("Este helper solo administra MONGO_MODE=local y nexolicit_local.")
    with admin_client(credentials) as client:
        try:
            client.admin.command("ping")
            print("MongoDB local ya está activo.")
            return
        except ConnectionFailure:
            pass
    key = RUNTIME / "replica.key"
    if not key.exists():
        private_write(key, base64.b64encode(secrets.token_bytes(512)).decode("ascii"))
    data = RUNTIME / "data"
    data.mkdir(exist_ok=True, mode=0o700)
    # Explicit executable path, no shell; never bind a network interface.
    subprocess.run(  # noqa: S603
        [
            str(Path(binary).resolve()),
            "--dbpath",
            str(data),
            "--bind_ip",
            "127.0.0.1",
            "--port",
            "27017",
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
    # MongoDB's localhost exception permits initial replica-set and first-user setup.
    with MongoClient(URI, serverSelectionTimeoutMS=5000) as bootstrap:
        try:
            bootstrap.admin.command(
                "replSetInitiate",
                {"_id": "nexo-local", "members": [{"_id": 0, "host": "127.0.0.1:27017"}]},
            )
        except OperationFailure as exc:
            if exc.code not in (13, 23):  # Already authenticated/initialized on restart.
                raise
        deadline = time.monotonic() + 30
        while not bootstrap.admin.command("hello").get("isWritablePrimary"):
            if time.monotonic() >= deadline:
                raise SystemExit("El replica set no eligió primary; revisá var/mongodb/mongod.log.")
            time.sleep(0.5)
        try:
            bootstrap.admin.command(
                "createUser",
                credentials["username"],
                pwd=credentials["password"],
                roles=[{"role": "root", "db": "admin"}],
            )
        except OperationFailure as exc:
            if exc.code != 13:  # Existing root disables localhost exception.
                raise
    with admin_client(credentials) as client:
        username = cfg.mongo_local_usuario.get_secret_value()
        if not client.admin.command("usersInfo", username)["users"]:
            client.admin.command(
                "createUser",
                username,
                pwd=cfg.mongo_local_clave.get_secret_value(),
                roles=[
                    {"role": "readWrite", "db": "nexolicit_local"},
                    {"role": "readWrite", "db": "nexolicit_test_local"},
                ],
            )
    from nexolicitcr.storage import Store, connect

    with connect(cfg) as client:
        store = Store(client[cfg.database_name])
        store.ping()
        store.ensure_indexes()
    print("MongoDB local listo; .env privado creado, base nexolicit_local e índices preparados.")


def stop():
    with admin_client(json.loads(ADMIN.read_text())) as client:
        try:
            client.admin.command("shutdown", force=False)
        except ConnectionFailure:
            pass  # The server closes the connection during successful shutdown.
    print("MongoDB local detenido.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["start", "stop"])
    parser.add_argument("--mongod", help="Ruta al binario mongod oficial")
    args = parser.parse_args()
    if args.action == "start":
        if not args.mongod:
            parser.error("start requiere --mongod")
        start(args.mongod)
    else:
        stop()
