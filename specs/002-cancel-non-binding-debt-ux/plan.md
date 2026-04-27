# Implementation Plan: Cancel Non-Binding Debt UX

**Branch**: `002-cancel-non-binding-debt-ux` | **Date**: 2026-04-28 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/002-cancel-non-binding-debt-ux/spec.md`

## Summary

Replace the existing one-tap "Cancel" button (which currently fires `POST /debts/{id}/cancel` with a hardcoded `"Cancelled"` message) with a two-tap confirmation dialog containing an always-visible optional message textarea (≤200 chars). The dialog is rendered only on the creditor's view of debts in `pending_confirmation` or `edit_requested`. After a successful cancel, the user remains on the debt details page; the page re-fetches and shows the new `cancelled` status. Errors from concurrent state changes (409) surface a translated, recoverable inline error and trigger a refresh. No backend, schema, or transition changes — purely a frontend surfacing.

## Technical Context

**Language/Version**: TypeScript 5.x (frontend); Python 3.12 (backend, untouched)
**Primary Dependencies**: React 19, Vite, `@supabase/supabase-js`, `lucide-react` (icon set already in use)
**Storage**: N/A (no schema or storage changes; backend already writes the `debt_events` cancel row)
**Testing**: Backend `pytest` with `FastAPI.TestClient` and `REPOSITORY_TYPE=memory` (existing transition test re-verified). No frontend test harness is currently set up — manual two-locale smoke test documented in `quickstart.md`.
**Target Platform**: Web (Chrome/Safari latest), bilingual AR (RTL) / EN (LTR), desktop and mobile breakpoints
**Project Type**: Web application — `frontend/` (React+Vite) + `backend/` (FastAPI). Only `frontend/` is touched in this phase.
**Performance Goals**: Cancel transition perceived under 800 ms on local Supabase (matches Phase 4 polish budget). Dialog open under 100 ms.
**Constraints**: Two-tap path (US1, FR-002); no implicit navigation after success (FR-011); 200-char hard cap on message (FR-003); both AR and EN coverage (FR-008).
**Scale/Scope**: Single page modified (`DebtsPage.tsx`), one new dialog component, ~5 new i18n keys × 2 locales.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Compliance |
|-----------|-----------|
| I. Bilateral Confirmation | ✅ No transition logic change. Cancel still respects existing allowed source states. |
| II. Canonical 7-State Lifecycle | ✅ Reuses existing `pending_confirmation`/`edit_requested → cancelled` transition; no new states or string IDs. |
| III. Commitment Indicator | ✅ Cancellation does not affect `commitment_score` (no score event written for cancels). |
| IV. Per-User Data Isolation | ✅ Affordance gated client-side on `viewer === debt.creditor_id`; backend handler `repo.cancel_debt(user.id, ...)` already enforces server-side. |
| V. Arabic-First | ✅ All new strings (5 keys) added to `frontend/src/lib/i18n.ts` for both locales; dialog uses existing direction-aware layout. |
| VI. Supabase-First Stack | ✅ No new auth, storage, or DB primitives — reuses existing `apiRequest` (`Authorization: Bearer <Supabase JWT>`). |
| VII. Schemas Are SoT | ✅ No enum or schema changes. Frontend uses existing `DebtStatus` from `lib/types.ts`. |
| VIII. Audit Trail Per Debt | ✅ Existing `cancel_debt` repository call writes the `cancelled` `debt_events` row with the actor and the optional message. |
| IX. QR Identity | ✅ Not relevant to this feature. |
| X. AI Paid-Tier | ✅ Not relevant to this feature. |

**Result**: PASS. No violations; no Complexity Tracking entries needed.

## Project Structure

### Documentation (this feature)

```text
specs/002-cancel-non-binding-debt-ux/
├── plan.md              # This file
├── spec.md              # Feature specification (already authored, clarified)
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output (manual two-locale verification script)
├── contracts/
│   └── cancel-debt-ui.md   # Front-end / API contract surface used by this feature
├── checklists/
│   └── requirements.md  # Spec-quality checklist (already passed)
└── tasks.md             # Phase 2 output (/speckit-tasks command — NOT created here)
```

### Source Code (repository root)

```text
frontend/
├── src/
│   ├── pages/
│   │   └── DebtsPage.tsx           # Modified: replace inline cancel button (line ~683) with dialog trigger + state
│   ├── components/
│   │   ├── CancelDebtDialog.tsx    # NEW: two-tap confirmation modal with optional message textarea
│   │   ├── AttachmentUploader.tsx  # (existing, unchanged)
│   │   ├── Layout.tsx              # (existing, unchanged)
│   │   └── ProtectedRoute.tsx      # (existing, unchanged)
│   └── lib/
│       └── i18n.ts                 # Modified: 5 new keys × AR + EN
└── tests/                          # No frontend test harness yet (out of scope to add one)

backend/
└── (untouched — endpoint, repository method, notification wiring all already exist)
```

**Structure Decision**: Web-application layout (Option 2). All changes land in `frontend/`; the backend stays untouched. The new dialog is its own component (`CancelDebtDialog.tsx`) so it is testable in isolation and reusable if Phase 4 demo polish surfaces a second cancel entry-point (e.g., from the dashboard).

## Complexity Tracking

> No constitution violations. Section intentionally empty.
