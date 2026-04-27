# Frontend Surface

React 19 + Vite + TypeScript. One file per route under `frontend/src/pages/`. Reusable parts in `frontend/src/components/`. Auth via `@supabase/supabase-js` (`frontend/src/lib/supabaseClient.ts`); JWT is forwarded to backend in `Authorization: Bearer` (`frontend/src/lib/api.ts`).

## Pages

| File | Route | Actor | UCs |
|---|---|---|---|
| `LandingPage.tsx` | `/` (unauthenticated) | shared | marketing, AR/EN toggle |
| `AuthPage.tsx` | `/auth` | shared | UC1 |
| `ProfilePage.tsx` | `/profile` | shared | UC1 |
| `SettingsPage.tsx` | `/settings` | shared | UC1, UC6 (per-creditor WhatsApp opt-out), UC7 (own indicator) |
| `DashboardPage.tsx` | `/dashboard` | role-routed | UC8 — resolves to creditor or debtor view from `account_type` |
| `DebtsPage.tsx` | `/debts`, `/debts/new`, `/debts/:id`, `/debts/:id/respond`, `/debts/:id/confirm-payment` | shared (role-aware) | UC2, UC3, UC5 |
| `QRPage.tsx` | `/qr`, `/qr/scan` | split (debtor display, creditor scanner) | UC4 |
| `NotificationsPage.tsx` | `/notifications` | shared | UC6 |
| `GroupsPage.tsx` | `/groups` | debtor (post-MVP, hidden from MVP nav) | UC9 |
| `AIPage.tsx` | `/ai` | creditor, gated | UC10 |

`/dashboard` is one path that resolves to creditor or debtor view based on `account_type`. `both` defaults to creditor with a one-tap switch (per `../pages-and-use-cases.md`).

## Shared infrastructure

| Path | Purpose |
|---|---|
| `frontend/src/contexts/AuthContext.tsx` | Supabase session + profile + role-routing state |
| `frontend/src/components/Layout.tsx` | Shell + nav |
| `frontend/src/components/ProtectedRoute.tsx` | Auth gate |
| `frontend/src/lib/api.ts` | fetch wrapper with `Authorization: Bearer` |
| `frontend/src/lib/auth.ts` | Supabase Auth helpers |
| `frontend/src/lib/supabaseClient.ts` | `@supabase/supabase-js` client |
| `frontend/src/lib/types.ts` | **Manual** mirror of `backend/app/schemas/domain.py` enums and DTOs |
| `frontend/src/lib/i18n.ts` | AR + EN strings; runtime RTL/LTR toggle |

## i18n

- AR is default; EN is a runtime toggle. Direction (RTL / LTR) flips at runtime.
- New user-facing strings **must** land in `lib/i18n.ts` for both languages. No hardcoded strings.

## Build

```bash
cd frontend
npm install
npm run dev          # :5173
npm run build        # tsc + vite build
npm run typecheck
```
