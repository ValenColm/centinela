"""Application services for accepting and retrieving transactions."""

from datetime import datetime, timezone
import logging
from typing import Any
from uuid import UUID, uuid4

from api.adapters import QueuePublisher, TransactionRepository
from api.models import TransactionCreate

logger = logging.getLogger(__name__)


class TransactionService:
    def __init__(self, repository: TransactionRepository, publisher: QueuePublisher) -> None:
        self._repository = repository
        self._publisher = publisher

    def accept(self, transaction: TransactionCreate) -> dict[str, Any]:
        transaction_id = uuid4()
        received_at = datetime.now(timezone.utc)
        record = transaction.model_dump(mode="json") | {
            "transaction_id": str(transaction_id),
            "received_at": received_at.isoformat(),
            "status": "accepted",
        }
        self._repository.create(record)
        try:
            self._publisher.publish(record)
        except Exception:
            self._repository.update_status(transaction_id, "queue_failed")
            logger.exception("Could not publish transaction %s to the scoring queue", transaction_id)
            raise
        return record

    def get(self, transaction_id: UUID) -> dict[str, Any] | None:
        return self._repository.get(transaction_id)
