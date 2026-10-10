"""Audit publishable files without displaying matching secrets or personal values."""

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
        errors.append((name, "binary requires manual review"))
        continue
    if name in {"tests/test_config.py", "scripts/check_publishable.py"}:
        text = text.replace(
            "mongodb+srv://user:secret@cluster.example.mongodb.net/", "SYNTHETIC_TEST_URI"
        )
    if any(x.search(text) for x in patterns) or any(
        x in text.casefold() for x in private if len(x) > 3
    ):
        errors.append((name, "possible private data"))
if errors:
    for name, reason in errors:
        print(f"REVIEW {name}: {reason}")
    raise SystemExit(1)
print(
    "Publishable files passed automated checks. Review legal attribution and commit identity manually."
)
