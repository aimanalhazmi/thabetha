# Data Model: Voice-to-Debt Draft Polish

## VoiceDebtDraftRequest

Input model for transcript-only draft creation.

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `transcript` | string | Yes | Non-empty after trim |
| `default_currency` | string | No | Backward-compatible input accepted, but missing-currency behavior uses creditor profile locale when currency is not detected |

Relationships:

- Authenticated creditor profile supplies `ai_enabled` and `preferred_language`.
- Produces a `VoiceDebtDraftOut`.

## VoiceDebtDraftAudioRequest

Multipart input contract for audio-based draft creation.

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `audio` | file | Yes | Content type/extension must be webm, mp3, wav, or m4a |
| `client_duration_seconds` | number | No | If present, must be <= 60 before upload/transcription proceeds |
| `hint` | string | No | Optional short text hint; must not replace transcript review |

Relationships:

- Creates a temporary `VoiceNoteProcessing` record/state during transcription.
- Produces a `Transcript`, then a `VoiceDebtDraftOut`.

## VoiceDebtDraftOut

Editable draft returned to clients. It is not a debt and must not create any `debt_events`.

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `debtor_name` | string or null | No | Free text only; never auto-linked to a profile |
| `amount` | decimal string or null | No | Positive when present |
| `currency` | string | Yes | ISO-style 3-character uppercase code; inferred from creditor profile locale when not detected |
| `description` | string or null | No | Derived from transcript or summary of spoken purpose |
| `due_date` | date string or null | No | ISO date when present |
| `confidence` | number | Yes | 0..1 aggregate compatibility field for existing clients |
| `raw_transcript` | string | Yes | Transcript used for extraction |
| `field_confirmations` | object | Yes | Per-field status for `debtor_name`, `amount`, `currency`, `description`, `due_date` |

Field confirmation values:

- `extracted_unconfirmed`: System extracted a value and the creditor must confirm or edit it.
- `missing`: No usable value was extracted; creditor must enter it when required for debt creation.
- `confirmed`: Creditor explicitly accepted the value.
- `edited`: Creditor changed the value.

State transition:

```text
draft_generated
  -> field_confirmed / field_edited per extracted field
  -> ready_for_create when all extracted fields are confirmed or edited and all required DebtCreate fields are present
  -> submitted through existing create-debt flow
  -> discarded by user action or page reset
```

## VoiceNoteProcessing

Temporary server-side audio processing state.

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `id` | string | Yes | Internal unique id |
| `owner_id` | string | Yes | Authenticated creditor id |
| `file_name` | string | Yes | Original or generated safe filename |
| `content_type` | string | Yes | Allowed audio type |
| `duration_seconds` | number or null | No | Must be <= 60 when known |
| `temporary_storage_path` | string or null | No | Private `voice-notes` path while processing |
| `status` | enum | Yes | `received`, `transcribing`, `transcribed`, `failed`, `deleted` |
| `created_at` | datetime | Yes | Server time |
| `deleted_at` | datetime or null | No | Set after successful transcription deletes audio |

Rules:

- Original audio must be deleted after successful transcription.
- Temporary paths must never be returned to clients as signed URLs.
- Failed processing must not turn temporary audio into a normal user attachment.

## Transcript

Text used for draft extraction.

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `raw_transcript` | string | Yes | Non-empty for draft extraction |
| `source` | enum | Yes | `audio` or `client_transcript` |
| `language_hint` | string or null | No | May be inferred; user does not choose language manually |

Rules:

- Arabic, English, and mixed Arabic/English text are accepted.
- Transcript is returned for creditor review.

## AIUsageRecord

Per-user daily usage accounting for AI draft generation.

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `user_id` | string | Yes | Authenticated creditor id |
| `usage_date` | date | Yes | Calendar day in server time |
| `feature` | string | Yes | `voice_debt_draft` |
| `count` | integer | Yes | Non-negative |
| `limit` | integer | Yes | Configured daily limit |
| `updated_at` | datetime | Yes | Server time |

Rules:

- JSON transcript and audio draft attempts share the same limit.
- Unsupported format, over-duration audio, ineligible users, and failed transcription do not increment count.
- Successful draft responses increment exactly once.

## Existing Entities Touched

### Profile

- Uses `ai_enabled` for AI-tier gating.
- Uses `preferred_language` to infer missing currency.

### DebtCreate

- Receives values only after the creditor confirms/edits extracted fields and submits through the existing create-debt flow.
- Voice drafts do not add new debt states or bypass debtor confirmation.
