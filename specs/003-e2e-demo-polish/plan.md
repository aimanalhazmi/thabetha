# Implementation Plan: End-to-End Demo Polish

**Branch**: `003-e2e-demo-polish` | **Date**: 2026-04-28 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/003-e2e-demo-polish/spec.md`

## Summary

A polish-sweep + test + doc bundle, not a feature. Three deliverables:

1. **Polish pass** across `DebtsPage.tsx`, `DashboardPage.tsx`, `NotificationsPage.tsx`, `QRPage.tsx`: every transition button gets a loading state, every empty page renders a translated empty-state, every catch block in those pages funnels errors through a new `humanizeError(err, language)` helper that maps the `apiRequest` `Error("STATUS: body")` shape to a translated user-facing string. Untranslated **existing** strings encountered along the way are collected (not fixed) for Phase 5.
2. **Two integration tests** in `backend/tests/test_e2e_demo_path.py`: the canonical happy path and the edit-request branch, both walking the eight-state lifecycle against the in-memory repository and asserting the commitment-score delta.
3. **Demo script** at `docs/demo-script.md`: 8–12 numbered steps that a fresh contributor can execute on local Supabase in under 5 minutes, starting from the **pre-seeded** demo accounts already created by `SEED_DEMO_DATA=true` in `backend/app/services/demo_data.py` (`merchant-1`/Baqala Al Noor and `customer-1`/Ahmed).

No new schemas, migrations, endpoints, or repository methods. The polish work surfaces existing backend behavior more cleanly.

## Technical Context

**Language/Version**: TypeScript 5.x (frontend, strict), Python 3.12 (backend tests). No backend source-code changes.
**Primary Dependencies**: React 19, Vite, `@supabase/supabase-js` (frontend); FastAPI + `pytest` + `TestClient` (backend tests). `lucide-react` for any icon additions.
**Storage**: N/A — no schema or migration changes. Demo seed data already exists in `backend/app/services/demo_data.py`.
**Testing**: `pytest` with `REPOSITORY_TYPE=memory` (forced by `tests/conftest.py`). Two new integration tests; combined runtime under 5 seconds (SC-005).
**Target Platform**: Web (Chrome/Safari latest), bilingual AR (RTL) / EN (LTR), local Supabase Docker stack.
**Project Type**: Web application — `frontend/` (React+Vite) + `backend/` (FastAPI). Backend touches are tests only.
**Performance Goals**: 800 ms perceived transition latency on local Supabase (FR-011, SC-002). Combined integration-test runtime < 5 s.
**Constraints**: 5-minute median demo completion (SC-001); 8–12 demo-script steps (SC-006); zero raw API errors leaking to UI (SC-003); zero blank panels on the four touched pages (SC-004).
**Scale/Scope**: Four pages modified, one helper added (`lib/errors.ts`), one new test file with two test functions, one new doc, ~10 new i18n keys × 2 locales (for empty-states and error-humanizer mappings only — existing untranslated strings deferred to Phase 5).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Compliance |
|-----------|-----------|
| I. Bilateral Confirmation | ✅ No transition logic change. Demo script and tests exercise the existing happy path exactly as defined. |
| II. Canonical 7-State Lifecycle | ✅ Tests assert the canonical sequence; no new states or string IDs introduced. |
| III. Commitment Indicator | ✅ Tests assert the existing rules (`+3` / `+1` / `−2 × 2^N`) but do not modify them. |
| IV. Per-User Data Isolation | ✅ No new endpoints or queries. |
| V. Arabic-First | ✅ Every **new** string (empty-state copy, error-humanizer mappings) lands in `frontend/src/lib/i18n.ts` for both locales. Untranslated **existing** strings are collected, not fixed (handed to Phase 5). |
| VI. Supabase-First Stack | ✅ No auth, storage, or DB primitive changes. |
| VII. Schemas Are SoT | ✅ No enum, schema, or `lib/types.ts` changes. |
| VIII. Audit Trail Per Debt | ✅ Demo and tests rely on existing `debt_events` rows; no new event types. |
| IX. QR Identity | ✅ Demo reuses Phase 2's QR pass-through; not modified here. |
| X. AI Paid-Tier | ✅ Not relevant. |

**Result**: PASS. No violations; no Complexity Tracking entries needed.

## Project Structure

### Documentation (this feature)

```text
specs/003-e2e-demo-polish/
├── plan.md              # This file
├── spec.md              # Feature spec (clarified)
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output (minimal — no persisted entities)
├── quickstart.md        # Phase 1 output (verification harness)
├── contracts/
│   └── humanize-error.md   # Internal contract for the error-humanizer helper
├── checklists/
│   └── requirements.md  # Spec-quality checklist (already passed)
└── tasks.md             # Phase 2 output (NOT created here)
```

### Source Code (repository root)

```text
frontend/
├── src/
│   ├── lib/
│   │   ├── errors.ts            # NEW: humanizeError(err, language, context?) — maps apiRequest Error to translated string
│   │   ├── i18n.ts              # MODIFIED: ~10 new keys × AR + EN
│   │   └── api.ts               # (existing, untouched)
│   ├── pages/
│   │   ├── DebtsPage.tsx        # MODIFIED: catch blocks → humanizeError; loading state on transition buttons; empty-states
│   │   ├── DashboardPage.tsx    # MODIFIED: same sweep pattern
│   │   ├── NotificationsPage.tsx# MODIFIED: same sweep pattern
│   │   ├── QRPage.tsx           # MODIFIED: same sweep pattern
│   │   └── (others)             # untouched
│   └── components/              # untouched

backend/
├── app/
│   └── services/
│       └── demo_data.py         # (existing, untouched)
└── tests/
    └── test_e2e_demo_path.py    # NEW: two integration tests

docs/
└── demo-script.md               # NEW: 8–12 numbered steps
```

**Structure Decision**: Web-application layout. Frontend changes are spread across four pages plus one new helper file (`lib/errors.ts`). Backend changes are tests only. The demo script lives at `docs/demo-script.md` (top-level `docs/`, not under `docs/spec-kit/`) so it is discoverable by anyone reading the project README, not just spec-kit users.

### Resolved planner-level details (from spec checklist Notes)

- **Demo script location**: `docs/demo-script.md` (top-level `docs/`, not nested under `spec-kit/`).
- **"Loading indicator" definition**: any of (a) button shows a spinner glyph, (b) button is `disabled` while in flight, or (c) button label changes to a loading symbol such as `…`. Match the existing pattern at `frontend/src/pages/AuthPage.tsx:175` (`{loading ? '...' : tr('signIn')}`) for consistency.

## Complexity Tracking

> No constitution violations. Section intentionally empty.
