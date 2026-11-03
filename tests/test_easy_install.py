"""Installer checks without network or real credentials."""

import errno
import importlib.util
import json
import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest

SPEC = importlib.util.spec_from_file_location(
    "easy_install", Path(__file__).resolve().parents[1] / "scripts" / "easy_install.py"
)
installer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installer)


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(os, "environ", os.environ.copy())
    monkeypatch.setattr(installer, "ROOT", tmp_path)
    monkeypatch.setattr(installer, "CONFIG", tmp_path / "var" / "installer" / "config.json")
    for key in list(os.environ):
        if key.startswith(("ATLAS_", "MONGO_", "APP_", "PUBLIC_", "REDIS_")):
            monkeypatch.delenv(key)
    return tmp_path


def test_config_round_trip_and_preservation(isolated, monkeypatch):
    values = iter(["mongodb+srv://example.mongodb.net/", "test-user", "test_database"])
    monkeypatch.setattr("builtins.input", lambda _: next(values))
    secret = "quotes'\" backslash\\ ${UNCHANGED} ñ"
    monkeypatch.setattr(installer.getpass, "getpass", lambda _: secret)
    installer.configure()
    original = installer.CONFIG.read_bytes()
    cfg = installer.load_config()
    assert cfg.atlas_clave.get_secret_value() == secret
    assert os.environ["ATLAS_CLAVE"] == secret
    installer.configure()
    assert installer.CONFIG.read_bytes() == original
    if os.name != "nt":
        assert installer.CONFIG.stat().st_mode & 0o777 == 0o600


def test_existing_env_is_never_replaced(isolated, monkeypatch):
    content = "ATLAS_URI=mongodb+srv://example.mongodb.net/\nATLAS_USUARIO=test-user\nATLAS_CLAVE=test-only\n"
    (isolated / ".env").write_text(content)
    monkeypatch.setattr("builtins.input", lambda _: pytest.fail("Unexpected prompt"))
    installer.configure()
    assert (isolated / ".env").read_text() == content
    assert not installer.CONFIG.exists()


def test_private_writer_refuses_overwrite(isolated):
    installer.private_json(installer.CONFIG, {"value": "original"})
    with pytest.raises(FileExistsError):
        installer.private_json(installer.CONFIG, {"value": "replacement"})
    assert json.loads(installer.CONFIG.read_text()) == {"value": "original"}


def test_invalid_input_does_not_create_config(isolated, monkeypatch):
    values = iter(["https://invalid.example", "user", "database"])
    monkeypatch.setattr("builtins.input", lambda _: next(values))
    monkeypatch.setattr(installer.getpass, "getpass", lambda _: "private-test")
    with pytest.raises(ValueError):
        installer.configure()
    assert not installer.CONFIG.exists()


def test_missing_poppler_fails_clearly(monkeypatch):
    monkeypatch.setattr(installer, "windows_paths", lambda: None)
    monkeypatch.setattr(installer.shutil, "which", lambda _: None)
    with pytest.raises(RuntimeError, match="Poppler"):
        installer.check()


def test_occupied_port_never_connects_to_database(isolated, monkeypatch):
    listener = MagicMock()
    listener.__enter__.return_value.bind.side_effect = OSError(errno.EADDRINUSE, "occupied")
    monkeypatch.setattr(installer.socket, "socket", lambda *args: listener)
    cfg = installer.Settings(
        _env_file=None,
        atlas_uri="mongodb+srv://example.mongodb.net/",
        atlas_usuario="test-user",
        atlas_clave="test-only",
        public_origin="http://localhost:8000",
    )
    monkeypatch.setattr(installer, "check", lambda: None)
    monkeypatch.setattr(installer, "configure", lambda: None)
    monkeypatch.setattr(installer, "load_config", lambda: cfg)
    monkeypatch.setattr(installer, "connect", lambda _: pytest.fail("Unexpected DB access"))
    with pytest.raises(RuntimeError, match="ocupado"):
        installer.run(no_browser=True)


@pytest.mark.parametrize("values", [{"PATH": "unexpected"}, {"ATLAS_CLAVE": 42}, []])
def test_invalid_config_never_changes_environment(isolated, values):
    installer.private_json(installer.CONFIG, values)
    before = dict(os.environ)
    with pytest.raises(RuntimeError):
        installer.load_config()
    assert dict(os.environ) == before


def test_invalid_atlas_config_never_changes_environment(isolated):
    installer.private_json(installer.CONFIG, {"ATLAS_URI": "invalid"})
    before = dict(os.environ)
    with pytest.raises(ValueError):
        installer.load_config()
    assert dict(os.environ) == before


def test_private_writer_validates_before_creating_file(isolated):
    with pytest.raises(TypeError):
        installer.private_json(installer.CONFIG, {"unsupported": object()})
    assert not installer.CONFIG.exists()
