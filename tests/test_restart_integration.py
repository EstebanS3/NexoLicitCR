"""Sesión y catálogo sobreviven a un reinicio real de la API (NLC-03). Opt-in; no borra bases."""

import os
import secrets
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest
from bs4 import BeautifulSoup

from nexolicitcr.config import Settings
from nexolicitcr.storage import Store, connect

ROOT = Path(__file__).resolve().parents[1]


def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def form_csrf(response):
    return BeautifulSoup(response.text, "html.parser").select_one('input[name="csrf"]')["value"]


@pytest.fixture
def real():
    local = os.getenv("NEXO_TEST_LOCAL") == "1"
    atlas = os.getenv("NEXO_TEST_ATLAS") == "1"
    if not local and not atlas:
        pytest.skip("Opt in with NEXO_TEST_LOCAL=1 or NEXO_TEST_ATLAS=1")
    if local and atlas:
        pytest.fail("Select only one MongoDB integration environment")
    database_name = os.environ.get("NEXO_TEST_DATABASE", "")
    if not database_name.startswith("nexolicit_test_"):
        pytest.fail("NEXO_TEST_DATABASE must start with nexolicit_test_")
    if Settings().mongo_mode != ("local" if local else "atlas"):
        pytest.fail("Integration opt-in does not match MONGO_MODE")
    port = free_port()
    env = dict(
        os.environ,
        ATLAS_BASE=database_name,
        MONGO_LOCAL_BASE=database_name,
        APP_MODE="local",
        PUBLIC_ORIGIN=f"http://localhost:{port}",
        PYTHONUTF8="1",
    )
    cfg = Settings(
        _env_file=ROOT / ".env", atlas_base=database_name, mongo_local_base=database_name
    )
    with connect(cfg) as client:
        store = Store(client[database_name])
        store.ensure_indexes()
        if not store.registration_open():
            # La contraseña del administrador existente es desconocida para la prueba.
            pytest.fail("La base de prueba ya tiene un administrador; usá una base vacía")
        original_items = store.catalog()["items"]
        try:
            yield port, env, store
        finally:
            admin = store.db.users.find_one({"_id": "administrator"})
            if admin:
                store.db.sessions.delete_many({"user_id": admin["_id"]})
                store.db.users.delete_one({"_id": "administrator"})
            store.db.catalog.update_one({"_id": "company"}, {"$set": {"items": original_items}})


class Server:
    """`nexolicit api` en un proceso propio, como lo ejecutaría un usuario."""

    def __init__(self, port, env):
        self.port, self.env, self.process = port, env, None

    def start(self):
        self.process = subprocess.Popen(  # noqa: S603 - intérprete y módulo propios
            [
                sys.executable,
                "-m",
                "nexolicitcr.cli",
                "api",
                "--port",
                str(self.port),
                "--no-worker",
            ],
            cwd=ROOT,
            env=self.env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                pytest.fail(f"La API no arrancó: {self.process.stderr.read().decode()[-2000:]}")
            try:
                if httpx.get(f"http://localhost:{self.port}/health/live").status_code == 200:
                    return
            except httpx.TransportError:
                pass
            time.sleep(0.3)
        pytest.fail("La API no respondió a tiempo")

    def kill(self):
        if self.process and self.process.poll() is None:
            self.process.kill()  # Sin apagado ordenado: nada puede quedar solo en memoria.
            self.process.wait(timeout=30)


@pytest.mark.integration
def test_session_and_catalog_survive_a_real_restart(real):
    port, env, store = real
    origin = {"origin": f"http://localhost:{port}", "accept": "text/html"}
    username, password = "restart-test", secrets.token_urlsafe(24)
    item_name = f"Servicio de prueba {secrets.token_hex(4)}"
    server = Server(port, env)
    try:
        server.start()
        with httpx.Client(base_url=f"http://localhost:{port}", headers=origin) as browser:
            token = form_csrf(browser.get("/register"))
            registered = browser.post(
                "/register",
                data={
                    "username": username,
                    "password": password,
                    "password_confirm": password,
                    "csrf": token,
                },
            )
            assert registered.status_code == 303
            token = form_csrf(browser.get("/login"))
            logged = browser.post(
                "/login", data={"username": username, "password": password, "csrf": token}
            )
            assert logged.status_code == 303 and browser.cookies.get("nexo_session")
            catalog = browser.get("/catalog")
            soup = BeautifulSoup(catalog.text, "html.parser")
            saved = browser.post(
                "/catalog",
                data={
                    "csrf": form_csrf(catalog),
                    "revision": soup.select_one('input[name="revision"]')["value"],
                    "name": item_name,
                    "keywords": "mantenimiento, redes",
                    "active": "true",
                },
            )
            assert saved.status_code == 303

            server.kill()
            server.start()

            after = browser.get("/catalog")
            assert after.status_code == 200, "La sesión no sobrevivió al reinicio"
            assert item_name in after.text, "El catálogo no sobrevivió al reinicio"
            stored = next(x for x in store.catalog()["items"] if x["name"] == item_name)
            assert stored["keywords"] == ["mantenimiento", "redes"] and stored["active"]

            revoked_token = browser.cookies["nexo_session"]
            assert browser.post("/logout", data={"csrf": form_csrf(after)}).status_code == 303
            server.kill()
            server.start()
        # Se reenvía el token a mano: el rechazo debe venir del servidor, no del navegador.
        with httpx.Client(
            base_url=f"http://localhost:{port}",
            headers=origin,
            cookies={"nexo_session": revoked_token},
        ) as replay:
            revoked = replay.get("/catalog")
            assert revoked.status_code == 303 and revoked.headers["location"] == "/login"
            assert item_name in {x["name"] for x in store.catalog()["items"]}
    finally:
        server.kill()
