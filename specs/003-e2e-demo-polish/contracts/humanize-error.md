# Internal Contract: `humanizeError`

**Date**: 2026-04-28
**Feature**: 003-e2e-demo-polish
**Location**: `frontend/src/lib/errors.ts` (NEW)

This is an **internal** contract — a helper used by the four target pages, not a public API. It exists to centralize the translation of `apiRequest`-thrown errors into user-facing strings so FR-005 ("no raw API error reaches the UI") can be enforced consistently.

## Why this exists

`frontend/src/lib/api.ts:32` throws `new Error(\`${response.status}: ${text}\`)`. Page code historically caught this and called `setMessage(err.message)`, leaking strings like `409: Active or paid debts cannot be cancelled` regardless of locale. Centralising the translation in one helper means future pages can opt in with a single import.

## Signature

```ts
import type { Language } from './types';

export type ErrorContext =
  | 'loadDebts'
  | 'loadDashboard'
  | 'loadNotifications'
  | 'transition'
  | 'qrResolve'
  | 'generic';

export function humanizeError(err: unknown, language: Language, context?: ErrorContext): string;
```

## Behavior

1. **Parse the status code.** If `err` is an `Error` whose `message` matches `^(\d{3}):` (the `apiRequest` format), extract the leading numeric status. Otherwise treat it as `unknown` (network failure, JSON parse error, etc.).
2. **Map (status, context) to an i18n key** using this table:

   | Status | Context | i18n key |
   |--------|---------|----------|
   | any | `loadDebts` | `errorLoadDebts` |
   | any | `loadDashboard` | `errorLoadDashboard` |
   | any | `loadNotifications` | `errorLoadNotifications` |
   | 409 | `transition` | `errorTransitionStateChanged` |
   | 403 | `transition` | `errorTransitionForbidden` |
   | 404 | `qrResolve` | `qr_expired_ask_refresh` (existing key from Phase 2) |
   | 410 | `qrResolve` | `qr_expired_ask_refresh` |
   | * | (none / `generic`) | `errorGeneric` |

3. **Return** `t(language, <key>)`.
4. **Never** include the raw status code or backend body in the returned string.
5. **Never** throw. If parsing fails, return `t(language, 'errorGeneric')`.

## New i18n keys (added to `frontend/src/lib/i18n.ts`)

| Key | English | Arabic |
|-----|---------|--------|
| `errorGeneric` | "Something went wrong, please try again." | "حدث خطأ، حاول مرة أخرى." |
| `errorLoadDebts` | "Couldn't load your debts. Please retry." | "تعذّر تحميل الديون. حاول مرة أخرى." |
| `errorLoadDashboard` | "Couldn't load your dashboard. Please retry." | "تعذّر تحميل لوحة التحكم. حاول مرة أخرى." |
| `errorLoadNotifications` | "Couldn't load your notifications. Please retry." | "تعذّر تحميل الإشعارات. حاول مرة أخرى." |
| `errorTransitionStateChanged` | "This debt's status changed — please refresh." | "تغيّرت حالة هذا الدين — يرجى التحديث." |
| `errorTransitionForbidden` | "You're not allowed to perform this action." | "غير مسموح لك بتنفيذ هذا الإجراء." |

Plus 1–4 new empty-state keys (final names decided during implementation; e.g., `noNotificationsYet`, `dashboardSectionEmpty`). The `qr_expired_ask_refresh` and `noDebtsYet` keys already exist and are not redefined.

## Caller integration pattern

Replace existing patterns:

```ts
// before
} catch (err) {
  setMessage(err instanceof Error ? err.message : 'Failed to load');
}

// after
} catch (err) {
  setMessage(humanizeError(err, language, 'loadDebts'));
}
```

## Out of scope

- Does **not** change `apiRequest` itself. The helper sits next to the existing throw and does parsing on read (research §R1 alternative-A rejection).
- Does **not** silently swallow errors — `humanizeError` only formats; pages decide how to render the resulting string (toast, inline, dismissible).
- Does **not** translate **existing** untranslated UI strings unrelated to error paths — those are collected for Phase 5 (FR-010, research §R8).
