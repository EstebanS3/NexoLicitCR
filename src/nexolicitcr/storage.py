import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from pymongo import ASCENDING, MongoClient, ReturnDocument
from pymongo.errors import DuplicateKeyError
from pymongo.read_concern import ReadConcern
from pymongo.write_concern import WriteConcern

from .models import CatalogItem, Tender


class ConflictError(Exception):
    pass


def utcnow():
    return datetime.now(UTC)


def token_hash(value):
    return hashlib.sha256(value.encode()).hexdigest()


def connect(settings):
    local = settings.mongo_mode == "local"
    return MongoClient(
        (settings.mongo_local_uri if local else settings.atlas_uri).get_secret_value(),
        username=(
            settings.mongo_local_usuario if local else settings.atlas_usuario
        ).get_secret_value(),
        password=(settings.mongo_local_clave if local else settings.atlas_clave).get_secret_value(),
        authSource="admin" if local else settings.atlas_authdb,
        tls=not local,
        serverSelectionTimeoutMS=settings.mongo_timeout_ms,
        connectTimeoutMS=settings.mongo_timeout_ms,
        socketTimeoutMS=10000,
        tz_aware=True,
        appname="NexoLicitCR",
        w="majority",
    )


class Store:
    def __init__(self, database):
        self.db = database

    def ping(self):
        self.db.command("ping")

    def ensure_indexes(self):
        self.db.users.create_index("username", unique=True)
        self.db.sessions.create_index("expires_at", expireAfterSeconds=0)
        self.db.login_tokens.create_index("expires_at", expireAfterSeconds=0)
        self.db.login_limits.create_index("expires_at", expireAfterSeconds=0)
        self.db.tenders.create_index([("status", ASCENDING), ("deadline_utc", ASCENDING)])
        self.db.tenders.create_index("observed_at")
        self.db.tender_versions.create_index([("key", ASCENDING), ("hash", ASCENDING)], unique=True)
        self.db.sync_runs.create_index("started_at")
        self.db.jobs.create_index([("installation_id", 1), ("idempotency_key", 1)], unique=True)
        self.db.jobs.create_index(
            [("installation_id", 1), ("status", 1), ("next_attempt_at", 1), ("lease_until", 1)]
        )
        self.db.decisions.create_index([("company", 1), ("tender_key", 1)], unique=True)
        self.db.matches.create_index(
            [
                ("company", 1),
                ("catalog_revision", 1),
                ("tender_key", 1),
                ("tender_hash", 1),
                ("rules_version", 1),
                ("document_generation", 1),
            ],
            unique=True,
        )
        self.db.documents.create_index(
            [("tender_key", 1), ("source_identity", 1), ("sha256", 1)], unique=True
        )
        self.db.documents.create_index("state")
        self.db.extracted_pages.create_index([("document_id", 1), ("page", 1)], unique=True)
        self.db.offers.create_index(
            [("tender_key", 1), ("source_hash", 1), ("position", 1)], unique=True
        )
        self.db.metadata.update_one(
            {"_id": "corpus"}, {"$setOnInsert": {"generation": 0}}, upsert=True
        )
        self.db.catalog.update_one(
            {"_id": "company"},
            {"$setOnInsert": {"revision": 0, "items": [], "updated_at": utcnow()}},
            upsert=True,
        )

    def create_admin(self, username, password_hash):
        # A fixed key guarantees that two concurrent bootstrap commands cannot create two admins.
        self.db.users.insert_one(
            {
                "_id": "administrator",
                "username": username,
                "password_hash": password_hash,
                "active": True,
            }
        )

    def user(self, username):
        return self.db.users.find_one({"username": username, "active": True})

    def session_create(self, user_id, hours):
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        self.db.sessions.insert_one(
            {
                "_id": token_hash(token),
                "user_id": user_id,
                "csrf": csrf,
                "expires_at": utcnow() + timedelta(hours=hours),
            }
        )
        return token

    def session_get(self, token):
        if not token or len(token) > 128:
            return None
        session = self.db.sessions.find_one(
            {"_id": token_hash(token), "expires_at": {"$gt": utcnow()}}
        )
        if session and self.db.users.find_one({"_id": session["user_id"], "active": True}):
            return session
        return None

    def session_delete(self, token):
        if token:
            self.db.sessions.delete_one({"_id": token_hash(token)})

    def login_allowed(self, address, username):
        # Shared limits across processes; only hashes, not client addresses or attempted names.
        bucket = int(utcnow().timestamp()) // 900
        for kind, value, maximum in (("address", address, 30), ("user", username, 10)):
            key = token_hash(f"{kind}:{value}:{bucket}")
            row = self.db.login_limits.find_one_and_update(
                {"_id": key},
                {
                    "$inc": {"count": 1},
                    "$setOnInsert": {"expires_at": utcnow() + timedelta(minutes=30)},
                },
                upsert=True,
                return_document=ReturnDocument.AFTER,
            )
            if row["count"] > maximum:
                return False
        return True

    def catalog(self):
        return self.db.catalog.find_one({"_id": "company"}) or {"revision": 0, "items": []}

    def save_catalog_item(self, item: CatalogItem, revision: int, item_id=None):
        catalog = self.catalog()
        if catalog["revision"] != revision:
            raise ConflictError("El catálogo cambió; recargá antes de guardar.")
        items = catalog["items"]
        if item_id:
            existing = next((x for x in items if x["id"] == item_id), None)
            if existing is None:
                raise ConflictError("Ítem inexistente")
            items = [
                dict(item.model_dump(), id=item_id) if x["id"] == item_id else x for x in items
            ]
        else:
            if len(items) >= 1000:
                raise ConflictError("El catálogo alcanzó el máximo de 1000 ítems")
            item_id = uuid4().hex
            items.append(dict(item.model_dump(), id=item_id))
        updated = self.db.catalog.update_one(
            {"_id": "company", "revision": revision},
            {"$set": {"items": items, "updated_at": utcnow()}, "$inc": {"revision": 1}},
        )
        if updated.matched_count != 1:
            raise ConflictError("El catálogo cambió; recargá antes de guardar.")
        return item_id

    def save_profile(self, profile, revision):
        result = self.db.catalog.update_one(
            {"_id": "company", "revision": revision},
            {
                "$set": {"profile": profile.model_dump(), "updated_at": utcnow()},
                "$inc": {"revision": 1},
            },
        )
        if result.matched_count != 1:
            raise ConflictError("El perfil cambió en otra ventana. Recargá antes de confirmar.")

    def save_tender(self, tender: Tender, observed_at, fence=None):
        payload = tender.model_dump(mode="json")  # Decimal values remain exact strings.
        digest = tender.fingerprint()

        def persist(session):
            if fence:
                fence(session)
            current = self.db.tenders.find_one({"_id": tender.key}, session=session)
            if current and current["observed_at"] > observed_at:
                return "stale"
            changed = not current or current["hash"] != digest
            self.db.tender_versions.update_one(
                {"key": tender.key, "hash": digest},
                {"$setOnInsert": {"payload": payload, "observed_at": observed_at}},
                upsert=True,
                session=session,
            )
            self.db.tenders.replace_one(
                {"_id": tender.key},
                {
                    "_id": tender.key,
                    "hash": digest,
                    "payload": payload,
                    "observed_at": observed_at,
                    "status": tender.status,
                    "deadline_utc": tender.deadline.utc,
                    "source_url": tender.source_url,
                },
                upsert=True,
                session=session,
            )
            if changed:
                self.db.metadata.update_one(
                    {"_id": "corpus"}, {"$inc": {"generation": 1}}, upsert=True, session=session
                )
            return "changed" if changed else "unchanged"

        # A concurrent first insert may conflict on unique keys. Retry the transaction,
        # never fall back to non-atomic writes on deployments without transactions.
        for attempt in range(3):
            try:
                with self.db.client.start_session() as session:
                    return session.with_transaction(
                        persist,
                        read_concern=ReadConcern("snapshot"),
                        write_concern=WriteConcern("majority"),
                    )
            except DuplicateKeyError:
                if attempt == 2:
                    raise
        raise ConflictError("No se pudo persistir el concurso")

    def tenders(self, page=1, query=""):
        filters = {}
        if query:
            import re

            pattern = re.escape(query)
            filters = {
                "$or": [
                    {"payload.title": {"$regex": pattern, "$options": "i"}},
                    {"payload.procedure": {"$regex": pattern, "$options": "i"}},
                ]
            }
        return list(
            self.db.tenders.find(filters)
            .sort([("observed_at", -1), ("_id", 1)])
            .skip((page - 1) * 25)
            .limit(26)
        )

    def tender(self, key):
        return self.db.tenders.find_one({"_id": key})
