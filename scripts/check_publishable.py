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
    # Delivery v0.9.0: reviewed fictional UI, narrated recording and slide exports.
    "docs/assets/demo/00-acceso.png": "2fb5ef378ecd5355cf62a24404e5fd8b4197b65979079ec9b406e15b00d0931c",
    "docs/assets/demo/01-inicio.png": "a34e1197ae818a3eb85f111a9e891ef23d3c98a90fbedc89e8688dc26c995e96",
    "docs/assets/demo/02-perfil.png": "7585d248a6119a607aee8ae48e662aad5a0a9e647ce9acd5a6a918c854abe4e8",
    "docs/assets/demo/03-catalogo.png": "68ff579f84085e7fee8abe202d43b94d5834fc5a7ab8f75629bf3d6c113c8c37",
    "docs/assets/demo/04-radar.png": "ac12e2029c120b970c696acc6300ed44d9791d24929a84b13477a5d1731fdc06",
    "docs/assets/demo/05-detalle.png": "c3102f4a82b4c9a9f4b82dc35ad53f0cc318090d5899c1a008386719d947b7fb",
    "docs/assets/demo/06-documento.png": "65038a9cd162833a633c2e6370460f607bf1f7936c291282f3ea25dec930970a",
    "docs/assets/demo/07-seguimiento.png": "9d685f776e91b4f60c280d32e9b22225536edd385cf6ed9534fc9bc2750e57dc",
    "docs/assets/demo/08-actividad.png": "b7742e5bfce8cdf15c040ba80a723452332e635cd916cd095a9694c05ef955fb",
    "docs/assets/demo/09-filtros.png": "8053d269ce6614e6674ffe8a24a674602c9901699ad7b8beadbbebd4c971c5e4",
    "docs/assets/demo/10-decision.png": "f7f4f407052269e4dfd6577f3552387563d7c38a02d58e3cee42b4d51a8a78f3",
    "docs/assets/demo/11-resumen.png": "a78ae4f5808720a6dc58ecac94e408884e209e3a8ef15edf5d3e482755aba122",
    "docs/entrega/presentacion/NexoLicitCR_presentacion_final.pptx": "f08dba0c65d546478c36c386aaa72612a7f76e2c16d50aa41a67bc3a352aaf59",
    "docs/entrega/presentacion/NexoLicitCR_presentacion_final.pdf": "deb9acbfdf5070c2cfe046f7955cd72a6a1772346d4d2f4b8968e7a58e330745",
}


def local_private_values(root):
    """Compare local secrets in memory; never return them in findings or logs."""
    home = Path.home()
    values = {str(home), str(root), socket.gethostname()}
    # Generic CI/container accounts are also ordinary code identifiers. Their full
    # home paths remain private; only a distinct workstation username is matched bare.
    if home.name.casefold() not in {"runner", "root"}:
        values.add(home.name)
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
            text = path.read_text(encoding="utf-8")
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
