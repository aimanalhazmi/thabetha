# Phase 0 — Research: Cancel Non-Binding Debt UX

**Date**: 2026-04-28
**Feature**: 002-cancel-non-binding-debt-ux

The spec has no `[NEEDS CLARIFICATION]` markers after `/speckit-clarify`. This document captures the small set of implementation-direction decisions that, while not strictly clarifications, set the design contract for Phase 1.

## R1 — Modal vs. inline confirmation pattern

- **Decision**: Use a fixed-positioned modal dialog (overlay + centered card), not an inline expanding section under the cancel button.
- **Rationale**: A modal forces a deliberate second tap (US1, FR-002) and visually disables the rest of the debt details page while it is open. Inline confirmation on a long, scrollable debts list risks the user mis-tapping when the cancel button shifts position.
- **Alternatives considered**: (a) Native `window.confirm()` — rejected because it can't host a textarea, can't be styled, and won't render Arabic correctly without locale tricks. (b) Inline expanding section — rejected as above.

## R2 — How the backend currently models cancellation

- **Decision**: Continue calling `POST /debts/{id}/cancel` with `ActionMessageIn { message: string }`. No backend changes.
- **Findings (verified)**:
  - `backend/app/api/debts.py::cancel_debt` (line 122) accepts `ActionMessageIn` and delegates to `repo.cancel_debt(user.id, debt_id, payload.message)`.
  - The repository method enforces source-state validation; disallowed transitions return `409 Conflict`.
  - `debt_events` audit row is written by the repository on success.
  - `notifications` row of type `debt_cancelled` is fired by the same code path, with the message in the body.
- **Implication**: The frontend simply needs to (a) gate the affordance, (b) send the textarea contents (or `""` if empty), and (c) translate the success/failure outcomes.

## R3 — Empty-message wire format

- **Decision**: Send `{ "message": "" }` for empty cancellations (do not omit the field).
- **Rationale**: `ActionMessageIn.message` is a required string in the existing schema. Sending `""` is what the current single-tap implementation already does (with hardcoded `"Cancelled"`); switching to empty string is consistent with how other action endpoints behave when the user provides no note.
- **Alternatives considered**: Sending the literal `"Cancelled"` for empty (preserves bytes-on-the-wire compatibility with the current button) — rejected because it leaks an English word into the audit trail and notification body for Arabic-locale users.

## R4 — Trimming and length enforcement

- **Decision**: Trim leading/trailing whitespace before sending. Hard-cap textarea input at `maxLength={200}` so the cap is enforced at typing time, not at submit time.
- **Rationale**: Matches the constitution's "tests for any new state transition" expectation by removing a class of submit-time edge cases. The 200-char cap matches `ActionMessageIn` server-side conventions used elsewhere in the codebase.
- **Alternatives considered**: Allowing >200 chars and rejecting at submit — rejected because it forces an extra error path and an extra round-trip.

## R5 — Concurrent-state-change handling (409)

- **Decision**: On a 409 response from the cancel call, the dialog stays open, displays a translated inline error ("This debt can no longer be cancelled — its status changed"), and triggers a debt-list refetch (the same `refresh()` already used elsewhere in `DebtsPage.tsx`). The user dismisses the dialog manually; the affordance disappears on the next render because the status check excludes the new state.
- **Rationale**: Prevents data desynchronization (dialog open against a stale state) without forcing an automatic close that swallows the error context.
- **Alternatives considered**: Auto-close on 409 with a toast — rejected because the user loses the message they typed before they can react.

## R6 — Where the cancel button lives in the existing UI

- **Decision**: Replace the existing creditor-side cancel button (line ~683 in `DebtsPage.tsx`) with a dialog trigger. The button position, label, and icon (`X`) stay; only the click handler changes.
- **Rationale**: Preserves the existing visual language of the actions row (mark-paid, confirm-payment, edit). No new entry point; no nav surface change.
- **Alternatives considered**: Moving cancel into a kebab menu — rejected as scope creep for an XS phase.

## R7 — i18n keys to add

- **Decision**: Add the five keys named in the spec's Technical context, exactly:
  - `cancel_debt`
  - `cancel_debt_confirm_title`
  - `cancel_debt_confirm_body`
  - `cancel_message_optional`
  - `cancelled_successfully`
- **Plus**: One additional error key surfaced by R5 — `cancel_debt_state_changed`. Spec is silent on its name; we choose a name consistent with existing snake_case convention in `i18n.ts`.

## R8 — Test coverage rule (constitution §12)

- **Decision**: No new state transition is introduced; constitution §12 does not require a *new* test. However, re-verify the existing positive and disallowed (e.g., `active → cancel = 409`) backend transition tests still pass, and add a test asserting cancellation **with an empty message** still succeeds (closing a small gap if the existing test only covers non-empty messages).
- **Rationale**: Empty-message is a new client behavior even if not a new server transition.

## Open questions

None. All design decisions above are firm. Proceed to Phase 1.
