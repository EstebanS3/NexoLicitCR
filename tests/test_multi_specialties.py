"""HTTP lifecycle and matching for multiple capabilities, without a live source."""

import pytest
from bs4 import BeautifulSoup

from nexolicitcr.models import CompanyProfile
from nexolicitcr.sectors import SECTORS, combined_terms

ORIGIN = {"origin": "http://localhost:8000"}


def auth(client, store):
    token = store.session_create("administrator", 8)
    client.cookies.set("nexo_session", token)
    return {"csrf": store.session_get(token)["csrf"], "revision": store.catalog()["revision"]}


def form_fields(response):
    soup = BeautifulSoup(response.text, "html.parser")
    form = soup.select_one('form[action="/discover/confirm"]')
    data = {}
    for field in form.select("input[name], textarea[name], select[name]"):
        name = field["name"]
        if name == "specialties":
            data.setdefault(name, []).append(field["value"])
        elif field.name == "textarea":
            data[name] = field.text
        elif field.name == "select":
            data[name] = (field.select_one("option[selected]") or field.select_one("option"))[
                "value"
            ]
        else:
            data[name] = field.get("value", "")
    return data


def test_cross_sector_round_trip_preserves_edits_and_no_search_until_requested(client, store):
    data = {
        **auth(client, store),
        "company_name": "Empresa mixta",
        "multiple": "true",
        "specialties": ["technology:software", "construction:roads", "health:medical_supplies"],
    }
    draft = client.post("/discover/draft", data=data, headers=ORIGIN)
    assert draft.status_code == 200
    fields = form_fields(draft)
    expected = combined_terms(data["specialties"])
    assert fields["services"].split(", ") == expected
    assert len(expected) > 8 and len(expected) == len(set(expected))
    assert "profile" not in store.catalog()
    fields.update(
        coverage="Cartago", exclusions="telefonía móvil", services="software, pavimentación"
    )
    revised = client.post("/discover/revise", data=fields, headers=ORIGIN)
    assert revised.status_code == 200
    soup = BeautifulSoup(revised.text, "html.parser")
    assert [x["value"] for x in soup.select("[name=specialties]:checked")] == data["specialties"]
    redraft = client.post(
        "/discover/draft",
        data={
            **data,
            "activity": fields["activity"],
            "draft_services": fields["services"],
            "draft_specialties": data["specialties"],
            "draft_coverage": fields["coverage"],
            "draft_exclusions": fields["exclusions"],
            "draft_category": "all",
        },
        headers=ORIGIN,
    )
    assert redraft.status_code == 200
    edited = form_fields(redraft)
    assert edited["services"] == "software, pavimentación"
    assert edited["coverage"] == "Cartago"
    assert client.post("/discover/confirm", data=edited, headers=ORIGIN).status_code == 200
    assert store.catalog()["profile"]["specialties"] == data["specialties"]
    assert store.catalog()["profile"]["services"] == ["software", "pavimentación"]
    assert store.db.jobs.count_documents({}) == 0
    assert client.post("/discover/confirm", data=edited, headers=ORIGIN).status_code == 409
    page = client.get("/opportunities")
    assert BeautifulSoup(page.text, "html.parser").select_one("[name=documents][checked]")
    search = {**data, "revision": 1, "idempotency_key": "with-documents", "documents": "true"}
    assert client.post("/discover/search", data=search, headers=ORIGIN).status_code == 200
    assert store.db.jobs.find_one()["payload"]["documents"] is True
    assert client.post("/discover/search", data=search, headers=ORIGIN).status_code == 200
    assert store.db.jobs.count_documents({}) == 1
    assert (
        client.post(
            "/discover/search", data={**search, "documents": "false"}, headers=ORIGIN
        ).status_code
        == 409
    )


@pytest.mark.parametrize(
    "selections",
    [
        [],
        ["unknown:x"],
        ["health:software"],
        ["technology:software"] * 2,
        ["technology:software"] * 9,
        ["x" * 82],
        ["a:b:c"],
    ],
)
@pytest.mark.parametrize("endpoint", ["draft", "revise", "confirm"])
def test_invalid_multiple_selections_do_not_save(client, store, selections, endpoint):
    data = {
        **auth(client, store),
        "multiple": "true",
        "specialties": selections,
        "activity": "Ofrecemos servicios para instituciones",
        "services": "software",
        "confirmed": "true",
    }
    response = client.post(f"/discover/{endpoint}", data=data, headers=ORIGIN)
    assert response.status_code == 422
    assert "profile" not in store.catalog()
    assert store.db.jobs.count_documents({}) == 0


def test_every_sector_combines_with_other_sectors_without_truncating_terms(client, store):
    base = auth(client, store)
    for sector, info in SECTORS.items():
        if sector == "other":
            continue
        choices = [f"{sector}:{next(iter(info['specialties']))}"]
        choices.append("sports:goal_nets" if sector != "sports" else "technology:software")
        result = client.post(
            "/discover/draft",
            data={**base, "multiple": "true", "specialties": choices},
            headers=ORIGIN,
        )
        assert result.status_code == 200
        data = form_fields(result)
        assert data["services"].split(", ") == combined_terms(choices)
        assert (
            CompanyProfile(
                activity=data["activity"], specialties=choices, services=combined_terms(choices)
            ).specialties
            == choices
        )


def test_custom_selection_requires_description_even_with_known_specialty(client, store):
    data = {
        **auth(client, store),
        "multiple": "true",
        "specialties": ["other:custom", "technology:software"],
    }
    assert client.post("/discover/draft", data=data, headers=ORIGIN).status_code == 422
    assert (
        client.post(
            "/discover/draft",
            data={**data, "activity": "Ofrecemos servicios de acuicultura"},
            headers=ORIGIN,
        ).status_code
        == 200
    )


def test_eight_specialties_and_64_terms_can_be_saved_and_65_are_rejected(client, store):
    choices = [f"{s}:{k}" for s, data in SECTORS.items() for k in data["specialties"]][:8]
    data = {
        **auth(client, store),
        "multiple": "true",
        "specialties": choices,
        "activity": "Ofrecemos servicios en varias especialidades",
        "confirmed": "true",
    }
    assert (
        client.post(
            "/discover/confirm",
            data={**data, "services": ",".join(f"servicio {i}" for i in range(65))},
            headers=ORIGIN,
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/discover/confirm",
            data={**data, "services": ",".join(f"servicio {i}" for i in range(64))},
            headers=ORIGIN,
        ).status_code
        == 200
    )
    assert len(store.catalog()["profile"]["services"]) == 64


def test_reordering_choices_does_not_replace_manual_services_or_description(client, store):
    choices = ["construction:roads", "technology:software"]
    profile = CompanyProfile(
        specialties=choices,
        activity="Diseñamos soluciones para instituciones locales",
        services=["mi servicio personalizado"],
        coverage="Heredia",
    )
    store.save_profile(profile, 0)
    data = {**auth(client, store), "multiple": "true", "specialties": list(reversed(choices))}
    draft = client.post("/discover/draft", data=data, headers=ORIGIN)
    assert draft.status_code == 200
    fields = form_fields(draft)
    assert fields["services"] == "mi servicio personalizado"
    assert fields["activity"] == profile.activity
    assert fields["coverage"] == "Heredia"
    revised = client.post(
        "/discover/draft",
        data={
            **data,
            "draft_specialties": choices,
            "draft_services": "servicio editado en borrador",
            "draft_category": "all",
        },
        headers=ORIGIN,
    )
    assert revised.status_code == 200
    assert form_fields(revised)["services"] == "servicio editado en borrador"
