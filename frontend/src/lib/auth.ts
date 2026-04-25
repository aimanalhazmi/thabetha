const API_BASE = "/api/v1";

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  expires_in: number;
  token_type: string;
}

export interface AuthUser {
  id: string;
  email: string;
  name: string;
  phone: string;
}

export interface SignUpData {
  name: string;
  phone: string;
  email: string;
  password: string;
  account_type: "individual" | "business";
  tax_id?: string;
  commercial_registration?: string;
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const text = await response.text().catch(() => response.statusText);
    throw new Error(`${response.status}: ${text}`);
  }
  return response.json() as Promise<T>;
}

export async function signUp(data: SignUpData): Promise<{ tokens: AuthTokens; user: AuthUser }> {
  const result = await post<Record<string, unknown>>("/auth/signup", data);

  // GoTrue response structure — GOTRUE_MAILER_AUTOCONFIRM=true so we get tokens immediately
  const access_token = (result.access_token as string) ?? "";
  const refresh_token = (result.refresh_token as string) ?? "";
  const expires_in = (result.expires_in as number) ?? 3600;

  const userRaw = (result.user as Record<string, unknown>) ?? result;
  const metadata = (userRaw.user_metadata as Record<string, string>) ?? {};

  return {
    tokens: { access_token, refresh_token, expires_in, token_type: "bearer" },
    user: {
      id: String(userRaw.id ?? result.id ?? ""),
      email: String(userRaw.email ?? data.email),
      name: String(metadata.name ?? data.name),
      phone: String(metadata.phone ?? data.phone),
    },
  };
}

export async function signIn(email: string, password: string): Promise<{ tokens: AuthTokens; user: AuthUser }> {
  const result = await post<Record<string, unknown>>("/auth/signin", { email, password });

  const access_token = (result.access_token as string) ?? "";
  const refresh_token = (result.refresh_token as string) ?? "";
  const expires_in = (result.expires_in as number) ?? 3600;

  const userRaw = (result.user as Record<string, unknown>) ?? {};
  const metadata = (userRaw.user_metadata as Record<string, string>) ?? {};

  return {
    tokens: { access_token, refresh_token, expires_in, token_type: "bearer" },
    user: {
      id: String(userRaw.id ?? ""),
      email: String(userRaw.email ?? email),
      name: String(metadata.name ?? email),
      phone: String(metadata.phone ?? ""),
    },
  };
}

export async function refreshTokens(refresh_token: string): Promise<AuthTokens> {
  return post<AuthTokens>("/auth/refresh", { refresh_token });
}

export function storeTokens(tokens: AuthTokens, user: AuthUser): void {
  localStorage.setItem("auth_token", tokens.access_token);
  localStorage.setItem("refresh_token", tokens.refresh_token);
  localStorage.setItem("auth_user", JSON.stringify(user));
  const expiresAt = Date.now() + tokens.expires_in * 1000;
  localStorage.setItem("auth_expires_at", String(expiresAt));
}

export function clearTokens(): void {
  localStorage.removeItem("auth_token");
  localStorage.removeItem("refresh_token");
  localStorage.removeItem("auth_user");
  localStorage.removeItem("auth_expires_at");
}

export function getStoredToken(): string | null {
  const token = localStorage.getItem("auth_token");
  const expiresAt = Number(localStorage.getItem("auth_expires_at") ?? "0");
  if (!token || Date.now() > expiresAt) {
    return null;
  }
  return token;
}

export function getStoredUser(): AuthUser | null {
  const raw = localStorage.getItem("auth_user");
  if (!raw) return null;
  try {
    return JSON.parse(raw) as AuthUser;
  } catch {
    return null;
  }
}
