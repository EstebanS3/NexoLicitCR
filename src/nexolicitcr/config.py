from typing import Literal
from urllib.parse import parse_qs, urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)

    atlas_uri: SecretStr
    atlas_usuario: SecretStr
    atlas_clave: SecretStr
    atlas_base: str = Field(pattern=r"^[a-zA-Z][a-zA-Z0-9_-]{0,62}$")
    atlas_authdb: str = Field(default="admin", pattern=r"^[a-zA-Z][a-zA-Z0-9_-]{0,62}$")
    app_mode: Literal["local", "server"] = "local"
    public_origin: str = "http://localhost:8000"
    sicop_timezone: str = ""
    redis_url: SecretStr = SecretStr("")
    mongo_timeout_ms: int = Field(default=5000, ge=500, le=30000)
    session_hours: int = Field(default=8, ge=1, le=24)

    @model_validator(mode="after")
    def validate_configuration(self):
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

    @property
    def secure_cookies(self) -> bool:
        return self.public_origin.startswith("https://")
