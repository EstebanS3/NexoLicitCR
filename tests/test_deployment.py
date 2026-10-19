import json
import runpy
from io import BytesIO
from pathlib import Path
from urllib.error import URLError

import pytest
from dotenv import dotenv_values

from nexolicitcr import healthcheck

configure = runpy.run_path(str(Path(__file__).resolve().parents[1] / "scripts/configure_atlas.py"))[
    "configure"
]


def test_atlas_import_preserves_secrets_and_never_overwrites(tmp_path):
    source, target = tmp_path / "atlas.env", tmp_path / ".env.atlas"
    original = (
        "ATLAS_URI=mongodb+srv://cluster.example.mongodb.net/?retryWrites=true&authSource=admin\n"
        "ATLAS_USUARIO=test-user\nATLAS_CLAVE='test-$literal-password'\nATLAS_BASE=other_database\n"
    )
    source.write_text(original)
    configure(source, target, "nexolicit_test_import")
    loaded = dotenv_values(target, interpolate=False)
    assert loaded["ATLAS_CLAVE"] == "test-$literal-password"
    assert loaded["ATLAS_BASE"] == "nexolicit_test_import"
    assert "authSource" not in loaded["ATLAS_URI"]
    assert loaded["ATLAS_AUTHDB"] == "admin"
    assert target.stat().st_mode & 0o777 == 0o600
    assert source.read_text() == original
    with pytest.raises(FileExistsError):
        configure(source, target, "nexolicit_test_import")


def test_atlas_import_rejects_tls_bypass_before_writing(tmp_path):
    source, target = tmp_path / "atlas.env", tmp_path / ".env.atlas"
    source.write_text(
        "ATLAS_URI=mongodb+srv://cluster.example.mongodb.net/?tlsAllowInvalidCertificates=true\n"
        "ATLAS_USUARIO=test-user\nATLAS_CLAVE=test-password\n"
    )
    with pytest.raises(ValueError):
        configure(source, target, "nexolicit_test_import")
    assert not target.exists()


def test_container_healthcheck_uses_trusted_host_and_database_readiness(monkeypatch):
    monkeypatch.setenv("PUBLIC_ORIGIN", "https://nexo.example")
    requests = []

    def respond(request, timeout):
        requests.append(request)
        return BytesIO(json.dumps({"mongodb": "available"}).encode())

    monkeypatch.setattr(healthcheck, "urlopen", respond)
    assert healthcheck.main() == 0
    assert requests[0].full_url == "http://127.0.0.1:8000/health/ready"
    assert requests[0].get_header("Host") == "nexo.example"

    def fail(*args, **kwargs):
        raise URLError("unavailable")

    monkeypatch.setattr(healthcheck, "urlopen", fail)
    assert healthcheck.main() == 1
