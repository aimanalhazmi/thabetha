# Product Requirements — Thabetha / ثبتها

## Problem

Across Arab local markets, shopkeepers, freelancers, friends, and family run informal credit on a paper "debt notebook" or scattered WhatsApp messages. Records are unilateral, easily disputed, and fall apart when the merchant changes phone, the customer denies the debt, or the notebook is lost. There is no shared truth, no reminders, no statistics, and no way to gauge how reliable a counterparty is — yet billions of riyals of micro-credit run through this channel daily.

## Solution

A bilingual (Arabic-first) web app that turns the paper notebook into a **bilaterally confirmed** ledger. Every debt is created by a creditor and only becomes binding when the debtor explicitly accepts. Both parties see the same record, the same audit trail, and the same status. The system layers on QR identity, in-app and (future) WhatsApp reminders, and a private **commitment indicator** that quietly captures repayment behaviour between the two parties.

This is not a credit bureau. The commitment indicator is internal to Thabetha, never published, and visible only in the bilateral context where it was earned. We use the term **commitment indicator / مؤشر الالتزام**, never "credit score".

## Actors

- **Creditor** — shop owner, freelancer, or individual lender. Creates debts, scans the debtor's QR, manages receivables, confirms payments, and (paid tier) uses AI helpers.
- **Debtor** — customer, friend, relative, or neighbour. Accepts/rejects/requests-edit on incoming debts, marks debts as paid, manages notification preferences, and shows the QR profile.
- **Both** — a freelancer who lends *and* borrows. Sees the union of creditor and debtor experiences.

## Features (UC list)

| UC | Title | Owner | One-line |
|---|---|---|---|
| UC1 | Sign up / profile | shared | Email + password via Supabase Auth; required fields are name, phone, account type. Business sub-profile is opt-in for creditors. |
| UC2 | Create debt | creditor | Amount, currency, debtor, description, due date are required; receipt photo and voice note are optional. AI tier can dictate. |
| UC3 | Bilateral confirm | debtor | Debtor accepts, rejects, or requests an edit. Debt is binding only on accept. |
| UC4 | QR identification | shared | Every user has a rotating short-lived QR. Creditors scan to identify the right debtor before creating a debt. |
| UC5 | Payment | shared | Debtor marks paid; creditor confirms receipt; debt closes; commitment indicator updates. |
| UC6 | Notifications | debtor | In-app on every transition. WhatsApp is mocked today; debtors can disable per-creditor in settings. |
| UC7 | Commitment indicator | debtor | Starts at 50/100, ±5 on on-time payment, −2 on late, −5 on overdue sweep. Never public. |
| UC8 | Dashboards | creditor / debtor | Creditor: total receivable, debtor count, overdue alerts, top-compliant customers. Debtor: total owed, due-soon, overdue, own indicator. |
| UC9 | Groups (post-MVP) | debtor | Friends/family group with shared visibility and auto-netting between members. |
| UC10 | AI assistant (paid) | creditor | Voice → debt extraction, ledger chatbot, future analytics. Hard-gated on `profile.ai_enabled`. |

The actor split (UC1/4/5 shared, UC2/8c/10 creditor, UC3/6/7/8d/9 debtor) is reflected in [`pages-and-use-cases.md`](./pages-and-use-cases.md).

## Non-functional requirements

- **Bilingual AR/EN** with runtime RTL/LTR toggle. Arabic is the default.
- **Auth via Supabase**. No bespoke password handling.
- **Per-user data isolation**. A user only ever sees debts where they are creditor, debtor, or accepted group member. Enforced both in API handlers and by Postgres RLS as defence-in-depth.
- **Audit trail** per debt: created-by + at, confirmed-by + at, paid-by + at, plus the full event log.
- **Simple UX** for non-technical shop owners; mobile-first.
- **No public debtor list, ever.** The commitment indicator is bilateral context only.

## Business logic

- Status transitions follow the table in [`debt-lifecycle.md`](./debt-lifecycle.md). Anything else is `409 Conflict`.
- A debt becomes `active` only after debtor accept; `paid` only after creditor confirms receipt.
- `overdue` is auto-derived from `due_date` and current state, not a destination of explicit user action.
- QR tokens are short-lived (10 minutes), rotated on demand, and resolve to a profile preview only — never to raw credentials.
- Storage objects (receipts, voice notes) are private and reachable only via signed URLs scoped to debt parties.
- AI endpoints return `403` unless `profile.ai_enabled` is true.

## MVP and future vision

[`mvp-scope.md`](./mvp-scope.md) lists the MoSCoW split. Today's MVP delivers UC1–UC8 minus the AI tier, on Supabase, in Arabic and English. The post-MVP roadmap is in [`roadmap.md`](./roadmap.md) — group auto-netting, real WhatsApp Business API, real payments, advanced AI behaviour analysis, fraud detection, and eventually micro-credit.
