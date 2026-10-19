"""Real HTTP + Atlas + SICOP smoke test, restricted to an isolated test database."""

import argparse
import json
import os
import secrets
import shutil
import subprocess
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

import httpx
from bs4 import BeautifulSoup
from dotenv import dotenv_values

from nexolicitcr.config import Settings
from nexolicitcr.storage import Store, connect

ROOT = Path(__file__).resolve().parents[1]


def require(condition, label):
    if not condition:
        raise RuntimeError(label)


def csrf(response):
    require(response.status_code == 200, "form_http_200")
    return BeautifulSoup(response.text, "html.parser").select_one('input[name="csrf"]')["value"]


def stop(process):
    if process is not None and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)


def run(args, report):
    values = {
        k: v for k, v in dotenv_values(args.env_file, interpolate=False).items() if v is not None
    }
    database = args.database or values.get("ATLAS_BASE", "")
    require(database.startswith("nexolicit_test_"), "exclusive_test_database_required")
    if not args.native:
        require(database == values.get("ATLAS_BASE"), "external_database_must_match_env_file")
        require(
            args.url.rstrip("/") == values.get("PUBLIC_ORIGIN", "").rstrip("/"),
            "external_url_must_match_env_file",
        )
    values.update(ATLAS_BASE=database, MONGO_MODE="atlas", PUBLIC_ORIGIN=args.url)
    if args.native:
        require(urlsplit(args.url).hostname == "localhost", "native_requires_localhost")
        values.update(APP_MODE="local", INSTALLATION_ID=f"smoke-{uuid4().hex[:12]}")
    cfg = Settings(_env_file=None, **{k.lower(): v for k, v in values.items()})
    require(cfg.public_origin == args.url.rstrip("/"), "origin_must_match_url")
    report.update(database=database, execution="native" if args.native else "external")
    processes = []
    api = None

    def compose(*command):
        docker = shutil.which("docker")
        require(bool(docker) and bool(args.compose_project), "docker_compose_project_required")
        subprocess.run(  # noqa: S603 -- explicit docker argv, no shell
            [docker, "compose", "-p", args.compose_project, *command],
            cwd=ROOT,
            env={
                **os.environ,
                "NEXO_ENV_FILE": str(args.env_file.resolve()),
                "NEXO_HTTP_PORT": str(urlsplit(args.url).port or 8000),
            },
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    with connect(cfg) as mongo:
        store = Store(mongo[database])
        store.ensure_indexes()
        require(store.registration_open(), "test_database_must_have_no_administrator")
        original_catalog = store.catalog()
        env = {**os.environ, **values, "PYTHONPATH": str(ROOT / "src")}

        def start_api():
            process = subprocess.Popen(  # noqa: S603 -- fixed own CLI, no shell
                [
                    sys.executable,
                    "-m",
                    "nexolicitcr.cli",
                    "api",
                    "--no-worker",
                    "--port",
                    str(urlsplit(args.url).port or 8000),
                ],
                cwd=ROOT,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            processes.append(process)
            return process

        try:
            if args.native:
                api = start_api()
                processes.append(
                    subprocess.Popen(  # noqa: S603 -- fixed own CLI, no shell
                        [sys.executable, "-m", "nexolicitcr.cli", "worker"],
                        cwd=ROOT,
                        env=env,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                )
            deadline = time.monotonic() + 60
            while True:
                try:
                    ready = httpx.get(args.url + "/health/ready", timeout=20)
                    if ready.status_code == 200:
                        break
                except httpx.TransportError:
                    pass
                require(time.monotonic() < deadline, "api_start_timeout")
                time.sleep(0.5)
            require(ready.json()["mongodb"] == "available", "atlas_readiness")
            report["checks"].append("http_readiness_atlas")
            username, password = f"smoke-{uuid4().hex[:8]}", secrets.token_urlsafe(32)
            headers = {"origin": args.url, "accept": "text/html"}
            with httpx.Client(base_url=args.url, headers=headers, timeout=30) as browser:
                token = csrf(browser.get("/register"))
                require(
                    browser.post(
                        "/register",
                        data={
                            "csrf": token,
                            "username": username,
                            "password": password,
                            "password_confirm": password,
                        },
                    ).status_code
                    == 303,
                    "registration",
                )
                token = csrf(browser.get("/login"))
                require(
                    browser.post(
                        "/login", data={"csrf": token, "username": username, "password": password}
                    ).status_code
                    == 303,
                    "login",
                )
                report["checks"].append("registration_and_login")
                catalog = browser.get("/catalog")
                token = csrf(catalog)
                require(
                    browser.post(
                        "/catalog",
                        data={
                            "csrf": token,
                            "revision": store.catalog()["revision"],
                            "name": "Redes de prueba cloud",
                            "keywords": "redes, soporte",
                            "active": "true",
                        },
                    ).status_code
                    == 303,
                    "catalog_save",
                )
                require(
                    browser.post(
                        "/discover/confirm",
                        data={
                            "csrf": token,
                            "revision": store.catalog()["revision"],
                            "company_name": "Prueba cloud",
                            "activity": "Instalamos redes informáticas para oficinas",
                            "services": "redes, soporte técnico",
                            "coverage": "Heredia",
                            "category": "servicios",
                            "confirmed": "true",
                        },
                    ).status_code
                    == 303,
                    "profile_save",
                )
                require(
                    browser.post(
                        "/catalog", data={"csrf": "invalid", "revision": 0, "name": "Invalid"}
                    ).status_code
                    == 403,
                    "csrf_rejected",
                )
                report["checks"].extend(["catalog_and_profile_atlas", "csrf_rejected"])
                for path in [
                    "/",
                    "/company",
                    "/catalog",
                    "/discover",
                    "/opportunities",
                    "/tenders",
                    "/jobs",
                    "/static/app.css",
                    "/static/app.js",
                ]:
                    require(browser.get(path).status_code == 200, "authenticated_pages_and_assets")
                report["checks"].append("authenticated_pages_and_assets")
                if args.native or args.compose_project:
                    if args.native:
                        stop(api)
                        api = start_api()
                    else:
                        compose("restart", "web")
                    deadline = time.monotonic() + 60
                    while True:
                        try:
                            persisted = browser.get("/catalog")
                            if persisted.status_code == 200:
                                break
                        except httpx.TransportError:
                            pass
                        require(time.monotonic() < deadline, "restart_timeout")
                        time.sleep(0.5)
                    require("Redes de prueba cloud" in persisted.text, "catalog_persisted")
                    report["checks"].append("session_catalog_survive_restart")
                if args.cache_outage:
                    require(bool(args.compose_project), "cache_outage_requires_compose")
                    compose("stop", "redis")
                    try:
                        require(
                            browser.get("/opportunities").status_code == 200,
                            "redis_outage_http_200",
                        )
                        require(
                            browser.get("/health/ready").json()["cache"] == "fallback",
                            "redis_outage_fallback",
                        )
                        report["checks"].append("redis_outage_falls_back_to_atlas")
                    finally:
                        compose("start", "redis")
                if args.sync:
                    response = browser.post(
                        "/sync-runs",
                        headers={"accept": "application/json"},
                        data={
                            "csrf": token,
                            "category": "servicios",
                            "limit": 1,
                            "idempotency_key": uuid4().hex,
                            "documents": str(args.documents).lower(),
                        },
                    )
                    require(response.status_code == 202, "queue_http_202")
                    job_id = response.json()["job_id"]
                    deadline = time.monotonic() + 360
                    while True:
                        state = browser.get(f"/jobs/{job_id}").json()
                        if state["status"] in {"succeeded", "failed", "canceled"}:
                            break
                        require(time.monotonic() < deadline, "sicop_worker_timeout")
                        time.sleep(2)
                    report["sicop_job"] = {
                        k: state[k]
                        for k in ["status", "progress", "attempt", "error_code", "pending_count"]
                    }
                    require(
                        state["status"] == "succeeded" and state["progress"] >= 1,
                        "real_sicop_job_succeeded",
                    )
                    tender = store.db.tenders.find_one({})
                    require(
                        tender is not None and bool(tender["payload"]["title"]), "tender_in_atlas"
                    )
                    require(
                        browser.get(f"/tenders/{tender['_id']}").status_code == 200,
                        "tender_http_200",
                    )
                    report["checks"].append("http_queue_separate_worker_real_sicop_atlas")
                    report["document_states"] = dict(
                        Counter(d["state"] for d in store.db.documents.find({}))
                    )
                    report["extracted_pages"] = store.db.extracted_pages.count_documents({})
                    report["gridfs_files"] = store.db.fs.files.count_documents({})
                require(browser.post("/logout", data={"csrf": token}).status_code == 303, "logout")
                report["checks"].append("logout")
        finally:
            for process in reversed(processes):
                stop(process)
            # Remove only the administrator created by this run; keep real SICOP evidence.
            admin = (
                store.db.users.find_one({"_id": "administrator", "username": username})
                if "username" in locals()
                else None
            )
            if admin:
                store.db.sessions.delete_many({"user_id": admin["_id"]})
                store.db.users.delete_one({"_id": admin["_id"], "username": username})
                store.db.catalog.replace_one({"_id": "company"}, original_catalog)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=Path(".env.atlas"))
    parser.add_argument("--database", default="")
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--native", action="store_true", help="Start own API and worker; no Docker")
    parser.add_argument(
        "--sync", action="store_true", help="Import one real SICOP tender and its documents"
    )
    parser.add_argument("--documents", action="store_true", help="Also fetch PDF/image attachments")
    parser.add_argument(
        "--compose-project", default="", help="Restart this Compose web during the test"
    )
    parser.add_argument(
        "--cache-outage", action="store_true", help="Stop/start this project's Redis"
    )
    parser.add_argument("--report", type=Path, default=Path("artifacts/cloud-smoke.json"))
    args = parser.parse_args()
    report = {"timestamp_utc": datetime.now(UTC).isoformat(), "checks": [], "ok": False}
    started = time.monotonic()
    try:
        run(args, report)
        report["ok"] = True
    except Exception as exc:
        # Never expose driver errors, connection strings, session cookies or signed URLs.
        report["error_type"] = type(exc).__name__
        if isinstance(exc, RuntimeError):
            report["failed_check"] = str(exc)
    report["duration_seconds"] = round(time.monotonic() - started, 2)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
