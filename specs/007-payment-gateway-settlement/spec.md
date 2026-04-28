# Feature Specification: Payment-Gateway Settlement

**Feature Branch**: `007-payment-gateway-settlement`
**Created**: 2026-04-28
**Status**: Draft
**Input**: User description: "Phase 7 — Payment-gateway settlement from the implementation plan"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Debtor Pays Debt Online (Priority: P1)

A debtor with an active or overdue debt opens the debt details page and sees a "Pay online" button alongside the existing "Mark as paid" button. They tap it, review the amount and fee breakdown, and are redirected to the payment gateway's hosted page. After entering card details on the gateway page, they are redirected back and see the debt status update to "paid" automatically — no creditor action required.

**Why this priority**: This is the core value proposition of the feature — removing the friction of manual confirmation for debtors who want to pay immediately.

**Independent Test**: Can be fully tested end-to-end in sandbox mode by a debtor acting on an `active` debt; delivers "online payment clears a debt without creditor action."

**Acceptance Scenarios**:

1. **Given** a debt in `active` state, **When** the debtor clicks "Pay online" and completes payment on the gateway page, **Then** the debt status transitions to `paid` and the debtor sees a confirmation screen.
2. **Given** a debt in `overdue` state, **When** the debtor initiates online payment, **Then** the same flow completes and the debt transitions to `paid`.
3. **Given** a debt in `paid` or `pending_confirmation` state, **When** the debtor visits the debt details page, **Then** the "Pay online" button is not shown.

---

### User Story 2 - Fee Transparency for Creditor (Priority: P2)

Before payment is initiated, the creditor's "you'll receive" amount (net of gateway fee) is displayed on the debtor's payment initiation screen. The creditor does not have to do anything — the disclosure is automatic.

**Why this priority**: Creditors agreed to a receivable amount; they must know what they actually receive net of fees before the transaction is locked in.

**Independent Test**: Can be tested by inspecting the payment initiation UI in sandbox mode and verifying the displayed net amount matches `debt.amount − gateway_fee`.

**Acceptance Scenarios**:

1. **Given** a debt of 100 SAR with a 2% gateway fee, **When** the debtor opens the online payment screen, **Then** the screen shows "Creditor receives: 98.00 SAR" prominently.
2. **Given** the fee rate changes in configuration, **When** the debtor opens the payment screen, **Then** the displayed net amount reflects the updated rate.

---

### User Story 3 - Webhook Auto-Confirms Payment (Priority: P1)

After the gateway processes a successful charge, it sends a webhook to Thabetha. The system verifies the webhook's authenticity, finds the matching payment intent, transitions the debt to `paid`, writes the audit event, and updates the commitment score — all without any manual step.

**Why this priority**: The automation is what makes online payment valuable; without reliable webhook processing, the "Pay online" button has no effect.

**Independent Test**: Can be tested independently by sending a mock signed webhook payload in sandbox mode and asserting the debt transitions to `paid` with correct audit and commitment-score rows.

**Acceptance Scenarios**:

1. **Given** a pending payment intent, **When** a valid signed webhook arrives with `status=succeeded`, **Then** the debt transitions to `paid`, a `debt_events` row is written, and the commitment score updates identically to the manual-confirm path.
2. **Given** the same webhook is delivered twice (replay), **When** the second delivery arrives, **Then** the debt remains `paid` with no duplicate events (idempotent).
3. **Given** a webhook with an invalid signature, **When** it arrives, **Then** the request is rejected with a 400 error and no state changes occur.

---

### User Story 4 - Manual Creditor Confirmation Still Works (Priority: P2)

For cash payments, the creditor's existing "Confirm payment" path is unchanged. The commitment-score event and audit trail produced by a manual confirmation are identical to those produced by the gateway webhook path.

**Why this priority**: Backward compatibility — the majority of existing payments are cash; the gateway path must not break or degrade the manual path.

**Independent Test**: Can be tested in isolation by using the existing `POST /debts/{id}/confirm-payment` flow and verifying the audit/score output matches the webhook path's output.

**Acceptance Scenarios**:

1. **Given** a debt in `payment_pending_confirmation`, **When** the creditor confirms manually, **Then** the debt transitions to `paid` with the same `debt_events` schema and the same commitment-score delta as a gateway-triggered transition.
2. **Given** a debt that was paid via gateway (status already `paid`), **When** the creditor tries to manually confirm again, **Then** the action is rejected with an appropriate error.

---

### Edge Cases

- What happens when the gateway succeeds but the webhook is delayed by minutes or hours? — Idempotency on the provider reference key ensures a late webhook is processed correctly regardless of timing.
- What if the payment is initiated but the debtor abandons the gateway page? — The payment intent remains in `pending` state; the debt stays `active`/`overdue` until a webhook signals success or the intent auto-expires after 30 minutes.
- What if the debtor taps "Pay online" again while a `pending` intent already exists for that debt? — The system blocks the new attempt and prompts the debtor to wait or try again after the existing intent expires (30-minute window).
- What if the debtor tries to pay a debt that is already `paid`? — The "Pay online" button is hidden for non-payable states; the backend endpoint rejects the request with a 409 if called directly.
- What if the post-payment redirect page polls for 60 seconds without a `paid` status appearing? — It times out gracefully, shows a "payment processing" message, and redirects to the dashboard — the debt will update when the webhook eventually arrives.
- What if the gateway sandbox environment is unavailable? — Errors surface to the debtor as a user-friendly message; the debt remains unchanged.
- What if the gateway declines the card (payment intent transitions to `failed`)? — The debtor may retry immediately; each attempt creates a new payment intent. Failed intents are retained immutably for audit purposes and do not block new attempts.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Only the debtor of a debt MAY initiate an online payment; the creditor has no ability to trigger a gateway charge. Debtors MUST be able to initiate online payment for debts in `active` or `overdue` state only; all other states must not expose the payment option.
- **FR-002**: Before confirming an online payment, the debtor MUST see the total debt amount AND the net amount the creditor will receive after gateway fees.
- **FR-003**: The system MUST automatically transition a debt to `paid` upon receiving a valid, authenticated webhook from the payment gateway indicating a successful charge.
- **FR-004**: The system MUST verify the cryptographic signature of every incoming payment webhook before taking any action; unsigned or incorrectly signed webhooks MUST be rejected.
- **FR-005**: Duplicate webhook deliveries carrying the same provider reference MUST be handled idempotently — only one state transition and one audit event may result.
- **FR-006**: The system MUST record every payment attempt as a payment intent, capturing: debt reference, provider, provider transaction reference, status, gross amount, fee amount, and timestamps.
- **FR-012**: Only one `pending` payment intent may exist per debt at a time. A new online payment attempt MUST be blocked if a `pending` intent already exists; the debtor MUST be informed and the block MUST auto-release when the existing intent expires after 30 minutes.
- **FR-013**: If a payment intent reaches `failed` status (e.g., card declined), the debtor MUST be able to retry immediately. Each retry creates a new payment intent. Failed intents MUST be retained immutably for audit and do not block new attempts.
- **FR-014**: Payment lifecycle events (`payment_initiated`, `payment_failed`, `payment_expired`) MUST be written to `debt_events` so the full debt history is visible in one audit trail. The `payment_intents` table remains the authoritative source for gateway-specific detail (provider reference, fee, raw status).
- **FR-007**: The creditor's manual cash-payment confirmation path MUST continue to work unchanged, producing audit-trail and commitment-score outputs identical to the gateway-triggered path.
- **FR-008**: A post-payment return page MUST poll debt status for up to 60 seconds; if `paid` is not reached, it MUST display a "payment processing" message and redirect to the dashboard without error.
- **FR-009**: Both the manual confirmation and gateway paths MUST produce a commitment-score delta using the same logic: `+3` if paid before `due_date`, `+1` if on `due_date`, `−2 × 2^N` if overdue.
- **FR-010**: The payment provider environment (sandbox vs. production) MUST be configurable via a toggle without code changes.
- **FR-011**: Both Arabic and English locales MUST be supported for all new UI strings (fee breakdown, button labels, status messages, error messages).

### Key Entities

- **Payment Intent**: Represents one charge attempt. Attributes: unique identifier, associated debt, payment provider name, provider-assigned transaction reference, status (pending / succeeded / failed / expired), gross amount, fee amount, creation timestamp, expiry timestamp (30 minutes after creation), completion timestamp. At most one `pending` intent may exist per debt at any time.
- **Debt** (existing): Gains the ability to be transitioned to `paid` by the gateway webhook path in addition to the existing manual path.
- **Commitment Score Event** (existing): Written identically whether payment was confirmed manually or by the gateway.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A debtor can complete an online payment — from tapping "Pay online" to seeing the "paid" confirmation — in under 3 minutes in the sandbox environment.
- **SC-002**: Replayed webhook payloads (same provider reference delivered twice) produce zero duplicate debt transitions and zero duplicate audit events, verified by automated test.
- **SC-003**: An automated equivalence test confirms that the manual confirmation path and the gateway webhook path produce identical `debt_events` schema and identical commitment-score deltas for the same timing scenarios.
- **SC-004**: The fee breakdown shown to the debtor on the payment initiation screen matches the actual fee deducted, with no discrepancy, across all tested amounts.
- **SC-005**: All new UI strings render correctly in both Arabic (RTL) and English (LTR) with no missing translation keys.

## Clarifications

### Session 2026-04-28

- Q: What happens if a debtor initiates a second online payment while a previous intent for the same debt is still `pending`? → A: Block new intent while one is `pending`; auto-expire pending intents after 30 minutes.
- Q: If a payment attempt fails (card declined), can the debtor retry and what happens to the failed intent? → A: Allow immediate retry; each attempt creates a new intent; failed intents are retained immutably for audit.
- Q: Can the creditor also initiate a gateway charge, or is online payment debtor-only? → A: Debtor-only; creditor has no ability to initiate a gateway charge.
- Q: Should payment intent state changes be recorded in `debt_events` or only in `payment_intents`? → A: Write payment lifecycle events (`payment_initiated`, `payment_failed`, `payment_expired`) to `debt_events`; `payment_intents` holds gateway-specific detail.
- Q: Does this phase need to comply with SAMA payment regulations and VAT receipt issuance? → A: Out of scope for this phase; explicitly deferred to a compliance hardening phase before production launch.

## Assumptions

- **Payment provider**: Tap is the default choice for this phase (better SAR card support, simpler webhook model). HyperPay is the backup if Tap integration stalls.
- **Fee bearer**: Gateway fees are borne by the creditor and deducted from the receivable. The configuration will make this adjustable post-MVP.
- **No card tokenization**: One-shot charges only. Saved cards / recurring billing are out of scope.
- **Refunds out of scope**: Manual reversal via existing audit trail is the only recovery path. A dedicated refund flow is post-MVP.
- **Currency**: SAR only. Multi-currency payment is not addressed in this phase.
- **Gateway webhooks**: Inbound delivery receipts update the payment intent and trigger the debt transition. Inbound chat/reply messages from the gateway are not expected and out of scope.
- **Failure isolation**: A gateway send failure or webhook processing error must not affect the underlying debt state; the debt stays in its current state until a successful webhook arrives.
- **Sandbox parity**: The sandbox and production environments behave identically from the application's perspective; only credentials differ.
- **Regulatory compliance deferred**: SAMA payment regulation compliance and VAT receipt issuance are explicitly out of scope for this phase. These must be addressed in a dedicated compliance hardening phase before production launch.
