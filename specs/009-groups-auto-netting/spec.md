# Feature Specification: Group Auto-Netting

**Feature Branch**: `009-groups-auto-netting`  
**Created**: 2026-04-29  
**Status**: Draft  
**Input**: User description: "Phase 9 — Group auto-netting (UC9 part 2)"

## Clarifications

### Session 2026-04-29

- Q: Can the member who created a settlement proposal cancel/withdraw it before it resolves? → A: No — only rejection by a required party or 7-day expiry can void an open proposal.
- Q: If the final settlement operation fails technically after all confirmations are received, what should the system do? → A: Mark proposal as "settlement failed", notify all members, keep all debts unchanged — members can start a new proposal.
- Q: Is counter-proposal (suggesting modified transfer terms) in scope, or does "counter" mean reject + new proposal? → A: Counter = reject — the proposal is voided and any member may initiate a new one.
- Q: What can zero-net-position members (observers) see when viewing an open settlement proposal? → A: Final transfer list only — computed transfers (payer, receiver, net amount) but not the underlying individual debt breakdown.
- Q: Are automated in-app notifications to required confirmers mandatory for this feature? → A: Mandatory — in-app notifications on proposal creation and near-expiry are a hard requirement.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Propose Group Settlement (Priority: P1)

A group member wants to clear all outstanding debts within the group in a single, fair settlement. They trigger a "settle group" action, which calculates the minimum number of transfers needed to zero out everyone's net position and presents these proposed transfers for all members to review before anything is committed.

**Why this priority**: This is the core value proposition — reducing N bilateral debts to the minimum number of payments eliminates manual tracking and back-and-forth negotiation.

**Independent Test**: Can be fully tested by creating a group with circular debts, triggering a settlement proposal, and verifying the proposed transfers represent the correct minimum-edge solution.

**Acceptance Scenarios**:

1. **Given** a group of 3 members with circular debts (A owes B, B owes C, C owes A each 100 SAR), **When** any member triggers "settle group", **Then** the system presents a proposal showing 1–2 transfers (not 3) that net all balances to zero.
2. **Given** a settlement proposal has been created, **When** a member views the proposal, **Then** they see each proposed transfer with payer name, receiver name, and amount.
3. **Given** a group with no outstanding debts, **When** a member triggers "settle group", **Then** the system informs them there is nothing to settle and no proposal is created.
4. **Given** a group already has an active open proposal, **When** any member attempts to trigger a new settlement, **Then** the system rejects the request and shows the existing open proposal.

---

### User Story 2 - Confirm or Reject Settlement Proposal (Priority: P2)

Each party involved in a proposed transfer reviews and confirms or rejects their role in the settlement. When all required parties confirm, the system atomically marks all underlying debts as settled and updates every member's commitment indicator.

**Why this priority**: Without multi-party confirmation, settlement cannot be binding or fair — all involved parties must explicitly agree before any debt is cleared.

**Independent Test**: Can be fully tested by having all required parties confirm a proposal and verifying all underlying debts transition to paid with correct commitment indicator updates.

**Acceptance Scenarios**:

1. **Given** a settlement proposal exists and all transfer parties confirm within 7 days, **When** the final confirmation lands, **Then** all debts in the snapshot are atomically marked paid and each party's commitment indicator is updated accordingly.
2. **Given** a settlement proposal exists, **When** one required party rejects it, **Then** the proposal is voided immediately and every debt remains in its pre-proposal state.
3. **Given** a settlement proposal has been open for 7 days without all confirmations received, **When** the deadline passes, **Then** the proposal expires automatically and all debts remain unchanged.
4. **Given** a settlement proposal exists, **When** a group member who has zero net position views it, **Then** they can see the proposal details but are not required to confirm (they are observers only).

---

### User Story 3 - Handle Mixed Currencies (Priority: P3)

When members of a group have debts denominated in different currencies, the system prevents auto-netting at proposal creation time and clearly explains why.

**Why this priority**: Netting requires a single unit of account. This guard prevents mathematically incorrect settlements.

**Independent Test**: Can be fully tested by creating group debts in two different currencies and attempting to trigger a settlement proposal, verifying immediate rejection.

**Acceptance Scenarios**:

1. **Given** a group contains debts in more than one currency, **When** a member triggers "settle group", **Then** the system immediately rejects the proposal with a clear message that mixed currencies cannot be auto-netted.
2. **Given** a group contains only same-currency debts, **When** a member triggers "settle group", **Then** the system proceeds normally with the netting calculation and proposal creation.

---

### Edge Cases

- What happens when a group has only two members and one debt? (Exactly one transfer needed; proposal still follows the two-phase confirmation flow)
- What if new debts are added to the group during the 7-day confirmation window? (New debts are excluded; only the snapshot taken at proposal creation is settled)
- What if a member involved in a proposed transfer attempts to leave the group while the proposal is open? (Leave action is blocked until the proposal resolves)
- What if the netting algorithm produces a proposal where a member both pays and receives in different transfers? (Both transfers are included; no further internal netting beyond the minimum-edge output)
- What happens when all group debts are between the same two members with no circular dependencies? (Simple two-transfer or single-transfer scenario, no netting benefit — proposal still works correctly)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Any accepted group member MUST be able to initiate a settlement proposal for their group at any time, subject to the one-active-proposal-per-group constraint.
- **FR-002**: The system MUST compute the minimum number of transfers that net all members' group debt balances to zero using a minimum-flow algorithm on the directed debt graph.
- **FR-003**: A settlement proposal MUST capture an immutable snapshot of all outstanding group debts at the moment of proposal creation; debts created or modified after that moment are excluded from this proposal.
- **FR-004**: The system MUST reject a settlement proposal at creation time if the group contains debts denominated in more than one currency.
- **FR-005**: Only one active settlement proposal may exist per group at a time; a new proposal cannot be initiated while an existing one is open. A proposal cannot be withdrawn by the proposer — it resolves only through rejection by a required party or 7-day expiry.
- **FR-006**: Every group member who appears as a payer or receiver in the proposed transfers MUST explicitly confirm or reject the proposal before settlement can proceed.
- **FR-007**: Group members with a net-zero position in the proposal are not required to confirm; they may view the proposal as observers. Observers see only the final transfer list (payer, receiver, net amount) — not the underlying individual debt breakdown in the snapshot.
- **FR-008**: A settlement proposal MUST expire automatically after 7 days if not all required confirmations have been received; expiry leaves all debts unchanged.
- **FR-009**: If any required party rejects the proposal, the system MUST void the proposal immediately and leave all debts in their pre-proposal state. There is no counter-proposal flow — rejection is final; any member may start a fresh proposal afterward.
- **FR-010**: When all required parties confirm, the system MUST atomically mark every snapshotted debt as paid in a single operation — partial settlement is not permitted. If the operation fails, the proposal MUST be marked "settlement failed", all members notified, and all debts left unchanged; members may then initiate a new proposal.
- **FR-011**: Upon successful settlement, each settled debt MUST trigger a commitment indicator update using neutral settlement rules (no early-payment bonus, no overdue penalty), regardless of original due dates.
- **FR-012**: The full settlement proposal — proposed transfers, each party's confirmation status, expiry date, and proposer identity — MUST be visible to all group members throughout the confirmation window.
- **FR-014**: The system MUST send in-app notifications to all required confirmers immediately when a proposal is created. A second reminder notification MUST be sent to any confirmer who has not yet responded when the proposal is within 24 hours of expiry.
- **FR-013**: A group member who is involved in a proposed transfer MUST NOT be able to leave the group while the proposal is open.

### Key Entities

- **Settlement Proposal**: Represents a single netting run for a group. Contains the debt snapshot, computed transfer list, status (open / confirmed / rejected / expired), proposer, creation date, and expiry date. One active proposal per group at a time.
- **Settlement Confirmation**: Records a required party's response (confirmed or rejected) with a timestamp. One record per (proposal, user) pair.
- **Proposed Transfer**: A single computed payment within a proposal — payer, receiver, and net amount. The full set of proposed transfers is the output of the netting algorithm applied to the debt snapshot.
- **Debt Snapshot**: The immutable set of outstanding group debts captured at proposal creation. The settlement operates exclusively on this snapshot.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A 3-member circular debt scenario (A→B→C→A) resolves to 2 or fewer proposed transfers, demonstrating minimum-edge netting correctness.
- **SC-002**: After the final required confirmation is received, all underlying debts transition to settled status within a single atomic operation — no additional user action or manual follow-up required.
- **SC-003**: A rejected proposal leaves every debt in the group in exactly the state it was in before the proposal was created — zero unintended state changes on rejection.
- **SC-004**: A mixed-currency group settlement attempt is rejected at proposal creation time, before any confirmation flow begins, with a user-facing explanation in the active language.
- **SC-005**: An expired proposal (7-day timeout without full confirmation) causes no debt state changes and is displayed as expired to all group members.
- **SC-006**: The settlement confirmation flow completes end-to-end — from proposal to all debts marked paid — without requiring any out-of-band coordination between members beyond in-app notifications.
- **SC-007**: A technically failed settlement (all confirmations received but operation fails) leaves every debt in the group unchanged and surfaces a "settlement failed" status to all members, with no silent data loss.

## Assumptions

- Group auto-netting applies only to debts explicitly tagged to the group; personal debts between the same users outside any group are unaffected.
- Only members with `accepted` status are included in netting calculations; pending invitees are excluded.
- Commitment indicator updates at settlement time treat each debt as paid on the settlement date — no early-payment bonus, no overdue penalty — regardless of the original due dates.
- The 7-day confirmation window is fixed and non-configurable in the current scope.
- Group ownership transfer is blocked while a settlement proposal is active.
- The netting algorithm operates on the final outstanding balance of each debt at snapshot time (after any partial payments, if such a concept exists) — not on original amounts.
- In-app notifications to all required confirmers on proposal creation and within-24-hours-of-expiry reminder are mandatory, not best-effort.
- The feature depends on Phase 8 (Groups MVP Surface) being complete — groups, membership, and group-tagged debts must already exist.
