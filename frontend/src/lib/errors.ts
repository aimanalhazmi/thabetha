import { t } from './i18n';
import type { Language } from './types';

export type ErrorContext =
  | 'loadDebts'
  | 'loadDashboard'
  | 'loadNotifications'
  | 'transition'
  | 'qrResolve'
  | 'generic';

const STATUS_CONTEXT_MAP: Record<string, Record<string, Parameters<typeof t>[1]>> = {
  loadDebts: { default: 'errorLoadDebts' },
  loadDashboard: { default: 'errorLoadDashboard' },
  loadNotifications: { default: 'errorLoadNotifications' },
  transition: { '409': 'errorTransitionStateChanged', '403': 'errorTransitionForbidden', default: 'errorGeneric' },
  qrResolve: { '404': 'qrExpiredAskRefresh', '410': 'qrExpiredAskRefresh', default: 'errorGeneric' },
  generic: { default: 'errorGeneric' },
};

/** Parse the status code from an apiRequest-thrown Error ("STATUS: body"). */
function parseStatus(err: unknown): string | null {
  if (!(err instanceof Error)) return null;
  const match = /^(\d{3}):/.exec(err.message);
  return match ? match[1] : null;
}

/**
 * Convert an apiRequest error into a translated user-facing string.
 * Never throws — falls back to errorGeneric on any failure.
 */
export function humanizeError(err: unknown, language: Language, context: ErrorContext = 'generic'): string {
  try {
    const status = parseStatus(err);
    const map = STATUS_CONTEXT_MAP[context] ?? STATUS_CONTEXT_MAP['generic'];
    const key = (status && map[status]) ? map[status] : map['default'];
    return t(language, key as Parameters<typeof t>[1]);
  } catch {
    return t(language, 'errorGeneric');
  }
}
