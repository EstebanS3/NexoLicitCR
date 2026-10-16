import pytest
from bs4 import BeautifulSoup

from nexolicitcr.models import CompanyProfile

ORIGIN = {"origin": "http://localhost:8000"}


def draft_data(client, store, **overrides):
    token = store.session_create("administrator", 8)
    client.cookies.set("nexo_session", token)
    return {
        "csrf": store.session_get(token)["csrf"],
        "revision": store.catalog()["revision"],
        "company_name": "Norte Deportivo",
        "sector": "sports",
        "specialty": "goal_nets",
        **overrides,
    }


def form_value(response, name):
    field = BeautifulSoup(response.text, "html.parser").select_one(f"[name={name}]")
    assert field is not None, f"Falta el campo {name}"
    if field.name == "select":
        option = field.select_one("option[selected]") or field.select_one("option")
        return option.get("value", "")
    return field.text if field.name == "textarea" else field.get("value", "")


@pytest.mark.parametrize("activity", [None, "", "   "])
def test_selected_specialty_needs_no_written_description(client, store, activity):
    data = draft_data(client, store)
    if activity is not None:
        data["activity"] = activity
    response = client.post("/discover/draft", data=data, headers=ORIGIN)
    assert response.status_code == 200
    assert form_value(response, "activity") == (
        "Norte Deportivo ofrece redes para arcos y porterías."
    )
    assert "redes para arcos" in form_value(response, "services")
    assert "redes informáticas" not in form_value(response, "services")
    assert "profile" not in store.catalog()
    assert store.catalog()["revision"] == 0
    assert store.db.jobs.count_documents({}) == 0

    confirmed = {
        **data,
        **{
            field: form_value(response, field)
            for field in ("activity", "services", "sector", "specialty", "company_name")
        },
        "confirmed": "true",
    }
    saved = client.post("/discover/confirm", data=confirmed, headers=ORIGIN)
    assert saved.status_code == 200
    profile = store.catalog()["profile"]
    assert profile["company_name"] == "Norte Deportivo"
    assert profile["sector"] == "sports"
    assert profile["specialty"] == "goal_nets"
    assert profile["activity"] == confirmed["activity"]
    assert profile["services"] == [
        "redes para arcos",
        "redes para porterías",
        "redes de fútbol",
    ]
    assert store.db.jobs.count_documents({}) == 0


@pytest.mark.parametrize(
    "overrides",
    [
        {"sector": "other", "specialty": "custom"},
        {"sector": "", "specialty": ""},
        {"sector": "sports", "specialty": "networks"},
        {"sector": "technology", "specialty": ""},
        {"activity": "Software", "sector": "", "specialty": ""},
        {"activity": "a" * 1001},
    ],
)
def test_invalid_or_incomplete_description_has_no_side_effects(client, store, overrides):
    response = client.post(
        "/discover/draft", data=draft_data(client, store, **overrides), headers=ORIGIN
    )
    assert response.status_code == 422
    assert "profile" not in store.catalog()
    assert store.catalog()["revision"] == 0


def test_custom_description_does_not_guess_services(client, store):
    response = client.post(
        "/discover/draft",
        data=draft_data(
            client,
            store,
            sector="other",
            specialty="custom",
            activity="Fabricamos redes para acuicultura",
        ),
        headers=ORIGIN,
    )
    assert response.status_code == 200
    assert form_value(response, "activity") == "Fabricamos redes para acuicultura"
    assert not form_value(response, "services").strip()


def test_existing_profile_keeps_edited_fields_when_description_is_omitted(client, store):
    profile = CompanyProfile(
        company_name="Norte Deportivo",
        sector="sports",
        specialty="goal_nets",
        activity="Fabricamos redes de fútbol a la medida para canchas municipales",
        services=["redes de fútbol"],
        coverage="Cartago",
        exclusions=["redes informáticas"],
        category="bienes",
    )
    store.save_profile(profile, 0)
    response = client.post("/discover/draft", data=draft_data(client, store), headers=ORIGIN)
    assert response.status_code == 200
    assert form_value(response, "activity") == profile.activity
    assert form_value(response, "services") == "redes de fútbol"
    assert form_value(response, "coverage") == "Cartago"
    assert form_value(response, "exclusions") == "redes informáticas"
    assert store.catalog()["profile"] == profile.model_dump(mode="json")
    assert store.catalog()["revision"] == 1

    changed = client.post(
        "/discover/draft",
        data=draft_data(client, store, sector="technology", specialty="networks"),
        headers=ORIGIN,
    )
    assert changed.status_code == 200
    assert "redes informáticas y cableado" in form_value(changed, "activity")
    assert "redes informáticas" in form_value(changed, "services")
    assert "redes de fútbol" not in form_value(changed, "services")
    assert store.catalog()["profile"] == profile.model_dump(mode="json")


def test_draft_rejects_stale_revision(client, store):
    data = draft_data(client, store)
    store.save_profile(
        CompanyProfile(activity="Desarrollamos aplicaciones web", services=["software"]), 0
    )
    response = client.post("/discover/draft", data=data, headers=ORIGIN)
    assert response.status_code == 409
    assert store.catalog()["revision"] == 1
    assert store.catalog()["profile"]["services"] == ["software"]


def test_legacy_explicit_description_without_sector_still_works(client, store):
    response = client.post(
        "/discover/draft",
        data=draft_data(
            client,
            store,
            sector="",
            specialty="",
            activity="Instalamos redes informáticas para oficinas",
        ),
        headers=ORIGIN,
    )
    assert response.status_code == 200
    assert form_value(response, "activity") == "Instalamos redes informáticas para oficinas"
    assert form_value(response, "services").strip()
    assert "profile" not in store.catalog()


@pytest.mark.parametrize("change_specialty", [False, True])
def test_revise_and_redraft_preserve_manual_details(client, store, change_specialty):
    data = draft_data(
        client,
        store,
        activity="Fabricamos redes de fútbol para canchas municipales",
        services="redes de fútbol a la medida",
        coverage="Cartago",
        exclusions="redes informáticas",
        category="bienes",
    )
    revised = client.post("/discover/revise", data=data, headers=ORIGIN)
    assert revised.status_code == 200
    assert revised.context["step"] == 1
    assert revised.context["profile"]["services"] == ["redes de fútbol a la medida"]
    assert revised.context["profile"]["company_name"] == "Norte Deportivo"
    assert "profile" not in store.catalog()

    resubmitted = {
        **data,
        **{
            f"draft_{field}": data[field]
            for field in ("services", "coverage", "exclusions", "category", "sector", "specialty")
        },
    }
    if change_specialty:
        resubmitted.update(sector="technology", specialty="networks")
    reviewed = client.post("/discover/draft", data=resubmitted, headers=ORIGIN)
    assert reviewed.status_code == 200
    if change_specialty:
        assert "redes informáticas" in form_value(reviewed, "services")
        assert "redes de fútbol" not in form_value(reviewed, "services")
    else:
        assert form_value(reviewed, "services") == "redes de fútbol a la medida"
    assert form_value(reviewed, "coverage") == "Cartago"
    assert form_value(reviewed, "exclusions") == "redes informáticas"
    assert form_value(reviewed, "category") == "bienes"
    assert form_value(reviewed, "company_name") == "Norte Deportivo"
    assert "profile" not in store.catalog()
    assert store.catalog()["revision"] == 0
    assert store.db.jobs.count_documents({}) == 0


def test_revise_allows_empty_services_to_be_corrected(client, store):
    data = draft_data(client, store, activity="Ofrecemos redes para arcos", services="")
    response = client.post("/discover/revise", data=data, headers=ORIGIN)
    assert response.status_code == 200
    assert response.context["profile"]["services"] == []
    assert "profile" not in store.catalog()
    draft = client.post(
        "/discover/draft",
        data={
            **data,
            "draft_services": "",
            "draft_sector": "sports",
            "draft_specialty": "goal_nets",
            "draft_category": "all",
        },
        headers=ORIGIN,
    )
    assert draft.status_code == 200
    assert form_value(draft, "services") == ""


@pytest.mark.parametrize(
    ("overrides", "status"),
    [
        ({"csrf": "forged"}, 403),
        ({"revision": 1}, 409),
        ({"specialty": "networks"}, 422),
        ({"category": "not-a-category"}, 422),
        ({"activity": "a" * 1001}, 422),
    ],
)
def test_revise_validates_scope_without_saving(client, store, overrides, status):
    response = client.post(
        "/discover/revise", data=draft_data(client, store, **overrides), headers=ORIGIN
    )
    assert response.status_code == status
    assert "profile" not in store.catalog()
    assert store.catalog()["revision"] == 0


def test_first_radar_has_a_clear_next_action(client, store):
    data = draft_data(client, store)
    store.save_profile(
        CompanyProfile(
            company_name="Norte Deportivo",
            activity="Suministro de redes para porterías",
            services=["redes para porterías"],
            sector="sports",
            specialty="goal_nets",
        ),
        data["revision"],
    )
    initial = client.get("/opportunities")
    assert "Buscar mis primeras oportunidades" in initial.text
    assert "Tu empresa está lista." in initial.text
    store.db.jobs.insert_one(
        {"_id": "previous", "installation_id": "nexolicit", "status": "failed"}
    )
    subsequent = client.get("/opportunities")
    assert "Tu radar está esperando información." in subsequent.text
    assert "Consultar novedades en SICOP" in subsequent.text


def test_revise_html_carries_draft_and_has_explicit_back_action(client, store):
    data = draft_data(client, store)
    draft = client.post("/discover/draft", data=data, headers=ORIGIN)
    fields = {
        name: form_value(draft, name)
        for name in (
            "csrf",
            "revision",
            "company_name",
            "sector",
            "specialty",
            "activity",
            "services",
            "coverage",
            "exclusions",
            "category",
        )
    }
    revised = client.post("/discover/revise", data=fields, headers=ORIGIN)
    assert form_value(revised, "draft_services") == fields["services"]
    assert form_value(revised, "draft_sector") == "sports"
    assert form_value(revised, "draft_specialty") == "goal_nets"
    assert 'formaction="/discover/revise"' in draft.text
    assert "profile" not in store.catalog()


def test_known_specialty_accepts_a_short_optional_detail(client, store):
    data = draft_data(client, store, activity="Oficinas")
    response = client.post("/discover/draft", data=data, headers=ORIGIN)
    assert response.status_code == 200
    assert "redes para arcos y porterías" in form_value(response, "activity")
    assert "Detalle: Oficinas" in form_value(response, "activity")
    assert "profile" not in store.catalog()
