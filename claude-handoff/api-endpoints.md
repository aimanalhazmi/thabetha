# API Endpoints — Claude Handoff Reference

All routes are mounted under `/api/v1`. Auth via `Authorization: Bearer <supabase_jwt>` (or `x-demo-user-id` in non-production for tests).

## Auth (`/api/v1/auth/`)

| Method | Path | Description |
|---|---|---|
| POST | `/auth/signup` | Proxy to Supabase Auth signup. |
| POST | `/auth/login` | Proxy to Supabase Auth token. |
| POST | `/auth/logout` | Proxy to Supabase Auth logout. |

## Profiles (`/api/v1/profiles/`)

| Method | Path | Description |
|---|---|---|
| GET | `/profiles/me` | Get own profile. |
| PATCH | `/profiles/me` | Update display name / avatar. |
| GET | `/profiles/qr` | Generate a QR token for the caller. |
| GET | `/profiles/resolve-qr/{token}` | Resolve a QR token to a profile preview. |

## Debts (`/api/v1/debts/`)

| Method | Path | Description |
|---|---|---|
| POST | `/debts` | Create a debt (creditor). |
| GET | `/debts` | List debts where caller is creditor or debtor. |
| GET | `/debts/{id}` | Get single debt. |
| POST | `/debts/{id}/accept` | Debtor accepts. |
| POST | `/debts/{id}/request-edit` | Debtor requests amendment. |
| POST | `/debts/{id}/approve-edit` | Creditor approves edit. |
| POST | `/debts/{id}/reject-edit` | Creditor rejects edit (original terms). |
| POST | `/debts/{id}/mark-paid` | Debtor marks as paid. |
| POST | `/debts/{id}/confirm-payment` | Creditor confirms receipt. |
| POST | `/debts/{id}/cancel` | Creditor cancels (pre-binding only). |

## Notifications (`/api/v1/notifications/`)

| Method | Path | Description |
|---|---|---|
| GET | `/notifications` | List caller's notifications. |
| POST | `/notifications/{id}/read` | Mark notification read. |

## Groups (`/api/v1/groups/`)

| Method | Path | Description |
|---|---|---|
| POST | `/groups` | Create a group (caller becomes owner). |
| GET | `/groups` | List groups where caller is an accepted member. |
| GET | `/groups/{id}` | Get group detail + member list. |
| POST | `/groups/{id}/invite` | Invite a user by `user_id`. |
| POST | `/groups/{id}/accept` | Accept a group invite. |
| POST | `/groups/{id}/leave` | Leave group. 409 `LeaveBlockedByOpenProposal` if the caller is in an open proposal's transfer list. |
| POST | `/groups/{id}/rename` | Owner renames group. |
| POST | `/groups/{id}/transfer-ownership` | Owner transfers ownership. |
| POST | `/groups/{id}/remove-member` | Owner removes a member. |

### Group Settlement Proposals (`/api/v1/groups/{group_id}/settlement-proposals/`)

Added in feature 009. All endpoints require the caller to be an accepted member.

| Method | Path | Status codes | Description |
|---|---|---|---|
| POST | `/{group_id}/settlement-proposals` | 201 / 409 | Create a settlement proposal. 409 codes: `OpenProposalExists`, `MixedCurrency`, `NothingToSettle`. |
| GET | `/{group_id}/settlement-proposals` | 200 | List proposals for the group (optional `?status=` filter). |
| GET | `/{group_id}/settlement-proposals/{pid}` | 200 / 404 | Get a single proposal. Triggers lazy expiry/reminder sweep. `snapshot` field is null for observers. |
| POST | `/{group_id}/settlement-proposals/{pid}/confirm` | 200 / 403 / 409 | Required party confirms. 403: `NotARequiredParty`. 409: `ProposalNotOpen`, `AlreadyResponded`. |
| POST | `/{group_id}/settlement-proposals/{pid}/reject` | 200 / 403 / 409 | Required party rejects. Same error codes as confirm. |
