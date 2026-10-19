"""Adapt an existing Atlas env without printing secrets or changing the local .env."""

import argparse
import os
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from dotenv import dotenv_values
from dotenv.main import DotEnv

from nexolicitcr.config import Settings


def configure(source: Path, output: Path, database: str):
    values = dotenv_values(source, interpolate=False)
    uri = urlsplit(values.get("ATLAS_URI") or "")
    if not uri.scheme and values.get("ATLAS_HOST"):
        uri = urlsplit(f"mongodb+srv://{values['ATLAS_HOST']}/")
    if uri.username is not None or uri.password is not None:
        raise ValueError("El ejemplo debe separar usuario y contraseña de ATLAS_URI")
    # The source also specifies authSource in its URI. Settings takes it separately.
    query = dict(parse_qsl(uri.query, keep_blank_values=True))
    allowed = {"retrywrites", "w", "appname"}
    unsupported = {k for k in query if k.lower() not in allowed | {"authsource"}}
    if unsupported:
        raise ValueError("El ejemplo contiene opciones Atlas no admitidas")
    target = {
        "MONGO_MODE": "atlas",
        "ATLAS_URI": urlunsplit(
            (
                uri.scheme,
                uri.netloc,
                "/",
                urlencode({k: v for k, v in query.items() if k.lower() in allowed}),
                "",
            )
        ),
        "ATLAS_USUARIO": values.get("ATLAS_USUARIO") or "",
        "ATLAS_CLAVE": values.get("ATLAS_CLAVE") or "",
        "ATLAS_BASE": database,
        "ATLAS_AUTHDB": values.get("ATLAS_AUTHDB") or query.get("authSource") or "admin",
        "APP_MODE": "local",
        "PUBLIC_ORIGIN": "http://localhost:8000",
        "SICOP_TIMEZONE": "America/Costa_Rica",
        "INSTALLATION_ID": "nexolicit-docker",
        "ENVIRONMENT": "development",
        "MONGO_TIMEOUT_MS": "15000",
        "REDIS_URL": "",
    }
    Settings(_env_file=None, **{k.lower(): v for k, v in target.items()})
    # Single quotes protect dollar signs from Compose interpolation as well as dotenv.
    if any("\n" in v or "\r" in v or "'" in v for v in target.values()):
        raise ValueError("Este formato requiere valores sin saltos de línea ni comillas simples")
    content = "# Configuración privada de Atlas. No versionar.\n" + "".join(
        f"{key}='{value}'\n" for key, value in target.items()
    )
    # Verify the exact bytes that both dotenv and Compose will consume.
    import io

    parsed = DotEnv(None, stream=io.StringIO(content), interpolate=False).dict()
    if parsed != target:
        raise ValueError("No se pudo preservar la configuración")
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as stream:
        stream.write(content)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Archivo env del ejemplo que ya conecta a Atlas")
    parser.add_argument("--output", type=Path, default=Path(".env.atlas"))
    parser.add_argument("--database", default="nexolicit_docker")
    args = parser.parse_args()
    try:
        configure(args.source, args.output, args.database)
    except (OSError, ValueError):
        parser.exit(1, "No se creó la configuración: revisá el origen y que la salida no exista.\n")
    print("Configuración Atlas creada con permisos privados; no se mostraron credenciales.")


if __name__ == "__main__":
    main()
