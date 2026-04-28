# Quickstart — Phase 6: WhatsApp Business API Integration

This walks the local-dev verification path (mock provider) plus the staging smoke test (real Cloud API). It does **not** describe Meta's business-verification flow — that's an operational task for the team setting up the WhatsApp Business Account.

---

## Prerequisites

- Repo cloned, `supabase start` running (see `docs/local-development.md`).
- Backend deps installed: `cd backend && uv sync`.
- Frontend deps installed: `cd frontend && npm install`.
- `.env` populated as in `.env.example` plus the new keys below.

---

## Local development (mock provider — default)

The mock provider is the default in dev and is forced in tests. No Meta credentials are required.

### 1. Apply the migration

```bash
supabase db reset      # runs every migration including 009_whatsapp_delivery.sql
```

### 2. Run the backend with the mock provider

`.env` (or `backend/.env`):

```dotenv
APP_ENV=local
REPOSITORY_TYPE=postgres
WHATSAPP_PROVIDER=mock                    # default; explicit here for clarity
# WHATSAPP_PROVIDER_TOKEN, WHATSAPP_PHONE_NUMBER_ID, WHATSAPP_WEBHOOK_SECRET, WHATSAPP_VERIFY_TOKEN
# left unset — mock provider does not need them
```

```bash
cd backend && uv run uvicorn app.main:app --reload
```

### 3. Walk the happy path

In a second terminal:

```bash
cd frontend && npm run dev
```

- Sign up two users via the UI (creditor + debtor; confirm via Inbucket at http://127.0.0.1:55324).
- As the creditor, create a debt addressed to the debtor.
- Backend logs should contain a line like:
  `[whatsapp.mock] sent template=debt_created locale=ar to=+9665XXXXXXXX provider_ref=mock-<uuid>`.
- As the creditor, open `/notifications` — the sent notification displays a "**delivered (mock)**" badge, because the mock provider auto-completes its own delivery callback synchronously.
- As the debtor, open `/notifications` — the same notification is present **without** any delivery badge (per Q1).

### 4. Verify preference enforcement

- As the debtor, open Settings → Notification preferences.
- Toggle the per-creditor WhatsApp preference for that one creditor to **off**.
- As the creditor, trigger another notification (e.g. mark the debt cancelled).
- Backend log should contain:
  `[whatsapp.dispatch] suppressed reason=per_creditor_opt_out user=<debtor_id> creditor=<creditor_id>`
  and the new notification row has `whatsapp_attempted=false`.

### 5. Run the test suite

```bash
cd backend && uv run pytest -k whatsapp
```

All provider-contract, dispatcher-preference, dispatcher-resilience, locale-fallback, and webhook tests should pass. `REPOSITORY_TYPE=memory` and `WHATSAPP_PROVIDER=mock` are forced by `tests/conftest.py`.

---

## Staging smoke test (real Cloud API)

> Run this **only** in staging or production. The local default is `mock`.

### 1. One-time provider setup (operational)

- Register a Meta WhatsApp Business Account, complete business verification, register a phone number.
- Pre-approve every template listed in `research.md` §R-3 in **both** `ar` and `en`.
- In the Meta dashboard, configure the webhook URL: `https://<staging-host>/api/v1/webhooks/whatsapp` and a verify token of your choosing — record it as `WHATSAPP_VERIFY_TOKEN`.
- Generate a permanent system-user access token — record it as `WHATSAPP_PROVIDER_TOKEN`.
- Record the phone-number ID as `WHATSAPP_PHONE_NUMBER_ID` and the App Secret as `WHATSAPP_WEBHOOK_SECRET`.

### 2. Staging environment

```dotenv
APP_ENV=staging
WHATSAPP_PROVIDER=cloud_api
WHATSAPP_PROVIDER_TOKEN=<permanent-token>
WHATSAPP_PHONE_NUMBER_ID=<phone-number-id>
WHATSAPP_WEBHOOK_SECRET=<app-secret>
WHATSAPP_VERIFY_TOKEN=<verify-token-you-chose>
```

### 3. Verify the webhook subscription

```bash
curl -i 'https://<staging-host>/api/v1/webhooks/whatsapp?hub.mode=subscribe&hub.verify_token=<verify-token>&hub.challenge=12345'
# expect: 200 OK, body: 12345
```

### 4. Send a real template message end-to-end

- In staging, sign in as a creditor whose debtor has a real WhatsApp-enabled handset.
- Create a debt.
- The debtor's phone receives a real WhatsApp message in their preferred locale within ~5 seconds.
- A few seconds later, Meta calls back to `/api/v1/webhooks/whatsapp` with `status=delivered`. Backend log:
  `[whatsapp.webhook] status=delivered provider_ref=wamid.XXXXX applied=1`.
- Refresh the creditor's notifications view — the badge flips from "attempted, status unknown" to "delivered".

### 5. Verify the failure path

- Repeat with the debtor's phone number set to a number that is not registered on WhatsApp.
- Send fails synchronously; log: `[whatsapp.cloud_api] blocked reason=invalid_phone provider_ref=None`.
- Creditor sees a "**failed: invalid phone**" badge (translated string).
- Debt itself was created — the failure did not roll back anything (FR-005).

### 6. Verify opt-out still works against the real provider

- Same as local step 4 above, but in staging. The debtor opts out of WhatsApp from creditor A.
- Creditor A triggers a notification → no Graph API call is made (verify by checking Meta's outbound logs and our own dispatcher log: `suppressed reason=per_creditor_opt_out`).
- Creditor B triggers a notification → message is sent normally.

---

## Acceptance signals checklist (from spec.md)

- [ ] Sending a real WhatsApp template succeeds in staging (steps §4).
- [ ] Debtor opt-out for creditor A still receives WhatsApp from creditor B and from in-app for both (steps §6 + local §4).
- [ ] A failed send produces a notification row with `whatsapp_delivered=false` and a reason (step §5).
