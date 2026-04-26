# Database Schema Documentation

The production target is Supabase Postgres with Row Level Security. The initial migration is in `supabase/migrations/001_initial_schema.sql`.

## Tables

| Table | Purpose |
|---|---|
| `profiles` | App-specific user data linked to Supabase Auth users |
| `business_profiles` | Shop/project data for business accounts |
| `qr_tokens` | Rotating QR identity tokens with expiry |
| `debts` | Main debt record and lifecycle status |
| `debt_events` | Audit trail for debt lifecycle changes |
| `payment_confirmations` | Debtor payment request and creditor confirmation |
| `attachments` | Invoice images and voice notes stored in Supabase Storage |
| `notifications` | In-app notification records and WhatsApp delivery attempts |
| `merchant_notification_preferences` | Per debtor/per merchant WhatsApp opt-out |
| `trust_score_events` | Audited trust score changes |
| `groups` | Friend/family settlement groups |
| `group_members` | Group membership and explicit consent status |
| `group_settlements` | Pay-for-other settlement records |

## Core Statuses

| Domain | Values |
|---|---|
| Debt | `pending_confirmation`, `active`, `overdue`, `payment_pending_confirmation`, `paid`, `rejected`, `change_requested` |
| Account | `individual`, `business` |
| Attachment | `invoice`, `voice_note`, `other` |
| Group member | `pending`, `accepted` |

## Privacy Rules

| Data | Access Rule |
|---|---|
| Profile | User can read/update own profile |
| Business profile | Owner can read/write |
| Debt | Creditor, debtor, or accepted group member can read |
| Debt update | Creditor/debtor depending on lifecycle action |
| Notifications | User can access own notifications |
| Groups | Accepted members can read group context |
| Trust score events | User can read own audit events |

