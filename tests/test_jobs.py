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
