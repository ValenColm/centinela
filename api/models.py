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
