# API Contracts: Payment-Gateway Settlement

**Feature**: `007-payment-gateway-settlement` | **Date**: 2026-04-28

---

## New Endpoints

### `POST /api/v1/debts/{debt_id}/pay-online`

Debtor initiates an online payment for a debt. Transitions `active/overdue → payment_pending_confirmation`, creates a `payment_intents` record, and returns a gateway checkout URL.

**Auth**: Bearer JWT (Supabase). Caller must be the **debtor** of the debt.

**Path params**:
- `debt_id` (string, uuid)

**Request body**: none

**Responses**:

| Status | Body | Condition |
|---|---|---|
| 200 | `PayOnlineOut` | Checkout URL created successfully |
| 403 | `{detail: "Only the debtor can initiate online payment"}` | Caller is not the debtor |
| 409 | `{detail: "payment_in_progress"}` | A pending intent exists (not yet expired) |
| 409 | `{detail: "Debt must be active or overdue"}` | Wrong debt state |
| 503 | `{detail: "payment_gateway_unavailable"}` | Provider call failed |

**`PayOnlineOut` schema**:
```json
{
  "payment_intent_id": "uuid",
  "checkout_url": "https://checkout.tap.company/...",
  "amount": 100.00,
  "fee": 2.75,
  "net_amount": 97.25,
  "currency": "SAR",
  "expires_at": "2026-04-28T12:30:00Z"
}
```

---

### `POST /api/v1/webhooks/payments`

Receives gateway delivery receipts. Verifies HMAC signature, processes charge outcome, and fires the `payment_pending_confirmation → paid` transition on success.

**Auth**: HMAC-SHA256 signature in `X-Tap-Signature` header (keyed on `TAP_WEBHOOK_SECRET`). No JWT.

**Request body**: Raw JSON from Tap (or mock provider). Key fields used:

```json
{
  "id": "<provider_ref>",
  "status": "CAPTURED",
  "amount": 100.00,
  "fee": 2.75
}
```

**Responses**:

| Status | Body | Condition |
|---|---|---|
| 200 | `{received: true, applied: 1}` | Event processed |
| 200 | `{received: true, applied: 0}` | Unknown `provider_ref` or no-op (idempotent replay) |
| 400 | — | Malformed JSON |
| 403 | — | Invalid signature |

**Tap status → internal action mapping**:

| Tap `status` | Action |
|---|---|
| `CAPTURED` | `payment_confirmed` (debt → paid) |
| `DECLINED` / `FAILED` / `CANCELLED` | `payment_failed` (intent failed, debt stays in `payment_pending_confirmation`) |

---

### `GET /api/v1/debts/{debt_id}/payment-intent`

Returns the current (most recent) payment intent for a debt, used by the post-payment return page to poll for completion.

**Auth**: Bearer JWT. Caller must be debtor or creditor.

**Responses**:

| Status | Body | Condition |
|---|---|---|
| 200 | `PaymentIntentOut` | Intent found |
| 404 | — | No intent exists for this debt |
| 403 | — | Caller is not debtor or creditor |

**`PaymentIntentOut` schema**:
```json
{
  "id": "uuid",
  "debt_id": "uuid",
  "provider": "tap",
  "status": "pending",
  "amount": 100.00,
  "fee": 2.75,
  "net_amount": 97.25,
  "created_at": "2026-04-28T12:00:00Z",
  "expires_at": "2026-04-28T12:30:00Z",
  "completed_at": null
}
```

---

## Modified Endpoints

### `POST /api/v1/debts/{debt_id}/confirm-payment` (existing, unchanged)

The manual creditor confirmation path is **not modified**. It continues to work for cash payments.

The `payment_confirmed` event written by this endpoint and the gateway webhook use the **same event type** to enable equivalence testing per FR-007 / SC-003.

---

## Provider Interface (internal)

```python
class PaymentProvider(ABC):
    @abstractmethod
    def create_checkout(self, debt_id: str, amount: Decimal, currency: str,
                        redirect_url: str, order_ref: str) -> CheckoutSession:
        """Returns CheckoutSession(checkout_url, provider_ref, fee)."""

    @abstractmethod
    def verify_signature(self, raw_body: bytes, signature_header: str) -> bool:
        """True if HMAC-SHA256 matches TAP_WEBHOOK_SECRET."""

    @abstractmethod
    def parse_webhook_event(self, raw_body: bytes) -> WebhookEvent:
        """Returns WebhookEvent(provider_ref, status, amount, fee)."""

    @abstractmethod
    def calculate_fee(self, amount: Decimal) -> Decimal:
        """Returns provider fee for a given gross amount."""
```
