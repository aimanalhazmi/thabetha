# MVP Scope

Hackathon-grade scope for **Thabetha / ثبتها**, framed as MoSCoW. Items map to the use cases in [`docs/pages-and-use-cases.md`](./pages-and-use-cases.md).

## Must Have

- Sign up / sign in via **Supabase Auth** (email + password). _UC1_
- Profile (name, phone, optional email, account type). _UC1_
- Business sub-profile for creditor accounts (shop name, activity, location, description). _UC1_
- Role-routed dashboards (creditor / debtor) selected from `account_type`. _UC8_
- Manually create a debt with amount, currency, debtor name, description, due date. _UC2_
- Bilateral confirmation: debtor can accept / reject / request edit. _UC3_
- Debt details page with the full event audit trail. _UC3, UC5_
- Debtor marks debt as paid; creditor confirms receipt (`payment_pending_confirmation` → `paid`). _UC5_
- Commitment indicator / **مؤشر الالتزام** visible to the debtor and to creditors who share a debt. _UC7_
- QR identity (rotating short-lived token, debtor side). _UC4_
- In-app notifications with Arabic/English copy. _UC6_
- Arabic-first UI with English toggle and runtime RTL/LTR switch.
- Audit trail per debt: created/confirmed/paid timestamps + event log.
- Receipt/invoice upload to **Supabase Storage** (`receipts` bucket). _UC2_

## Should Have

- QR scanner (creditor side) that resolves a debtor's QR token to a profile preview. _UC4_
- Cancel a non-binding debt (creditor) and the matching debtor notification. _UC2_
- Per-creditor WhatsApp opt-out (debtor setting; system honours when sending). _UC6_

## Could Have

- AI receipt extraction (creditor-only, paid tier). _UC10_
- AI voice-to-debt draft + confirmation. _UC10_
- AI merchant chatbot for ledger summaries. _UC10_
- Charts and richer statistics on the creditor dashboard. _UC8_
- Mock WhatsApp preview pane (renders the message that *would* go out). _UC6_

## Won't Have (now)

- Real WhatsApp Business API integration.
- Real payment gateway / settlement of cash/online transfers.
- Group debt with auto-netting between members. _UC9 — endpoints exist behind a feature flag, not surfaced in MVP nav._
- Advanced AI: behaviour analysis, payment-likelihood prediction, fraud detection.
- Micro-credit, formal contracts, multi-country compliance.
