import { supabase } from './supabaseClient';
import type { AccountType } from './types';

export interface AuthUser {
  id: string;
  email: string;
  name: string;
  phone: string;
  account_type: AccountType;
}

export interface SignUpData {
  name: string;
  phone: string;
  email: string;
  password: string;
  tax_id?: string;
  commercial_registration?: string;
}

/**
 * Sign up a new user via Supabase Auth.
 * If tax_id is provided, account_type = 'creditor', otherwise 'debtor'.
 * Email confirmation is required — user must verify email before sign-in.
 */
export async function signUp(data: SignUpData): Promise<{ needsVerification: boolean }> {
  const account_type: AccountType = data.tax_id ? 'creditor' : 'debtor';

  const { error } = await supabase.auth.signUp({
    email: data.email,
    password: data.password,
    options: {
      data: {
        name: data.name,
        phone: data.phone,
        account_type,
        tax_id: data.tax_id || null,
        commercial_registration: data.commercial_registration || null,
      },
    },
  });

  if (error) throw new Error(error.message);

  return { needsVerification: true };
}

/**
 * Sign in with email + password via Supabase Auth.
 * Only works after email verification.
 */
export async function signIn(email: string, password: string): Promise<AuthUser> {
  const { data, error } = await supabase.auth.signInWithPassword({
    email,
    password,
  });

  if (error) throw new Error(error.message);

  const user = data.user;
  const meta = user.user_metadata ?? {};

  return {
    id: user.id,
    email: user.email ?? email,
    name: meta.name ?? '',
    phone: meta.phone ?? '',
    account_type: meta.account_type ?? 'debtor',
  };
}

/**
 * Sign out the current user.
 */
export async function signOut(): Promise<void> {
  const { error } = await supabase.auth.signOut();
  if (error) throw new Error(error.message);
}

/**
 * Get the current session user, or null.
 */
export async function getCurrentUser(): Promise<AuthUser | null> {
  const { data: { session } } = await supabase.auth.getSession();
  if (!session?.user) return null;

  const user = session.user;
  const meta = user.user_metadata ?? {};

  return {
    id: user.id,
    email: user.email ?? '',
    name: meta.name ?? '',
    phone: meta.phone ?? '',
    account_type: meta.account_type ?? 'debtor',
  };
}

/**
 * Get the current access token for API calls.
 */
export async function getAccessToken(): Promise<string | null> {
  const { data: { session } } = await supabase.auth.getSession();
  return session?.access_token ?? null;
}
