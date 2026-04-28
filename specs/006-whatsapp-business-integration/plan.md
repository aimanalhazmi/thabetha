# Implementation Plan: Real WhatsApp Business API Integration

**Branch**: `006-whatsapp-business-integration` | **Date**: 2026-04-28 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/006-whatsapp-business-integration/spec.md`

## Summary

Replace the mock WhatsApp send path with a provider-agnostic outbound channel that, when configured for the real provider (WhatsApp Cloud API by Meta), sends pre-approved Arabic and English templates per `NotificationType` whenever a debt-state notification is fired. Outbound sends respect both the global per-user toggle (`profiles.whatsapp_enabled`) and the per-creditor opt-out (`merchant_notification_preferences.whatsapp_enabled`). Per-message delivery state (`attempted` / `delivered` / `failed reason`) is recorded on the `notifications` row, populated by a signed inbound webhook `POST /api/v1/webhooks/whatsapp`. Provider failures never roll back the underlying business action; in-app notifications always fire. Delivery state is visible only to the sending creditor on their notifications view (per Clarifications Q1). Provider selection is deployment-time only — no runtime failover (Q2). The "attempted, status unknown" state is permanent until a real callback arrives — no background promotion (Q3).

Technical approach: introduce `backend/app/services/whatsapp/` with a `WhatsAppProvider` ABC, two implementations (`mock.py`, `cloud_api.py`), and a thin façade `dispatch.py` that resolves preferences, picks the right template+locale, calls the provider, and writes the resulting state onto the in-app notification row in the same transaction-or-best-effort flow that already creates that row. Add migration `009_whatsapp_delivery.sql` extending `notifications` with `whatsapp_attempted boolean`, `whatsapp_delivered boolean`, `whatsapp_provider_ref text`, `whatsapp_failed_reason text`. Add a public webhook router that does HMAC verification and idempotent upsert keyed on `whatsapp_provider_ref`. Frontend surfaces the new badge on the creditor's notifications view only and continues to use the existing settings UI for opt-out.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript 5 strict (frontend, React 19 + Vite)
**Primary Dependencies**: FastAPI, `httpx` (sync via `requests` is not used; reuse the existing async client patterns in the codebase), `pydantic` v2, `supabase-py`, `@supabase/supabase-js`. No new top-level dependency required for the Cloud API integration — Meta's Graph API is plain HTTPS+JSON.
**Storage**: Supabase Postgres. New columns on `notifications`; no new tables. RLS policies on `notifications` already restrict reads to creditor or debtor party; new columns inherit those policies (no policy rewrite needed) but a row-level filter in handler code restricts WhatsApp delivery columns to the sending creditor's view of their own row.
**Testing**: `pytest` via `FastAPI.TestClient` with `REPOSITORY_TYPE=memory`; `WHATSAPP_PROVIDER=mock` is the test default. Provider-interface contract tests run against the mock; webhook signature verification tests use known-good and known-bad HMAC fixtures. Integration tests assert preference enforcement (global off → no provider call; per-creditor off for A → A suppressed, B unaffected) and the underlying transition still completes when the provider raises.
**Target Platform**: Linux server (FastAPI / `uv run uvicorn`) behind Supabase Auth; React SPA bundled by Vite. Webhook endpoint must be publicly reachable in staging/production for Meta to call back.
**Project Type**: Web application (FastAPI backend + React/Vite frontend, Supabase as the data + auth + storage backbone).
**Performance Goals**: Outbound send P50 under 500 ms server-side (single Graph API request, fire-and-forget enough for one synchronous call inside the notification path). Webhook handling under 100 ms — strictly verify HMAC, write one row, return 200. Spec target: 95% of messages delivered within 30 s of triggering event (SC-001).
**Constraints**: `WhatsApp send failure MUST NOT fail the underlying transition` (FR-005) — the dispatch call is wrapped in a try/except that records the failure on the notification row and continues. Webhook MUST verify HMAC before any DB write (FR-009). Idempotency keyed on `provider_ref` (FR-014). One send attempt per notification (FR-016) — no retry queue. "Unknown" state never auto-promotes (FR-017) — no sweeper.
**Scale/Scope**: MVP scale (<1k active users, <10k notifications/month), so provider-level rate limits are sufficient and no application-level throttling is needed. Migration touches one table; backend introduces one new module (≈4 files) and one new router (≈1 file).

## Constitution Check

This feature is principally a backend integration; the impact on the constitution's principles is bounded and the gate passes without exceptions.

| Principle | Touchpoint | Compliance |
|---|---|---|
| I. Bilateral Confirmation | None — no new transitions. | ✅ Pass |
| II. Canonical 7-State Lifecycle | None — no transition changes. WhatsApp leg is a side-effect of existing transitions. | ✅ Pass |
| III. Commitment Indicator | None — independent of scoring. | ✅ Pass |
| IV. Per-User Data Isolation | New columns on `notifications` inherit the existing creditor-or-debtor RLS read policy. **Handler code** further hides the new delivery columns from the debtor (Q1) — only the sending creditor's view of their notification exposes the delivery state. The webhook endpoint is unauthenticated for the user but signed by the provider; it writes with a service role and is the **only** code path that can mutate delivery columns. | ✅ Pass |
| V. Arabic-First | New user-visible strings (delivery badge labels, failure reason rendering, settings copy) added to `frontend/src/lib/i18n.ts` AR + EN. WhatsApp template variants registered in both languages with the provider, selected by `profiles.preferred_language`. | ✅ Pass |
| VI. Supabase-First Stack | Reuses Supabase Postgres + existing migration runner. New migration is `supabase/migrations/009_whatsapp_delivery.sql`. No parallel auth or storage. | ✅ Pass |
| VII. Schemas Are Single Source | New enum `WhatsAppDeliveryStatus` (or a derived computed property; see research) lives in `backend/app/schemas/domain.py`; `frontend/src/lib/types.ts` mirrors it. | ✅ Pass |
| VIII. Audit Trail Per Debt | No new `debt_events` rows — WhatsApp delivery is a notification-level concern, not a debt-level transition. The notification row itself is the audit record for messaging. | ✅ Pass |
| IX. QR Identity | Not affected. | ✅ Pass |
| X. AI Paid-Tier Gating | Not affected. | ✅ Pass |

**Gate result**: PASS. No Complexity Tracking entries required.

## Project Structure

### Documentation (this feature)

```text
specs/006-whatsapp-business-integration/
├── plan.md              # this file
├── research.md          # Phase 0 — provider, templates, webhook signature, idempotency
├── data-model.md        # Phase 1 — notifications schema delta
├── contracts/
│   ├── whatsapp_provider.md      # Internal ABC contract (send / verify / etc.)
│   └── webhook_meta.md           # POST /api/v1/webhooks/whatsapp request shape
├── quickstart.md        # Phase 1 — running locally with mock + curl-driven webhook
├── checklists/
│   └── requirements.md
└── tasks.md             # produced by /speckit-tasks (NOT this command)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── api/
│   │   ├── notifications.py            # existing — minor read-side changes to scope new columns to creditor view
│   │   ├── webhooks_whatsapp.py        # NEW — POST /api/v1/webhooks/whatsapp
│   │   └── router.py                   # mount the new router under /api/v1
│   ├── core/
│   │   ├── config.py                   # extend Settings with whatsapp_phone_number_id, whatsapp_webhook_secret
│   │   └── security.py                 # NEW helper verify_whatsapp_signature(raw_body, header) — HMAC SHA256
│   ├── repositories/
│   │   ├── base.py                     # extend Repository with mark_whatsapp_attempted / mark_whatsapp_delivery
│   │   ├── memory.py                   # implement on InMemoryRepository
│   │   └── postgres.py                 # implement on PostgresRepository (UPDATE ... WHERE whatsapp_provider_ref = :ref)
│   ├── schemas/
│   │   └── domain.py                   # add NotificationOut fields; add WhatsAppDeliveryStatus enum
│   └── services/
│       └── whatsapp/                   # NEW MODULE
│           ├── __init__.py             # `get_provider()` factory selecting mock vs cloud_api from settings
│           ├── provider.py             # ABC: send_template(to_e164, template_id, locale, params) -> SendResult
│           ├── mock.py                 # current mock logic moved here; deterministic SendResult for tests
│           ├── cloud_api.py            # Meta Graph API impl using httpx + bearer token
│           ├── templates.py            # Map NotificationType + locale -> (template_id, param_layout)
│           └── dispatch.py             # Orchestrator: resolve preferences, choose locale, call provider, persist state
└── tests/
    ├── conftest.py                     # already forces REPOSITORY_TYPE=memory; force WHATSAPP_PROVIDER=mock too
    ├── services/
    │   └── whatsapp/
    │       ├── test_provider_contract.py    # ABC contract test against mock
    │       ├── test_dispatch_preferences.py # global off / per-creditor off / both on / both off
    │       ├── test_dispatch_resilience.py  # provider raises -> transition still succeeds
    │       └── test_templates_locale.py     # AR+EN selection + fallback
    └── api/
        └── test_webhooks_whatsapp.py        # signature OK / bad / replay / unknown ref

frontend/
├── src/
│   ├── lib/
│   │   ├── i18n.ts                     # add: whatsapp_status_attempted, whatsapp_status_delivered, whatsapp_status_failed, plus reason mapping
│   │   └── types.ts                    # mirror NotificationOut delivery fields + WhatsAppDeliveryStatus
│   ├── pages/
│   │   └── NotificationsPage.tsx       # creditor view: render delivery badge for sent notifications
│   └── components/
│       └── WhatsAppDeliveryBadge.tsx   # NEW small presentational component (creditor-only)

supabase/migrations/
└── 009_whatsapp_delivery.sql           # ALTER notifications ADD COLUMN ... + RLS unchanged

docs/spec-kit/
├── api-endpoints.md                    # add POST /api/v1/webhooks/whatsapp row
└── database-schema.md                  # add notifications delta
```

**Structure Decision**: Web application (Option 2). The backend gains a new vertical slice under `services/whatsapp/` plus one new router; the frontend gets one new badge component and i18n strings; the database gains one migration. This matches the constitution's Supabase-first / repository-pattern layout already in place.

## Complexity Tracking

> Constitution Check passed; no exceptions to justify.
