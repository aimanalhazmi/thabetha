import { supabase } from './supabaseClient';

const API_BASE = '/api/v1';

/**
 * Thin wrapper around `fetch` that:
 *  - prepends the API base path
 *  - injects the Bearer token from Supabase session
 *  - sets JSON content-type for JSON requests with a body
 *  - throws on non-2xx responses
 */
export async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);

  const { data: { session } } = await supabase.auth.getSession();
  if (session?.access_token) {
    headers.set('Authorization', `Bearer ${session.access_token}`);
  }

  const isFormDataBody = typeof FormData !== 'undefined' && init?.body instanceof FormData;
  if (init?.body && !isFormDataBody && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
  });

  if (!response.ok) {
    const text = await response.text().catch(() => response.statusText);
    throw new Error(`${response.status}: ${text}`);
  }

  if (response.status === 204) {
    return undefined as unknown as T;
  }

  return response.json() as Promise<T>;
}
