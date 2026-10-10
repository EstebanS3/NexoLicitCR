"""Opt-in integration; never deletes an entire database."""

import json
import os
from pathlib import Path
from uuid import uuid4

import pytest

from nexolicitcr.config import Settings
from nexolicitcr.sicop import normalize
from nexolicitcr.storage import Store, connect, utcnow


@pytest.mark.integration
def test_real_atlas_transaction_and_reimport():
    if os.getenv("NEXO_TEST_ATLAS") != "1":
        pytest.skip("Set NEXO_TEST_ATLAS=1 and isolated NEXO_TEST_DATABASE to opt in")
    database_name = os.environ.get("NEXO_TEST_DATABASE", "")
    if not database_name.startswith("nexolicit_test_"):
        pytest.fail("NEXO_TEST_DATABASE must start with nexolicit_test_")
    cfg = Settings()
    data = json.loads((Path(__file__).parent / "fixtures/tender.json").read_text())
    tender = normalize(data["listing"], data["detail"], data["lines"], "servicios")
    tender = tender.model_copy(update={"source_id": str(uuid4().int)[:25]})
    with connect(cfg) as client:
        store = Store(client[database_name])
        store.ensure_indexes()
        try:
            assert store.save_tender(tender, utcnow()) == "changed"
            assert store.save_tender(tender, utcnow()) == "unchanged"
            assert store.db.tender_versions.count_documents({"key": tender.key}) == 1
            assert store.tender(tender.key)["payload"]["title"] == tender.title
        finally:
            store.db.tenders.delete_one({"_id": tender.key})
            store.db.tender_versions.delete_many({"key": tender.key})
