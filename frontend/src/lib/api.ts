import type { DemoUser } from "./types";

const API_BASE = "/api/v1";

/**
 * Thin wrapper around `fetch` that:
 *  - prepends the API base path
 *  - injects demo-user headers so the backend knows who is calling
 *  - sets JSON content-type for requests with a body
 *  - throws on non-2xx responses
 */
export async function apiRequest<T>(
  path: string,
  user: DemoUser,
  init?: RequestInit
): Promise<T> {
  const headers = new Headers(init?.headers);
  headers.set("X-Demo-User-Id", user.id);
  headers.set("X-Demo-User-Name", user.name);
  headers.set("X-Demo-User-Phone", user.phone);

  if (init?.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
  });

  if (!response.ok) {
    const text = await response.text().catch(() => response.statusText);
    throw new Error(`${response.status}: ${text}`);
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return undefined as unknown as T;
  }

  return response.json() as Promise<T>;
}
