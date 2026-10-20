from datetime import timedelta

import pytest
from bs4 import BeautifulSoup
from pymongo.errors import ConnectionFailure

from nexolicitcr.storage import token_hash, utcnow

ORIGIN = {"origin": "http://localhost:8000"}


def csrf(response):
    return BeautifulSoup(response.text, "html.parser").select_one('input[name="csrf"]')["value"]


def login(client):
    token = csrf(client.get("/login"))
    return client.post(
        "/login",
        data={"username": "admin", "password": "test-password-for-fixtures", "csrf": token},
        headers=ORIGIN,
    )


def test_authentication_and_revocation(client, store):
    assert client.get("/catalog", follow_redirects=False).status_code == 303
    assert login(client).status_code == 200
    raw = client.cookies["nexo_session"]
    assert store.db.sessions.find_one({"_id": raw}) is None
    assert store.db.sessions.find_one({"_id": token_hash(raw)})
    token = csrf(client.get("/catalog"))
    assert client.post("/logout", data={"csrf": token}, headers=ORIGIN).status_code == 200
    assert store.session_get(raw) is None


def test_login_csrf_origin_and_replay(client):
    token = csrf(client.get("/login"))
    data = {"username": "admin", "password": "test-password-for-fixtures", "csrf": token}
    assert client.post("/login", data=data).status_code == 403
    assert client.post("/login", data={**data, "csrf": "forged"}, headers=ORIGIN).status_code == 403
    assert client.post("/login", data=data, headers=ORIGIN).status_code == 200
    assert client.post("/login", data=data, headers=ORIGIN).status_code == 403


def test_expired_session_rejected_without_ttl_cleanup(client, store):
    login(client)
    store.db.sessions.update_many({}, {"$set": {"expires_at": utcnow() - timedelta(seconds=1)}})
    assert client.get("/catalog", follow_redirects=False).status_code == 303


def test_catalog_crud_csrf_escape_and_revision(client, store):
    login(client)
    token = csrf(client.get("/catalog"))
    data = {
        "csrf": token,
        "revision": 0,
        "name": "<script>alert(1)</script>",
        "description": "Servicio de ejemplo",
        "keywords": "redes, soporte",
        "active": "true",
    }
    assert (
        client.post("/catalog", data={**data, "csrf": "forged"}, headers=ORIGIN).status_code == 403
    )
    response = client.post("/catalog", data=data, headers=ORIGIN)
    assert response.status_code == 200
    assert "&lt;script&gt;" in response.text and "<script>alert" not in response.text
    assert store.catalog()["revision"] == 1
    assert client.post("/catalog", data=data, headers=ORIGIN).status_code == 409
    item = store.catalog()["items"][0]
    response = client.post(
        "/catalog",
        data={**data, "revision": 1, "item_id": item["id"], "active": "false"},
        headers=ORIGIN,
    )
    assert response.status_code == 200
    assert store.catalog()["items"][0]["active"] is False


def test_db_failure_is_sanitized(client, store, monkeypatch):
    def fail():
        raise ConnectionFailure("sensitive-uri-must-not-appear")

    monkeypatch.setattr(store, "ping", fail)
    response = client.get("/health/ready")
    assert response.status_code == 503
    assert "sensitive-uri" not in response.text
    assert client.get("/health/live").status_code == 200


def test_rate_limit_and_body_limit(client):
    for _ in range(10):
        token = csrf(client.get("/login"))
        assert (
            client.post(
                "/login",
                data={"csrf": token, "username": "admin", "password": "wrong"},
                headers=ORIGIN,
            ).status_code
            == 401
        )
    token = csrf(client.get("/login"))
    assert (
        client.post(
            "/login", data={"csrf": token, "username": "admin", "password": "wrong"}, headers=ORIGIN
        ).status_code
        == 429
    )
    assert client.post("/login", content=b"a" * 40000, headers=ORIGIN).status_code == 413


def test_security_headers_and_host(client):
    response = client.get("/login")
    assert "script-src 'self'" in response.headers["content-security-policy"]
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["referrer-policy"] == "same-origin"
    assert client.get("/login", headers={"host": "attacker.example"}).status_code == 400


def test_invalid_password_never_reflected(client):
    secret = "sensitive-test-value-" * 20
    response = client.post(
        "/login", data={"username": "admin", "password": secret, "csrf": "x"}, headers=ORIGIN
    )
    assert response.status_code == 422
    assert "sensitive-test-value" not in response.text


def test_unicode_csrf_is_rejected_without_server_error(client):
    client.get("/login")
    response = client.post(
        "/login",
        data={"username": "admin", "password": "wrong", "csrf": "inválido"},
        headers=ORIGIN,
    )
    assert response.status_code == 403
    login(client)
    assert client.post("/logout", data={"csrf": "inválido"}, headers=ORIGIN).status_code == 403


def test_disabled_account_revokes_access(client, store):
    login(client)
    store.db.users.update_many({}, {"$set": {"active": False}})
    for path in ("/", "/catalog", "/tenders", "/tenders/123:1"):
        assert client.get(path, follow_redirects=False).status_code == 303


def test_security_headers_on_rejected_origin(client):
    response = client.post("/login", data={})
    assert response.status_code == 403
    assert response.headers["cache-control"] == "no-store"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]


def test_imported_tender_detail_search_and_escaping(client, store):
    import json
    from pathlib import Path

    from nexolicitcr.sicop import normalize
    from nexolicitcr.storage import utcnow

    data = json.loads((Path(__file__).parent / "fixtures/tender.json").read_text())
    tender = normalize(data["listing"], data["detail"], data["lines"], "servicios")
    tender.title = '<script>alert("source")</script>'
    store.db.tenders.insert_one(
        {
            "_id": tender.key,
            "payload": tender.model_dump(mode="json"),
            "source_url": tender.source_url,
            "observed_at": utcnow(),
        }
    )
    login(client)
    listing = client.get("/tenders", params={"q": "<script>"})
    assert listing.status_code == 200 and "&lt;script&gt;" in listing.text
    detail = client.get(f"/tenders/{tender.key}")
    assert detail.status_code == 200
    assert "125.35" in detail.text and "2026-10-15T16:00:00" in detail.text
    assert "<script>alert" not in detail.text
    assert client.get("/tenders/absent").status_code == 404
    assert client.get("/tenders", params={"q": ".*"}).text.count("No hay concursos") == 1


def test_readiness_reports_selected_mongo_backend(settings, store):
    from fastapi.testclient import TestClient

    from nexolicitcr.config import Settings
    from nexolicitcr.web import create_app

    cfg = Settings(
        _env_file=None,
        **settings.model_dump()
        | {
            "mongo_mode": "local",
            "mongo_local_usuario": "local-user",
            "mongo_local_clave": "test-only-local-password",
        },
    )
    with TestClient(create_app(cfg, store), base_url="http://localhost:8000") as client:
        response = client.get("/health/ready")
        assert response.status_code == 200
        assert response.json()["mongo_mode"] == "local"
        assert response.json()["mongodb"] == "available"


@pytest.mark.parametrize("origin", ["null", "https://attacker.example", "http://localhost:8001"])
def test_login_rejects_untrusted_origins(client, origin):
    token = csrf(client.get("/login"))
    response = client.post(
        "/login",
        data={"username": "admin", "password": "test-password-for-fixtures", "csrf": token},
        headers={"origin": origin},
    )
    assert response.status_code == 403
    assert "nexo_session" not in client.cookies


def test_persistent_jobs_http_and_csrf(client, store):
    assert (
        client.post(
            "/sync-runs",
            data={"csrf": "x", "idempotency_key": "anonymous"},
            headers=ORIGIN,
            follow_redirects=False,
        ).status_code
        == 303
    )
    login(client)
    token = csrf(client.get("/jobs"))
    data = {
        "csrf": token,
        "category": "bienes",
        "limit": 5,
        "since": "",
        "idempotency_key": "http-once",
    }
    response = client.post("/sync-runs", data=data, headers=ORIGIN | {"accept": "application/json"})
    assert response.status_code == 202
    job_id = response.json()["job_id"]
    assert store.db.jobs.find_one({"_id": job_id})["status"] == "queued"
    assert client.post("/sync-runs", data=data, headers=ORIGIN).json()["job_id"] == job_id
    assert client.get(f"/jobs/{job_id}").json()["status"] == "queued"
    assert client.get(f"/jobs/{job_id}/view").status_code == 200
    assert (
        client.post(f"/jobs/{job_id}/cancel", data={"csrf": "bad"}, headers=ORIGIN).status_code
        == 403
    )
    assert (
        client.post(f"/jobs/{job_id}/cancel", data={"csrf": token}, headers=ORIGIN).status_code
        == 200
    )
    assert store.db.jobs.find_one({"_id": job_id})["cancel_requested"]
    store.db.jobs.update_one({"_id": job_id}, {"$set": {"installation_id": "other"}})
    assert client.get(f"/jobs/{job_id}").status_code == 404


def test_radar_filters_and_decision_survive_catalog_edit(client, store):
    import json
    from pathlib import Path

    from nexolicitcr.models import CatalogItem
    from nexolicitcr.sicop import normalize

    data = json.loads((Path(__file__).parent / "fixtures/tender.json").read_text())
    tender = normalize(data["listing"], data["detail"], data["lines"], "servicios")
    store.db.tenders.insert_one(
        {
            "_id": tender.key,
            "payload": tender.model_dump(mode="json"),
            "source_url": tender.source_url,
            "observed_at": utcnow(),
        }
    )
    login(client)
    token = csrf(client.get("/catalog"))
    assert (
        client.post(
            f"/decisions/{tender.key}",
            data={"csrf": token, "status": "following", "note": "<script>private</script>"},
            headers=ORIGIN,
        ).status_code
        == 200
    )
    store.save_catalog_item(CatalogItem(name="Redes", keywords=["redes"]), 0)
    assert client.get("/opportunities?status=following").status_code == 200
    assert "1 resultado" in client.get("/opportunities?status=following").text
    assert "&lt;script&gt;private" in client.get(f"/tenders/{tender.key}").text
    assert client.get("/opportunities?minimum=101").status_code == 422


def test_resume_job_requires_csrf_and_preserves_history(client, store):
    login(client)
    token = csrf(client.get("/jobs"))
    response = client.post(
        "/sync-runs", data={"csrf": token, "idempotency_key": "resume-web"}, headers=ORIGIN
    )
    job_id = response.json()["job_id"]
    assert (
        client.post(f"/jobs/{job_id}/resume", data={"csrf": token}, headers=ORIGIN).status_code
        == 409
    )
    store.db.jobs.update_one(
        {"_id": job_id},
        {"$set": {"status": "failed", "progress": 1, "checkpoint": ["bienes:A:00"]}},
    )
    assert "Reanudar pendientes" in client.get(f"/jobs/{job_id}/view").text
    assert (
        client.post(f"/jobs/{job_id}/resume", data={"csrf": "invalid"}, headers=ORIGIN).status_code
        == 403
    )
    result = client.post(
        f"/jobs/{job_id}/resume", data={"csrf": token}, headers=ORIGIN, follow_redirects=False
    )
    assert result.status_code == 303
    assert (
        client.post(
            f"/jobs/{job_id}/resume", data={"csrf": token}, headers=ORIGIN, follow_redirects=False
        ).headers["location"]
        == result.headers["location"]
    )
    assert store.db.jobs.find_one({"resume_of": job_id})["checkpoint"] == ["bienes:A:00"]
    assert store.db.jobs.find_one({"_id": job_id})["status"] == "failed"
    store.db.jobs.update_one({"_id": job_id}, {"$set": {"installation_id": "other"}})
    assert (
        client.post(f"/jobs/{job_id}/resume", data={"csrf": token}, headers=ORIGIN).status_code
        == 404
    )


def test_missing_pages_are_html_for_browsers_and_json_for_api(client):
    login(client)
    browser = {"accept": "text/html,application/xhtml+xml"}
    for path in ("/catalog?edit=missing", "/tenders/absent"):
        page = client.get(path, headers=browser)
        assert page.status_code == 404
        assert page.headers["content-type"].startswith("text/html")
        assert 'role="alert"' in page.text and "No encontramos esta página." in page.text
        assert "Volver al formulario" not in page.text
    api = client.get("/tenders/absent", headers={"accept": "application/json"})
    assert api.status_code == 404 and "detail" in api.json()
