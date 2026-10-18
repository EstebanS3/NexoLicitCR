"""Audit publishable files without displaying matching secrets or personal values."""

import hashlib
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
paths = (
    subprocess.check_output(  # noqa: S603 -- fixed read-only git arguments; no user command input
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
patterns = [
    re.compile(r"/(?:Users|home)/[^/\s]+/"),
    re.compile(r"/(?:private/)?var/folders/"),
    re.compile(r"[A-Za-z]:\\Users\\"),
    re.compile(r"mongodb(?:\+srv)?://[^\s/@:]+:[^\s/@]+@"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
]
# Derive private identifiers at runtime. Never hard-code the workstation identity.
private = [Path.home().name.casefold()]
# Exact reviewed image bytes; changed or additional binaries require manual review.
reviewed_assets = {
    "docs/validacion/radar-escritorio.png": "6d17941c929139dd360b36a41bdb17f0e296cdbe2976cc601b04790c9cfce270",
    "docs/validacion/catalogo-movil.png": "69fcc86ce15f3b6b3a4b74f119361aec02080811c8355405b801c44b62016b11",
    "docs/validacion/acceso-invalido-movil.png": "644df89489b9933ad5f76a4134e458cbf06e40e765d2e84a9540d8450f500302",
    "docs/assets/mongodb-schema.png": "3878f364077ba6d5d32016652c794a06121850bc3dc1852cec37cd4c40f51bbe",
    "docs/assets/nexolicitcr-logo.png": "58ac82248b6e3a94511b63b4c10409682490d762deef013138c07b895531bfad",
}
errors = []
for name in filter(None, paths):
    path = ROOT / name
    if not path.is_file():
        continue
    if name == "LICENSE":
        # Existing legal attribution is not replaced by an automated hygiene check.
        continue
    if name.startswith(".env") and not name.endswith(".example"):
        errors.append((name, "environment file"))
        continue
    try:
        text = path.read_text()
    except UnicodeDecodeError:
        if reviewed_assets.get(name) == hashlib.sha256(path.read_bytes()).hexdigest():
            continue
        errors.append((name, "binary requires manual review"))
        continue
    if name in {"tests/test_config.py", "scripts/check_publishable.py"}:
        text = text.replace(
            "mongodb+srv://user:secret@cluster.example.mongodb.net/", "SYNTHETIC_TEST_URI"
        )
    if any(x.search(text) for x in patterns) or any(
        re.search(r"(?<![a-z0-9_])" + re.escape(x) + r"(?![a-z0-9_])", text.casefold())
        for x in private
        if len(x) > 3
    ):
        errors.append((name, "possible private data"))
if errors:
    for name, reason in errors:
        print(f"REVIEW {name}: {reason}")
    raise SystemExit(1)
print(
    "Publishable files passed automated checks. Review legal attribution and commit identity manually."
)
