# Database Schema

State of the Supabase Postgres database after all migrations (`supabase/migrations/001..007_*.sql`) are applied. Use `supabase db reset` locally to recreate from scratch.

## Migration ledger

| File | Purpose |
|---|---|
| `001_initial_schema.sql` | Initial enums, `profiles`, `business_profiles`, `merchant_notification_preferences`, `debts`, `qr_tokens`, `groups`, `group_members`, `debt_events`, `commitment_score_events` (created as `trust_score_events`), seed RLS, `handle_new_user` trigger, legacy bucket `thabetha-attachments`. |
| `002_commitment_and_lifecycle.sql` | Rename `trust_score → commitment_score` (column + table); expand `debt_status` enum; reset default; recreate `handle_new_user`; create canonical buckets `receipts` + `voice-notes`. |
| `003_storage_policies.sql` | RLS for storage objects in `receipts` / `voice-notes`. Helper `public.user_is_debt_party(uuid)`. |
| `004_fix_debt_status_enum.sql` | Idempotent enum-add safety net + legacy value migration. |
| `005_repository_alignment.sql` | Adds `notifications`, `payment_confirmations`, `attachments`, `group_settlements`. RLS for all four. |
| `006_lifecycle_and_reminders.sql` | Removes `rejected` from `debt_status` (rebuilds enum). Adds `debts.reminder_dates date[]` and `commitment_score_events.reminder_date` + partial unique index `commitment_score_events_missed_reminder_uniq`. |
| `007_business_profile_rls.sql` | Adds owner-scoped policy on `business_profiles` (RLS was enabled in 001 without a policy, blocking access). |

## Enums

| Type | Values |
|---|---|
| `account_type` | `creditor`, `debtor`, `both`, `business` |
| `debt_status` | `pending_confirmation`, `active`, `edit_requested`, `overdue`, `payment_pending_confirmation`, `paid`, `cancelled` (no `rejected` after 006) |
| `attachment_type` | `invoice`, `voice_note`, `other` |
| `group_member_status` | `pending`, `accepted` |

## Tables

### `public.profiles`
1:1 with `auth.users`. Auto-populated via `handle_new_user()` trigger.

| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | FK → `auth.users(id)` ON DELETE CASCADE |
| `name` | text NOT NULL | |
| `phone` | text NOT NULL DEFAULT `''` | |
| `email` | text | |
| `account_type` | `account_type` NOT NULL DEFAULT `'debtor'` | |
| `tax_id` | text | |
| `commercial_registration` | text | |
| `whatsapp_enabled` | boolean NOT NULL DEFAULT `true` | Global toggle |
| `ai_enabled` | boolean NOT NULL DEFAULT `false` | Hard-gates `/api/v1/ai/*` |
| `commitment_score` | int NOT NULL DEFAULT `50`, CHECK between 0 and 100 | |
| `created_at`, `updated_at` | timestamptz NOT NULL DEFAULT `now()` | |

RLS: `auth.uid() = id` (full access).

### `public.business_profiles`
1:1 with profile (UNIQUE on `owner_id`).

| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK DEFAULT `gen_random_uuid()` | |
| `owner_id` | uuid NOT NULL UNIQUE | FK → `profiles(id)` ON DELETE CASCADE |
| `shop_name`, `activity_type`, `location`, `description` | text | |
| `created_at`, `updated_at` | timestamptz NOT NULL DEFAULT `now()` | |

RLS (added in 007): `auth.uid() = owner_id` (USING + WITH CHECK).

### `public.merchant_notification_preferences`
Composite-keyed per-creditor WhatsApp opt-out for a given debtor.

| Column | Type | Notes |
|---|---|---|
| `user_id` | uuid | FK → `profiles(id)` ON DELETE CASCADE — debtor |
| `merchant_id` | uuid | FK → `profiles(id)` ON DELETE CASCADE — creditor |
| `whatsapp_enabled` | boolean NOT NULL DEFAULT `true` | |
| `updated_at` | timestamptz NOT NULL DEFAULT `now()` | |

PK `(user_id, merchant_id)`.

### `public.debts`

| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK DEFAULT `gen_random_uuid()` | |
| `creditor_id` | uuid NOT NULL | FK → `profiles(id)` ON DELETE CASCADE |
| `debtor_id` | uuid | FK → `profiles(id)` ON DELETE SET NULL — nullable when debtor not yet known |
| `debtor_name` | text NOT NULL | Always populated |
| `amount` | numeric(12,2) NOT NULL CHECK > 0 | |
| `currency` | char(3) NOT NULL DEFAULT `'SAR'` | |
| `description` | text NOT NULL | |
| `due_date` | date NOT NULL | |
| `reminder_dates` | date[] NOT NULL DEFAULT `'{}'` | Added in 006 |
| `status` | `debt_status` NOT NULL DEFAULT `'pending_confirmation'` | |
| `invoice_url` | text | Legacy single-attachment path |
| `notes` | text | |
| `group_id` | uuid | Soft reference to `groups(id)` |
| `created_at`, `updated_at`, `confirmed_at`, `paid_at` | timestamptz | |

RLS: `auth.uid() = creditor_id OR auth.uid() = debtor_id`.

### `public.debt_events`
Audit trail row for every transition.

| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `debt_id` | uuid NOT NULL | FK → `debts(id)` ON DELETE CASCADE |
| `actor_id` | uuid | FK → `profiles(id)` ON DELETE SET NULL |
| `event_type` | text NOT NULL | Free-form string, mirrors lifecycle action names |
| `message` | text | |
| `metadata` | jsonb NOT NULL DEFAULT `'{}'` | |
| `created_at` | timestamptz NOT NULL DEFAULT `now()` | |

### `public.commitment_score_events`
Originally `trust_score_events`. Renamed in 002.

| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `user_id` | uuid NOT NULL | FK → `profiles(id)` ON DELETE CASCADE |
| `delta` | int NOT NULL | Signed score change |
| `score_after` | int NOT NULL CHECK between 0 and 100 | |
| `reason` | text NOT NULL | e.g. `paid_early`, `paid_on_time`, `paid_late`, `missed_reminder`, `debt_overdue` |
| `debt_id` | uuid | Soft reference |
| `reminder_date` | date | Added in 006 |
| `created_at` | timestamptz | |

Index: `commitment_score_events_missed_reminder_uniq` UNIQUE on `(debt_id, reminder_date) WHERE reason = 'missed_reminder'` — enforces idempotent missed-reminder penalties.

RLS: `auth.uid() = user_id`.

### `public.qr_tokens`

| Column | Type | Notes |
|---|---|---|
| `token` | uuid PK DEFAULT `gen_random_uuid()` | The token itself |
| `user_id` | uuid NOT NULL | FK → `profiles(id)` ON DELETE CASCADE |
| `expires_at` | timestamptz NOT NULL | TTL ~10 min |
| `created_at` | timestamptz NOT NULL | |

### `public.groups`, `public.group_members`, `public.group_settlements`
Standard ownership-and-membership shape. `group_members` has `(group_id, user_id)` UNIQUE; status is `pending` until `accepted_at`. `group_settlements` is RLS-scoped to accepted members of the group.

### `public.notifications`

| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `user_id` | uuid NOT NULL | FK → `profiles(id)` ON DELETE CASCADE |
| `notification_type` | text NOT NULL | Mirrors `NotificationType` enum |
| `title`, `body` | text NOT NULL | |
| `debt_id` | uuid | FK → `debts(id)` ON DELETE CASCADE |
| `whatsapp_attempted` | boolean NOT NULL DEFAULT `true` | Mock for now |
| `read_at` | timestamptz | |
| `created_at` | timestamptz | |

Index: `notifications_user_created_idx` on `(user_id, created_at desc)`.
RLS: select + update where `auth.uid() = user_id`.

### `public.payment_confirmations`

| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `debt_id` | uuid NOT NULL | FK → `debts(id)` ON DELETE CASCADE |
| `debtor_id` | uuid NOT NULL | FK → `profiles(id)` |
| `creditor_id` | uuid NOT NULL | FK → `profiles(id)` |
| `status` | text NOT NULL | |
| `note` | text | |
| `requested_at`, `confirmed_at` | timestamptz | |

Index: `payment_confirmations_debt_idx` on `(debt_id)`.
RLS: parties (`debtor_id` or `creditor_id`).

### `public.attachments`

| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `debt_id` | uuid NOT NULL | FK → `debts(id)` ON DELETE CASCADE |
| `uploader_id` | uuid NOT NULL | FK → `profiles(id)` |
| `attachment_type` | text NOT NULL | |
| `file_name`, `storage_path` | text NOT NULL | |
| `content_type`, `public_url` | text | |
| `created_at` | timestamptz | |

RLS: party-of-debt via `EXISTS` subquery on `debts`.

## Storage

Three buckets:

| Bucket | Purpose | Created |
|---|---|---|
| `thabetha-attachments` | Legacy generic attachments | 001 (still present) |
| `receipts` | Invoice photos / receipts | 002 |
| `voice-notes` | Optional voice memos | 002 |

Path convention: `<bucket>/<debt_id>/<uuid>-<filename>`. Storage RLS in 003 keys access on the first path segment being a `debts.id` the caller is creditor/debtor of (`public.user_is_debt_party(uuid)` helper).

## Triggers

- `on_auth_user_created` (after insert on `auth.users`) → `handle_new_user()` inserts a `profiles` row using `raw_user_meta_data->>{name,phone,account_type}`.
