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
