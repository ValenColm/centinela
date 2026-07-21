import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from persistence import (
    guardar_config,
    leer_config,
    listar_config_por_tipo,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ── Umbral ──────────────────────────────────────────


class UmbralRequest(BaseModel):
    umbral: int


@router.get("/umbral")
def get_umbral():
    entry = leer_config("umbral", "score_threshold")
    if not entry:
        return {"umbral": 60}
    return {"umbral": int(entry.config_value)}


@router.put("/umbral")
def put_umbral(body: UmbralRequest):
    if body.umbral < 0 or body.umbral > 100:
        raise HTTPException(400, "El umbral debe estar entre 0 y 100")
    guardar_config("umbral", "score_threshold", str(body.umbral))
    return {"umbral": body.umbral}


# ── Reglas ──────────────────────────────────────────


class ReglaParams(BaseModel):
    enabled: bool
    parametros: dict | None = None


@router.get("/reglas")
def listar_reglas():
    entries = listar_config_por_tipo("regla")
    if not entries:
        return {
            "reglas": {
                "velocidad_transaccion": {
                    "enabled": True,
                    "parametros": {"umbral_velocidad": 5, "ventana_minutos": 3, "puntos": 35},
                },
                "monto_atipico": {
                    "enabled": True,
                    "parametros": {"factor": 2.0, "puntos": 30},
                },
                "ubicacion_imposible": {
                    "enabled": True,
                    "parametros": {"velocidad_max_kmh": 900, "puntos": 17},
                },
                "comercio_riesgo": {
                    "enabled": True,
                    "parametros": {"puntos": 20},
                },
            }
        }
    reglas = {}
    for e in entries:
        reglas[e.config_key] = json.loads(e.config_value)
    return {"reglas": reglas}


@router.get("/reglas/{nombre}")
def get_regla(nombre: str):
    entry = leer_config("regla", nombre)
    if not entry:
        raise HTTPException(404, f"Regla '{nombre}' no encontrada")
    return json.loads(entry.config_value)


@router.put("/reglas/{nombre}")
def put_regla(nombre: str, body: ReglaParams):
    valor = json.dumps(body.model_dump())
    guardar_config("regla", nombre, valor)
    return {"regla": nombre, **body.model_dump()}


# ── Comercios de riesgo ──────────────────────────────


class ComercioRiesgoRequest(BaseModel):
    merchant_id: str = ""
    categoria: str = ""
    nombre: str = ""
    motivo: str = ""


@router.get("/comercios")
def listar_comercios():
    entries = listar_config_por_tipo("comercio_riesgo")
    comercios = []
    for e in entries:
        comercios.append(json.loads(e.config_value))
    return {"comercios": comercios}


@router.post("/comercios")
def crear_comercio(body: ComercioRiesgoRequest):
    if not body.merchant_id and not body.categoria:
        raise HTTPException(400, "Debe especificar merchant_id o categoria")
    key = body.merchant_id or body.categoria
    valor = json.dumps(body.model_dump())
    guardar_config("comercio_riesgo", key, valor)
    return {"mensaje": "Comercio registrado como riesgo", "comercio": body.model_dump()}


@router.delete("/comercios/{key}")
def eliminar_comercio(key: str):
    from persistence.repository import _get_service_client

    client = _get_service_client()
    table = client.get_table_client("Configuracion")
    try:
        table.delete_entity(partition_key="comercio_riesgo", row_key=key)
        return {"mensaje": f"Comercio '{key}' eliminado"}
    except Exception:
        raise HTTPException(404, f"Comercio '{key}' no encontrado")
