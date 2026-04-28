# Contract — Static-check (lint) rule

This contract specifies what the lint guard must catch (Blocker findings) and what it must allow (the documented escape hatch). It is enforceable by `npm run lint` locally and in CI.

## Must fail (Blocker findings)

The rule MUST emit a lint error and exit non-zero when any of the following appear in a file under `frontend/src/pages/` or `frontend/src/components/`:

| # | Pattern | Example |
|---|---|---|
| L1 | A bare string-literal child of a JSX element | `<button>Submit</button>` |
| L2 | A bare string-literal value for `aria-label`, `aria-describedby`, `aria-placeholder`, `aria-roledescription`, `aria-valuetext` | `<button aria-label="Close" />` |
| L3 | A bare string-literal value for `alt` on `<img>` | `<img alt="Profile photo" />` |
| L4 | A bare string-literal value for `title` (on any element) | `<input title="Required" />` |
| L5 | A bare string-literal value for `placeholder` | `<input placeholder="Enter amount" />` |
| L6 | A bare string-literal child of `<title>` (page title) | `<title>Dashboard</title>` |
| L7 | A bare string-literal value for `content` on `<meta name="description">` and OpenGraph `<meta property="og:*">` | `<meta name="description" content="Track debts" />` |
| L8 | A bare string-literal RHS of `document.title = "..."` | `document.title = 'Dashboard';` |
| L9 | A template literal containing user-visible text without any expression interpolation, in any of the above positions | `<button>{"\`Submit\`"}</button>` |

The rule is locale-agnostic — it fires on any text containing letters, including Arabic text. Numeric-only and punctuation-only literals (`<span>:</span>`, `<button>1</button>`) are allowed.

## Must pass (escape hatch)

The rule MUST allow the following — these are pure code identifiers, not user-visible text:

| # | Pattern | Example |
|---|---|---|
| E1 | `data-testid` and other `data-*` attributes | `<button data-testid="submit-button" />` |
| E2 | Asset paths (URLs, file paths) in `src`, `href`, `srcSet` | `<img src="/logo.svg" />` |
| E3 | Route keys / paths in `react-router-dom` `to` props | `<Link to="/dashboard" />` |
| E4 | Icon names from `lucide-react` (component imports, not string props) | `<Settings />` |
| E5 | Code-only error keys (string codes returned by the API and translated client-side via `t(`error.${code}`)`) | `t(\`error.${code}\`)` |
| E6 | Strings inside an `eslint-disable-next-line` block, with a required justification comment | `// i18n-allowlisted: data-testid value` |

Keys allowed via `react/jsx-no-literals`'s `allowedStrings` array (e.g., punctuation tokens used as content delimiters):

- `' '`, `' / '`, `' · '`, `':'`, `'—'`, single Unicode dash variants used decoratively.

## Severity behavior

- All L1–L9 violations are **Blocker** findings (per spec FR-009).
- Major and Minor findings (untranslated assistive-tech surfaces caught by other audits, RTL/LTR cosmetic) are tracked in `findings.md`, **not** by this lint rule.

## Exit codes

- `0` — no L1–L9 violations.
- Non-zero — at least one violation; CI MUST block the merge.

## Calibration test

A separate test file `frontend/tests/lint-calibration.fixtures/` contains 20 deliberate violations spanning L1–L9. CI runs `npm run lint -- --no-error-on-unmatched-pattern frontend/tests/lint-calibration.fixtures/` separately and asserts the violation count is ≥ 19 (≥ 95% catch rate, SC-003). This calibration step does NOT block CI; it produces a metric for the audit closure report.

## Suppression policy

Inline suppression comments (`// eslint-disable-next-line react/jsx-no-literals`) are permitted only with a justification comment naming the exempt category (`// i18n-allowlisted: <reason>`). PR review MUST reject suppressions without a justification. A repo-grep CI step counts suppressions and fails the audit closure if it finds an unjustified one (this step belongs to the audit report tooling, not to the lint rule itself).
