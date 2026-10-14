import pytest
from pydantic import ValidationError

from nexolicitcr.config import Settings


def build(settings, **updates):
    return Settings(_env_file=None, **(settings.model_dump() | updates))


@pytest.mark.parametrize(
    "uri",
    [
        "mongodb://localhost/",
        "mongodb+srv://cluster.example.mongodb.net/?tls=false",
        "mongodb+srv://user:secret@cluster.example.mongodb.net/",
        "mongodb+srv://cluster.example.mongodb.net/?tlsAllowInvalidCertificates=true",
    ],
)
def test_insecure_uri_rejected(settings, uri):
    with pytest.raises(ValidationError):
        build(settings, atlas_uri=uri)


def test_server_requires_https(settings):
    with pytest.raises(ValidationError):
        build(settings, app_mode="server")
    assert build(settings, app_mode="server", public_origin="https://nexo.example").secure_cookies


def test_secrets_hidden(settings):
    assert "test-only-password" not in repr(settings)
    with pytest.raises(ValidationError) as error:
        build(settings, atlas_uri="mongodb://secret-host/")
    assert "secret-host" not in str(error.value)


def local_settings(**updates):
    return Settings(
        _env_file=None,
        **{
            "mongo_mode": "local",
            "mongo_local_usuario": "local-user",
            "mongo_local_clave": "test-only-local-password",
        }
        | updates,
    )


def test_local_settings_without_atlas_credentials():
    cfg = local_settings()
    assert cfg.database_name == "nexolicit_local"
    assert not cfg.atlas_uri.get_secret_value()


@pytest.mark.parametrize(
    "uri",
    [
        "mongodb://external.example:27017/?replicaSet=nexo-local",
        "mongodb://127.0.0.1:27017,external.example:27017/?replicaSet=nexo-local",
        "mongodb://" + "user:secret@127.0.0.1:27017/?replicaSet=nexo-local",
        "mongodb://127.0.0.1:27017/",
        "mongodb://127.0.0.1:27017/?replicaSet=nexo-local&tls=false",
        "mongodb://127.0.0.1:27017/?replicaSet=nexo-local&replicaSet=other",
        "mongodb://127.0.0.1:27017/admin?replicaSet=nexo-local",
    ],
)
def test_local_remote_hosts_and_unsafe_options_rejected(uri):
    with pytest.raises(ValidationError):
        local_settings(mongo_local_uri=uri)


def test_local_mode_cannot_be_used_on_server():
    with pytest.raises(ValidationError):
        local_settings(app_mode="server", public_origin="https://nexo.example")
    with pytest.raises(ValidationError):
        local_settings(mongo_local_clave="")


def test_connection_separates_local_and_atlas(settings, monkeypatch):
    from nexolicitcr import storage

    calls = []
    monkeypatch.setattr(storage, "MongoClient", lambda *a, **k: calls.append((a, k)))
    storage.connect(settings)
    storage.connect(local_settings())
    assert calls[0][1]["tls"] is True
    assert calls[0][1]["username"] == "test-user"
    assert calls[1][1]["tls"] is False
    assert calls[1][1]["username"] == "local-user"
    assert calls[1][0][0].startswith("mongodb://127.0.0.1:")
