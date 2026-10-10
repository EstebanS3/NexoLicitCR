import mongomock
import pytest
from fastapi.testclient import TestClient

from nexolicitcr.config import Settings
from nexolicitcr.security import PASSWORDS
from nexolicitcr.storage import Store
from nexolicitcr.web import create_app


@pytest.fixture
def settings():
    return Settings(
        _env_file=None,
        atlas_uri="mongodb+srv://cluster.example.mongodb.net/",
        atlas_usuario="test-user",
        atlas_clave="test-only-password",
        atlas_base="nexolicit_test",
    )


@pytest.fixture
def store():
    store = Store(mongomock.MongoClient(tz_aware=True).test_db)
    store.ensure_indexes()
    store.create_admin("admin", PASSWORDS.hash("test-password-for-fixtures"))
    return store


@pytest.fixture
def client(settings, store):
    with TestClient(create_app(settings, store), base_url="http://localhost:8000") as client:
        yield client
