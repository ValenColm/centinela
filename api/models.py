"""Request and response contracts for transaction ingestion."""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator


NonEmptyText = Annotated[
    str, StringConstraints(min_length=1, max_length=120, strip_whitespace=True)
]
CurrencyCode = Annotated[str, Field(pattern=r"^[A-Z]{3}$")]
CountryCode = Annotated[str, Field(pattern=r"^[A-Z]{2}$")]


class Location(BaseModel):
    model_config = ConfigDict(extra="forbid")

    city: NonEmptyText
    country: CountryCode
    latitude: Annotated[Decimal, Field(ge=-90, le=90)]
    longitude: Annotated[Decimal, Field(ge=-180, le=180)]


class Merchant(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: NonEmptyText
    name: NonEmptyText
    category: NonEmptyText


class TransactionCreate(BaseModel):
    """Payload accepted from the fintech. The server owns transaction_id."""

    model_config = ConfigDict(extra="forbid")

    account_id: NonEmptyText
    amount: Annotated[Decimal, Field(gt=0, max_digits=18, decimal_places=2)]
    currency: CurrencyCode
    timestamp: datetime
    location: Location
    merchant: Merchant
    device_id: UUID

    @field_validator("timestamp")
    @classmethod
    def timestamp_must_be_utc_or_offset_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must include a timezone offset")
        if value.astimezone(timezone.utc) > datetime.now(timezone.utc):
            raise ValueError("timestamp cannot be in the future")
        return value.astimezone(timezone.utc)


class AcceptedTransaction(BaseModel):
    transaction_id: UUID
    status: str = "accepted"


class TransactionRecord(TransactionCreate):
    transaction_id: UUID
    received_at: datetime
    status: str
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class UserSession(BaseModel):
    username: str
    name: str
    role: str

class RuleConfig(BaseModel):
    nombre: str
    puntos: int
    activa: bool

class MerchantConfig(BaseModel):
    merchant_id: str
    name: str
    category: str

class SystemConfig(BaseModel):
    umbral: int = 60
    reglas: List[RuleConfig] = []
    comercios: List[MerchantConfig] = []

class AuditLogEntry(BaseModel):
    fecha: str
    usuario: str
    accion: str
    detalle: str

class RuleEvidence(BaseModel):
    regla: str
    puntos: int
    disparada: bool
    evidencia: Dict[str, Any]

class Case(BaseModel):
    case_id: str
    transaction_id: str
    account_id: str
    score: int
    monto: float
    explicacion: str
    estado: str  # abierto, en_revision, resuelto_fraude, resuelto_descarte, escalado
    documentos: List[str] = []
    audit_log: List[AuditLogEntry] = []
    reglas_disparadas: List[RuleEvidence] = []
    creado_en: str
