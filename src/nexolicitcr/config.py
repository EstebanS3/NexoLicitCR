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
    redis_url: SecretStr = SecretStr("")
    mongo_timeout_ms: int = Field(default=5000, ge=500, le=30000)
    session_hours: int = Field(default=8, ge=1, le=24)

    @model_validator(mode="after")
    def validate_configuration(self):
        if self.mongo_mode == "local":
            self.validate_local_mongo()
        else:
            self.validate_atlas()
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
