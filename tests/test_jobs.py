from datetime import timedelta

import pytest

from nexolicitcr.jobs import JobQueue, LeaseLost
from nexolicitcr.storage import utcnow


def test_idempotency_and_installation_isolation(store, settings):
    queue = JobQueue(store, settings)
    first = queue.enqueue("all", 10, "", "click-1")
    assert queue.enqueue("all", 10, "", "click-1")["_id"] == first["_id"]
    with pytest.raises(ValueError):
        queue.enqueue("all", 20, "", "click-1")
    other = JobQueue(store, settings.model_copy(update={"installation_id": "other"}))
    assert other.claim("worker") is None
    assert other.get(first["_id"]) is None


def test_expired_worker_cannot_publish_or_heartbeat(store, settings):
    queue = JobQueue(store, settings)
    queue.enqueue("bienes", 10, "", "lease")
    first = queue.claim("first")
    assert queue.claim("second") is None
    store.db.jobs.update_one(
        {"_id": first["_id"]}, {"$set": {"lease_until": utcnow() - timedelta(seconds=1)}}
    )
    second = queue.claim("second")
    assert second["attempt"] == 2 and second["lease_token"] != first["lease_token"]
    with pytest.raises(LeaseLost):
        queue.guard(first)
    with pytest.raises(LeaseLost):
        queue.finish(first, "succeeded")
    queue.heartbeat(second)
    queue.checkpoint(second, "record:1")
    queue.checkpoint(second, "record:1")
    assert queue.get(second["_id"])["progress"] == 1
    queue.finish(second, "succeeded")
    assert queue.get(second["_id"])["status"] == "succeeded"


def test_cancel_and_exhausted_lease(store, settings):
    queue = JobQueue(store, settings)
    pending = queue.enqueue("bienes", 10, "", "cancel")
    queue.cancel(pending["_id"])
    assert queue.claim("worker") is None
    assert queue.get(pending["_id"])["status"] == "canceled"
    queue.enqueue("bienes", 10, "", "final")
    job = queue.claim("worker")
    store.db.jobs.update_one(
        {"_id": job["_id"]},
        {
            "$set": {
                "attempt": settings.job_max_attempts,
                "lease_until": utcnow() - timedelta(seconds=1),
            }
        },
    )
    assert queue.claim("new") is None
    assert queue.get(job["_id"])["status"] == "failed"


def test_worker_revisits_active_and_resumes_failed_records(store, settings, monkeypatch):
    import json
    from pathlib import Path

    from nexolicitcr.jobs import execute
    from nexolicitcr.sicop import SourceError, normalize

    data = json.loads((Path(__file__).parent / "fixtures/tender.json").read_text())
    tender = normalize(data["listing"], data["detail"], data["lines"], "servicios")
    store.db.tenders.insert_one(
        {"_id": tender.key, "payload": tender.model_dump(mode="json"), "observed_at": utcnow()}
    )
    calls = []

    class Source:
        fail = True

        def listings(self, category):
            return [data["listing"]]

        def tender(self, listing, category, timezone):
            calls.append(listing)
            if self.fail:
                self.fail = False
                raise SourceError("temporary failure")
            return tender

    def save(value, observed, fence):
        fence()
        return "unchanged"

    monkeypatch.setattr(store, "save_tender", save)
    queue = JobQueue(store, settings)
    source = Source()
    job = queue.enqueue("servicios", 5, "2099-01-01", "resume")
    assert execute(queue, queue.claim("first"), source)["status"] == "retry_wait"
    assert not queue.get(job["_id"])["checkpoint"]
    store.db.jobs.update_one({"_id": job["_id"]}, {"$set": {"next_attempt_at": utcnow()}})
    result = execute(queue, queue.claim("second"), source)
    assert result["status"] == "succeeded" and result["progress"] == 1
    assert len(calls) == 2 and calls[0]["_revisit"]
    assert store.db.sync_runs.find_one({"_id": job["_id"]})["status"] == "succeeded"


@pytest.mark.parametrize("failure_persists", [False, True])
def test_retry_recovers_failed_record_after_listing_window_changes(
    store, settings, monkeypatch, failure_persists
):
    from test_cache_matching import tender_payload

    from nexolicitcr.jobs import execute
    from nexolicitcr.models import Tender
    from nexolicitcr.sicop import SourceError

    tender = Tender.model_validate(tender_payload())
    calls, saved = [], []

    class Source:
        scans = 0
        failed_once = False

        def listings(self, category):
            self.scans += 1
            keys = ["A", "B", "outside-limit"] if self.scans == 1 else ["A", "C", "outside-limit"]
            return [{"cartelNo": key, "cartelSeq": "00"} for key in keys]

        def tender(self, listing, category, timezone):
            key = listing["cartelNo"]
            calls.append((category, key))
            if key == "B" and (failure_persists or not self.failed_once):
                self.failed_once = True
                raise SourceError("temporary failure")
            return tender.model_copy(update={"source_id": key, "sequence": "00"})

    def save(value, observed, fence):
        fence()
        saved.append(value.source_id)

    monkeypatch.setattr(store, "save_tender", save)
    queue, source = JobQueue(store, settings), Source()
    job = queue.enqueue("servicios", 2, "", "changing-window")
    first = execute(queue, queue.claim("first"), source)
    assert first["status"] == "retry_wait"
    assert first["checkpoint"] == ["servicios:A:00"]
    store.db.jobs.update_one({"_id": job["_id"]}, {"$set": {"next_attempt_at": utcnow()}})
    second = execute(queue, queue.claim("second"), source)
    assert calls == [("servicios", "A"), ("servicios", "B"), ("servicios", "B"), ("servicios", "C")]
    assert second["status"] == ("retry_wait" if failure_persists else "succeeded")
    assert second["progress"] == (2 if failure_persists else 3)
    assert "outside-limit" not in saved
    if failure_persists:
        store.db.jobs.update_one({"_id": job["_id"]}, {"$set": {"next_attempt_at": utcnow()}})
        final = execute(queue, queue.claim("third"), source)
        assert final["status"] == "failed" and final["error_code"] == "SOURCE_PARTIAL"
        assert final["progress"] == 2
        assert calls.count(("servicios", "B")) == 3
        assert "servicios:B:00" not in final["checkpoint"]


def test_maintenance_repairs_orphans_preserves_progress_and_fences_owner(store, settings):
    queue = JobQueue(store, settings)
    queue.enqueue("servicios", 10, "", "orphan")
    old = queue.claim("dead-worker")
    queue.checkpoint(old, "saved:1")
    store.db.jobs.update_one({"_id": old["_id"]}, {"$unset": {"lease_until": ""}})
    assert queue.maintain()["recovered"] == 1
    assert not any(queue.maintain().values())
    repaired = queue.get(old["_id"])
    assert repaired["checkpoint"] == ["saved:1"] and repaired["progress"] == 1
    assert repaired["attempt"] == 1
    with pytest.raises(LeaseLost):
        queue.checkpoint(old, "stale:2")
    assert queue.claim("replacement")["attempt"] == 2


def test_maintenance_respects_live_leases_cancellation_scope_and_retry_budget(store, settings):
    queue = JobQueue(store, settings)
    live = queue.enqueue("all", 1, "", "live")
    queue.claim("live-worker")
    canceled = queue.enqueue("all", 1, "", "canceled")
    exhausted = queue.enqueue("all", 1, "", "exhausted")
    missing_date = queue.enqueue("all", 1, "", "date")
    other = JobQueue(store, settings.model_copy(update={"installation_id": "other"}))
    foreign = other.enqueue("all", 1, "", "foreign")
    for job in (canceled, exhausted, foreign):
        store.db.jobs.update_one(
            {"_id": job["_id"]}, {"$set": {"attempt": settings.job_max_attempts}}
        )
    queue.cancel(canceled["_id"])
    store.db.jobs.update_one({"_id": missing_date["_id"]}, {"$unset": {"next_attempt_at": ""}})
    assert queue.maintain() == {"canceled": 1, "exhausted": 1, "recovered": 0, "scheduled": 1}
    assert queue.get(live["_id"])["status"] == "running"
    assert other.get(foreign["_id"])["status"] == "queued"
    assert queue.get(canceled["_id"])["status"] == "canceled"
    assert queue.get(exhausted["_id"])["status"] == "failed"
    assert not any(queue.maintain().values())
    assert queue.claim("next")["_id"] == missing_date["_id"]


def test_rate_limit_pauses_installation_and_retains_pending_record(store, settings, monkeypatch):
    from test_cache_matching import tender_payload

    from nexolicitcr.jobs import execute
    from nexolicitcr.models import Tender
    from nexolicitcr.sicop import SourceRateLimited

    calls = []
    tender = Tender.model_validate(tender_payload())

    class Source:
        def listings(self, category):
            return [{"cartelNo": key, "cartelSeq": "00"} for key in ["A", "B", "C"]]

        def tender(self, listing, category, timezone):
            calls.append(listing["cartelNo"])
            if listing["cartelNo"] == "B":
                raise SourceRateLimited(300)
            return tender.model_copy(update={"source_id": listing["cartelNo"]})

    monkeypatch.setattr(store, "save_tender", lambda value, observed, fence: fence())
    queue = JobQueue(store, settings)
    queue.enqueue("bienes", 3, "", "limited")
    result = execute(queue, queue.claim("worker"), Source())
    assert result["status"] == "retry_wait"
    assert result["error_code"] == "SOURCE_RATE_LIMITED"
    assert result["checkpoint"] == ["bienes:A:00"]
    assert result["errors"] == [{"identity": "bienes:B:00", "code": "SOURCE_RATE_LIMITED"}]
    assert calls == ["A", "B"]
    assert result["next_attempt_at"] >= result["updated_at"] + timedelta(seconds=299)
    waiting = queue.enqueue("obras", 3, "", "another")
    assert waiting["next_attempt_at"] == result["source_retry_at"]
    assert queue.claim("worker") is None
    other = JobQueue(store, settings.model_copy(update={"installation_id": "other"}))
    other.enqueue("servicios", 3, "", "other")
    assert other.claim("other-worker") is not None
    store.db.jobs.update_one(
        {"_id": result["_id"]}, {"$set": {"source_retry_at": utcnow() - timedelta(seconds=1)}}
    )
    store.db.jobs.update_one(
        {"_id": waiting["_id"]}, {"$set": {"next_attempt_at": utcnow() - timedelta(seconds=1)}}
    )
    assert queue.claim("worker")["payload"]["category"] == "obras"


def test_resume_preserves_progress_filters_and_is_idempotent(store, settings):
    queue = JobQueue(store, settings)
    old = queue.enqueue("all", 50, "2026-01-01", "original", True, 7)
    store.db.jobs.update_one(
        {"_id": old["_id"]},
        {
            "$set": {
                "status": "failed",
                "checkpoint": ["bienes:A:00"],
                "progress": 1,
                "attempt": 3,
                "error_code": "SOURCE_RATE_LIMITED",
                "errors": [
                    {"identity": "bienes:A:00", "code": "SOURCE_INVALID"},
                    {"identity": "obras:B:00", "code": "SOURCE_RATE_LIMITED"},
                ],
                "source_retry_at": utcnow() + timedelta(minutes=5),
            }
        },
    )
    resumed = queue.resume(old["_id"])
    assert resumed["_id"] != old["_id"] and resumed["resume_of"] == old["_id"]
    assert resumed["payload"] == old["payload"]
    assert resumed["checkpoint"] == ["bienes:A:00"] and resumed["progress"] == 1
    assert resumed["errors"] == [{"identity": "obras:B:00", "code": "SOURCE_RATE_LIMITED"}]
    assert resumed["attempt"] == 0 and resumed["status"] == "queued"
    assert resumed["next_attempt_at"] > utcnow() + timedelta(minutes=4)
    assert queue.claim("worker") is None
    store.db.jobs.update_one({"_id": resumed["_id"]}, {"$set": {"progress": 2}})
    assert queue.resume(old["_id"])["progress"] == 2
    assert store.db.jobs.count_documents({"resume_of": old["_id"]}) == 1
    assert queue.get(old["_id"])["status"] == "failed"
    other = JobQueue(store, settings.model_copy(update={"installation_id": "other"}))
    with pytest.raises(LookupError):
        other.resume(old["_id"])


@pytest.mark.parametrize("status", ["queued", "running", "retry_wait", "succeeded"])
def test_resume_rejects_active_or_completed_jobs(store, settings, status):
    queue = JobQueue(store, settings)
    job = queue.enqueue("bienes", 5, "", "resume-state")
    store.db.jobs.update_one({"_id": job["_id"]}, {"$set": {"status": status}})
    with pytest.raises(ValueError):
        queue.resume(job["_id"])


def test_repeated_rate_limit_extends_wait(store, settings):
    from nexolicitcr.jobs import execute
    from nexolicitcr.sicop import SourceRateLimited

    class Source:
        def listings(self, category):
            raise SourceRateLimited(60)

    queue = JobQueue(store, settings)
    job = queue.enqueue("bienes", 5, "", "backoff")
    first = execute(queue, queue.claim("one"), Source())
    assert first["next_attempt_at"] >= first["updated_at"] + timedelta(seconds=299)
    store.db.jobs.update_one(
        {"_id": job["_id"]},
        {
            "$set": {
                "source_retry_at": utcnow() - timedelta(seconds=1),
                "next_attempt_at": utcnow() - timedelta(seconds=1),
            }
        },
    )
    second = execute(queue, queue.claim("two"), Source())
    assert second["next_attempt_at"] >= second["updated_at"] + timedelta(seconds=599)
