/** Shared type definitions for the Thabetha frontend. */

export interface Profile {
  id: string;
  name: string;
  phone: string;
  email?: string;
  account_type: "individual" | "business";
  trust_score: number;
  ai_enabled: boolean;
  whatsapp_enabled: boolean;
}

export interface QRToken {
  token: string;
  expires_at: string;
}

export interface Debt {
  id: string;
  creditor_id: string;
  debtor_id: string;
  debtor_name: string;
  amount: string;
  currency: string;
  description: string;
  due_date: string;
  status: string;
  notes?: string;
  created_at: string;
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
}

export type Language = "ar" | "en";
