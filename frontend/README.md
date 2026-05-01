# Thabetha Frontend

React 19 + TypeScript + Vite single-page application for Thabetha. Supports Arabic (RTL) and English (LTR) with full i18n coverage.

## Environment Secrets

Copy the example file and fill in the Supabase public keys before running:

```powershell
copy .env.example .env
```

Key variable:

| Variable | Purpose |
|---|---|
| `VITE_SUPABASE_URL` | Supabase project URL |
| `VITE_SUPABASE_ANON_KEY` | Supabase public anon key |
| `VITE_API_BASE_URL` | Backend API base URL (defaults to `/api/v1` via Vite proxy) |

Obtain values from `supabase status -o env` when running the local Supabase stack.

## Setup

```powershell
npm install
npm run dev
```

The Vite dev server starts on `http://127.0.0.1:5173` and proxies `/api` requests to the backend at `http://localhost:8000`.

## Available Scripts

| Command | Description |
|---|---|
| `npm run dev` | Start Vite dev server with HMR |
| `npm run build` | Type-check and produce a production build in `dist/` |
| `npm run typecheck` | Run TypeScript compiler without emitting |
| `npm run lint` | Run ESLint |
| `npm run test` | Run Vitest test suite |
| `npm run test:watch` | Run Vitest in watch mode |
| `npm run preview` | Preview the production build locally |

## Source Structure

```
src/
  pages/          One file per route (role-aware)
  components/     Reusable UI components and layout
  contexts/       React context providers (auth)
  lib/
    api.ts          Typed API client; attaches auth headers
    auth.ts         Supabase auth helpers
    i18n.ts         Arabic and English translation strings
    types.ts        Shared TypeScript types mirroring backend schemas
    supabaseClient.ts  Supabase JS client singleton
  styles/         Global CSS (RTL/LTR, responsive)
  App.tsx         Root component and router
  main.tsx        Entry point
```

## Authentication

In production the app uses Supabase Auth (`@supabase/supabase-js`). The JWT is attached as `Authorization: Bearer <token>` on all API requests via `lib/api.ts`.

In `APP_ENV=local`, the backend also accepts demo headers for quick debugging without a full auth flow. These headers are not used in production builds.

## i18n

All user-visible strings are defined in `src/lib/i18n.ts` with Arabic and English entries. When adding new UI text, add both translations before opening a pull request. The app locale defaults to Arabic and respects the user's saved preference.
