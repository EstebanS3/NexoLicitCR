from datetime import timedelta

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
    assert "script-src 'none'" in response.headers["content-security-policy"]
    assert response.headers["cache-control"] == "no-store"
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
