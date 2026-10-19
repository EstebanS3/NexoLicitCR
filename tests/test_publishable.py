import runpy
import secrets
from pathlib import Path

audit = runpy.run_path(str(Path(__file__).resolve().parents[1] / "scripts/check_publishable.py"))


def test_detects_local_password_without_returning_its_value():
    secret = secrets.token_urlsafe(24)
    reason = audit["inspect_text"]("ATLAS_CLAVE=" + secret, "config.txt", {secret.casefold()})
    assert reason == "local secret or workstation identifier"
    assert secret not in reason


def test_detects_signed_urls_and_real_endpoints():
    signed_url = "https://storage.example.com/p/" + secrets.token_urlsafe(24) + "/file.pdf"
    assert audit["inspect_text"](signed_url, "report.md")
    host = "private-cluster" + ".mongodb.net"
    assert audit["inspect_text"](host, "config.txt") == "non-example Atlas endpoint"
    assert audit["inspect_text"]("mongodb+srv://cluster.example.mongodb.net/", "example") is None


def test_env_files_are_rejected_even_if_force_added_or_nested(tmp_path):
    folder = tmp_path / "nested"
    folder.mkdir()
    (folder / "atlas.env").write_text("configuration")
    (tmp_path / ".env.atlas").write_text("configuration")
    (tmp_path / ".env.atlas.example").write_text("ATLAS_CLAVE=\n")
    errors = audit["audit_paths"](
        tmp_path, ["nested/atlas.env", ".env.atlas", ".env.atlas.example"]
    )
    assert errors == [("nested/atlas.env", "environment file"), (".env.atlas", "environment file")]


def test_detects_workstation_names_without_hardcoding_this_computer():
    host = "private-" + secrets.token_hex(6)
    assert audit["inspect_text"]("host=" + host, "report.md", {host})
