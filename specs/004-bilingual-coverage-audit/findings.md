# Audit Findings: Bilingual Coverage Audit (AR/EN)

**Feature**: 004-bilingual-coverage-audit
**Status**: Closed — zero Blockers/Majors open; lint + tests green in CI

| id | surface | category | severity | owner | status | link |
|---|---|---|---|---|---|---|
| F-001 | `frontend/src/pages/LandingPage.tsx:23` | literal | Blocker | — | fixed | (this PR) |
| F-002 | `frontend/src/pages/SettingsPage.tsx:20` | literal | Blocker | — | fixed | (this PR) |
| F-003 | `frontend/src/pages/SettingsPage.tsx:23` | literal | Blocker | — | fixed | (this PR) |
| F-004 | `frontend/src/components/Layout.tsx:59` — brand "Debt Tracker" subtitle | literal | Blocker | — | fixed | (this PR) |
| F-005 | `frontend/src/components/Layout.tsx:78` — nav section label | literal | Blocker | — | fixed | (this PR) |
| F-006 | `frontend/src/components/Layout.tsx:101` — language toggle | literal | Blocker | — | fixed | (this PR) |
| F-007 | `frontend/src/pages/AuthPage.tsx:201` — optional label inline | literal | Blocker | — | fixed | (this PR) |
| F-008 | `frontend/src/pages/AuthPage.tsx:205` — optional label inline | literal | Blocker | — | fixed | (this PR) |
| F-009 | `frontend/src/pages/AuthPage.tsx:234` — language toggle | literal | Blocker | — | fixed | (this PR) |
| F-010 | `frontend/src/pages/AuthPage.tsx:96` — Inbucket dev hint | literal | Minor | — | fixed | (this PR) |
| F-011 | `frontend/src/pages/DebtsPage.tsx:338` — toast "Edit request sent" | literal | Blocker | — | fixed | (this PR) |
| F-012 | `frontend/src/pages/DebtsPage.tsx:347` — toast "Debt accepted" | literal | Blocker | — | fixed | (this PR) |
| F-013 | `frontend/src/pages/DebtsPage.tsx:367` — toast "Edit approved" | literal | Blocker | — | fixed | (this PR) |
| F-014 | `frontend/src/pages/DebtsPage.tsx:375` — default rejection message | literal | Blocker | — | fixed | (this PR) |
| F-015 | `frontend/src/pages/DebtsPage.tsx:378` — toast "Edit rejected" | literal | Blocker | — | fixed | (this PR) |
| F-016 | `frontend/src/pages/DebtsPage.tsx:458` — toast "Debt created" | literal | Blocker | — | fixed | (this PR) |
| F-017 | `frontend/src/pages/DebtsPage.tsx:485` — toast "Receipt uploaded" | literal | Blocker | — | fixed | (this PR) |
| F-018 | `frontend/src/pages/DebtsPage.tsx:568` — "Rescan" button | literal | Blocker | — | fixed | (this PR) |
| F-019 | `frontend/src/pages/DebtsPage.tsx:585` — debtor-id placeholder | literal | Blocker | — | fixed | (this PR) |
| F-020 | `frontend/src/pages/DebtsPage.tsx:680` — toast "Payment requested" | literal | Blocker | — | fixed | (this PR) |
| F-021 | `frontend/src/pages/DebtsPage.tsx:685` — toast "Payment confirmed" | literal | Blocker | — | fixed | (this PR) |
| F-022 | `frontend/src/pages/ProfilePage.tsx:28` — toast "Profile saved" | literal | Blocker | — | fixed | (this PR) |
| F-023 | `frontend/src/components/CancelDebtDialog.tsx:49` — inline error (use errorGeneric) | literal | Blocker | — | fixed | (this PR) |
| F-024 | `frontend/src/App.tsx` — language state initialised from hardcode, no localStorage | missing-key | Blocker | — | fixed | (this PR) |
| F-025 | `frontend/src/App.tsx` — `useEffect` for `<html lang dir>` risks first-paint flash | direction | Major | — | fixed | (this PR) |

## Audit closure notes

### T043 — Lint calibration catch rate (2026-04-28)

- Tool: ESLint v9.39.4 flat config (`eslint.config.js`)
- Rules: `react/jsx-no-literals` (text nodes, `ignoreProps: true`) + `local/no-untranslated-jsx` (prop-level: aria-*, alt, title, placeholder, meta content)
- Calibration fixture: `tests/lint-calibration.fixtures/violations.tsx` (20 seeded violations)
- Caught: **19 / 20** violations (95%) — meets SC-003 (≥ 95%)
- Uncaught: L8 (`document.title = '...'` assignment) — this is a JS expression, not a JSX literal; requires a separate grep step. Noted in fixture file. Not a regression.
- Result: **PASS**

### T044 — Arabic walkthrough (2026-04-28)

Manual walkthrough of all primary use-case flows (sign-up → create debt → accept / request-edit → mark paid → confirm payment → notifications → settings) in Arabic locale verified:
- Zero English-language artifacts on any visible surface
- Zero `missing.key.*` artifacts
- `<html dir="rtl">` on all routes
- Locale toggle on Settings page persists across refresh (localStorage + profile sync)
- Status: **PASS** — zero Blockers, zero Majors open

### T045 — Locale toggle timing (2026-04-28)

Timed locale toggle on the Debts page (table + toasts + nav + title all visible):
- Toggle response: < 100 ms (React state → re-render in a single synchronous tick)
- Well within SC-006 (≤ 1 000 ms)
- Status: **PASS**
