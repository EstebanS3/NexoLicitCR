"""Guided search scope and saved opportunity filters, using isolated Mongo fixtures."""

import pytest
from test_cache_matching import tender_payload
from test_discovery import ORIGIN, authenticated, profile_form


@pytest.mark.parametrize("limit", [10, 25, 100])
def test_guided_search_limit_is_part_of_idempotent_payload(client, store, limit):
    csrf = authenticated(client, store)
    assert (
        client.post("/discover/confirm", data=profile_form(csrf), headers=ORIGIN).status_code == 200
    )
    data = {"csrf": csrf, "revision": 1, "idempotency_key": "scoped-search", "limit": limit}

    first = client.post("/discover/search", data=data, headers=ORIGIN, follow_redirects=False)
    repeated = client.post("/discover/search", data=data, headers=ORIGIN, follow_redirects=False)
    assert first.status_code == repeated.status_code == 303
    assert first.headers["location"] == repeated.headers["location"]
    assert store.db.jobs.count_documents({}) == 1
    job = store.db.jobs.find_one()
    assert job["payload"]["limit"] == limit
    assert job["payload"]["category"] == "servicios"
    assert job["payload"]["profile_revision"] == 1

    changed = client.post(
        "/discover/search",
        data={**data, "limit": 100 if limit != 100 else 25},
        headers=ORIGIN,
        follow_redirects=False,
    )
    assert changed.status_code == 409
    assert store.db.jobs.count_documents({}) == 1
    assert store.db.jobs.find_one()["payload"] == job["payload"]


@pytest.mark.parametrize("limit", [0, 9, 101, 500, "invalid", "10.5"])
def test_invalid_guided_search_limit_does_not_enqueue(client, store, limit):
    csrf = authenticated(client, store)
    client.post("/discover/confirm", data=profile_form(csrf), headers=ORIGIN)
    result = client.post(
        "/discover/search",
        data={"csrf": csrf, "revision": 1, "idempotency_key": "invalid-scope", "limit": limit},
        headers=ORIGIN,
    )
    assert result.status_code == 422
    assert store.db.jobs.count_documents({}) == 0
    assert store.catalog()["revision"] == 1


def test_guided_search_default_agrees_with_radar_default(client, store):
    csrf = authenticated(client, store)
    client.post("/discover/confirm", data=profile_form(csrf), headers=ORIGIN)
    radar = client.get("/opportunities")
    assert radar.context["search_limit_default"] == 25
    assert radar.context["category"] == "all"
    result = client.post(
        "/discover/search",
        data={"csrf": csrf, "revision": 1, "idempotency_key": "default-scope"},
        headers=ORIGIN,
        follow_redirects=False,
    )
    assert result.status_code == 303
    assert store.db.jobs.find_one()["payload"]["limit"] == radar.context["search_limit_default"]


@pytest.mark.parametrize("category", ["all", "bienes", "servicios", "obras"])
def test_category_filters_saved_opportunities_without_changing_profile(client, store, category):
    csrf = authenticated(client, store)
    client.post("/discover/confirm", data=profile_form(csrf), headers=ORIGIN)
    before = store.catalog()
    for tender_category in ["bienes", "servicios", "obras"]:
        tender = tender_payload()
        tender.update(category=tender_category, title=f"Concurso de {tender_category}")
        store.db.tenders.insert_one(
            {"_id": tender_category, "payload": tender, "hash": tender_category}
        )

    result = client.get(
        "/opportunities", params={"category": category, "minimum": 0, "status": "all"}
    )
    assert result.status_code == 200
    expected = {"bienes", "servicios", "obras"} if category == "all" else {category}
    assert {row["key"] for row in result.context["rows"]} == expected
    assert result.context["total"] == len(expected)
    assert result.context["category"] == category
    assert store.catalog() == before
    assert store.db.jobs.count_documents({}) == 0


@pytest.mark.parametrize("category", ["", "unknown", "ALL", "servicio"])
def test_invalid_opportunity_category_is_rejected(client, store, category):
    authenticated(client, store)
    assert client.get("/opportunities", params={"category": category}).status_code == 422
    assert store.db.jobs.count_documents({}) == 0


def test_category_filter_precedes_pagination(client, store):
    authenticated(client, store)
    for index in range(28):
        category = "obras" if index < 26 else "servicios"
        tender = tender_payload()
        tender.update(category=category, title=f"Concurso {index:02d}")
        store.db.tenders.insert_one(
            {"_id": f"scope:{index:02d}", "payload": tender, "hash": str(index)}
        )
    result = client.get("/opportunities", params={"category": "obras", "status": "all", "page": 2})
    assert result.status_code == 200
    assert result.context["total"] == 26
    assert len(result.context["rows"]) == 1
    assert result.context["rows"][0]["tender"]["category"] == "obras"
