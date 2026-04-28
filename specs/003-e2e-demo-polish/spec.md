# Feature Specification: End-to-End Demo Polish

**Feature Branch**: `003-e2e-demo-polish`
**Created**: 2026-04-28
**Status**: Draft
**Input**: User description: "Phase 4 of the Thabetha implementation plan — End-to-end demo polish. A fresh user must walk the canonical happy path on local Supabase without dev help: signup → create debt (with receipt, via QR) → debtor accepts → debtor marks paid → creditor confirms → commitment indicator updates. Identify and fix every UX rough edge along that path. Plus one branch: debtor requests edit, creditor approves with new terms. Output: polish-pass PR + one-page demo script + canonical happy-path integration test. Not a feature — it's a polish sweep."

## Clarifications

### Session 2026-04-28

- Q: Where does the canonical happy path begin in the demo and the regression test? → A: Pre-seeded accounts (creditor + debtor exist when the script starts; first action is "sign in"). The signup step from the original input is excluded from this phase's scope.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Happy-path demo runs end-to-end without dev help (Priority: P1) 🎯 MVP

A new contributor (or a hackathon judge) opens local Supabase and the running app, follows a written demo script, and walks the canonical happy path — signup → QR-based debt creation with receipt → debtor accepts → debtor marks paid → creditor confirms → commitment indicator visibly updates — without getting stuck on any UI rough edge and without needing developer assistance.

**Why this priority**: This is the demo. If a fresh contributor can't get through the happy path, the product cannot be shown. Everything else in this phase is in service of this outcome.

**Independent Test**: Hand the written demo script (`docs/demo-script.md`) to a contributor who has never run the app. They execute it on local Supabase. Stopwatch starts when they read step 1, ends when the commitment indicator shows the post-payment delta. Pass = they finish without asking for help and without seeing a raw API error.

**Acceptance Scenarios**:

1. **Given** a fresh local Supabase stack and two seeded accounts (one creditor, one debtor), **When** a contributor walks the demo script top to bottom, **Then** the debt reaches `paid` status and the debtor's commitment indicator increases by the correct amount (per `docs/debt-lifecycle.md`).
2. **Given** the demo script is being executed, **When** any state transition fires (accept, mark-paid, confirm-payment), **Then** the relevant page (debts list, dashboard, notifications) reflects the new state without manual refresh and within 800 ms perceived latency.
3. **Given** any error occurs during the happy path (network blip, expired QR, etc.), **When** the error surfaces in the UI, **Then** the user sees a translated, human-readable message — never a raw HTTP status code or stack trace.

---

### User Story 2 — Edit-request branch completes cleanly (Priority: P1)

The single in-scope branch off the happy path: the debtor requests an edit before accepting, the creditor reviews and approves with new terms, the debtor accepts the new terms, and the rest of the happy path proceeds normally. Every transition in this branch is as polished as the main happy path.

**Why this priority**: The edit-request flow is the most-used non-trivial branch in UC3 and is what makes Thabetha bilateral. If this branch leaks rough edges, the demo's headline differentiation is undermined.

**Independent Test**: Same setup as US1, but the debtor clicks "Request edit" on the new debt instead of "Accept", types a reason and a proposed amount, then the creditor approves. Verify the debt rejoins the happy path with new terms and the rest of the script completes the same way.

**Acceptance Scenarios**:

1. **Given** a debt in `pending_confirmation`, **When** the debtor submits a request-edit with a new amount, **Then** the debt is `edit_requested` on both sides within 800 ms and both UIs show the proposed terms clearly.
2. **Given** a debt in `edit_requested` viewed by its creditor, **When** the creditor approves with the proposed amount unchanged, **Then** the debt returns to `pending_confirmation` with the new amount, the debtor sees the updated terms, and the standard accept button is available.
3. **Given** the edit-request branch has completed, **When** the debtor accepts the new terms, **Then** the rest of the happy path (mark paid → confirm payment → commitment indicator update) runs identically to US1.

---

### User Story 3 — Canonical happy-path regression test guards against regressions (Priority: P1)

A backend integration test walks the full happy path top-to-bottom against the in-memory repository and asserts every status transition and the final commitment-score delta. This test is the **canonical regression test** for the MVP demo path; future phases must keep it green.

**Why this priority**: Without an automated guardrail, the polish achieved in US1/US2 will silently rot. P1 because it is small but lands the durability of everything else.

**Independent Test**: Run `pytest -k happy_path` (or the chosen test name). Test creates two demo users, creates a debt, transitions through the eight-state lifecycle's happy edges, and asserts both the final `paid` status and the commitment-score increment per the lifecycle document. The test must pass without any external services.

**Acceptance Scenarios**:

1. **Given** the in-memory repository is the active backend, **When** the happy-path integration test runs, **Then** it asserts the debt status sequence `pending_confirmation → active → payment_pending_confirmation → paid` and the commitment-score delta matches the rule in `docs/debt-lifecycle.md` (e.g., `+3` if paid before due date).
2. **Given** the edit-request branch is also covered, **When** that test variant runs, **Then** it asserts the additional intermediate status `edit_requested` and that the final terms reflect the creditor's approved values.
3. **Given** any future change breaks a happy-path transition, **When** CI runs, **Then** the test fails with a clear assertion message identifying which transition or final value diverged.

---

### User Story 4 — Demo script is self-serve (~5-minute walkthrough) (Priority: P2)

A one-page markdown demo script (`docs/demo-script.md`) lists ~10 numbered steps that walk the happy path plus the edit-request branch. A new contributor can complete it in under 5 minutes on local Supabase.

**Why this priority**: Necessary for the phase's "demo-able by a fresh contributor" outcome but lower priority than the polish itself — a polished UI without a script is still demo-able by someone who knows the app, while a script without a polished UI fails on contact with reality.

**Independent Test**: Time three different contributors executing the script back-to-back. Median time under 5 minutes. Each contributor finishes without skipping a step or asking for clarification.

**Acceptance Scenarios**:

1. **Given** the demo script exists at `docs/demo-script.md`, **When** read top-to-bottom, **Then** it covers exactly the happy path and the edit-request branch — no other branches are mentioned.
2. **Given** a contributor with only `docs/local-development.md` and the demo script, **When** they execute the script, **Then** they reach the final "commitment indicator updated" step with no off-script action required.
3. **Given** the script is reviewed for length, **When** counted, **Then** it has between 8 and 12 numbered steps and fits on one printed page.

---

### Edge Cases

- **Untranslated string surfaced during the sweep**: Caught visually but **not fixed in this phase** — collected in a new section of `frontend/src/lib/i18n.ts` (or a tracking note in the PR) and folded into Phase 5's bilingual coverage audit. Don't fix individual strings here.
- **Slow transition (> 800 ms perceived)**: If the slow transition is in the lazy commitment-indicator sweeper, profile and fix; if it is repository or notification I/O, file a follow-up but do not block this phase.
- **Loading state missing on a button**: A click that fires a transition with no immediate feedback (spinner, disabled state, or change in label) counts as a rough edge and must be fixed.
- **Failure to refresh after a transition**: A page that requires manual reload to reflect the new state counts as a rough edge.
- **Empty state missing**: An initially empty debts list, dashboard panel, or notifications list that renders blank (no message) counts as a rough edge.
- **Raw API error reaches the UI**: A toast or message containing a status code (`500`, `403`) or backend-provided English string when the user is in Arabic locale counts as a rough edge.
- **Demo script step that needs developer-only knowledge**: A step that says "now run X command" where X is not in the contributor's environment counts as a rough edge in the script (not the UI) and must be replaced with a UI-only action.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A new contributor MUST be able to complete the canonical happy path (sign in as creditor → create debt with receipt via QR → sign in as debtor → accept → mark paid → sign in as creditor → confirm payment → indicator update) on local Supabase using only the demo script and `docs/local-development.md`. The demo MUST start with two **pre-seeded** accounts (creditor and debtor) — signup is out of scope for this phase.
- **FR-002**: A new contributor MUST be able to complete the edit-request branch (debtor requests edit → creditor approves with new terms → debtor accepts → rest of happy path) using the same demo script.
- **FR-003**: Every state transition surface on the happy path and on the edit-request branch MUST refresh the relevant page automatically; the user MUST NOT be required to manually reload to see the new state.
- **FR-004**: Every action button that triggers a state transition MUST present an immediate loading indicator (spinner, disabled state, or label change) until the response arrives.
- **FR-005**: Every error message that surfaces in the UI on the happy path or the edit-request branch MUST be a translated, human-readable string in the active locale (Arabic or English) — no raw HTTP status codes or backend stack traces.
- **FR-006**: Every page reachable on the happy path (debts, dashboard, notifications, QR) MUST render a translated empty-state when there is no data to show, instead of rendering blank.
- **FR-007**: A backend integration test MUST exist that walks the full happy path against the in-memory repository, asserting (a) the exact status-transition sequence, (b) at least one notification is created per transition, and (c) the final commitment-indicator delta matches `docs/debt-lifecycle.md`.
- **FR-008**: A second backend integration test MUST cover the edit-request branch, asserting the additional `edit_requested` status and that the final terms reflect the creditor-approved values.
- **FR-009**: A markdown demo script MUST exist at `docs/demo-script.md` containing 8–12 numbered steps that, executed top-to-bottom, complete both the happy path and the edit-request branch.
- **FR-010**: Untranslated strings discovered during the polish sweep MUST be collected in the PR description (or a follow-up issue), not fixed individually in this phase.
- **FR-011**: Each happy-path transition MUST complete in under 800 ms perceived latency on local Supabase, measured from button-click to UI reflecting the new state.

### Key Entities

- **Demo Script** (new artifact, `docs/demo-script.md`): A 8–12 step markdown checklist covering both the happy path and the edit-request branch. Lives outside the running app and outside any spec-kit feature directory.
- **Happy-path Integration Test** (new test): Pytest function in `backend/tests/` that exercises the entire canonical lifecycle against the in-memory repository.
- **Edit-request Integration Test** (new test): Pytest function in `backend/tests/` that exercises the edit-request branch + happy path completion.
- **Polish-pass changes** (modifications to existing pages): Touches `DebtsPage.tsx`, `DashboardPage.tsx`, `NotificationsPage.tsx`, `QRPage.tsx` to address loading states, empty states, error-message translation, and post-transition refresh. No new persisted entities.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Three different contributors, each unfamiliar with the codebase, complete the demo script (happy path + edit-request branch) on local Supabase in under 5 minutes median, without asking for help.
- **SC-002**: 100% of state transitions on the happy path and the edit-request branch are visible in the UI within 800 ms perceived latency from the user's click.
- **SC-003**: 0 raw API error messages reach the UI on the happy path or the edit-request branch — every visible error is a translated string in the active locale.
- **SC-004**: 100% of pages reachable on the happy path render a translated empty-state when there is no data; manual inspection across the four pages (debts, dashboard, notifications, QR) finds zero blank panels.
- **SC-005**: The canonical happy-path integration test and the edit-request branch test both pass; the test suite executes both in under 5 seconds combined.
- **SC-006**: The demo script document is between 8 and 12 numbered steps and fits on one printed page (≤ 1 A4 page when rendered as markdown).
- **SC-007**: Untranslated strings discovered during the sweep are captured (count + locations) in the PR description for handoff to Phase 5.

## Assumptions

- The local Supabase stack (`supabase start`) and the contributor's `.env` files are already set up per `docs/local-development.md`. This phase does not change setup steps.
- Two demo accounts (one creditor, one debtor) are pre-seeded before the demo begins — either via the existing `SEED_DEMO_DATA=true` flag on the in-memory repository, by an equivalent seed mechanism on the Postgres-backed local Supabase stack, or by a documented one-time setup step in `docs/local-development.md`. The demo script's first user-facing step is "sign in as the creditor"; signup is **not** part of the demo or the integration test in this phase.
- The eight-state debt lifecycle in `docs/debt-lifecycle.md` is authoritative; transitions outside the happy path and the one in-scope branch are not exercised by this phase.
- Phases 1 (receipt upload), 2 (QR pass-through), and 3 (cancel UX) are merged into `develop` before this phase ships. The demo script reuses receipt and QR flows as part of the happy path; if those phases land late, this phase's PR can rebase but must not duplicate their work.
- The commitment-indicator math (`+3` early, `+1` on-time, etc.) is already implemented and tested in earlier phases; this phase asserts the visible delta but does not modify the rules.
- "Local Supabase" means the Docker stack started by `supabase start`; performance budgets do not apply to a remote staging environment.
- Untranslated strings found during the sweep are tracked by file path and key name only; the actual translation work happens in Phase 5 (bilingual coverage audit).
- The in-memory repository (`REPOSITORY_TYPE=memory`) is sufficient for the integration tests; no Postgres-specific behavior is being asserted.
- Two-locale rendering (Arabic and English) is verified by spot-checks during the sweep but is not exhaustively audited here — that is Phase 5's job.
