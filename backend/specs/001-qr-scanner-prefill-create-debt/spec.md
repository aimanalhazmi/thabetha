# Feature Specification: QR-scanner pass-through to Create Debt

**Feature Branch**: `001-qr-scanner-prefill-create-debt`
**Created**: 2026-04-27
**Status**: Draft
**Input**: User description: "Phase 2 — QR-scanner pass-through to Create Debt (per docs/spec-kit/implementation-plan.md)"

## Clarifications

### Session 2026-04-27

- Q: After a successful QR resolve, does the scanner navigate directly to Create Debt, or show an intermediate confirm step first? → A: Show a confirm step on the scanner with the resolved profile preview and explicit "Create debt for this person" / "Cancel" actions before navigating.
- Q: How is QR-token single-use enforced after a debt is created from it? → A: Client-side only — strip the `qr_token` from the URL after a successful debt creation; rely on the existing TTL for residual replay risk. No backend change.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Creditor scans debtor QR and lands in a pre-identified Create Debt form (Priority: P1)

A creditor opens the QR scanner, points it at a debtor's displayed QR code, and is taken directly to the Create Debt form with the debtor's identity already filled in and locked. The creditor only enters the debt-specific details (amount, currency, description, due date, optional reminders, optional receipts) and submits. They never have to type or re-confirm the debtor's name.

**Why this priority**: This is the core promise of the QR feature — identity is established by the scan, not by retyping. Without this pass-through, the QR scan today produces only a profile preview that the creditor must then translate manually into a debt, which is the friction we set out to remove. It is the minimum viable slice for Phase 2.

**Independent Test**: From a logged-in creditor session, scan a valid debtor QR token, observe that the resulting Create Debt screen shows the debtor's name as a locked field with a "scanned debtor" indicator and a commitment indicator badge, fill in the remaining fields, submit, and verify the resulting debt is associated with the correct debtor.

**Acceptance Scenarios**:

1. **Given** a creditor on the QR scanner page and a fresh, valid debtor QR token displayed by another user, **When** the creditor scans the code, **Then** the scanner shows a confirmation step displaying the resolved debtor's profile preview (name, last 4 digits of phone, commitment indicator) with explicit "Create debt for this person" and "Cancel" actions; on confirm, the app navigates to the Create Debt form with the debtor identity prefilled and locked and the preview repeated above the form.
2. **Given** the creditor lands on the prefilled Create Debt form via QR, **When** they fill in amount, currency, and other debt fields and submit, **Then** the system creates the debt linking the prefilled debtor identity (not a free-text name) and routes the debt into the standard `pending_confirmation` state for that debtor.
3. **Given** the creditor wants to abandon the scanned debtor and start over, **When** they tap the "clear / change debtor" link, **Then** the form resets to the manual-entry path with no debtor identity attached and no QR token in the URL.

---

### User Story 2 - QR token errors are handled gracefully without losing the creditor's progress (Priority: P2)

When the QR token is invalid, expired, or self-targeted (the creditor's own QR), the creditor sees a clear, translated message and can either dismiss the error to continue with manual entry or return to the scanner. They are never blocked on a broken screen and never see a raw error code.

**Why this priority**: Tokens have a TTL (default 10 minutes) and can expire between display and scan, especially in a busy market. Self-scanning is a foreseeable mistake. A polished error path is required for the demo and for real-world reliability, but the happy path (Story 1) delivers the value on its own.

**Independent Test**: Visit the prefilled Create Debt route with three different bad inputs — an expired token, an unknown token, and a token that resolves to the current user — and verify each shows the appropriate translated message and offers a path forward.

**Acceptance Scenarios**:

1. **Given** the creditor opens the Create Debt form via a QR deep link whose token has expired, **When** the form attempts to resolve the token, **Then** the user sees a translated "QR expired, ask the customer to refresh their code" message and a control to either rescan or switch to manual entry.
2. **Given** the QR token resolves to the creditor's own profile, **When** the form loads, **Then** submission is blocked and a translated "you can't bill yourself" message is shown.
3. **Given** the token was valid on first load but has expired by the time the creditor submits the form, **When** the form re-resolves on submit, **Then** the same expired-token error path is shown and previously entered debt fields (amount, description, etc.) are preserved so the creditor does not lose their work.

---

### User Story 3 - Manual debtor entry remains available alongside the QR path (Priority: P3)

A creditor who arrives at Create Debt without scanning a QR code can still enter a debtor by name as today. QR is one of two entry points; the manual path is unchanged.

**Why this priority**: Necessary for completeness and to avoid regressing existing flows, but it is not new behavior — it is the default that already exists. Verifying it is preserved is enough.

**Independent Test**: Open Create Debt without a `qr_token` parameter, confirm the form looks and behaves exactly as before, with the debtor name field unlocked and editable.

**Acceptance Scenarios**:

1. **Given** the creditor navigates to Create Debt directly (no QR token), **When** the form renders, **Then** the debtor name field is editable, no profile preview is shown, and submission produces a debt without a `debtor_id` link, matching today's manual flow.

---

### Edge Cases

- The QR token is missing from the URL but the route was reached via the scanner — the form falls back to manual entry rather than erroring.
- The token is valid on mount and resolves correctly, then the user leaves the form open longer than the TTL and submits — the submit-time re-resolution catches the expiration without silently using stale identity.
- The scanner reads a QR that is not a Thabetha token (random URL, vCard, etc.) — the scanner page surfaces a "not a Thabetha QR" message and never navigates.
- The creditor scans the same valid token twice in quick succession — the second resolution either succeeds (still within TTL) or shows the expired-token message; no duplicate or partial debt is created in either case.
- Network failure during the on-mount resolve — the form shows a retry control and any entered fields are preserved.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: On a successful resolution of a debtor QR token, the QR scanner screen MUST first present a confirmation step showing the resolved debtor's profile preview with explicit "Create debt for this person" and "Cancel" actions; only on confirmation MUST it hand control to the Create Debt screen via a deep link that carries the same token, so the Create Debt screen can re-resolve and prefill identity itself. "Cancel" MUST return the creditor to the live scanner without navigating.
- **FR-002**: The Create Debt screen MUST detect the presence of a QR token in its entry parameters on mount and, if present, resolve the token against the existing QR-resolution capability before rendering the form.
- **FR-003**: When a QR token resolves successfully to a debtor profile, the Create Debt screen MUST prefill the debtor identity (debtor's display name and the resolved internal identifier) and MUST present those fields as read-only.
- **FR-004**: The Create Debt screen MUST display, above the form, a debtor profile preview consisting of the debtor's name, the last four digits of their phone number, and their commitment indicator badge. The preview MUST NOT include tax identifiers or email addresses.
- **FR-005**: The Create Debt screen MUST offer a visible "clear / change debtor" control that, when activated, removes the prefilled identity, removes the QR token from the URL, and reverts the form to the manual-entry path.
- **FR-006**: The system MUST re-resolve the QR token at submission time and MUST refuse to create the debt if the token is no longer valid, surfacing a translated "QR expired, ask the customer to refresh their code" message and preserving the user's already-entered debt fields.
- **FR-007**: When a QR token resolves to the same user who is creating the debt, the system MUST block creation in the UI (submit affordance hidden, translated "you can't bill yourself" message shown) **and** the backend MUST reject `POST /debts` with 409 if `debtor_id` equals the authenticated user's id, mirroring the rule in handler code per constitution §IV.
- **FR-008**: When a QR token is malformed, unknown, or otherwise non-resolvable, the Create Debt screen MUST present a translated error and offer a path to either rescan or switch to manual entry, without leaving the user on a broken screen.
- **FR-009**: The Create Debt screen MUST continue to support the manual-entry path unchanged when no QR token is present, including allowing the creditor to enter a debtor by free-text name only.
- **FR-010**: The system MUST add new translated strings for the user-facing copy introduced by this feature — at minimum: QR-expired notice, self-billing block, "clear debtor" affordance, and "scanned debtor" label — in both Arabic and English.
- **FR-011**: When a debt is created via the QR pass-through, the resulting debt MUST be linked to the resolved debtor identity (not stored as free-text name only), so subsequent flows (debtor accept, edit-request, notifications, commitment-indicator updates) operate on the bilateral pair as in the existing lifecycle.
- **FR-012**: After a successful debt creation via the QR pass-through, the system MUST remove the QR token from the Create Debt URL and from any in-memory form state, so navigating back, refreshing, or revisiting the page does not silently produce a second debt against the same scan. Single-use is enforced client-side only; the existing token TTL bounds any residual replay risk and no backend change is introduced for this purpose in this phase.

### Key Entities *(include if feature involves data)*

- **QR token**: A short-lived random identifier displayed by a debtor that resolves to a debtor profile preview. Already exists; this feature only adds a new consumer (the Create Debt screen) and a re-resolution at submit time.
- **Debtor profile preview**: The minimal, non-credential subset of a profile (display name, last-four phone digits, commitment indicator) shown to the scanning creditor. No new fields; the preview is a presentation of existing profile attributes.
- **Debt (creation input)**: The Create Debt form input. Adds a derived "debtor identity source" — either `qr` (with a resolved internal identifier) or `manual` (free-text name only) — affecting which fields are locked and how the submission is structured.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A creditor can complete the scan-to-debt-created flow in two screens (scanner → Create Debt) with zero manual typing of the debtor's identity.
- **SC-002**: 100% of debts created via the QR pass-through carry a resolved debtor identity link (not just a free-text name), as verified by an integration test asserting the resulting debt's debtor association.
- **SC-003**: All four error/edge messages introduced by this feature (expired token, self-billing block, clear-debtor affordance, scanned-debtor label) render in both Arabic and English with no fallback to a missing-key placeholder.
- **SC-004**: An expired token at submission time does not destroy the creditor's already-entered debt fields — verified by a test that loads the form, expires the token, attempts submission, sees the error, and confirms the form still holds the entered amount and description.
- **SC-005**: A self-targeted QR scan results in zero debts created and a translated block message, with no need for the creditor to refresh or restart the app.
- **SC-006**: Time from a successful scan to a fully rendered, prefilled Create Debt form is under 1 second on a healthy local environment, perceived as instantaneous by the creditor.

## Assumptions

- The existing QR resolution capability already returns a debtor profile sufficient for the preview (display name, phone, commitment indicator) and remains the single source of truth for QR validity. No backend changes to that capability are required for this phase.
- The existing Create Debt submission path already supports linking a debt to a resolved debtor identity; this feature only ensures the identity is captured and forwarded, not that a new submission shape is invented.
- The existing canonical 7-state debt lifecycle (per constitution §II — `pending_confirmation`, `active`, `edit_requested`, `overdue`, `payment_pending_confirmation`, `paid`, `cancelled`) is unchanged. A QR-originated debt enters `pending_confirmation` exactly like a manually-entered one.
- Receipts attached at creation (Phase 1) and reminder configuration are orthogonal to this feature and continue to work whether the debtor identity came from QR or manual entry.
- The QR token TTL (default 10 minutes) is the canonical validity window; this feature relies on it rather than introducing a new expiration concept.
- Voice notes, group tagging, and AI-assisted draft creation are out of scope for this phase even if visible on the Create Debt form, since they are independent of how the debtor identity was captured.
- Marketing/landing surfaces are out of scope; the QR pass-through only affects authenticated creditor flows.
