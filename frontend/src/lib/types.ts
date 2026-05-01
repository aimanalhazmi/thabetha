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
  groups_enabled: boolean;
  /** User's preferred locale — persisted across devices for signed-in users. Default 'ar'. */
  preferred_language: Language;
  /** ISO 4217 currency code used as default when creating debts. Default 'SAR'. */
  default_currency?: string;
}

export interface ProfilePreview {
  id: string;
  name: string;
  phone: string;
  commitment_score: number;
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
  group_id?: string | null;
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

export type WhatsAppDeliveryStatus =
  | 'not_attempted'
  | 'attempted_unknown'
  | 'delivered'
  | 'failed';

export type WhatsAppFailedReason =
  | 'recipient_blocked'
  | 'invalid_phone'
  | 'template_not_approved'
  | 'template_param_mismatch'
  | 'provider_4xx'
  | 'provider_5xx'
  | 'network_error'
  | 'no_template'
  | 'no_phone_number';

export interface NotificationItem {
  id: string;
  notification_type?: string;
  title: string;
  body: string;
  read_at: string | null;
  created_at: string;
  whatsapp_attempted?: boolean;
  // Creditor-only fields — only present when the API returns NotificationOutCreditor.
  whatsapp_delivered?: boolean | null;
  whatsapp_failed_reason?: WhatsAppFailedReason | null;
  whatsapp_status?: WhatsAppDeliveryStatus;
  whatsapp_status_received_at?: string | null;
}

export type GroupMemberStatus = 'pending' | 'accepted' | 'declined' | 'left';

export interface Group {
  id: string;
  name: string;
  description?: string;
  owner_id: string;
  member_count: number;
  /** The caller's membership status in this group (set by the list endpoint). */
  member_status?: GroupMemberStatus | null;
  created_at: string;
  updated_at?: string;
}

export interface GroupMember {
  id: string;
  group_id: string;
  user_id: string;
  status: GroupMemberStatus;
  created_at: string;
  accepted_at?: string | null;
  name?: string | null;
  email?: string | null;
  phone?: string | null;
  commitment_score?: number | null;
}

export interface GroupMemberDebtSummary {
  user_id: string;
  name?: string | null;
  email?: string | null;
  phone?: string | null;
  total_owed: string;
  status_totals: Partial<Record<DebtStatus, string>>;
  debts: Debt[];
}

export interface GroupDebtOverview {
  total_current_owed: string;
  status_totals: Partial<Record<DebtStatus, string>>;
  member_debts: GroupMemberDebtSummary[];
}

export interface GroupDetail extends Group {
  members: GroupMember[];
  pending_invites?: GroupMember[] | null;
  debt_overview?: GroupDebtOverview | null;
}

export interface GroupInviteIn {
  email?: string;
  phone?: string;
}

// ── Group auto-netting (Phase 9 / UC9 part 2) ──────────────────────────────

export type SettlementProposalStatus =
  | 'open'
  | 'rejected'
  | 'expired'
  | 'settlement_failed'
  | 'settled';

export type SettlementConfirmationStatus =
  | 'pending'
  | 'confirmed'
  | 'rejected';

export interface ProposedTransfer {
  payer_id: string;
  receiver_id: string;
  amount: string;
}

export interface SnapshotDebt {
  debt_id: string;
  debtor_id: string;
  creditor_id: string;
  amount: string;
}

export interface SettlementConfirmation {
  user_id: string;
  status: SettlementConfirmationStatus;
  responded_at: string | null;
}

export interface SettlementProposal {
  id: string;
  group_id: string;
  proposed_by: string;
  currency: string;
  transfers: ProposedTransfer[];
  /** Null for observers (zero-net members). FR-007. */
  snapshot: SnapshotDebt[] | null;
  confirmations: SettlementConfirmation[];
  status: SettlementProposalStatus;
  failure_reason: string | null;
  created_at: string;
  expires_at: string;
  resolved_at: string | null;
}

export interface VoiceDraft {
  debtor_name: string | null;
  amount: string | null;
  currency: string;
  description: string | null;
  due_date: string | null;
  confidence: number;
  raw_transcript: string;
  field_confirmations: Record<'debtor_name' | 'amount' | 'currency' | 'description' | 'due_date', 'extracted_unconfirmed' | 'missing' | 'confirmed' | 'edited'>;
}

export interface ChatTurn {
  role: 'user' | 'assistant';
  content: string;
}

export interface ToolTraceEntry {
  tool: 'list_debts' | 'get_debt' | 'get_dashboard_summary' | 'get_commitment_history';
  outcome: 'ok' | 'error' | 'empty';
  duration_ms: number;
}

export interface MerchantChatRequest {
  message: string;
  history?: ChatTurn[];
  locale?: Language;
  timezone?: string;
}

export interface MerchantChatResponse {
  answer: string;
  facts: Record<string, unknown>;
  tool_trace?: ToolTraceEntry[] | null;
}

export interface PayOnlineResult {
  payment_intent_id: string;
  checkout_url: string;
  amount: string;
  fee: string;
  net_amount: string;
  currency: string;
  expires_at: string;
}

export interface PaymentIntent {
  id: string;
  debt_id: string;
  provider: string;
  provider_ref: string | null;
  checkout_url: string | null;
  status: 'pending' | 'succeeded' | 'failed' | 'expired';
  amount: string;
  fee: string;
  net_amount: string;
  created_at: string;
  expires_at: string;
  completed_at: string | null;
}
