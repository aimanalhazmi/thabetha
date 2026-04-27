# Feature Specification: Receipt Upload on Create Debt

**Feature Branch**: `001-receipt-upload-on-create-debt`  
**Created**: 2026-04-27  
**Status**: Draft  
**Input**: User description: "Read the plan in docs/spec-kit/implementation-plan.md and do only Phase 1 - Receipt upload on Create Debt"

## Clarifications

### Session 2026-04-27

- Q: How long should secure receipt access last? → A: Receipt files remain available until the debt is paid, are archived for 6 months after payment, and each secure access link expires after 1 hour.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Attach Receipts While Creating a Debt (Priority: P1)

A creditor creating a debt can optionally add one or more receipt files before submitting the debt, so the proof of purchase or invoice is captured in the same workflow as the debt.

**Why this priority**: This closes the primary MVP gap for debt creation and removes a separate follow-up step for creditors.

**Independent Test**: Can be fully tested by creating a debt with two valid receipt files and verifying that the created debt includes both files on its details page.

**Acceptance Scenarios**:

1. **Given** a creditor is filling out the create-debt form, **When** they select multiple valid receipt images or PDFs and submit the form, **Then** the debt is created and each selected receipt is attached to the new debt.
2. **Given** a creditor does not select any receipt, **When** they submit the create-debt form, **Then** the debt is created normally without requiring an attachment.

---

### User Story 2 - View Receipts From Debt Details (Priority: P2)

A debtor viewing a debt can see the attached receipts and open them through secure temporary access, so they can verify the supporting documentation before responding to the debt.

**Why this priority**: Receipt upload has value only if the counterparty can inspect the attached evidence.

**Independent Test**: Can be tested by opening a debt with attached receipts as the debtor and confirming that receipt filenames or thumbnails appear and each receipt can be opened.

**Acceptance Scenarios**:

1. **Given** a debt has one or more attached receipts, **When** the debtor opens the debt details page, **Then** the debtor sees each receipt with a filename and a visual preview where available.
2. **Given** a debtor opens a receipt from debt details, **When** the receipt access is requested, **Then** the system provides secure temporary access to the file.

---

### User Story 3 - Recover From Receipt Upload Problems (Priority: P3)

A creditor receives clear validation and recovery options when a selected receipt cannot be attached, so the debt is not lost and the creditor can retry attachment later.

**Why this priority**: Upload failures should not block debt creation or cause users to re-enter debt details.

**Independent Test**: Can be tested by submitting a debt with one valid receipt and one receipt that fails attachment, then verifying the debt is still created and the creditor is offered a retry path from debt details.

**Acceptance Scenarios**:

1. **Given** a creditor selects a file larger than the allowed size, **When** the file is added to the create-debt form, **Then** the system rejects that file before submission and shows a translated error.
2. **Given** a debt is created successfully but one receipt attachment fails, **When** the creation flow completes, **Then** the creditor sees a non-blocking error and can retry attaching the failed receipt from debt details.

### Edge Cases

- No receipt selected: debt creation remains available and unchanged.
- Multiple files selected together: each file is validated independently before submission.
- Unsupported file type selected: the file is rejected before submission with a translated error.
- Selected file is larger than 4 MB and no larger than 5 MB: the creditor receives a warning but may continue.
- Selected file is larger than 5 MB: the file is rejected before submission.
- A valid receipt upload fails after the debt is created: the debt remains created, the failure is shown as non-blocking, and retry is available from debt details.
- A creditor removes a selected receipt before submission: the removed file is not attached.
- A debtor opens a debt while receipt access is temporarily unavailable: the debt details remain visible and the receipt area shows a retryable error state.
- A debt is paid: receipt files move to archived retention for 6 months after payment.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST let creditors add receipt files as an optional part of the create-debt form.
- **FR-002**: The system MUST allow one or more receipt files to be selected for a single debt creation flow.
- **FR-003**: The system MUST accept image files and PDF files as receipts.
- **FR-004**: The system MUST reject unsupported receipt file types before the debt is submitted.
- **FR-005**: The system MUST warn creditors when a selected receipt is larger than 4 MB and no larger than 5 MB.
- **FR-006**: The system MUST reject any selected receipt larger than 5 MB before the debt is submitted.
- **FR-007**: The system MUST resize accepted image receipts whose longest edge exceeds 2048 pixels before attaching them, while preserving legibility.
- **FR-008**: The system MUST create the debt even when no receipt is selected.
- **FR-009**: The system MUST attach each accepted receipt to the newly created debt after the debt is created.
- **FR-010**: The system MUST keep the debt created if one or more receipt attachments fail after debt creation.
- **FR-011**: The system MUST show a non-blocking, translated error when a receipt attachment fails after debt creation.
- **FR-012**: The system MUST provide a retry path from debt details for receipt attachments that failed during creation.
- **FR-013**: The system MUST show attached receipts on the debt details page to permitted debt participants.
- **FR-014**: The system MUST let permitted debt participants open attached receipts through secure temporary access links that expire after 1 hour.
- **FR-015**: The system MUST show each attached receipt with its filename and a thumbnail when a visual preview is available.
- **FR-016**: The system MUST record audit history for debt creation and for each successful receipt attachment.
- **FR-017**: The system MUST provide user-facing receipt upload labels, validation messages, failure messages, and retry text in supported interface languages.
- **FR-018**: The system MUST keep voice notes and non-receipt media outside the scope of this feature.
- **FR-019**: The system MUST keep receipt files available until the debt is paid, then retain them in archived state for 6 months after payment.

### Key Entities

- **Debt**: A financial obligation created by a creditor for a debtor; may have zero or more receipt attachments.
- **Receipt Attachment**: A file linked to a debt as supporting evidence; includes filename, file type, file size, preview availability, attachment status, secure access availability, and retention state.
- **Debt Participant**: A creditor or debtor permitted to view the debt and its allowed supporting materials.
- **Debt Activity Event**: A user-visible audit entry for meaningful debt activity, including debt creation and successful receipt attachment.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 95% of creditors can create a debt with two receipt files in under 3 minutes during usability testing.
- **SC-002**: 100% of unsupported files and files larger than 5 MB are rejected before submission with a translated user-facing message.
- **SC-003**: 95% of attached receipts appear on debt details within 5 seconds after a successful debt creation flow completes.
- **SC-004**: 100% of tested receipt upload failures after debt creation preserve the created debt and show a retry option.
- **SC-005**: 100% of tested successful receipt attachments create an audit history entry visible in the debt activity history.
- **SC-006**: 90% of debtor test participants can locate and open attached receipts from debt details without assistance.
- **SC-007**: 100% of tested secure receipt access links expire after 1 hour, while receipt files remain retained until the debt is paid and for 6 archived months after payment.

## Assumptions

- Existing debt creation already authenticates the creditor and identifies the debtor according to current product rules.
- Existing attachment storage and permission controls are available for receipt files.
- "Receipt" includes purchase receipts, invoices, and similar proof documents.
- Receipt upload is optional; creating a debt without receipts remains valid.
- Voice notes, receipt text extraction, and AI-assisted receipt parsing are out of scope for this phase.
- Secure temporary access links expire after 1 hour; receipt files remain available until the debt is paid and are retained in archived state for 6 months after payment.
