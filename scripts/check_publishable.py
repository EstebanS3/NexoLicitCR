"""Audit publishable files without displaying matching secrets or personal values."""

import hashlib
import re
import shutil
import socket
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
patterns = [
    re.compile(r"/(?:Users|home)/[^/\s]+/"),
    re.compile(r"/(?:private/)?var/folders/"),
    re.compile(r"[A-Za-z]:\\Users\\"),
    re.compile(r"mongodb(?:\+srv)?://[^\s/@:]+:[^\s/@]+@"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})"),
    re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    re.compile(r"https?://[^\s\"'<>]*/p/[A-Za-z0-9_-]{20,}/"),
    re.compile(r"[?&](?:X-Amz-Signature|X-Goog-Signature|access_token|api_key)=[^\s&\"']+", re.I),
]
atlas_hosts = re.compile(r"\b(?:[a-z0-9-]+\.)+mongodb\.net\b", re.I)
# Exact reviewed image bytes; changed or additional binaries require manual review.
reviewed_assets = {
    "docs/validacion/radar-escritorio.png": "6d17941c929139dd360b36a41bdb17f0e296cdbe2976cc601b04790c9cfce270",
    "docs/validacion/catalogo-movil.png": "69fcc86ce15f3b6b3a4b74f119361aec02080811c8355405b801c44b62016b11",
    "docs/validacion/acceso-invalido-movil.png": "644df89489b9933ad5f76a4134e458cbf06e40e765d2e84a9540d8450f500302",
    "docs/assets/mongodb-schema.png": "3878f364077ba6d5d32016652c794a06121850bc3dc1852cec37cd4c40f51bbe",
    "docs/assets/nexolicitcr-logo.png": "58ac82248b6e3a94511b63b4c10409682490d762deef013138c07b895531bfad",
}


def local_private_values(root):
    """Compare local secrets in memory; never return them in findings or logs."""
    values = {Path.home().name, str(Path.home()), str(root), socket.gethostname()}
    for path in root.glob(".env*"):
        if not path.is_file() or path.name.endswith(".example"):
            continue
        for key, value in dotenv_values(path, interpolate=False).items():
            if not value:
                continue
            if key.lower() == "atlas_usuario" or any(
                part in key.lower() for part in ("clave", "password", "secret", "token")
            ):
                values.add(value)
            if "uri" in key.lower():
                host = urlsplit(value).hostname
                if host and host.endswith(".mongodb.net"):
                    values.add(host)
    return {value.casefold() for value in values if len(value) > 4}


def inspect_text(text, name, private=()):
    if name in {"tests/test_config.py", "scripts/check_publishable.py"}:
        text = text.replace(
            "mongodb+srv://user:secret@cluster.example.mongodb.net/", "SYNTHETIC_TEST_URI"
        )
    if any(x.search(text) for x in patterns):
        return "possible private data or credential"
    if any(
        host != "example.mongodb.net" and not host.endswith(".example.mongodb.net")
        for host in atlas_hosts.findall(text)
    ):
        return "non-example Atlas endpoint"
    if any(
        re.search(r"(?<![a-z0-9_])" + re.escape(x) + r"(?![a-z0-9_])", text.casefold())
        for x in private
        if len(x) > 3
    ):
        return "local secret or workstation identifier"
    return None


def audit_paths(root, paths, private=()):
    errors = []
    for name in filter(None, paths):
        path = root / name
        if not path.is_file():
            continue
        if name == "LICENSE":
            # Preserve legal attribution; do not rewrite authors during a hygiene check.
            continue
        if (path.name.startswith(".env") or path.name.endswith(".env")) and not path.name.endswith(
            ".example"
        ):
            errors.append((name, "environment file"))
            continue
        try:
            text = path.read_text()
        except UnicodeDecodeError:
            if reviewed_assets.get(name) != hashlib.sha256(path.read_bytes()).hexdigest():
                errors.append((name, "binary requires manual review"))
            continue
        reason = inspect_text(text, name, private)
        if reason:
            errors.append((name, reason))
    return errors


def main():
    paths = (
        subprocess.check_output(  # noqa: S603 -- fixed read-only Git arguments
            [
                shutil.which("git") or "/usr/bin/git",
                "ls-files",
                "--cached",
                "--others",
                "--exclude-standard",
                "-z",
            ],
            cwd=ROOT,
        )
        .decode()
        .split("\0")
    )
    errors = audit_paths(ROOT, paths, local_private_values(ROOT))
    for name, reason in errors:
        print(f"REVIEW {name}: {reason}")
    if errors:
        return 1
    print(
        "Publishable files passed automated checks. Review legal attribution and commit identity manually."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
