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

## UC6 — Notifications · debtor · 🟡

In-app notifications on every transition. Per-creditor WhatsApp opt-out (debtor-controlled).

- Endpoints: `GET /notifications`, `POST /notifications/{id}/read`, `PATCH /notifications/preferences`.
- Tables: `notifications`, `merchant_notification_preferences`.
- Enum: `NotificationType` covers `debt_created`, `debt_confirmed`, `debt_edit_{requested,approved,rejected}`, `debt_cancelled`, `due_soon`, `overdue`, `payment_requested`, `payment_confirmed`.
- Frontend: `frontend/src/pages/NotificationsPage.tsx`.
- **Gap**: WhatsApp provider is mocked; `whatsapp_attempted` flag exists but no real send. Mock-WhatsApp-preview pane (Could-Have) not built.

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

## UC9 — Groups (friends/family) · debtor · ⛔ (post-MVP)

Endpoints exist but are not surfaced in MVP nav. Auto-netting is not implemented; settlements are recorded as opaque rows.

- Endpoints: `POST /groups`, `GET /groups`, `POST /groups/{id}/invite`, `POST /groups/{id}/accept`, `GET /groups/{id}/debts`, `POST /groups/{id}/settlements`.
- Tables: `groups`, `group_members`, `group_settlements`, plus `debts.group_id`.

## UC10 — AI assistant (paid tier) · creditor · ⛔ (Could-Have, gated)

Stubs only. Returns `403` unless `profile.ai_enabled = true`.

- Endpoints: `POST /ai/debt-draft-from-voice` (transcript → draft), `POST /ai/merchant-chat`.
- Frontend: `frontend/src/pages/AIPage.tsx` (hard-gated).
