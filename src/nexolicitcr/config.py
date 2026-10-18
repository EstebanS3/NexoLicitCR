from typing import Literal
from urllib.parse import parse_qs, urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)

    mongo_mode: Literal["atlas", "local"] = "atlas"
    mongo_local_uri: SecretStr = SecretStr("mongodb://127.0.0.1:27017/?replicaSet=nexo-local")
    mongo_local_usuario: SecretStr = SecretStr("")
    mongo_local_clave: SecretStr = SecretStr("")
    mongo_local_base: str = Field(
        default="nexolicit_local", pattern=r"^nexolicit_[a-zA-Z0-9_-]{1,50}$"
    )
    atlas_uri: SecretStr = SecretStr("")
    atlas_usuario: SecretStr = SecretStr("")
    atlas_clave: SecretStr = SecretStr("")
    atlas_base: str = Field(default="nexolicit_dev", pattern=r"^[a-zA-Z][a-zA-Z0-9_-]{0,62}$")
    atlas_authdb: str = Field(default="admin", pattern=r"^[a-zA-Z][a-zA-Z0-9_-]{0,62}$")
    app_mode: Literal["local", "server"] = "local"
    public_origin: str = "http://localhost:8000"
    sicop_timezone: str = ""
    sicop_request_delay_seconds: float = Field(default=2, ge=0.4, le=30)
    redis_url: SecretStr = SecretStr("")
    mongo_timeout_ms: int = Field(default=5000, ge=500, le=30000)
    installation_id: str = Field(default="nexolicit", pattern=r"^[a-z0-9][a-z0-9_-]{0,47}$")
    environment: Literal["development", "test", "production"] = "development"
    redis_namespace: str = Field(default="nexolicitcr", pattern=r"^[a-z0-9][a-z0-9_-]{0,47}$")
    cache_ttl_seconds: int = Field(default=120, ge=5, le=900)
    cache_timeout_ms: int = Field(default=150, ge=20, le=1000)
    cache_breaker_seconds: int = Field(default=30, ge=1, le=300)
    job_lease_seconds: int = Field(default=90, ge=15, le=600)
    job_max_attempts: int = Field(default=3, ge=1, le=10)
    worker_poll_seconds: float = Field(default=2, ge=0.1, le=60)
    document_max_bytes: int = Field(default=20971520, ge=1024, le=52428800)
    document_max_pages: int = Field(default=30, ge=1, le=100)
    document_max_files: int = Field(default=5, ge=1, le=20)
    extraction_timeout_seconds: int = Field(default=120, ge=5, le=600)
    # Oracle source provenance verified in docs/source-validation.md.
    document_hosts: str = (
        "www.sicop.go.cr,prod-api.sicop.go.cr,objectstorage.us-ashburn-1.oraclecloud.com"
    )
    session_hours: int = Field(default=8, ge=1, le=24)

    @model_validator(mode="after")
    def validate_configuration(self):
        if self.mongo_mode == "local":
            self.validate_local_mongo()
        else:
            self.validate_atlas()
        if self.redis_url.get_secret_value():
            redis = urlsplit(self.redis_url.get_secret_value())
            if (
                redis.scheme not in {"redis", "rediss"}
                or not redis.hostname
                or redis.query
                or redis.fragment
            ):
                raise ValueError("REDIS_URL requiere redis/rediss sin opciones adicionales")
        origin = urlsplit(self.public_origin)
        if (
            origin.username
            or origin.password
            or origin.path not in ("", "/")
            or origin.query
            or origin.fragment
        ):
            raise ValueError("PUBLIC_ORIGIN debe ser un origen sin ruta ni credenciales")
        if not origin.hostname or origin.scheme not in ("http", "https"):
            raise ValueError("PUBLIC_ORIGIN inválido")
        if self.app_mode == "server" and origin.scheme != "https":
            raise ValueError("El servidor requiere PUBLIC_ORIGIN HTTPS")
        if self.app_mode == "local" and origin.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError("El modo local solo admite loopback")
        if self.sicop_timezone:
            try:
                ZoneInfo(self.sicop_timezone)
            except ZoneInfoNotFoundError:
                raise ValueError("SICOP_TIMEZONE no es una zona IANA válida") from None
        self.public_origin = self.public_origin.rstrip("/")
        return self

    def validate_local_mongo(self):
        if self.app_mode != "local":
            raise ValueError("MongoDB local solo se admite en APP_MODE=local")
        uri = urlsplit(self.mongo_local_uri.get_secret_value())
        if (
            uri.scheme != "mongodb"
            or uri.hostname != "127.0.0.1"
            or uri.netloc != f"127.0.0.1:{uri.port}"
            or uri.path not in ("", "/")
            or uri.fragment
        ):
            raise ValueError("MONGO_LOCAL_URI debe usar 127.0.0.1 y un puerto explícito")
        if parse_qs(uri.query, keep_blank_values=True) != {"replicaSet": ["nexo-local"]}:
            raise ValueError("MongoDB local requiere replicaSet=nexo-local sin otras opciones")
        if (
            not self.mongo_local_usuario.get_secret_value()
            or not self.mongo_local_clave.get_secret_value()
        ):
            raise ValueError("Faltan credenciales de MongoDB local")

    def validate_atlas(self):
        uri = urlsplit(self.atlas_uri.get_secret_value())
        if (
            uri.scheme != "mongodb+srv"
            or not uri.hostname
            or not uri.hostname.endswith(".mongodb.net")
        ):
            raise ValueError("ATLAS_URI debe identificar un cluster Atlas mediante mongodb+srv")
        if uri.username is not None or uri.password is not None or uri.fragment:
            raise ValueError("Usar ATLAS_USUARIO y ATLAS_CLAVE separados de ATLAS_URI")
        allowed = {"retrywrites", "w", "appname"}
        if any(k.lower() not in allowed for k in parse_qs(uri.query, keep_blank_values=True)):
            raise ValueError("ATLAS_URI contiene opciones no admitidas; TLS es obligatorio")
        if not self.atlas_usuario.get_secret_value() or not self.atlas_clave.get_secret_value():
            raise ValueError("Faltan credenciales Atlas")

    @property
    def database_name(self) -> str:
        return self.mongo_local_base if self.mongo_mode == "local" else self.atlas_base

    @property
    def secure_cookies(self) -> bool:
        return self.public_origin.startswith("https://")
