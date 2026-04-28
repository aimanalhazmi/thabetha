---

description: "Tasks for Bilingual Coverage Audit (AR/EN) — Feature 004"
---

# Tasks: Bilingual Coverage Audit (AR/EN)

**Input**: Design documents from `specs/004-bilingual-coverage-audit/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: User Story 4 in spec.md is explicitly about automated locale tests (FR-013); test tasks are therefore included for US4 and the test stack is added in Setup. Other stories use lightweight verification.

**Organization**: Grouped by user story to enable independent implementation and testing. US1 and US2 are symmetric (Arabic-first / English) and share the same coverage sweep; they are combined into one phase but tagged with both story labels for traceability.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Maps to spec user stories (US1, US2, US3, US4)
- File paths are exact and absolute-from-repo-root

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Add the dev-only tooling the audit depends on (linting + testing).

- [x] T001 [P] Add devDependencies to `frontend/package.json`: `eslint`, `@typescript-eslint/parser`, `@typescript-eslint/eslint-plugin`, `eslint-plugin-react`, `eslint-plugin-jsx-a11y`. Run `npm install` to update `package-lock.json`.
- [x] T002 [P] Add devDependencies to `frontend/package.json`: `vitest`, `@vitest/ui`, `@testing-library/react`, `@testing-library/jest-dom`, `jsdom`. Run `npm install` to update `package-lock.json`.
- [x] T003 Add npm scripts to `frontend/package.json`: `"lint": "eslint --ext .ts,.tsx src/"`, `"test": "vitest run"`, `"test:watch": "vitest"`, `"lint:calibration": "eslint --ext .ts,.tsx tests/lint-calibration.fixtures/ || true"`. Wire the existing `tsc --noEmit` typecheck to remain available as `typecheck`. Depends on T001 + T002.
- [x] T004 [P] Create the empty findings tracker file `specs/004-bilingual-coverage-audit/findings.md` with the column schema from `data-model.md` (id, surface, category, severity, owner, status, link). Audit findings will be appended during Phase 3.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Wire `profiles.preferred_language` end-to-end and connect the active locale to `<html lang dir>`. US1, US2, and US4 all depend on the toggle being functional and on the document direction being settable.

**⚠️ CRITICAL**: No user-story work can begin until this phase is complete.

### Database

- [x] T005 Create `supabase/migrations/008_preferred_language.sql` per the sketch in `data-model.md`: `alter table public.profiles add column preferred_language text not null default 'ar' check (preferred_language in ('ar', 'en'));` plus a `create or replace function public.handle_new_user()` that seeds the column from `raw_user_meta_data->>'preferred_language'` (default `'ar'`). Verify the migration applies cleanly via `supabase db reset`.

### Backend schema + repositories + API

- [x] T006 [P] Update `backend/app/schemas/domain.py` `Profile` model: add `preferred_language: Literal["ar", "en"] = "ar"`. Update any related `ProfileUpdate`/`ProfileCreate` schemas in the same file to accept the field as optional on update.
- [x] T007 [P] Update `backend/app/repositories/memory.py` to round-trip `preferred_language` on profile create / update / fetch. Default to `"ar"` for any existing in-memory profile that does not specify it.
- [x] T008 [P] Update `backend/app/repositories/postgres.py` to select and update `preferred_language` on the `profiles` table.
- [x] T009 Update or add the profile update route in `backend/app/api/profiles.py` so `PATCH /api/v1/profiles/me` accepts `{ "preferred_language": "ar" | "en" }` per `contracts/profile-locale.md`. Pydantic validation rejects any other value with 422. Depends on T006, T007, T008.
- [x] T010 [P] Add backend test `backend/tests/test_profile_locale.py` covering the five surfaces in `contracts/profile-locale.md` (default-on-fetch, set-and-readback, invalid-value 422, cross-user isolation, migration round-trip). Uses `client` fixture and demo headers per `backend/tests/conftest.py`.

### Frontend types + locale plumbing

- [x] T011 [P] Update `frontend/src/lib/types.ts`: add `preferred_language: Language` to the `Profile` interface (where `Language = 'ar' | 'en'` already exists or add it).
- [x] T012 [P] Add `frontend/src/lib/localePersistence.ts` exposing `loadInitialLocale(profile?: Profile): Language` (priority: profile.preferred_language → `localStorage['thabetha.locale']` → `'ar'`) and `setLocale(next: Language, opts: { signedIn: boolean; profileId?: string })` (writes localStorage; if signedIn, fires `PATCH /api/v1/profiles/me`).
- [x] T013 Update `frontend/src/contexts/AuthContext.tsx` to: (a) on session bootstrap and on profile refresh, call `loadInitialLocale(profile)` and apply the returned locale; (b) expose `locale: Language` and `setLocale: (next: Language) => Promise<void>` in the context value; (c) on sign-in, override any existing localStorage value with `profile.preferred_language`. Depends on T011, T012.
- [x] T014 Update `frontend/src/App.tsx` to set `document.documentElement.lang = locale` and `document.documentElement.dir = locale === 'ar' ? 'rtl' : 'ltr'` via a `useLayoutEffect` that runs before the first child render (avoid first-paint flicker — see `quickstart.md` troubleshooting). Depends on T013.
- [x] T015 [P] Add `formatDate(value: string | Date, locale: Language): string` and `formatCurrency(amount: number, locale: Language, currency = 'SAR'): string` helpers to `frontend/src/lib/i18n.ts`. Both wrap `Intl.DateTimeFormat` / `Intl.NumberFormat` keyed on the locale; Gregorian-only per FR-005.

**Checkpoint**: Locale toggle persists end-to-end (anonymous → localStorage; signed in → `profiles.preferred_language`); `<html lang dir>` updates without flicker; `Intl` helpers are available on the i18n sink.

---

## Phase 3: User Story 1 + User Story 2 — AR/EN coverage sweep (Priority: P1) 🎯 MVP

**Goal**: Every page and every component renders all user-perceived strings via `i18n.ts`, in fluent Arabic and fluent English, with correct RTL/LTR behavior on every surface enumerated in FR-001 (visible text, `aria-*`, `alt`, `<title>`, `<meta>`, `<input title>`, image captions).

**Independent Test (US1)**: Walk every route in `frontend/src/App.tsx` with the locale set to Arabic; confirm zero English-language artifacts and zero `missing.key.*` placeholders; confirm `<html dir="rtl">`. Per `quickstart.md` "Audit walkthrough".

**Independent Test (US2)**: Same walkthrough with the locale set to English; `<html dir="ltr">`; zero Arabic artifacts; runtime locale toggle reflows every visible surface (FR-007).

### Per-page sweep

> Each task: replace every user-perceived string literal (visible text, `aria-*`, `alt`, `title`, `placeholder`, `<title>`, `<meta>`) with `t('key')` calls; add any missing keys to `frontend/src/lib/i18n.ts` (BOTH locales together — never add an EN-only or AR-only key); replace any direct date/number formatting with `formatDate` / `formatCurrency`; wrap any bidi-fragile interpolation in `<bdi>`. Append every defect found that you cannot fix in the same diff to `specs/004-bilingual-coverage-audit/findings.md` with the right severity tier.

- [x] T016 [P] [US1] [US2] Sweep `frontend/src/pages/LandingPage.tsx` (in scope per Q2 — no exclusions).
- [x] T017 [P] [US1] [US2] Sweep `frontend/src/pages/AuthPage.tsx`, including the email-confirmation / password-reset entry surfaces it renders.
- [x] T018 [P] [US1] [US2] Sweep `frontend/src/pages/DashboardPage.tsx`, including chart axis labels, legends, and tooltips (cover FR-007 dialog/toast cases triggered from this page).
- [x] T019 [P] [US1] [US2] Sweep `frontend/src/pages/DebtsPage.tsx`, including table headers, status badges, and the inline state-transition flows.
- [x] T020 [P] [US1] [US2] Sweep `frontend/src/pages/QRPage.tsx` — both the QR-display surface and the QR-scanner surface; QR-landing deep-link entry must render bilingually (FR-014, edge case).
- [x] T021 [P] [US1] [US2] Sweep `frontend/src/pages/NotificationsPage.tsx`, including notification-type labels (must be sourced from `i18n.ts`, not from any backend string).
- [x] T022 [P] [US1] [US2] Sweep `frontend/src/pages/ProfilePage.tsx`, including the commitment-indicator label — preserve "commitment indicator / مؤشر الالتزام"; never introduce "trust score" / "credit score" (Constitution principle III).
- [x] T023 [P] [US1] [US2] Sweep `frontend/src/pages/SettingsPage.tsx`, including the language toggle UI itself; add the language toggle if it does not yet expose `setLocale` from `AuthContext`. Ensure persistence test (anonymous → localStorage, signed-in → profile) is exercisable from this page.
- [x] T024 [P] [US1] [US2] Sweep `frontend/src/pages/GroupsPage.tsx` (in scope as a routed page even though group debt is post-MVP nav).
- [x] T025 [P] [US1] [US2] Sweep `frontend/src/pages/AIPage.tsx` (audit covers strings; AI gating itself untouched per Constitution principle X).
- [x] T026 [P] [US1] [US2] Sweep `frontend/src/components/Layout.tsx`, including all navigation labels, document-title-setter logic, and any direction-meaningful icons (mirror chevrons / back-arrows under `[dir="rtl"]`).
- [x] T027 [P] [US1] [US2] Sweep `frontend/src/components/AttachmentUploader.tsx`, including the file-picker `aria-label`, drop-zone copy, and validation messages.
- [x] T028 [P] [US1] [US2] Sweep `frontend/src/components/CancelDebtDialog.tsx`, including dialog title, body, action button labels, and aria attributes.
- [x] T029 [P] [US1] [US2] Sweep `frontend/src/components/ProtectedRoute.tsx` for any redirect / fallback message it surfaces.

### CSS / RTL polish

- [x] T030 [US1] [US2] Sweep `frontend/src/styles/app.css` (and any other CSS files reachable from it): replace `left`/`right`/`margin-left`/`padding-right`/`text-align: left|right` with logical properties (`inset-inline-start`, `margin-inline-start`, `padding-inline-end`, `text-align: start|end`). Add `[dir="rtl"]` mirror rules for direction-meaningful icons. Verifies the FR-003/FR-004 RTL surfaces (forms, tables, modals, toasts, navigation drawer, charts) listed in spec edge cases.

### Document metadata

- [x] T031 [US1] [US2] Audit `frontend/index.html` and any place that sets `document.title` or writes meta tags: ensure the page `<title>`, `<meta name="description">`, and any OG tags are sourced from `i18n.ts` (or set client-side via `t()`) — not hardcoded English.

### i18n sink hygiene

- [x] T032 [US1] [US2] Final pass on `frontend/src/lib/i18n.ts`: confirm the AR and EN keysets are equal (no key present in only one locale). Sort or comment-group keys for review-ability. This task is the human-side counterpart to the automated parity check in T040. Depends on T016–T031.

**Checkpoint**: Every routed page and every component renders fully bilingually with correct direction. Findings file lists any cosmetic-only Minor issues that are tracked but non-blocking; zero Blockers and zero Majors remain `open`. Backend-leak findings, if any, are filed and assigned per FR-015.

---

## Phase 4: User Story 3 — Lint + CI guardrail (Priority: P2)

**Goal**: A static check exits non-zero on any L1–L9 violation from `contracts/lint-rule.md` in `frontend/src/pages/` and `frontend/src/components/`, runs locally via `npm run lint`, and is enforced by CI. Suppressions require a justification comment.

**Independent Test**: Add a deliberately raw JSX literal to any page or component file, run `npm run lint`, observe non-zero exit and a clear message. Remove the literal; lint passes. CI fails on the same violation when introduced via a PR.

- [x] T033 [US3] Add `frontend/.eslintrc.cjs` (or `.eslintrc.json`) wiring `@typescript-eslint/parser`, `plugin:react/recommended`, `plugin:jsx-a11y/recommended`, and `plugin:@typescript-eslint/recommended`. Enable `react/jsx-no-literals` with `noStrings: true`, an `allowedStrings` list for benign delimiters (`' '`, `' / '`, `' · '`, `':'`, `'—'`), and `ignoreProps: false`. Restrict the rule's scope to `src/pages/**` and `src/components/**` via overrides.
- [x] T034 [P] [US3] Decide whether `react/jsx-no-literals` covers L2–L8 from `contracts/lint-rule.md` cleanly. If not, create `frontend/eslint-rules/no-untranslated-jsx.js` — a small custom rule that fails on string-literal RHS for the explicit prop allowlist (`aria-label`, `aria-describedby`, `aria-placeholder`, `aria-roledescription`, `aria-valuetext`, `alt`, `title`, `placeholder`, `<title>` children, `content` on `<meta name="description">` and `og:*`, and `document.title = ...` assignments). Register the rule in `.eslintrc.cjs` via `rulePaths`/`plugins`.
- [x] T035 [P] [US3] Document the suppression policy at the top of `frontend/.eslintrc.cjs` (in a comment) and in `quickstart.md` (already done): inline `// eslint-disable-next-line` requires a `// i18n-allowlisted: <reason>` comment. Add a small CI grep step (or simple npm script) `lint:suppressions-justified` that fails if any `eslint-disable` line lacks a paired `i18n-allowlisted` comment.
- [x] T036 [P] [US3] Create `frontend/tests/lint-calibration.fixtures/` containing the 20 deliberately seeded violations (one file per L1–L9 pattern, plus extras to hit 20 total) per the calibration spec in `contracts/lint-rule.md` and `research.md` R1. These files MUST be excluded from production builds (gitignore from build, or kept under `tests/` which Vite already excludes).
- [x] T037 [US3] Wire `npm run lint` into the existing CI workflow (or add a step if none): the lint step runs on every PR and blocks merges on non-zero exit. Update `docs/local-development.md` if a new `npm run lint` command needs to be documented for contributors.

**Checkpoint**: Lint runs locally and in CI; raw JSX strings (and the L2–L8 prop variants) fail the build; suppressions without justification fail the suppressions-justified check; calibration fixtures yield ≥ 19 / 20 caught (SC-003).

---

## Phase 5: User Story 4 — Per-page locale tests (Priority: P3)

**Goal**: A Vitest test suite renders every routed page in both locales, asserts no `missing.key.*` artifact in the DOM, and asserts `document.documentElement.dir`/`lang` match the locale. A separate test asserts AR/EN keyset parity in `i18n.ts`.

**Independent Test**: `npm run test` exits 0 with one passing case per route × locale. Removing a key from one locale in `i18n.ts` causes the parity test to fail with a message that names the missing key (FR-010, SC-002). Renaming any page's translation key without removing call sites causes the relevant route × locale test to fail.

- [x] T038 [P] [US4] Add `frontend/vitest.config.ts` with `environment: 'jsdom'`, `setupFiles: ['./tests/setup.ts']`, and `globals: true`. Configure `include: ['tests/**/*.test.{ts,tsx}']` and a 60-second test-suite timeout to enforce SC-007.
- [x] T039 [P] [US4] Add `frontend/tests/setup.ts` that imports `@testing-library/jest-dom`, mocks any browser APIs the app relies on (e.g., `localStorage`, `matchMedia` if used), and provides a `renderWithLocale(routePath: string, locale: 'ar' | 'en')` helper that mounts `<App />` (or a thin test-router wrapper) with the locale forced via the AuthContext provider.
- [x] T040 [P] [US4] Add `frontend/tests/i18n-key-parity.test.ts`: import the AR and EN dictionaries from `frontend/src/lib/i18n.ts`, assert their keysets are deeply equal. On failure, the message lists the keys present in one locale only.
- [x] T041 [US4] Add `frontend/tests/locale-coverage.test.tsx`: enumerate every route from `frontend/src/App.tsx` and use `describe.each(ROUTES)` × `it.each(['ar', 'en'])` to assert (a) the rendered DOM does not contain `/missing\.key\./`, (b) `document.documentElement.dir` matches the locale, (c) `document.documentElement.lang` matches the locale. Depends on T038, T039.
- [x] T042 [US4] Wire `npm run test` into CI (same workflow as T037) so failures block merges. The combined lint + test step must complete in under 60 seconds locally per SC-007; if it does not, profile with `vitest --reporter=verbose` and split routes into `it.concurrent` cases as needed.

**Checkpoint**: All four user stories are independently functional. Removing or unbalancing any translation key, or breaking any page's direction, fails CI before review.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [x] T043 [P] Run the calibration step (`npm run lint:calibration`) and record the catch rate in `findings.md` audit-closure notes. Confirm ≥ 19 / 20 (SC-003).
- [x] T044 [P] Walk through every primary task per SC-005 (sign up → create debt → accept / request-edit → mark paid → confirm payment → notifications → settings) in Arabic and verify zero English-language artifacts on any visible surface. Capture remaining Minor cosmetic findings in `findings.md`.
- [x] T045 [P] Confirm SC-006 manually: time the locale toggle on the dashboard with multiple visible surfaces (toast open, dialog open, navigation expanded). Must update every visible surface within 1 second on a standard dev build.
- [x] T046 Update `docs/project-status.md`: flip "Polished bilingual UI" → ✅ once `findings.md` shows zero `Blocker` / `Major` rows with status `open` and every `backend-leak` row has a non-empty `owner` and `link` (per FR-009a / SC-009).
- [x] T047 [P] Update `docs/spec-kit/implementation-plan.md` Phase 5 references from the placeholder branch `005-bilingual-coverage-audit` to the actual branch `004-bilingual-coverage-audit`.
- [x] T048 [P] Run `quickstart.md` end-to-end (anonymous flow, authenticated flow, per-page sweep, lint, tests) on a fresh checkout to validate the audit is reproducible.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately.
- **Foundational (Phase 2)**: Depends on Setup. **Blocks all user-story phases** because every story relies on the working locale toggle and the `<html lang dir>` plumbing. T005 (migration) blocks T009 + T010; T006/T007/T008 are parallel and all block T009; T011/T012 are parallel and both block T013 → T014.
- **Phase 3 (US1+US2)**: Depends on Foundational (T014 in particular — without `<html lang dir>` working the manual walkthrough cannot verify direction). T032 depends on T016–T031.
- **Phase 4 (US3)**: Depends on Setup (T001, T003) only. **Can run in parallel with Phase 3** — the lint rule is independent of the per-page sweep, and seeding the lint config early is helpful so the sweep does not introduce new violations.
- **Phase 5 (US4)**: Depends on Setup (T002, T003) and Foundational (T014). **Can run in parallel with Phase 3 and Phase 4** once Foundational is done. T041 depends on T038 + T039.
- **Phase 6 (Polish)**: Depends on Phases 3, 4, 5 being substantively complete.

### User Story Dependencies

- **US1 + US2 (P1)**: Symmetric; share the sweep tasks (T016–T032). Independently testable per locale via the manual walkthrough.
- **US3 (P2)**: Independent of US1/US2 — the lint rule does not assume the sweep is done; it just prevents new regressions. Can ship before the sweep is complete (existing repo will fail until T016–T032 land, which is the desired behavior).
- **US4 (P3)**: Depends on the AR/EN keysets being usable (Foundational + minimal `i18n.ts`). The parity test (T040) starts passing as soon as the existing keys are balanced.

### Within Each User Story

- **Phase 3**: T016–T029 are parallel (different files); T030 (CSS) and T031 (metadata) can run alongside; T032 must run last.
- **Phase 4**: T033 first; T034–T036 in parallel; T037 last.
- **Phase 5**: T038–T040 in parallel; T041 after T038 + T039; T042 last.

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel (T001, T002, T004).
- Foundational schema/repo tasks T006–T008 are parallel; T010, T011, T012, T015 are parallel.
- Phase 3 sweep tasks T016–T029 are 14-way parallel (different files).
- Phase 4 sub-tasks T034–T036 parallel after T033 is in place.
- Phase 5 sub-tasks T038–T040 parallel; T041 sequential.
- Polish tasks T043–T048 are mostly parallel except T046 which depends on the rest.

---

## Parallel Example: Phase 2 Foundational (after T005)

```text
# Backend schema + repo plumbing — 4 different files, no ordering between them:
Task: "Update Profile schema in backend/app/schemas/domain.py"               # T006
Task: "Round-trip preferred_language in backend/app/repositories/memory.py"   # T007
Task: "Round-trip preferred_language in backend/app/repositories/postgres.py" # T008
Task: "Add backend test in backend/tests/test_profile_locale.py"              # T010

# Frontend type + helper plumbing — also parallel:
Task: "Mirror Profile.preferred_language in frontend/src/lib/types.ts"        # T011
Task: "Add frontend/src/lib/localePersistence.ts"                             # T012
Task: "Add formatDate/formatCurrency helpers to frontend/src/lib/i18n.ts"     # T015
```

## Parallel Example: Phase 3 sweep

```text
# 14 page/component sweeps, all on different files — fully parallelizable:
Task: "Sweep frontend/src/pages/LandingPage.tsx"             # T016
Task: "Sweep frontend/src/pages/AuthPage.tsx"                # T017
Task: "Sweep frontend/src/pages/DashboardPage.tsx"           # T018
Task: "Sweep frontend/src/pages/DebtsPage.tsx"               # T019
Task: "Sweep frontend/src/pages/QRPage.tsx"                  # T020
Task: "Sweep frontend/src/pages/NotificationsPage.tsx"       # T021
Task: "Sweep frontend/src/pages/ProfilePage.tsx"             # T022
Task: "Sweep frontend/src/pages/SettingsPage.tsx"            # T023
Task: "Sweep frontend/src/pages/GroupsPage.tsx"              # T024
Task: "Sweep frontend/src/pages/AIPage.tsx"                  # T025
Task: "Sweep frontend/src/components/Layout.tsx"             # T026
Task: "Sweep frontend/src/components/AttachmentUploader.tsx" # T027
Task: "Sweep frontend/src/components/CancelDebtDialog.tsx"   # T028
Task: "Sweep frontend/src/components/ProtectedRoute.tsx"     # T029
```

---

## Implementation Strategy

### MVP First (Phase 1 + Phase 2 + Phase 3)

1. Setup (T001–T004).
2. Foundational (T005–T015).
3. AR/EN coverage sweep (T016–T032).
4. **STOP and VALIDATE**: manual walkthrough in both locales per `quickstart.md` confirms zero Blockers and zero Majors. This is the demo-ready state — Arabic-first + English UI both fully functional.

### Incremental Delivery

1. MVP above → demo (Polished bilingual UI minus durable guardrail).
2. Add US3 (T033–T037) → prevents regressions on every future PR.
3. Add US4 (T038–T042) → catches missing keys and broken direction in CI.
4. Polish (T043–T048) → flip `project-status.md`, run calibration, update Phase-5 references, close audit.

### Parallel Team Strategy

- **Developer A** (after Foundational): drives the Phase 3 sweep across pages.
- **Developer B** (after Setup): drives Phase 4 lint + custom rule + calibration fixtures.
- **Developer C** (after Foundational): drives Phase 5 test infrastructure + parity + locale-coverage tests.
- All converge in Phase 6 for the audit-closure walk and `project-status.md` flip.

---

## Notes

- [P] tasks operate on different files with no dependencies on incomplete tasks in the same phase.
- [Story] labels (US1/US2/US3/US4) are present on every task in Phases 3–5; Setup, Foundational, and Polish tasks intentionally have no story label.
- The audit's success criteria SC-001..SC-009 map to: SC-001 → T016–T031 + T044; SC-002 → T040; SC-003 → T036 + T043; SC-004 → T037 + T042; SC-005 → T044; SC-006 → T045; SC-007 → T038 + T042; SC-008 → T035; SC-009 → T046.
- Constitution principle VII (schemas single source of truth) is enforced by T005 + T006 + T011 landing in the same PR (or at least the same coordinated push). Reviewers should reject any partial drift.
- Findings tracking lives in `specs/004-bilingual-coverage-audit/findings.md` (T004); audit closure (T046) reads it.
