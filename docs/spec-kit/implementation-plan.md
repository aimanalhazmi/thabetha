# Thabetha — Implementation Plan (Spec-Kit Phased Roadmap)

> **Snapshot date:** 2026-04-27 · **Branch:** `develop`
> **Purpose:** Continue from the current state toward MVP-complete + post-MVP, structured as discrete spec-kit features. Each phase below is sized for one `/specify → /clarify → /plan → /tasks → /implement` cycle.

---

## How to use this plan with spec-kit

Each **phase** below is one feature for spec-kit. The flow per phase is:

1**`/clarify`** — let spec-kit ask its clarification questions. Use the *Pre-answered clarifications* in each phase to answer quickly and consistently.
2**`/plan`** — feed in the *Technical context* from the phase (stack, constraints, files to touch). spec-kit produces `plan.md` + design artifacts.
3**`/tasks`** — produces an ordered, dependency-aware task list.
4**`/analyze`** (optional) — cross-check spec/plan/tasks consistency before coding.
5**`/implement`** or hand tasks to a teammate. Each phase lists *Acceptance signals* — these are what closes the phase.
6**After merge:** update `claude-handoff/project-status.md` and the relevant row in `claude-handoff/use-cases.md`. Tick the phase below.

**Branching:** one branch per phase, named `NNN-<slug>` to mirror spec-kit's folder. Rebase on `develop` before opening the PR. Don't combine phases — the small surface area is the point.

**Testing rule (from constitution §12):** every new state transition or auth-affecting change ships with a `FastAPI.TestClient` test using `REPOSITORY_TYPE=memory`. No exceptions.

---

## Phase ordering rationale

The phases below are ordered by **dependency**, not priority. Demo polish (Phase 3) needs receipt upload (Phase 1) and QR pass-through (Phase 2) to be meaningful. AR/EN audit (Phase 4) is best done after the new UI surfaces from 1–2 land, so we audit once, not twice. WhatsApp (Phase 6) needs the cancel UX (Phase 5) to have something useful to send. Groups (Phase 7) and AI (Phases 8–10) are gated by MVP completion.

| Phase | Slug | Block | Depends on | Rough size |
|---|---|---|---|---|
| 1 | `receipt-upload-on-create-debt` | MVP gap | — | S |
| 2 | `qr-scanner-prefill-create-debt` | MVP gap | — | S |
| 3 | `cancel-non-binding-debt-ux` | MVP gap | — | XS |
| 4 | `e2e-demo-polish` | MVP gap | 1, 2, 3 | M |
| 5 | `bilingual-coverage-audit` | MVP gap | 1, 2, 3 | M |
| 6 | `whatsapp-business-integration` | Post-MVP | 4, 5 | L |
| 7 | `payment-gateway-settlement` | Post-MVP | 4 | L |
| 8 | `groups-mvp-surface` | Post-MVP | 4 | M |
| 9 | `groups-auto-netting` | Post-MVP | 8 | L |
| 10 | `backend-rls-enforcement` | Hardening | — | M |
| 11 | `ai-receipt-extraction` | Paid tier | 1 | L |
| 12 | `ai-voice-debt-draft` | Paid tier | — | M |
| 13 | `ai-merchant-chat-grounding` | Paid tier | — | M |
| H1 | `types-codegen` | Housekeeping | — | S |
| H2 | `legacy-bucket-cleanup` | Housekeeping | — | XS |
| H3 | `transition-test-coverage` | Housekeeping | — | M |

Block 1 (Phases 1–5) closes the MVP. Block 2 (Phases 6–10) is post-MVP hardening. Block 3 (Phases 11–13) is the paid AI tier. Housekeeping items can run in parallel with any block.

---

# Block 1 — Close the MVP

## Phase 1 — Receipt upload on Create Debt

**Maps to:** `spec-kit-plan.md#F1`, UC2, `project-status.md` "Receipt upload on Create Debt".

### Problem statement (paste into `/specify`)

> Creditors creating a debt cannot attach a receipt photo from the create-debt screen, even though the backend already supports it. Wire the existing `POST /debts/{id}/attachments` (multipart, `attachment_type=invoice`) into the create-debt UI so a creditor can attach one or more receipt photos at creation time. The debtor must be able to view the attachment via signed URL on the debt details page.

### Pre-answered clarifications

- **One receipt or many?** Many. Backend accepts repeat calls; UI should allow multi-select.
- **Image only?** Images + PDF (`image/*` and `application/pdf`). Reject everything else client-side.
- **Max size?** 5 MB per file, hard cap; warn at 4 MB.
- **Where in flow?** Optional field on the create-debt form. After `POST /debts` returns 201, fire `POST /debts/{id}/attachments` for each file. If any attachment upload fails, the debt itself is still created — show a non-blocking error and offer a retry from the debt details page.
- **Compression?** Yes — client-side resize to max 2048px on the long edge before upload (saves bandwidth, helps the 5 MB cap).
- **Voice notes?** Out of scope for this phase. Same pattern, separate phase if needed.

### Technical context (feed into `/plan`)

- **Frontend:** `frontend/src/pages/DebtsPage.tsx` (create form), new `frontend/src/components/AttachmentUploader.tsx` for reuse on details page.
- **Backend:** no changes expected. `POST /debts/{id}/attachments` already exists.
- **Storage:** bucket `receipts`, path `<debt_id>/<uuid>-<filename>`. RLS already in place (migration 003).
- **Signed URLs:** debt details page already lists attachments via `GET /debts/{id}/attachments`; ensure `public_url` field returns a Supabase signed URL with a sane TTL (1 hour). If currently returning a raw path, that's an in-scope backend tweak.
- **i18n:** new strings (`upload_receipt`, `select_files`, `file_too_large`, `unsupported_file_type`, `upload_failed_retry`) → `frontend/src/lib/i18n.ts` AR + EN.
- **Tests:** integration test in `backend/tests/` exercising `POST /debts` then `POST /debts/{id}/attachments` then `GET /debts/{id}/attachments` with `REPOSITORY_TYPE=memory`. Frontend smoke test only if you have one set up.

### Acceptance signals

- Creditor can create a debt with 1–N receipts attached in one flow.
- Debtor opens debt details and sees thumbnails / filenames; clicking opens a signed URL.
- 6 MB file is rejected client-side with a translated error.
- Both attachments and debt creation events are visible in `debt_events`.

### Branch & PR

- Branch: `001-receipt-upload-on-create-debt`
- PR title: `feat: receipt upload on create-debt`
- Updates: `project-status.md` (move bullet from "In progress" to "Shipped"), `use-cases.md` UC2 status `🟡 → ✅` for the receipt sub-bullet.

---

## Phase 2 — QR-scanner pass-through to Create Debt

**Maps to:** `spec-kit-plan.md#F2`, UC4 → UC2.

### Problem statement

> A creditor scanning a debtor's QR code lands on a profile preview but cannot proceed to "create a debt for this person" without retyping the debtor's identity. After a successful `GET /qr/resolve/{token}`, hand the resolved profile preview into the create-debt form so `debtor_id` and `debtor_name` are prefilled and locked.

### Pre-answered clarifications

- **Locked, or editable after prefill?** Locked. The whole point of QR is that identity is not retyped. A "clear / change debtor" link allows starting over.
- **What if token is expired between scan and submit?** The form re-resolves on submit; if expired, show "QR expired, ask the customer to refresh their code."
- **Profile preview shown?** Yes — show debtor name, phone last 4 digits, and commitment indicator badge above the form. No tax_id or email.
- **Manual debtor entry path?** Still available — QR is one of two entry points to `/debts/new`. Manual entry uses `debtor_name` only (no `debtor_id`), as today.
- **Deep link?** Yes — `/debts/new?qr_token=<token>` so the scanner can navigate directly. Token is consumed (resolved) once on mount.

### Technical context

- **Frontend:**
  - `frontend/src/pages/QRPage.tsx` (scanner half) → on successful resolve, navigate to `/debts/new?qr_token=...`.
  - `frontend/src/pages/DebtsPage.tsx` (create flow) → on mount with `qr_token`, call `GET /qr/resolve/{token}`, hydrate state, lock debtor fields.
- **Backend:** no changes. `GET /qr/resolve/{token}` already returns `ProfileOut`.
- **Edge cases:** QR resolves to the creditor themselves → block with "you can't bill yourself".
- **i18n:** `qr_expired_ask_refresh`, `cannot_bill_self`, `clear_debtor`, `scanned_debtor_label`.
- **Tests:** unit-test the `qr_token` query param branch in the create-debt page if a test harness exists; otherwise a manual E2E note in the PR.

### Acceptance signals

- Scanner → create-debt flow completes in two screens with no manual debtor typing.
- Expired token in URL shows the right error and lets the user dismiss to manual entry.
- Self-scan is blocked with a translated error.

### Branch & PR

- Branch: `002-qr-scanner-prefill-create-debt`
- Updates: `use-cases.md` UC4 status `🟡 → ✅`.

---

## Phase 3 — Cancel non-binding debt UX

**Maps to:** `spec-kit-plan.md#F5`, UC3 (creditor side).

### Problem statement

> The creditor backend can cancel a debt that is still `pending_confirmation` or `edit_requested` via `POST /debts/{id}/cancel`, but the UI surface is partial. Add a clear "Cancel debt" affordance on the creditor's debt details page for those two states only, with a confirmation dialog and an optional message that flows into the `debt_cancelled` notification.

### Pre-answered clarifications

- **Allowed states?** Only `pending_confirmation` and `edit_requested`. The button is hidden otherwise.
- **Confirmation dialog?** Yes, two-tap. "Cancel debt? The debtor will be notified."
- **Optional message?** Yes — single textarea, max 200 chars, passed as `ActionMessageIn.message`. Empty is fine.
- **Notification copy?** Reuses existing `NotificationType.debt_cancelled`. Body includes the optional message if present.
- **Audit trail?** `debt_events` row of type `cancelled` with the actor and message. Backend already does this.

### Technical context

- **Frontend:** debt details page (`DebtsPage.tsx` route `/debts/:id`) — visible for creditor only when `status ∈ {pending_confirmation, edit_requested}`.
- **Backend:** no changes. Endpoint and notification wiring exist.
- **i18n:** `cancel_debt`, `cancel_debt_confirm_title`, `cancel_debt_confirm_body`, `cancel_message_optional`, `cancelled_successfully`.
- **Tests:** existing transition test should already cover the backend; add a frontend test if relevant. Re-verify the disallowed-from-`active` path returns 409.

### Acceptance signals

- Creditor cancels a non-binding debt in two taps.
- Debtor sees a `debt_cancelled` notification (in-app), with the optional message body.
- Trying to cancel an `active` debt is impossible from the UI (button hidden).

### Branch & PR

- Branch: `003-cancel-non-binding-debt-ux`
- Updates: `use-cases.md` UC3 row note (cancel sub-bullet now done).

---

## Phase 4 — End-to-end demo polish

**Maps to:** `spec-kit-plan.md#F3`, MVP demo path.

### Problem statement

> A fresh user must be able to walk the canonical happy path on local Supabase without dev help: signup → create debt (with receipt, via QR) → debtor accepts → debtor marks paid → creditor confirms → commitment indicator updates. Identify and fix every UX rough edge along that path. This is not a feature — it is a polish sweep.

### Pre-answered clarifications

- **Scope?** Strictly the happy path above plus one branch (debtor requests edit, creditor approves with new terms). No other branches in this phase.
- **What counts as a rough edge?** Any of: untranslated string surfaced, error toast with raw API message, missing loading state on button, broken back navigation, missing empty-state, failure to refresh after a transition.
- **Performance budget?** Each transition under 800 ms perceived on local Supabase.
- **Output?** A polish-pass PR plus a one-page demo script (markdown, ~10 steps) checked into `claude-handoff/` as `demo-script.md`.

### Technical context

- **Frontend:** mostly `DebtsPage.tsx`, `DashboardPage.tsx`, `NotificationsPage.tsx`, `QRPage.tsx`.
- **Backend:** unlikely to change. If a transition is slow, profile the lazy sweeper.
- **i18n:** any string found untranslated during the sweep is folded into Phase 5's audit. Don't fix individual strings here in isolation — collect them.
- **Tests:** add a `pytest` integration test that walks the entire happy path top-to-bottom with `REPOSITORY_TYPE=memory`, asserting status transitions and the final commitment score delta. This becomes the canonical regression test.

### Acceptance signals

- The integration "happy path" test passes.
- The demo script can be executed in under 5 minutes by a new contributor.
- No raw API error messages reach the UI on the happy path.

### Branch & PR

- Branch: `004-e2e-demo-polish`
- Updates: `project-status.md` "End-to-end demo path" → ✅.

---

## Phase 5 — Bilingual coverage audit (AR/EN)

**Maps to:** `spec-kit-plan.md#F4`, constitution §5.

### Problem statement

> Audit every visible string in the frontend against `frontend/src/lib/i18n.ts`. No hardcoded English or Arabic strings may remain outside that file. Both locales must render with correct RTL/LTR direction, including form inputs, dialogs, toasts, and date/number formatting.

### Pre-answered clarifications

- **Scope?** All pages in `frontend/src/pages/` and all components in `frontend/src/components/`. Skip `LandingPage.tsx` if it is intentionally English-only marketing — confirm with PM first.
- **What about backend error messages?** Out of scope here; backend returns codes, frontend translates. If any backend message is leaking to the UI as user-visible text, file a separate bug.
- **Date/number formatting?** Use `Intl.DateTimeFormat` and `Intl.NumberFormat` keyed on the active locale. SAR currency formatting both ways. Hijri calendar is **not** in scope — Gregorian only for this audit.
- **RTL test surfaces?** Form inputs (caret position, alignment), tables, modals, toasts, navigation drawer, charts on dashboards.
- **Linting?** Add an ESLint rule (or a small repo grep CI step) to catch raw string literals in JSX. Document the escape hatch (data-test ids, etc.).

### Technical context

- **Frontend:** `frontend/src/lib/i18n.ts` (string sink), every page and component, `frontend/src/contexts/AuthContext.tsx` for direction toggle if not already there.
- **Tooling:** consider `eslint-plugin-i18next` or a small custom rule. CI must fail on a raw string in JSX.
- **No backend changes.**
- **Tests:** add a snapshot test per page in both locales (Vitest + Testing Library) — or at least a smoke render in both directions.

### Acceptance signals

- Lint rule fires on any new raw JSX string.
- Both locales render every page without missing keys (no `missing.key.x` artifacts).
- RTL audit passes on dashboards, debt details, create-debt, notifications, settings.

### Branch & PR

- Branch: `004-bilingual-coverage-audit`
- Updates: `project-status.md` "Polished bilingual UI" → ✅.

---

# Block 2 — Post-MVP hardening

## Phase 6 — Real WhatsApp Business API integration

**Maps to:** `spec-kit-plan.md#F6`, UC6.

### Problem statement

> Replace the mock WhatsApp provider with a real WhatsApp Business API integration. Outbound messages on debt-state notifications must respect `merchant_notification_preferences.whatsapp_enabled` per (debtor, creditor) and the global `profiles.whatsapp_enabled` toggle. A debtor's opt-out for a specific creditor must stop outbound WhatsApp messages from that creditor only.

### Pre-answered clarifications

- **Provider?** WhatsApp Cloud API (Meta) is the default — cheapest path to a verified template flow. Twilio is the fallback if business verification stalls. The integration must be provider-agnostic behind a `WhatsAppProvider` interface.
- **Templates?** Pre-approved templates per `NotificationType` value. Bilingual variants per template.
- **Failure mode?** WhatsApp send failure does **not** fail the underlying transition. Notification row gets `whatsapp_attempted=true, whatsapp_delivered=false` plus an error code. In-app notification still fires.
- **Rate limits?** Provider-level — no app-level throttling needed for MVP scale.
- **Webhook?** Inbound delivery receipts update the notification row. Inbound user replies are out of scope (we are sending, not chatting).
- **Secrets?** `WHATSAPP_PROVIDER_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_WEBHOOK_SECRET` in env.

### Technical context

- **Backend:**
  - New module `backend/app/services/whatsapp/` with `provider.py` (interface) + `cloud_api.py` (Meta) + `mock.py` (existing logic moved here).
  - Selected via `WHATSAPP_PROVIDER` env (`mock` | `cloud_api`). Default `mock` in dev/test.
  - New webhook route `POST /api/v1/webhooks/whatsapp` — verifies HMAC, updates `notifications.whatsapp_delivered`, `whatsapp_failed_reason`.
  - DB: ALTER `notifications` to add `whatsapp_delivered boolean`, `whatsapp_failed_reason text`. New migration `008_whatsapp_delivery.sql`.
- **Frontend:** Settings page already shows the per-creditor opt-out; verify enforcement end-to-end with the real provider.
- **Tests:**
  - Unit-test the `WhatsAppProvider` interface against `mock`.
  - Integration test: opt-out by debtor → notification row exists → no provider call.
  - Webhook signature-verification test.

### Acceptance signals

- Sending a real WhatsApp template succeeds in staging.
- Debtor opt-out for creditor A still receives WhatsApp from creditor B and from in-app for both.
- A failed send produces a notification row with `whatsapp_delivered=false` and a reason.

### Branch & PR

- Branch: `006-whatsapp-business-integration`
- Updates: `project-status.md` "Real WhatsApp" out of MVP scope → moved to "Shipped"; `database-schema.md` notifications table; new migration entry.

---

## Phase 7 — Payment-gateway settlement

**Maps to:** `spec-kit-plan.md#F7`, UC5.

### Problem statement

> Integrate a payment gateway (HyperPay or Tap, region-appropriate) so the `payment_pending_confirmation → paid` transition can be resolved automatically by a successful gateway charge. The creditor must still have the manual confirm path. Both paths must produce identical audit and commitment-score events.

### Pre-answered clarifications

- **HyperPay or Tap?** Decide via a one-page comparison in the spec phase. Default leaning Tap (better SAR card support, simpler webhook model).
- **Who pays the fee?** Creditor (out of receivable). UI clearly shows "you'll receive X SAR" net of fee. Configurable later.
- **Refunds?** Out of scope this phase. Manual reversal via existing audit trail.
- **Saved cards?** No tokenization in this phase. One-shot charge.
- **Sandbox?** Yes — separate `PAYMENT_PROVIDER=sandbox|production` toggle.
- **What if the gateway succeeds but the webhook is delayed?** Idempotency on the gateway-reference key. Late webhook is a no-op if the debt is already `paid`.

### Technical context

- **Backend:**
  - New `backend/app/services/payments/` with provider interface.
  - New endpoint `POST /api/v1/debts/{id}/pay-online` — debtor only, debt must be `active` or `overdue`. Creates a charge intent, returns redirect or hosted-page URL.
  - Webhook `POST /api/v1/webhooks/payments` — verifies signature, transitions debt to `paid`, writes `debt_events` row, fires commitment-score update (same code path as manual confirm).
  - DB: new table `payment_intents` (id, debt_id, provider, provider_ref, status, amount, fee, created_at, completed_at). Migration `009_payment_intents.sql`.
- **Frontend:**
  - Debtor side of debt details: new "Pay online" button alongside the existing "Mark paid" button.
  - Post-payment redirect page polls debt status until `paid` or timeout (60 s) before redirecting to dashboard.
- **Tests:**
  - Webhook idempotency test (same provider_ref delivered twice → one transition).
  - Equivalence test: manual `confirm-payment` and gateway-webhook path produce same `debt_events` and same commitment-score delta.

### Acceptance signals

- A debtor can pay an active debt online; debt transitions to `paid` automatically.
- Replayed webhook is a no-op.
- Manual creditor confirmation still works for cash payments.

### Branch & PR

- Branch: `007-payment-gateway-settlement`
- Updates: significant — `database-schema.md` (new table, new migration), `api-endpoints.md` (new endpoints), `use-cases.md` UC5 row.

---

## Phase 8 — Surface Groups in MVP nav (UC9 part 1)

**Maps to:** `spec-kit-plan.md#F8` (split), UC9.

### Problem statement

> The Groups endpoints exist but are not surfaced in the UI. Add Groups to the main nav (debtor-side, behind a feature flag if desired), with: list my groups, create group, invite member, accept invite, view group debts. Auto-netting is **not** in scope here — settlements are recorded as opaque rows. Members in an accepted group can see each other's group-tagged debts (per the constitution: privacy is intentionally relaxed inside groups).

### Pre-answered clarifications

- **Feature flag?** Yes — `profile.groups_enabled` boolean, default `true` for new users (no prod harm), but gate behind a settings toggle so existing testers opt in.
- **Who can create groups?** Anyone (creditor or debtor account type), since the consumer model is friends/family.
- **Member cap?** 20 members per group for MVP (reasonable for a family/friend circle). Hard-cap on invite endpoint.
- **Visibility?** Members of an accepted group see each other's `debts` where `group_id` matches the group. Personal debts outside any group remain private.
- **Leaving a group?** Yes — `POST /groups/{id}/leave`. Pending invites can be `decline`d. Owner cannot leave; must transfer ownership or delete the group (delete only allowed if zero debts).
- **Tagging a debt to a group?** When creating a debt and both parties are in the same accepted group, an optional "group" dropdown appears.

### Technical context

- **Backend:**
  - Likely new endpoints: `POST /groups/{id}/leave`, `POST /groups/{id}/invite/decline`, `DELETE /groups/{id}` (owner only, blocked if debts exist).
  - DB: ALTER `profiles` add `groups_enabled boolean default true`. Migration `010_groups_feature_flag.sql`.
  - Cap enforcement: invite endpoint checks accepted-member count.
- **Frontend:**
  - New surface from `GroupsPage.tsx` — list, detail, invite, accept, leave.
  - Create-debt form: optional group selector when both parties share an accepted group.
  - Settings: groups feature toggle.
- **Tests:**
  - Member cap exceeded → 409.
  - Non-member tries to view group debts → 403.
  - Leave when not a member → 404.

### Acceptance signals

- A user can create a group, invite by email/phone, accept, view shared debts.
- Member cap is enforced.
- A debt can be tagged with a group at creation; group members can see it.

### Branch & PR

- Branch: `008-groups-mvp-surface`
- Updates: `use-cases.md` UC9 from `⛔` to `🟡` (auto-netting still pending), `database-schema.md` profiles + migration.

---

## Phase 9 — Group auto-netting (UC9 part 2)

**Maps to:** `spec-kit-plan.md#F8` (split), UC9 completion.

### Problem statement

> Implement auto-netting for debts inside a group so that transitive obligations settle to the minimum-edge transfer graph. When a group member triggers "settle group", the system computes net positions, presents the proposed transfers, and on confirmation atomically marks the underlying debts as paid (with appropriate audit trail) and writes corresponding `group_settlements` rows.

### Pre-answered clarifications

- **Who can trigger?** Group owner or any member (subject to all-members-must-confirm — see below).
- **Algorithm?** Standard greedy min-flow netting on the directed multigraph of (debtor → creditor, amount). Output is a list of (from, to, amount) transfers minimizing the number of transfers.
- **Confirmation model?** Two-phase: (1) any member proposes a settlement run → snapshots current group debts → presents proposed transfers; (2) every party in the proposed transfer must confirm or counter within 7 days. If any party rejects, the proposal is dropped — original debts are untouched.
- **Atomicity?** When all confirmations land, the backend marks every snapshotted debt as `paid` in a single transaction, writes settlement rows, and updates commitment scores per debt as if each were paid on time (no penalty, no early bonus).
- **Edge cases?** Different currencies in the same group → block ("can't auto-net mixed currencies in MVP"). New debts added during the 7-day window are ignored (they're not in the snapshot).
- **Privacy?** Settlement proposal shows everyone's amount-owed lines to all members of the proposal. This is consistent with the existing group-privacy relaxation.

### Technical context

- **Backend:**
  - New tables: `group_settlement_proposals` (id, group_id, proposed_by, snapshot jsonb, status, created_at, expires_at), `group_settlement_confirmations` (proposal_id, user_id, status, responded_at). Migration `011_group_settlement_proposals.sql`.
  - New endpoints: `POST /groups/{id}/settlement-proposals`, `GET /groups/{id}/settlement-proposals/{pid}`, `POST /groups/{id}/settlement-proposals/{pid}/confirm`, `POST /groups/{id}/settlement-proposals/{pid}/reject`.
  - Algorithm in `backend/app/services/netting.py`. Pure function, heavily tested.
- **Frontend:** new "Settle group" button on group detail page; proposal review screen; per-user confirmation flow with notifications.
- **Tests:**
  - Algorithm: 3-cycle resolves to 1 transfer; 4-node chain resolves to N-1 transfers; mixed currency raises.
  - End-to-end: 3 members, circular debts, all confirm, all debts hit `paid` atomically.
  - One-rejects: nothing changes.

### Acceptance signals

- 3-member circular debt scenario resolves to ≤ 2 transfers and all debts settle.
- A rejected proposal leaves all debts in their prior state.
- Mixed-currency proposal is rejected at proposal time, not at confirmation.

### Branch & PR

- Branch: `009-groups-auto-netting`
- Updates: `use-cases.md` UC9 → ✅, two new migrations.

---

## Phase 10 — Backend stops running as Postgres role

**Maps to:** `spec-kit-plan.md#F9`, constitution §4.

### Problem statement

> Today the backend connects to Postgres as the schema owner and bypasses RLS at runtime; defence is in handler code only. Switch the backend to use scoped, per-request JWTs so RLS is enforced at the database layer. A handler that forgets the authorisation check must fail to leak data.

### Pre-answered clarifications

- **Mechanism?** PostgREST-style: backend sets the request-scoped role (`SET LOCAL ROLE authenticated`) and `request.jwt.claims` from the verified Supabase JWT, before any query. Handle this in middleware so handlers don't need to remember.
- **Service-role escapes?** A small whitelist for tasks that legitimately need elevation (the lazy sweeper, `handle_new_user` is already a trigger). These run via a separate connection pool.
- **Performance?** SET LOCAL is cheap. Connection pooling stays on PgBouncer in transaction-pooling mode (must verify SET LOCAL works there; otherwise session pooling for this path).
- **Migration plan?** Run RLS-on and RLS-off in shadow mode for one release: log every query that *would* fail under RLS but doesn't, fix the gaps, then flip the switch.

### Technical context

- **Backend:**
  - Middleware: `backend/app/core/db_session.py` — wrap each request transaction with `SET LOCAL request.jwt.claims = '<jwt>'` and `SET LOCAL ROLE authenticated`.
  - Repository: ensure `repositories/postgres.py` uses the request-scoped session, not a global one.
  - Sweeper / system tasks: separate session factory using a service role (no JWT).
- **DB:** revisit RLS policies — add explicit policies wherever shadow-mode logging shows missing ones. Likely tweaks to `business_profiles`, `notifications`, `attachments`.
- **Tests:**
  - Negative tests: a handler stripped of its authorisation check must still 403/404 for cross-user access (the test proves RLS, not handler logic).
  - Performance smoke: P50 query time within 10% of pre-change baseline.

### Acceptance signals

- All tests pass with the new middleware enabled.
- A deliberately-broken handler (no `get_authorized_debt`) returns no leaked rows.
- Shadow-mode log is empty for one full E2E run.

### Branch & PR

- Branch: `010-backend-rls-enforcement`
- Updates: `project-status.md` "Known technical debt" — drop the "backend runs as Postgres role" bullet.

---

# Block 3 — AI tier (paid)

All Block 3 phases assume the gating from constitution §10: `/api/v1/ai/*` returns 403 unless `profile.ai_enabled = true`.

## Phase 11 — AI receipt extraction

**Maps to:** `spec-kit-plan.md#F11`.

### Problem statement

> Given a receipt image (jpg/png/pdf), extract a populated `DebtCreate` draft (debtor name, amount, currency, description, due date) with confidence scores. The creditor reviews and edits before submitting. Hard-gated on `profile.ai_enabled`.

### Pre-answered clarifications

- **Model?** Claude (vision) via Anthropic API. Use the Pydantic-schema → JSON pattern.
- **Confidence threshold?** Surface every field; if any field has confidence < 0.7, highlight it. Don't auto-submit ever.
- **Currency default?** SAR if not detected.
- **Due date?** If not on the receipt (usually isn't), default to "not detected" — creditor enters manually.
- **PII?** Receipts may contain debtor names. Storage uses the existing `receipts` bucket with RLS. Don't log full text in stdout.
- **Cost control?** Per-user daily limit (env-configurable, default 50/day). 429 with retry-after when exceeded.

### Technical context

- **Backend:**
  - New endpoint `POST /api/v1/ai/receipt-extract` (multipart: image + optional hint).
  - Service `backend/app/services/ai/receipt_extract.py`.
  - Reuse the `receipts` bucket — image is stored once, referenced by URL in the model call.
- **Frontend:** new "Scan receipt" button on the create-debt form (creditor only, AI tier only). Opens camera or file picker, calls the endpoint, prefills the form with confidence highlighting.
- **Tests:**
  - Mock provider for tests (returns canned JSON).
  - Gating test: `ai_enabled=false` → 403.
  - Daily limit test: 51st call → 429.

### Acceptance signals

- Demo receipt set: median field-level confidence ≥ 0.7, fully populated draft.
- Gating works.
- Daily limit returns 429 with translated message.

### Branch & PR

- Branch: `011-ai-receipt-extraction`
- Updates: `use-cases.md` UC10 row, `api-endpoints.md` (new endpoint).

---

## Phase 12 — Voice-to-debt draft polish

**Maps to:** `spec-kit-plan.md#F12`.

### Problem statement

> Replace the stub in `POST /ai/debt-draft-from-voice` with a real transcript pipeline (Arabic and English). The endpoint already accepts a transcript; this phase adds upstream audio handling so the creditor records or uploads audio, the system transcribes, and the same draft-extraction logic runs.

### Pre-answered clarifications

- **STT provider?** OpenAI Whisper (cheap, multilingual including Arabic). Behind a provider interface.
- **Audio formats?** webm, mp3, wav, m4a. Max 60 s for MVP.
- **Storage?** `voice-notes` bucket, same path convention.
- **Already-have-transcript path?** Keep it — useful for tests and for clients that bring their own STT.
- **Round-trip?** `raw_transcript` returned in `VoiceDebtDraftOut` so the UI can show what was heard.

### Technical context

- **Backend:**
  - Modify `POST /ai/debt-draft-from-voice` to accept either `multipart` (audio) or JSON (transcript). Discriminate on content-type.
  - New service `backend/app/services/ai/transcribe.py`.
  - Reuse the receipt-extraction prompt logic for the transcript-to-draft step.
- **Frontend:** voice-record button on create-debt form (AI tier).
- **Tests:** mock transcribe + canned draft. Gating + daily limit identical to Phase 11.

### Acceptance signals

- Spoken Arabic produces a populated draft and a round-trippable transcript.
- 60+-second audio is rejected client-side.

### Branch & PR

- Branch: `012-ai-voice-debt-draft`

---

## Phase 13 — Merchant-chat grounding

**Maps to:** `spec-kit-plan.md#F13`.

### Problem statement

> Ground `POST /ai/merchant-chat` answers in the caller's actual ledger. The chatbot must be able to answer "who owes me the most?", "did Ahmed pay me last month?", "what's my overdue exposure?" without hallucinating, and must never expose debts the user is not a party to.

### Pre-answered clarifications

- **RAG vs tool-use?** Tool-use. Define a small set of tools: `list_debts(filter)`, `get_debt(id)`, `get_dashboard_summary()`, `get_commitment_history(user_id)` — all of which call the existing repository scoped to the caller. The model picks tools, the backend executes with the caller's auth.
- **Streaming?** Optional. Phase ships non-streaming first.
- **Conversation history?** Maintained per-call by the client (stateless on backend). Last 10 turns only.
- **Refusals?** If the user asks about another user's data, the model must refuse — and the tools wouldn't return it anyway because they're scoped.
- **Rate limiting?** Same daily limit pattern as Phases 11–12.

### Technical context

- **Backend:**
  - `backend/app/services/ai/merchant_chat.py` — orchestrates tool-use loop.
  - Tools call the existing `repo` with the caller's user_id. No new endpoints, just internal functions.
  - Logging: log tool calls (not args) for observability.
- **Frontend:** chat surface on `AIPage.tsx`.
- **Tests:**
  - Cross-user leakage: caller A asks about caller B's debts → no leak.
  - Hallucination guard: question with no relevant data → "I don't have that information" rather than fabrication.

### Acceptance signals

- Three demo prompts return correct, grounded answers from a seeded ledger.
- Cross-user prompt does not leak data.

### Branch & PR

- Branch: `013-ai-merchant-chat-grounding`

---

# Housekeeping (run in parallel)

## H1 — TypeScript codegen for `frontend/src/lib/types.ts`

**Maps to:** `spec-kit-plan.md#H2`.

### Problem statement

> The frontend types are a manual mirror of the backend Pydantic schemas and drift is possible. Generate the TypeScript types from `backend/app/schemas/domain.py` automatically and run the generator in CI; fail CI if the generated file diverges from the committed copy.

### Pre-answered clarifications

- **Tool?** `datamodel-code-generator` for Pydantic → JSON Schema, then `json-schema-to-typescript`. Or skip the middle step and use Pydantic v2's native JSON Schema export piped to `json-schema-to-typescript` directly.
- **Where does it live?** `scripts/generate-types.sh` at repo root. CI step: run the script, then `git diff --exit-code frontend/src/lib/types.ts`.
- **Custom types?** A small `types.custom.ts` for hand-written helpers; never edit generated file.

### Acceptance signals

- CI fails when a backend enum changes without regenerating.
- Existing usages in the frontend compile unchanged after first generation pass.

### Branch & PR

- Branch: `H1-types-codegen`

---

## H2 — Drop legacy `thabetha-attachments` bucket

**Maps to:** `spec-kit-plan.md#H1`.

### Problem statement

> Migration 001 created a `thabetha-attachments` bucket; canonical buckets are now `receipts` + `voice-notes`. Migrate any straggler objects to the canonical buckets, update any references, and drop the legacy bucket.

### Pre-answered clarifications

- **Stragglers?** Likely none in production, but check via `select bucket_id, count(*) from storage.objects group by 1`.
- **Migration?** New migration `012_drop_legacy_bucket.sql`. Idempotent — `if exists`.
- **Risk?** If any code still references the legacy bucket, this breaks it. Grep `'thabetha-attachments'` repo-wide first.

### Acceptance signals

- Bucket gone, no broken paths, all attachments still resolve.

### Branch & PR

- Branch: `H2-legacy-bucket-cleanup`

---

## H3 — Test coverage for every state transition

**Maps to:** `spec-kit-plan.md#H3`, constitution §12.

### Problem statement

> The constitution requires a test for every state transition. Audit the existing transition table in `claude-handoff/api-endpoints.md` and `../debt-lifecycle.md` against `backend/tests/`. Add the missing tests.

### Pre-answered clarifications

- **Format?** One test function per (from_state, action) pair, plus negative tests for disallowed transitions (asserting 409).
- **Coverage target?** 100% of the transition table. Each row in the canonical state machine maps to at least one passing positive test.
- **Output?** A short `backend/tests/lifecycle/README.md` explaining the table-test pattern and listing each transition with its test name.

### Acceptance signals

- Coverage matrix in the README has a green checkmark for every transition.
- Disallowed transitions all return 409 in tests.

### Branch & PR

- Branch: `H3-transition-test-coverage`

---

# Per-phase deliverable checklist (use this in every PR)

For every phase above, the PR description must include:

```
## Phase: <N> — <slug>

- [ ] spec-kit `spec.md` committed under `specs/NNN-<slug>/`
- [ ] spec-kit `plan.md`, `tasks.md` committed
- [ ] Tests: <list>
- [ ] Migration(s) added: <list or "none">
- [ ] i18n strings added: <count> AR + <count> EN
- [ ] `claude-handoff/project-status.md` updated
- [ ] `claude-handoff/use-cases.md` row updated
- [ ] `claude-handoff/api-endpoints.md` updated (if endpoints changed)
- [ ] `claude-handoff/database-schema.md` updated (if schema changed)
- [ ] Constitution rules respected (cite the §s touched)
```