# Contract — Profile locale read/write

This contract covers reading and updating the authenticated user's preferred language. It extends the existing profile API; no new resource is introduced.

## Read — included in existing profile fetch

`GET /api/v1/profiles/me` (existing endpoint) returns the user's profile row, now including:

```json
{
  "id": "<uuid>",
  "name": "...",
  "phone": "...",
  "email": "...",
  "account_type": "creditor" | "debtor" | "both",
  "preferred_language": "ar" | "en",
  "...": "other existing fields"
}
```

**Default**: `"ar"` for any row that has not been explicitly updated (column default, applied to existing rows by the migration).

**Authorization**: existing — caller must be authenticated; RLS restricts to `auth.uid() = id`.

## Update — `PATCH /api/v1/profiles/me`

Either extend the existing profile update endpoint to accept the new field, or add a dedicated endpoint if no general profile-update route exists. The contract for this field:

**Request body** (additive; other existing fields remain accepted):

```json
{
  "preferred_language": "ar" | "en"
}
```

**Validation**:

- Value must be one of the two literals `"ar"` or `"en"`. Anything else → `422 Unprocessable Entity` with a Pydantic validation error citing the field.
- Body may include other profile fields; the contract for those is unchanged.

**Responses**:

- `200 OK` — returns the updated profile (same shape as `GET`).
- `401 Unauthorized` — no/invalid JWT.
- `422` — invalid `preferred_language` value.

**Side effects**:

- `public.profiles.preferred_language` is updated atomically.
- The frontend immediately re-renders with the new locale and direction (via `AuthContext` → `App.tsx`'s `<html lang dir>` effect).
- No `debt_events` or commitment-score effects (this is purely a UI preference).

**Idempotency**: setting the same value is a no-op-equivalent (returns 200 with unchanged value).

## Anonymous visitors (no contract)

Anonymous visitors have no server-side preference. Their locale is read from and written to `localStorage['thabetha.locale']` only. On sign-in, the profile's `preferred_language` overrides the local value.

## Test surfaces

Backend tests must cover:

1. `GET /profiles/me` returns `preferred_language` for an existing-row user (default `"ar"`).
2. `PATCH /profiles/me { "preferred_language": "en" }` returns 200 with the new value, and a follow-up `GET` returns `"en"`.
3. `PATCH /profiles/me { "preferred_language": "fr" }` returns 422.
4. `PATCH /profiles/me { "preferred_language": "ar" }` from a different user does not affect the first user's row (RLS / handler-level isolation).
5. Migration `008_preferred_language.sql` applies cleanly under `REPOSITORY_TYPE=postgres` and existing rows pick up the `'ar'` default.
