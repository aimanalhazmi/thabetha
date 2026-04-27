# API Endpoints

All endpoints mounted under `/api/v1` (`backend/app/api/router.py`). Auth: every route except `/health` and `/auth/*` requires a Supabase JWT in `Authorization: Bearer`. In `APP_ENV != production`, `x-demo-*` headers are also accepted (see `backend/app/core/security.py`).

Schema names below refer to Pydantic models in `backend/app/schemas/domain.py`.

---

## Health

| Method | Path | Response | Notes |
|---|---|---|---|
| GET | `/health` | `HealthOut` | Reports `supabase_connected` |

## Auth (proxy to Supabase Auth REST)

The frontend talks to Supabase Auth directly via `@supabase/supabase-js`; these endpoints exist for server-side flows.

| Method | Path | Body | Notes |
|---|---|---|---|
| POST | `/auth/signup` | `{email, password, name, phone, tax_id?, commercial_registration?}` | `tax_id` set ⇒ `account_type=creditor`, otherwise `debtor` (`auth.py:43`). Triggers Supabase verification email. |
| POST | `/auth/signin` | `{email, password}` | Proxies to `/token?grant_type=password`. |
| POST | `/auth/refresh` | `{refresh_token}` | Proxies to `/token?grant_type=refresh_token`. |
| POST | `/auth/signout` | — | Returns `{"message": "Signed out successfully"}`. Token revocation is client-side. |

## Profiles

| Method | Path | Body | Response | Notes |
|---|---|---|---|---|
| GET | `/profiles/me` | — | `ProfileOut` | |
| PATCH | `/profiles/me` | `ProfileUpdate` | `ProfileOut` | Partial; includes business fields and feature flags (`whatsapp_enabled`, `ai_enabled`). |
| POST | `/profiles/business-profile` | `BusinessProfileIn` | `BusinessProfileOut` (201) | Upsert (1:1 by `owner_id`). |
| GET | `/profiles/business-profile` | — | `BusinessProfileOut \| null` | |
| GET | `/profiles/me/commitment-score-events` | — | `list[CommitmentScoreEventOut]` | Score-history audit log. |

## QR

| Method | Path | Response | Notes |
|---|---|---|---|
| GET | `/qr/current` | `QRTokenOut` | Active short-lived token (≈10 min TTL). |
| POST | `/qr/rotate` | `QRTokenOut` | Issues a new token; old still valid until expiry. |
| GET | `/qr/resolve/{token}` | `ProfileOut` | Profile **preview** only — never credentials. |

## Debts

| Method | Path | Body | Response | Notes |
|---|---|---|---|---|
| POST | `/debts` | `DebtCreate` | `DebtOut` (201) | Creates in `pending_confirmation`. |
| GET | `/debts` | — | `list[DebtOut]` | Caller-scoped (creditor or debtor). Read-time runs the lazy overdue + missed-reminder sweeper. |
| GET | `/debts/{id}` | — | `DebtOut` | 403 if caller is not a party. |
| GET | `/debts/{id}/events` | — | `list[DebtEventOut]` | Full audit trail. |
| POST | `/debts/{id}/accept` | — | `DebtOut` | Debtor only. `pending_confirmation → active`. Sets `confirmed_at`. |
| POST | `/debts/{id}/edit-request` | `DebtEditRequest` | `DebtOut` | Debtor only. `pending_confirmation → edit_requested`. |
| POST | `/debts/{id}/edit-request/approve` | `DebtEditApproval` | `DebtOut` | Creditor only. `edit_requested → pending_confirmation` with new terms (creditor may override the debtor's proposal). |
| POST | `/debts/{id}/edit-request/reject` | `ActionMessageIn` | `DebtOut` | Creditor only. `edit_requested → pending_confirmation` with original terms. |
| POST | `/debts/{id}/cancel` | `ActionMessageIn` | `DebtOut` | Creditor only. Reachable only from `pending_confirmation` / `edit_requested`. |
| POST | `/debts/{id}/mark-paid` | `PaymentRequest` | `PaymentConfirmationOut` | Debtor only. `active`/`overdue → payment_pending_confirmation`. Creates `payment_confirmations` row. |
| POST | `/debts/{id}/confirm-payment` | — | `DebtOut` | Creditor only. `payment_pending_confirmation → paid`. Sets `paid_at`. Triggers commitment-indicator update (early/on-time/late). |
| POST | `/debts/{id}/attachments?attachment_type=...` | `multipart/form-data` (`file`) | `AttachmentOut` (201) | Either party may upload. `attachment_type ∈ AttachmentType`. |
| GET | `/debts/{id}/attachments` | — | `list[AttachmentOut]` | |

Any disallowed transition raises `409 Conflict` (see [`../debt-lifecycle.md`](../debt-lifecycle.md)).

## Dashboards

| Method | Path | Response | Notes |
|---|---|---|---|
| GET | `/dashboard/debtor` | `DebtorDashboardOut` | Total current debt, due-soon and overdue counts, creditors, own commitment score, debts. |
| GET | `/dashboard/creditor` | `CreditorDashboardOut` | Total receivable, debtor count, active/overdue/paid counts, best customers, alerts, debts. |

Both also drive the lazy sweeper for overdue / missed-reminder events.

## Notifications

| Method | Path | Body | Response | Notes |
|---|---|---|---|---|
| GET | `/notifications` | — | `list[NotificationOut]` | Caller-scoped. |
| POST | `/notifications/{id}/read` | — | `NotificationOut` | Idempotent. |
| PATCH | `/notifications/preferences` | `NotificationPreferenceIn` | `NotificationPreferenceOut` | Per-creditor WhatsApp opt-out (caller is the debtor; `merchant_id` is the creditor). |

## Groups (post-MVP — surfaced behind feature flag)

| Method | Path | Body | Response | Notes |
|---|---|---|---|---|
| POST | `/groups` | `GroupCreate` | `GroupOut` (201) | Creator becomes owner. |
| GET | `/groups` | — | `list[GroupOut]` | Caller's groups (owner or accepted member). |
| POST | `/groups/{id}/invite` | `GroupInviteIn` | `GroupMemberOut` | Owner-only. Status starts `pending`. |
| POST | `/groups/{id}/accept` | — | `GroupMemberOut` | Invitee only. Sets `accepted_at`. |
| GET | `/groups/{id}/debts` | — | `list[DebtOut]` | Debts with this `group_id`. |
| POST | `/groups/{id}/settlements` | `SettlementCreate` | `SettlementOut` (201) | Records a settlement; no auto-netting yet. |

## AI (paid tier — gated on `profile.ai_enabled`, otherwise 403)

| Method | Path | Body | Response | Notes |
|---|---|---|---|---|
| POST | `/ai/debt-draft-from-voice` | `VoiceDebtDraftRequest` | `VoiceDebtDraftOut` | Transcript → structured draft (debtor name, amount, due date, confidence). |
| POST | `/ai/merchant-chat` | `MerchantChatRequest` | `MerchantChatOut` | Ledger Q&A. |
