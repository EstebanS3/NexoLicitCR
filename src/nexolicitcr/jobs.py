"""Durable MongoDB jobs with installation scope and fenced, renewable leases."""

import hashlib
import json
import logging
import threading
from datetime import timedelta
from itertools import chain, islice
from uuid import uuid4

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError, PyMongoError

from .matching import deadline_status
from .models import JobPayload
from .sicop import RUBROS, SicopClient, SourceError, source_date
from .storage import utcnow

LOG = logging.getLogger(__name__)
TERMINAL = {"succeeded", "failed", "canceled"}


class LeaseLost(Exception):
    pass


class JobQueue:
    def __init__(self, store, settings):
        self.store, self.settings = store, settings
        self.collection = store.db.jobs
        self.scope = settings.installation_id

    def enqueue(self, category, limit, since, idempotency_key, documents=False):
        if (
            category not in {*RUBROS, "all"}
            or not 1 <= limit <= 500
            or not 1 <= len(idempotency_key) <= 128
        ):
            raise ValueError("Filtros de sincronización inválidos")
        from datetime import date

        if since:
            date.fromisoformat(since)
        payload = JobPayload(
            category=category, limit=limit, since=since, documents=documents
        ).model_dump()
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        row = {
            "_id": uuid4().hex,
            "installation_id": self.scope,
            "idempotency_key": idempotency_key,
            "payload": payload,
            "payload_hash": digest,
            "status": "queued",
            "created_at": utcnow(),
            "updated_at": utcnow(),
            "next_attempt_at": utcnow(),
            "attempt": 0,
            "checkpoint": [],
            "progress": 0,
            "errors": [],
            "cancel_requested": False,
        }
        try:
            self.collection.insert_one(row)
            return row
        except DuplicateKeyError:
            existing = self.collection.find_one(
                {"installation_id": self.scope, "idempotency_key": idempotency_key}
            )
            if existing["payload_hash"] != digest:
                raise ValueError("La clave de idempotencia ya se usó con otros filtros") from None
            return existing

    def get(self, job_id):
        return self.collection.find_one({"_id": job_id, "installation_id": self.scope})

    def claim(self, owner, job_id=None):
        now = utcnow()
        # Expired final attempts are terminal, never left running forever.
        self.collection.update_many(
            {
                "installation_id": self.scope,
                "status": "running",
                "lease_until": {"$lte": now},
                "attempt": {"$gte": self.settings.job_max_attempts},
            },
            {"$set": {"status": "failed", "error_code": "LEASE_EXHAUSTED", "updated_at": now}},
        )
        self.collection.update_many(
            {
                "installation_id": self.scope,
                "cancel_requested": True,
                "$or": [
                    {"status": {"$in": ["queued", "retry_wait"]}},
                    {"status": "running", "lease_until": {"$lte": now}},
                ],
            },
            {"$set": {"status": "canceled", "updated_at": now}},
        )
        filters = {
            "installation_id": self.scope,
            "cancel_requested": False,
            "attempt": {"$lt": self.settings.job_max_attempts},
            "$or": [
                {"status": {"$in": ["queued", "retry_wait"]}, "next_attempt_at": {"$lte": now}},
                {"status": "running", "lease_until": {"$lte": now}},
            ],
        }
        if job_id:
            filters["_id"] = job_id
        return self.collection.find_one_and_update(
            filters,
            {
                "$set": {
                    "status": "running",
                    "owner": owner,
                    "lease_token": uuid4().hex,
                    "lease_until": now + timedelta(seconds=self.settings.job_lease_seconds),
                    "heartbeat_at": now,
                    "updated_at": now,
                },
                "$inc": {"attempt": 1},
            },
            sort=[("created_at", 1)],
            return_document=ReturnDocument.AFTER,
        )

    def owned(self, job):
        return {
            "_id": job["_id"],
            "installation_id": self.scope,
            "status": "running",
            "lease_token": job["lease_token"],
            "lease_until": {"$gt": utcnow()},
            "cancel_requested": False,
        }

    def guard(self, job, session=None):
        # This write inside the tender transaction is a fencing barrier.
        result = self.collection.update_one(
            self.owned(job), {"$inc": {"fence": 1}}, session=session
        )
        if result.matched_count != 1:
            raise LeaseLost()

    def heartbeat(self, job):
        now = utcnow()
        result = self.collection.update_one(
            self.owned(job),
            {
                "$set": {
                    "heartbeat_at": now,
                    "lease_until": now + timedelta(seconds=self.settings.job_lease_seconds),
                }
            },
        )
        if result.matched_count != 1:
            raise LeaseLost()

    def checkpoint(self, job, identity, error=None):
        update = {
            "$addToSet": {"checkpoint": identity},
            "$inc": {"progress": 1},
            "$set": {"updated_at": utcnow()},
        }
        if error:
            update["$push"] = {"errors": {"identity": identity, "code": error}}
        filters = self.owned(job) | {"checkpoint": {"$ne": identity}}
        if not self.collection.update_one(filters, update).matched_count:
            self.guard(job)

    def finish(self, job, status, error=None):
        update = {"status": status, "updated_at": utcnow(), "error_code": error}
        if status == "retry_wait":
            update["next_attempt_at"] = utcnow() + timedelta(seconds=min(60, 2 ** job["attempt"]))
        if not self.collection.update_one(
            self.owned(job), {"$set": update, "$unset": {"lease_token": "", "lease_until": ""}}
        ).matched_count:
            raise LeaseLost()

    def cancel(self, job_id):
        return self.collection.update_one(
            {"_id": job_id, "installation_id": self.scope, "status": {"$nin": list(TERMINAL)}},
            {"$set": {"cancel_requested": True, "updated_at": utcnow()}},
        ).matched_count

    def acknowledge_cancel(self, job):
        self.collection.update_one(
            {
                "_id": job["_id"],
                "installation_id": self.scope,
                "lease_token": job["lease_token"],
                "status": "running",
                "lease_until": {"$gt": utcnow()},
                "cancel_requested": True,
            },
            {"$set": {"status": "canceled", "updated_at": utcnow()}},
        )


def execute(queue, job, source=None):
    """Bounded scan with record checkpoints. Retry failed records, never skip them."""
    from pydantic import ValidationError

    from .documents import DocumentService

    client = source or SicopClient()
    stop, lost = threading.Event(), threading.Event()

    def renew():
        while not stop.wait(queue.settings.job_lease_seconds / 3):
            try:
                queue.heartbeat(job)
            except (LeaseLost, PyMongoError):
                lost.set()
                return

    def guard(session=None):
        if lost.is_set():
            raise LeaseLost()
        queue.guard(job, session)

    heartbeat = threading.Thread(target=renew, daemon=True)
    heartbeat.start()
    errors = 0
    try:
        payload = job["payload"]
        categories = list(RUBROS) if payload["category"] == "all" else [payload["category"]]
        for category in categories:
            processed = 0
            # Revisit oldest active/unknown records even outside the recent listing window.
            active = (
                {
                    "cartelNo": row["payload"]["source_id"],
                    "cartelSeq": row["payload"]["sequence"],
                    "_revisit": True,
                }
                for row in queue.store.db.tenders.find({"payload.category": category}).sort(
                    "observed_at", 1
                )
                if deadline_status(row["payload"]) not in {"closed", "canceled"}
            )
            seen = set()
            for listing in chain(islice(active, payload["limit"]), client.listings(category)):
                guard()
                published = source_date(listing.get("regDt"), queue.settings.sicop_timezone)
                if (
                    not listing.get("_revisit")
                    and payload["since"]
                    and published.raw
                    and published.raw[:10] < payload["since"]
                ):
                    continue
                identity = f"{category}:{listing.get('cartelNo')}:{listing.get('cartelSeq')}"
                if identity in seen:
                    continue
                seen.add(identity)
                if not listing.get("_revisit"):
                    processed += 1
                if identity not in job["checkpoint"]:
                    try:
                        tender = client.tender(listing, category, queue.settings.sicop_timezone)
                        queue.store.save_tender(tender, utcnow(), fence=guard)
                        if payload["documents"]:
                            guard()
                            states = DocumentService(queue.store, queue.settings).ingest_tender(
                                tender, guard
                            )
                            if any(state in {"failed", "partial"} for state in states):
                                raise SourceError("DOCUMENTS_PARTIAL")
                        queue.checkpoint(job, identity)
                    except (SourceError, ValidationError):
                        errors += 1
                        queue.collection.update_one(
                            queue.owned(job),
                            {"$push": {"errors": {"identity": identity, "code": "SOURCE_INVALID"}}},
                        )
                if processed >= payload["limit"]:
                    break
        guard()
        if errors:
            queue.finish(
                job,
                "retry_wait" if job["attempt"] < queue.settings.job_max_attempts else "failed",
                "SOURCE_PARTIAL",
            )
        else:
            queue.finish(job, "succeeded")
        LOG.info(json.dumps({"job_id": job["_id"], "stage": "complete", "errors": errors}))
    except LeaseLost:
        queue.acknowledge_cancel(job)
    except (SourceError, PyMongoError):
        try:
            queue.finish(
                job,
                "retry_wait" if job["attempt"] < queue.settings.job_max_attempts else "failed",
                "DEPENDENCY_UNAVAILABLE",
            )
        except (LeaseLost, PyMongoError):
            pass  # Lease recovery remains durable if MongoDB is unavailable.
    finally:
        stop.set()
        heartbeat.join(timeout=1)
        if source is None:
            client.close()
    result = queue.get(job["_id"])
    if result and result["status"] in TERMINAL:
        queue.store.db.sync_runs.update_one(
            {"_id": job["_id"]},
            {
                "$set": {
                    "job_id": job["_id"],
                    "status": result["status"],
                    "progress": result["progress"],
                    "errors": result["errors"],
                    "finished_at": result["updated_at"],
                }
            },
            upsert=True,
        )
    return result
