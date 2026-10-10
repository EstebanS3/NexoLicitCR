import json
from pathlib import Path

import pytest

from nexolicitcr.ingestion import sync
from nexolicitcr.sicop import SourceError, normalize


def test_partial_import_records_rejections(store, monkeypatch):
    data = json.loads((Path(__file__).parent / "fixtures/tender.json").read_text())

    class Client:
        def listings(self, category):
            return [data["listing"], data["listing"]]

        def tender(self, listing, category, timezone):
            if self.failed:
                return normalize(listing, data["detail"], data["lines"], category)
            self.failed = True
            raise SourceError("Bad detail")

        failed = False

    monkeypatch.setattr(store, "save_tender", lambda t, observed: "changed")
    result = sync(store, Client(), ["servicios"], limit=2)
    assert result["errors"] == 1 and result["changed"] == 1
    assert result["status"] == "partial"
    assert store.db.sync_runs.find_one()["errors"][0]["code"] == "SOURCE_INVALID"


def test_source_failure_marks_run_failed(store):
    class Client:
        def listings(self, category):
            raise SourceError("No service")

    with pytest.raises(SourceError):
        sync(store, Client(), ["bienes"])
    assert store.db.sync_runs.find_one()["status"] == "failed"
