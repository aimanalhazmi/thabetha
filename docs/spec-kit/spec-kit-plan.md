# Spec-Kit Plan — Candidate Features

A backlog of next features framed as one-line problem statements, ready to feed into spec-kit's `/specify` → `/plan` → `/tasks` flow. Each entry is intentionally non-prescriptive — spec-kit should produce the implementation plan from the constraints, not from a pre-written design.

## How to use

1. Treat [`./constitution.md`](./constitution.md) as the spec-kit Constitution.
2. Pick one item below, run `/specify "<problem statement>"`, then `/plan`, then `/tasks`.
3. When done, mark the item ✅ here and update [`./project-status.md`](./project-status.md) and the relevant row in [`./use-cases.md`](./use-cases.md).

---

## P0 — Close MVP gaps

### F1. Receipt upload on Create Debt
Wire `POST /debts/{id}/attachments` (multipart, `attachment_type=invoice`) into the create-debt UI so the creditor can attach a receipt photo at creation time. Storage bucket `receipts`, path convention `<debt_id>/<uuid>-<filename>`. Acceptance: a creditor can create a debt with a receipt and the debtor can view it via signed URL on the debt details page. UC2.

### F2. QR-scanner pass-through to Create Debt
After a successful `GET /qr/resolve/{token}`, hand the resolved profile preview into the create-debt form so `debtor_id` and `debtor_name` are prefilled. Acceptance: creditor scans a debtor's QR and lands on `/debts/new` with debtor identity locked. UC4 → UC2.

### F3. End-to-end demo polish
Smoke-test the canonical flow on local Supabase: signup → create debt → debtor accept → debtor mark-paid → creditor confirm receipt → indicator updates. Catch and fix any UX rough edges. Acceptance: a fresh user can complete the flow without dev help.

### F4. AR/EN coverage audit
Audit every visible string against `frontend/src/lib/i18n.ts`. Acceptance: no hardcoded English/Arabic strings outside `i18n.ts`; both locales render with correct RTL/LTR.

### F5. Cancel-non-binding-debt UX
Surface `POST /debts/{id}/cancel` in the creditor UI for `pending_confirmation` / `edit_requested` debts; emit the correct debtor notification. Acceptance: creditor can cancel a non-binding debt in two taps and the debtor sees a `debt_cancelled` notification.

## P1 — Post-MVP

### F6. Real WhatsApp Business API integration
Replace the mock provider. Honour `merchant_notification_preferences.whatsapp_enabled` per (debtor, creditor). Acceptance: opt-out by debtor stops outbound WhatsApp messages from that creditor.

### F7. Payment-gateway settlement
Integrate HyperPay or Tap so `payment_pending_confirmation → paid` can be resolved by gateway callback (creditor still has the manual confirm path). Acceptance: a successful gateway charge transitions the debt to `paid` automatically and writes the same audit/score events as the manual path.

### F8. Group debt with auto-netting (UC9)
Surface groups in MVP nav; implement auto-netting on `group_settlements` so transitive debts within a group settle to the minimum-edge graph. Acceptance: three members with circular debts net to one or two transfers.

### F9. Backend stops running as Postgres role
Switch the backend connection to use scoped JWTs so RLS is enforced at runtime, not just in handler logic. Acceptance: handlers that forget the authorisation check still fail to leak data.

### F10. Charts & statistics on creditor dashboard
Time-series of receivables, top compliant customers, overdue distribution. Acceptance: dashboard renders charts from existing data without new tables (or with a thin aggregate cache).

## P2 — AI tier (paid)

### F11. AI receipt extraction
Image → debt draft fields. Hard-gated on `profile.ai_enabled`. Acceptance: photo of a receipt produces a populated `DebtCreate` draft with confidence ≥ 0.7 on the demo set.

### F12. Voice-to-debt draft polish
Replace the stub in `POST /ai/debt-draft-from-voice` with a real transcript pipeline. Acceptance: spoken Arabic prompt yields a populated draft with `raw_transcript` round-trippable.

### F13. Merchant-chatbot grounding
Ground `POST /ai/merchant-chat` answers in the caller's actual ledger. Acceptance: chatbot answers questions about real receivables and never about debts the user is not a party to.

## Cross-cutting / housekeeping

### H1. Drop legacy `thabetha-attachments` bucket
Migrate any straggler objects, then drop the legacy bucket created in 001 (canonical buckets are `receipts` + `voice-notes`).

### H2. Auto-derive `frontend/src/lib/types.ts` from `domain.py`
Manual mirror is drift-prone. Generate the TypeScript types from the Pydantic schemas (e.g. `datamodel-code-generator` + a small post-processor) and run it in CI.

### H3. Test coverage for every state transition
The constitution requires a test for any new transition. Audit the existing transition table against `backend/tests/` and fill gaps.
