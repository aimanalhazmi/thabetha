import type { Language } from './types';
import { apiRequest } from './api';

const STORAGE_KEY = 'thabetha.locale';

/** Read locale in priority order: profile → localStorage → 'ar' default. */
export function loadInitialLocale(preferredLanguage?: string): Language {
  if (preferredLanguage === 'ar' || preferredLanguage === 'en') return preferredLanguage;
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored === 'ar' || stored === 'en') return stored;
  return 'ar';
}

/** Persist the locale locally and, if signed-in, sync to the user profile. */
export async function persistLocale(next: Language, signedIn: boolean): Promise<void> {
  localStorage.setItem(STORAGE_KEY, next);
  if (signedIn) {
    try {
      await apiRequest('/profiles/me', {
        method: 'PATCH',
        body: JSON.stringify({ preferred_language: next }),
      });
    } catch {
      // Sync failure is non-critical — localStorage already updated.
    }
  }
}
