# Contract — `WhatsAppProvider` (internal ABC)

**Module**: `backend/app/services/whatsapp/provider.py`
**Selected by**: `WHATSAPP_PROVIDER` env var (`mock` | `cloud_api`). Defaulted to `mock` in dev/test.

This is an internal Python contract — not a public REST API. Both implementations (`mock.py`, `cloud_api.py`) MUST satisfy it identically so the dispatcher and tests are provider-agnostic.

---

## Types

```python
class SendOutcome(StrEnum):
    sent = "sent"          # provider accepted; we have a provider_ref
    blocked = "blocked"    # provider rejected for a known reason (invalid number, recipient blocked, template not approved)
    error = "error"        # provider 5xx or network error; transient


@dataclass(frozen=True, slots=True)
class SendRequest:
    to_e164: str            # recipient phone in E.164 (e.g. "+9665XXXXXXXX")
    template_id: str        # Meta template name (post-approval)
    locale: Literal["ar", "en"]
    params: list[str]       # ordered positional substitutions for the template


@dataclass(frozen=True, slots=True)
class SendResult:
    outcome: SendOutcome
    provider_ref: str | None       # set iff outcome == sent
    failed_reason: str | None      # set iff outcome != sent; from the failure codebook
```

The `failed_reason` codebook (string values):
`recipient_blocked`, `invalid_phone`, `template_not_approved`, `template_param_mismatch`, `provider_4xx`, `provider_5xx`, `network_error`, `no_template`, `no_phone_number`.

## Methods

```python
class WhatsAppProvider(ABC):
    @abstractmethod
    def send_template(self, req: SendRequest) -> SendResult: ...

    @abstractmethod
    def verify_webhook_signature(self, raw_body: bytes, signature_header: str) -> bool: ...

    @abstractmethod
    def parse_status_callback(self, payload: dict) -> list[StatusUpdate]: ...
```

```python
@dataclass(frozen=True, slots=True)
class StatusUpdate:
    provider_ref: str
    status: Literal["sent", "delivered", "read", "failed"]
    failed_reason: str | None
    occurred_at: datetime
```

A single inbound webhook body may contain multiple status entries — `parse_status_callback` returns a list (possibly empty) and the dispatcher applies each idempotently.

## Behavioural contract (must hold for every implementation)

1. **Pure on input**: `send_template` MUST NOT mutate any state outside the provider; persistence is the dispatcher's job.
2. **No exceptions for known failures**: provider 4xx/5xx and protocol failures MUST be reported via `SendResult(outcome=error|blocked, failed_reason=...)`. Raising is reserved for genuine programmer errors (e.g. missing config).
3. **Verification is constant-time**: `verify_webhook_signature` MUST use `hmac.compare_digest` and MUST NOT short-circuit on early bytes.
4. **Locale routing is the caller's responsibility**: providers do not pick a locale; the caller passes the chosen `locale` explicitly. Providers that lack a template for the requested locale MUST return `SendResult(outcome=blocked, failed_reason="no_template")` (this case is normally caught earlier by the dispatcher's locale fallback).

## Mock implementation requirements

- Records every call into an in-memory list inspectable by tests via `MockWhatsAppProvider.calls`.
- `send_template` returns `SendResult(outcome=sent, provider_ref=f"mock-{uuid4()}")` by default.
- A test hook lets tests pre-program the next outcome (`mock.set_next_outcome(SendOutcome.error, "provider_5xx")`).
- `verify_webhook_signature` accepts a fixed dev secret; tests assert both true and false outputs.
- `parse_status_callback` accepts the same JSON shape as Cloud API for symmetry.

## Cloud API implementation requirements

- `send_template`:
  - `POST https://graph.facebook.com/v20.0/{WHATSAPP_PHONE_NUMBER_ID}/messages`
  - JSON body uses Meta's template object format with `language.code` set from `req.locale`.
  - On HTTP 200, returns `SendResult(outcome=sent, provider_ref=resp["messages"][0]["id"])`.
  - On HTTP 4xx with a recognised error code, maps to a `failed_reason` from the codebook via a small lookup table; outcome is `blocked`.
  - On HTTP 5xx or network error, returns `SendResult(outcome=error, failed_reason="provider_5xx" | "network_error")`.
- `verify_webhook_signature`:
  - Computes `hmac.new(WHATSAPP_WEBHOOK_SECRET, raw_body, sha256).hexdigest()`.
  - Strips a `sha256=` prefix from the header before comparing constant-time.
- `parse_status_callback`:
  - Walks `entry[].changes[].value.statuses[]` per Meta's documented shape.
  - Returns one `StatusUpdate` per entry; maps Meta's `errors[].code` onto the failure codebook.

## Dispatcher contract (consumer of this ABC)

`backend/app/services/whatsapp/dispatch.py::dispatch_notification(notification: Notification)`:

1. Resolve recipient profile and (for outbound from creditor → debtor) the relevant `merchant_notification_preferences` row.
2. **Preference gate**:
   - If recipient profile `whatsapp_enabled = false` → mark `whatsapp_attempted = false` (i.e. leave it false), return.
   - If per-creditor preference exists and `whatsapp_enabled = false` → same.
3. **Phone gate**: if recipient has no phone number → mark `whatsapp_attempted = true`, `whatsapp_failed_reason = "no_phone_number"`, return.
4. **Template lookup**: pick `(template_id, locale)` from `templates.TEMPLATE_REGISTRY[notification_type][profile.preferred_language]` with fallback to the other locale. If neither exists → `attempted=true, failed_reason="no_template"`.
5. **Build params**: from notification payload (creditor name, amount, currency, debt link).
6. **Call provider** with `try/except`. Persist `SendResult` to the notification row via `repo.mark_whatsapp_attempted(notification_id, result)`.

The dispatcher is the only call site that mutates the new columns at send time; the webhook is the only call site that mutates them on inbound delivery callbacks.
