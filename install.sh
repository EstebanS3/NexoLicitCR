#!/usr/bin/env bash
# Ejecutar desde una copia o ZIP extraído del repositorio.
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ "${1:-}" == "--help" ]]; then
  echo 'Uso: bash install.sh [--skip-system] [--no-configure]'
  echo 'Instala Python/dependencias y prepara el inicio. Requiere internet.'
  exit 0
fi
SKIP_SYSTEM=0
CONFIGURE=1
for arg in "$@"; do
  case "$arg" in
    --skip-system) SKIP_SYSTEM=1 ;;
    --no-configure) CONFIGURE=0 ;;
    *) echo "Opción desconocida: $arg" >&2; exit 1 ;;
  esac
done
cd "$ROOT"
[[ -f uv.lock && -f scripts/easy_install.py ]] || { echo 'Extraé el ZIP completo del proyecto antes de instalar.' >&2; exit 1; }
if [[ "$SKIP_SYSTEM" == 0 ]]; then
  case "$(uname -s)" in
    Linux)
      command -v apt-get >/dev/null || { echo 'Soporte automático: Ubuntu/Debian. En otras distribuciones instalá curl, Tesseract (spa/osd) y Poppler; luego usá --skip-system.' >&2; exit 1; }
      SUDO=()
      if [[ "$EUID" != 0 ]]; then SUDO=(sudo); fi
      "${SUDO[@]}" apt-get update
      "${SUDO[@]}" apt-get install -y curl ca-certificates tesseract-ocr tesseract-ocr-spa tesseract-ocr-osd poppler-utils
      ;;
    Darwin)
      command -v brew >/dev/null || { echo 'Instalá Homebrew desde https://brew.sh y volvé a ejecutar este script.' >&2; exit 1; }
      brew install tesseract tesseract-lang poppler
      ;;
    *) echo 'Sistema no soportado por este script. Windows: install.ps1.' >&2; exit 1 ;;
  esac
fi
mkdir -p "$ROOT/var/installer/bin"
UV="$ROOT/var/installer/bin/uv"
if [[ ! -x "$UV" ]]; then
  curl --fail --location --retry 3 https://astral.sh/uv/0.12.24/install.sh -o "$ROOT/var/installer/uv-install.sh"
  UV_UNMANAGED_INSTALL="$ROOT/var/installer/bin" sh "$ROOT/var/installer/uv-install.sh"
fi
"$UV" sync --frozen --no-dev --python 3.12
.venv/bin/python scripts/easy_install.py check
if [[ "$CONFIGURE" == 1 ]]; then .venv/bin/python scripts/easy_install.py configure; fi
chmod +x start.sh start.command
printf '\nInstalación preparada. Iniciá con: bash "%s/start.sh"\n' "$ROOT"
