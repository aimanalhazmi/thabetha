# Thabetha Frontend

React + TypeScript + Vite frontend for Thabetha.

## Setup

```bash
npm install
npm run dev
```

## Checks

```bash
npm run typecheck
npm run build
```

## Structure

| Path | Responsibility |
|---|---|
| `src/App.tsx` | Main app shell and feature screens |
| `src/lib/api.ts` | API client with local demo auth headers |
| `src/lib/i18n.ts` | Arabic/English translations |
| `src/lib/types.ts` | Shared frontend API types |
| `src/styles/app.css` | Responsive RTL/LTR UI styling |

## Demo Mode

The app uses three switchable demo users:

| User | ID |
|---|---|
| Merchant | `merchant-1` |
| Customer | `customer-1` |
| Friend | `friend-1` |

The Vite dev server proxies `/api` to `http://localhost:8000`.

