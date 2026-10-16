from datetime import timedelta

import mongomock
import pytest
from bs4 import BeautifulSoup
from fastapi.testclient import TestClient

from nexolicitcr.security import PASSWORDS, check_password
from nexolicitcr.storage import Store, token_hash, utcnow
from nexolicitcr.web import create_app

ORIGIN = {"origin": "http://localhost:8000"}
TEST_PASSWORD = "a-test-only-long-passphrase"


@pytest.fixture
def installation(settings):
    store = Store(mongomock.MongoClient(tz_aware=True).registration_test)
    store.ensure_indexes()
    with TestClient(create_app(settings, store), base_url="http://localhost:8000") as client:
        yield client, store


def form(client, **changes):
    page = client.get("/register")
    token = BeautifulSoup(page.text, "html.parser").select_one('input[name="csrf"]')["value"]
    return {
        "username": "my.company",
        "password": TEST_PASSWORD,
        "password_confirm": TEST_PASSWORD,
        "csrf": token,
        **changes,
    }


def test_initial_registration_keeps_existing_schema_and_can_log_in(installation):
    client, store = installation
    assert 'href="/register"' in client.get("/login").text
    data = form(client, username=" My.Company ")
    response = client.post("/register", data=data, headers=ORIGIN, follow_redirects=False)
    assert response.status_code == 303 and response.headers["location"] == "/login?registered=1"
    user = store.db.users.find_one()
    assert set(user) == {"_id", "username", "password_hash", "active"}
    assert user["_id"] == "administrator" and user["username"] == "my.company"
    assert user["active"] and user["password_hash"] != TEST_PASSWORD
    assert check_password(TEST_PASSWORD, user["password_hash"])[0]
    assert store.db.sessions.count_documents({}) == 0
    assert store.catalog()["items"] == [] and "profile" not in store.catalog()
    assert store.db.jobs.count_documents({}) == 0
    assert not store.registration_open()
    login_page = client.get(response.headers["location"])
    assert "Tu cuenta está lista" in login_page.text and 'href="/register"' not in login_page.text
    nonce = BeautifulSoup(login_page.text, "html.parser").select_one('input[name="csrf"]')["value"]
    assert (
        client.post(
            "/login",
            data={"username": "my.company", "password": TEST_PASSWORD, "csrf": nonce},
            headers=ORIGIN,
            follow_redirects=False,
        ).status_code
        == 303
    )
    assert client.get("/company").status_code == 200
    assert client.post("/register", data=data, headers=ORIGIN).status_code == 409
    assert store.db.users.count_documents({}) == 1


@pytest.mark.parametrize(
    "changes,message",
    [
        ({"username": "x"}, "3 y 64"),
        ({"username": "<script>alert(1)</script>"}, "3 y 64"),
        ({"password": "weak"}, "14 y 256"),
        ({"password_confirm": "a-different-long-passphrase"}, "no coinciden"),
    ],
)
def test_registration_validation_preserves_no_passwords(installation, changes, message):
    client, store = installation
    data = form(client, **changes)
    response = client.post("/register", data=data, headers=ORIGIN)
    assert response.status_code == 422 and message in response.text
    assert data["password"] not in response.text
    assert "<script>alert(1)</script>" not in response.text
    assert store.db.users.count_documents({}) == 0
    assert (
        BeautifulSoup(response.text, "html.parser").select_one('input[name="csrf"]')["value"]
        != data["csrf"]
    )
    assert all(set(row) == {"_id", "expires_at"} for row in store.db.login_tokens.find())


def test_registration_requires_origin_and_one_time_nonce(installation):
    client, store = installation
    data = form(client)
    assert (
        client.post("/register", data=data, headers={"origin": "https://example.com"}).status_code
        == 403
    )
    assert (
        client.post("/register", data={**data, "csrf": "inválido"}, headers=ORIGIN).status_code
        == 403
    )
    data = form(client)
    store.db.login_tokens.update_one(
        {"_id": token_hash("register:" + data["csrf"])},
        {"$set": {"expires_at": utcnow() - timedelta(seconds=1)}},
    )
    assert client.post("/register", data=data, headers=ORIGIN).status_code == 403
    data = form(client, username="x")
    assert client.post("/register", data=data, headers=ORIGIN).status_code == 422
    client.cookies.set("nexo_register", data["csrf"], path="/register", domain="localhost.local")
    assert client.post("/register", data=data, headers=ORIGIN).status_code == 403
    assert store.db.users.count_documents({}) == 0


def test_login_nonce_cannot_create_initial_account(installation):
    client, store = installation
    data = form(client)
    login_page = client.get("/login")
    nonce = BeautifulSoup(login_page.text, "html.parser").select_one('input[name="csrf"]')["value"]
    client.cookies.set("nexo_register", nonce, path="/register", domain="localhost.local")
    assert client.post("/register", data={**data, "csrf": nonce}, headers=ORIGIN).status_code == 403
    assert store.db.login_tokens.find_one({"_id": token_hash(nonce)})
    assert not store.db.users.find_one()


def test_registration_is_rate_limited_before_password_hashing(installation):
    client, store = installation
    for _ in range(10):
        assert (
            client.post("/register", data=form(client, username="x"), headers=ORIGIN).status_code
            == 422
        )
    assert client.post("/register", data=form(client), headers=ORIGIN).status_code == 429
    assert store.db.users.count_documents({}) == 0


def test_competing_bootstrap_cannot_replace_first_account(installation, monkeypatch):
    client, store = installation
    create = store.create_admin
    winner_hash = PASSWORDS.hash("another-test-only-passphrase")

    def competing(username, encoded):
        create("winner", winner_hash)
        create(username, encoded)

    monkeypatch.setattr(store, "create_admin", competing)
    assert client.post("/register", data=form(client), headers=ORIGIN).status_code == 409
    assert store.db.users.count_documents({}) == 1
    assert store.user("winner")["password_hash"] == winner_hash
    assert "Esta instalación" in client.get("/register").text


def test_existing_or_disabled_account_keeps_registration_closed(client, store):
    before = store.db.users.find_one()
    store.db.users.update_one({"_id": before["_id"]}, {"$set": {"active": False}})
    assert not store.registration_open()
    page = client.get("/register")
    assert page.status_code == 200 and 'action="/register"' not in page.text
    assert (
        client.post(
            "/register",
            data={
                "username": "replacement",
                "password": TEST_PASSWORD,
                "password_confirm": TEST_PASSWORD,
                "csrf": "invalid",
            },
            headers=ORIGIN,
        ).status_code
        == 409
    )
    assert store.db.users.find_one()["password_hash"] == before["password_hash"]
    assert store.db.users.count_documents({}) == 1


def test_oversized_registration_never_reflects_password(installation):
    client, store = installation
    data = form(client, password="secret" * 50)
    response = client.post("/register", data=data, headers=ORIGIN)
    assert response.status_code == 422 and data["password"] not in response.text
    assert store.db.users.count_documents({}) == 0


def test_root_shows_initial_registration_and_accepts_its_nonce(installation):
    client, store = installation
    page = client.get("/", follow_redirects=False)
    assert page.status_code == 200
    assert "Creá tu cuenta" in page.text and 'action="/register"' in page.text
    csrf = BeautifulSoup(page.text, "html.parser").select_one('input[name="csrf"]')["value"]
    assert store.db.users.count_documents({}) == 0
    result = client.post(
        "/register",
        data={
            "username": "company.owner",
            "password": TEST_PASSWORD,
            "password_confirm": TEST_PASSWORD,
            "csrf": csrf,
        },
        headers=ORIGIN,
        follow_redirects=False,
    )
    assert result.status_code == 303
    assert store.user("company.owner")
    root = client.get("/", follow_redirects=False)
    assert root.status_code == 303 and root.headers["location"] == "/login"


def test_root_does_not_reopen_registration_for_disabled_account(client, store):
    store.db.users.update_many({}, {"$set": {"active": False}})
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 303 and response.headers["location"] == "/login"
    assert store.db.users.count_documents({}) == 1
