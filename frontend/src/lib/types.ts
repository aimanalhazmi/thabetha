/** Shared type definitions for the Thabetha frontend. */

export type AccountType = 'creditor' | 'debtor' | 'both';
export type DebtStatus =
  | 'waiting_for_confirmation'
  | 'active'
  | 'paid'
  | 'delay'
  | 'rejected'
  | 'change_requested'
  | 'payment_pending_confirmation';
export type Language = 'ar' | 'en';

export interface Profile {
  id: string;
  name: string;
  phone: string;
  email?: string;
  account_type: AccountType;
  tax_id?: string;
  commercial_registration?: string;
  shop_name?: string;
  activity_type?: string;
  shop_location?: string;
  shop_description?: string;
  trust_score: number;
  ai_enabled: boolean;
  whatsapp_enabled: boolean;
}

export interface QRToken {
  token: string;
  user_id: string;
  expires_at: string;
  created_at: string;
}

export interface Debt {
  id: string;
  creditor_id: string;
  creditor_name: string;
  debtor_id: string | null;
  debtor_name: string;
  amount: string;
  currency: string;
  description: string;
  due_date: string;
  status: DebtStatus;
  notes?: string;
  created_at: string;
  updated_at: string;
  confirmed_at?: string;
  paid_at?: string;
}

export interface DebtorDashboard {
  total_current_debt: string;
  overdue_count: number;
  due_soon_count: number;
  creditors: string[];
  trust_score: number;
  debts: Debt[];
}

export interface CreditorDashboard {
  total_receivable: string;
  overdue_count: number;
  active_count: number;
  debtor_count: number;
  paid_count: number;
  alerts: string[];
  debts: Debt[];
}

export interface NotificationItem {
  id: string;
  title: string;
  body: string;
  read_at: string | null;
  created_at: string;
}

export interface Group {
  id: string;
  name: string;
  description?: string;
  owner_id: string;
  created_at: string;
}

export interface VoiceDraft {
  debtor_name: string | null;
  amount: string | null;
  currency: string;
  description: string | null;
  due_date: string | null;
  confidence: number;
  raw_transcript: string;
}
