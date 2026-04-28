# Feature Specification: Bilingual Coverage Audit (AR/EN)

**Feature Branch**: `004-bilingual-coverage-audit`
**Created**: 2026-04-28
**Status**: Draft
**Input**: User description: "Phase 5 — Bilingual coverage audit (AR/EN). Audit every visible string in the frontend against the i18n string sink. No hardcoded English or Arabic strings may remain outside that file. Both locales must render with correct RTL/LTR direction, including form inputs, dialogs, toasts, and date/number formatting. Linting/CI must prevent regressions."

## Clarifications

### Session 2026-04-28

- Q: What surfaces count as "user-visible strings" for the audit and lint rule? → A: Everything an end user perceives — JSX text, button labels, placeholders, validation messages, toasts, dialog content, plus `aria-label`/`aria-describedby`, `alt` text, `<title>`/`document.title`, `<meta name="description">`, OG tags, `<input title>`, and image captions. Only pure code identifiers (test ids, asset paths, route keys, icon names, code-only error keys) are exempt via the documented escape hatch.
- Q: Which pages are in scope? → A: All pages, including the landing/marketing page, password-reset and email-confirmation flows, QR-scan landing pages, and any share/deep-link entry pages — all must be fully bilingual. There are no excluded pages.
- Q: Do backend-leaked user-visible strings block the audit from being marked complete? → A: No. The audit is marked complete once all frontend findings are resolved AND every backend-leak finding is filed as a tracked defect with a named owner. Backend fixes may land after the audit is closed.
- Q: How are findings prioritized for CI vs. manual audit closure? → A: Three severity tiers. Blocker: hardcoded user-visible literal, `missing.key.*` artifact, wrong document direction. Major: missing-key parity defect, broken bidirectional rendering, untranslated assistive-tech surface (`aria-*`, `alt`, `<title>`, meta tags). Minor: cosmetic RTL/LTR misalignment, mirrored-icon polish. CI blocks Blockers; manual audit closure requires Blockers + Majors resolved; Minors are tracked but non-blocking.
- Q: How is locale persisted across sessions and devices? → A: User-profile-persisted when authenticated and synced across devices; falls back to browser-local persistence (`localStorage`) when anonymous; defaults to Arabic when neither is set. A signed-in user updating their locale on one device sees it applied on other devices on next load.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Arabic-first user sees a fully Arabic UI with correct RTL behavior (Priority: P1)

A native Arabic-speaking creditor or debtor opens Thabetha with Arabic selected. Every label, button, table column, dialog, toast, navigation item, and inline helper text appears in fluent Arabic. The whole layout flips to right-to-left: text aligns to the right, icons mirror where appropriate (chevrons, back arrows), form input carets sit on the right edge, and tables read right-to-left. Dates and currency render in locale-appropriate forms (e.g., Gregorian dates with Arabic numerals where the locale dictates, SAR currency with Arabic-aware formatting).

**Why this priority**: Arabic-first is the product's core differentiator (per constitution §5 and CLAUDE.md). A leaking English string or a misaligned RTL element on a primary screen breaks trust with the target user immediately and is the most visible regression risk during demos and onboarding.

**Independent Test**: Switch the language to Arabic, walk through every page reachable from the role-aware navigation (creditor, debtor, both), and confirm zero English-language artifacts and visually correct RTL layout. This can be verified end-to-end without depending on any other story.

**Acceptance Scenarios**:

1. **Given** a user with locale set to Arabic, **When** they navigate to any page reachable from the navigation drawer, **Then** every visible string is rendered from the Arabic translations and no `missing.key.*` placeholder or untranslated English literal appears.
2. **Given** a user with locale set to Arabic, **When** they open a form (e.g., create debt, settings), **Then** input alignment, caret position, and field/label order follow RTL reading order.
3. **Given** a user with locale set to Arabic, **When** a dialog, toast, or confirmation modal appears, **Then** its content, action buttons, and close affordance are translated and laid out RTL.
4. **Given** a user with locale set to Arabic, **When** a date or amount is shown, **Then** it is formatted using the active locale's conventions and SAR currency renders correctly.

---

### User Story 2 - English user sees a fully English UI with correct LTR behavior (Priority: P1)

A user who selects English sees every visible string in fluent English with left-to-right layout. No leftover Arabic characters appear on shared components, charts, or modals. Dates and currency render in English locale conventions.

**Why this priority**: English is the product's secondary supported language and the demo language for non-Arabic stakeholders (judges, investors, partners). Leaking Arabic into the English UI breaks demos as severely as the inverse.

**Independent Test**: Switch the language to English and walk through every page; confirm zero Arabic artifacts and visually correct LTR layout. Can be verified independently of the Arabic flow.

**Acceptance Scenarios**:

1. **Given** a user with locale set to English, **When** they navigate any page, **Then** every visible string renders in English with no Arabic characters and no `missing.key.*` artifacts.
2. **Given** a user with locale set to English, **When** they switch from Arabic to English mid-session, **Then** the layout direction flips to LTR and all previously rendered components re-render in English without requiring a full page reload.

---

### User Story 3 - Developer is prevented from introducing hardcoded strings (Priority: P2)

A developer adds a new component or page and accidentally types a raw English or Arabic literal directly into JSX (instead of routing through the translation sink). Local linting and CI fail with a clear, actionable message pointing to the offending file, line, and recommended fix (move the string to the translation sink and use a translation key).

**Why this priority**: Without this guard, the audit decays the moment new features land. The lint guardrail is what makes the audit durable. It is P2 because it does not directly affect end users today, only future regressions.

**Independent Test**: Open a clean branch, add a JSX element with a raw string literal in a page or component file, run the project's lint command and CI; both must fail with a translation-related rule.

**Acceptance Scenarios**:

1. **Given** a JSX file under the pages or components directory, **When** a raw string literal is added inside JSX, **Then** the lint command exits non-zero and identifies the file, line, and rule name.
2. **Given** an intentional non-translatable literal (e.g., a `data-testid` value, an icon name, a code identifier), **When** the developer applies the documented escape hatch, **Then** lint passes without re-introducing risk on real user-facing strings.
3. **Given** a pull request that adds a raw user-visible string, **When** CI runs, **Then** the build fails on the same rule before review.

---

### User Story 4 - QA can verify both locales automatically per page (Priority: P3)

A QA engineer or developer runs the frontend test suite and gets per-page coverage that asserts both locales render without missing keys, in the correct direction, on every primary page. Automated tests catch the most common regressions (a translation key removed, a new key added in only one language, a page accidentally rendering the wrong direction) before they reach a manual reviewer.

**Why this priority**: Automated locale tests are valuable but the manual audit (US1, US2) and the lint guard (US3) prevent most regressions. Per-page locale tests are the safety net.

**Independent Test**: Run the frontend test command. Tests for each primary page exercise both locales and assert the rendered output contains no missing-key placeholders and the document direction matches the locale.

**Acceptance Scenarios**:

1. **Given** the frontend test suite, **When** a translation key is removed from one locale only, **Then** at least one test fails with a message that names the missing key.
2. **Given** the frontend test suite, **When** a page is rendered in Arabic, **Then** a test asserts the page's effective document direction is RTL.

---

### Edge Cases

- A user switches language while a toast or dialog is already open — the open surface must update or close cleanly without leaving stale-language text on screen.
- A backend response leaks a user-visible string (e.g., a raw error message) — must be flagged as a separate bug, not silently translated. The frontend should display a generic, translated fallback for unknown error codes.
- A string contains an interpolated value (a name, an amount, a date) — the interpolation must respect the locale's formatting and direction (numbers, currency symbols, date order).
- A page contains a chart, table, or data visualization — axis labels, legends, tooltips, and column headers must all be translated and the chart's reading direction should match the locale where applicable.
- A user lands on a deep-link-only page (password reset, email confirmation, QR-scan landing, share/invite link) — that page must render fully bilingually with correct RTL/LTR behavior, the same as any nav-reachable page.
- A new language is added later — the audit's structure (single string sink, lint rule, per-page tests) must extend without per-page rewrites.
- A right-to-left rendering inside a left-to-right container (or vice-versa) — bidirectional text segments (e.g., a Latin proper noun inside an Arabic sentence) must render with correct neutral-character handling and not break alignment.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The frontend MUST source every user-visible string from a single translation sink that defines both Arabic and English values for every key. "User-visible string" includes, at minimum: JSX text nodes, button labels, placeholders, form validation messages, toasts, dialog content, `aria-label` and `aria-describedby` values, `alt` text, `<title>` / `document.title`, `<meta name="description">`, OpenGraph/social meta tags, `<input title>`, and image captions.
- **FR-002**: No page or component file MUST contain a hardcoded user-visible Arabic or English string literal — including the assistive-tech and document-metadata surfaces enumerated in FR-001 — in JSX or in JSX-adjacent props (e.g., `aria-*`, `alt`, page-title setters). Only pure code identifiers (test ids, asset paths, route keys, icon names, code-only error keys) are exempt via a documented escape hatch.
- **FR-003**: When the active locale is Arabic, the application MUST render with right-to-left document direction, including text alignment, list/table reading order, form inputs (caret and label/field order), navigation drawers, dialogs, and toasts.
- **FR-004**: When the active locale is English, the application MUST render with left-to-right document direction across the same surfaces.
- **FR-005**: The application MUST format dates using locale-aware date formatting keyed on the active locale, restricted to the Gregorian calendar for this audit.
- **FR-006**: The application MUST format numbers and SAR currency using locale-aware number formatting keyed on the active locale.
- **FR-007**: Switching the locale MUST update every currently visible surface (pages, open dialogs, toasts, navigation) to the new language and direction without requiring a full reload.
- **FR-007a**: The user's locale preference MUST be persisted on the authenticated user's profile and applied on first paint of every authenticated session, including from a different device. For unauthenticated visitors, the preference MUST be persisted in browser-local storage so a returning visitor on the same device sees their last-chosen locale on first paint. When neither a profile preference nor a browser-local preference is set, the application MUST default to Arabic.
- **FR-008**: A static check (lint rule or equivalent automated repository check) MUST fail when a raw user-visible string literal — as defined in FR-001 — is introduced in a JSX file under the pages or components directories, including in `aria-*`, `alt`, document-title, and meta-tag props.
- **FR-009**: The static check MUST be enforced in continuous integration, blocking merges that introduce any Blocker-tier finding (hardcoded user-visible literal, `missing.key.*` artifact, wrong document direction). Major and Minor findings are tracked but do not block CI.
- **FR-009a**: The audit is marked complete once every Blocker- and Major-tier finding is resolved (frontend findings) or filed as a tracked defect with a named owner (backend-leak findings). Minor-tier findings are tracked separately and do not gate audit closure.
- **FR-010**: The translation sink MUST contain the same set of keys for both locales; any key present in only one locale MUST be detected as a defect.
- **FR-011**: The application MUST never display `missing.key.*` placeholder artifacts to users in either locale on any page reachable from the role-aware navigation.
- **FR-012**: A documented escape hatch MUST exist for legitimate non-translatable string literals — limited to test ids, asset paths, route keys, icon names, and code-only error keys — so developers can satisfy the lint rule without bypassing it on user-visible strings.
- **FR-013**: Each primary page MUST have an automated test that renders the page in both locales and asserts no missing-key artifact and the document direction matches the locale.
- **FR-014**: The audit's scope MUST cover every page in the frontend, including pages reachable only via deep links (auth callbacks such as password reset and email confirmation, QR-scan landing pages, and share/invite entry pages) and the landing/marketing page. There are no intentionally excluded pages.
- **FR-015**: Backend-originated user-visible text leaking through to the UI without translation MUST be detectable during the audit; each such instance MUST be filed as a tracked defect with a named owner rather than worked around in the frontend. The audit MAY be marked complete once all frontend findings are resolved and every backend-leak finding has been filed and assigned, even if the backend fix has not yet landed.
- **FR-016**: Bidirectional text (e.g., Latin names or numbers embedded in Arabic strings, or vice-versa) MUST render with correct neutral-character handling and without breaking line alignment in either locale.

### Key Entities

- **Translation key**: A stable identifier referenced by code that resolves to one Arabic value and one English value. Owns its key name, two locale values, and the set of components that reference it.
- **Locale**: The user's selected language. Determines which translation values are read, the document direction (RTL or LTR), and the formatting rules for dates and numbers. Persisted on the authenticated user profile (synced across devices) with a browser-local fallback for unauthenticated visitors and an Arabic default when neither is set.
- **Page**: A top-level route surface in scope of the audit. Owns its locale-test coverage, its set of referenced translation keys, and its scope status (in scope / explicitly excluded with rationale).
- **Audit finding**: A defect produced by the audit (hardcoded literal, missing key in one locale, broken RTL/LTR layout, leaked backend string). Owns location (file or surface), category, severity tier, and resolution status. Severity tiers are: **Blocker** — hardcoded user-visible literal, `missing.key.*` artifact, or wrong document direction; **Major** — missing-key parity defect, broken bidirectional rendering, or untranslated assistive-tech / document-metadata surface (`aria-*`, `alt`, `<title>`, meta tags); **Minor** — cosmetic RTL/LTR misalignment or mirrored-icon polish.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of pages defined as routes in the frontend (including deep-link-only and marketing pages) render in both Arabic and English with zero hardcoded literals and zero `missing.key.*` artifacts during a manual walkthrough.
- **SC-002**: The translation sink has identical key coverage in Arabic and English (zero keys present in one locale only).
- **SC-003**: The lint/static check catches at least 95% of synthetically introduced raw JSX strings in a calibration sample of 20 deliberately seeded violations across pages and components.
- **SC-004**: A pull request that introduces a raw user-visible string literal fails CI before human review in 100% of cases, measured over the first 10 PRs after enforcement is enabled.
- **SC-005**: An Arabic-first user can complete each primary task (sign up, create a debt, accept/request-edit a debt, mark paid, confirm payment, view notifications, change settings) without encountering a single English-language artifact on any visible surface.
- **SC-006**: Switching the locale at runtime updates every currently visible surface to the target language and direction within 1 second on a standard development build, with no leftover stale-language text on dialogs, toasts, or navigation.
- **SC-007**: Automated locale tests cover every page listed as in-scope and run in under 60 seconds locally and in CI, so the audit remains a routine guardrail rather than a release-blocking effort.
- **SC-008**: Reviewers can confirm any new feature ships with translations by reading the diff alone — no PR ever passes review with a translation TODO or a placeholder string.
- **SC-009**: At audit close, 100% of frontend findings are resolved and 100% of backend-leak findings are filed as tracked defects with a named owner; zero findings remain in an unfiled or unassigned state.

## Assumptions

- The product remains Arabic-first and English-secondary for the foreseeable future. Adding additional locales is out of scope for this audit but the structure should accommodate it.
- The Hijri calendar is **out of scope** for this phase. Dates are formatted Gregorian-only.
- The audit covers every page in the frontend with no intentional exclusions. The landing/marketing page, auth callbacks (password reset, email confirmation), QR-scan landings, and share/deep-link entry pages are all fully bilingual.
- Backend error messages are returned as codes; user-visible translation happens on the frontend. Any backend-produced user-visible English/Arabic string leaking through is a defect filed separately and not silently translated.
- The existing translation sink is the single source of truth for translations. Adopting a different translation library or splitting the sink is out of scope.
- The page list to audit is "every page that can be rendered to a user" — derived by enumerating route definitions in the frontend, not just role-aware navigation entries. Deep-link-only pages are included.
- Right-to-left support is provided by the platform's standard direction handling; no custom bidirectional algorithm is required beyond correctly setting the document direction and using direction-aware components for inputs, drawers, and dialogs.
- The lint and CI tooling already used by the repository is extensible enough to add a JSX-string rule without a new build pipeline.
- Currency in scope is SAR. Multi-currency formatting is out of scope.
