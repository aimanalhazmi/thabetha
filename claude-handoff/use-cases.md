# Use Cases — Claude Handoff Reference

| UC | Name | Status | Notes |
|---|---|---|---|
| UC1 | Creditor creates debt | ✅ Shipped | |
| UC2 | Debtor accepts / requests edit | ✅ Shipped | |
| UC3 | Debtor marks paid, creditor confirms | ✅ Shipped | |
| UC4 | QR code scanning (creditor scans debtor QR) | ✅ Shipped | |
| UC5 | Notifications | ✅ Shipped | In-app; WhatsApp mock. |
| UC6 | Commitment indicator | ✅ Shipped | `profiles.commitment_score` 0–100. |
| UC7 | Reminders | ✅ Shipped | `debts.reminder_dates`, lazy sweeper. |
| UC8 | Dashboard / debt list | ✅ Shipped | |
| UC9 | Groups auto-netting | ✅ Shipped | Group formation (008) + auto-netting (009). See `specs/009-groups-auto-netting/`. |
| UC10 | AI voice/chat tier | 🟡 Partial | Voice draft (Phase 12) ✅. Merchant-chat grounding (Phase 13) ✅ on `013-ai-merchant-chat-grounding` — tool-using LLM scoped to caller's ledger; mock + Anthropic providers; daily quota via `ai_merchant_chat_daily_limit`. Gated on `profile.ai_enabled`. |
