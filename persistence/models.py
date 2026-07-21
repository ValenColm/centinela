from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from enum import Enum


class Location(BaseModel):
    city: str
    country: str
    latitude: float
    longitude: float


class Merchant(BaseModel):
    id: str
    name: str
    category: str


class Transaction(BaseModel):
    transaction_id: str
    account_id: str
    amount: float
    currency: str
    timestamp: datetime
    location: Location
    merchant: Merchant
    device_id: str


class TransactionEvent(BaseModel):
    transaction_id: str
    account_id: str
    amount: float
    currency: str
    timestamp: datetime
    location: Location
    merchant: Merchant
    device_id: str
    received_at: datetime


class RuleResult(BaseModel):
    regla: str
    puntos: int
    disparada: bool
    evidencia: dict


class ScoreResult(BaseModel):
    transaction_id: str
    account_id: str
    score: int
    umbral: int
    reglas: list[RuleResult]
    decision: str


class CaseStatus(str, Enum):
    abierto = "abierto"
    en_revision = "en_revision"
    resuelto_fraude = "resuelto_fraude"
    resuelto_descarte = "resuelto_descarte"
    escalado = "escalado"


class AuditEntry(BaseModel):
    fecha: datetime
    usuario: str
    accion: str
    detalle: str


class Case(BaseModel):
    case_id: str
    transaction_id: str
    account_id: str
    score: int
    umbral: int
    reglas_disparadas: list[RuleResult]
    explicacion: str = ""
    estado: CaseStatus = CaseStatus.abierto
    analista_asignado: Optional[str] = None
    documentos: list[str] = Field(default_factory=list)
    audit_log: list[AuditEntry] = Field(default_factory=list)
    creado_en: datetime
    actualizado_en: datetime


class ConfigEntry(BaseModel):
    config_type: str
    config_key: str
    config_value: str
