import { describe, it, expect } from 'vitest';
import { _getTranslationKeys } from '../src/lib/i18n';

// TypeScript's `Translations = Record<TranslationKey, string>` already enforces at compile
// time that every key in the union is present in both `ar` and `en`. This test documents
// that contract at runtime and catches any drift that might bypass TypeScript
// (e.g., a runtime-generated dictionary, a JSON override, or a build-time strip).

describe('i18n key parity', () => {
  it('AR and EN translation dictionaries contain identical key sets', () => {
    const arKeys = new Set(_getTranslationKeys('ar'));
    const enKeys = new Set(_getTranslationKeys('en'));

    const onlyInAr = [...arKeys].filter((k) => !enKeys.has(k));
    const onlyInEn = [...enKeys].filter((k) => !arKeys.has(k));

    expect(
      onlyInAr,
      `Keys present in AR but missing in EN: ${onlyInAr.join(', ')}`,
    ).toHaveLength(0);

    expect(
      onlyInEn,
      `Keys present in EN but missing in AR: ${onlyInEn.join(', ')}`,
    ).toHaveLength(0);
  });

  it('neither locale has an empty dictionary', () => {
    expect(_getTranslationKeys('ar').length).toBeGreaterThan(0);
    expect(_getTranslationKeys('en').length).toBeGreaterThan(0);
  });
});
