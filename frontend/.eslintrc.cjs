// i18n Suppression Policy:
// Inline eslint-disable on a specific line requires a paired justification comment:
//   // i18n-allowlisted: <reason>
// Allowed exemptions (E1-E6): data-testid and other data-* attrs, asset paths in src/href/srcSet,
// route paths in react-router `to` props, lucide-react icon component names, code-only API error
// keys, and single punctuation/delimiter tokens in allowedStrings below.
// Any suppression without an i18n-allowlisted comment fails the lint:suppressions-justified check.

'use strict';

module.exports = {
  root: true,
  parser: '@typescript-eslint/parser',
  parserOptions: {
    ecmaVersion: 2022,
    sourceType: 'module',
    ecmaFeatures: { jsx: true },
  },
  plugins: ['@typescript-eslint', 'react', 'jsx-a11y'],
  extends: [
    'plugin:react/recommended',
    'plugin:react/jsx-runtime',
    'plugin:jsx-a11y/recommended',
    'plugin:@typescript-eslint/recommended',
  ],
  settings: {
    react: { version: 'detect' },
  },
  rulePaths: ['./eslint-rules'],
  rules: {
    'no-untranslated-jsx': 'error',
    // Disable rules that fire on legitimate patterns in this codebase
    '@typescript-eslint/no-explicit-any': 'off',
    'react/prop-types': 'off',
  },
  overrides: [
    {
      // ── JSX literal guard (L1 – L5): user-visible text nodes and common props ──
      files: ['src/pages/**/*.{ts,tsx}', 'src/components/**/*.{ts,tsx}'],
      rules: {
        'react/jsx-no-literals': [
          'error',
          {
            noStrings: true,
            allowedStrings: [' ', ' / ', ' · ', ':', '—', '…', '(', ')', '{', '}'],
            ignoreProps: false,
          },
        ],
      },
    },
  ],
};
