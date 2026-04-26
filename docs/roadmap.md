# Roadmap

## Hackathon (current)

Goal: ship MVP per [`mvp-scope.md`](./mvp-scope.md) on local Supabase.

- [x] Supabase-first stack (Auth + Postgres + Storage + RLS).
- [x] Canonical 8-state debt lifecycle.
- [x] Commitment indicator / مؤشر الالتزام (renamed from "trust score").
- [x] Role-based dashboards.
- [ ] Polished bilingual UI (Arabic-first, English toggle).
- [ ] End-to-end demo: signup → create debt → bilateral confirm → mark-paid → confirm → indicator updates.
- [ ] Receipt upload to Supabase Storage on Create Debt.
- [ ] QR scanner pass-through on Create Debt.

## Post-MVP (next 2–4 weeks)

- WhatsApp Business API integration (replace the mock provider).
- Payment gateway integration (start with HyperPay or Tap; settle the `payment_pending_confirmation → paid` step automatically).
- Group debt with auto-netting (UC9). Endpoints already exist; surface in nav.
- Charts and statistics (creditor dashboard timeseries).
- Mobile PWA polish, offline create-debt queue.
- Per-creditor WhatsApp opt-out enforcement on the actual sender.
- Hardened RLS — backend stops running with the Postgres role and switches to scoped JWTs.

## Future expansion (3+ months)

- AI behaviour analysis (segment debtors by payment patterns).
- Payment-likelihood prediction at debt creation.
- Fraud detection (duplicate debts, ring patterns).
- Repayment-plan suggestions and auto-reminders tuned to debtor preferences.
- Voice-first AR experience for low-literacy users.
- Micro-credit / formal contracts on top of repeated good behaviour.
- Multi-country compliance (KSA, EG, AE first).
- Accountant export (PDF / Excel of receivables, by period).
