# Quickstart: Voice-to-Debt Draft Polish

## Prerequisites

- Backend dependencies installed.
- Frontend dependencies installed.
- `REPOSITORY_TYPE=memory` for fast local tests.
- AI provider can be mocked locally. Real provider usage requires `OPENAI_API_KEY`.

## Backend Verification

Run the focused backend tests:

```bash
cd backend
REPOSITORY_TYPE=memory pytest tests/test_ai_voice_debt_draft.py
```

Expected coverage:

- `ai_enabled=false` returns 403.
- JSON transcript path still returns a draft and raw transcript.
- Multipart audio path calls the mock transcription provider and returns the same draft shape.
- Audio over 60 seconds is rejected before draft extraction.
- Unsupported audio type is rejected.
- Successful transcription deletes original audio.
- Daily limit returns 429 with `Retry-After`.
- Extracted debtor names are not profile-matched.
- Missing currency is inferred from creditor profile locale.

Run the broader backend regression suite:

```bash
cd backend
REPOSITORY_TYPE=memory pytest
```

## Frontend Verification

Start the app stack as usual, then sign in as a creditor with AI enabled.

Manual flow:

1. Open the create-debt page.
2. Record or upload a short Arabic voice note that includes debtor name, amount, and due date.
3. Verify an editable draft appears with raw transcript.
4. Verify every extracted field requires confirmation or editing before the create button can submit.
5. Verify the debtor name remains free text and no profile id is silently selected.
6. Submit only after resolving the debtor through the normal manual or QR flow.
7. Repeat with a direct transcript request and verify the same draft behavior.
8. Try unsupported audio and over-60-second audio; verify translated errors.
9. Switch locale and verify all new UI strings render in Arabic and English.

If frontend tests exist for this surface, run the focused suite:

```bash
cd frontend
npm test -- voice-debt-draft
```

## Contract Check

Use the contract in [contracts/voice-debt-draft.md](./contracts/voice-debt-draft.md) as the acceptance reference for response shape and error codes. The endpoint must support both:

- `Content-Type: application/json` with `transcript`
- `Content-Type: multipart/form-data` with `audio`

## Storage/Privacy Check

For successful audio transcription:

- No signed voice-note URL is returned.
- Temporary audio is deleted after transcription.
- The retained review artifact is `raw_transcript`.
