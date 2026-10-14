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
from pymongo.errors import PyMongoError
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .cache import OptionalCache
from .config import Settings
from .jobs import JobQueue
from .matching import Radar, deadline_status, score
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
        return TEMPLATES.TemplateResponse(
            request=request, name=template, context={"cache_status": cache.status, **context}
        )

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
        return {
            "mongodb": "available",
            "mongo_mode": settings.mongo_mode,
            "cache": cache.status,
            "redis_required": False,
        }

    @app.get("/", response_class=HTMLResponse)
    def home(request: Request):
        current = session(request)
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
            opportunities=rows[:4],
            recent_jobs=list(
                store.db.jobs.find({"installation_id": settings.installation_id})
                .sort("created_at", -1)
                .limit(3)
            ),
        )

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
            current_status=deadline_status(tender["payload"]),
            match=score(
                tender["payload"],
                store.catalog(),
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
        request: Request, status: str = "active", q: str = "", minimum: int = 0, page: int = 1
    ):
        current = session(request)
        if (
            status not in {"active", "all", "following", "discarded", "unknown", "closed"}
            or len(q) > 120
            or not 0 <= minimum <= 100
            or not 1 <= page <= 1000
        ):
            raise HTTPException(422, "Filtros inválidos")
        rows = radar.rows()
        filtered = [
            r
            for r in rows
            if r["match"]["score"] >= minimum
            and q.casefold() in (r["tender"]["title"] + " " + r["tender"]["institution"]).casefold()
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
        return render(
            request,
            "opportunities.html",
            csrf=current["csrf"],
            rows=filtered[(page - 1) * 25 : page * 25],
            total=len(filtered),
            page=page,
            status=status,
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
        return {
            key: job.get(key)
            for key in (
                "_id",
                "status",
                "progress",
                "attempt",
                "error_code",
                "cancel_requested",
                "errors",
            )
        }

    @app.get("/jobs/{job_id}/view", response_class=HTMLResponse)
    def job_view(request: Request, job_id: str):
        current = session(request)
        job = queue.get(job_id)
        if not job:
            raise HTTPException(404, "Trabajo inexistente")
        return render(request, "job.html", csrf=current["csrf"], job=job)

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
