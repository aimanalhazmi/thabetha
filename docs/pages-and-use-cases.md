# Pages & Use Cases

Page → actor → use case mapping for **Thabetha / ثبتها**. Use cases reference the canonical UC numbers in [`docs/product-requirements.md`](./product-requirements.md).

## Use case → actor split

| UC | Title | Creditor | Debtor | Shared |
|---|---|:-:|:-:|:-:|
| UC1 | Sign up / profile | | | ● |
| UC2 | Create debt | ● | | |
| UC3 | Bilateral confirm (accept / reject / request edit) | | ● | |
| UC4 | QR identification | | | ● |
| UC5 | Payment (mark paid → confirm receipt) | | | ● |
| UC6 | Notifications | | ● | |
| UC7 | Commitment indicator | | ● | |
| UC8 | Dashboards | ● (creditor view) | ● (debtor view) | |
| UC9 | Groups (friends/family) | | ● | |
| UC10 | AI assistant (paid tier) | ● | | |

## Shared pages

| Page | Route | Use cases |
|---|---|---|
| Public Landing | `/` (unauthenticated) | Marketing, AR/EN toggle, CTA → auth |
| Login / Sign Up | `/auth` | UC1 |
| Profile | `/profile` | UC1 |
| Debt Details | `/debts/:id` | UC4, UC5 |
| Notifications | `/notifications` | shared list view |
| Settings | `/settings` | UC1 |

## Creditor pages

| Page | Route | Use cases |
|---|---|---|
| Creditor Dashboard | `/dashboard` (when `account_type ∈ {creditor, both}`) | UC8 (creditor) |
| Create Debt | `/debts/new` | UC2 |
| QR Scanner | `/qr/scan` | UC4 |
| Customer / Debtor Context | `/debtors/:id` | UC2, UC7 (bilateral) |
| Debt Details (creditor view) | `/debts/:id` | UC2, UC5 |
| Payment Confirmation | `/debts/:id/confirm-payment` | UC5 |
| AI Assistant *(optional / paid)* | `/ai` | UC10 |

## Debtor pages

| Page | Route | Use cases |
|---|---|---|
| Debtor Dashboard | `/dashboard` (when `account_type = debtor`) | UC8 (debtor) |
| Debt Confirmation | `/debts/:id/respond` | UC3 |
| Debt Details (debtor view) | `/debts/:id` | UC3, UC5 |
| QR Profile | `/qr` | UC4 |
| Notifications | `/notifications` | UC6 |
| Settings | `/settings` | UC6 (per-creditor WhatsApp opt-out), UC7 (own indicator) |
| Groups *(optional, post-MVP)* | `/groups` | UC9 |

## Routing notes

- `/dashboard` is one path that resolves to either `CreditorDashboardPage` or `DebtorDashboardPage` based on the loaded profile's `account_type`. `both` defaults to creditor with a one-tap switch.
- `account_type = both` (a freelancer who lends *and* borrows) sees both nav menus combined.
- The QR experience splits across two pages — the **debtor's** profile page shows a rotating QR; the **creditor's** scanner page reads it. They are never the same component.
- AI pages must hard-gate on `profile.ai_enabled` and return `403` from the backend if not.
