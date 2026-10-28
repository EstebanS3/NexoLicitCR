#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
[[ -x .venv/bin/python ]] || { echo 'Primero ejecutá bash install.sh.' >&2; exit 1; }
exec .venv/bin/python scripts/easy_install.py run "$@"
