# Feature Specification: Voice-to-Debt Draft Polish

**Feature Branch**: `012-ai-voice-debt-draft`  
**Created**: 2026-04-29  
**Status**: Draft  
**Input**: User description: "Phase 12 — Voice-to-debt draft polish"

## Clarifications

### Session 2026-04-29

- Q: How long should the system retain original voice audio after transcription? → A: Delete audio after successful transcription; retain transcript with the draft.
- Q: How should the creditor review extracted voice-draft fields before creating a debt? → A: Require manual confirmation for every extracted field.
- Q: What should happen when currency is not spoken or confidently detected? → A: Infer currency from creditor profile locale.
- Q: Should voice drafts attempt to match spoken debtor names to existing profiles? → A: Never attempt profile matching from voice drafts.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Create a debt draft from recorded or uploaded audio (Priority: P1)

A creditor creating a debt can record or upload a short Arabic or English voice note instead of manually entering every field. The system transcribes the audio, extracts the debt details, and presents an editable draft before anything is created.

**Why this priority**: This is the core user value of the phase. It reduces create-debt friction while preserving creditor review and control before submission.

**Independent Test**: A creditor provides a valid short Arabic or English audio note, receives a draft containing debtor name, amount, due date, and description when those details were spoken, reviews the transcript, confirms or edits every extracted field, resolves the debtor through the normal create-debt flow, and submits or discards the draft without creating unintended debt records.

**Acceptance Scenarios**:

1. **Given** an AI-tier creditor is on the create-debt form, **When** they record a valid 30-second Arabic voice note containing debtor, amount, and due date, **Then** the system shows an editable draft populated from the spoken details and displays the transcript used to create it.
2. **Given** an AI-tier creditor uploads a valid English audio file containing debt details, **When** processing completes, **Then** the system shows the extracted fields and raw transcript before the creditor creates the debt.
3. **Given** the extracted draft contains populated, uncertain, or missing fields, **When** the creditor reviews the draft, **Then** every extracted field requires explicit confirmation or editing before submission.
4. **Given** the transcript includes a debtor name matching an existing profile, **When** the draft is generated, **Then** the system treats the debtor as free text and does not link the draft to that profile automatically.

---

### User Story 2 - Keep transcript-based draft creation available (Priority: P1)

A client or test flow that already has a transcript can still submit the transcript directly and receive the same editable debt draft, without requiring audio.

**Why this priority**: The existing transcript path is already useful for tests and clients that bring their own speech-to-text capability. Preserving it prevents regression while audio handling is added.

**Independent Test**: Submit a transcript containing debt details and verify that the same draft extraction behavior is available without uploading audio.

**Acceptance Scenarios**:

1. **Given** a valid transcript with debtor, amount, and due date, **When** an eligible creditor submits the transcript for draft creation, **Then** the system returns a populated editable draft, includes the same transcript in the response, and requires explicit confirmation or editing of every extracted field before submission.
2. **Given** a transcript omits the amount, **When** draft creation completes, **Then** the draft leaves amount blank or marked as unresolved so the creditor must fill it before creating a debt.

---

### User Story 3 - Enforce AI-tier access and usage limits (Priority: P2)

Only creditors with access to the AI tier can create debt drafts from voice or transcript, and daily usage limits apply consistently across both input methods.

**Why this priority**: Voice-to-debt is part of the paid AI tier. Access and daily-limit behavior must match other AI draft features so the product boundary is predictable.

**Independent Test**: Attempt voice and transcript draft creation as ineligible, eligible-with-quota, and eligible-over-quota creditors, then verify the correct allowed or blocked outcome in each case.

**Acceptance Scenarios**:

1. **Given** a creditor without AI-tier access, **When** they attempt to create a draft from audio or transcript, **Then** the system blocks the request with a clear upgrade or access message and no draft is created.
2. **Given** an AI-tier creditor has reached the daily limit, **When** they attempt another audio or transcript draft, **Then** the system blocks the request with a translated daily-limit message.
3. **Given** an AI-tier creditor still has daily quota, **When** they create a draft from audio or transcript, **Then** usage is counted exactly once for the successful draft attempt.

### Edge Cases

- Audio longer than 60 seconds must be rejected before draft extraction and must not count against the daily usage limit.
- Unsupported audio formats must be rejected with a user-friendly message before draft extraction.
- Empty, silent, or unintelligible audio must return a clear "could not transcribe" outcome and allow the creditor to retry or enter the debt manually.
- Mixed Arabic and English speech must still produce the best available transcript and draft without requiring the user to choose a language first.
- Transcription succeeds but draft extraction finds no debt details: the system must show the transcript and ask the creditor to enter the missing debt details manually.
- The transcript contains an amount but no currency: the draft must infer currency from the creditor profile locale and still require creditor confirmation before submission.
- The transcript contains a debtor name that matches one or more existing profiles: the draft must not auto-link to any profile and the creditor must resolve the debtor manually through the normal create-debt flow.
- Audio processing fails after upload or recording: the creditor must be able to retry without losing the create-debt form state.
- A transcript submitted directly must follow the same eligibility, daily-limit, and draft-validation rules as audio input.
- Successfully transcribed audio must be deleted after transcription; if transcription fails, any temporary audio retained for retry or diagnostics must not become a long-lived user attachment.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST allow eligible creditors to create a debt draft from a recorded or uploaded audio note while creating a debt.
- **FR-002**: The system MUST support audio files in webm, mp3, wav, and m4a formats.
- **FR-003**: The system MUST reject audio longer than 60 seconds before attempting draft extraction.
- **FR-004**: The system MUST support Arabic and English voice input without requiring the creditor to manually select the language.
- **FR-005**: The system MUST convert accepted audio into a transcript before extracting debt draft fields.
- **FR-006**: The system MUST return the raw transcript used for draft extraction so the creditor can review what was heard.
- **FR-007**: The system MUST extract draft debt fields from the transcript, including debtor name, amount, due date, and description when present in the transcript.
- **FR-008**: The system MUST present extracted debt fields as an editable draft and MUST NOT create a debt until the creditor explicitly confirms or edits every extracted field and submits the reviewed draft.
- **FR-009**: The system MUST preserve the existing direct-transcript draft path for clients and tests that already have a transcript.
- **FR-010**: If the transcript contains an amount but no currency, the system MUST infer the draft currency from the creditor profile locale and require creditor confirmation before submission.
- **FR-011**: The system MUST NOT attempt to match or link extracted debtor names to existing profiles from voice drafts; debtor resolution remains a creditor-confirmed create-debt step.
- **FR-012**: Direct-transcript draft creation MUST return the provided transcript as the raw transcript for review.
- **FR-013**: The system MUST apply the same AI-tier access checks to audio-based and transcript-based draft creation.
- **FR-014**: The system MUST apply the same daily usage limit to audio-based and transcript-based draft creation.
- **FR-015**: Failed attempts caused by unsupported format, excessive duration, or unavailable transcription MUST NOT create a draft and MUST NOT create a debt.
- **FR-016**: The creditor MUST be able to retry voice draft creation or continue manual debt entry after any audio processing failure.
- **FR-017**: The system MUST delete original voice audio after successful transcription and MUST retain the resulting transcript with the draft for creditor review.
- **FR-018**: User-facing errors and status messages for recording, upload, transcription, draft extraction, access denial, and daily limits MUST be available in Arabic and English.
- **FR-019**: Voice draft creation MUST not expose any debt, profile, transcript, or voice-note data to users who are not authorized participants in the relevant create-debt flow.

### Key Entities *(include if feature involves data)*

- **Voice Debt Draft**: An editable proposed debt created from a transcript. Contains extracted debtor name as free text, amount, currency, due date, description, per-field confirmation status, confidence or unresolved-field indicators when available, and the raw transcript. It does not contain an auto-linked debtor profile.
- **Voice Note**: A recorded or uploaded audio input supplied by a creditor for draft creation. Includes format, duration, owner, temporary storage reference, and processing status. Original audio is deleted after successful transcription.
- **Transcript**: The text representation of spoken debt details. It may come from audio transcription or be submitted directly by a client.
- **AI Usage Record**: A countable draft-generation attempt associated with a creditor and date, used to enforce AI-tier daily limits.
- **Draft Field Resolution**: The status of each extracted debt field, indicating whether it is populated, missing, edited, or explicitly confirmed by the creditor before submission.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: At least 90% of clear Arabic and English demo voice notes under 60 seconds produce an editable draft with a raw transcript displayed to the creditor.
- **SC-002**: For clear demo inputs that mention debtor, amount, due date, and description, at least 85% of generated drafts populate all four fields without manual typing.
- **SC-003**: 100% of audio files longer than 60 seconds are rejected before draft extraction and before debt creation.
- **SC-004**: 100% of unsupported audio formats are rejected with a translated, user-friendly message.
- **SC-005**: 100% of ineligible or over-limit creditors are blocked from both audio-based and transcript-based draft creation.
- **SC-006**: A creditor can complete the primary voice-to-draft flow from starting recording/upload to seeing an editable draft in under 30 seconds for a 60-second-or-shorter demo note under normal local test conditions.
- **SC-007**: No automated test or manual acceptance scenario creates a debt until the creditor explicitly confirms or edits every extracted field and submits the reviewed draft.
- **SC-008**: The existing transcript-only draft path continues to pass its regression tests with no loss of returned draft fields.

## Assumptions

- Voice-to-debt draft creation is part of the paid AI tier and uses the same access rules and daily-limit model as other AI draft features.
- Creditors remain responsible for reviewing and confirming draft details before a debt is created.
- The create-debt form already has a manual entry path; this feature augments it rather than replacing it.
- Audio input is limited to one voice note per draft attempt for the MVP.
- The maximum audio duration for MVP is 60 seconds.
- Voice-note storage is temporary for successful transcriptions; the retained user-visible record is the transcript, not the original audio.
- Draft extraction from a direct transcript should behave the same as draft extraction from an audio-generated transcript.
- Currency inference relies on the creditor profile locale when currency is not spoken or confidently detected.
- Voice drafts do not perform profile matching from spoken debtor names; identity resolution stays in the existing creditor-confirmed debtor selection flow.
