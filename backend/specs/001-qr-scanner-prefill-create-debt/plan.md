# Implementation Plan: QR-scanner pass-through to Create Debt

**Branch**: `001-qr-scanner-prefill-create-debt` | **Date**: 2026-04-27 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-qr-scanner-prefill-create-debt/spec.md`

## Summary

Make the QR scan a real shortcut to a debt: a creditor scans a debtor's short-lived QR token, sees a confirm step on the scanner with the resolved profile preview (name, last-4 phone, commitment indicator) and explicit "Create debt for this person" / "Cancel" actions, then lands on the Create Debt form with the debtor identity prefilled and locked. The form re-resolves the token at mount and at submit; expiration, self-scan, and unknown tokens are handled with translated messages without losing the creditor's already-entered fields. Manual debtor entry remains the alternate path. Single-use of the token is enforced client-side by stripping `qr_token` from the URL after a successful create. **One small backend change** — a 3-line self-billing guard added to the existing `POST /debts` handler (constitution §IV mirror of the UI block). No schema change, no migration, no new endpoint.

## Technical Context

**Language/Version**: TypeScript 5.x (frontend, strict), Python 3.12 (backend, no source changes)
**Primary Dependencies**: React 19 + Vite + React Router (frontend); `@supabase/supabase-js` for auth; FastAPI (backend, untouched)
**Storage**: N/A for this feature — no new persistence. Existing QR tokens live in the repository (memory + Postgres) per the QR identity principle.
**Testing**: `FastAPI.TestClient` integration test in `backend/tests/` covering the create-debt-with-`debtor_id` path under `REPOSITORY_TYPE=memory`. Frontend: manual E2E in PR description (no Vitest harness exists today; do not add one in this phase).
**Target Platform**: Web (mobile-first responsive). Local Supabase stack for dev (`supabase start`).
**Project Type**: Web application (frontend + backend split — Option 2).
**Performance Goals**: Scan-to-prefilled-form under 1 second on local Supabase (SC-006). One QR resolve on mount + one on submit; no extra round trips.
**Constraints**: Arabic-first; both new strings land in `frontend/src/lib/i18n.ts` (AR + EN). RTL must render correctly in the scanner confirm sheet and the locked debtor field. No new endpoints; no migration.
**Scale/Scope**: Two frontend files touched (`QRPage.tsx`, `DebtsPage.tsx`), one i18n file. ~4 new translation keys. One new backend integration test asserting the `debtor_id`-linked path.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Relevance | Compliance |
|---|---|---|
| I. Bilateral confirmation | A QR-originated debt enters `pending_confirmation` exactly like manual entry; no shortcut around debtor accept. | ✅ Lifecycle untouched. |
| II. Canonical 7-state lifecycle | No new transitions, no new states. | ✅ No-op. |
| III. Commitment indicator | Preview shows the existing `commitment_score` badge; no scoring logic added. | ✅ Read-only surface only. |
| IV. Per-user data isolation | QR resolve is already auth-gated; the resolved preview is the existing minimal-PII view (no `tax_id`, no email). Self-billing rule mirrored in the `POST /debts` handler (T018a) so UI and backend both enforce it. | ✅ No new data exposure; double-enforced rule. |
| V. Arabic-first | Four new strings (`qr_expired_ask_refresh`, `cannot_bill_self`, `clear_debtor`, `scanned_debtor_label`) land in AR + EN. | ✅ Will add to `lib/i18n.ts`. |
| VI. Supabase-first stack | No bypass; uses existing FastAPI proxy + Supabase auth. | ✅ |
| VII. Schemas as source of truth | `DebtCreate` already accepts `debtor_id` (`backend/app/schemas/domain.py:122`); no schema change. | ✅ Mirror in `frontend/src/lib/types.ts` already present. |
| VIII. Audit trail per debt | Standard create path → `debt_events` row written by existing logic. | ✅ |
| IX. QR identity is bilateral & short-lived | Reuses existing 10-min TTL token; no new identity surface; preview-only. Single-use enforced client-side per Q2 clarification. | ✅ |
| X. AI paid-tier gating | Not relevant. | n/a |

**Result**: All gates pass. No deviations recorded. Complexity Tracking section is omitted intentionally.

## Project Structure

### Documentation (this feature)

```text
specs/001-qr-scanner-prefill-create-debt/
├── plan.md              # this file
├── research.md          # Phase 0 — small implementation decisions (R1–R5)
├── data-model.md        # Phase 1 — derived form-state machine (no DB entities)
├── quickstart.md        # Phase 1 — manual E2E walkthrough for the PR reviewer
├── contracts/
│   └── frontend-routes.md  # Deep-link contract: /debts/new?qr_token=<token>
├── checklists/
│   └── requirements.md  # already created by /speckit.specify
└── tasks.md             # created by /speckit.tasks (NOT this command)
```

### Source Code (repository root)

```text
backend/                                   # No source changes; one new test only.
├── app/
│   ├── api/
│   │   ├── qr.py                          # untouched — GET /qr/resolve/{token} returns ProfileOut
│   │   └── debts.py                       # untouched — POST /debts already accepts debtor_id
│   └── schemas/domain.py                  # untouched — DebtCreate has debtor_id (line 122) + debtor_name (line 121)
└── tests/
    └── test_create_debt_with_debtor_id.py # NEW — integration: resolve → create with debtor_id → assert linkage

frontend/
└── src/
    ├── pages/
    │   ├── QRPage.tsx                     # CHANGED — add scanner confirm sheet (preview + Cancel/Create);
    │   │                                  #           on confirm: navigate(`/debts/new?qr_token=${token}`)
    │   └── DebtsPage.tsx                  # CHANGED — on mount, if URL has qr_token: resolve + lock debtor fields
    │                                      #           + render preview header; on submit: re-resolve, on success
    │                                      #           strip qr_token from URL (history.replaceState)
    └── lib/
        └── i18n.ts                        # CHANGED — add 4 keys (AR + EN)
```

**Structure Decision**: Web application (Option 2). The repo already follows the `backend/` + `frontend/` split. This feature is a frontend-only change with one supporting backend test; no new directories.

## Phase 0 — Research

Output: [`research.md`](./research.md). Resolves the small set of decisions that the spec deliberately leaves to the implementer:

- **R1** — Where does the scanner's confirm step live (overlay on `QRPage.tsx` vs. dedicated route)? Decision: in-page sheet/overlay on `QRPage.tsx` so "Cancel" trivially equals "dismiss the sheet, camera stays live".
- **R2** — How does the Create Debt form handle the transient loading state while resolving on mount? Decision: skeleton header in place of the preview; debt fields disabled until resolve completes or fails.
- **R3** — On submit-time re-resolve failure, how do we preserve the user's typed fields? Decision: keep the form mounted, swap the preview header for an error banner with "Rescan" / "Switch to manual entry" buttons; never unmount the form.
- **R4** — Self-scan blocking — compare resolved profile id against the current user's `id` (from `useAuth`). Decision: yes; suppress the submit button entirely and replace the preview with the translated `cannot_bill_self` message.
- **R5** — Manual-entry fallback when "clear debtor" is tapped — should the URL navigate or `replace`? Decision: `replace`, so the back button doesn't bounce the user back to the prefilled state.

## Phase 1 — Design & Contracts

### Data model — [`data-model.md`](./data-model.md)

No new persistent entities. The data model captures the **form's local state machine** for the Create Debt screen:

- `debtorSource: 'manual' | 'qr-resolving' | 'qr-resolved' | 'qr-expired' | 'qr-self' | 'qr-error'`
- `prefilled: { debtor_id: string; debtor_name: string; phone_last4: string; commitment_score: number } | null`
- Transitions and per-state UI affordances are documented in `data-model.md`.

### Contracts — [`contracts/frontend-routes.md`](./contracts/frontend-routes.md)

The only new contract is a deep-link convention between the scanner and the create-debt screen:

- **Route**: `/debts/new?qr_token=<token>`
- **Producer**: `QRPage.tsx`, after the user confirms on the scanner sheet
- **Consumer**: `DebtsPage.tsx`'s create-debt route, on mount
- **Backend touchpoints**: `GET /qr/resolve/{token}` (existing, `backend/app/api/qr.py:31`), `POST /debts` (existing, accepts `debtor_id` + `debtor_name`)
- **Lifecycle**: token stripped from URL on successful debt creation (Q2 clarification — client-side single-use)

### Quickstart — [`quickstart.md`](./quickstart.md)

A short manual walkthrough a reviewer can run to validate the feature locally: sign in as creditor A in one browser, sign in as debtor B in another, open B's QR page, scan from A's `QRPage.tsx`, confirm on the sheet, fill the Create Debt form, submit, and assert that the resulting debt on B's side carries the correct `debtor_id` link.

### Agent context update

Run `.specify/scripts/bash/update-agent-context.sh claude` after this plan is committed to refresh `CLAUDE.md` markers with any new technology this feature introduces (none in this case — the feature uses already-known stacks).

## Post-design Constitution Re-check

Re-evaluating after Phase 1 artifacts:

- No new persistent entities → no schema, no migration, no RLS surface change. Principle IV stays clean.
- No new endpoints → no new authorisation contract to mirror in handlers. Principle IV stays clean.
- New frontend strings list (4 keys) is bilingual from the start. Principle V satisfied.
- The QR token is read but never persisted past the form lifecycle. Principle IX preserved (TTL still authoritative; client-side URL strip is additive defense).

**Result**: gates still pass; no Complexity Tracking entries needed.

## Complexity Tracking

*Not applicable — Constitution Check passes with no deviations.*
