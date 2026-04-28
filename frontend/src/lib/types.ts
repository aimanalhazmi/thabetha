/** Shared type definitions for the Thabetha frontend. */

export type AccountType = 'creditor' | 'debtor' | 'both' | 'business';

/**
 * Canonical 8-state debt lifecycle. Mirrors `DebtStatus` in
 * `backend/app/schemas/domain.py`. See `docs/debt-lifecycle.md`.
 */
export type DebtStatus =
  | 'pending_confirmation'
  | 'active'
  | 'edit_requested'
  | 'overdue'
  | 'payment_pending_confirmation'
  | 'paid'
  | 'cancelled';

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
  /** Internal commitment indicator / مؤشر الالتزام (0–100). Not a credit score. */
  commitment_score: number;
  ai_enabled: boolean;
  whatsapp_enabled: boolean;
  /** User's preferred locale — persisted across devices for signed-in users. Default 'ar'. */
  preferred_language: Language;
}

export interface QRToken {
  token: string;
  expires_at: string;
}

export interface Debt {
  id: string;
  creditor_id: string;
  debtor_id: string | null;
  debtor_name: string;
  amount: string;
  currency: string;
  description: string;
  due_date: string;
  reminder_dates: string[];
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
  commitment_score: number;
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

export interface DebtEvent {
  id: string;
  debt_id: string;
  actor_id: string;
  event_type: string;
  message?: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
}

export type AttachmentType = 'invoice' | 'voice_note' | 'other';
export type AttachmentRetentionState = 'available' | 'archived' | 'retention_expired';

export interface Attachment {
  id: string;
  debt_id: string;
  uploader_id: string;
  attachment_type: AttachmentType;
  file_name: string;
  content_type?: string | null;
  url: string;
  url_expires_at?: string | null;
  retention_state: AttachmentRetentionState;
  retention_expires_at?: string | null;
  created_at: string;
}

export type ReceiptUploadStatus = 'ready' | 'warning' | 'uploading' | 'uploaded' | 'failed';

export interface ReceiptUploadItem {
  id: string;
  file: File;
  uploadFile: File;
  name: string;
  size: number;
  contentType: string;
  status: ReceiptUploadStatus;
  error?: string;
  warning?: string;
  previewUrl?: string;
}

export const RECEIPT_WARN_BYTES = 4 * 1024 * 1024;
export const RECEIPT_MAX_BYTES = 5 * 1024 * 1024;
export const RECEIPT_IMAGE_MAX_EDGE = 2048;
export const RECEIPT_ACCEPT = 'image/*,application/pdf';

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
