# Phase 0 Research — QR-scanner pass-through to Create Debt

All NEEDS-CLARIFICATION items in the spec were resolved during `/speckit.clarify`. The remaining decisions are small implementation choices that don't affect spec wording but pin behavior so `tasks.md` and the implementer don't have to re-decide.

## R1 — Confirm-step surface on the scanner

**Decision**: In-page overlay/sheet on `QRPage.tsx`. The scanner stays mounted underneath; "Cancel" closes the sheet and the camera continues running for a re-scan with no remount cost.

**Rationale**: A dedicated route for the confirm step would add a back-stack entry, making the back button bounce between scanner and confirm — a known mobile-UX wart. An overlay also lets us keep the camera frame visible behind the preview, which is a reassuring "you scanned the right person" cue.

**Alternatives considered**:
- Dedicated route `/qr/confirm/:token` — rejected for the back-stack reason and because it duplicates layout chrome.
- Inline expansion below the scanner (no overlay) — rejected because the preview can be tall on small screens and pushes the camera out of view.

## R2 — Loading state while resolving on mount

**Decision**: Render a skeleton header (gray block where the preview will go) and keep the debt-fields portion of the form *visible but disabled* until the resolve completes or fails.

**Rationale**: A full-screen spinner would feel slower than the work being done (resolve is a single sub-second `GET`). A skeleton header is a familiar pattern and matches what the dashboard already does for debt cards.

**Alternatives considered**:
- Full-screen spinner — rejected; it hides the form, making the page feel heavier.
- Render nothing until resolved — rejected; flicker on slow networks and no visible "we're working on it" feedback.

## R3 — Submit-time re-resolve failure

**Decision**: Keep the form mounted; on a submit-time resolve failure, swap the preview header for an error banner with two actions — "Rescan" (back to `/qr`) and "Switch to manual entry" (clears the QR state and unlocks debtor fields, preserving everything else). Never unmount the form.

**Rationale**: Spec SC-004 explicitly requires that the user's already-entered fields survive an expired-token error. The simplest way to guarantee that is to never destroy the form's local state when the token goes bad — only the preview header changes.

**Alternatives considered**:
- Show a modal blocking the form — rejected; modals can dismiss-and-resubmit, and we'd risk re-firing the same expired-token call.
- Auto-fall-back to manual entry silently — rejected; loses the audit guarantee that QR-originated debts carry a `debtor_id`. The user must explicitly choose to abandon the QR identity.

## R4 — Self-scan detection

**Decision**: Compare the resolved profile's `id` against the current user's `id` from `useAuth()`. If equal: replace the preview with the translated `cannot_bill_self` message and suppress the form's submit affordance entirely (don't merely disable it — hide it, so the user understands the path is blocked rather than failing).

**Rationale**: A disabled submit button is ambiguous ("did I miss a required field?"). Hiding it plus a clear message removes the guesswork. The "clear / change debtor" link remains visible so the user can recover by switching to manual entry or rescanning.

**Alternatives considered**:
- Backend-side block on `POST /debts` when `debtor_id == creditor_id` — rejected for this phase because it adds backend scope; the implementation plan explicitly notes "no backend changes". A backend guard is reasonable as a defense-in-depth follow-up but is not required here.

## R5 — Clear-debtor URL semantics

**Decision**: When "clear / change debtor" is tapped, use `history.replaceState` (or React Router's `navigate(..., { replace: true })`) to remove the `qr_token` query param without adding a history entry.

**Rationale**: If we `push`, then the back button takes the user back to the prefilled-and-locked state, which is confusing — they just chose to clear it. `replace` makes the action feel like a state reset, not a navigation.

**Alternatives considered**:
- Keep the token in the URL but mark the local state as "manual" — rejected; refresh would re-prefill and undo the user's choice.

## Cross-cutting notes

- **No new dependencies.** The scanner already uses whatever camera library is in `QRPage.tsx`; the confirm overlay is plain JSX + existing layout components.
- **i18n keys to add** (AR + EN): `qr_expired_ask_refresh`, `cannot_bill_self`, `clear_debtor`, `scanned_debtor_label`. Plus reuse existing keys for "Cancel" and a new `create_debt_for_person` if not already present (verify before adding).
- **Test surface**: one new backend integration test (`test_create_debt_with_debtor_id.py`) — exercises `GET /qr/resolve/{token}` then `POST /debts` with `debtor_id` and asserts the resulting debt is queryable from the debtor side. Frontend gets a manual E2E in the PR; no Vitest harness is added in this phase.
