import pytest

from nexolicitcr.discovery import suggest
from nexolicitcr.models import CatalogItem

ORIGIN = {"origin": "http://localhost:8000"}


def authenticated(client, store):
    token = store.session_create("administrator", 8)
    client.cookies.set("nexo_session", token)
    return store.session_get(token)["csrf"]


def profile_form(csrf, revision=0):
    return {
        "csrf": csrf,
        "revision": revision,
        "activity": "Instalamos redes informáticas para oficinas",
        "services": "redes, soporte técnico",
        "coverage": "Heredia",
        "category": "servicios",
        "confirmed": "true",
    }


def test_draft_is_not_saved_and_confirmation_preserves_catalog(client, store):
    csrf = authenticated(client, store)
    store.save_catalog_item(CatalogItem(name="Producto existente"), 0)
    assert client.get("/discover").status_code == 200
    draft = client.post(
        "/discover/draft",
        data={
            "csrf": csrf,
            "revision": 1,
            "activity": "Instalamos redes informáticas para oficinas",
        },
        headers=ORIGIN,
    )
    assert draft.status_code == 200 and "BORRADOR" in draft.text
    assert "profile" not in store.catalog()
    assert store.db.jobs.count_documents({}) == 0
    data = profile_form(csrf, 1)
    assert (
        client.post(
            "/discover/confirm", data={**data, "confirmed": "false"}, headers=ORIGIN
        ).status_code
        == 422
    )
    result = client.post("/discover/confirm", data=data, headers=ORIGIN)
    assert result.status_code == 200 and "TU PERFIL CONFIRMADO" in result.text
    catalog = store.catalog()
    assert catalog["revision"] == 2 and catalog["items"][0]["name"] == "Producto existente"
    assert catalog["profile"]["services"] == ["redes", "soporte técnico"]
    assert client.post("/discover/confirm", data=data, headers=ORIGIN).status_code == 409


def test_guided_search_uses_confirmed_scope_and_is_idempotent(client, store):
    csrf = authenticated(client, store)
    client.post("/discover/confirm", data=profile_form(csrf), headers=ORIGIN)
    data = {"csrf": csrf, "revision": 1, "idempotency_key": "guided-click"}
    for _ in range(2):
        assert client.post("/discover/search", data=data, headers=ORIGIN).status_code == 200
    job = store.db.jobs.find_one()
    assert store.db.jobs.count_documents({}) == 1
    assert job["payload"]["category"] == "servicios"
    assert job["payload"]["profile_revision"] == 1
    assert (
        client.post("/discover/search", data={**data, "revision": 0}, headers=ORIGIN).status_code
        == 409
    )
    assert (
        client.post(
            "/discover/confirm", data={**profile_form(csrf, 1), "csrf": "forged"}, headers=ORIGIN
        ).status_code
        == 403
    )


@pytest.mark.parametrize("services", ["", ", ,", ",".join(["term"] * 9)])
def test_invalid_services_do_not_mutate_profile(client, store, services):
    csrf = authenticated(client, store)
    result = client.post(
        "/discover/confirm", data={**profile_form(csrf), "services": services}, headers=ORIGIN
    )
    assert result.status_code == 422
    assert store.catalog()["revision"] == 0


def test_unknown_activity_requests_detail_and_escapes_html(client, store):
    csrf = authenticated(client, store)
    assert suggest("Somos una empresa de servicios generales") == []
    response = client.post(
        "/discover/draft",
        data={"csrf": csrf, "revision": 0, "activity": "<script>alert(1)</script> servicios"},
        headers=ORIGIN,
    )
    assert response.status_code == 200
    assert "<script>alert" not in response.text


def test_profile_changes_invalidate_radar_without_losing_decisions(store, settings):
    from test_cache_matching import MemoryRedis, tender_payload

    from nexolicitcr.cache import OptionalCache
    from nexolicitcr.matching import Radar
    from nexolicitcr.models import CompanyProfile

    tender = tender_payload()
    tender["title"] = "Instalación de redes"
    store.db.tenders.insert_one({"_id": "demo:1", "payload": tender, "hash": "demo-v1"})
    radar = Radar(store, OptionalCache(settings, MemoryRedis()))
    radar.decide("demo:1", "following", "Seguimiento existente")
    assert radar.rows()[0]["match"]["score"] == 0
    store.save_profile(
        CompanyProfile(activity="Instalamos redes informáticas", services=["redes"]), 0
    )
    rows = radar.rows()
    assert rows[0]["match"]["score"] > 0
    assert rows[0]["decision"]["note"] == "Seguimiento existente"
    store.save_profile(
        CompanyProfile(activity="Servicios de jardinería", services=["jardinería"]), 1
    )
    assert radar.rows()[0]["match"]["score"] == 0
    assert len(store.catalog()["items"]) == 0


def test_company_onboarding_is_draft_until_confirmation(client, store):
    from bs4 import BeautifulSoup

    csrf = authenticated(client, store)
    assert "Crear mi empresa" in client.get("/").text
    assert client.get("/company").status_code == 200
    company = client.post(
        "/company/draft",
        data={
            "csrf": csrf,
            "revision": 0,
            "company_name": "Mi empresa nueva",
        },
        headers=ORIGIN,
    )
    assert company.status_code == 200
    assert "profile" not in store.catalog()
    draft = client.post(
        "/discover/draft",
        data={
            "csrf": csrf,
            "revision": 0,
            "company_name": "Mi empresa nueva",
            "activity": "Desarrollamos software para empresas",
        },
        headers=ORIGIN,
    )
    assert "Mi empresa nueva" in draft.text
    assert store.db.jobs.count_documents({}) == 0
    assert "profile" not in store.catalog()
    form = profile_form(csrf)
    form.update(company_name="Mi empresa nueva", services="software")
    assert client.post("/discover/confirm", data=form, headers=ORIGIN).status_code == 200
    assert store.catalog()["profile"]["company_name"] == "Mi empresa nueva"
    assert store.db.jobs.count_documents({}) == 0
    assert "Mi empresa nueva" in client.get("/").text
    edit = client.get("/company")
    assert (
        BeautifulSoup(edit.text, "html.parser").select_one("[name=company_name]")["value"]
        == "Mi empresa nueva"
    )
    assert (
        client.post(
            "/company/draft",
            data={
                "csrf": csrf,
                "revision": 0,
                "company_name": "Otro nombre",
            },
            headers=ORIGIN,
        ).status_code
        == 409
    )
    assert (
        client.post(
            "/company/draft",
            data={
                "csrf": "forged",
                "revision": 1,
                "company_name": "Otro nombre",
            },
            headers=ORIGIN,
        ).status_code
        == 403
    )


def test_onboarding_html_errors_are_actionable(client, store):
    csrf = authenticated(client, store)
    response = client.post(
        "/company/draft",
        data={
            "csrf": csrf,
            "revision": 0,
            "company_name": " ",
        },
        headers={**ORIGIN, "accept": "text/html"},
    )
    assert response.status_code == 422
    assert "Volver al formulario" in response.text
    assert "profile" not in store.catalog()


@pytest.mark.parametrize(
    ("sector", "specialty", "expected", "absent"),
    [
        ("sports", "goal_nets", "redes para arcos", "redes informáticas"),
        ("technology", "networks", "redes informáticas", "redes para arcos"),
        ("marketing", "social", "redes sociales", "redes informáticas"),
    ],
)
def test_explicit_specialty_disambiguates_networks(
    client, store, sector, specialty, expected, absent
):
    from bs4 import BeautifulSoup

    csrf = authenticated(client, store)
    result = client.post(
        "/discover/draft",
        data={
            "csrf": csrf,
            "revision": 0,
            "activity": "Nuestra empresa ofrece redes",
            "sector": sector,
            "specialty": specialty,
        },
        headers=ORIGIN,
    )
    assert result.status_code == 200
    terms = BeautifulSoup(result.text, "html.parser").select_one("[name=services]").text
    assert expected in terms and absent not in terms
    assert "profile" not in store.catalog()


def test_specialty_must_belong_to_sector(client, store):
    csrf = authenticated(client, store)
    data = {
        "csrf": csrf,
        "revision": 0,
        "activity": "Nuestra empresa ofrece redes",
        "sector": "sports",
        "specialty": "networks",
    }
    assert client.post("/discover/draft", data=data, headers=ORIGIN).status_code == 422
    assert (
        client.post(
            "/discover/confirm",
            data={**data, "services": "redes", "confirmed": "true"},
            headers=ORIGIN,
        ).status_code
        == 422
    )
    assert "profile" not in store.catalog()
