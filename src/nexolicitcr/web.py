import secrets
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from pymongo.errors import DuplicateKeyError, PyMongoError
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .cache import OptionalCache
from .config import Settings
from .discovery import matching_catalog, suggest
from .jobs import JobQueue
from .matching import Radar, deadline_status, normalized, score
from .models import CatalogItem, CompanyProfile
from .sectors import SECTORS, specialty_terms
from .security import DUMMY_HASH, PASSWORDS, check_password, valid_username, validate_password
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
        store = Store(mongo[settings.database_name])

    cache = OptionalCache(settings)
    radar = Radar(store, cache)
    queue = JobQueue(store, settings)

    @asynccontextmanager
    async def lifespan(app):
        yield
        cache.close()
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
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; "
            "frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        # Preserve Origin on HTML form POSTs; suppress referrers to external sites.
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Cache-Control"] = "no-store"
        if settings.secure_cookies:
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        return response

    def user_error(request, message, status_code):
        if "text/html" in request.headers.get("accept", ""):
            return TEMPLATES.TemplateResponse(
                request=request,
                name="form_error.html",
                context={"message": message, "status_code": status_code},
                status_code=status_code,
            )
        return JSONResponse({"detail": message}, status_code=status_code)

    @app.exception_handler(HTTPException)
    def http_error(request, exc):
        if exc.status_code in {400, 403, 409, 422, 503}:
            return user_error(request, str(exc.detail), exc.status_code)
        return JSONResponse(
            {"detail": exc.detail}, status_code=exc.status_code, headers=exc.headers
        )

    @app.exception_handler(RequestValidationError)
    def invalid_request(request, exc):
        return user_error(request, "Datos inválidos; revisá los campos del formulario.", 422)

    @app.exception_handler(PyMongoError)
    def database_error(request, exc):
        return user_error(request, "Persistencia no disponible. Intentá nuevamente.", 503)

    @app.exception_handler(ConflictError)
    def conflict(request, exc):
        return user_error(request, str(exc), 409)

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
        return TEMPLATES.TemplateResponse(
            request=request,
            name=template,
            context={"cache_status": cache.status, "sectors": SECTORS, **context},
        )

    def login_page(request, error="", status=200, registered=False):
        nonce = secrets.token_urlsafe(32)
        store.db.login_tokens.insert_one(
            {"_id": token_hash(nonce), "expires_at": utcnow() + timedelta(minutes=15)}
        )
        response = render(
            request,
            "login.html",
            token=nonce,
            error=error,
            registration_open=store.registration_open(),
            registered=registered,
        )
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

    def registration_page(request, error="", username="", status=200):
        opened = store.registration_open()
        nonce = secrets.token_urlsafe(32) if opened else ""
        if opened:
            store.db.login_tokens.insert_one(
                {
                    "_id": token_hash("register:" + nonce),
                    "expires_at": utcnow() + timedelta(minutes=15),
                }
            )
        response = render(
            request,
            "register.html",
            registration_open=opened,
            token=nonce,
            username=username,
            error=error,
        )
        response.status_code = status
        if opened:
            response.set_cookie(
                "nexo_register",
                nonce,
                max_age=900,
                httponly=True,
                secure=settings.secure_cookies,
                samesite="strict",
                path="/register",
            )
        else:
            response.delete_cookie("nexo_register", path="/register")
        return response

    @app.get("/register", response_class=HTMLResponse)
    def register_get(request: Request):
        return registration_page(request)

    @app.post("/register")
    def register_post(
        request: Request,
        username: str = Form(max_length=64),
        password: str = Form(max_length=256),
        password_confirm: str = Form(max_length=256),
        csrf: str = Form(max_length=128),
    ):
        if not store.registration_open():
            return registration_page(request, status=409)
        cookie = request.cookies.get("nexo_register", "")
        if not cookie or not secrets.compare_digest(cookie.encode(), csrf.encode()):
            return registration_page(
                request, "El formulario no es válido. Intentá nuevamente.", status=403
            )
        nonce = store.db.login_tokens.find_one_and_delete(
            {"_id": token_hash("register:" + cookie), "expires_at": {"$gt": utcnow()}}
        )
        if nonce is None:
            return registration_page(
                request, "El formulario venció. Intentá nuevamente.", status=403
            )
        address = request.client.host if request.client else "unknown"
        if not store.login_allowed(address, "initial-registration"):
            return registration_page(request, "Demasiados intentos. Intentá más tarde.", status=429)
        username = username.strip().lower()
        if not valid_username(username):
            return registration_page(
                request,
                "Usá entre 3 y 64 caracteres: letras minúsculas, números, punto, guion o guion bajo.",
                username,
                422,
            )
        try:
            validate_password(password)
        except ValueError as exc:
            return registration_page(request, str(exc), username, 422)
        if not secrets.compare_digest(password.encode(), password_confirm.encode()):
            return registration_page(request, "Las contraseñas no coinciden.", username, 422)
        try:
            store.create_admin(username, PASSWORDS.hash(password))
        except DuplicateKeyError:
            return registration_page(request, status=409)
        response = RedirectResponse("/login?registered=1", status_code=303)
        response.delete_cookie("nexo_register", path="/register")
        return response

    @app.get("/health/live")
    def live():
        return {"status": "ok"}

    @app.get("/health/ready")
    def ready():
        store.ping()
        return {
            "mongodb": "available",
            "mongo_mode": settings.mongo_mode,
            "cache": cache.status,
            "redis_required": False,
        }

    @app.get("/", response_class=HTMLResponse)
    def home(request: Request):
        if store.registration_open():
            return registration_page(request)
        current = session(request)
        if not store.catalog().get("profile"):
            return render(request, "welcome.html", csrf=current["csrf"])
        rows = radar.rows()
        stats = {
            "total": len(rows),
            "relevant": sum(
                r["match"]["score"] > 0 and r["current_status"] not in {"closed", "canceled"}
                for r in rows
            ),
            "following": sum(r["decision"].get("status") == "following" for r in rows),
            "catalog": sum(i["active"] for i in store.catalog()["items"]),
        }
        return render(
            request,
            "home.html",
            csrf=current["csrf"],
            stats=stats,
            profile=store.catalog().get("profile"),
            opportunities=[
                r
                for r in rows
                if r["current_status"] not in {"closed", "canceled"}
                and r["match"]["score"] > 0
                and r["decision"].get("status") != "discarded"
            ][:4],
            recent_jobs=list(
                store.db.jobs.find({"installation_id": settings.installation_id})
                .sort("created_at", -1)
                .limit(3)
            ),
        )

    @app.get("/login", response_class=HTMLResponse)
    def login_get(request: Request, registered: bool = False):
        return login_page(request, registered=registered)

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

    @app.get("/company", response_class=HTMLResponse)
    def company(request: Request):
        current = session(request)
        catalog = store.catalog()
        return render(
            request,
            "company.html",
            csrf=current["csrf"],
            profile=catalog.get("profile") or {},
            revision=catalog["revision"],
        )

    @app.post("/company/draft", response_class=HTMLResponse)
    def company_draft(
        request: Request,
        csrf: str = Form(max_length=128),
        revision: int = Form(ge=0),
        company_name: str = Form(min_length=2, max_length=160),
    ):
        require_csrf(request, csrf)
        if len(company_name.strip()) < 2:
            raise HTTPException(422, "Escribí el nombre de tu empresa (al menos 2 caracteres).")
        catalog = store.catalog()
        if revision != catalog["revision"]:
            raise ConflictError("El perfil cambió. Recargá antes de continuar.")
        return render(
            request,
            "discover.html",
            csrf=csrf,
            revision=revision,
            step=1,
            profile={**(catalog.get("profile") or {}), "company_name": company_name.strip()},
        )

    @app.get("/discover", response_class=HTMLResponse)
    def discover(request: Request):
        current = session(request)
        catalog = store.catalog()
        return render(
            request,
            "discover.html",
            csrf=current["csrf"],
            profile=catalog.get("profile") or {},
            revision=catalog["revision"],
            step=1,
        )

    @app.post("/discover/draft", response_class=HTMLResponse)
    def discover_draft(
        request: Request,
        csrf: str = Form(max_length=128),
        revision: int = Form(ge=0),
        activity: str = Form(default="", max_length=1000),
        company_name: str = Form(default="", max_length=160),
        sector: str = Form(default="", max_length=40),
        specialty: str = Form(default="", max_length=40),
        draft_services: str | None = Form(default=None, max_length=1000),
        draft_coverage: str | None = Form(default=None, max_length=500),
        draft_exclusions: str | None = Form(default=None, max_length=2100),
        draft_category: str | None = Form(default=None, max_length=20),
        draft_sector: str | None = Form(default=None, max_length=40),
        draft_specialty: str | None = Form(default=None, max_length=40),
    ):
        require_csrf(request, csrf)
        catalog = store.catalog()
        if revision != catalog["revision"]:
            raise ConflictError("El perfil cambió. Recargá antes de continuar.")
        old = catalog.get("profile") or {}
        try:
            selected = specialty_terms(sector, specialty)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        has_draft = any(
            value is not None
            for value in (
                draft_services,
                draft_coverage,
                draft_exclusions,
                draft_category,
                draft_sector,
                draft_specialty,
            )
        )
        if has_draft:
            try:
                specialty_terms(draft_sector or "", draft_specialty or "")
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from None
            if draft_category not in {None, "all", "bienes", "servicios", "obras"}:
                raise HTTPException(422, "Elegí un tipo de oportunidades válido.")
        company_name = company_name.strip() or old.get("company_name", "")
        same_specialty = sector == old.get("sector", "") and specialty == old.get("specialty", "")
        activity = activity.strip()
        if not activity and selected:
            activity = (
                old["activity"]
                if same_specialty and old.get("activity")
                else f"{company_name or 'La empresa'} ofrece "
                f"{SECTORS[sector]['specialties'][specialty][0].lower()}."
            )
        if selected and activity and len(activity) < 12:
            activity = (
                f"{company_name or 'La empresa'} ofrece "
                f"{SECTORS[sector]['specialties'][specialty][0].lower()}. "
                f"Detalle: {activity}"
            )
        if len(activity) < 12:
            raise HTTPException(
                422,
                "Describí tu actividad con al menos 12 caracteres o elegí una especialidad "
                "de la lista. Para otra actividad, necesitamos esa descripción.",
            )
        services = (
            old.get("services", [])
            if activity == old.get("activity") and same_specialty
            else selected
            if selected is not None
            else suggest(activity)
        )
        details = {}
        if has_draft:
            details = {
                "coverage": draft_coverage or "",
                "exclusions": [x.strip() for x in (draft_exclusions or "").split(",") if x.strip()],
                "category": draft_category or "all",
            }
            if sector == (draft_sector or "") and specialty == (draft_specialty or ""):
                services = [x.strip() for x in (draft_services or "").split(",") if x.strip()]
        return render(
            request,
            "discover.html",
            csrf=csrf,
            revision=revision,
            step=2,
            profile={
                **old,
                **details,
                "company_name": company_name,
                "activity": activity,
                "sector": sector,
                "specialty": specialty,
                "services": services,
            },
        )

    @app.post("/discover/revise", response_class=HTMLResponse)
    def discover_revise(
        request: Request,
        csrf: str = Form(max_length=128),
        revision: int = Form(ge=0),
        activity: str = Form(default="", max_length=1000),
        services: str = Form(default="", max_length=1000),
        coverage: str = Form(default="", max_length=500),
        exclusions: str = Form(default="", max_length=2100),
        category: str = Form(default="all", max_length=20),
        company_name: str = Form(default="", max_length=160),
        sector: str = Form(default="", max_length=40),
        specialty: str = Form(default="", max_length=40),
    ):
        require_csrf(request, csrf)
        if revision != store.catalog()["revision"]:
            raise ConflictError("El perfil cambió. Recargá antes de continuar.")
        try:
            specialty_terms(sector, specialty)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        if category not in {"all", "bienes", "servicios", "obras"}:
            raise HTTPException(422, "Elegí un tipo de oportunidades válido.")
        return render(
            request,
            "discover.html",
            csrf=csrf,
            revision=revision,
            step=1,
            profile={
                "company_name": company_name.strip(),
                "activity": activity,
                "sector": sector,
                "specialty": specialty,
                "services": [x.strip() for x in services.split(",") if x.strip()],
                "coverage": coverage,
                "exclusions": [x.strip() for x in exclusions.split(",") if x.strip()],
                "category": category,
            },
        )

    @app.post("/discover/confirm")
    def discover_confirm(
        request: Request,
        csrf: str = Form(max_length=128),
        revision: int = Form(ge=0),
        activity: str = Form(min_length=12, max_length=1000),
        services: str = Form(max_length=1000),
        coverage: str = Form(default="", max_length=500),
        exclusions: str = Form(default="", max_length=2100),
        category: str = Form(default="all"),
        confirmed: bool = Form(default=False),
        company_name: str = Form(default="", max_length=160),
        sector: str = Form(default="", max_length=40),
        specialty: str = Form(default="", max_length=40),
    ):
        require_csrf(request, csrf)
        if not confirmed:
            raise HTTPException(422, "Confirmá que el perfil describe lo que ofrece tu empresa.")
        try:
            profile = CompanyProfile(
                company_name=company_name.strip(),
                sector=sector,
                specialty=specialty,
                activity=activity,
                services=[x.strip() for x in services.split(",") if x.strip()],
                coverage=coverage,
                exclusions=[x.strip() for x in exclusions.split(",") if x.strip()],
                category=category,
            )
        except ValueError:
            raise HTTPException(
                422, "Revisá el perfil: entre 1 y 8 servicios, de hasta 100 caracteres cada uno."
            ) from None
        store.save_profile(profile, revision)
        return RedirectResponse("/opportunities?minimum=1", status_code=303)

    @app.post("/discover/search")
    def discover_search(
        request: Request,
        csrf: str = Form(max_length=128),
        revision: int = Form(ge=0),
        idempotency_key: str = Form(min_length=1, max_length=128),
        limit: int = Form(default=25, ge=10, le=100),
    ):
        require_csrf(request, csrf)
        catalog = store.catalog()
        if not catalog.get("profile") or catalog["revision"] != revision:
            raise HTTPException(409, "El perfil cambió. Recargá antes de actualizar la búsqueda.")
        try:
            job = queue.enqueue(
                catalog["profile"]["category"],
                limit,
                "",
                idempotency_key,
                profile_revision=revision,
            )
        except ValueError:
            raise HTTPException(
                409,
                "Esta solicitud corresponde a otro perfil o alcance. "
                "Recargá para iniciar una nueva consulta.",
            ) from None
        return RedirectResponse(f"/jobs/{job['_id']}/view", status_code=303)

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
            current_status=deadline_status(tender["payload"]),
            match=score(
                tender["payload"],
                matching_catalog(store.catalog()),
                list(
                    store.db.extracted_pages.find(
                        {
                            "document_id": {
                                "$in": store.db.documents.distinct(
                                    "_id",
                                    {
                                        "tender_key": key,
                                        "current": True,
                                        "state": {"$in": ["ready", "partial"]},
                                    },
                                )
                            }
                        }
                    )
                ),
            ),
            documents=list(store.db.documents.find({"tender_key": key})),
            offers=list(store.db.offers.find({"tender_key": key}).sort("fetched_at", -1).limit(50)),
            decision=store.db.decisions.find_one({"company": "company", "tender_key": key}) or {},
        )

    @app.get("/opportunities", response_class=HTMLResponse)
    def opportunities(
        request: Request,
        status: str = "active",
        q: str = "",
        minimum: int | None = None,
        page: int = 1,
        category: str = "all",
    ):
        current = session(request)
        if (
            status not in {"active", "all", "following", "discarded", "unknown", "closed"}
            or category not in {"all", "bienes", "servicios", "obras"}
            or len(q) > 120
            or minimum is not None
            and not 0 <= minimum <= 100
            or not 1 <= page <= 1000
        ):
            raise HTTPException(422, "Filtros inválidos")
        catalog = store.catalog()
        if minimum is None:
            minimum = 1 if catalog.get("profile") and status == "active" else 0
        rows = radar.rows()
        filtered = [
            r
            for r in rows
            if r["match"]["score"] >= minimum
            and (category == "all" or r["tender"]["category"] == category)
            and normalized(q) in normalized(r["tender"]["title"] + " " + r["tender"]["institution"])
            and (
                status == "all"
                or status == "active"
                and r["current_status"] not in {"closed", "canceled"}
                and r["decision"].get("status") != "discarded"
                or status in {"following", "discarded"}
                and r["decision"].get("status") == status
                or status in {"unknown", "closed"}
                and r["current_status"] == status
            )
        ]
        catalog = store.catalog()
        return render(
            request,
            "opportunities.html",
            profile=catalog.get("profile"),
            search_key=secrets.token_urlsafe(24),
            profile_revision=catalog["revision"],
            search_limit_default=25,
            first_search=not rows
            and not store.db.jobs.find_one({"installation_id": settings.installation_id}),
            has_saved_tenders=bool(rows),
            csrf=current["csrf"],
            rows=filtered[(page - 1) * 25 : page * 25],
            total=len(filtered),
            page=page,
            status=status,
            category=category,
            q=q,
            minimum=minimum,
        )

    @app.post("/decisions/{key}")
    def decision_post(
        request: Request,
        key: str,
        csrf: str = Form(max_length=128),
        status: str = Form(max_length=20),
        note: str = Form(default="", max_length=2000),
    ):
        require_csrf(request, csrf)
        try:
            radar.decide(key, status, note)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        return RedirectResponse(f"/tenders/{key}", status_code=303)

    @app.get("/jobs", response_class=HTMLResponse)
    def jobs_get(request: Request):
        current = session(request)
        return render(
            request,
            "jobs.html",
            csrf=current["csrf"],
            source_pause_until=queue.source_pause_until(),
            jobs=list(
                store.db.jobs.find({"installation_id": settings.installation_id})
                .sort("created_at", -1)
                .limit(50)
            ),
            idempotency_key=secrets.token_urlsafe(24),
        )

    @app.post("/sync-runs")
    def sync_post(
        request: Request,
        csrf: str = Form(max_length=128),
        category: str = Form(default="all"),
        limit: int = Form(default=10, ge=1, le=500),
        since: str = Form(default="", max_length=10),
        idempotency_key: str = Form(min_length=1, max_length=128),
        documents: bool = Form(default=False),
    ):
        require_csrf(request, csrf)
        try:
            job = queue.enqueue(category, limit, since, idempotency_key, documents)
        except ValueError:
            raise HTTPException(422, "Filtros o clave de idempotencia inválidos") from None
        if "text/html" in request.headers.get("accept", ""):
            return RedirectResponse(f"/jobs/{job['_id']}/view", status_code=303)
        return JSONResponse(
            {"job_id": job["_id"], "status": job["status"], "url": f"/jobs/{job['_id']}/view"},
            status_code=202,
        )

    @app.get("/jobs/{job_id}")
    def job_status(request: Request, job_id: str):
        session(request)
        job = queue.get(job_id)
        if not job:
            raise HTTPException(404, "Trabajo inexistente")
        result = {
            key: job.get(key)
            for key in (
                "_id",
                "status",
                "progress",
                "attempt",
                "error_code",
                "cancel_requested",
                "next_attempt_at",
                "errors",
            )
        }
        result["source_pause_until"] = queue.source_pause_until()
        result["pending_count"] = len(
            {e["identity"] for e in job.get("errors", [])} - set(job.get("checkpoint", []))
        )
        return result

    @app.post("/jobs/{job_id}/resume")
    def job_resume(request: Request, job_id: str, csrf: str = Form(max_length=128)):
        require_csrf(request, csrf)
        try:
            resumed = queue.resume(job_id)
        except LookupError:
            raise HTTPException(404, "Consulta inexistente") from None
        except ValueError:
            raise HTTPException(409, "Solo se pueden reanudar consultas interrumpidas") from None
        return RedirectResponse(f"/jobs/{resumed['_id']}/view", status_code=303)

    @app.get("/jobs/{job_id}/view", response_class=HTMLResponse)
    def job_view(request: Request, job_id: str):
        current = session(request)
        job = queue.get(job_id)
        if not job:
            raise HTTPException(404, "Trabajo inexistente")
        return render(
            request,
            "job.html",
            csrf=current["csrf"],
            job=job,
            source_pause_until=queue.source_pause_until(),
            pending_count=len(
                {e["identity"] for e in job.get("errors", [])} - set(job.get("checkpoint", []))
            ),
        )

    @app.post("/jobs/{job_id}/cancel")
    def job_cancel(request: Request, job_id: str, csrf: str = Form(max_length=128)):
        require_csrf(request, csrf)
        if not queue.get(job_id):
            raise HTTPException(404)
        queue.cancel(job_id)
        return RedirectResponse(f"/jobs/{job_id}/view", status_code=303)

    @app.get("/documents/{document_id}", response_class=HTMLResponse)
    def document_view(request: Request, document_id: str):
        current = session(request)
        document = store.db.documents.find_one({"_id": document_id})
        if not document:
            raise HTTPException(404)
        return render(
            request,
            "document.html",
            csrf=current["csrf"],
            document=document,
            pages=list(store.db.extracted_pages.find({"document_id": document_id}).sort("page", 1)),
        )

    @app.get("/documents/{document_id}/download")
    def document_download(request: Request, document_id: str):
        session(request)
        import gridfs

        document = store.db.documents.find_one({"_id": document_id})
        if not document or not document.get("gridfs_id"):
            raise HTTPException(404)
        fs = gridfs.GridFS(store.db)
        if not fs.exists(document["gridfs_id"]):
            raise HTTPException(404)

        def chunks():
            with fs.get(document["gridfs_id"]) as stream:
                while chunk := stream.read(65536):
                    yield chunk

        return StreamingResponse(
            chunks(),
            media_type="application/octet-stream",
            headers={"Content-Disposition": 'attachment; filename="documento.bin"'},
        )

    return app
