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
