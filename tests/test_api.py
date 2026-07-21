from datetime import datetime, timezone

from fastapi.testclient import TestClient

from api.adapters import InMemoryQueuePublisher, InMemoryTransactionRepository
from api.config import Settings
from api.main import create_app
from api.services import TransactionService


def make_client(*, limit: int = 100, max_bytes: int = 102400):
    app = create_app(
        Settings(
            storage_connection_string=None,
            storage_account_url=None,
            queue_name="transacciones-pendientes",
            transactions_table_name="transacciones",
            request_limit_per_minute=limit,
            max_payload_bytes=max_bytes,
        )
    )
    repository = InMemoryTransactionRepository()
    publisher = InMemoryQueuePublisher()
    app.state.transaction_service = TransactionService(repository, publisher)
    return TestClient(app), repository, publisher


def valid_payload():
    return {
        "account_id": "account-001",
        "amount": "1234.50",
        "currency": "COP",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "location": {"city": "Medellin", "country": "CO", "latitude": 6.2476, "longitude": -75.5658},
        "merchant": {"id": "M001", "name": "Store", "category": "retail"},
        "device_id": "8f3e8327-0f42-4f13-a3b3-5994ce6e4dd8",
    }


def test_accepts_persists_and_queues_a_valid_transaction():
    client, repository, publisher = make_client()
    response = client.post("/api/transacciones", json=valid_payload())

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "accepted"
    assert body["transaction_id"] in repository.records
    assert publisher.messages[0]["transaction_id"] == body["transaction_id"]
    assert publisher.messages[0]["received_at"]


def test_returns_a_stored_transaction_and_404_for_unknown_id():
    client, _, _ = make_client()
    accepted = client.post("/api/transacciones", json=valid_payload()).json()

    found = client.get(f"/api/transacciones/{accepted['transaction_id']}")
    missing = client.get("/api/transacciones/7e117dd1-dfb4-4f2f-9d60-577cec65d59c")

    assert found.status_code == 200
    assert found.json()["transaction_id"] == accepted["transaction_id"]
    assert missing.status_code == 404


def test_rejects_invalid_payloads_with_422():
    client, _, _ = make_client()
    payload = valid_payload()
    payload["amount"] = "0"
    payload["location"]["latitude"] = 91

    response = client.post("/api/transacciones", json=payload)
    assert response.status_code == 422


def test_rejects_payload_larger_than_100_kb():
    client, _, _ = make_client(max_bytes=100)
    response = client.post("/api/transacciones", content=b"x" * 101, headers={"content-type": "application/json"})

    assert response.status_code == 413


def test_limits_requests_per_ip():
    client, _, _ = make_client(limit=2)

    assert client.get("/docs").status_code == 200
    assert client.get("/docs").status_code == 200
    response = client.get("/docs")

    assert response.status_code == 429
    assert response.headers["Retry-After"]
