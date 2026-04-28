# Phase 0 — Research: WhatsApp Business API Integration

**Feature**: `006-whatsapp-business-integration`
**Date**: 2026-04-28

The spec entered Phase 0 with all clarifications resolved (3 of 5 quota used). No `[NEEDS CLARIFICATION]` markers remained, so research focuses on best-practice resolution for vendor and protocol choices implied by the spec.

---

## R-1: Outbound provider — WhatsApp Cloud API vs. Twilio WhatsApp

**Decision**: Use **WhatsApp Cloud API (Meta)** as the default real provider behind the `WhatsAppProvider` ABC. Keep `mock` as the dev/test default. Treat Twilio as a code-level fallback that is *not* implemented in this phase but is unblocked by the ABC.

**Rationale**:
- Cheapest verified-template path for Saudi numbers; no per-message Twilio markup.
- Direct access to delivery callbacks (no double-hop through a CPaaS).
- Single vendor to verify business identity with for the hackathon target.
- Per Clarification Q2: only one provider is active per deployment, so we don't pay the cost of building both implementations in this phase.

**Alternatives considered**:
- **Twilio WhatsApp API** — better DX, faster onboarding for hobby use, but adds an extra US$ markup per message and an extra link in the delivery-receipt chain. Deferred behind the ABC for if business verification stalls (per spec Assumptions).
- **MessageBird / 360dialog** — viable, but smaller ecosystem and no immediate cost win over Meta direct.

---

## R-2: Authentication and webhook signature scheme

**Decision**: Outbound calls use a permanent system user access token (`WHATSAPP_PROVIDER_TOKEN`) sent as `Authorization: Bearer …` to `https://graph.facebook.com/v20.0/{WHATSAPP_PHONE_NUMBER_ID}/messages`. Inbound webhook verification uses HMAC SHA-256 over the **raw request body** keyed by `WHATSAPP_WEBHOOK_SECRET` (Meta calls this the "App Secret"), comparing against the `X-Hub-Signature-256` header in constant time.

**Rationale**:
- Standard Meta pattern; the access token is rotatable from the Meta dashboard without code changes.
- HMAC SHA-256 over the raw body matches Meta's documented mechanism and avoids JSON-canonicalisation pitfalls (we MUST preserve the request body bytes before parsing).
- Constant-time comparison via `hmac.compare_digest` mitigates timing attacks.

**Alternatives considered**:
- Mutual TLS — overkill and not how Meta delivers webhooks.
- Pre-shared bearer token in a custom header — simpler for us but Meta does not support it; we'd be inventing a non-standard scheme.

**Implementation note**: FastAPI's default body parsing consumes the stream. The webhook handler will read the raw bytes via `Request.body()` first, verify the signature, and only then parse JSON.

---

## R-3: Templates and locale selection

**Decision**: Maintain a static `TEMPLATE_REGISTRY: dict[NotificationType, dict[Locale, TemplateBinding]]` in `backend/app/services/whatsapp/templates.py`. Each `TemplateBinding` carries the Meta-side template name and the parameter-binding order (Meta templates use positional `{{1}}…{{N}}` slots). Locale selected from `profiles.preferred_language`, defaulting to `ar`. If the chosen locale's template is missing from the registry, fall back to the other supported locale (FR-007 + spec Edge Cases). If both are missing, log + treat as `failed (no_template)` and skip the provider call.

**Rationale**:
- Provider templates must be pre-approved per locale; a static registry mirrors that reality and prevents accidental free-text sends (which Meta blocks outside the 24-hour customer-service window anyway).
- Hard-coding the parameter order in the registry keeps the dispatch code simple and the failure modes explicit.

**Alternatives considered**:
- Pulling templates from Meta's API at boot — fragile and adds a hard dependency on Meta being up at startup.
- Storing template metadata in the DB — more flexible but adds a migration and a small admin surface we don't need in this phase.

**Templates to register (one per `NotificationType`)**:
- `debt_created` (debtor)
- `debt_accepted` (creditor)
- `debt_edit_requested` (creditor)
- `debt_edit_approved` / `debt_edit_rejected` (debtor)
- `payment_pending_confirmation` (creditor)
- `payment_confirmed` (debtor)
- `debt_cancelled` (debtor)
- `reminder_due` (debtor)

Each in `ar` + `en`. (The exact set is discoverable from `NotificationType` in `backend/app/schemas/domain.py` at implementation time.)

---

## R-4: Idempotency keying for inbound delivery callbacks

**Decision**: When sending, persist the provider's `messages[0].id` as `notifications.whatsapp_provider_ref` and also persist `whatsapp_attempted = true`. The webhook handler resolves the row by `whatsapp_provider_ref`. Updates set `whatsapp_delivered`, optionally `whatsapp_failed_reason`, and a `whatsapp_status_received_at` timestamp **only if** the inbound status represents a forward step (`sent → delivered → read` or `sent → failed`). A duplicate callback for the same `(provider_ref, status)` is a no-op (FR-014).

**Rationale**:
- Meta's `wa_id` / message id is globally unique and is what its webhook references — keying on it is natural and avoids inventing our own correlation token.
- Forward-only state machine (using a tiny `_status_rank` map) makes "the same callback twice" trivially idempotent and lets out-of-order callbacks (e.g., `read` arriving before `delivered`) collapse correctly.

**Alternatives considered**:
- Generating our own correlation UUID and passing it via Meta's `biz_opaque_callback_data` — works, but the provider id is already unique and we'd be carrying two ids for no win.

---

## R-5: Failure isolation between WhatsApp send and underlying transition

**Decision**: The notification dispatch runs **after** the business action commits its primary effect (debt row, transition row, `debt_events` row). The dispatcher wraps the provider call in a single `try/except Exception` that:
1. On success, updates `notifications.whatsapp_attempted = true`, `whatsapp_provider_ref = <id>`.
2. On any provider exception, updates `notifications.whatsapp_attempted = true`, `whatsapp_failed_reason = <short string>` and swallows the exception. The HTTP response for the original action is unaffected.

**Rationale**: FR-005 is non-negotiable: a failed text message can't undo a real debt. The notification row is created up-front by the existing notification-creation code so even total dispatcher failure leaves the in-app side intact.

**Alternatives considered**:
- Background task queue (Celery / RQ) — would isolate failure cleanly but introduces infra we don't need at MVP scale and complicates local dev.
- Synchronous send inside the same DB transaction — bad: a 30-second provider stall would block the user-facing request and a provider 5xx would roll back the debt action.

---

## R-6: Visibility of delivery columns to debtor (Q1 enforcement)

**Decision**: RLS on `notifications` continues to grant SELECT to creditor-or-debtor parties (no policy change). The handler `GET /api/v1/notifications` projects the response model differently based on `current_user.id`:
- If `notification.actor_id == current_user.id` (i.e., the user *sent* this notification, which for our notifications maps to the creditor side of the debt), include `whatsapp_attempted`, `whatsapp_delivered`, `whatsapp_failed_reason` in the response.
- Otherwise, omit those fields entirely.

**Rationale**: Q1 is a UX/visibility decision, not a data-isolation one — the debtor would still have row-read access at the DB layer (because they're a party), so we enforce it in the response shape via Pydantic models. Two response models: `NotificationOut` (debtor-facing, no delivery fields) and `NotificationOutCreditor` (with delivery fields). The handler picks based on the recipient relationship.

**Alternatives considered**:
- Splitting into two RLS-policied views — overengineering for a presentational concern.
- Always-include columns and trust the frontend to hide — violates "API as source of truth" ethos and leaks operationally.

---

## R-7: Webhook URL exposure in local development

**Decision**: Local development continues to use the `mock` provider (the global default and forced in tests by `conftest.py`); no inbound webhook is needed locally. For staging, expose the FastAPI server publicly via the existing Supabase / hosting setup or via a tunnel (ngrok, Cloudflared). Document the required URL: `https://<host>/api/v1/webhooks/whatsapp`.

**Rationale**: Avoids the burden of running a tunnel for every dev. The `cloud_api` provider is staging-and-up only.

**Alternatives considered**:
- Bake an ngrok integration into local dev — out of scope; the spec treats real-provider testing as a staging concern.

---

## Open questions for `/speckit-tasks` to consider

None blocking. All decisions above are concrete and testable.
