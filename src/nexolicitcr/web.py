import secrets
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from pymongo.errors import PyMongoError
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .config import Settings
from .models import CatalogItem
from .security import DUMMY_HASH, check_password, valid_username
from .storage import ConflictError, Store, connect, token_hash, utcnow

ROOT = Path(__file__).parent
TEMPLATES = Jinja2Templates(directory=str(ROOT / "templates"))


class RequestLimits:
    """Bound form bodies before multipart parsing, including chunked requests."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in {"POST", "PUT", "PATCH"}:
            return await self.app(scope, receive, send)
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            if len(body) > 32768:
                response = JSONResponse({"detail": "Solicitud demasiado grande"}, status_code=413)
                return await response(scope, receive, send)
            if not message.get("more_body", False):
                break
        delivered = False

        async def limited_receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, limited_receive, send)


def create_app(settings: Settings | None = None, store: Store | None = None):
    settings = settings or Settings()
    mongo = None
    if store is None:
        mongo = connect(settings)
        store = Store(mongo[settings.atlas_base])

    @asynccontextmanager
    async def lifespan(app):
        yield
        if mongo is not None:
            mongo.close()

    app = FastAPI(
        title="NexoLicitCR",
        telemetry={"tracing": False, "metrics": False, "logs": False, "auto_configure": False},
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.add_middleware(RequestLimits)
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=[urlsplit(settings.public_origin).hostname]
    )
    app.mount("/static", StaticFiles(directory=str(ROOT / "static")), name="static")

    @app.middleware("http")
    async def safety_headers(request, call_next):
        if (
            request.method not in {"GET", "HEAD", "OPTIONS"}
            and request.headers.get("origin") != settings.public_origin
        ):
            response = JSONResponse({"detail": "Origen inválido"}, status_code=403)
        else:
            response = await call_next(request)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'none'; style-src 'self'; img-src 'self'; "
            "frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        # "no-referrer" hace que el navegador envíe Origin: null en los POST de formularios,
        # lo que la verificación de origen rechaza; "same-origin" no filtra la URL a terceros.
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Cache-Control"] = "no-store"
        if settings.secure_cookies:
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        return response

    @app.exception_handler(RequestValidationError)
    def invalid_request(request, exc):
        return JSONResponse(
            {"detail": "Datos inválidos; revisá los campos del formulario."}, status_code=422
        )

    @app.exception_handler(PyMongoError)
    def database_error(request, exc):
        return JSONResponse(
            {"detail": "Persistencia no disponible. Intentá nuevamente."}, status_code=503
        )

    @app.exception_handler(ConflictError)
    def conflict(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=409)

    def session(request):
        value = store.session_get(request.cookies.get("nexo_session"))
        if value is None:
            raise HTTPException(303, headers={"Location": "/login"})
        return value

    def require_csrf(request, supplied):
        current = session(request)
        if not secrets.compare_digest(current["csrf"].encode(), supplied.encode()):
            raise HTTPException(403, "Formulario inválido; recargá la página")
        return current

    def render(request, template, **context):
        return TEMPLATES.TemplateResponse(request=request, name=template, context=context)

    def login_page(request, error="", status=200):
        nonce = secrets.token_urlsafe(32)
        store.db.login_tokens.insert_one(
            {"_id": token_hash(nonce), "expires_at": utcnow() + timedelta(minutes=15)}
        )
        response = render(request, "login.html", token=nonce, error=error)
        response.status_code = status
        response.set_cookie(
            "nexo_login",
            nonce,
            max_age=900,
            httponly=True,
            secure=settings.secure_cookies,
            samesite="strict",
        )
        return response

    @app.get("/health/live")
    def live():
        return {"status": "ok"}

    @app.get("/health/ready")
    def ready():
        store.ping()
        return {"atlas": "available", "cache": "unused", "redis_required": False}

    @app.get("/", response_class=HTMLResponse)
    def home(request: Request):
        current = session(request)
        return render(request, "home.html", csrf=current["csrf"])

    @app.get("/login", response_class=HTMLResponse)
    def login_get(request: Request):
        return login_page(request)

    @app.post("/login")
    def login_post(
        request: Request,
        username: str = Form(max_length=64),
        password: str = Form(max_length=256),
        csrf: str = Form(max_length=128),
    ):
        cookie = request.cookies.get("nexo_login", "")
        if not cookie or not secrets.compare_digest(cookie.encode(), csrf.encode()):
            raise HTTPException(403, "Formulario inválido")
        nonce = store.db.login_tokens.find_one_and_delete(
            {"_id": token_hash(cookie), "expires_at": {"$gt": utcnow()}}
        )
        if nonce is None:
            raise HTTPException(403, "Formulario vencido")
        username = username.strip().lower()
        address = request.client.host if request.client else "unknown"
        if not store.login_allowed(address, username):
            return login_page(request, "Demasiados intentos. Intentá más tarde.", 429)
        user = store.user(username) if valid_username(username) else None
        valid, updated_hash = check_password(
            password, user["password_hash"] if user else DUMMY_HASH
        )
        if not user or not valid:
            return login_page(request, "Credenciales inválidas.", 401)
        if updated_hash:
            store.db.users.update_one(
                {"_id": user["_id"]}, {"$set": {"password_hash": updated_hash}}
            )
        store.session_delete(request.cookies.get("nexo_session"))
        token = store.session_create(user["_id"], settings.session_hours)
        response = RedirectResponse("/", status_code=303)
        response.set_cookie(
            "nexo_session",
            token,
            max_age=settings.session_hours * 3600,
            httponly=True,
            secure=settings.secure_cookies,
            samesite="strict",
        )
        response.delete_cookie("nexo_login")
        return response

    @app.post("/logout")
    def logout(request: Request, csrf: str = Form(max_length=128)):
        require_csrf(request, csrf)
        store.session_delete(request.cookies.get("nexo_session"))
        response = RedirectResponse("/login", status_code=303)
        response.delete_cookie("nexo_session")
        return response

    @app.get("/catalog", response_class=HTMLResponse)
    def catalog_get(request: Request, edit: str = ""):
        current = session(request)
        catalog = store.catalog()
        selected = next((x for x in catalog["items"] if x["id"] == edit), None)
        if edit and selected is None:
            raise HTTPException(404, "Ítem inexistente")
        return render(
            request,
            "catalog.html",
            csrf=current["csrf"],
            catalog=catalog,
            item=selected or {},
            error="",
        )

    @app.post("/catalog")
    def catalog_post(
        request: Request,
        csrf: str = Form(max_length=128),
        revision: int = Form(ge=0),
        item_id: str = Form(default="", max_length=32),
        name: str = Form(max_length=160),
        description: str = Form(default="", max_length=4000),
        capabilities: str = Form(default="", max_length=4000),
        coverage: str = Form(default="", max_length=500),
        keywords: str = Form(default="", max_length=4000),
        exclusions: str = Form(default="", max_length=4000),
        classification_system: str = Form(default="", max_length=100),
        classification_code: str = Form(default="", max_length=100),
        active: bool = Form(default=False),
    ):
        require_csrf(request, csrf)
        try:
            item = CatalogItem(
                name=name,
                description=description,
                capabilities=capabilities,
                coverage=coverage,
                keywords=[x.strip() for x in keywords.split(",") if x.strip()],
                exclusions=[x.strip() for x in exclusions.split(",") if x.strip()],
                classification_system=classification_system,
                classification_code=classification_code,
                active=active,
            )
        except ValidationError:
            raise HTTPException(
                422, "Revisá los campos; código y sistema deben indicarse juntos."
            ) from None
        store.save_catalog_item(item, revision, item_id or None)
        return RedirectResponse("/catalog", status_code=303)

    @app.get("/tenders", response_class=HTMLResponse)
    def tenders_get(request: Request, page: int = 1, q: str = ""):
        current = session(request)
        if not 1 <= page <= 1000 or len(q) > 120:
            raise HTTPException(422, "Búsqueda inválida")
        tenders = store.tenders(page, q)
        return render(
            request,
            "tenders.html",
            csrf=current["csrf"],
            tenders=tenders[:25],
            more=len(tenders) > 25,
            page=page,
            q=q,
        )

    @app.get("/tenders/{key}", response_class=HTMLResponse)
    def tender_get(request: Request, key: str):
        current = session(request)
        if len(key) > 40:
            raise HTTPException(404)
        tender = store.tender(key)
        if not tender:
            raise HTTPException(404, "Concurso inexistente")
        return render(
            request,
            "tender.html",
            csrf=current["csrf"],
            record=tender,
            tender=tender["payload"],
            awards=[x["payload"] for x in store.awards_for(tender["payload"]["procedure"])],
        )

    return app
