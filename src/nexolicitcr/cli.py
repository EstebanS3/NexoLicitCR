import getpass
from datetime import date

import typer
from pydantic import ValidationError
from pymongo.errors import DuplicateKeyError, PyMongoError

from .config import Settings
from .ingestion import sync as synchronize
from .security import PASSWORDS, valid_username, validate_password
from .sicop import RUBROS, SicopClient, SourceError
from .storage import Store, connect

app = typer.Typer(help="NexoLicitCR: web, catálogo e ingesta de SICOP.")


def settings():
    try:
        return Settings()
    except (ValidationError, ValueError):
        typer.echo(
            "Configuración inválida. Revisá .env y .env.example; no se muestran valores.", err=True
        )
        raise typer.Exit(2) from None


def db_action(action):
    cfg = settings()
    try:
        with connect(cfg) as client:
            store = Store(client[cfg.database_name])
            store.ping()
            return action(store, cfg)
    except DuplicateKeyError:
        typer.echo("El registro ya existe; no se sobrescribió.", err=True)
        raise typer.Exit(1) from None
    except PyMongoError:
        typer.echo("MongoDB no disponible o sin permisos para la operación.", err=True)
        raise typer.Exit(1) from None


@app.command()
def init_db():
    """Crear índices de forma idempotente en la base configurada."""
    db_action(lambda store, cfg: store.ensure_indexes())
    typer.echo("Índices preparados.")


@app.command()
def create_admin():
    """Crear el único administrador sin contraseñas en argumentos o logs."""
    username = typer.prompt("Usuario").strip().lower()
    if not valid_username(username):
        typer.echo("Usuario inválido: 3–64 caracteres alfanuméricos, punto, guion o guion bajo.")
        raise typer.Exit(2)
    password = getpass.getpass("Contraseña (mínimo 14 caracteres): ")
    try:
        validate_password(password)
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(2) from None
    if password != getpass.getpass("Confirmar contraseña: "):
        typer.echo("Las contraseñas no coinciden.", err=True)
        raise typer.Exit(2)
    encoded = PASSWORDS.hash(password)
    db_action(lambda store, cfg: store.create_admin(username, encoded))
    typer.echo("Administrador creado.")


@app.command()
def api(port: int = typer.Option(8000, min=1024, max=65535)):
    """Iniciar web; server requiere TLS en un proxy de confianza."""
    import uvicorn

    from .web import create_app

    cfg = settings()
    uvicorn.run(
        create_app(cfg),
        host="127.0.0.1" if cfg.app_mode == "local" else "0.0.0.0",  # noqa: S104
        port=port,
        proxy_headers=False,
        access_log=False,
    )


@app.command()
def sync(
    category: str = typer.Option("bienes"),
    limit: int = typer.Option(20, min=1, max=500),
    since: str = typer.Option(""),
):
    """Corrida manual acotada. category=all consulta los tres rubros."""
    categories = list(RUBROS) if category == "all" else [category]
    if any(x not in RUBROS for x in categories):
        raise typer.BadParameter("Usá bienes, obras, servicios o all")
    try:
        start = date.fromisoformat(since) if since else None
    except ValueError:
        raise typer.BadParameter("since debe ser AAAA-MM-DD") from None

    def run(store, cfg):
        client = SicopClient()
        try:
            return synchronize(store, client, categories, limit, start, cfg.sicop_timezone)
        finally:
            client.close()

    try:
        result = db_action(run)
    except SourceError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from None
    typer.echo(
        f"Corrida {result['run_id']}: {result['status']}; "
        f"actualizados={result['changed']}, sin cambios={result['unchanged']}, "
        f"errores={result['errors']}. Consulta acotada por rubro."
    )
    if result["errors"]:
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
