"""Opt-in MongoDB integration; never deletes an entire database."""

import json
import os
from pathlib import Path
from uuid import uuid4

import pytest

from nexolicitcr.config import Settings
from nexolicitcr.sicop import normalize
from nexolicitcr.storage import Store, connect, utcnow


@pytest.mark.integration
def test_real_mongo_transaction_and_reimport():
    local = os.getenv("NEXO_TEST_LOCAL") == "1"
    atlas = os.getenv("NEXO_TEST_ATLAS") == "1"
    if not local and not atlas:
        pytest.skip("Opt in with NEXO_TEST_LOCAL=1 or NEXO_TEST_ATLAS=1")
    if local and atlas:
        pytest.fail("Select only one MongoDB integration environment")
    database_name = os.environ.get("NEXO_TEST_DATABASE", "")
    if not database_name.startswith("nexolicit_test_"):
        pytest.fail("NEXO_TEST_DATABASE must start with nexolicit_test_")
    cfg = Settings()
    if cfg.mongo_mode != ("local" if local else "atlas"):
        pytest.fail("Integration opt-in does not match MONGO_MODE")
    data = json.loads((Path(__file__).parent / "fixtures/tender.json").read_text())
    tender = normalize(data["listing"], data["detail"], data["lines"], "servicios")
    tender = tender.model_copy(update={"source_id": str(uuid4().int)[:25]})
    with connect(cfg) as client:
        store = Store(client[database_name])
        store.ensure_indexes()
        marker = uuid4().hex
        # A real aborted transaction must leave neither collection partially written.
        with client.start_session() as session:
            with pytest.raises(RuntimeError, match="abort-test"):
                with session.start_transaction():
                    store.db.tenders.insert_one({"_id": marker}, session=session)
                    store.db.tender_versions.insert_one(
                        {"key": marker, "hash": marker}, session=session
                    )
                    raise RuntimeError("abort-test")
        assert store.db.tenders.find_one({"_id": marker}) is None
        assert store.db.tender_versions.find_one({"key": marker}) is None
        try:
            assert store.save_tender(tender, utcnow()) == "changed"
            assert store.save_tender(tender, utcnow()) == "unchanged"
            assert store.db.tender_versions.count_documents({"key": tender.key}) == 1
            assert store.tender(tender.key)["payload"]["title"] == tender.title
        finally:
            store.db.tenders.delete_one({"_id": tender.key})
            store.db.tender_versions.delete_many({"key": tender.key})
