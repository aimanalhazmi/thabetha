# Tasks: Receipt Upload on Create Debt

**Input**: Design documents from `specs/001-receipt-upload-on-create-debt/`  
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/receipt-attachments.openapi.yaml](./contracts/receipt-attachments.openapi.yaml), [quickstart.md](./quickstart.md)

**Tests**: Backend tests are required by the implementation plan and constitution guidance. Write the listed `FastAPI.TestClient` tests before implementation and confirm they fail for the missing behavior.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel because it touches different files and has no dependency on an incomplete task.
- **[Story]**: Maps a task to a user story from [spec.md](./spec.md).
- Every task includes an exact file path.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish shared constants, translation keys, and multipart support needed by every story.

- [X] T001 [P] Update receipt storage defaults and signed URL TTL settings in `backend/app/core/config.py`
- [X] T002 [P] Add `Attachment`, attachment upload state, and receipt upload constants in `frontend/src/lib/types.ts`
- [X] T003 [P] Add AR/EN receipt upload labels, warnings, errors, and retry strings in `frontend/src/lib/i18n.ts`
- [X] T004 [P] Update `apiRequest` to avoid setting JSON `Content-Type` for `FormData` bodies in `frontend/src/lib/api.ts`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Backend and UI contracts that must exist before any story implementation can be completed.

**Critical**: No user story work should be considered complete until this phase is complete.

- [X] T005 [P] Extend `AttachmentOut` with `url_expires_at`, `retention_state`, and `retention_expires_at` in `backend/app/schemas/domain.py`
- [X] T006 [P] Add backend receipt file validation helper for image/PDF MIME types and 5 MB max size in `backend/app/api/debts.py`
- [X] T007 [P] Document the repository attachment contract for signed URLs, retention fields, and audit events in `backend/app/repositories/base.py`
- [X] T008 [P] Add foundational uploader, receipt list, status, and thumbnail CSS hooks in `frontend/src/styles/app.css`

**Checkpoint**: Frontend and backend contracts are ready for user-story implementation.

---

## Phase 3: User Story 1 - Attach Receipts While Creating a Debt (Priority: P1)

**Goal**: A creditor can optionally select one or more valid image/PDF receipts on the create-debt form, submit the debt, and have each receipt attached after the debt is created.

**Independent Test**: Create a debt with two valid receipt files and verify both are attached and successful attachment events exist.

### Tests for User Story 1

- [X] T009 [P] [US1] Add failing integration test for create debt plus two invoice receipt uploads and `attachment_uploaded` events in `backend/tests/test_receipt_attachments.py`

### Implementation for User Story 1

- [X] T010 [US1] Apply receipt upload validation and use `AttachmentType.invoice` for create-flow uploads in `backend/app/api/debts.py`
- [X] T011 [US1] Implement receipt attachment creation with 1-hour mock signed URL fields and `attachment_uploaded` events in `backend/app/repositories/memory.py`
- [X] T012 [US1] Implement canonical `receipts` bucket path storage and `attachment_uploaded` debt event writes for invoice attachments in `backend/app/repositories/postgres.py`
- [X] T013 [P] [US1] Create reusable multi-select receipt uploader with validation, 4 MB warning, 5 MB rejection, removal, and 2048 px image resize in `frontend/src/components/AttachmentUploader.tsx`
- [X] T014 [US1] Integrate the receipt uploader into the create-debt form and upload accepted files after debt creation in `frontend/src/pages/DebtsPage.tsx`

**Checkpoint**: User Story 1 works independently for the successful create-and-attach path.

---

## Phase 4: User Story 2 - View Receipts From Debt Details (Priority: P2)

**Goal**: A debtor or creditor who is a debt participant can see receipt filenames/previews and open each receipt through a 1-hour signed access link.

**Independent Test**: Open a debt with attached receipts as the debtor and confirm receipt metadata is visible, links are temporary, and unrelated users are denied.

### Tests for User Story 2

- [X] T015 [US2] Add failing integration test for debtor listing attachments with `url_expires_at`, 1-hour expiry, paid-debt archived retention state, and outsider forbidden access in `backend/tests/test_receipt_attachments.py`

### Implementation for User Story 2

- [X] T016 [US2] Derive attachment retention state and 1-hour signed mock URL metadata when listing attachments in `backend/app/repositories/memory.py`
- [X] T017 [US2] Generate Supabase signed URLs, `url_expires_at`, and derived retention state for listed receipt attachments in `backend/app/repositories/postgres.py`
- [X] T018 [US2] Load per-debt attachment state for visible debt cards in `frontend/src/pages/DebtsPage.tsx`
- [X] T019 [US2] Render receipt filenames, image/PDF previews, open links, and retryable load errors in `frontend/src/pages/DebtsPage.tsx`
- [X] T020 [P] [US2] Style receipt lists, thumbnails, document rows, and open-link actions in `frontend/src/styles/app.css`

**Checkpoint**: User Stories 1 and 2 both work independently: receipts can be attached and viewed by debt participants.

---

## Phase 5: User Story 3 - Recover From Receipt Upload Problems (Priority: P3)

**Goal**: Receipt validation and upload failures do not discard the created debt; the creditor sees a clear translated error and can retry failed receipt uploads from the debt surface.

**Independent Test**: Submit a debt with one valid receipt and one failing receipt, then verify the debt exists and the failed receipt can be retried.

### Tests for User Story 3

- [X] T021 [US3] Add failing integration test that invalid receipt upload returns 400 while the created debt remains readable in `backend/tests/test_receipt_attachments.py`

### Implementation for User Story 3

- [X] T022 [US3] Add failed-file state, per-file upload status, and retry callbacks to `frontend/src/components/AttachmentUploader.tsx`
- [X] T023 [US3] Show non-blocking upload failure messages and preserve failed receipt files after debt creation in `frontend/src/pages/DebtsPage.tsx`
- [X] T024 [US3] Add debt-surface retry action for failed receipt uploads after creation in `frontend/src/pages/DebtsPage.tsx`
- [X] T025 [P] [US3] Style failed receipt rows, retry actions, and warning/error states in `frontend/src/styles/app.css`

**Checkpoint**: All user stories work independently and together.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Documentation updates, regression checks, and manual verification.

- [X] T026 [P] Update the receipt-upload MVP status after implementation in `docs/spec-kit/project-status.md`
- [X] T027 [P] Update UC2 receipt-upload status after implementation in `docs/spec-kit/use-cases.md`
- [X] T028 Run `cd backend && uv run pytest` and fix receipt-related failures in `backend/tests/test_receipt_attachments.py`
- [X] T029 Run `cd frontend && npm run typecheck && npm run build` and fix receipt-related failures in `frontend/src/pages/DebtsPage.tsx`
- [ ] T030 Execute the manual smoke path and retention check documented in `specs/001-receipt-upload-on-create-debt/quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies; tasks can start immediately.
- **Foundational (Phase 2)**: Depends on Setup; blocks all user stories.
- **User Story 1 (Phase 3)**: Depends on Foundational.
- **User Story 2 (Phase 4)**: Depends on Foundational; can be started independently, but full UI value is clearer after US1 creates attachments.
- **User Story 3 (Phase 5)**: Depends on Foundational and the uploader surface from US1.
- **Polish (Phase 6)**: Depends on the implemented stories selected for delivery.

### User Story Dependencies

- **US1 Attach Receipts While Creating a Debt**: MVP scope; no dependency on US2 or US3.
- **US2 View Receipts From Debt Details**: Independently testable with seeded/uploaded attachments; complements US1.
- **US3 Recover From Receipt Upload Problems**: Depends on US1 uploader/create flow and adds failure handling.

### Within Each User Story

- Write tests first and confirm they fail.
- Backend schema/validation before repository behavior.
- Repository behavior before frontend integration that depends on response shape.
- Component behavior before page-level wiring.
- Story checkpoint before moving to the next priority if working sequentially.

## Parallel Opportunities

- T001, T002, T003, and T004 can run in parallel.
- T005, T006, T007, and T008 can run in parallel after setup.
- T009 and T013 can run in parallel during US1 because they touch different files.
- T020 can run in parallel with either T018 or T019 during US2 after backend response fields are available; T018 and T019 both edit `DebtsPage.tsx` and should be sequenced.
- T025 can run in parallel with one of T022, T023, or T024 during US3 once the uploader exists; T023 and T024 both edit `DebtsPage.tsx` and should be sequenced.
- T026 and T027 can run in parallel during polish.

## Parallel Example: User Story 1

```bash
Task: "T009 Add failing integration test for create debt plus two invoice receipt uploads and attachment_uploaded events in backend/tests/test_receipt_attachments.py"
Task: "T013 Create reusable multi-select receipt uploader with validation, warnings, rejection, removal, and resize in frontend/src/components/AttachmentUploader.tsx"
```

## Parallel Example: User Story 2

```bash
Task: "T018 Load per-debt attachment state for visible debt cards in frontend/src/pages/DebtsPage.tsx"
Task: "T020 Style receipt lists, thumbnails, document rows, and open-link actions in frontend/src/styles/app.css"
```

## Parallel Example: User Story 3

```bash
Task: "T022 Add failed-file state, per-file upload status, and retry callbacks to frontend/src/components/AttachmentUploader.tsx"
Task: "T025 Style failed receipt rows, retry actions, and warning/error states in frontend/src/styles/app.css"
```

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 setup.
2. Complete Phase 2 foundational tasks.
3. Complete Phase 3 User Story 1.
4. Run the US1 backend test and manually create a debt with two valid receipts.
5. Stop and demo if the MVP only needs successful receipt attachment.

### Incremental Delivery

1. US1: attach receipts during debt creation.
2. US2: view receipt filenames/previews and open temporary signed links.
3. US3: preserve the debt on upload failure and support retry.
4. Polish: update project docs and run backend/frontend verification.

### Validation Targets

- `cd backend && uv run pytest`
- `cd frontend && npm run typecheck`
- `cd frontend && npm run build`
- Manual smoke path in [quickstart.md](./quickstart.md)

## Notes

- Keep `attachment_type=invoice` for this feature; voice notes remain out of scope.
- Signed link expiry is 1 hour; file retention is until paid plus 6 archived months.
- Do not use the legacy `thabetha-attachments` bucket for new receipt uploads.
- Every user-facing string added by these tasks must have AR and EN entries.
