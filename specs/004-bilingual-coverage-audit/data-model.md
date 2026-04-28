# Phase 1 — Data Model: Bilingual Coverage Audit (AR/EN)

The audit is mostly tooling; the only persistent-data change is one new column on `public.profiles`. The other two entities (Locale state, Audit finding) are spec entities with no DB representation.

---

## Entity 1 — `public.profiles.preferred_language` (new column)

| Field | Type | Constraints | Notes |
|---|---|---|---|
| `preferred_language` | `text` | `not null`, `default 'ar'`, `check (preferred_language in ('ar','en'))` | Owns the user's locale across devices. Migration: `008_preferred_language.sql`. |

**Migration sketch** (illustrative; final SQL lands during implementation):

```sql
-- supabase/migrations/008_preferred_language.sql
alter table public.profiles
  add column preferred_language text not null default 'ar'
  check (preferred_language in ('ar', 'en'));

-- Backfill: every existing row defaults to 'ar' via the column default.

create or replace function public.handle_new_user()
returns trigger language plpgsql security definer as $$
begin
  insert into public.profiles (id, name, phone, email, account_type, preferred_language)
  values (
    new.id,
    coalesce(new.raw_user_meta_data->>'name', ''),
    coalesce(new.raw_user_meta_data->>'phone', ''),
    new.email,
    coalesce((new.raw_user_meta_data->>'account_type')::public.account_type, 'debtor'),
    coalesce(new.raw_user_meta_data->>'preferred_language', 'ar')
  );
  return new;
end;
$$;
```

**RLS impact**: none. Existing `profiles` policies (own-row read/update from migration 007) cover the new column.

**Backend schema mirror** (`backend/app/schemas/domain.py`):

```python
class Profile(BaseModel):
    # ... existing fields ...
    preferred_language: Literal["ar", "en"] = "ar"
```

**Frontend type mirror** (`frontend/src/lib/types.ts`):

```ts
export type Language = 'ar' | 'en';

export interface Profile {
  // ... existing fields ...
  preferred_language: Language;
}
```

These three updates **must** land in the same PR per Constitution principle VII.

---

## Entity 2 — Translation key (existing; no DB representation)

Lives entirely in `frontend/src/lib/i18n.ts`. Properties:

- `key` — string identifier referenced by code (e.g., `'createDebt'`).
- `ar` — Arabic value.
- `en` — English value.

**Invariant** (FR-010, SC-002): the set of `ar` keys equals the set of `en` keys. Enforced at runtime by the existing TypeScript union-type definition (`TranslationKey`) and at test time by `i18n-key-parity.test.ts`.

---

## Entity 3 — Client-side Locale state

Lives in `AuthContext` and `localStorage`; no DB row beyond `preferred_language`.

| Source (in priority order) | Read at | Written when |
|---|---|---|
| `profile.preferred_language` | Sign-in, sign-up, profile refresh, app boot for authenticated users | User toggles language while signed in (PATCH profile) |
| `localStorage['thabetha.locale']` | App boot for anonymous visitors | User toggles language at any time (always; gives signed-in users a working fallback if the PATCH fails) |
| `'ar'` literal default | When neither is set | Never — fallback only |

**Document side effects** (set in `App.tsx` on every locale change):

- `document.documentElement.lang = locale`
- `document.documentElement.dir = locale === 'ar' ? 'rtl' : 'ltr'`

**Synchronization rule**: when a user signs in, profile's `preferred_language` overrides any existing `localStorage` value (the signed-in preference wins). When a signed-in user signs out, the locale stays as it was; `localStorage` retains the last value as the fallback for the next anonymous visit.

---

## Entity 4 — Audit finding (no DB representation; planning artifact)

Tracked in `specs/004-bilingual-coverage-audit/findings.md` as a Markdown table. Schema:

| Field | Values |
|---|---|
| `id` | Sequential within the file (`F-001`, `F-002`, …). |
| `surface` | File path or page identifier (e.g., `frontend/src/pages/DashboardPage.tsx:42`, `<html dir>`, `OG meta on AuthPage`). |
| `category` | `literal` \| `missing-key` \| `direction` \| `bidi` \| `metadata` \| `backend-leak` |
| `severity` | `Blocker` \| `Major` \| `Minor` (per Q4 / spec FR-009/FR-009a) |
| `owner` | Person responsible for resolution. **Required** for `backend-leak` per FR-015. |
| `status` | `open` \| `fixed` \| `filed` (used for `backend-leak`) \| `wontfix` |
| `link` | URL to fix PR or defect ticket. |

**Closure invariants** (per FR-009a / SC-009): at audit close, the file MUST contain zero `Blocker`/`Major` rows with status `open`, and every `backend-leak` row MUST have a non-empty `owner` and `link` and status `filed`.
