# Contract: Voice-to-Debt Draft

Base path: `/api/v1/ai/debt-draft-from-voice`

All requests require an authenticated creditor. The endpoint returns `403` when `profile.ai_enabled` is false.

## JSON Transcript Request

```http
POST /api/v1/ai/debt-draft-from-voice
Content-Type: application/json
Authorization: Bearer <token>
```

```json
{
  "transcript": "على Ahmed 25 groceries due 2026-05-01",
  "default_currency": "SAR"
}
```

Notes:

- `default_currency` remains accepted for backward compatibility.
- If no currency is detected in the transcript, the response currency is inferred from the creditor profile locale.

## Multipart Audio Request

```http
POST /api/v1/ai/debt-draft-from-voice
Content-Type: multipart/form-data
Authorization: Bearer <token>
```

Fields:

| Field | Required | Description |
|-------|----------|-------------|
| `audio` | Yes | One webm, mp3, wav, or m4a file |
| `client_duration_seconds` | No | Client-measured duration; values above 60 are rejected before transcription |
| `hint` | No | Optional short creditor hint |

## Success Response

Status: `200 OK`

```json
{
  "debtor_name": "Ahmed",
  "amount": "25",
  "currency": "SAR",
  "description": "groceries",
  "due_date": "2026-05-01",
  "confidence": 0.84,
  "raw_transcript": "على Ahmed 25 groceries due 2026-05-01",
  "field_confirmations": {
    "debtor_name": "extracted_unconfirmed",
    "amount": "extracted_unconfirmed",
    "currency": "extracted_unconfirmed",
    "description": "extracted_unconfirmed",
    "due_date": "extracted_unconfirmed"
  }
}
```

Rules:

- `debtor_name` is free text only. The response must not include a debtor profile id or match metadata.
- Every extracted field starts as `extracted_unconfirmed`.
- Missing fields use `null` values and `missing` confirmation status.
- The response creates no debt. Clients submit through the existing create-debt contract only after confirmation/editing.
- Audio input returns the raw transcript and deletes original audio after successful transcription.

## Error Responses

### AI tier disabled

Status: `403 Forbidden`

```json
{
  "detail": {
    "code": "ai_subscription_required",
    "message": "AI features require an active AI subscription"
  }
}
```

### Daily limit reached

Status: `429 Too Many Requests`

Header: `Retry-After: <seconds>`

```json
{
  "detail": {
    "code": "ai_daily_limit_reached",
    "message": "Daily AI draft limit reached"
  }
}
```

### Unsupported audio format

Status: `415 Unsupported Media Type`

```json
{
  "detail": {
    "code": "unsupported_audio_type",
    "message": "Unsupported audio format"
  }
}
```

### Audio too long

Status: `413 Payload Too Large`

```json
{
  "detail": {
    "code": "audio_too_long",
    "message": "Voice notes must be 60 seconds or shorter"
  }
}
```

### Transcription unavailable or unintelligible

Status: `422 Unprocessable Entity`

```json
{
  "detail": {
    "code": "transcription_failed",
    "message": "Could not transcribe the audio"
  }
}
```

## Compatibility Requirements

- Existing JSON transcript tests continue to pass after schema additions.
- Clients that ignore `field_confirmations` can still read the original fields, but the create-debt UI must enforce confirmation before submission.
- Errors surfaced in the frontend must map to localized AR/EN strings rather than raw backend messages.
