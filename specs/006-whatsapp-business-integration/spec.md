# Feature Specification: Real WhatsApp Business API Integration

**Feature Branch**: `006-whatsapp-business-integration`
**Created**: 2026-04-28
**Status**: Draft
**Input**: User description: "Replace the mock WhatsApp provider with a real WhatsApp Business API integration. Outbound messages on debt-state notifications must respect per-creditor preferences and the global toggle. A debtor's opt-out for a specific creditor must stop outbound WhatsApp messages from that creditor only."

## Clarifications

### Session 2026-04-28

- Q: Who can see the per-message WhatsApp delivery status indicator (attempted / delivered / failed + reason)? → A: The sender (creditor) only, on their own notifications view. The debtor sees only the in-app notification body, with no WhatsApp delivery badge.
- Q: When does the fallback messaging provider engage — runtime auto-failover, or a deployment-time switch? → A: Deployment-time switch only. A single provider is active per deployment; switching is an ops task (config change + redeploy). No runtime auto-failover and no admin runtime toggle.
- Q: How long does an "attempted, status unknown" notification stay in that state if no delivery callback ever arrives? → A: Indefinitely. No background sweeper auto-promotes "unknown" to "delivered" or "failed". The state only changes when a real callback arrives.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Creditor reaches debtor on WhatsApp for real debt-lifecycle events (Priority: P1)

A creditor creates a debt, the debtor accepts it, and later the creditor confirms a payment. At each lifecycle event, the debtor receives a real WhatsApp message (in their preferred language) on the phone number tied to their account, in addition to the in-app notification — provided the debtor has not opted out of WhatsApp from this creditor and has not disabled WhatsApp globally.

**Why this priority**: This is the core value of the phase — moving from mock to real WhatsApp delivery. Without P1, the feature delivers nothing new to users. Every other story is gated on this working.

**Independent Test**: Configure the system against a real (or sandbox) WhatsApp provider, create a debt between two real test accounts in staging, walk a debt through `pending_confirmation → active → paid`, and verify each notification arrives on WhatsApp on the debtor's real handset within seconds. Validates the entire send pipeline end-to-end.

**Acceptance Scenarios**:

1. **Given** a debtor with global WhatsApp enabled and no creditor-specific opt-out, **When** the creditor creates a debt addressed to them, **Then** the debtor receives a WhatsApp message containing the creditor name, amount, currency, and a link to view the debt in-app, in their preferred locale (Arabic or English).
2. **Given** a debt in `pending_confirmation`, **When** the debtor accepts it, **Then** the creditor receives a WhatsApp message confirming acceptance, in the creditor's preferred locale.
3. **Given** a debt in `payment_pending_confirmation`, **When** the creditor confirms the payment, **Then** the debtor receives a WhatsApp message confirming closure, and the in-app notification is also created.
4. **Given** the configured WhatsApp provider returns a transient failure, **When** a notification is fired, **Then** the underlying debt transition still completes successfully and the in-app notification still fires.

---

### User Story 2 - Debtor controls WhatsApp contact per creditor (Priority: P1)

A debtor wants to stay reachable on WhatsApp from one shop they regularly buy from but silence WhatsApp messages from a different lender they no longer want chasing them. They open settings, find the per-creditor list, and toggle WhatsApp off for the second creditor while leaving WhatsApp on for the first. They also retain the option to disable WhatsApp globally for all creditors with a single switch.

**Why this priority**: Without enforced opt-out the integration is non-compliant with messaging policy and risks the WhatsApp business account being suspended. This is non-negotiable for production.

**Independent Test**: With two creditors A and B both messaging the same debtor, set the debtor's per-creditor preference for creditor A to opt-out, then trigger one notification from each creditor. Verify creditor B's WhatsApp arrives, creditor A's WhatsApp is suppressed, and in both cases the in-app notification still appears.

**Acceptance Scenarios**:

1. **Given** a debtor has globally enabled WhatsApp and explicitly opted out of WhatsApp from creditor A only, **When** creditor A triggers a notification, **Then** no WhatsApp message is sent to the debtor; the in-app notification is still created.
2. **Given** the same debtor as above, **When** creditor B triggers a notification, **Then** the debtor receives a WhatsApp message from creditor B.
3. **Given** a debtor has globally disabled WhatsApp, **When** any creditor triggers a notification, **Then** no WhatsApp messages are sent regardless of per-creditor preferences; in-app notifications still fire.
4. **Given** a debtor has no preference recorded for a given creditor, **When** that creditor triggers a notification, **Then** the global preference is the source of truth (default opt-in unless globally disabled).

---

### User Story 3 - Operators see whether each WhatsApp message was delivered (Priority: P2)

When a creditor or support user is reviewing a debt's history, they need to know which notifications actually reached the recipient on WhatsApp versus those that were attempted but failed (and why). The system records, per notification: whether WhatsApp was attempted, whether it was delivered, and a reason code if it failed.

**Why this priority**: Visibility into delivery enables debugging the integration and gives operators a way to explain to a confused user "yes the system tried, but the message did not reach you because your number is invalid." Lower than P1 because the system can technically operate without it; the integration just becomes a black box.

**Independent Test**: Send a notification to a known-bad phone number, then sign in as the sending creditor and verify their notifications view shows a "delivery failed" indicator with a translated reason for that notification, and that the audit record contains a non-empty failure reason. Sign in as the debtor and verify they see the in-app notification body but no delivery badge. Then send to a good number and verify the creditor's "delivered" indicator updates after the provider's delivery receipt arrives.

**Acceptance Scenarios**:

1. **Given** a notification has been queued for WhatsApp delivery, **When** the provider acknowledges the message was delivered to the recipient's device, **Then** the notification record reflects "delivered" within a reasonable window (under 1 minute typical).
2. **Given** the provider rejects the message (invalid number, template not approved, recipient blocked), **When** the rejection is received, **Then** the notification record reflects "failed" with a human-readable reason code surfaced in the sending creditor's notifications view.
3. **Given** the provider never returns a delivery receipt, **When** the sending creditor views the notification, **Then** the notification displays an "attempted, status unknown" state rather than falsely claiming delivery.

---

### Edge Cases

- **Debtor's WhatsApp number is invalid or not registered on WhatsApp**: outbound send fails; the failure is recorded with a clear reason; in-app notification still works; subsequent notifications for the same debt continue to attempt (no automatic blocklisting in this phase).
- **Provider is temporarily unreachable**: the underlying business action (debt transition, payment confirmation) must not fail. The notification is recorded as attempted-and-failed with a transient error; no automatic retry queue is required for MVP.
- **Recipient's preferred locale has no approved template variant yet**: fall back to the other supported locale rather than failing silently.
- **Webhook from provider arrives for a notification record that has been deleted (e.g., test data wiped)**: webhook processing is idempotent and a no-op for unknown references.
- **Webhook arrives with an invalid signature**: the request is rejected and an audit log entry is recorded.
- **A notification is fired during the brief window when the recipient toggles WhatsApp off**: the system reads the preference at send time, not at queue time; if the user has just toggled off, no message is sent.
- **Same delivery receipt arrives twice from the provider** (duplicate webhook): the notification record is updated idempotently — no double-counting.
- **Recipient does not have a phone number on file at all**: WhatsApp send is skipped with a "no phone number" reason; in-app still fires.
- **The creditor account that triggered a notification is later deleted**: existing notification records preserve the historical creditor reference for opt-out enforcement; new sends from that creditor cannot occur.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST send a real WhatsApp message for each notification type that currently triggers a mock WhatsApp message, replacing the mock when configured to do so.
- **FR-002**: The system MUST consult the recipient's global WhatsApp preference and the recipient's per-creditor WhatsApp preference before sending; if either resolves to "off" for the (recipient, creditor) pair, the system MUST NOT send a WhatsApp message.
- **FR-003**: A debtor's opt-out from a specific creditor MUST suppress WhatsApp messages from that creditor only; messages from other creditors to the same debtor MUST continue to be sent (subject to other preferences).
- **FR-004**: An in-app notification record MUST be created for every triggering event regardless of whether the WhatsApp send was attempted, succeeded, or failed.
- **FR-005**: A WhatsApp send failure MUST NOT cause the underlying debt transition (or other business action that triggered the notification) to fail or roll back.
- **FR-006**: The system MUST record, per notification: whether WhatsApp delivery was attempted, whether it was delivered, and a reason code or message when it was not delivered. This delivery status MUST be visible only to the sending creditor on their own notifications view; debtors MUST NOT see a WhatsApp delivery indicator on the in-app notifications they receive.
- **FR-007**: The system MUST send messages using pre-approved message templates appropriate to each notification type, in the recipient's preferred language (Arabic or English), with the other language as a fallback if the preferred locale's template is unavailable.
- **FR-008**: The system MUST accept inbound delivery-status callbacks from the provider, verify their authenticity, and update the corresponding notification record's delivery status accordingly.
- **FR-009**: The system MUST reject inbound delivery-status callbacks whose authenticity cannot be verified and MUST NOT alter notification records based on them.
- **FR-010**: Inbound user replies on WhatsApp MUST NOT be treated as actionable input by this feature; this feature is send-only.
- **FR-011**: Configuration of which provider to use (mock vs. real) MUST be a deployment-time setting; tests and local development MUST default to the mock so the production provider is never accidentally invoked from a developer machine.
- **FR-012**: Provider credentials and webhook signing secrets MUST be supplied via environment configuration and MUST NOT be checked into source control or hardcoded.
- **FR-013**: The integration MUST be structured behind a provider-agnostic boundary so a fallback provider can be substituted without changes to notification-firing code. Switching to the fallback provider is a deployment-time operation (configuration change + redeploy); the system MUST NOT support runtime auto-failover or a runtime admin toggle between providers in this phase.
- **FR-014**: Repeated provider callbacks for the same delivery event MUST be idempotent — processing the same callback twice MUST yield the same final state and MUST NOT double-count metrics or duplicate audit rows.
- **FR-015**: The settings surface that already lets a debtor manage per-creditor WhatsApp preferences MUST continue to work end-to-end against the real provider with no UI regression.
- **FR-016**: The system MUST cap message send attempts to one per notification — there is no automatic retry-on-failure for MVP. (Retry logic is explicitly post-MVP.)
- **FR-017**: A notification in the "attempted, status unknown" state MUST remain in that state until a real delivery callback arrives from the provider. The system MUST NOT auto-promote unknown → delivered or unknown → failed via any background job in this phase.

### Key Entities *(include if feature involves data)*

- **Notification**: An auditable record of a debt-lifecycle event addressed to one user. Carries delivery state for the WhatsApp channel (attempted, delivered, failure reason) in addition to the in-app payload.
- **WhatsApp message template**: A pre-approved, locale-specific text body associated with a notification type. The template is parameterized by debt-specific values (creditor name, amount, currency, debt link).
- **Recipient preference**: The combination of the global WhatsApp toggle on the user's profile and the per-creditor preferences keyed on (recipient, creditor). The most restrictive setting wins.
- **Provider delivery callback**: An inbound message from the messaging provider reporting that a previously-sent message was delivered, read, or failed. Tied to a notification by the provider's reference identifier.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 95% of WhatsApp messages sent under nominal provider conditions are reported as delivered to the recipient device within 30 seconds of the triggering event.
- **SC-002**: 100% of debtor opt-outs (global or per-creditor) suppress the corresponding outbound WhatsApp message in functional tests covering all notification types.
- **SC-003**: 0% of business actions (debt transitions, payment confirmations) fail because the messaging provider was unreachable or returned an error, measured across an injected-failure test suite.
- **SC-004**: 100% of inbound delivery callbacks with invalid signatures are rejected without altering any notification record.
- **SC-005**: A duplicate inbound delivery callback for the same provider reference produces no change to the notification record's state on the second receipt (idempotency verified).
- **SC-006**: A creditor reviewing any notification they sent can determine within 5 seconds whether the WhatsApp leg was attempted, delivered, or failed (and why) directly from their notifications view.
- **SC-007**: A debtor toggling per-creditor WhatsApp off in settings sees the next outbound message from that creditor suppressed, with no further configuration steps required.

## Assumptions

- The currently-shipped settings UI for per-creditor WhatsApp preferences is functional end-to-end and does not need redesign — only verification against the real provider.
- The recipient's phone number is stored on the user profile and is reliable enough to send to. Validating phone number ownership (e.g., via verification code) is out of scope here.
- The default messaging provider is WhatsApp Cloud API (Meta) on the cheapest verified-template path, with a fallback provider as contingency if business verification stalls. Only one provider is active per deployment; engaging the fallback is an ops task (config change + redeploy), not a runtime event.
- Pre-approving the message templates with the provider is part of feature delivery, but the act of submitting templates for approval is an operational task, not a code task.
- Provider-side rate limits are sufficient for MVP-scale traffic; no application-level throttling is required at this stage.
- Inbound user replies are out of scope for this feature; the integration is send-only.
- Local development and the test suite default to the mock provider so the real provider is never accidentally invoked outside staging or production.
- Existing in-app notifications continue to be the source of truth for the user's notification history; WhatsApp is a delivery channel, not a separate inbox.
- Hijri/Gregorian formatting and other locale concerns are inherited from the existing notification copy and need no change here.
- The notification record schema can be extended to capture delivery state without breaking existing readers.
- Phase 5 (bilingual coverage) is shipped, so AR/EN strings exist for the in-app side of every notification copy that has a WhatsApp counterpart.
