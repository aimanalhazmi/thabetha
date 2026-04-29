import type {
  Debt,
  Group,
  GroupDetail,
  GroupInviteIn,
  GroupMember,
  PaymentIntent,
  PayOnlineResult,
  SettlementProposal,
} from './types';
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

export async function payOnline(debtId: string): Promise<PayOnlineResult> {
  return apiRequest<PayOnlineResult>(`/debts/${debtId}/pay-online`, { method: 'POST' });
}

export async function getPaymentIntent(debtId: string): Promise<PaymentIntent> {
  return apiRequest<PaymentIntent>(`/debts/${debtId}/payment-intent`);
}

/** Read the `code` from a backend error body, if present. Falls back to ''. */
export function errorCode(err: unknown): string {
  if (err instanceof Error) {
    const match = err.message.match(/^(\d+):\s*(.*)$/s);
    if (match) {
      try {
        const body = JSON.parse(match[2]);
        const detail = body?.detail;
        if (typeof detail === 'object' && detail && typeof detail.code === 'string') {
          return detail.code;
        }
      } catch {
        return '';
      }
    }
  }
  return '';
}

export const groups = {
  list: () => apiRequest<Group[]>('/groups'),
  create: (body: { name: string; description?: string }) =>
    apiRequest<Group>('/groups', { method: 'POST', body: JSON.stringify(body) }),
  get: (id: string) => apiRequest<GroupDetail>(`/groups/${id}`),
  members: (id: string) => apiRequest<GroupMember[]>(`/groups/${id}/members`),
  pendingInvites: (id: string) => apiRequest<GroupMember[]>(`/groups/${id}/invites`),
  invite: (id: string, body: GroupInviteIn) =>
    apiRequest<GroupMember>(`/groups/${id}/invite`, { method: 'POST', body: JSON.stringify(body) }),
  accept: (id: string) => apiRequest<GroupMember>(`/groups/${id}/accept`, { method: 'POST' }),
  decline: (id: string) => apiRequest<GroupMember>(`/groups/${id}/decline`, { method: 'POST' }),
  leave: (id: string) => apiRequest<GroupMember>(`/groups/${id}/leave`, { method: 'POST' }),
  rename: (id: string, name: string) =>
    apiRequest<Group>(`/groups/${id}/rename`, { method: 'POST', body: JSON.stringify({ name }) }),
  transferOwnership: (id: string, newOwnerUserId: string) =>
    apiRequest<Group>(`/groups/${id}/transfer-ownership`, {
      method: 'POST',
      body: JSON.stringify({ new_owner_user_id: newOwnerUserId }),
    }),
  delete: (id: string) => apiRequest<void>(`/groups/${id}`, { method: 'DELETE' }),
  revokeInvite: (id: string, userId: string) =>
    apiRequest<void>(`/groups/${id}/invites/${userId}`, { method: 'DELETE' }),
  debts: (id: string) => apiRequest<Debt[]>(`/groups/${id}/debts`),
  shared: (withUserId: string) =>
    apiRequest<Group[]>(`/groups/shared?with_user_id=${encodeURIComponent(withUserId)}`),
};

export const settlements = {
  /** Trigger auto-netting for a group. 409 on open-proposal-exists / mixed-currency / nothing-to-settle. */
  create: (groupId: string) =>
    apiRequest<SettlementProposal>(`/groups/${groupId}/settlement-proposals`, {
      method: 'POST',
      body: JSON.stringify({}),
    }),
  list: (groupId: string, status?: string) => {
    const qs = status ? `?status=${encodeURIComponent(status)}` : '';
    return apiRequest<SettlementProposal[]>(`/groups/${groupId}/settlement-proposals${qs}`);
  },
  get: (groupId: string, proposalId: string) =>
    apiRequest<SettlementProposal>(`/groups/${groupId}/settlement-proposals/${proposalId}`),
  confirm: (groupId: string, proposalId: string) =>
    apiRequest<SettlementProposal>(
      `/groups/${groupId}/settlement-proposals/${proposalId}/confirm`,
      { method: 'POST', body: JSON.stringify({}) },
    ),
  reject: (groupId: string, proposalId: string) =>
    apiRequest<SettlementProposal>(
      `/groups/${groupId}/settlement-proposals/${proposalId}/reject`,
      { method: 'POST', body: JSON.stringify({}) },
    ),
};
