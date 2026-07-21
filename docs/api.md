# Centinela Ingestion API

The ingestion API accepts financial transactions and immediately acknowledges them. Fraud scoring is asynchronous: the API writes the accepted transaction to Table Storage and publishes it to Azure Queue Storage for the scoring component.

Base path: `/api`

## POST `/api/transacciones`

Accepts a transaction for asynchronous scoring. The API generates `transaction_id`; clients must not send it.

```json
{
  "account_id": "account-001",
  "amount": 1234.50,
  "currency": "COP",
  "timestamp": "2026-07-14T12:00:00Z",
  "location": {
    "city": "Medellin",
    "country": "CO",
    "latitude": 6.2476,
    "longitude": -75.5658
  },
  "merchant": {
    "id": "M001",
    "name": "Store",
    "category": "retail"
  },
  "device_id": "8f3e8327-0f42-4f13-a3b3-5994ce6e4dd8"
}
```

Successful response (`202 Accepted`):

```json
{
  "transaction_id": "c3926432-ff11-48d4-b0be-6a90b36837e1",
  "status": "accepted"
}
```

Validation errors return `422`. Payloads larger than 100 KB return `413`. If the transaction cannot be published for scoring, the API returns `503` and records `queue_failed` for operational follow-up.

## GET `/api/transacciones/{transaction_id}`

Returns the stored transaction and its current processing status.

- `200 OK`: transaction exists.
- `404 Not Found`: no transaction exists with that UUID.

## Operational limits

- Maximum request body: 100 KB.
- Rate limit: 100 requests per minute per source IP. Exceeded requests return `429 Too Many Requests` with `Retry-After`.
- Every request logs its IP, method, endpoint, response status, and duration. Request bodies and secrets are never logged.

## Runtime configuration

| Variable | Purpose |
| --- | --- |
| `AZURE_STORAGE_CONNECTION_STRING` | Local development Storage connection string. |
| `AZURE_STORAGE_ACCOUNT_URL` | Azure Storage account URL for Managed Identity authentication in Azure. |
| `TRANSACTIONS_QUEUE_NAME` | Queue name; defaults to `transacciones-pendientes`. |
| `TRANSACTIONS_TABLE_NAME` | Table name; defaults to `transacciones`. |
| `REQUEST_LIMIT_PER_MINUTE` | Per-instance request limit; defaults to `100`. |
| `MAX_PAYLOAD_BYTES` | Maximum request size; defaults to `102400`. |

Use only one of `AZURE_STORAGE_CONNECTION_STRING` and `AZURE_STORAGE_ACCOUNT_URL`. Production Functions should use `AZURE_STORAGE_ACCOUNT_URL` with Managed Identity.
