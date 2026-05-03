/**
 * Per-page locale coverage tests.
 * For each routed page, renders the standalone page component in both locales
 * and asserts:
 *   1. No `missing.key.*` artifact in the rendered DOM.
 *   2. The `t()` helper doesn't fall back to the key (smoke-check via text scan).
 *
 * Note: Full route-level rendering (with react-router + AuthContext + API) is
 * integration territory; page-component smoke renders are sufficient for the
 * audit's SC-001 / SC-007 targets and run in well under 60s.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import type { Language } from '../src/lib/types';

// Minimal mock of AuthContext so pages that call useAuth() don't throw.
vi.mock('../src/contexts/AuthContext', () => ({
  useAuth: () => ({
    user: { id: 'u1', email: 'test@example.com', name: 'Test', phone: '', account_type: 'both' },
    isAuthenticated: true,
    isLoading: false,
    profileLocale: undefined,
    signIn: vi.fn(),
    signUp: vi.fn(),
    signOut: vi.fn(),
  }),
  AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

// Minimal mock for API calls so pages don't fire real network requests.
vi.mock('../src/lib/api', () => ({
  apiRequest: vi.fn().mockResolvedValue({ debts: [], alerts: [], total_receivable: '0', total_current_debt: '0', debtors: [], creditors: [], commitment_score: 50, overdue_count: 0, due_soon_count: 0, active_count: 0, debtor_count: 0, paid_count: 0, best_customers: [] }),
  errorCode: vi.fn().mockReturnValue(''),
  groups: {
    list: vi.fn().mockResolvedValue([]),
    create: vi.fn(),
    get: vi.fn(),
    debts: vi.fn().mockResolvedValue([]),
    accept: vi.fn(),
    decline: vi.fn(),
  },
  settlements: {
    list: vi.fn().mockResolvedValue([]),
    create: vi.fn(),
    get: vi.fn(),
    confirm: vi.fn(),
    reject: vi.fn(),
  },
}));

// Minimal mock for supabaseClient
vi.mock('../src/lib/supabaseClient', () => ({
  supabase: { auth: { onAuthStateChange: () => ({ data: { subscription: { unsubscribe: vi.fn() } } }) } },
}));

import React from 'react';
import { MemoryRouter } from 'react-router-dom';
import { LandingPage } from '../src/pages/LandingPage';
import { SettingsPage } from '../src/pages/SettingsPage';
import { DashboardPage } from '../src/pages/DashboardPage';
import { NotificationsPage } from '../src/pages/NotificationsPage';
import { GroupsPage } from '../src/pages/GroupsPage';
import { AIPage } from '../src/pages/AIPage';
import { ProfilePage } from '../src/pages/ProfilePage';
import { QRPage } from '../src/pages/QRPage';

const LOCALES: Language[] = ['ar', 'en'];

function wrap(ui: React.ReactElement) {
  return render(<MemoryRouter>{ui}</MemoryRouter>);
}

function assertNoMissingKeys(container: HTMLElement) {
  expect(container.textContent).not.toMatch(/missing\.key\./);
}

describe.each(LOCALES)('locale: %s', (locale) => {
  const noop = vi.fn();

  it('LandingPage — no missing keys', () => {
    const { container } = wrap(<LandingPage language={locale} onToggleLanguage={noop} />);
    assertNoMissingKeys(container);
  });

  it('SettingsPage — no missing keys', () => {
    const { container } = wrap(<SettingsPage language={locale} onToggleLanguage={noop} />);
    assertNoMissingKeys(container);
  });

  it('DashboardPage — no missing keys', () => {
    const { container } = wrap(<DashboardPage language={locale} message="" />);
    assertNoMissingKeys(container);
  });

  it('NotificationsPage — no missing keys', () => {
    const { container } = wrap(<NotificationsPage language={locale} />);
    assertNoMissingKeys(container);
  });

  it('GroupsPage — no missing keys', () => {
    const { container } = wrap(<GroupsPage language={locale} />);
    assertNoMissingKeys(container);
  });

  it('AIPage — no missing keys', () => {
    const { container } = wrap(<AIPage language={locale} />);
    assertNoMissingKeys(container);
  });

  it('ProfilePage — no missing keys', () => {
    const { container } = wrap(<ProfilePage language={locale} />);
    assertNoMissingKeys(container);
  });

  it('QRPage — no missing keys', () => {
    const { container } = wrap(<QRPage language={locale} />);
    assertNoMissingKeys(container);
  });
});
