"""FastAPI application exposed through Azure Functions ASGI."""

import logging
from uuid import UUID

from fastapi import FastAPI, HTTPException, status

from api.adapters import (
    AzureQueuePublisher,
    AzureTableTransactionRepository,
    InMemoryQueuePublisher,
    InMemoryTransactionRepository,
)
from api.config import Settings
from api.middleware import PayloadTooLargeMiddleware, SlidingWindowRateLimiter, request_controls_and_logging
from api.models import AcceptedTransaction, TransactionCreate, TransactionRecord
from api.services import TransactionService

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


def build_service(settings: Settings) -> TransactionService:
    if settings.storage_connection_string or settings.storage_account_url:
        return TransactionService(
            AzureTableTransactionRepository(settings), AzureQueuePublisher(settings)
        )
    return TransactionService(InMemoryTransactionRepository(), InMemoryQueuePublisher())


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_environment()
    application = FastAPI(title="Centinela Ingestion API", version="1.0.0")
    application.state.transaction_service = build_service(settings)
    application.state.rate_limiter = SlidingWindowRateLimiter(settings.request_limit_per_minute)
    application.add_middleware(PayloadTooLargeMiddleware, max_bytes=settings.max_payload_bytes)
    application.middleware("http")(request_controls_and_logging)

    @application.post(
        "/api/transacciones",
        response_model=AcceptedTransaction,
        status_code=status.HTTP_202_ACCEPTED,
    )
    def create_transaction(transaction: TransactionCreate) -> AcceptedTransaction:
        try:
            record = application.state.transaction_service.accept(transaction)
        except Exception as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Transaction could not be queued for scoring",
            ) from error
        return AcceptedTransaction(transaction_id=record["transaction_id"])

    @application.get("/api/transacciones/{transaction_id}", response_model=TransactionRecord)
    def get_transaction(transaction_id: UUID) -> TransactionRecord:
        record = application.state.transaction_service.get(transaction_id)
        if record is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
        return TransactionRecord.model_validate(record)

    return application


app = create_app()
