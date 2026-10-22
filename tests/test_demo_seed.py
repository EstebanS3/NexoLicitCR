"""The demo must be isolated, repeatable and explicitly disconnected from SICOP."""

import importlib.util
import io
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

import gridfs
import mongomock
import pytest
from fastapi.testclient import TestClient
from mongomock.gridfs import enable_gridfs_integration
from pypdf import PdfReader

from nexolicitcr.config import Settings
from nexolicitcr.discovery import matching_catalog
from nexolicitcr.matching import deadline_status, tender_match
from nexolicitcr.security import check_password
from nexolicitcr.storage import Store

spec = importlib.util.spec_from_file_location(
    "demo_seed", Path(__file__).resolve().parents[1] / "scripts/prepare_demo.py"
)
demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo)


@pytest.fixture
def demo_settings():
    return Settings(
        _env_file=None,
        mongo_mode="local",
        mongo_local_uri=demo.REPLICA_URI,
        mongo_local_usuario="example-demo",
        mongo_local_clave="fixture-password-only",
        mongo_local_base=demo.DATABASE,
        app_mode="local",
        public_origin="http://localhost:8010",
        installation_id="nexolicit-demo-v090",
        redis_url="",
    )


@pytest.fixture
def demo_store(monkeypatch):
    enable_gridfs_integration()
    client = mongomock.MongoClient(tz_aware=True)

    @contextmanager
    def session():
        class Transaction:
            def with_transaction(self, callback, **kwargs):
                return callback(None)

        yield Transaction()

    monkeypatch.setattr(client, "start_session", session)
    return Store(client[demo.DATABASE])


def test_seed_is_repeatable_and_contains_real_pdf_evidence(demo_store, demo_settings):
    access = {"username": "demo.fixture", "password": "fictional-test-password-only"}
    anchor = datetime(2035, 1, 10, 18, tzinfo=UTC)
    first = demo.seed_database(demo_store, demo_settings, access, anchor=anchor)
    password_hash = demo_store.user(access["username"])["password_hash"]
    counts = {
        name: demo_store.db[name].count_documents({})
        for name in demo_store.db.list_collection_names()
    }
    second = demo.seed_database(
        demo_store, demo_settings, access, anchor=datetime(2040, 1, 1, tzinfo=UTC)
    )
    assert first == second
    assert {name: demo_store.db[name].count_documents({}) for name in counts} == counts
    assert counts["tenders"] == 5
    assert counts["documents"] == counts["fs.files"] == 3
    assert demo_store.user(access["username"])["password_hash"] == password_hash
    assert check_password(access["password"], password_hash)[0]
    main = demo_store.tender("99900000001:00")
    assert main["source_url"] == "#demo-ficticia"
    match = tender_match(
        demo_store, main["_id"], main["payload"], matching_catalog(demo_store.catalog())
    )
    assert match["score"] > 0 and not match["preliminary"]
    assert any(
        reason["method"] == "code" for item in match["products"] for reason in item["reasons"]
    )
    assert any(
        reason["method"] == "digital" for item in match["products"] for reason in item["reasons"]
    )
    partial = demo_store.tender("99900000003:00")
    assert tender_match(
        demo_store, partial["_id"], partial["payload"], matching_catalog(demo_store.catalog())
    )["preliminary"]
    expired = demo_store.tender("99900000004:00")
    assert deadline_status(expired["payload"], now=anchor) == "closed"
    for document in demo_store.db.documents.find():
        payload = gridfs.GridFS(demo_store.db).get(document["gridfs_id"]).read()
        assert "ESCENARIO FICTICIO" in PdfReader(io.BytesIO(payload)).pages[0].extract_text()


def test_seed_rejects_foreign_database_without_writing(demo_settings):
    foreign = Store(mongomock.MongoClient().nexolicit_local)
    foreign.db.catalog.insert_one({"_id": "company", "private": "untouched"})
    with pytest.raises(ValueError, match="no apunta"):
        demo.seed_database(foreign, demo_settings, {})
    assert foreign.db.list_collection_names() == ["catalog"]
    assert foreign.db.catalog.find_one()["private"] == "untouched"


def test_seed_preserves_unowned_database(demo_store, demo_settings):
    demo_store.db.users.insert_one({"_id": "existing"})
    with pytest.raises(ValueError, match="sin marcador"):
        demo.seed_database(demo_store, demo_settings, {})
    assert demo_store.db.list_collection_names() == ["users"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("mongo_local_base", "nexolicit_local"),
        ("mongo_local_uri", "mongodb://127.0.0.1:27017/?replicaSet=nexo-local"),
        ("public_origin", "http://localhost:8000"),
        ("redis_url", "redis://localhost:6379/0"),
    ],
)
def test_demo_configuration_cannot_target_existing_services(demo_settings, field, value):
    from pydantic import SecretStr

    if field in {"mongo_local_uri", "redis_url"}:
        value = SecretStr(value)
    with pytest.raises(ValueError, match="aislados"):
        demo.validate_settings(demo_settings.model_copy(update={field: value}))


def test_demo_banner_and_external_actions_disabled(demo_settings, demo_store, monkeypatch):
    monkeypatch.setattr("nexolicitcr.web.connect", lambda settings: demo_store.db.client)
    demo_store.ensure_indexes()
    with TestClient(demo.demo_app(demo_settings), base_url="http://localhost:8010") as client:
        page = client.get("/login")
        assert "DEMO LOCAL" in page.text
        assert "Sin conexión a SICOP" in page.text
        for path in ("/sync-runs", "/discover/search", "/onboarding/sync", "/jobs/example/resume"):
            response = client.post(path, headers={"origin": "http://localhost:8010"})
            assert response.status_code == 409
            assert "consultas externas están desactivadas" in response.text
        assert demo_store.db.jobs.count_documents({}) == 0
