"""Storage and messaging adapters for Azure and local tests."""

from __future__ import annotations

from collections.abc import Iterable
import json
from typing import Any, Protocol
from uuid import UUID

from azure.core.exceptions import ResourceNotFoundError
from azure.data.tables import TableServiceClient
from azure.identity import DefaultAzureCredential
from azure.storage.queue import QueueClient

from api.config import Settings


class TransactionRepository(Protocol):
    def create(self, record: dict[str, Any]) -> None: ...

    def get(self, transaction_id: UUID) -> dict[str, Any] | None: ...

    def update_status(self, transaction_id: UUID, status: str) -> None: ...


class QueuePublisher(Protocol):
    def publish(self, message: dict[str, Any]) -> None: ...


class AzureTableTransactionRepository:
    """Table Storage repository, partitioned by account_id as defined by Centinela."""

    def __init__(self, settings: Settings) -> None:
        if settings.storage_connection_string:
            service = TableServiceClient.from_connection_string(settings.storage_connection_string)
        elif settings.storage_account_url:
            service = TableServiceClient(
                endpoint=settings.storage_account_url,
                credential=DefaultAzureCredential(),
            )
        else:
            raise RuntimeError("Azure Storage configuration is missing")
        self._table = service.get_table_client(settings.transactions_table_name)
        self._table.create_table_if_not_exists()

    def create(self, record: dict[str, Any]) -> None:
        entity = {
            "PartitionKey": record["account_id"],
            "RowKey": record["transaction_id"],
            "payload": json.dumps(record, default=str),
            "status": record["status"],
        }
        self._table.create_entity(entity)

    def get(self, transaction_id: UUID) -> dict[str, Any] | None:
        entities: Iterable[dict[str, Any]] = self._table.query_entities(
            query_filter=f"RowKey eq '{transaction_id}'",
        )
        entity = next(iter(entities), None)
        return json.loads(entity["payload"]) if entity else None

    def update_status(self, transaction_id: UUID, status: str) -> None:
        record = self.get(transaction_id)
        if not record:
            return
        record["status"] = status
        entity = {
            "PartitionKey": record["account_id"],
            "RowKey": record["transaction_id"],
            "payload": json.dumps(record, default=str),
            "status": status,
        }
        self._table.update_entity(entity, mode="Replace")


class AzureQueuePublisher:
    def __init__(self, settings: Settings) -> None:
        if settings.storage_connection_string:
            self._queue = QueueClient.from_connection_string(
                settings.storage_connection_string, settings.queue_name
            )
        elif settings.storage_account_url:
            queue_url = f"{settings.storage_account_url.rstrip('/')}/{settings.queue_name}"
            self._queue = QueueClient(queue_url, credential=DefaultAzureCredential())
        else:
            raise RuntimeError("Azure Storage configuration is missing")
        self._queue.create_queue()

    def publish(self, message: dict[str, Any]) -> None:
        self._queue.send_message(json.dumps(message, default=str))


class InMemoryTransactionRepository:
    """Deterministic local adapter used by tests and local development."""

    def __init__(self) -> None:
        self.records: dict[str, dict[str, Any]] = {}

    def create(self, record: dict[str, Any]) -> None:
        self.records[record["transaction_id"]] = record.copy()

    def get(self, transaction_id: UUID) -> dict[str, Any] | None:
        record = self.records.get(str(transaction_id))
        return record.copy() if record else None

    def update_status(self, transaction_id: UUID, status: str) -> None:
        record = self.records.get(str(transaction_id))
        if record:
            record["status"] = status


class InMemoryQueuePublisher:
    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []

    def publish(self, message: dict[str, Any]) -> None:
        self.messages.append(message.copy())
