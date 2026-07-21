import json
import os
from datetime import datetime, timedelta, timezone
from enum import Enum

from azure.data.tables import TableServiceClient, TableEntity
from azure.identity import DefaultAzureCredential

from .models import (
    AuditEntry,
    Case,
    CaseStatus,
    ConfigEntry,
    Location,
    Merchant,
    RuleResult,
    Transaction,
)


def _get_service_client() -> TableServiceClient:
    conn_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    if conn_str:
        return TableServiceClient.from_connection_string(conn_str)

    account_name = os.getenv("AZURE_STORAGE_ACCOUNT")
    if account_name:
        table_url = f"https://{account_name}.table.core.windows.net"
        return TableServiceClient(endpoint=table_url, credential=DefaultAzureCredential())

    raise ValueError(
        "Neither AZURE_STORAGE_CONNECTION_STRING nor AZURE_STORAGE_ACCOUNT is set"
    )


TABLE_TRANSACCIONES = "transacciones"
TABLE_CASOS = "casos"
TABLE_CONFIG = "configuracion"


# ── Transacciones ────────────────────────────────────────


def entity_to_transaction(entity: dict) -> Transaction:
    return Transaction(
        transaction_id=entity["RowKey"],
        account_id=entity["PartitionKey"],
        amount=float(entity.get("amount", 0)),
        currency=entity.get("currency", "COP"),
        timestamp=entity.get("timestamp", entity.get("Timestamp", datetime.now(timezone.utc))),
        location=json.loads(entity.get("location_json", "{}")),
        merchant=json.loads(entity.get("merchant_json", "{}")),
        device_id=entity.get("device_id", ""),
    )


def insertar_transaccion(transaction: Transaction) -> None:
    entity = TableEntity(
        PartitionKey=transaction.account_id,
        RowKey=transaction.transaction_id,
        amount=transaction.amount,
        currency=transaction.currency,
        timestamp=transaction.timestamp.isoformat(),
        location_json=transaction.location.model_dump_json(),
        merchant_json=transaction.merchant.model_dump_json(),
        device_id=transaction.device_id,
    )
    client = _get_service_client()
    table = client.get_table_client(TABLE_TRANSACCIONES)
    table.upsert_entity(entity)


def query_historial_por_cuenta(
    account_id: str, minutos: int
) -> list[Transaction]:
    since = (datetime.now(timezone.utc) - timedelta(minutes=minutos)).isoformat()
    filter_str = f"PartitionKey eq '{account_id}' and timestamp gt '{since}'"
    client = _get_service_client()
    table = client.get_table_client(TABLE_TRANSACCIONES)
    entities = table.query_entities(filter_str)
    return [entity_to_transaction(e) for e in entities]


def query_historial_completo(account_id: str) -> list[Transaction]:
    client = _get_service_client()
    table = client.get_table_client(TABLE_TRANSACCIONES)
    entities = table.query_entities(f"PartitionKey eq '{account_id}'")
    return [entity_to_transaction(e) for e in entities]


def query_ultima_transaccion(account_id: str) -> Transaction | None:
    historial = query_historial_completo(account_id)
    if not historial:
        return None
    return max(historial, key=lambda t: t.timestamp)


# ── Casos ────────────────────────────────────────────────


def _entity_to_case(entity: dict) -> Case:
    return Case(
        case_id=entity["RowKey"],
        transaction_id=entity.get("transaction_id", ""),
        account_id=entity.get("account_id", ""),
        score=int(entity.get("score", 0)),
        umbral=int(entity.get("umbral", 0)),
        reglas_disparadas=[
            RuleResult(**r) for r in json.loads(entity.get("reglas_json", "[]"))
        ],
        explicacion=entity.get("explicacion", ""),
        estado=CaseStatus(entity.get("estado", "abierto")),
        analista_asignado=entity.get("analista_asignado") or None,
        documentos=json.loads(entity.get("documentos_json", "[]")),
        audit_log=[
            AuditEntry(**a) for a in json.loads(entity.get("audit_json", "[]"))
        ],
        creado_en=entity.get("creado_en", datetime.now(timezone.utc)),
        actualizado_en=entity.get("actualizado_en", datetime.now(timezone.utc)),
    )


def insertar_caso(caso: Case) -> None:
    entity = TableEntity(
        PartitionKey=caso.case_id,
        RowKey=caso.case_id,
        transaction_id=caso.transaction_id,
        account_id=caso.account_id,
        score=caso.score,
        umbral=caso.umbral,
        reglas_json=json.dumps(
            [r.model_dump(mode="json") for r in caso.reglas_disparadas]
        ),
        explicacion=caso.explicacion,
        estado=caso.estado.value,
        analista_asignado=caso.analista_asignado or "",
        documentos_json=json.dumps(caso.documentos),
        audit_json=json.dumps(
            [a.model_dump(mode="json") for a in caso.audit_log]
        ),
        creado_en=caso.creado_en.isoformat(),
        actualizado_en=caso.actualizado_en.isoformat(),
    )
    client = _get_service_client()
    table = client.get_table_client(TABLE_CASOS)
    table.upsert_entity(entity)


def query_casos(estado: str | None = None) -> list[Case]:
    client = _get_service_client()
    table = client.get_table_client(TABLE_CASOS)
    if estado:
        entities = table.query_entities(f"estado eq '{estado}'")
    else:
        entities = table.query_entities("")
    return [_entity_to_case(e) for e in entities]


def obtener_caso(case_id: str) -> Case | None:
    client = _get_service_client()
    table = client.get_table_client(TABLE_CASOS)
    try:
        entity = table.get_entity(partition_key=case_id, row_key=case_id)
        return _entity_to_case(entity)
    except Exception:
        return None


def actualizar_caso(case_id: str, updates: dict) -> None:
    entity = TableEntity(PartitionKey=case_id, RowKey=case_id)
    for key, value in updates.items():
        if isinstance(value, datetime):
            entity[key] = value.isoformat()
        elif isinstance(value, list):
            entity[key] = json.dumps(
                [v.model_dump(mode="json") if hasattr(v, "model_dump") else v for v in value]
            )
        elif isinstance(value, Enum):
            entity[key] = value.value
        else:
            entity[key] = value
    client = _get_service_client()
    table = client.get_table_client(TABLE_CASOS)
    table.upsert_entity(entity)


# ── Configuración ────────────────────────────────────────


def leer_config(config_type: str, config_key: str) -> ConfigEntry | None:
    client = _get_service_client()
    table = client.get_table_client(TABLE_CONFIG)
    try:
        entity = table.get_entity(partition_key=config_type, row_key=config_key)
        return ConfigEntry(
            config_type=entity["PartitionKey"],
            config_key=entity["RowKey"],
            config_value=entity.get("config_value", ""),
        )
    except Exception:
        return None


def guardar_config(config_type: str, config_key: str, config_value: str) -> None:
    entity = TableEntity(
        PartitionKey=config_type,
        RowKey=config_key,
        config_value=config_value,
    )
    client = _get_service_client()
    table = client.get_table_client(TABLE_CONFIG)
    table.upsert_entity(entity)


def listar_config_por_tipo(config_type: str) -> list[ConfigEntry]:
    client = _get_service_client()
    table = client.get_table_client(TABLE_CONFIG)
    entities = table.query_entities(f"PartitionKey eq '{config_type}'")
    return [
        ConfigEntry(
            config_type=e["PartitionKey"],
            config_key=e["RowKey"],
            config_value=e.get("config_value", ""),
        )
        for e in entities
    ]
