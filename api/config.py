"""Runtime configuration for the ingestion API."""

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    """Configuration read from environment variables, never from source control."""

    storage_connection_string: str | None
    storage_account_url: str | None
    queue_name: str
    transactions_table_name: str
    request_limit_per_minute: int
    max_payload_bytes: int

    @classmethod
    def from_environment(cls) -> "Settings":
        return cls(
            storage_connection_string=os.getenv("AZURE_STORAGE_CONNECTION_STRING"),
            storage_account_url=os.getenv("AZURE_STORAGE_ACCOUNT_URL"),
            queue_name=os.getenv("TRANSACTIONS_QUEUE_NAME", "transacciones-pendientes"),
            transactions_table_name=os.getenv("TRANSACTIONS_TABLE_NAME", "transacciones"),
            request_limit_per_minute=int(os.getenv("REQUEST_LIMIT_PER_MINUTE", "100")),
            max_payload_bytes=int(os.getenv("MAX_PAYLOAD_BYTES", "102400")),
        )
