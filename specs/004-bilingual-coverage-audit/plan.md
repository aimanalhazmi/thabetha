# Implementation Plan: Bilingual Coverage Audit (AR/EN)

**Branch**: `004-bilingual-coverage-audit` | **Date**: 2026-04-28 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/004-bilingual-coverage-audit/spec.md`

## Summary

Audit and harden the frontend so every user-perceived string — visible text and assistive-tech / document-metadata surfaces — is sourced from the single i18n sink in `frontend/src/lib/i18n.ts`, both locales render with correct RTL/LTR behavior on every routed page, dates and SAR currency are formatted via `Intl` keyed on the active locale, and a static check enforces this in CI for all future PRs. The user's locale preference is persisted on `public.profiles.preferred_language` for authenticated users (synced across devices), with a `localStorage` fallback for anonymous visitors and an Arabic default when neither is set.

The work is delivered in three slices that map to spec user stories:

1. **US1+US2 — Coverage sweep**: Inventory every JSX literal and assistive-tech / metadata string across the 10 pages and 4 components, port them into `i18n.ts`, ensure key parity AR↔EN, set `<html lang dir>` from the active locale, and run a manual walk-through in both languages.
2. **US3 — Lint + CI guardrail**: Add a minimal ESLint config (TypeScript-aware) with a JSX-no-literal rule plus a small custom rule for direction-aware props (`aria-*`, `alt`, `title`, `<title>` children, meta `content`); wire `npm run lint` into the existing Vite/TS toolchain and into CI.
3. **US4 — Per-page locale tests + persistence**: Introduce Vitest + Testing Library, add a parameterized test that renders every routed page in both locales asserting no missing-key artifacts and correct `document.dir`, and ship a Supabase migration adding `profiles.preferred_language text not null default 'ar'` plus the `AuthContext`/`localStorage` plumbing.

## Technical Context

**Language/Version**: TypeScript 5.7 strict (frontend), Python 3.12 (backend, schemas-only touch via Supabase migration)
**Primary Dependencies**: React 19, Vite 7, react-router-dom 7, @supabase/supabase-js 2.x. New dev dependencies: `eslint`, `@typescript-eslint/parser`, `@typescript-eslint/eslint-plugin`, `eslint-plugin-react`, `eslint-plugin-jsx-a11y`, `vitest`, `@vitest/ui`, `@testing-library/react`, `@testing-library/jest-dom`, `jsdom`. No new runtime dependencies.
**Storage**: Supabase Postgres — one new migration `008_preferred_language.sql` that adds `profiles.preferred_language text not null default 'ar' check (preferred_language in ('ar','en'))` and updates the `handle_new_user()` trigger.
**Testing**: Vitest + jsdom + @testing-library/react for the per-page locale render tests. Existing `pytest` (backend) only runs to validate the migration applies cleanly under `REPOSITORY_TYPE=postgres`.
**Target Platform**: Web (modern evergreen browsers; same as today). No mobile-platform changes.
**Project Type**: Web application (existing `frontend/` + `backend/` + `supabase/` layout).
**Performance Goals**: Locale switch updates every visible surface within 1 s on a standard dev build (SC-006). Per-page locale test suite completes in under 60 s locally and in CI (SC-007).
**Constraints**:
- Zero new runtime dependencies (use platform `Intl.*` APIs; do not add `i18next` or similar — the existing `i18n.ts` sink stays the single source of truth).
- Lint must catch ≥ 95% of synthetically seeded raw-JSX violations across pages and components (SC-003) and ≥ 100% of the violations on the 20-sample calibration (SC-004 first-10-PR window).
- Profile-locale column add must be backwards-compatible (default `'ar'`, no breaking schema change for existing rows).
**Scale/Scope**: 10 routed pages, 4 components, 1 layout, ~300 existing translation keys (estimated from `i18n.ts`). Two locales today (ar, en); structure must accommodate adding a third locale without per-page rewrites.

No `NEEDS CLARIFICATION` items remain — Phase 0 research below documents the tooling decisions.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Relevance | Status |
|---|---|---|
| I. Bilateral Confirmation | N/A — no lifecycle changes. | ✅ Pass |
| II. Canonical 7-State Lifecycle | N/A — no debt-state code is touched. | ✅ Pass |
| III. Commitment Indicator, never "Credit Score" | Audit may rename leftover EN strings; **must** preserve "commitment indicator / مؤشر الالتزام" wording and never introduce "trust score" / "credit score" in either locale. | ✅ Pass — spec FR-001/FR-010 enforce key parity; audit will explicitly verify the canonical term in both locales. |
| IV. Per-User Data Isolation | Profile-locale read/write is per-user; the new column is gated by the existing `profiles` RLS policies (own-row read/update). The migration only adds the column — no policy changes needed. | ✅ Pass |
| V. Arabic-First | This audit **is** the enforcement of this principle. Default locale stays `'ar'`; new column default is `'ar'`. | ✅ Pass — directly aligned. |
| VI. Supabase-First Stack | Locale persistence uses the existing `profiles` row; no parallel storage. Migration lands as the next sequential file. | ✅ Pass |
| VII. Schemas Are The Single Source Of Truth | Adding `preferred_language` requires updating `backend/app/schemas/domain.py` (`Profile` schema) **and** `frontend/src/lib/types.ts` in lockstep. New migration file (no edits to `001_*.sql`). | ✅ Pass — captured as a discrete task. |
| VIII. Audit Trail Per Debt | N/A — no debt mutations. | ✅ Pass |
| IX. QR Identity Bilateral | The QR landing page is in audit scope (per Q2 → all pages), but no QR contract changes. | ✅ Pass |
| X. AI Paid-Tier Gating | N/A — `AIPage.tsx` is in audit scope for strings, but the gate is untouched. | ✅ Pass |

No violations. No Complexity Tracking entries needed.

## Project Structure

### Documentation (this feature)

```text
specs/004-bilingual-coverage-audit/
├── plan.md              # This file
├── spec.md              # Feature spec
├── research.md          # Phase 0 — tooling + persistence decisions
├── data-model.md        # Phase 1 — entities (Profile.preferred_language, client Locale state)
├── quickstart.md        # Phase 1 — how to run the audit, lint, and tests locally
├── contracts/
│   ├── profile-locale.md    # GET / PATCH profile language contract
│   └── lint-rule.md         # Static-check contract: what triggers a Blocker finding
├── checklists/
│   └── requirements.md  # From /speckit-specify
└── tasks.md             # Generated by /speckit-tasks (next step)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── schemas/
│   │   └── domain.py            # MODIFY: add `preferred_language: Literal['ar','en']` to Profile
│   ├── repositories/
│   │   ├── memory.py            # MODIFY: round-trip preferred_language
│   │   └── postgres.py          # MODIFY: select/update preferred_language
│   └── api/
│       └── profiles.py          # MODIFY (or add): PATCH profile preferred_language
└── tests/                       # ADD: test for profile locale round-trip

frontend/
├── src/
│   ├── App.tsx                  # MODIFY: set <html lang dir> from active locale
│   ├── contexts/
│   │   └── AuthContext.tsx      # MODIFY: load profile locale on sign-in; expose locale + setter
│   ├── lib/
│   │   ├── i18n.ts              # MODIFY: add any missing keys; add helpers `formatDate`, `formatCurrency` keyed on locale
│   │   ├── types.ts             # MODIFY: mirror Profile.preferred_language
│   │   └── localePersistence.ts # ADD: localStorage fallback + profile sync
│   ├── pages/                   # MODIFY all: replace literals with t() calls; verify metadata
│   ├── components/              # MODIFY all: same as pages
│   └── styles/
│       └── app.css              # MODIFY (if needed): RTL-aware utility classes / logical properties
├── tests/                       # ADD
│   ├── setup.ts                 # ADD: Vitest + jsdom + Testing Library bootstrap
│   ├── locale-coverage.test.tsx # ADD: parameterized render-each-page-in-both-locales
│   └── i18n-key-parity.test.ts  # ADD: assert AR keys == EN keys
├── .eslintrc.cjs                # ADD: TS-aware ESLint config with no-literal-string rule
├── eslint-rules/
│   └── no-untranslated-jsx.js   # ADD (only if no off-the-shelf rule covers our exempt-set cleanly)
├── vitest.config.ts             # ADD
└── package.json                 # MODIFY: scripts (`lint`, `test`); devDependencies

supabase/
└── migrations/
    └── 008_preferred_language.sql   # ADD: column + handle_new_user() update
```

**Structure Decision**: Existing web-app layout (`backend/`, `frontend/`, `supabase/`) is unchanged. The audit adds tooling files inside `frontend/` (eslint config, vitest config, tests/), updates every page and component file in place, adds one Supabase migration, and threads `preferred_language` through the schema → repositories → router → frontend types in lockstep per Constitution principle VII.

## Complexity Tracking

> No Constitution Check violations. Section intentionally empty.
