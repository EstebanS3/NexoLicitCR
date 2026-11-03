"""Asistente compartido por install.sh/install.ps1; no imprime credenciales."""

import argparse
import errno
import getpass
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import uuid
import webbrowser
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import urlopen

from nexolicitcr.config import Settings
from nexolicitcr.extractor import ocr_executable
from nexolicitcr.storage import Store, connect

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "var" / "installer"
CONFIG = PRIVATE / "config.json"


def private_json(path, values):
    content = json.dumps(values, ensure_ascii=False, indent=2)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        stream.write(content)


def load_config():
    # An existing .env is authoritative; never overwrite or import .env.atlas silently.
    if not (ROOT / ".env").exists() and CONFIG.exists():
        values = json.loads(CONFIG.read_text(encoding="utf-8"))
        allowed = {key.upper() for key in Settings.model_fields}
        if not isinstance(values, dict) or any(
            key not in allowed or not isinstance(value, str) for key, value in values.items()
        ):
            raise RuntimeError(
                "config.json debe contener solo opciones de la aplicación con valores de texto."
            )
        # Validate before mutating the environment inherited by the worker.
        Settings(_env_file=None, **{key.lower(): value for key, value in values.items()})
        os.environ.update(values)
    return Settings()


def configure():
    if (ROOT / ".env").exists() or CONFIG.exists():
        load_config()
        print("Configuración existente conservada.")
        return
    print("Usá una base exclusiva y autorizá tu IP en Atlas. La clave no se muestra.")
    values = {
        "MONGO_MODE": "atlas",
        "APP_MODE": "local",
        "ATLAS_URI": input("URI Atlas (mongodb+srv://cluster.mongodb.net/): ").strip(),
        "ATLAS_USUARIO": input("Usuario de base de datos Atlas: ").strip(),
        "ATLAS_CLAVE": getpass.getpass("Contraseña Atlas: "),
        "ATLAS_BASE": input("Base exclusiva [nexolicit_local]: ").strip() or "nexolicit_local",
        "PUBLIC_ORIGIN": "http://localhost:8000",
        "SICOP_TIMEZONE": "America/Costa_Rica",
        "INSTALLATION_ID": "nexo-" + uuid.uuid4().hex[:16],
        "REDIS_URL": "",
    }
    Settings(_env_file=None, **{key.lower(): value for key, value in values.items()})
    private_json(CONFIG, values)
    print("Configuración guardada en var/installer/config.json (privado; no subir a Git).")


def windows_paths():
    if os.name != "nt":
        return
    candidates = []
    for key in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
        if os.environ.get(key):
            candidates.append(Path(os.environ[key]) / "Tesseract-OCR")
    local = Path(os.environ["LOCALAPPDATA"])
    candidates.append(local / "Microsoft" / "WinGet" / "Links")
    packages = local / "Microsoft" / "WinGet" / "Packages"
    candidates.extend(p.parent for p in packages.glob("oschwartz10612.Poppler*/**/pdftoppm.exe"))
    os.environ["PATH"] = (
        os.pathsep.join(str(p) for p in candidates if p.is_dir())
        + os.pathsep
        + os.environ.get("PATH", "")
    )
    data = PRIVATE / "tessdata"
    if data.is_dir():
        os.environ["TESSDATA_PREFIX"] = str(data)


def windows_ocr():
    # Keep language files in the user's project, not in protected Program Files.
    data = PRIVATE / "tessdata"
    data.mkdir(parents=True, exist_ok=True)
    for lang in ("spa", "osd"):
        target = data / f"{lang}.traineddata"
        if not target.exists():
            url = f"https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/4.1.0/{lang}.traineddata"
            with urlopen(url, timeout=60) as response:  # noqa: S310 -- fixed HTTPS origin
                content = response.read()
            temp = target.with_suffix(".part")
            temp.write_bytes(content)
            temp.replace(target)
    windows_paths()


def check():
    windows_paths()
    if not shutil.which("pdftoppm"):
        raise RuntimeError("Falta Poppler (pdftoppm). Repetí el instalador o revisá PATH.")
    subprocess.run([shutil.which("pdftoppm"), "-v"], check=True, capture_output=True, timeout=10)  # noqa: S603
    ocr_executable.cache_clear()
    ocr_executable()
    print("OCR listo: Poppler y Tesseract con spa/osd.")


def open_when_ready(server, url):
    for _ in range(120):
        if server.should_exit:
            return
        if server.started:
            try:
                with urlopen(url + "/health/ready", timeout=2) as response:  # noqa: S310 -- validated loopback origin
                    if json.load(response).get("mongodb") == "available":
                        webbrowser.open(url)
                        return
            except (OSError, ValueError):
                pass
        time.sleep(0.5)
    print("No se abrió el navegador automáticamente. Revisá la terminal y abrí la URL indicada.")


def run(no_browser=False):
    import uvicorn

    from nexolicitcr.web import create_app

    check()
    configure()
    cfg = load_config()
    origin = urlsplit(cfg.public_origin)
    if (
        cfg.app_mode != "local"
        or origin.scheme != "http"
        or origin.hostname not in {"localhost", "127.0.0.1"}
    ):
        raise RuntimeError(
            "El lanzador requiere APP_MODE=local y PUBLIC_ORIGIN=http://localhost:PUERTO."
        )
    port = origin.port or 80
    if not 1024 <= port <= 65535:
        raise RuntimeError(
            "PUBLIC_ORIGIN requiere un puerto entre 1024 y 65535; por ejemplo http://localhost:8000."
        )
    # Reserve the port before starting the worker or opening a browser.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        try:
            listener.bind(("127.0.0.1", port))
        except OSError as exc:
            if exc.errno != errno.EADDRINUSE:
                raise RuntimeError(
                    f"No se pudo abrir el puerto {port}. Revisá permisos o restricciones de red locales."
                ) from None
            raise RuntimeError(
                f"El puerto {port} está ocupado. Cerrá la otra instancia o cambiá PUBLIC_ORIGIN."
            ) from None
        with connect(cfg) as client:
            store = Store(client[cfg.database_name])
            store.ping()
            store.ensure_indexes()
        app = create_app(cfg, with_worker=True)
        server = uvicorn.Server(
            uvicorn.Config(app, host="127.0.0.1", port=port, proxy_headers=False, access_log=False)
        )
        print(
            f"NexoLicitCR: {cfg.public_origin}\nMantené esta ventana abierta. Ctrl+C detiene web y worker."
        )
        if not no_browser:
            threading.Thread(
                target=open_when_ready, args=(server, cfg.public_origin), daemon=True
            ).start()
        server.run(sockets=[listener])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["configure", "check", "windows-ocr", "run"])
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    os.chdir(ROOT)
    try:
        if args.action == "run":
            run(args.no_browser)
        else:
            {"configure": configure, "check": check, "windows-ocr": windows_ocr}[args.action]()
    except KeyboardInterrupt:
        return 130
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception:
        # Settings, MongoDB and subprocess errors can contain private input.
        print(
            "No se completó la operación. Revisá configuración, internet, permisos y acceso/IP en Atlas. No se muestran credenciales.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
