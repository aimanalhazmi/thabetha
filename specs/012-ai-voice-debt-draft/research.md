# Research: Voice-to-Debt Draft Polish

## Decision: Keep one endpoint with content-type dispatch

**Decision**: Evolve `POST /api/v1/ai/debt-draft-from-voice` to accept either JSON transcript input or multipart audio input. JSON keeps the existing transcript path; multipart accepts one audio file and optional client hints.

**Rationale**: The product feature is one user-facing capability: "create a debt draft from voice." Keeping one endpoint preserves the existing contract while allowing clients with their own STT to keep using transcript-only calls. Content-type dispatch is explicit and testable.

**Alternatives considered**:

- Add a second `/ai/debt-draft-from-audio` endpoint: clearer backend separation, but splits client behavior and duplicates gating/limits/contracts.
- Replace JSON with multipart only: breaks existing tests and clients that bring their own transcript.

## Decision: Provider interface around speech-to-text

**Decision**: Add a local speech-to-text provider interface with a real provider backed by OpenAI speech-to-text and a deterministic mock provider for tests.

**Rationale**: The implementation plan calls for multilingual Arabic/English transcription and mentions OpenAI Whisper. A provider boundary keeps the endpoint testable, lets the test suite run without network access, and gives a clean fallback if provider choice changes.

**Alternatives considered**:

- Call the provider directly from the router: simpler initially, but hard to test and harder to replace.
- Browser-only transcription: avoids backend audio handling, but fails the API-level audio requirement and gives inconsistent quality across clients.

## Decision: Shared transcript-to-draft service

**Decision**: Move the current regex stub into a `draft_extract` service and replace it with a schema-oriented transcript-to-draft pipeline shared by JSON and audio paths.

**Rationale**: Audio and transcript inputs must produce identical draft semantics: no debtor profile matching, currency inference from creditor locale, per-field confirmation state, raw transcript returned, and no debt creation. One service prevents drift between input modes.

**Alternatives considered**:

- Keep the existing router-local regex extraction: too limited for Arabic/English phrase variation and difficult to reuse.
- Separate extraction logic for audio vs transcript: duplicates validation and increases test matrix size.

## Decision: Temporary audio retention only

**Decision**: Accepted audio is stored only as needed for transcription, then deleted after successful transcription. The transcript is retained with the draft response. Failed transcription may retain temporary audio only within short-lived operational cleanup rules and never as a long-lived user attachment.

**Rationale**: The clarification selected minimal voice-data retention. Voice recordings are more sensitive than text drafts; retaining only transcript supports review while reducing privacy risk.

**Alternatives considered**:

- Retain audio like a normal attachment: simpler storage lifecycle but conflicts with the privacy clarification.
- Delete transcript too: stronger privacy but conflicts with the requirement to show what was heard.

## Decision: Daily limit is one countable successful draft attempt

**Decision**: Count one daily AI usage unit when a draft attempt reaches transcript-to-draft processing and returns a draft. Reject unsupported formats, over-duration audio, unauthenticated/unauthorized users, and provider-unavailable failures without counting.

**Rationale**: This matches the spec: invalid audio should not count, and successful JSON/audio draft attempts should share the same quota. Counting after successful draft creation is easiest for users to understand and tests to verify.

**Alternatives considered**:

- Count all attempts, including invalid uploads: discourages retry after correctable user mistakes.
- Count provider attempts before draft extraction: penalizes users for provider outages.

## Decision: Use creditor profile locale for missing currency

**Decision**: If the transcript contains an amount but no currency, infer currency from the creditor profile locale and mark it as requiring creditor confirmation.

**Rationale**: This records the selected clarification and avoids hardcoding SAR in every case. The create-debt form already exposes currency as editable, so confirmation remains explicit.

**Alternatives considered**:

- Default to SAR: locally convenient, but ignores the clarification.
- Leave blank: safer but adds friction for common voice notes.

## Decision: No profile matching from spoken debtor names

**Decision**: Extract debtor name as free text only. Do not search or link profiles from the voice draft. Existing QR/manual debtor resolution remains the only identity path.

**Rationale**: Financial identity mistakes are high risk. Free-text extraction is useful for draft filling, while linking stays with explicit user action.

**Alternatives considered**:

- Auto-link exact matches: risky for duplicate names and transliteration variants.
- Suggest matches: more useful, but still introduces identity UI and matching policy beyond this phase.

## Decision: Backend tests are mandatory; frontend tests are conditional

**Decision**: Add `FastAPI.TestClient` tests with `REPOSITORY_TYPE=memory` for gating, JSON transcript, multipart audio, daily limit, deletion semantics, field confirmation schema, currency fallback, and no profile matching. Add frontend tests only if the existing Vitest harness is present; otherwise document manual UI verification in quickstart.

**Rationale**: The constitution explicitly requires FastAPI TestClient tests for auth-affecting behavior. The repository has mature backend tests today; frontend test infrastructure may be present from Phase 5 but should not block this planning artifact.

**Alternatives considered**:

- Manual-only verification: insufficient for AI gating and usage limit regressions.
- Broad E2E automation: useful later, but too large for this medium-sized phase.
