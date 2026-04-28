# Phase 0 — Research: Bilingual Coverage Audit (AR/EN)

This document resolves every tooling and approach decision the spec deferred to planning. There were no `NEEDS CLARIFICATION` markers; the items below are best-practice consolidations to lock in choices before Phase 1 design.

---

## R1. Static check — which lint rule catches raw JSX strings?

**Decision**: Use **`eslint-plugin-react`'s `react/jsx-no-literals`** as the primary rule, configured with our project's exempt-set (test ids, asset paths, route keys, icon names, code-only error keys), supplemented by **`eslint-plugin-jsx-a11y`** for assistive-tech surfaces. If `react/jsx-no-literals` does not cover string-valued props (`aria-label`, `alt`, `title`, `<meta content>`, `document.title` setters) tightly enough, add a **small custom rule** at `frontend/eslint-rules/no-untranslated-jsx.js` that fails on string-literal RHS for an explicit prop allowlist.

**Rationale**:

- `react/jsx-no-literals` is community-maintained, supports `noStrings`/`allowedStrings`/`ignoreProps`, and is already tuned for React 19 / TS.
- An off-the-shelf rule beats a bespoke one for the 80% case; a tiny custom rule is acceptable for the assistive-tech surfaces because there is no generic ESLint rule that says "no string literal in `aria-label` / `alt` / `title` / etc."
- Keeps the dependency footprint minimal (no `i18next`-specific tooling, since we don't use `i18next`).

**Alternatives considered**:

- `eslint-plugin-i18next` — assumes `i18next` runtime, which we don't use. Rejected.
- `eslint-plugin-formatjs` — same, plus FormatJS-specific. Rejected.
- Pure-bash `grep` step in CI — fragile against TypeScript syntax (template literals, JSX expressions). Rejected.
- Custom-only rule — duplicates `react/jsx-no-literals`. Rejected.

**Calibration**: Seed 20 deliberate violations (raw text in JSX, raw `aria-label`, raw `alt`, raw `<title>` child, raw meta `content`, hardcoded validation message, hardcoded toast string, hardcoded placeholder, raw `document.title=` assignment, raw locale-bound date string) across pages and components, run `npm run lint`, expect ≥ 19 / 20 caught (SC-003 ≥ 95%).

---

## R2. Test framework — which to add for per-page locale render tests?

**Decision**: Add **Vitest** + **@testing-library/react** + **jsdom**. Single new dev-dep stack, zero new runtime deps.

**Rationale**:

- Vitest is the natural fit for a Vite project — same config pipeline, same TypeScript handling, near-zero setup cost.
- Testing Library's `render` + `screen.queryByText(/missing\.key\./)` gives a one-liner for the missing-key assertion (FR-011).
- `jsdom` is sufficient for our needs; we are not testing visual RTL rendering pixel-perfectly, only the document direction and content presence.

**Alternatives considered**:

- Playwright (real browser) — overkill for the assertions we need; CI would balloon past the 60 s budget (SC-007). Rejected for this audit; remains a fit for future visual-regression work.
- Jest — works but duplicates the toolchain Vite already provides; slower start; weaker default ESM/TS handling. Rejected.

**Test shape**:

```ts
describe.each(ROUTES)('%s', (route) => {
  it.each(['ar', 'en'] as const)('renders without missing-key artifacts in %s', (locale) => {
    const { container } = renderWithLocale(route, locale);
    expect(container.textContent).not.toMatch(/missing\.key\./);
    expect(document.documentElement.dir).toBe(locale === 'ar' ? 'rtl' : 'ltr');
    expect(document.documentElement.lang).toBe(locale);
  });
});
```

A separate `i18n-key-parity.test.ts` enumerates the AR and EN key sets and asserts equality (FR-010, SC-002).

---

## R3. Locale persistence — schema and propagation

**Decision**:

- **Schema**: add `preferred_language text not null default 'ar' check (preferred_language in ('ar','en'))` to `public.profiles` in `008_preferred_language.sql`. Update the `handle_new_user()` trigger to seed the column from `auth.users.raw_user_meta_data->>'preferred_language'` if present, else `'ar'`.
- **Backend**: add the field to `Profile` schema in `backend/app/schemas/domain.py` (`Literal['ar','en']`); both `InMemoryRepository` and `PostgresRepository` round-trip it. Add `PATCH /api/v1/profiles/me` (or extend the existing profile update endpoint) accepting `{ "preferred_language": "ar" | "en" }`. RLS already restricts row updates to `auth.uid() = id`.
- **Frontend**: `localePersistence.ts` exposes `loadInitialLocale()` (reads in order: `profile.preferred_language` if signed in → `localStorage['thabetha.locale']` → `'ar'`) and `setLocale(next)` (writes both stores; if signed in, fires the PATCH; else writes `localStorage` only). `AuthContext` reads on sign-in/sign-up and on profile refresh; `App.tsx` mirrors `lang` and `dir` onto `<html>`.

**Rationale**:

- One column on the existing `profiles` row keeps the change inside the Supabase-first principle; no parallel store.
- `text` (not an enum type) keeps adding a third locale a one-liner (extend the check constraint).
- Default `'ar'` preserves Arabic-first.
- `localStorage` fallback covers QR-landing/share-link flows where the visitor is not yet authenticated.

**Alternatives considered**:

- New `user_preferences` table — over-engineered for one boolean-equivalent field. Rejected.
- Postgres enum type for the language — locks us into a migration when we add a third locale. Rejected.
- `Accept-Language` header–driven default — surprising for users who expect Arabic-first. Rejected as the default but a reasonable signal for an unauthenticated `localStorage`-empty visitor. Out of scope for this phase.

---

## R4. Document direction toggling

**Decision**: Set `lang` and `dir` on the `<html>` element in `App.tsx` (a single `useEffect` keyed on the active locale). Use **CSS logical properties** (`margin-inline-start`, `padding-inline-end`, `text-align: start`, etc.) wherever the existing CSS uses `left`/`right`. Mirror chevrons / back-arrows that are direction-meaningful by appending `rtl:rotate-180` or equivalent via a small CSS rule keyed on `[dir="rtl"]`.

**Rationale**:

- `<html dir>` is the platform-standard signal; every browser handles RTL form-input alignment, caret position, and text alignment automatically when it is set.
- Logical properties are stable and well-supported (Chrome 87+, Firefox 66+, Safari 15+) — well within our supported-browsers floor.
- No CSS-in-JS framework migration needed; the existing `app.css` can absorb logical-property replacements gradually as part of the audit sweep.

**Alternatives considered**:

- Per-component direction props — duplicative; impossible to keep in lockstep. Rejected.
- A CSS-in-JS framework (e.g., styled-components) with theme-driven direction — out of scope. Rejected.
- `react-helmet` for `<html dir>` — extra runtime dep when a `useEffect` does the job. Rejected.

---

## R5. Date and SAR currency formatting

**Decision**: Add `formatDate(value, locale)` and `formatCurrency(value, locale, currency='SAR')` to `frontend/src/lib/i18n.ts`. Both wrap `Intl.DateTimeFormat` and `Intl.NumberFormat`. Gregorian calendar only (per FR-005). Replace every direct date/number `.toString()`/`.toLocaleString()` call site found during the sweep.

**Rationale**:

- Platform `Intl` APIs handle Arabic-Eastern numerals, SAR currency placement, and locale-appropriate separators without extra dependencies.
- A single helper gives the audit one place to spot-check during code review.

**Alternatives considered**:

- `date-fns` / `dayjs` with locale plugins — useful for parsing/manipulation but unnecessary for formatting; we already have `Date` instances. Rejected.

---

## R6. Bidirectional text handling

**Decision**: Wrap interpolated proper-noun and digit segments in `<bdi>` (or use `&#x2068;…&#x2069;` first-strong-isolate characters) at the call sites identified during the sweep. Document the pattern in `quickstart.md` so contributors know when to reach for it.

**Rationale**: Browser-native, zero runtime cost, addresses the "Latin name embedded in an Arabic sentence" edge case (FR-016) without relying on whitespace tricks.

**Alternatives considered**:

- Manual Unicode bidi-override characters everywhere — error-prone, hides intent. Rejected.
- Custom React component — fine, but adds indirection over a one-line `<bdi>` wrapper. Optional; may add later if call sites multiply.

---

## R7. Audit-finding tracking

**Decision**: Track findings in a single Markdown table at `specs/004-bilingual-coverage-audit/findings.md` (created during execution, **not** part of this plan). Columns: id, file/surface, category (literal | missing-key | direction | bidi | metadata | backend-leak), severity (Blocker | Major | Minor), owner, status, link to fix PR / defect ticket. Backend-leak findings link to a tracked defect rather than a fix PR.

**Rationale**: No need for a heavyweight tracker for ≤ 200 expected findings. A diffable Markdown file in the spec directory keeps the audit auditable.

**Alternatives considered**:

- GitHub Issues per finding — heavy for cosmetic items; overkill for the closure rules from Q4. Rejected for in-feature findings; mandatory for backend-leak findings (per Q3).

---

## Summary of choices

| Concern | Choice |
|---|---|
| Lint rule | `react/jsx-no-literals` + `jsx-a11y` + small custom rule for prop allowlist |
| Test framework | Vitest + Testing Library + jsdom |
| Locale persistence | `profiles.preferred_language` (text, default `'ar'`) + `localStorage` fallback |
| Direction toggling | `<html lang dir>` + CSS logical properties |
| Date / currency | `Intl.DateTimeFormat` / `Intl.NumberFormat` via i18n helpers |
| Bidi text | `<bdi>` at interpolation sites |
| Findings log | `specs/004-bilingual-coverage-audit/findings.md` (Markdown table) |

All dependencies are dev-only; zero new runtime deps. Migration count: +1 (`008_preferred_language.sql`).
