"""Versioned relevance rules. Evidence is advisory, never a statement of eligibility."""

import re
import unicodedata
from datetime import datetime

from pydantic import ValidationError

from .models import Match, Tender
from .storage import ConflictError, utcnow

RULES_VERSION = "2026-10-v1"


def normalized(value):
    return " ".join(
        "".join(
            c for c in unicodedata.normalize("NFKD", value.lower()) if not unicodedata.combining(c)
        ).split()
    )


def contains(text, term):
    return bool(re.search(r"(?<!\w)" + re.escape(normalized(term)) + r"(?!\w)", normalized(text)))


def deadline_status(tender, now=None):
    now = now or utcnow()
    if tender["status"] in {"closed", "canceled"}:
        return tender["status"]
    value = tender["deadline"].get("utc")
    if not value:
        return "unknown"
    deadline = (
        datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value
    )
    if deadline.tzinfo is None:
        return "unknown"
    return "closed" if deadline <= now else tender["status"]


def score(tender, catalog, pages=()):
    evidence = [(tender["title"], "title", None, None, True, 35)]
    evidence += [
        (x["description"], "line", None, f"{x['lot']}/{x['number']}", True, 30)
        for x in tender["lines"]
    ]
    evidence += [
        (x["text"], x["method"], x.get("document_id"), x["page"], x["method"] == "digital", 15)
        for x in pages
    ]
    products = []
    for item in catalog["items"]:
        if not item["active"]:
            continue
        reasons, exclusions, review = [], [], False
        for text, method, document, page, reliable, weight in evidence:
            for term in item.get("exclusions", []):
                if contains(text, term):
                    if reliable:
                        exclusions.append(term)
                    else:
                        review = True
            for term in item.get("keywords", []) or [item["name"]]:
                if contains(text, term):
                    position = normalized(text).find(normalized(term))
                    reasons.append(
                        {
                            "term": term,
                            "method": method,
                            "document_id": document,
                            "page": page,
                            "fragment": text[max(0, position - 60) : position + 180],
                            "weight": weight,
                        }
                    )
        # Only exact, explicitly selected SICOP classification codes are comparable.
        if item.get("classification_system", "").upper() == "SICOP" and item.get(
            "classification_code"
        ):
            for line in tender["lines"]:
                if line.get("product_code") == item["classification_code"]:
                    reasons.append(
                        {
                            "term": item["classification_code"],
                            "method": "code",
                            "document_id": None,
                            "page": f"{line['lot']}/{line['number']}",
                            "fragment": line["description"][:240],
                            "weight": 40,
                        }
                    )
        points = min(
            100, sum({(r["method"], normalized(r["term"])): r["weight"] for r in reasons}.values())
        )
        if reasons or exclusions:
            products.append(
                {
                    "item_id": item["id"],
                    "item_name": item["name"],
                    "score": 0 if exclusions else points,
                    "reasons": reasons[:20],
                    "exclusions": sorted(set(exclusions)),
                    "review_required": review,
                }
            )
    return {
        "score": max((p["score"] for p in products), default=0),
        "products": products,
        "rules_version": RULES_VERSION,
        "preliminary": not bool(pages) or any(page.get("error") for page in pages),
    }


class Radar:
    def __init__(self, store, cache):
        self.store, self.cache = store, cache

    def version(self):
        from .discovery import matching_catalog

        catalog = matching_catalog(self.store.catalog())
        generation = (self.store.db.metadata.find_one({"_id": "corpus"}) or {}).get("generation", 0)
        return catalog, generation

    @staticmethod
    def valid_cached_rows(rows):
        if not isinstance(rows, list):
            return False
        try:
            for row in rows:
                if not isinstance(row, dict) or not isinstance(row.get("key"), str):
                    return False
                Tender.model_validate(row["tender"])
                Match.model_validate(row["match"])
        except (KeyError, TypeError, ValidationError):
            return False
        return True

    def rows(self):
        for _ in range(3):
            catalog, generation = self.version()
            key = self.cache.key("radar", catalog["revision"], generation, RULES_VERSION, {})
            rows = self.cache.get(key)
            if not self.valid_cached_rows(rows):
                rows = []
                for row in self.store.db.tenders.find({}).sort("_id", 1):
                    docs = list(
                        self.store.db.documents.find(
                            {
                                "tender_key": row["_id"],
                                "current": True,
                                "state": {"$in": ["ready", "partial"]},
                            }
                        )
                    )
                    pages = list(
                        self.store.db.extracted_pages.find(
                            {"document_id": {"$in": [d["_id"] for d in docs]}}
                        )
                    )
                    match = score(row["payload"], catalog, pages)
                    identity = {
                        "company": "company",
                        "catalog_revision": catalog["revision"],
                        "tender_key": row["_id"],
                        "tender_hash": row.get("hash", ""),
                        "rules_version": RULES_VERSION,
                        "document_generation": generation,
                    }
                    self.store.db.matches.update_one(
                        identity,
                        {"$set": {"result": match, "calculated_at": utcnow()}},
                        upsert=True,
                    )
                    rows.append({"key": row["_id"], "tender": row["payload"], "match": match})
                if (self.version()[0]["revision"], self.version()[1]) != (
                    catalog["revision"],
                    generation,
                ):
                    continue
                self.cache.put(key, rows)
            if (self.version()[0]["revision"], self.version()[1]) != (
                catalog["revision"],
                generation,
            ):
                continue
            decisions = {
                d["tender_key"]: d for d in self.store.db.decisions.find({"company": "company"})
            }
            for row in rows:
                row["current_status"] = deadline_status(row["tender"])
                row["decision"] = decisions.get(row["key"], {})
            return sorted(rows, key=lambda r: (-r["match"]["score"], r["key"]))
        raise ConflictError("Los datos cambiaron durante la consulta; recargá el radar.")

    def decide(self, key, status, note):
        if status not in {"relevant", "following", "discarded", "none"} or len(note) > 2000:
            raise ValueError("Decisión inválida")
        if not self.store.tender(key):
            raise ValueError("Concurso inexistente")
        self.store.db.decisions.update_one(
            {"company": "company", "tender_key": key},
            {"$set": {"status": status, "note": note, "updated_at": utcnow()}},
            upsert=True,
        )
