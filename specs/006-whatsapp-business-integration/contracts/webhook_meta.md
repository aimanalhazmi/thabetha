# Contract — `POST /api/v1/webhooks/whatsapp` (inbound delivery callbacks)

**Endpoint**: `POST /api/v1/webhooks/whatsapp`
**Auth**: HMAC SHA-256 over the raw request body, keyed by `WHATSAPP_WEBHOOK_SECRET`. Header: `X-Hub-Signature-256: sha256=<hex>`. **No** Supabase JWT — this is a third-party callback.
**Content-Type**: `application/json` (Meta-defined).
**Idempotency**: keyed on `whatsapp_provider_ref` derived from `entry[].changes[].value.statuses[].id`. Duplicate callbacks are no-ops (FR-014).

The endpoint must also handle Meta's verification handshake on `GET /api/v1/webhooks/whatsapp`:

---

## GET — verification handshake

```
GET /api/v1/webhooks/whatsapp?hub.mode=subscribe&hub.verify_token=<token>&hub.challenge=<int>
```

- If `hub.mode == "subscribe"` and `hub.verify_token == WHATSAPP_VERIFY_TOKEN` → respond `200 OK` with body = `hub.challenge` (plain text, integer).
- Otherwise → respond `403 Forbidden`.

`WHATSAPP_VERIFY_TOKEN` is a separate env var from the webhook secret; it is the value entered in the Meta dashboard at subscription time.

---

## POST — delivery callback

### Request shape (Meta's "messages" webhook, abbreviated)

```json
{
  "object": "whatsapp_business_account",
  "entry": [
    {
      "id": "<waba_id>",
      "changes": [
        {
          "field": "messages",
          "value": {
            "messaging_product": "whatsapp",
            "statuses": [
              {
                "id": "wamid.XXXXXX",
                "status": "delivered",
                "timestamp": "1714291200",
                "recipient_id": "9665XXXXXXXX",
                "errors": [
                  { "code": 131026, "title": "Message undeliverable", "message": "..." }
                ]
              }
            ]
          }
        }
      ]
    }
  ]
}
```

Only `entry[].changes[]` with `field == "messages"` and a `value.statuses[]` array are relevant for this feature. Other variants (replies, message-template-status updates) are ignored — out of scope.

### Response

| Condition | HTTP | Body |
|---|---|---|
| Signature verifies AND payload parses | `200 OK` | `{"received": true}` |
| Signature missing or invalid | `403 Forbidden` | empty |
| Body cannot be parsed as JSON | `400 Bad Request` | empty |
| Unknown `provider_ref` | `200 OK` | `{"received": true, "applied": 0}` (no-op, idempotent) |
| DB write fails | `500 Internal Server Error` | empty (Meta will retry) |

Meta retries on non-2xx, so we MUST return 200 even when there is nothing to do (idempotent no-op for unknown ids).

### Handler algorithm

```text
1. raw = await request.body()
2. signature = request.headers.get("X-Hub-Signature-256", "")
3. if not provider.verify_webhook_signature(raw, signature):
       return 403
4. payload = json.loads(raw)            # 400 on JSONDecodeError
5. updates = provider.parse_status_callback(payload)
6. for update in updates:
       repo.apply_whatsapp_status(update)   # idempotent forward-only
7. return 200
```

`repo.apply_whatsapp_status(update)` performs (in one statement):

```sql
UPDATE notifications
   SET whatsapp_delivered = CASE
         WHEN :status = 'delivered' THEN true
         WHEN :status = 'failed' AND COALESCE(whatsapp_delivered, false) = false THEN false
         ELSE whatsapp_delivered
       END,
       whatsapp_failed_reason = CASE
         WHEN :status = 'failed' AND whatsapp_failed_reason IS NULL THEN :failed_reason
         ELSE whatsapp_failed_reason
       END,
       whatsapp_status_received_at = COALESCE(whatsapp_status_received_at, :occurred_at)
 WHERE whatsapp_provider_ref = :provider_ref;
```

This makes the callback idempotent (a duplicate `delivered` is a no-op; a `failed` after `delivered` is a no-op) and preserves the first-delivery timestamp.

### Security properties

- **Signature MUST be verified before any DB read or write.** Step 3 short-circuits; step 4 onward never runs on an unverified payload.
- **Constant-time comparison** is provided by `provider.verify_webhook_signature` (per ABC contract §3).
- **No write on unknown `provider_ref`** prevents an attacker who somehow forges a signature from creating new rows.
- **No reflection of payload content** in error responses — bodies are empty on error to avoid information disclosure.

### Logging

- Log one INFO line per successful callback with: `provider_ref`, `status`, `applied: 0|1`.
- Log one WARN line per signature failure with: `signature_present: bool`, `body_len`. **Never** log the body itself (PII).
- Log ERROR on DB write failure with the SQLSTATE.

### Tests required (link to plan §test layout)

- `test_webhooks_whatsapp.py::test_signature_valid_applies_status` — happy path.
- `test_webhooks_whatsapp.py::test_signature_invalid_returns_403` — auth failure.
- `test_webhooks_whatsapp.py::test_signature_missing_returns_403` — header absent.
- `test_webhooks_whatsapp.py::test_unknown_provider_ref_is_noop` — applied=0, status 200.
- `test_webhooks_whatsapp.py::test_duplicate_callback_idempotent` — second call leaves row unchanged.
- `test_webhooks_whatsapp.py::test_failed_after_delivered_is_noop` — forward-only enforcement.
- `test_webhooks_whatsapp.py::test_get_verification_handshake_ok_and_403`.
