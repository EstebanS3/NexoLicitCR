"""Optional cache; MongoDB remains authoritative. Never scan/flush shared Redis."""

import hashlib
import json
import threading
import time

from redis import Redis
from redis.backoff import NoBackoff
from redis.exceptions import RedisError
from redis.retry import Retry


class OptionalCache:
    def __init__(self, settings, client=None, clock=time.monotonic):
        self.settings = settings
        self.clock = clock
        self.failed_until = 0.0
        self.lock = threading.Lock()
        # Database identity makes accidental reuse of installation IDs less dangerous.
        endpoint = (
            settings.mongo_local_uri if settings.mongo_mode == "local" else settings.atlas_uri
        )
        database = hashlib.sha256(
            (endpoint.get_secret_value() + "/" + settings.database_name).encode()
        ).hexdigest()[:16]
        self.prefix = f"{settings.redis_namespace}:{settings.environment}:{settings.installation_id}:{database}:v1"
        self.client = client
        if self.client is None and settings.redis_url.get_secret_value():
            self.client = Redis.from_url(
                settings.redis_url.get_secret_value(),
                socket_timeout=settings.cache_timeout_ms / 1000,
                socket_connect_timeout=settings.cache_timeout_ms / 1000,
                retry=Retry(NoBackoff(), 0),
                max_connections=8,
                decode_responses=False,
                client_name=f"{settings.redis_namespace}-{settings.installation_id}",
            )

    @property
    def status(self):
        if self.client is None:
            return "disabled"
        return "fallback" if self.clock() < self.failed_until else "configured"

    def key(self, resource, revision, generation, rules, filters):
        digest = hashlib.sha256(
            json.dumps(filters, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return f"{self.prefix}:company:company:{resource}:catalog:{revision}:rules:{rules}:corpus:{generation}:{digest}"

    def fail(self):
        with self.lock:
            self.failed_until = self.clock() + self.settings.cache_breaker_seconds

    def get(self, key):
        if self.client is None or self.clock() < self.failed_until:
            return None
        try:
            raw = self.client.get(key)
            if raw is None or len(raw) > 4 * 1024 * 1024:
                return None
            return json.loads(raw)
        except (RedisError, ValueError, TypeError, UnicodeError):
            self.fail()
            return None

    def put(self, key, value):
        if self.client is None or self.clock() < self.failed_until:
            return
        try:
            raw = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
            if len(raw.encode()) <= 4 * 1024 * 1024:
                self.client.set(key, raw, ex=self.settings.cache_ttl_seconds)
        except (RedisError, ValueError, TypeError):
            self.fail()

    def close(self):
        if self.client:
            try:
                self.client.close()
            except RedisError:
                pass
