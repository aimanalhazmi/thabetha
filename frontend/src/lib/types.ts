/** Shared type definitions for the Thabetha frontend. */

export interface DemoUser {
  id: string;
  name: string;
  phone: string;
}

export interface Profile {
  id: string;
  name: string;
  phone: string;
  trust_score: number;
  ai_enabled: boolean;
  whatsapp_enabled: boolean;
  language: string;
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
  upcoming_count: number;
}

export interface CreditorDashboard {
  total_receivable: string;
  overdue_count: number;
  pending_count: number;
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
  members: string[];
}

export interface VoiceDraft {
  debtor_name: string | null;
  amount: string | null;
  currency: string;
  description: string | null;
  due_date: string | null;
}

export type Language = "ar" | "en";
