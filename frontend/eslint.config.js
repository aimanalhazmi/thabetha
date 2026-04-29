// i18n Suppression Policy:
// Inline eslint-disable on a specific line requires a paired justification comment:
//   // i18n-allowlisted: <reason>
// Allowed exemptions (E1-E6): data-testid and other data-* attrs, asset paths in src/href/srcSet,
// route paths in react-router `to` props, lucide-react icon component names, code-only API error
// keys, and single punctuation/delimiter tokens in allowedStrings below.
// Any suppression without an i18n-allowlisted comment fails the lint:suppressions-justified check.

import typescriptParser from '@typescript-eslint/parser';
import typescriptPlugin from '@typescript-eslint/eslint-plugin';
import reactPlugin from 'eslint-plugin-react';
import jsxA11yPlugin from 'eslint-plugin-jsx-a11y';
import noUntranslatedJsxRule from './eslint-rules/no-untranslated-jsx.js';

export default [
  {
    ignores: ['dist/**', 'build/**', 'coverage/**', 'node_modules/**', '*.min.js'],
  },
  {
    files: ['src/**/*.{ts,tsx}', 'tests/**/*.{ts,tsx}'],
    languageOptions: {
      parser: typescriptParser,
      parserOptions: {
        ecmaVersion: 2022,
        sourceType: 'module',
        ecmaFeatures: { jsx: true },
      },
      globals: {
        document: 'readonly',
        window: 'readonly',
        console: 'readonly',
        setTimeout: 'readonly',
        clearTimeout: 'readonly',
        localStorage: 'readonly',
        fetch: 'readonly',
        URL: 'readonly',
        navigator: 'readonly',
        File: 'readonly',
        FileList: 'readonly',
        FormData: 'readonly',
        HTMLInputElement: 'readonly',
        HTMLElement: 'readonly',
        process: 'readonly',
      },
    },
    plugins: {
      '@typescript-eslint': typescriptPlugin,
      react: reactPlugin,
      'jsx-a11y': jsxA11yPlugin,
      local: {
        rules: {
          'no-untranslated-jsx': noUntranslatedJsxRule,
        },
      },
    },
    settings: {
      react: { version: 'detect' },
    },
    rules: {
      '@typescript-eslint/no-unused-vars': ['warn', { argsIgnorePattern: '^_' }],
      '@typescript-eslint/no-explicit-any': 'off',
      '@typescript-eslint/no-require-imports': 'off',
      'react/react-in-jsx-scope': 'off',
      'react/prop-types': 'off',
      'local/no-untranslated-jsx': 'error',
    },
  },
  {
    // JSX literal guard (L1–L5): user-visible text nodes and common props
    files: [
      'src/pages/**/*.{ts,tsx}',
      'src/components/**/*.{ts,tsx}',
      'tests/lint-calibration.fixtures/**/*.{ts,tsx}',
    ],
    rules: {
      'react/jsx-no-literals': [
        'error',
        {
          noStrings: true,
          allowedStrings: [' ', ' / ', ' · ', ':', '—', '…', '(', ')', '{', '}', '→', '✓', '✕', '⚠️', '····', '/100', '/ 100', '/200'],
          ignoreProps: true,
        },
      ],
    },
  },
];
