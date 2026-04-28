# Feature Specification: Cancel Non-Binding Debt UX

**Feature Branch**: `002-cancel-non-binding-debt-ux`
**Created**: 2026-04-28
**Status**: Draft
**Input**: User description: "Cancel non-binding debt UX — Phase 3 of the Thabetha implementation plan. Add a clear 'Cancel debt' affordance on the creditor's debt details page, restricted to debts that are still non-binding (`pending_confirmation` or `edit_requested`). Two-tap confirmation with an optional message that flows into the existing `debt_cancelled` notification."

## Clarifications

### Session 2026-04-28

- Q: After the creditor confirms cancellation, where does the UI take them? → A: Stay on the debt details page; it now shows `cancelled` status, no cancel button, success toast briefly visible.
- Q: How is the optional-message field presented when the dialog opens? → A: Always visible. Empty textarea with placeholder is rendered alongside confirm/dismiss buttons whenever the dialog opens.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Creditor cancels a debt awaiting debtor confirmation (Priority: P1)

A creditor created a debt by mistake (wrong amount, wrong debtor, customer changed their mind before accepting) while the debtor has not yet confirmed. The creditor opens the debt details page and cancels it in two taps. The debtor is notified that the request was withdrawn and never has to act on it.

**Why this priority**: This is the primary recovery path for the most common creditor error. Without it, mistaken debts linger as `pending_confirmation` forever or force the debtor to manually request edits. It is the smallest-surface unblocker that closes UC3 on the creditor side.

**Independent Test**: Sign in as a creditor, create a debt for a debtor, observe the debt is in `pending_confirmation`, navigate to its details page, click "Cancel debt", confirm in the dialog, and verify (a) the debt status is `cancelled`, (b) the debtor's notifications list contains a `debt_cancelled` entry, (c) the cancel button is no longer visible.

**Acceptance Scenarios**:

1. **Given** a debt in `pending_confirmation` viewed by its creditor, **When** the creditor clicks "Cancel debt" and confirms in the dialog, **Then** the debt transitions to `cancelled` and the debtor receives a `debt_cancelled` notification.
2. **Given** a debt in `edit_requested` viewed by its creditor, **When** the creditor clicks "Cancel debt" and confirms, **Then** the debt transitions to `cancelled` and the debtor is notified.
3. **Given** the cancel confirmation dialog is open, **When** the creditor dismisses without confirming, **Then** no state change occurs and the debt remains in its prior status.

---

### User Story 2 - Creditor attaches an optional reason to the cancellation (Priority: P2)

A creditor cancelling a debt wants to tell the debtor why ("wrong amount, will re-issue", "paid in cash already, sorry"). The creditor types a short note in the cancellation dialog; the debtor sees the note attached to the cancellation notification.

**Why this priority**: Important for debtor-side context but not required for the cancellation itself to function. Empty-message cancellations must still work.

**Independent Test**: Cancel a debt with a 1–200 character message, then sign in as the debtor and verify the message text appears in the body of the `debt_cancelled` notification.

**Acceptance Scenarios**:

1. **Given** a creditor opens the cancel dialog for a `pending_confirmation` debt, **When** they enter a 50-character message and confirm, **Then** the resulting `debt_cancelled` notification body includes that message verbatim.
2. **Given** a creditor opens the cancel dialog, **When** they leave the message empty and confirm, **Then** the cancellation succeeds and the notification body uses the default `debt_cancelled` copy without an empty-message section.
3. **Given** the cancel dialog is open, **When** the creditor types more than 200 characters, **Then** the input is capped at 200 characters and the confirm button remains enabled.

---

### User Story 3 - Cancellation is hidden for non-cancellable states (Priority: P1)

The "Cancel debt" affordance must not appear for debts whose state does not allow cancellation. A creditor viewing an `active`, `payment_pending_confirmation`, `paid`, `cancelled`, `awaiting_creditor_response`, or other non-`pending_confirmation`/`edit_requested` debt must not see the button at all.

**Why this priority**: Hiding (not just disabling) the affordance is a correctness requirement: the system must not invite a transition the backend will reject with 409. P1 because it is part of the same UI change as US1 and protects against confusing user experience.

**Independent Test**: For each debt status the user can view, render the creditor's debt details page and assert the "Cancel debt" button is absent except for `pending_confirmation` and `edit_requested`.

**Acceptance Scenarios**:

1. **Given** an `active` debt viewed by its creditor, **When** the page renders, **Then** the "Cancel debt" button is not present.
2. **Given** a `paid` debt viewed by its creditor, **When** the page renders, **Then** the "Cancel debt" button is not present.
3. **Given** a debtor (not the creditor) views a `pending_confirmation` debt, **When** the page renders, **Then** the "Cancel debt" button is not present (debtor cannot cancel).

---

### Edge Cases

- **Concurrent state change**: The debtor accepts (or requests an edit on) the debt in the moment between the creditor opening the cancel dialog and confirming. The cancellation request hits a state the backend no longer permits. The UI surfaces a translated error ("This debt can no longer be cancelled — its status changed") and refreshes the debt details view.
- **Network failure mid-cancel**: The confirm tap dispatches the cancel request and the network drops. The dialog stays open, shows a translated retry-able error, and the debt status is unchanged. The user can retry or dismiss.
- **Optional message length**: Input is hard-capped at 200 characters at the input level. There is no separate "too long" error because the input cannot exceed the cap.
- **Already-cancelled debt opened from a stale link**: The cancel button is hidden because the status check excludes `cancelled`.
- **Localization**: Both the dialog copy and the notification body must render correctly in Arabic (RTL) and English.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The creditor's debt details page MUST display a "Cancel debt" affordance when, and only when, the viewer is the creditor of the debt **and** the debt status is `pending_confirmation` or `edit_requested`.
- **FR-002**: Activating the "Cancel debt" affordance MUST open a confirmation dialog before any state change is attempted (no single-tap cancellation).
- **FR-003**: The confirmation dialog MUST render an always-visible optional message textarea (free text, hard-capped at 200 characters, with a translated placeholder indicating it is optional) alongside explicit confirm and dismiss controls. The textarea MUST be rendered empty on every open of the dialog and MUST NOT be hidden behind a toggle or secondary screen.
- **FR-004**: On confirm, the system MUST transition the debt to `cancelled` via the existing cancel transition, recording the actor and the optional message in the audit trail.
- **FR-005**: On confirm, the system MUST emit exactly one `debt_cancelled` notification to the debtor, including the optional message in the notification body when present.
- **FR-006**: Dismissing the dialog MUST leave the debt in its prior status with no notification fired.
- **FR-007**: If the cancel attempt is rejected because the debt is no longer in a cancellable state (e.g., the debtor accepted concurrently), the UI MUST surface a translated, recoverable error and refresh the debt view to reflect the actual current status.
- **FR-008**: All visible strings introduced by this feature (button label, dialog title and body, message field placeholder, success toast, error messages) MUST be available in Arabic and English.
- **FR-009**: The "Cancel debt" affordance MUST NOT be rendered for any user other than the creditor of the debt, regardless of the debt's status.
- **FR-010**: Successful cancellation MUST display a translated success indicator (toast or inline confirmation) and remove the cancel affordance from the page.
- **FR-011**: After successful cancellation, the user MUST remain on the debt details page; the page MUST refresh to show `cancelled` status and MUST NOT navigate away automatically.

### Key Entities

- **Debt**: The bilateral debt record. Relevant attributes: `status` (one of the 8 lifecycle states), `creditor_id`, `debtor_id`. Cancellation transitions `status` from `pending_confirmation` or `edit_requested` to `cancelled`.
- **Debt Event**: Append-only audit row created on cancellation, tagged `cancelled`, linking the actor (creditor) and the optional message.
- **Notification**: A `debt_cancelled` row addressed to the debtor, with a body that includes the optional message when present.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A creditor can cancel a non-binding debt in two taps from the debt details page (open dialog → confirm), with no other navigation steps required.
- **SC-002**: For 100% of debt statuses that disallow cancellation, the cancel affordance is not rendered (verified by a per-status UI assertion across all 8 lifecycle states).
- **SC-003**: After successful cancellation, the debtor sees a `debt_cancelled` notification within 5 seconds of the creditor's confirmation under nominal local-Supabase conditions.
- **SC-004**: A backend-rejected cancel attempt (concurrent state change) results in a translated, user-facing error in 100% of cases — never a raw API message.
- **SC-005**: Both Arabic and English locales render every introduced string correctly (no `missing.key.x` artifacts) and respect the active text direction in dialog and notification surfaces.

## Assumptions

- The backend `POST /debts/{id}/cancel` endpoint, the `cancelled` debt-event type, and the `debt_cancelled` notification type already exist and behave as documented in `docs/debt-lifecycle.md`. This phase is purely a UI surfacing exercise; no schema or transition changes are introduced.
- The debt details route already exposes the current viewer's role (creditor vs. debtor) and the debt's status to the frontend; no new fields are needed on the read API.
- The existing in-app notification surface is sufficient for delivery; this phase does not depend on the WhatsApp integration (Phase 6).
- Optional message length cap of 200 characters matches the existing `ActionMessageIn.message` server-side contract used by other debt actions.
- The audit-trail entry for cancellation is already written by the backend on successful transition; the UI does not need to write events directly.
- "Two taps" is measured from the debt details page (the page itself is reachable from any normal navigation path; reaching it is not counted).
