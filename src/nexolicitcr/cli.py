import getpass

import typer
from pydantic import ValidationError
from pymongo.errors import DuplicateKeyError, PyMongoError

from .config import Settings
from .security import PASSWORDS, valid_username, validate_password
from .sicop import SourceError
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
    once: bool = typer.Option(False, "--once"),
    documents: bool = typer.Option(False, "--documents"),
):
    """Crear un job durable; --once procesa un intento en este proceso."""
    from uuid import uuid4

    from .jobs import JobQueue, execute

    def run(store, cfg):
        queue = JobQueue(store, cfg)
        try:
            job = queue.enqueue(category, limit, since, uuid4().hex, documents)
        except ValueError as exc:
            raise typer.BadParameter(str(exc)) from None
        typer.echo(f"Job: {job['_id']}")
        if once:
            claimed = queue.claim("cli", job["_id"])
            if claimed:
                job = execute(queue, claimed)
            else:
                job = queue.get(job["_id"])
            typer.echo(f"Estado: {job['status']}")
            if job["status"] != "succeeded":
                raise typer.Exit(1)

    db_action(run)


@app.command()
def worker(once: bool = typer.Option(False, "--once")):
    """Procesar jobs de INSTALLATION_ID; Ctrl+C termina sin perder la cola."""
    import logging
    import time
    from uuid import uuid4

    from .jobs import JobQueue, execute

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    def run(store, cfg):
        queue, owner = JobQueue(store, cfg), uuid4().hex
        try:
            while True:
                job = queue.claim(owner)
                result = execute(queue, job) if job else None
                if once:
                    if result and result["status"] != "succeeded":
                        raise typer.Exit(1)
                    return
                if not job:
                    time.sleep(cfg.worker_poll_seconds)
        except KeyboardInterrupt:
            return

    db_action(run)


@app.command("import-offers")
def offers(tender_key: str, lot: str = "1"):
    """Consultar una partida pública; precios presentados, nunca adjudicados."""
    from .history import import_offers

    try:
        count = db_action(lambda store, cfg: import_offers(store, tender_key, lot))
        typer.echo(f"Ofertas registradas: {count}")
    except (SourceError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from None


@app.command("document-orphans")
def document_orphans():
    """Reportar candidatos huérfanos de GridFS sin borrar datos."""
    import json

    from .documents import DocumentService

    result = db_action(lambda store, cfg: DocumentService(store, cfg).orphan_report())
    typer.echo(json.dumps(result))


if __name__ == "__main__":
    app()
