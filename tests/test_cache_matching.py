import json
from datetime import timedelta
from pathlib import Path

from redis.exceptions import ConnectionError

from nexolicitcr.cache import OptionalCache
from nexolicitcr.config import Settings
from nexolicitcr.matching import Radar, deadline_status, score
from nexolicitcr.models import CatalogItem
from nexolicitcr.sicop import normalize
from nexolicitcr.storage import utcnow


class MemoryRedis:
    def __init__(self):
        self.data, self.calls, self.broken = {}, 0, False

    def get(self, key):
        self.calls += 1
        if self.broken:
            raise ConnectionError()
        return self.data.get(key)

    def set(self, key, value, ex):
        self.calls += 1
        if self.broken:
            raise ConnectionError()
        assert 5 <= ex <= 900
        self.data[key] = value


def tender_payload():
    data = json.loads((Path(__file__).parent / "fixtures/tender.json").read_text())
    return normalize(data["listing"], data["detail"], data["lines"], "servicios").model_dump(
        mode="json"
    )


def test_cache_namespace_isolates_apps_environments_installations_and_databases(settings):
    keys = set()
    for patch in [
        {},
        {"redis_namespace": "other"},
        {"environment": "test"},
        {"installation_id": "second"},
        {"atlas_base": "other_database"},
        {"atlas_uri": "mongodb+srv://other.example.mongodb.net/"},
    ]:
        cfg = Settings(_env_file=None, **settings.model_dump() | patch)
        keys.add(OptionalCache(cfg).key("radar", 1, 1, "v1", {}))
    assert len(keys) == 6
    cache = OptionalCache(settings)
    assert cache.key("radar", 1, 1, "v1", {}) != cache.key("radar", 2, 1, "v1", {})
    assert cache.key("radar", 1, 1, "v1", {}) != cache.key("radar", 1, 2, "v1", {})


def test_cache_breaker_and_recovery(settings):
    backend = MemoryRedis()
    clock = [0]
    cache = OptionalCache(settings, backend, clock=lambda: clock[0])
    cache.put("key", [1])
    assert cache.get("key") == [1]
    backend.broken = True
    assert cache.get("key") is None
    calls = backend.calls
    assert cache.get("key") is None
    cache.put("other", [])
    assert backend.calls == calls
    backend.broken = False
    clock[0] = 31
    assert cache.get("key") == [1]


def test_radar_cache_equivalence_invalidation_and_decisions(store, settings):
    tender = tender_payload()
    store.db.tenders.insert_one({"_id": "test:1", "payload": tender, "hash": "v1"})
    store.save_catalog_item(CatalogItem(name="Servicios", keywords=["soporte"]), 0)
    backend = MemoryRedis()
    cached = Radar(store, OptionalCache(settings, backend))
    uncached = Radar(store, OptionalCache(settings))
    assert cached.rows() == uncached.rows()
    cached.decide("test:1", "following", "No perder seguimiento")
    assert cached.rows()[0]["decision"]["status"] == "following"
    item = store.catalog()["items"][0]
    store.save_catalog_item(CatalogItem(name="Nuevo", keywords=["inexistente"]), 1, item["id"])
    assert cached.rows() == uncached.rows()
    backend.broken = True
    assert cached.rows() == uncached.rows()
    assert cached.rows()[0]["decision"]["note"] == "No perder seguimiento"


def test_expiration_computed_even_with_cached_rows():
    tender = tender_payload()
    tender["status"] = "open"
    tender["deadline"]["utc"] = (utcnow() - timedelta(seconds=1)).isoformat()
    assert deadline_status(tender) == "closed"
    tender["deadline"]["utc"] = None
    assert deadline_status(tender) == "unknown"


def test_matching_evidence_exclusions_and_code_system():
    tender = tender_payload()
    tender["title"] = "Soporte de redes y mantenimiento"
    item = CatalogItem(
        name="Redes", keywords=["redes"], exclusions=["mantenimiento"]
    ).model_dump() | {"id": "item"}
    result = score(tender, {"items": [item]})
    assert result["score"] == 0 and result["products"][0]["exclusions"]
    item["exclusions"] = ["prohibido"]
    pages = [{"text": "prohibido redes", "method": "ocr", "page": 1, "document_id": "doc"}]
    result = score(tender, {"items": [item]}, pages)
    assert result["score"] > 0 and result["products"][0]["review_required"]
    assert any(r["document_id"] == "doc" for r in result["products"][0]["reasons"])


def test_codes_only_match_same_classification_system():
    tender = tender_payload()
    tender["lines"][0]["product_code"] = "123456"
    item = CatalogItem(
        name="Producto",
        keywords=["no-coincide"],
        classification_system="CIIU",
        classification_code="123456",
    ).model_dump() | {"id": "item"}
    assert score(tender, {"items": [item]})["score"] == 0
    item["classification_system"] = "SICOP"
    assert score(tender, {"items": [item]})["score"] == 40


def test_corpus_change_invalidates_warm_cache(store, settings):
    tender = tender_payload()
    store.db.tenders.insert_one({"_id": "test:1", "payload": tender, "hash": "v1"})
    store.save_catalog_item(CatalogItem(name="Soporte", keywords=["soporte"]), 0)
    radar = Radar(store, OptionalCache(settings, MemoryRedis()))
    radar.decide("test:1", "following", "Revisar")
    before = radar.rows()
    store.db.tenders.update_one(
        {"_id": "test:1"}, {"$set": {"payload.status": "canceled", "hash": "v2"}}
    )
    store.db.metadata.update_one({"_id": "corpus"}, {"$inc": {"generation": 1}})
    after = radar.rows()
    assert after[0]["current_status"] == "canceled"
    assert after[0]["decision"] == before[0]["decision"]


def test_partial_ocr_keeps_match_preliminary():
    tender = tender_payload()
    pages = [{"text": "", "method": "ocr", "page": 1, "error": "OCR_FAILED_OR_UNAVAILABLE"}]
    assert score(tender, {"items": []}, pages)["preliminary"]
