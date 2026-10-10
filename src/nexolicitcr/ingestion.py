from datetime import date, timedelta
from uuid import uuid4

from pydantic import ValidationError

from .sicop import AWARDS_MAX_DAYS, RUBROS, SourceError, source_date
from .storage import utcnow


def sync(store, client, categories, limit=20, since: date | None = None, timezone=""):
    """Bounded manual scan; no watermark that could hide updates to active tenders."""
    if not categories or any(x not in RUBROS for x in categories) or not 1 <= limit <= 500:
        raise ValueError("Alcance de sincronización inválido")
    run_id = uuid4().hex
    summary = {"seen": 0, "changed": 0, "unchanged": 0, "stale": 0, "errors": 0}
    store.db.sync_runs.insert_one(
        {
            "_id": run_id,
            "started_at": utcnow(),
            "status": "running",
            "categories": categories,
            "limit_per_category": limit,
            "since": str(since) if since else None,
        }
    )
    errors = []
    truncated = False
    try:
        for category in categories:
            processed = 0
            for listing in client.listings(category):
                summary["seen"] += 1
                try:
                    # Filtering never assumes globally descending order or breaks on old rows.
                    published = source_date(listing.get("regDt"), timezone)
                    if since and published.raw:
                        from datetime import datetime

                        if (
                            datetime.fromisoformat(published.raw.replace("Z", "+00:00")).date()
                            < since
                        ):
                            continue
                    observed = utcnow()
                    tender = client.tender(listing, category, timezone)
                    summary[store.save_tender(tender, observed)] += 1
                except (SourceError, ValidationError):
                    summary["errors"] += 1
                    errors.append(
                        {
                            "category": category,
                            "position": summary["seen"],
                            "code": "SOURCE_INVALID",
                        }
                    )
                processed += 1
                if processed >= limit:
                    truncated = True
                    break
        status = "partial" if summary["errors"] else "succeeded"
    except Exception:
        store.db.sync_runs.update_one(
            {"_id": run_id},
            {
                "$set": {
                    "status": "failed",
                    "ended_at": utcnow(),
                    "summary": summary,
                    "errors": errors,
                    "error_code": "SYNC_INTERRUPTED",
                }
            },
        )
        raise
    store.db.sync_runs.update_one(
        {"_id": run_id},
        {
            "$set": {
                "status": status,
                "ended_at": utcnow(),
                "summary": summary,
                "errors": errors,
                "bounded_scan": truncated,
            }
        },
    )
    return {"run_id": run_id, "status": status, "bounded_scan": truncated, **summary}


def windows(start: date, end: date, days=AWARDS_MAX_DAYS):
    """Ventanas contiguas y sin solapamiento que respetan el máximo de SICOP."""
    while start <= end:
        stop = min(start + timedelta(days=days), end)
        yield start, stop
        start = stop + timedelta(days=1)


def sync_awards(store, client, start: date, end: date):
    """Importar adjudicaciones por rango; una ventana fallida marca la corrida como fallida."""
    if start > end or end > date.today():
        raise ValueError("Rango de adjudicaciones inválido")
    run_id = uuid4().hex
    summary = {"seen": 0, "changed": 0, "unchanged": 0, "duplicates": 0, "rejected": 0}
    store.db.sync_runs.insert_one(
        {
            "_id": run_id,
            "kind": "awards",
            "started_at": utcnow(),
            "status": "running",
            "start": str(start),
            "end": str(end),
        }
    )
    try:
        for window_start, window_end in windows(start, end):
            awards, quality = client.awards(window_start, window_end)
            summary["seen"] += len(awards)
            for key in ("duplicates", "rejected"):
                summary[key] += quality[key]
            for key, value in store.save_awards(awards, utcnow()).items():
                summary[key] += value
        status = "partial" if summary["rejected"] else "succeeded"
    except Exception:
        store.db.sync_runs.update_one(
            {"_id": run_id},
            {
                "$set": {
                    "status": "failed",
                    "ended_at": utcnow(),
                    "summary": summary,
                    "error_code": "SYNC_INTERRUPTED",
                }
            },
        )
        raise
    store.db.sync_runs.update_one(
        {"_id": run_id},
        {"$set": {"status": status, "ended_at": utcnow(), "summary": summary}},
    )
    return {"run_id": run_id, "status": status, **summary}
