import json
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path

import pytest
from pymongo.errors import DuplicateKeyError

from nexolicitcr.models import CatalogItem
from nexolicitcr.sicop import normalize
from nexolicitcr.storage import ConflictError, utcnow


def test_catalog_persistence_and_concurrent_edit(store):
    from nexolicitcr.storage import Store

    item = CatalogItem(name="Soporte", keywords=["redes"])
    key = store.save_catalog_item(item, 0)
    assert Store(store.db).catalog()["items"][0]["id"] == key
    with pytest.raises(ConflictError):
        store.save_catalog_item(item, 0)
    assert len(store.catalog()["items"]) == 1


def test_only_one_admin(store):
    with pytest.raises(DuplicateKeyError):
        store.create_admin("second", "hash")


def test_tender_idempotency_versions_and_stale_logic(store, monkeypatch):
    # Logic-only test. This fake does NOT verify MongoDB transaction guarantees.
    @contextmanager
    def fake_session():
        class Session:
            def with_transaction(self, callback, **kwargs):
                return callback(None)

        yield Session()

    monkeypatch.setattr(store.db.client, "start_session", fake_session)
    data = json.loads((Path(__file__).parent / "fixtures/tender.json").read_text())
    tender = normalize(data["listing"], data["detail"], data["lines"], "servicios")
    first = utcnow()
    assert store.save_tender(tender, first) == "changed"
    assert store.save_tender(tender, first + timedelta(seconds=1)) == "unchanged"
    changed = tender.model_copy(update={"title": "Modificado"})
    assert store.save_tender(changed, first + timedelta(seconds=2)) == "changed"
    assert store.save_tender(tender, first) == "stale"
    assert store.db.tenders.count_documents({}) == 1
    assert store.db.tender_versions.count_documents({}) == 2
    assert store.tender(tender.key)["payload"]["title"] == "Modificado"
