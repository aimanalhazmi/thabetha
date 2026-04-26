# API Endpoints

All endpoints are prefixed with `/api/v1`.

## Health

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/health` | Service health check |

## Profiles

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/profiles/me` | Get or create current user profile |
| `PATCH` | `/profiles/me` | Update profile fields |
| `POST` | `/profiles/business-profile` | Create/update shop profile |
| `GET` | `/profiles/business-profile` | Get current user's shop profile |
| `GET` | `/profiles/me/trust-score-events` | View trust score audit events |

## QR

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/qr/current` | Get current valid QR token |
| `POST` | `/qr/rotate` | Generate a new QR token |
| `GET` | `/qr/resolve/{token}` | Resolve a valid QR token to a profile |

## Debts

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/debts` | Create a pending debt |
| `GET` | `/debts` | List debts visible to current user |
| `GET` | `/debts/{debt_id}` | Get debt details |
| `GET` | `/debts/{debt_id}/events` | Get debt audit history |
| `POST` | `/debts/{debt_id}/accept` | Debtor accepts debt |
| `POST` | `/debts/{debt_id}/reject` | Debtor rejects debt |
| `POST` | `/debts/{debt_id}/change-request` | Debtor requests changes |
| `POST` | `/debts/{debt_id}/mark-paid` | Debtor marks payment complete |
| `POST` | `/debts/{debt_id}/confirm-payment` | Creditor confirms receipt |
| `POST` | `/debts/{debt_id}/attachments` | Upload invoice or voice note |
| `GET` | `/debts/{debt_id}/attachments` | List debt attachments |

## Dashboards

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/dashboard/debtor` | Debtor totals, due-soon, overdue, trust score |
| `GET` | `/dashboard/creditor` | Creditor receivables, customers, alerts |

## Notifications

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/notifications` | List current user's notifications |
| `POST` | `/notifications/{notification_id}/read` | Mark notification as read |
| `PATCH` | `/notifications/preferences` | Set WhatsApp preference per merchant |

## Groups

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/groups` | Create friend/family group |
| `GET` | `/groups` | List accepted groups |
| `POST` | `/groups/{group_id}/invite` | Invite user to group |
| `POST` | `/groups/{group_id}/accept` | Accept group invitation |
| `GET` | `/groups/{group_id}/debts` | View group-visible debts |
| `POST` | `/groups/{group_id}/settlements` | Record pay-for-other settlement |

## AI

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/ai/debt-draft-from-voice` | Extract editable debt draft from transcript |
| `POST` | `/ai/merchant-chat` | Merchant summaries and recommendations |

