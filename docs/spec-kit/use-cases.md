# Use Cases — Status & Implementation Map

Each use case from `../product-requirements.md`, with current status and the concrete code that implements it. Status legend: ✅ shipped · 🟡 partial · ⏳ pending · ⛔ out-of-scope (post-MVP).

---

## UC1 — Sign up / profile · shared · ✅

Email + password via Supabase Auth, with name, phone, account type. Optional business sub-profile for creditors.

- Endpoints: `POST /auth/signup`, `POST /auth/signin`, `POST /auth/refresh`, `POST /auth/signout`, `GET/PATCH /profiles/me`, `GET/POST /profiles/business-profile`.
- Tables: `profiles`, `business_profiles`.
- Trigger: `public.handle_new_user()` (migration 002) auto-inserts a `profiles` row when `auth.users` gets a row.
- Frontend: `frontend/src/pages/AuthPage.tsx`, `ProfilePage.tsx`, `SettingsPage.tsx`.
- Notes: `tax_id` on signup auto-promotes `account_type=creditor`, otherwise `debtor` (`backend/app/api/auth.py:43`).

## UC2 — Create debt · creditor · ✅

Amount, currency, debtor, description, due date are required; receipt photo and voice note optional; reminder dates configurable.

- Endpoints: `POST /debts` (`DebtCreate`), `POST /debts/{id}/attachments` (multipart image/PDF invoice receipts), `GET /debts/{id}/attachments`.
- Tables: `debts` (with `reminder_dates date[]`), `attachments`, storage buckets `receipts` + `voice-notes`.
- Frontend: `frontend/src/pages/DebtsPage.tsx` (list + create flow), `frontend/src/components/AttachmentUploader.tsx`.
- Notes: receipt uploads are attached after debt creation, expose 1-hour access links, move to archived retention for 6 months after payment, and failed uploads can be retried from the debt card.
- **Remaining gaps**: voice-note attachment UI not built.

## UC3 — Bilateral confirm (accept / request-edit) · debtor · ✅

Debtor accepts → `active`. Debtor requests edit → `edit_requested`. Creditor approves (re-`pending_confirmation` with new terms) or rejects (re-`pending_confirmation` with original terms). The `rejected` status was removed in migration 006.

- Endpoints: `POST /debts/{id}/accept`, `POST /debts/{id}/edit-request`, `POST /debts/{id}/edit-request/approve`, `POST /debts/{id}/edit-request/reject`, `POST /debts/{id}/cancel`.
- Schemas: `DebtEditRequest`, `DebtEditApproval`, `ActionMessageIn` (`backend/app/schemas/domain.py:132-156`).
- Tables: `debts`, `debt_events` (audit trail).
- Frontend: inline edit-request thread on debt details page.
- **Cancel non-binding debt (creditor side) ✅** — Two-tap confirmation dialog with optional message. Available when `status ∈ {pending_confirmation, edit_requested}`. Hidden for all other states and for the debtor. On success, debt moves to `cancelled`, debtor receives `debt_cancelled` notification with the optional message body, page stays on debt details. Implemented in `002-cancel-non-binding-debt-ux`.

## UC4 — QR identification · shared · ✅

Rotating short-lived QR (default TTL 10 min) for debtors; creditor scanner resolves to a profile preview, then navigates to Create Debt with debtor prefilled and locked.

- Endpoints: `GET /qr/current`, `POST /qr/rotate`, `GET /qr/resolve/{token}`.
- Tables: `qr_tokens`.
- Frontend: `frontend/src/pages/QRPage.tsx` (debtor display + creditor scanner confirm step), `frontend/src/pages/DebtsPage.tsx` (QR prefill + locked field + submit-time re-resolve).
- **Shipped (PR #8 → spec 001)**: scanner confirm step in `QRPage.tsx`; `/debts?qr_token=<token>` deep-link; `DebtsPage.tsx` resolves token on mount, prefills and locks debtor name/ID, re-resolves at submit, strips URL on success; expired/self-scan/error banners; backend 409 self-billing guard in `POST /debts`; 2 integration tests (`test_create_debt_with_debtor_id.py`); bilingual strings (AR+EN).

## UC5 — Payment (mark paid → confirm receipt) · shared · ✅

Debtor marks paid → `payment_pending_confirmation`. Creditor confirms receipt → `paid`. Commitment indicator updates atomically.

- Endpoints: `POST /debts/{id}/mark-paid` (`PaymentRequest`), `POST /debts/{id}/confirm-payment`.
- Tables: `debts`, `payment_confirmations`, `commitment_score_events`, `debt_events`.
- Frontend: debt details page + creditor confirmation page.

## UC6 — Notifications · debtor · ✅

In-app notifications on every transition. Per-creditor WhatsApp opt-out (debtor-controlled). Real WhatsApp Business API delivery (branch `006-whatsapp-business-integration`).

- Endpoints: `GET /notifications`, `POST /notifications/{id}/read`, `PATCH /notifications/preferences`, `POST /webhooks/whatsapp`, `GET /webhooks/whatsapp`.
- Tables: `notifications` (+ migration 009 delivery columns), `merchant_notification_preferences`.
- Enum: `NotificationType` covers `debt_created`, `debt_confirmed`, `debt_edit_{requested,approved,rejected}`, `debt_cancelled`, `due_soon`, `overdue`, `payment_requested`, `payment_confirmed`.
- Frontend: `frontend/src/pages/NotificationsPage.tsx` + `WhatsAppDeliveryBadge.tsx` (creditor-only delivery badge).
- **Shipped (US1+US2+US3)**: real WhatsApp Cloud API provider behind `WhatsAppProvider` ABC; opt-out enforcement (global + per-creditor); per-message delivery state (`attempted_unknown / delivered / failed`) visible to creditor; HMAC-verified inbound webhook; idempotent status updates; `whatsapp_status_received_at` tracked.

## UC7 — Commitment indicator · debtor · ✅

`profiles.commitment_score` (0–100, default 50). See [`constitution.md`](./constitution.md#3-commitment-indicator-never-credit-score) for the full rules.

- Endpoint: `GET /profiles/me/commitment-score-events` returns the historical event log.
- Tables: `commitment_score_events` (with `reminder_date` + partial unique index for missed-reminder idempotency).
- Frontend: visible in debtor dashboard and bilateral debt views.

## UC8 — Dashboards · creditor / debtor · ✅

Creditor: total receivable, debtor count, active/overdue/paid counts, best customers, alerts. Debtor: total current debt, due-soon and overdue counts, creditors, own indicator.

- Endpoints: `GET /dashboard/creditor` (`CreditorDashboardOut`), `GET /dashboard/debtor` (`DebtorDashboardOut`).
- Frontend: `frontend/src/pages/DashboardPage.tsx` (role-routed by `account_type`).
- Notes: dashboard reads also drive the lazy overdue/missed-reminder sweeper.

## UC9 — Groups (friends/family) · both · 🟡 (Part 1 surfaced, auto-netting pending)

Part 1 (008-groups-mvp-surface) ships Groups in nav for all users (`profiles.groups_enabled` gate). Full lifecycle (create, invite by email/phone, accept/decline, leave, rename, transfer-ownership, delete) is implemented. Group-tagged debt creation and retag via `PATCH /debts/{id}` are wired. Auto-netting is not implemented; settlements are recorded as opaque rows.

- Endpoints: 13 group routes (`GET /groups`, `POST /groups`, `GET /groups/{id}`, `GET /groups/{id}/members`, `GET /groups/{id}/invites`, `POST /groups/{id}/invite`, `POST /groups/{id}/accept`, `POST /groups/{id}/decline`, `POST /groups/{id}/leave`, `POST /groups/{id}/rename`, `POST /groups/{id}/transfer-ownership`, `DELETE /groups/{id}`, `DELETE /groups/{id}/invites/{user_id}`, `GET /groups/{id}/debts`, `POST /groups/{id}/settlements`, `GET /groups/shared`), `PATCH /debts/{id}` for group retag.
- Tables: `groups`, `group_members` (widened `status` enum), `group_events` (audit), `group_settlements`, `debts.group_id`; `profiles.groups_enabled`.

## UC10 — AI assistant (paid tier) · creditor · 🟡 (Voice draft in progress, gated)

Voice-to-debt draft is being upgraded from stub to a real Arabic/English transcript pipeline. Returns `403` unless `profile.ai_enabled = true`; voice drafts never create debts until the creditor confirms or edits every extracted field and submits through the normal create-debt flow.

- Endpoints: `POST /ai/debt-draft-from-voice` (JSON transcript or multipart audio → draft), `POST /ai/merchant-chat`.
- Frontend: create-debt form voice draft panel (creditor + AI tier), plus `frontend/src/pages/AIPage.tsx` compatibility surface.
