import hashlib
import json
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)


class CatalogItem(Contract):
    name: str = Field(min_length=2, max_length=160)
    description: str = Field(default="", max_length=4000)
    capabilities: str = Field(default="", max_length=4000)
    coverage: str = Field(default="", max_length=500)
    keywords: list[str] = Field(default_factory=list, max_length=40)
    exclusions: list[str] = Field(default_factory=list, max_length=40)
    classification_system: str = Field(default="", max_length=100)
    classification_code: str = Field(default="", max_length=100)
    active: bool = True

    @model_validator(mode="after")
    def validate_terms(self):
        if bool(self.classification_code) != bool(self.classification_system):
            raise ValueError("Código y sistema de clasificación deben indicarse juntos")
        for terms in (self.keywords, self.exclusions):
            if any(not t.strip() or len(t) > 100 for t in terms):
                raise ValueError("Términos inválidos")
        return self


class SourceDate(Contract):
    raw: str | None = None
    utc: datetime | None = None
    assumed_timezone: str | None = None


class TenderLine(Contract):
    lot: str
    number: str
    product_code: str | None = None
    description: str
    quantity: Decimal | None = None
    unit: str | None = None
    currency: str | None = None
    budget_unit_price: Decimal | None = None
    budget_total: Decimal | None = None


class TenderFile(Contract):
    number: str
    name: str
    document: str = ""
    file_type: str = ""
    size_mb: Decimal | None = None


class Tender(Contract):
    source: Literal["sicop"] = "sicop"
    source_id: str = Field(pattern=r"^\d{1,30}$")
    sequence: str = Field(pattern=r"^\d{1,5}$")
    procedure: str
    title: str = Field(min_length=1)
    institution: str
    category: Literal["bienes", "obras", "servicios"]
    status_raw: str
    status: Literal["open", "published", "canceled", "closed", "unknown"]
    published: SourceDate
    deadline: SourceDate
    source_version: str | None = None
    conditions: dict[str, str]
    lines: list[TenderLine]
    files: list[TenderFile] = Field(default_factory=list)
    requirements_complete: Literal[False] = False
    warnings: list[str] = Field(default_factory=list)

    @property
    def key(self) -> str:
        return f"{self.source_id}:{self.sequence}"

    @property
    def source_url(self) -> str:
        return (
            "https://www.sicop.go.cr/app/module/bid/public/cartel-specification-published"
            f"?cartelNo={self.source_id}&cartelSeq={self.sequence}"
        )

    def fingerprint(self) -> str:
        payload = self.model_dump(mode="json")
        # Source version and observation time are metadata, not substantive content.
        payload.pop("source_version")
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()


class Award(Contract):
    """Línea adjudicada según el reporte de datos abiertos de SICOP (sin fecha de adjudicación)."""

    source: Literal["sicop-datos-abiertos"] = "sicop-datos-abiertos"
    procedure: str = Field(min_length=1)
    title: str
    institution: str
    procedure_type: str
    modality: str
    object_class: str
    lot: str
    number: str
    supplier: str = Field(min_length=1)
    currency: str | None = None
    amount: Decimal | None = None
    exchange_rate: Decimal | None = None
    amount_crc: Decimal | None = None
    status_raw: str

    @property
    def key(self) -> str:
        # El reporte repite filas y a veces varía solo el tipo de cambio: la línea adjudicada
        # a un proveedor es la identidad; el resto es contenido versionable.
        raw = "|".join((self.procedure, self.lot, self.number, self.supplier))
        return hashlib.sha256(raw.encode()).hexdigest()[:32]

    def fingerprint(self) -> str:
        return hashlib.sha256(
            json.dumps(self.model_dump(mode="json"), sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()
