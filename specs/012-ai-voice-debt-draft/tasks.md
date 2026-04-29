# Tasks: Voice-to-Debt Draft Polish

**Input**: Design documents from `/specs/012-ai-voice-debt-draft/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/voice-debt-draft.md, quickstart.md

**Tests**: Backend TestClient tests are required by the feature spec and constitution for AI gating, daily limits, and draft behavior. Frontend tests are included only if the existing frontend test harness supports this surface; otherwise quickstart manual validation closes the UI path.

**Organization**: Tasks are grouped by user story so each story can be implemented and tested independently after foundational work.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel because it touches different files or has no dependency on incomplete work.
- **[Story]**: User story label from spec.md. Setup, Foundational, and Polish tasks do not use story labels.
- Every task includes an exact repository path.

## Phase 1: Setup

**Purpose**: Prepare the feature file structure and configuration points.

- [X] T001 Create the AI service package skeleton in `backend/app/services/ai/__init__.py`
- [X] T002 [P] Add AI speech-to-text and daily-limit settings placeholders in `backend/app/core/config.py`
- [X] T003 [P] Add the Postgres usage-counter migration skeleton in `supabase/migrations/014_ai_voice_draft_usage.sql`
- [X] T004 [P] Add voice draft i18n key placeholders for Arabic and English in `frontend/src/lib/i18n.ts`

---

## Phase 2: Foundational

**Purpose**: Shared contracts, persistence, provider abstractions, and helpers that block all user stories.

**Critical**: No user story implementation should start until this phase is complete.

- [X] T005 Update `backend/app/schemas/domain.py` with `VoiceDraftFieldStatus`, `VoiceDraftFieldConfirmations`, expanded `VoiceDebtDraftRequest`, multipart-compatible helper schema if needed, and `VoiceDebtDraftOut.field_confirmations`
- [X] T006 Update `frontend/src/lib/types.ts` so `VoiceDraft` mirrors `VoiceDebtDraftOut`, including `raw_transcript`, `confidence`, and `field_confirmations`
- [X] T007 Define AI usage-counter repository methods in `backend/app/repositories/base.py`
- [X] T008 Implement AI usage-counter methods in `backend/app/repositories/memory.py`
- [X] T009 Implement AI usage-counter methods in `backend/app/repositories/postgres.py`
- [X] T010 Implement the SQL objects for `ai_usage_records` or equivalent daily counter in `supabase/migrations/014_ai_voice_draft_usage.sql`
- [X] T011 Add `backend/app/services/ai/limits.py` to enforce per-user daily limits with shared JSON/audio counting semantics
- [X] T012 Add `backend/app/services/ai/transcribe.py` with the speech-to-text provider interface, supported audio type validation, max-duration validation, and real-provider factory
- [X] T013 [P] Add deterministic test transcription provider in `backend/app/services/ai/mock_transcribe.py`
- [X] T014 Add `backend/app/services/ai/draft_extract.py` for shared transcript-to-draft extraction, currency inference from `ProfileOut.preferred_language`, no profile matching, and default field confirmation statuses
- [X] T015 Refactor `backend/app/api/ai.py` so `draft_debt_from_voice` delegates AI gating, daily-limit checks, transcription, and draft extraction to shared services without changing route path
- [X] T016 Add JSON and multipart helper functions for voice drafts in `frontend/src/lib/api.ts`

**Checkpoint**: Backend and frontend contracts can compile against the new draft shape; stories can now be implemented.

---

## Phase 3: User Story 1 - Create a debt draft from recorded or uploaded audio (Priority: P1)

**Goal**: A creditor records or uploads short Arabic/English audio, receives an editable draft with raw transcript, confirms/edits every extracted field, and creates no debt until submitting through the normal create-debt flow.

**Independent Test**: Use a valid short audio upload through the AI endpoint and create-debt UI. Verify the draft includes transcript, debtor name as free text, amount, currency, due date, description, and unconfirmed field statuses; audio is deleted after transcription; no debt exists until form submission.

### Tests for User Story 1

- [X] T017 [US1] Add backend multipart audio success test with mock transcription in `backend/tests/test_ai_voice_debt_draft.py`
- [X] T018 [US1] Add backend unsupported audio type and over-60-second rejection tests in `backend/tests/test_ai_voice_debt_draft.py`
- [X] T019 [US1] Add backend test proving successful audio transcription deletes temporary audio and returns no signed audio URL in `backend/tests/test_ai_voice_debt_draft.py`
- [X] T020 [US1] Add backend test proving spoken debtor names are free text and no profile id or match metadata is returned in `backend/tests/test_ai_voice_debt_draft.py`

### Implementation for User Story 1

- [X] T021 [P] [US1] Implement multipart content-type dispatch and `UploadFile` handling in `backend/app/api/ai.py`
- [X] T022 [US1] Implement temporary voice-note storage and delete-after-success behavior through repository/storage helpers in `backend/app/repositories/base.py`, `backend/app/repositories/memory.py`, and `backend/app/repositories/postgres.py`
- [X] T023 [US1] Wire mock and real transcription provider selection in `backend/app/services/ai/transcribe.py`
- [X] T024 [US1] Ensure audio draft extraction populates `field_confirmations` as `extracted_unconfirmed` or `missing` in `backend/app/services/ai/draft_extract.py`
- [X] T025 [P] [US1] Add create-debt form state for voice draft, raw transcript, and per-field confirmation in `frontend/src/pages/DebtsPage.tsx`
- [X] T026 [US1] Add creditor-only voice record/upload controls and loading/error states to the create-debt panel in `frontend/src/pages/DebtsPage.tsx`
- [X] T027 [US1] Apply audio draft values into the existing `debtForm` without setting `debtor_id` in `frontend/src/pages/DebtsPage.tsx`
- [X] T028 [US1] Block create-debt submission until every extracted voice draft field is confirmed or edited in `frontend/src/pages/DebtsPage.tsx`
- [X] T029 [P] [US1] Add Arabic and English labels/errors for recording, upload, transcript review, field confirmation, unsupported type, audio-too-long, and transcription failure in `frontend/src/lib/i18n.ts`

**Checkpoint**: User Story 1 works independently for audio input and does not create a debt before reviewed form submission.

---

## Phase 4: User Story 2 - Keep transcript-based draft creation available (Priority: P1)

**Goal**: Existing transcript-only clients and tests continue to receive the same draft behavior without audio.

**Independent Test**: Submit a JSON transcript and verify a populated draft with `raw_transcript`, field confirmation statuses, missing-field behavior, currency inference, and no audio/provider requirement.

### Tests for User Story 2

- [X] T030 [P] [US2] Update existing JSON transcript AI test in `backend/tests/test_profiles_qr_groups_ai.py` to assert `raw_transcript`, `field_confirmations`, and backward-compatible fields
- [X] T031 [P] [US2] Add JSON transcript regression tests for missing amount and missing currency inference in `backend/tests/test_ai_voice_debt_draft.py`

### Implementation for User Story 2

- [X] T032 [US2] Preserve JSON request parsing for `VoiceDebtDraftRequest` in `backend/app/api/ai.py`
- [X] T033 [US2] Ensure JSON transcript requests use the same `draft_extract` service and field confirmation behavior in `backend/app/services/ai/draft_extract.py`
- [X] T034 [US2] Update `frontend/src/pages/AIPage.tsx` to handle the expanded `VoiceDraft` response shape without rendering raw untranslated backend errors

**Checkpoint**: User Story 2 works independently through JSON input and existing AI tests remain compatible.

---

## Phase 5: User Story 3 - Enforce AI-tier access and usage limits (Priority: P2)

**Goal**: Both audio and transcript draft creation are blocked for ineligible creditors and over-limit AI-tier creditors, while successful draft attempts count exactly once.

**Independent Test**: Attempt JSON and audio draft creation as `ai_enabled=false`, `ai_enabled=true` under limit, and `ai_enabled=true` over limit. Verify 403, 200, 429 with `Retry-After`, and correct counting behavior.

### Tests for User Story 3

- [X] T035 [US3] Add backend tests for `ai_enabled=false` returning structured 403 for both JSON and multipart in `backend/tests/test_ai_voice_debt_draft.py`
- [X] T036 [US3] Add backend tests for daily-limit 429 and `Retry-After` on JSON and multipart draft attempts in `backend/tests/test_ai_voice_debt_draft.py`
- [X] T037 [US3] Add backend tests proving invalid audio and failed transcription do not increment daily usage in `backend/tests/test_ai_voice_debt_draft.py`

### Implementation for User Story 3

- [X] T038 [P] [US3] Return structured AI subscription errors from `_require_ai_enabled` in `backend/app/api/ai.py`
- [X] T039 [US3] Enforce daily limits before successful draft responses and increment usage exactly once in `backend/app/services/ai/limits.py` and `backend/app/api/ai.py`
- [X] T040 [P] [US3] Add localized frontend error mapping for `ai_subscription_required`, `ai_daily_limit_reached`, and `Retry-After` guidance in `frontend/src/lib/errors.ts` and `frontend/src/lib/i18n.ts`
- [X] T041 [US3] Hide or disable voice draft controls for non-AI-tier creditors with translated upgrade copy in `frontend/src/pages/DebtsPage.tsx`

**Checkpoint**: User Story 3 works independently for access control and quota behavior across both input paths.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final verification, documentation, and consistency cleanup across the whole feature.

- [X] T042 [P] Update `docs/spec-kit/use-cases.md` UC10 to mention voice-to-debt draft behavior and gating
- [X] T043 [P] Update `docs/spec-kit/api-endpoints.md` with the JSON and multipart `/api/v1/ai/debt-draft-from-voice` contract
- [X] T044 [P] Update `docs/spec-kit/project-status.md` to reflect Phase 12 planning/implementation status
- [X] T045 Run backend focused tests with `REPOSITORY_TYPE=memory pytest backend/tests/test_ai_voice_debt_draft.py backend/tests/test_profiles_qr_groups_ai.py`
- [X] T046 Run broader backend regression tests with `REPOSITORY_TYPE=memory pytest backend/tests`
- [X] T047 Run frontend validation with `npm --prefix frontend run lint` and available frontend tests if configured
- [ ] T048 Execute the manual checks in `specs/012-ai-voice-debt-draft/quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 Setup**: No dependencies.
- **Phase 2 Foundational**: Depends on Phase 1. Blocks all user stories.
- **Phase 3 US1**: Depends on Phase 2. Delivers the audio MVP.
- **Phase 4 US2**: Depends on Phase 2. Can run in parallel with US1 after shared services exist, but must reconcile shared files with US1.
- **Phase 5 US3**: Depends on Phase 2. Can run in parallel with US1/US2 for tests and limits service, but route integration touches `backend/app/api/ai.py`.
- **Phase 6 Polish**: Depends on the user stories selected for delivery.

### User Story Dependencies

- **US1 (P1)**: MVP for audio input. No dependency on US2 or US3 beyond Foundational.
- **US2 (P1)**: Regression path for transcript input. No dependency on US1 beyond shared extraction.
- **US3 (P2)**: Access and limits. Depends on shared repository/service contracts from Foundational; can be validated independently.

### Parallel Opportunities

- T002, T003, T004 can run in parallel after T001.
- T013 can run in parallel with T011 and T012.
- T017 through T020 should be sequenced or coordinated because they share `backend/tests/test_ai_voice_debt_draft.py`.
- T030 and T031 can be authored in parallel before US2 implementation.
- T035 through T037 should be sequenced or coordinated because they share `backend/tests/test_ai_voice_debt_draft.py`.
- T042, T043, T044 can run in parallel during polish.

---

## Parallel Example: User Story 1

```text
Task: "T021 [P] [US1] Implement multipart content-type dispatch and UploadFile handling in backend/app/api/ai.py"
Task: "T025 [P] [US1] Add create-debt form state for voice draft, raw transcript, and per-field confirmation in frontend/src/pages/DebtsPage.tsx"
Task: "T029 [P] [US1] Add Arabic and English labels/errors for recording, upload, transcript review, field confirmation, unsupported type, audio-too-long, and transcription failure in frontend/src/lib/i18n.ts"
```

## Parallel Example: User Story 2

```text
Task: "T030 [P] [US2] Update existing JSON transcript AI test in backend/tests/test_profiles_qr_groups_ai.py to assert raw_transcript, field_confirmations, and backward-compatible fields"
Task: "T031 [P] [US2] Add JSON transcript regression tests for missing amount and missing currency inference in backend/tests/test_ai_voice_debt_draft.py"
```

## Parallel Example: User Story 3

```text
Task: "T038 [P] [US3] Return structured AI subscription errors from _require_ai_enabled in backend/app/api/ai.py"
Task: "T040 [P] [US3] Add localized frontend error mapping for ai_subscription_required, ai_daily_limit_reached, and Retry-After guidance in frontend/src/lib/errors.ts and frontend/src/lib/i18n.ts"
Task: "T041 [US3] Hide or disable voice draft controls for non-AI-tier creditors with translated upgrade copy in frontend/src/pages/DebtsPage.tsx"
```

---

## Implementation Strategy

### MVP First

1. Complete Phase 1 and Phase 2.
2. Complete Phase 3 (US1) for audio input.
3. Validate with T017-T020 and quickstart audio checks.
4. Stop here if only the voice audio MVP is needed.

### Full Feature

1. Complete Setup and Foundational phases.
2. Deliver US1 audio draft flow.
3. Deliver US2 transcript regression path.
4. Deliver US3 gating and daily-limit behavior.
5. Finish polish tasks and run the full validation set.

### File Conflict Notes

- `backend/app/api/ai.py` is touched by US1, US2, and US3; coordinate route edits carefully.
- `frontend/src/pages/DebtsPage.tsx` is touched by US1 and US3; land the draft state model before adding AI-tier visibility polish.
- `backend/tests/test_ai_voice_debt_draft.py` contains tests for all stories; parallel test authors should avoid editing the same region.
