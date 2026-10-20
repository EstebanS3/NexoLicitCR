from datetime import timedelta

import pytest
from test_cache_matching import MemoryRedis, tender_payload
from test_discovery import authenticated

from nexolicitcr.cache import OptionalCache
from nexolicitcr.jobs import JobQueue
from nexolicitcr.matching import Radar
from nexolicitcr.storage import utcnow
from nexolicitcr.web import cr_datetime


def saved_tender(store):
    payload = tender_payload()
    store.db.tenders.insert_one(
        {
            "_id": "test:00",
            "payload": payload,
            "hash": "v1",
            "observed_at": utcnow() - timedelta(days=2),
        }
    )


@pytest.mark.parametrize("state", ["failed", "omitted", "processing", "partial"])
def test_detail_and_radar_agree_when_another_document_is_incomplete(client, store, settings, state):
    authenticated(client, store)
    saved_tender(store)
    for identity, current_state in [("readable", "ready"), ("incomplete", state)]:
        store.db.documents.insert_one(
            {
                "_id": identity,
                "tender_key": "test:00",
                "source_identity": identity,
                "sha256": identity,
                "current": True,
                "state": current_state,
            }
        )
    store.db.extracted_pages.insert_one(
        {
            "document_id": "readable",
            "page": 1,
            "method": "digital",
            "text": "Servicio de soporte de redes",
            "error": None,
        }
    )
    assert Radar(store, OptionalCache(settings)).rows()[0]["match"]["preliminary"]
    assert "Evidencia documental pendiente" in client.get("/tenders/test:00").text
    store.db.documents.update_one({"_id": "incomplete"}, {"$set": {"current": False}})
    assert "Evidencia documental pendiente" not in client.get("/tenders/test:00").text


def test_identical_reimport_refreshes_observation_date_with_a_warm_match_cache(store, settings):
    saved_tender(store)
    radar = Radar(store, OptionalCache(settings, MemoryRedis()))
    before = radar.rows()[0]
    observed = utcnow()
    store.db.tenders.update_one({"_id": "test:00"}, {"$set": {"observed_at": observed}})
    after = radar.rows()[0]
    assert after["match"] == before["match"]
    assert after["observed_at"] > before["observed_at"]
    assert abs((after["observed_at"] - observed).total_seconds()) < 0.001


def test_radar_shows_successful_scope_and_subsequent_failure_without_hiding_saved_results(
    client, store, settings
):
    authenticated(client, store)
    saved_tender(store)
    queue = JobQueue(store, settings)
    success = queue.enqueue("servicios", 10, "", "success")
    success_at = utcnow() - timedelta(days=1)
    store.db.jobs.update_one(
        {"_id": success["_id"]},
        {"$set": {"status": "succeeded", "created_at": success_at, "updated_at": success_at}},
    )
    failed = queue.enqueue("obras", 25, "", "failure")
    store.db.jobs.update_one({"_id": failed["_id"]}, {"$set": {"status": "failed", "progress": 2}})
    # A newer job from a different installation must not alter the summary.
    foreign = queue.enqueue("all", 100, "", "foreign")
    store.db.jobs.update_one(
        {"_id": foreign["_id"]}, {"$set": {"installation_id": "other", "status": "succeeded"}}
    )
    response = client.get("/opportunities?status=all&minimum=0")
    assert response.status_code == 200
    assert "Última consulta exitosa" in response.text and cr_datetime(success_at) in response.text
    assert "hasta 10 recientes" in response.text and "hasta 100 recientes" not in response.text
    assert "La última consulta no se completó" in response.text
    assert "Actualización parcial" in response.text and "Conservamos 2" in response.text
    assert "Última verificación" in response.text and "/tenders/test:00" in response.text
    assert f"/jobs/{failed['_id']}/view" in response.text


@pytest.mark.parametrize("status", ["queued", "running", "retry_wait", "canceled"])
def test_radar_distinguishes_current_job_state_from_absence_of_results(
    client, store, settings, status
):
    authenticated(client, store)
    job = JobQueue(store, settings).enqueue("bienes", 10, "", "current")
    store.db.jobs.update_one({"_id": job["_id"]}, {"$set": {"status": status}})
    response = client.get("/opportunities")
    assert response.status_code == 200
    expected = (
        "Hay una consulta"
        if status in {"queued", "running"}
        else "La última consulta no se completó"
    )
    assert expected in response.text
    assert "Todavía no hay una consulta exitosa" in response.text


def test_saved_corpus_without_job_history_does_not_claim_a_successful_update(client, store):
    authenticated(client, store)
    saved_tender(store)
    response = client.get("/opportunities?status=all&minimum=0")
    assert "Todavía no hay una consulta exitosa" in response.text
    assert "Última verificación" in response.text
