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
from .sicop import RUBROS, SicopClient, SourceError, SourceRateLimited, source_date
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

    def enqueue(
        self, category, limit, since, idempotency_key, documents=False, profile_revision=None
    ):
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
            category=category,
            limit=limit,
            since=since,
            documents=documents,
            profile_revision=profile_revision,
        ).model_dump(exclude_none=True)
        return self._insert(payload, idempotency_key)

    def source_pause_until(self):
        row = self.collection.find_one(
            {"installation_id": self.scope, "source_retry_at": {"$gt": utcnow()}},
            {"source_retry_at": 1},
            sort=[("source_retry_at", -1)],
        )
        return row["source_retry_at"] if row else None

    def resume(self, job_id):
        previous = self.get(job_id)
        if not previous:
            raise LookupError("Consulta inexistente")
        if previous["status"] not in {"failed", "canceled"}:
            raise ValueError("Solo se pueden reanudar consultas interrumpidas")
        return self._insert(previous["payload"], f"resume:{job_id}", previous)

    def _insert(self, payload, idempotency_key, previous=None):
        identity = {"payload": payload, "resume_of": previous["_id"]} if previous else payload
        digest = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        checkpoints = sorted(set(previous.get("checkpoint", []))) if previous else []
        pending = (
            {
                error["identity"]: error
                for error in previous.get("errors", [])
                if error["identity"] not in checkpoints
            }
            if previous
            else {}
        )
        row = {
            "_id": uuid4().hex,
            "installation_id": self.scope,
            "idempotency_key": idempotency_key,
            "payload": payload,
            "payload_hash": digest,
            "status": "queued",
            "created_at": utcnow(),
            "updated_at": utcnow(),
            "next_attempt_at": self.source_pause_until() or utcnow(),
            "attempt": 0,
            "checkpoint": checkpoints,
            "progress": len(checkpoints),
            "errors": list(pending.values()),
            "cancel_requested": False,
        }
        if previous:
            row["resume_of"] = previous["_id"]
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

    def maintain(self):
        """Idempotent, scoped repairs. Never reclaim a valid lease or erase history."""
        now = utcnow()
        abandoned = {
            "status": "running",
            "$or": [{"lease_until": {"$lte": now}}, {"lease_until": None}],
        }
        available = {"$or": [{"status": {"$in": ["queued", "retry_wait"]}}, abandoned]}
        counts = {}

        def repair(name, filters, values):
            result = self.collection.update_many(
                {"installation_id": self.scope, **filters},
                {
                    "$set": {
                        **values,
                        "updated_at": now,
                        "maintenance_at": now,
                        "maintenance_action": name,
                    },
                    "$unset": {"owner": "", "lease_token": "", "lease_until": ""},
                },
            )
            counts[name] = result.modified_count

        # Cancellation takes precedence even when the retry budget is exhausted.
        repair(
            "canceled",
            {**available, "cancel_requested": True},
            {"status": "canceled", "error_code": None},
        )
        repair(
            "exhausted",
            {
                **available,
                "cancel_requested": {"$ne": True},
                "attempt": {"$gte": self.settings.job_max_attempts},
            },
            {"status": "failed", "error_code": "LEASE_EXHAUSTED"},
        )
        repair(
            "recovered",
            {
                **abandoned,
                "cancel_requested": {"$ne": True},
                "attempt": {"$lt": self.settings.job_max_attempts},
            },
            {"status": "retry_wait", "next_attempt_at": now, "error_code": "WORKER_INTERRUPTED"},
        )
        # Legacy/incomplete pending records must not wait forever without a date.
        repair(
            "scheduled",
            {"status": {"$in": ["queued", "retry_wait"]}, "next_attempt_at": None},
            {"next_attempt_at": now},
        )
        if any(counts.values()):
            LOG.info(json.dumps({"stage": "queue_maintenance", "counts": counts}))
        return counts

    def claim(self, owner, job_id=None):
        self.maintain()
        now = utcnow()
        if self.collection.find_one(
            {"installation_id": self.scope, "source_retry_at": {"$gt": now}}, {"_id": 1}
        ):
            return None
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

    def finish(self, job, status, error=None, retry_after=0):
        update = {"status": status, "updated_at": utcnow(), "error_code": error}
        if error == "SOURCE_RATE_LIMITED":
            update["source_retry_at"] = utcnow() + timedelta(seconds=retry_after)
        if status == "retry_wait":
            update["next_attempt_at"] = utcnow() + timedelta(
                seconds=max(retry_after, min(60, 2 ** job["attempt"]))
            )
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

    client = source or SicopClient(delay=queue.settings.sicop_request_delay_seconds)
    stop, lost = threading.Event(), threading.Event()

    def renew():
        while not stop.wait(queue.settings.job_lease_seconds / 3):
            try:
                queue.heartbeat(job)
                queue.maintain()
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
        pending = {category: {} for category in categories}
        for failure in job.get("errors", []):
            identity = failure.get("identity", "")
            if identity in job["checkpoint"]:
                continue
            parts = identity.split(":", 2)
            if len(parts) == 3 and parts[0] in pending:
                pending[parts[0]][identity] = {
                    "cartelNo": parts[1],
                    "cartelSeq": parts[2],
                    "_revisit": True,
                }
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

            def candidates(current_category, active_records):
                # Retry unfinished records before a moving listing can hide them.
                # These are prior work; recent and active scan limits stay unchanged.
                yield from chain(
                    pending[current_category].values(), islice(active_records, payload["limit"])
                )
                yield from client.listings(current_category)

            for listing in candidates(category, active):
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
                    except SourceRateLimited:
                        queue.collection.update_one(
                            queue.owned(job),
                            {
                                "$push": {
                                    "errors": {"identity": identity, "code": "SOURCE_RATE_LIMITED"}
                                }
                            },
                        )
                        raise
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
    except SourceRateLimited as exc:
        try:
            queue.finish(
                job,
                "retry_wait" if job["attempt"] < queue.settings.job_max_attempts else "failed",
                "SOURCE_RATE_LIMITED",
                retry_after=min(86400, max(exc.retry_after, 300 * 2 ** (job["attempt"] - 1))),
            )
        except (LeaseLost, PyMongoError):
            pass
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
