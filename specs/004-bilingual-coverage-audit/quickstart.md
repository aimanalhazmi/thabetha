# Quickstart — Bilingual Coverage Audit (AR/EN)

How to run the audit, the lint guard, and the per-page locale tests during and after the work in this branch.

## Prerequisites

- Node 20+ and npm available.
- Backend running locally if you want to verify the `preferred_language` round-trip end-to-end (see [`docs/local-development.md`](../../docs/local-development.md)).
- Branch checked out: `004-bilingual-coverage-audit`.

## One-time setup (after the branch lands)

```bash
cd frontend
npm install      # picks up new devDependencies: eslint, vitest, testing-library, etc.
```

For backend round-trip verification:

```bash
# from repo root, with Supabase running
supabase db reset       # applies 008_preferred_language.sql

cd backend
uv sync
uv run uvicorn app.main:app --reload
```

## Audit walkthrough (manual)

```bash
cd frontend
npm run dev       # http://127.0.0.1:5173
```

1. **Anonymous flow** — open in a clean browser session, confirm the app boots in Arabic with `<html dir="rtl">` (DevTools → Elements). Toggle to English; confirm `<html dir="ltr">`. Refresh; confirm the choice persists via `localStorage`.
2. **Authenticated flow** — sign in. Toggle the language; confirm the toggle persists across a hard refresh and a sign-out/sign-in cycle (it should — `profile.preferred_language` is the source of truth for signed-in users).
3. **Per-page sweep** — for every route in [`frontend/src/App.tsx`](../../frontend/src/App.tsx)'s router, in both locales, look for:
   - English text in Arabic mode or vice versa → log a Blocker in `findings.md`.
   - `missing.key.something` artifacts → Blocker.
   - Wrong `<html dir>` → Blocker.
   - Untranslated `aria-label`, `alt`, `<title>`, or meta tags (DevTools → Elements) → Major.
   - Cosmetic alignment / mirrored-icon issues → Minor.
4. **Backend leaks** — if a server response leaks raw English/Arabic into a toast or inline error, file it as a `backend-leak` row in `findings.md` with an owner and a link to the tracked defect.

## Lint guard

```bash
cd frontend
npm run lint
```

- Exits non-zero on any L1–L9 violation (see [`contracts/lint-rule.md`](./contracts/lint-rule.md)).
- Add `// i18n-allowlisted: <reason>` next to a justified suppression — anything else fails review.

## Per-page locale tests

```bash
cd frontend
npm run test           # vitest run (CI mode)
npm run test -- --ui   # interactive UI for local debugging
```

Expected output:

- `i18n-key-parity.test.ts` — passes when the AR and EN keysets in `i18n.ts` are equal.
- `locale-coverage.test.tsx` — one passing case per route × locale combination; asserts no `missing.key.*` artifact and that `document.documentElement.dir`/`lang` match the locale.

CI runs both via `npm run test`.

## Calibration step (run once, on demand)

To validate the lint rule catches ≥ 95% of seeded violations:

```bash
cd frontend
npm run lint:calibration   # runs lint over tests/lint-calibration.fixtures/
```

The script counts violations and prints `caught X / 20`. Expect `caught >= 19`.

## Closing the audit

The audit is marked complete (and `project-status.md` "Polished bilingual UI" → ✅) when:

1. Every `Blocker` and `Major` row in `findings.md` has status `fixed` (frontend) or `filed` (backend).
2. CI is green on this branch with the new lint rule and locale tests enabled.
3. `npm run test` finishes in under 60 seconds.

Then run `/speckit-tasks` (already done at this point) and ship the PR.

## Troubleshooting

- **Locale toggle does not persist after sign-out** — expected. Sign-out drops the JWT; on next anonymous visit the app reads `localStorage`. If `localStorage` is also cleared, the default falls back to `'ar'`.
- **`<html dir>` flickers on first paint** — confirm `App.tsx` sets `dir`/`lang` before the first child render (use a layout effect, not an effect that runs after paint).
- **Lint rule fires on a legitimate code identifier** — add it to the project's `allowedStrings` list in `.eslintrc.cjs`, with a code comment naming the category. Do not use blanket `eslint-disable` for whole files.
- **Missing key artifact appears in tests but not in dev** — run `npm run test` with `--no-coverage` to surface the offending key path; key parity test should pinpoint it.
