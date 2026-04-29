# Database Schema — Claude Handoff Reference

All tables live in the `public` schema with RLS enabled. Migrations are applied in order from `supabase/migrations/`.

## Core Tables

| Table | Key columns | Notes |
|---|---|---|
| `profiles` | `id`, `commitment_score` (0–100, default 50), `groups_enabled` (bool) | One row per auth user. |
| `debts` | `id`, `creditor_id`, `debtor_id`, `amount`, `currency`, `status`, `group_id`, `reminder_dates date[]` | 7-state lifecycle (see `docs/debt-lifecycle.md`). |
| `debt_events` | `debt_id`, `event_type`, `actor_id`, `metadata jsonb` | Full audit trail. |
| `commitment_score_events` | `debt_id`, `proposal_id`, `event_type`, `delta`, `reason`, `reminder_date` | Idempotency by `(debt_id, reminder_date)` for reminder penalties; by `(debt_id, proposal_id) WHERE reason='settlement_neutral'` for group-settlement events. |
| `notifications` | `user_id`, `notification_type`, `title`, `body`, `read`, `debt_id` | In-app only; WhatsApp is mock. |

## Groups Tables (added in 008)

| Table | Key columns | Notes |
|---|---|---|
| `groups` | `id`, `name`, `owner_id`, `updated_at` | |
| `group_members` | `group_id`, `user_id`, `status` (`invited`/`accepted`/`removed`/`left`) | Partial-unique index for live membership. |
| `group_events` | `group_id`, `event_type`, `actor_id`, `payload jsonb` | Event type includes the six settlement lifecycle events (added in 012). |

## Group Settlement Tables (added in 009 — migration 012)

| Table | Key columns | Notes |
|---|---|---|
| `group_settlement_proposals` | `id`, `group_id`, `proposed_by`, `currency`, `snapshot jsonb`, `transfers jsonb`, `status` (`open`/`rejected`/`expired`/`settlement_failed`/`settled`), `failure_reason`, `expires_at`, `resolved_at`, `reminder_sent_at` | Partial-unique index `one_open_proposal_per_group` on `(group_id) WHERE status='open'`. |
| `group_settlement_confirmations` | `proposal_id`, `user_id`, `status` (`pending`/`confirmed`/`rejected`), `responded_at` | Only required parties (payers + receivers) get a row — observers do not. |

## New Enums (012)

- `settlement_proposal_status`: `open`, `rejected`, `expired`, `settlement_failed`, `settled`
- `settlement_confirmation_status`: `pending`, `confirmed`, `rejected`
