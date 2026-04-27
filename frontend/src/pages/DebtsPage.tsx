import { Check, CreditCard, ExternalLink, FileText, Image as ImageIcon, Pencil, RotateCcw, WalletCards, X } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { AttachmentUploader } from '../components/AttachmentUploader';
import { CancelDebtDialog } from '../components/CancelDebtDialog';
import { Input, Panel } from '../components/Layout';
import { useAuth } from '../contexts/AuthContext';
import { apiRequest } from '../lib/api';
import { t } from '../lib/i18n';
import type { Attachment, Debt, DebtEvent, DebtStatus, Language, Profile, ReceiptUploadItem } from '../lib/types';

type DebtorSource = 'manual' | 'qr-resolving' | 'qr-resolved' | 'qr-expired' | 'qr-self' | 'qr-error';

interface Prefilled {
  debtor_id: string;
  debtor_name: string;
  phone_last4: string;
  commitment_score: number;
}

interface PendingEditRequest {
  message: string;
  requested_amount?: string;
  requested_due_date?: string;
  requested_description?: string;
}

interface CreditorDecisionDraft {
  message: string;
  amount: string;
  due_date: string;
  description: string;
}

type DebtorThreadKind = 'pending' | 'approved' | 'rejected';

interface DebtorEditThread {
  kind: DebtorThreadKind;
  /** Debtor's original reason for the edit (always present once an edit was requested). */
  yourMessage?: string;
  /** Creditor's reply, present once the creditor has approved or rejected. */
  creditorReply?: string;
  /** When approved: the values applied (creditor's final terms). */
  appliedAmount?: string;
  appliedDueDate?: string;
  appliedDescription?: string;
}

interface DebtAttachmentState {
  items: Attachment[];
  loading: boolean;
  error?: string;
}

interface Props { language: Language }

const statusKeys: (DebtStatus | 'all')[] = [
  'all',
  'pending_confirmation',
  'active',
  'edit_requested',
  'overdue',
  'payment_pending_confirmation',
  'paid',
  'cancelled',
];

type ReminderPreset = { key: 'reminderPresetOnDue' | 'reminderPresetPlus1' | 'reminderPresetPlus3' | 'reminderPresetPlus7' | 'reminderPresetPlus14'; offsetDays: number };

const REMINDER_PRESETS: ReminderPreset[] = [
  { key: 'reminderPresetOnDue', offsetDays: 0 },
  { key: 'reminderPresetPlus1', offsetDays: 1 },
  { key: 'reminderPresetPlus3', offsetDays: 3 },
  { key: 'reminderPresetPlus7', offsetDays: 7 },
  { key: 'reminderPresetPlus14', offsetDays: 14 },
];

function addDays(iso: string, days: number): string {
  const d = new Date(iso);
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

export function DebtsPage({ language }: Props) {
  const tr = (key: Parameters<typeof t>[1]) => t(language, key);
  const { user } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const isCreditor = user?.account_type === 'creditor' || user?.account_type === 'both' || user?.account_type === 'business';
  const [debts, setDebts] = useState<Debt[]>([]);
  const [message, setMessage] = useState('');
  const [filter, setFilter] = useState<DebtStatus | 'all'>('all');

  // QR prefill state
  const [debtorSource, setDebtorSource] = useState<DebtorSource>('manual');
  const [prefilled, setPrefilled] = useState<Prefilled | null>(null);
  const [qrToken, setQrToken] = useState<string | null>(null);
  const [receiptItems, setReceiptItems] = useState<ReceiptUploadItem[]>([]);
  const [attachmentsByDebt, setAttachmentsByDebt] = useState<Record<string, DebtAttachmentState>>({});
  const [failedReceiptItemsByDebt, setFailedReceiptItemsByDebt] = useState<Record<string, ReceiptUploadItem[]>>({});
  const [debtForm, setDebtForm] = useState({
    debtor_name: '',
    debtor_id: '',
    amount: '25.00',
    currency: 'SAR',
    description: '',
    due_date: new Date(Date.now() + 7 * 86400000).toISOString().slice(0, 10),
    notes: '',
  });
  const [reminderPresets, setReminderPresets] = useState<Set<number>>(new Set([3]));
  const [reminderCustom, setReminderCustom] = useState<string>('');

  // Debtor: id of the debt whose edit-request form is open, plus its draft fields.
  const [editingDebtId, setEditingDebtId] = useState<string | null>(null);
  const [cancelDialogDebtId, setCancelDialogDebtId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<{ message: string; requested_amount: string; requested_due_date: string; requested_description: string }>({
    message: '',
    requested_amount: '',
    requested_due_date: '',
    requested_description: '',
  });

  // Creditor: latest pending edit-request per debt (debtor's proposal) + the creditor's draft decision.
  const [pendingEdits, setPendingEdits] = useState<Record<string, PendingEditRequest>>({});
  const [creditorDrafts, setCreditorDrafts] = useState<Record<string, CreditorDecisionDraft>>({});

  // Debtor: latest edit-thread state per debt (so the conversation surfaces in the debt card itself).
  const [debtorThreads, setDebtorThreads] = useState<Record<string, DebtorEditThread>>({});

  const reminderDates = useMemo(() => {
    const presets = Array.from(reminderPresets).map((days) => addDays(debtForm.due_date, days));
    const customs = reminderCustom.split(',').map((s) => s.trim()).filter(Boolean);
    return Array.from(new Set([...presets, ...customs])).sort();
  }, [reminderPresets, reminderCustom, debtForm.due_date]);

  function togglePreset(days: number) {
    setReminderPresets((prev) => {
      const next = new Set(prev);
      if (next.has(days)) next.delete(days); else next.add(days);
      return next;
    });
  }

  // T005a: shared clear-debtor handler — used by "change debtor" link and US2 error recovery
  function clearDebtor() {
    setPrefilled(null);
    setQrToken(null);
    setDebtorSource('manual');
    setDebtForm((f) => ({ ...f, debtor_name: '', debtor_id: '' }));
    navigate({ search: '' }, { replace: true });
  }

  // T009: On mount, detect qr_token and resolve
  useEffect(() => {
    const token = searchParams.get('qr_token');
    if (!token || !isCreditor) return;
    setQrToken(token);
    setDebtorSource('qr-resolving');
    void (async () => {
      try {
        const profile = await apiRequest<Profile>(`/qr/resolve/${encodeURIComponent(token)}`);
        if (profile.id === user?.id) {
          setDebtorSource('qr-self');
        } else {
          setDebtorSource('qr-resolved');
          const p: Prefilled = {
            debtor_id: profile.id,
            debtor_name: profile.name,
            phone_last4: profile.phone.slice(-4),
            commitment_score: profile.commitment_score,
          };
          setPrefilled(p);
          setDebtForm((f) => ({ ...f, debtor_name: profile.name, debtor_id: profile.id }));
        }
      } catch {
        setDebtorSource('qr-expired');
      }
    })();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function load() {
    try {
      const data = await apiRequest<Debt[]>('/debts');
      setDebts(data);
      void loadAttachmentsForDebts(data);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'Failed to load');
    }
  }

  async function loadAttachmentsForDebts(targetDebts: Debt[]) {
    await Promise.all(targetDebts.map((debt) => loadAttachmentsForDebt(debt.id)));
  }

  async function loadAttachmentsForDebt(debtId: string) {
    setAttachmentsByDebt((prev) => ({ ...prev, [debtId]: { items: prev[debtId]?.items ?? [], loading: true } }));
    try {
      const items = await apiRequest<Attachment[]>(`/debts/${debtId}/attachments`);
      setAttachmentsByDebt((prev) => ({ ...prev, [debtId]: { items, loading: false } }));
    } catch {
      setAttachmentsByDebt((prev) => ({
        ...prev,
        [debtId]: { items: prev[debtId]?.items ?? [], loading: false, error: tr('receiptLoadFailed') },
      }));
    }
  }

  useEffect(() => { void load(); }, []);

  // Creditor view: fetch the latest debt_edit_requested event for any debt currently in edit_requested status.
  useEffect(() => {
    if (!isCreditor) return;
    const targets = debts.filter(d => d.status === 'edit_requested' && !pendingEdits[d.id]);
    if (targets.length === 0) return;
    let cancelled = false;
    void Promise.all(targets.map(async (d) => {
      try {
        const events = await apiRequest<DebtEvent[]>(`/debts/${d.id}/events`);
        const latest = [...events].reverse().find((e) => e.event_type === 'debt_edit_requested');
        if (!latest) return null;
        const meta = (latest.metadata ?? {}) as Record<string, unknown>;
        const req: PendingEditRequest = {
          message: latest.message ?? (typeof meta.message === 'string' ? meta.message : ''),
          requested_amount: meta.requested_amount != null ? String(meta.requested_amount) : undefined,
          requested_due_date: typeof meta.requested_due_date === 'string' ? meta.requested_due_date : undefined,
          requested_description: typeof meta.requested_description === 'string' ? meta.requested_description : undefined,
        };
        return [d.id, req, d] as const;
      } catch {
        return null;
      }
    })).then((results) => {
      if (cancelled) return;
      const nextEdits: Record<string, PendingEditRequest> = {};
      const nextDrafts: Record<string, CreditorDecisionDraft> = {};
      for (const r of results) {
        if (!r) continue;
        const [id, req, debt] = r;
        nextEdits[id] = req;
        // Prefill creditor's decision form with debtor's proposal (or current debt values).
        nextDrafts[id] = {
          message: '',
          amount: req.requested_amount ?? debt.amount,
          due_date: req.requested_due_date ?? debt.due_date,
          description: req.requested_description ?? debt.description,
        };
      }
      if (Object.keys(nextEdits).length > 0) {
        setPendingEdits((prev) => ({ ...prev, ...nextEdits }));
        setCreditorDrafts((prev) => ({ ...nextDrafts, ...prev }));
      }
    });
    return () => { cancelled = true; };
  }, [debts, isCreditor, pendingEdits]);

  // Debtor view: fetch the latest edit-related event for each pending/edit_requested debt so the
  // conversation (your request → creditor's decision) surfaces inline on the debt card.
  useEffect(() => {
    if (isCreditor) return;
    const targets = debts.filter((d) =>
      (d.status === 'edit_requested' || d.status === 'pending_confirmation') && !debtorThreads[d.id]
    );
    if (targets.length === 0) return;
    let cancelled = false;
    void Promise.all(targets.map(async (d) => {
      try {
        const events = await apiRequest<DebtEvent[]>(`/debts/${d.id}/events`);
        const ordered = [...events].reverse(); // newest first
        const latest = ordered.find((e) =>
          e.event_type === 'debt_edit_approved' ||
          e.event_type === 'debt_edit_rejected' ||
          e.event_type === 'debt_edit_requested'
        );
        if (!latest) return null;
        const meta = (latest.metadata ?? {}) as Record<string, unknown>;
        if (latest.event_type === 'debt_edit_requested') {
          return [d.id, {
            kind: 'pending' as const,
            yourMessage: latest.message ?? undefined,
          }] as const;
        }
        // approved or rejected — find the original request (most-recent debt_edit_requested before it).
        const requestEvent = ordered.find((e) => e.event_type === 'debt_edit_requested');
        const yourMessage = requestEvent?.message ?? undefined;
        if (latest.event_type === 'debt_edit_approved') {
          const requestedMeta = (meta.requested ?? {}) as Record<string, unknown>;
          const applied = meta.applied_amount ?? requestedMeta.requested_amount;
          const appliedDate = meta.applied_due_date ?? requestedMeta.requested_due_date;
          const appliedDesc = meta.applied_description ?? requestedMeta.requested_description;
          return [d.id, {
            kind: 'approved' as const,
            yourMessage,
            creditorReply: latest.message ?? undefined,
            appliedAmount: applied != null ? String(applied) : undefined,
            appliedDueDate: typeof appliedDate === 'string' ? appliedDate : undefined,
            appliedDescription: typeof appliedDesc === 'string' ? appliedDesc : undefined,
          }] as const;
        }
        return [d.id, {
          kind: 'rejected' as const,
          yourMessage,
          creditorReply: latest.message ?? undefined,
        }] as const;
      } catch {
        return null;
      }
    })).then((results) => {
      if (cancelled) return;
      const next: Record<string, DebtorEditThread> = {};
      for (const r of results) if (r) next[r[0]] = r[1];
      if (Object.keys(next).length > 0) setDebtorThreads((prev) => ({ ...prev, ...next }));
    });
    return () => { cancelled = true; };
  }, [debts, isCreditor, debtorThreads]);

  // After the debtor takes any action (accept / re-request edit), flush the cached thread so
  // it gets re-fetched on the next reload.
  function clearDebtorThread(debtId: string) {
    setDebtorThreads((prev) => { const next = { ...prev }; delete next[debtId]; return next; });
  }

  function openEditForm(debtId: string) {
    setEditingDebtId(debtId);
    setEditForm({ message: '', requested_amount: '', requested_due_date: '', requested_description: '' });
  }

  async function submitEditRequest(debtId: string) {
    if (!editForm.message.trim()) return;
    const body: Record<string, unknown> = { message: editForm.message.trim() };
    if (editForm.requested_amount.trim()) body.requested_amount = editForm.requested_amount.trim();
    if (editForm.requested_due_date) body.requested_due_date = editForm.requested_due_date;
    if (editForm.requested_description.trim()) body.requested_description = editForm.requested_description.trim();
    await runAction(
      () => apiRequest(`/debts/${debtId}/edit-request`, { method: 'POST', body: JSON.stringify(body) }),
      language === 'ar' ? 'تم إرسال طلب التعديل' : 'Edit request sent',
    );
    setEditingDebtId(null);
    clearDebtorThread(debtId);
  }

  async function debtorAcceptDebt(debtId: string) {
    await runAction(
      () => apiRequest(`/debts/${debtId}/accept`, { method: 'POST' }),
      language === 'ar' ? 'تم قبول الدين' : 'Debt accepted',
    );
    clearDebtorThread(debtId);
  }

  function clearDecisionState(debtId: string) {
    setPendingEdits((prev) => { const next = { ...prev }; delete next[debtId]; return next; });
    setCreditorDrafts((prev) => { const next = { ...prev }; delete next[debtId]; return next; });
  }

  async function approveEditRequest(debtId: string, debt: Debt) {
    const draft = creditorDrafts[debtId];
    if (!draft || !draft.message.trim()) return;
    const body: Record<string, unknown> = { message: draft.message.trim() };
    // Only send fields the creditor actually changed from the current debt value.
    if (draft.amount.trim() && draft.amount.trim() !== debt.amount) body.amount = draft.amount.trim();
    if (draft.due_date && draft.due_date !== debt.due_date) body.due_date = draft.due_date;
    if (draft.description.trim() && draft.description.trim() !== debt.description) body.description = draft.description.trim();
    await runAction(
      () => apiRequest(`/debts/${debtId}/edit-request/approve`, { method: 'POST', body: JSON.stringify(body) }),
      language === 'ar' ? 'تمت الموافقة على التعديل' : 'Edit approved',
    );
    clearDecisionState(debtId);
  }

  async function rejectEditRequest(debtId: string) {
    const draft = creditorDrafts[debtId];
    const reply = draft?.message.trim();
    const body = JSON.stringify({ message: reply || (language === 'ar' ? 'الشروط الأصلية سارية' : 'Original terms stand') });
    await runAction(
      () => apiRequest(`/debts/${debtId}/edit-request/reject`, { method: 'POST', body }),
      language === 'ar' ? 'تم رفض التعديل' : 'Edit rejected',
    );
    clearDecisionState(debtId);
  }

  function patchCreditorDraft(debtId: string, patch: Partial<CreditorDecisionDraft>) {
    setCreditorDrafts((prev) => ({ ...prev, [debtId]: { ...(prev[debtId] ?? { message: '', amount: '', due_date: '', description: '' }), ...patch } }));
  }

  async function runAction(action: () => Promise<unknown>, success: string) {
    try {
      await action();
      setMessage(success);
      await load();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'Action failed');
    }
  }

  function canUploadReceipt(item: ReceiptUploadItem): boolean {
    return item.status === 'ready' || item.status === 'warning' || item.status === 'failed';
  }

  async function uploadReceiptForDebt(debtId: string, item: ReceiptUploadItem): Promise<Attachment> {
    const formData = new FormData();
    formData.append('file', item.uploadFile, item.name);
    return apiRequest<Attachment>(`/debts/${debtId}/attachments?attachment_type=invoice`, {
      method: 'POST',
      body: formData,
    });
  }

  function patchReceiptItem(id: string, patch: Partial<ReceiptUploadItem>) {
    setReceiptItems((prev) => prev.map((item) => item.id === id ? { ...item, ...patch } : item));
  }

  async function createDebtWithReceipts() {
    // Guard: submit should never be reachable from error/resolving/self states (defense-in-depth)
    if (debtorSource === 'qr-resolving' || debtorSource === 'qr-self' || debtorSource === 'qr-expired' || debtorSource === 'qr-error') return;

    // T012: re-resolve token at submit time when QR-prefilled
    if (debtorSource === 'qr-resolved' && qrToken) {
      try {
        const recheck = await apiRequest<Profile>(`/qr/resolve/${encodeURIComponent(qrToken)}`);
        if (recheck.id === user?.id) { setDebtorSource('qr-self'); return; }
        if (recheck.id !== prefilled?.debtor_id) { setDebtorSource('qr-error'); return; }
      } catch {
        setDebtorSource('qr-expired');
        return;
      }
    }

    try {
      const created = await apiRequest<Debt>('/debts', {
        method: 'POST',
        body: JSON.stringify({ ...debtForm, reminder_dates: reminderDates }),
      });

      const uploadable = receiptItems.filter(canUploadReceipt);
      const failed: ReceiptUploadItem[] = [];
      for (const item of uploadable) {
        patchReceiptItem(item.id, { status: 'uploading', error: undefined });
        try {
          await uploadReceiptForDebt(created.id, item);
          patchReceiptItem(item.id, { status: 'uploaded', error: undefined });
        } catch (err) {
          failed.push({ ...item, status: 'failed', error: err instanceof Error ? err.message : tr('receiptUploadFailed') });
          patchReceiptItem(item.id, { status: 'failed', error: err instanceof Error ? err.message : tr('receiptUploadFailed') });
        }
      }

      if (failed.length > 0) {
        setFailedReceiptItemsByDebt((prev) => ({ ...prev, [created.id]: failed }));
        setReceiptItems(failed);
        setMessage(tr('receiptUploadFailed'));
      } else {
        setReceiptItems([]);
        setMessage(language === 'ar' ? 'تم إنشاء الدين' : 'Debt created');
      }
      // T013: strip qr_token from URL after success (client-side single-use)
      if (qrToken) {
        setPrefilled(null);
        setQrToken(null);
        setDebtorSource('manual');
        navigate({ search: '' }, { replace: true });
      }
      await load();
      await loadAttachmentsForDebt(created.id);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'Action failed');
    }
  }

  async function retryFailedReceipt(debtId: string, item: ReceiptUploadItem) {
    setFailedReceiptItemsByDebt((prev) => ({
      ...prev,
      [debtId]: (prev[debtId] ?? []).map((candidate) => candidate.id === item.id ? { ...candidate, status: 'uploading', error: undefined } : candidate),
    }));
    try {
      await uploadReceiptForDebt(debtId, item);
      setFailedReceiptItemsByDebt((prev) => ({
        ...prev,
        [debtId]: (prev[debtId] ?? []).filter((candidate) => candidate.id !== item.id),
      }));
      setMessage(language === 'ar' ? 'تم رفع الإيصال' : 'Receipt uploaded');
      await loadAttachmentsForDebt(debtId);
    } catch (err) {
      const error = err instanceof Error ? err.message : tr('receiptUploadFailed');
      setFailedReceiptItemsByDebt((prev) => ({
        ...prev,
        [debtId]: (prev[debtId] ?? []).map((candidate) => candidate.id === item.id ? { ...candidate, status: 'failed', error } : candidate),
      }));
      setMessage(error);
    }
  }

  const filtered = useMemo(() =>
    filter === 'all' ? debts : debts.filter(d => d.status === filter),
    [debts, filter]
  );

  const statusCounts = useMemo(() =>
    debts.reduce<Record<string, number>>((acc, d) => { acc[d.status] = (acc[d.status] ?? 0) + 1; return acc; }, {}),
    [debts]
  );

  function statusLabel(s: string): string {
    switch (s) {
      case 'pending_confirmation': return tr('pendingConfirmation');
      case 'active': return tr('active');
      case 'edit_requested': return tr('editRequested');
      case 'overdue': return tr('overdue');
      case 'payment_pending_confirmation': return tr('paymentPendingConfirmation');
      case 'paid': return tr('paid');
      case 'cancelled': return tr('cancelled');
      default: return s;
    }
  }

  return (
    <section className={isCreditor ? 'split' : ''}>
      {isCreditor && (
        <Panel title={tr('createDebt')}>
          {message && <div className="message">{message}</div>}

          {/* T014: skeleton while resolving */}
          {debtorSource === 'qr-resolving' && (
            <div className="qr-debtor-preview qr-debtor-skeleton" aria-busy="true">
              <div className="skeleton-line" style={{ width: '60%', height: '1rem', background: '#e2e8f0', borderRadius: 4 }} />
              <div className="skeleton-line" style={{ width: '40%', height: '0.75rem', background: '#e2e8f0', borderRadius: 4, marginTop: 6 }} />
            </div>
          )}

          {/* T010: debtor profile preview when QR resolved */}
          {debtorSource === 'qr-resolved' && prefilled && (
            <div className="qr-debtor-preview">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div>
                  <p style={{ margin: 0, fontWeight: 600 }}>{prefilled.debtor_name}</p>
                  <p style={{ margin: '2px 0 0', fontSize: '0.8rem', color: '#64748b' }}>···· {prefilled.phone_last4}</p>
                  <p style={{ margin: '4px 0 0', fontSize: '0.8rem' }}>{tr('commitmentIndicator')}: <strong>{prefilled.commitment_score}/100</strong></p>
                </div>
                <span style={{ fontSize: '0.7rem', background: '#dcfce7', color: '#166534', padding: '2px 6px', borderRadius: 4 }}>{tr('scannedDebtorLabel')}</span>
              </div>
              {/* T011 / T022: clear-debtor link */}
              <button type="button" className="link-button" style={{ fontSize: '0.8rem', marginTop: 8 }} onClick={clearDebtor}>
                {tr('clearDebtor')}
              </button>
            </div>
          )}

          {/* T018: self-scan block */}
          {debtorSource === 'qr-self' && (
            <div className="message error">
              <p style={{ margin: 0 }}>{tr('cannotBillSelf')}</p>
              <button type="button" className="link-button" style={{ fontSize: '0.8rem', marginTop: 6 }} onClick={clearDebtor}>
                {tr('clearDebtor')}
              </button>
            </div>
          )}

          {/* T015 / T016: expired or error banner */}
          {(debtorSource === 'qr-expired' || debtorSource === 'qr-error') && (
            <div className="message error">
              <p style={{ margin: 0 }}>{tr('qrExpiredAskRefresh')}</p>
              <div style={{ display: 'flex', gap: 8, marginTop: 6 }}>
                <button type="button" className="link-button" style={{ fontSize: '0.8rem' }} onClick={() => navigate('/qr')}>
                  {language === 'ar' ? 'مسح من جديد' : 'Rescan'}
                </button>
                <button type="button" className="link-button" style={{ fontSize: '0.8rem' }} onClick={clearDebtor}>
                  {tr('clearDebtor')}
                </button>
              </div>
            </div>
          )}

          {/* T011: debtor name locked when QR-resolved, editable otherwise */}
          {debtorSource === 'qr-resolved' ? (
            <Input label={`${tr('debtorName')} — ${tr('scannedDebtorLabel')}`} value={debtForm.debtor_name} onChange={() => {}} disabled />
          ) : (
            <Input label={tr('debtorName')} value={debtForm.debtor_name} onChange={(v) => setDebtForm({ ...debtForm, debtor_name: v })} disabled={debtorSource === 'qr-resolving'} />
          )}
          {/* Hide debtor_id field when QR-resolved (it's set internally) */}
          {debtorSource !== 'qr-resolved' && (
            <Input label={tr('debtorId')} value={debtForm.debtor_id} onChange={(v) => setDebtForm({ ...debtForm, debtor_id: v })} placeholder={language === 'ar' ? 'معرف المدين (اختياري)' : 'Debtor user ID (optional)'} disabled={debtorSource === 'qr-resolving'} />
          )}
          <Input label={tr('amount')} value={debtForm.amount} onChange={(v) => setDebtForm({ ...debtForm, amount: v })} disabled={debtorSource === 'qr-resolving'} />
          <Input label={tr('currency')} value={debtForm.currency} onChange={(v) => setDebtForm({ ...debtForm, currency: v })} disabled={debtorSource === 'qr-resolving'} />
          <Input label={tr('description')} value={debtForm.description} onChange={(v) => setDebtForm({ ...debtForm, description: v })} disabled={debtorSource === 'qr-resolving'} />
          <Input label={tr('dueDate')} type="date" value={debtForm.due_date} onChange={(v) => setDebtForm({ ...debtForm, due_date: v })} disabled={debtorSource === 'qr-resolving'} />

          <div className="reminder-picker">
            <label>{tr('reminderDates')}</label>
            <div className="reminder-presets">
              {REMINDER_PRESETS.map(({ key, offsetDays }) => (
                <button
                  key={key}
                  type="button"
                  className={`filter-tab${reminderPresets.has(offsetDays) ? ' active' : ''}`}
                  onClick={() => togglePreset(offsetDays)}
                >
                  {tr(key)}
                </button>
              ))}
            </div>
            <Input
              label={tr('addReminder')}
              value={reminderCustom}
              onChange={setReminderCustom}
              placeholder="YYYY-MM-DD, YYYY-MM-DD"
            />
            {reminderDates.length > 0 && (
              <div className="reminder-list">{reminderDates.join(', ')}</div>
            )}
          </div>

          <AttachmentUploader
            language={language}
            items={receiptItems}
            onItemsChange={setReceiptItems}
          />

          {/* T017/T019: hide submit entirely in error/self/resolving states */}
          {(debtorSource === 'manual' || debtorSource === 'qr-resolved') && (
            <button
              className="primary-button"
              onClick={() => void createDebtWithReceipts()}
            >
              <CreditCard size={18} />
              <span>{tr('create')}</span>
            </button>
          )}
        </Panel>
      )}

      {!isCreditor && message && <div className="message">{message}</div>}

      <Panel title={isCreditor ? `${tr('debts')} (${debts.length})` : `${tr('myDebtStatus')} (${debts.length})`}>
        {/* Filter tabs */}
        <div className="filter-tabs">
          {statusKeys.map(s => (
            <button
              key={s}
              className={`filter-tab${filter === s ? ' active' : ''}`}
              onClick={() => setFilter(s)}
            >
              {s === 'all' ? tr('allStatuses') : statusLabel(s)}
              {s !== 'all' && ` (${statusCounts[s] ?? 0})`}
            </button>
          ))}
        </div>

        <div className="debt-stack">
          {filtered.map((debt) => {
            const pending = isCreditor && debt.status === 'edit_requested' ? pendingEdits[debt.id] : undefined;
            const isEditing = !isCreditor && editingDebtId === debt.id;
            const thread = !isCreditor ? debtorThreads[debt.id] : undefined;
            return (
            <article key={debt.id} className="debt-item">
              <div>
                <strong>{debt.debtor_name}</strong>
                <span>{debt.description}</span>
              </div>
              <b>{debt.amount} {debt.currency}</b>
              <span className={`status-badge ${debt.status}`}>
                {statusLabel(debt.status)}
              </span>
              <div className="actions">
                {!isCreditor && (debt.status === 'pending_confirmation' || debt.status === 'edit_requested') && (
                  <button onClick={() => void debtorAcceptDebt(debt.id)}>
                    <Check size={16} /><span>{tr('accept')}</span>
                  </button>
                )}
                {!isCreditor && debt.status === 'pending_confirmation' && !isEditing && (
                  <button onClick={() => openEditForm(debt.id)}>
                    <Pencil size={16} /><span>{tr('requestEdit')}</span>
                  </button>
                )}
                {!isCreditor && (debt.status === 'active' || debt.status === 'overdue') && (
                  <button onClick={() => void runAction(() => apiRequest(`/debts/${debt.id}/mark-paid`, { method: 'POST', body: JSON.stringify({ note: 'Paid' }) }), language === 'ar' ? 'تم طلب تأكيد الدفع' : 'Payment requested')}>
                    <WalletCards size={16} /><span>{tr('markPaid')}</span>
                  </button>
                )}
                {isCreditor && debt.status === 'payment_pending_confirmation' && (
                  <button onClick={() => void runAction(() => apiRequest(`/debts/${debt.id}/confirm-payment`, { method: 'POST' }), language === 'ar' ? 'تم تأكيد الدفع' : 'Payment confirmed')}>
                    <Check size={16} /><span>{tr('confirmPayment')}</span>
                  </button>
                )}
                {isCreditor && (debt.status === 'pending_confirmation' || debt.status === 'edit_requested') && (
                  <button onClick={() => setCancelDialogDebtId(debt.id)}>
                    <X size={16} /><span>{tr('cancel_debt')}</span>
                  </button>
                )}
              </div>

              <div className="receipt-section">
                <div className="receipt-section-header">
                  <strong>{tr('receiptList')}</strong>
                  {attachmentsByDebt[debt.id]?.loading && <span>{tr('receiptLoading')}</span>}
                  {attachmentsByDebt[debt.id]?.error && (
                    <button type="button" onClick={() => void loadAttachmentsForDebt(debt.id)}>
                      <RotateCcw size={14} />
                      <span>{tr('receiptRetry')}</span>
                    </button>
                  )}
                </div>
                {(attachmentsByDebt[debt.id]?.items.length ?? 0) === 0 && !attachmentsByDebt[debt.id]?.loading && !attachmentsByDebt[debt.id]?.error && (
                  <span className="receipt-empty">{tr('receiptNone')}</span>
                )}
                {(attachmentsByDebt[debt.id]?.items ?? []).map((attachment) => (
                  <div key={attachment.id} className="receipt-row">
                    <div className="receipt-thumb" aria-hidden="true">
                      {attachment.content_type?.startsWith('image/') ? <ImageIcon size={18} /> : <FileText size={18} />}
                    </div>
                    <div className="receipt-meta">
                      <strong>{attachment.file_name}</strong>
                      <span>{attachment.retention_state === 'archived' ? tr('receiptArchived') : tr('receiptAvailable')}</span>
                    </div>
                    <a className="receipt-open" href={attachment.url} target="_blank" rel="noreferrer">
                      <ExternalLink size={14} />
                      <span>{tr('receiptOpen')}</span>
                    </a>
                  </div>
                ))}
                {(failedReceiptItemsByDebt[debt.id] ?? []).length > 0 && (
                  <div className="receipt-retry-panel">
                    <strong>{tr('receiptUploadRetry')}</strong>
                    {(failedReceiptItemsByDebt[debt.id] ?? []).map((item) => (
                      <div key={item.id} className={`receipt-row failed ${item.status}`}>
                        <div className="receipt-thumb" aria-hidden="true">
                          {item.previewUrl ? <img src={item.previewUrl} alt="" /> : <FileText size={18} />}
                        </div>
                        <div className="receipt-meta">
                          <strong>{item.name}</strong>
                          {item.error && <span className="receipt-error">{item.error}</span>}
                        </div>
                        <button type="button" className="ghost-button" disabled={item.status === 'uploading'} onClick={() => void retryFailedReceipt(debt.id, item)}>
                          <RotateCcw size={14} />
                          <span>{item.status === 'uploading' ? tr('receiptUploading') : tr('receiptRetry')}</span>
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {isEditing && (
                <div className="edit-request-form" style={{ gridColumn: '1 / -1', display: 'flex', flexDirection: 'column', gap: '0.5rem', paddingTop: '0.75rem', marginTop: '0.5rem', borderTop: '1px dashed var(--border, #e3e6ee)' }}>
                  <label style={{ fontWeight: 600 }}>{tr('editReason')}</label>
                  <textarea
                    rows={3}
                    placeholder={tr('editReasonPlaceholder')}
                    value={editForm.message}
                    onChange={(e) => setEditForm({ ...editForm, message: e.target.value })}
                  />
                  <Input
                    label={`${tr('proposedDescription')} (${tr('optional')})`}
                    value={editForm.requested_description}
                    onChange={(v) => setEditForm({ ...editForm, requested_description: v })}
                    placeholder={debt.description}
                  />
                  <Input
                    label={`${tr('proposedAmount')} (${tr('optional')})`}
                    value={editForm.requested_amount}
                    onChange={(v) => setEditForm({ ...editForm, requested_amount: v })}
                    placeholder={`${debt.amount} ${debt.currency}`}
                  />
                  <Input
                    label={`${tr('proposedDueDate')} (${tr('optional')})`}
                    type="date"
                    value={editForm.requested_due_date}
                    onChange={(v) => setEditForm({ ...editForm, requested_due_date: v })}
                  />
                  <div className="actions">
                    <button className="primary-button" disabled={!editForm.message.trim()} onClick={() => void submitEditRequest(debt.id)}>
                      <Pencil size={16} /><span>{tr('sendEditRequest')}</span>
                    </button>
                    <button onClick={() => setEditingDebtId(null)}>
                      <X size={16} /><span>{tr('cancel')}</span>
                    </button>
                  </div>
                </div>
              )}

              {isCreditor && debt.status === 'edit_requested' && (() => {
                const draft = creditorDrafts[debt.id];
                return (
                <div className="edit-request-details" style={{ gridColumn: '1 / -1', display: 'flex', flexDirection: 'column', gap: '0.5rem', paddingTop: '0.75rem', marginTop: '0.5rem', borderTop: '1px dashed var(--border, #e3e6ee)' }}>
                  <strong>{tr('editRequestFromDebtor')}</strong>
                  {pending ? (
                    <div style={{ padding: '0.5rem 0.75rem', background: 'var(--surface, #fff)', borderRadius: 6, border: '1px solid var(--border, #e3e6ee)' }}>
                      <div style={{ fontSize: '0.85em', opacity: 0.7, marginBottom: '0.25rem' }}>{tr('debtorProposed')}</div>
                      <p style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{pending.message}</p>
                      {(pending.requested_amount || pending.requested_due_date || pending.requested_description) && (
                        <ul style={{ margin: '0.5rem 0 0', paddingInlineStart: '1.25rem' }}>
                          {pending.requested_description && (
                            <li>{tr('description')}: <i>{debt.description}</i> → <b>{pending.requested_description}</b></li>
                          )}
                          {pending.requested_amount && (
                            <li>{tr('amount')}: <i>{debt.amount} {debt.currency}</i> → <b>{pending.requested_amount} {debt.currency}</b></li>
                          )}
                          {pending.requested_due_date && (
                            <li>{tr('dueDate')}: <i>{debt.due_date}</i> → <b>{pending.requested_due_date}</b></li>
                          )}
                        </ul>
                      )}
                    </div>
                  ) : (
                    <p className="empty" style={{ margin: 0 }}>{tr('loading')}</p>
                  )}

                  {pending && draft && (
                    <>
                      <Input
                        label={tr('finalDescription')}
                        value={draft.description}
                        onChange={(v) => patchCreditorDraft(debt.id, { description: v })}
                      />
                      <Input
                        label={tr('finalAmount')}
                        value={draft.amount}
                        onChange={(v) => patchCreditorDraft(debt.id, { amount: v })}
                      />
                      <Input
                        label={tr('finalDueDate')}
                        type="date"
                        value={draft.due_date}
                        onChange={(v) => patchCreditorDraft(debt.id, { due_date: v })}
                      />
                      <label style={{ fontWeight: 600, marginTop: '0.25rem' }}>{tr('creditorReply')}</label>
                      <textarea
                        rows={2}
                        placeholder={tr('creditorReplyPlaceholder')}
                        value={draft.message}
                        onChange={(e) => patchCreditorDraft(debt.id, { message: e.target.value })}
                      />
                      <div className="actions">
                        <button
                          className="primary-button"
                          disabled={!draft.message.trim()}
                          onClick={() => void approveEditRequest(debt.id, debt)}
                        >
                          <Check size={16} /><span>{tr('approveAndSave')}</span>
                        </button>
                        <button onClick={() => void rejectEditRequest(debt.id)}>
                          <X size={16} /><span>{tr('rejectEdit')}</span>
                        </button>
                      </div>
                    </>
                  )}
                </div>
                );
              })()}

              {!isCreditor && !isEditing && thread && (
                <div className="edit-thread" style={{ gridColumn: '1 / -1', display: 'flex', flexDirection: 'column', gap: '0.5rem', paddingTop: '0.75rem', marginTop: '0.5rem', borderTop: '1px dashed var(--border, #e3e6ee)' }}>
                  {thread.kind === 'pending' && (
                    <>
                      <strong>{tr('awaitingCreditor')}</strong>
                      {thread.yourMessage && (
                        <div style={{ padding: '0.5rem 0.75rem', background: 'var(--surface-2, #f6f7fb)', borderRadius: 6 }}>
                          <div style={{ fontSize: '0.8em', opacity: 0.7, marginBottom: '0.2rem' }}>{tr('yourEditRequest')}</div>
                          <p style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{thread.yourMessage}</p>
                        </div>
                      )}
                    </>
                  )}
                  {thread.kind === 'approved' && (
                    <>
                      <strong style={{ color: 'var(--success, #1a7f3c)' }}>✓ {tr('creditorApprovedEdit')}</strong>
                      {thread.creditorReply && (
                        <div style={{ padding: '0.5rem 0.75rem', background: 'var(--surface-2, #f6f7fb)', borderRadius: 6 }}>
                          <p style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{thread.creditorReply}</p>
                        </div>
                      )}
                      {(thread.appliedAmount || thread.appliedDueDate || thread.appliedDescription) && (
                        <div>
                          <div style={{ fontSize: '0.8em', opacity: 0.7, marginBottom: '0.2rem' }}>{tr('newTerms')}</div>
                          <ul style={{ margin: 0, paddingInlineStart: '1.25rem' }}>
                            {thread.appliedDescription && <li>{tr('description')}: <b>{thread.appliedDescription}</b></li>}
                            {thread.appliedAmount && <li>{tr('amount')}: <b>{thread.appliedAmount} {debt.currency}</b></li>}
                            {thread.appliedDueDate && <li>{tr('dueDate')}: <b>{thread.appliedDueDate}</b></li>}
                          </ul>
                        </div>
                      )}
                      {debt.status === 'pending_confirmation' && (
                        <p style={{ margin: 0, fontSize: '0.9em', opacity: 0.85 }}>{tr('reviewAndAccept')}</p>
                      )}
                    </>
                  )}
                  {thread.kind === 'rejected' && (
                    <>
                      <strong style={{ color: 'var(--danger, #b42318)' }}>✕ {tr('creditorRejectedEdit')}</strong>
                      {thread.creditorReply && (
                        <div style={{ padding: '0.5rem 0.75rem', background: 'var(--surface-2, #f6f7fb)', borderRadius: 6 }}>
                          <p style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{thread.creditorReply}</p>
                        </div>
                      )}
                      {debt.status === 'pending_confirmation' && (
                        <p style={{ margin: 0, fontSize: '0.9em', opacity: 0.85 }}>{tr('reviewAndAccept')}</p>
                      )}
                    </>
                  )}
                </div>
              )}
            </article>
          );
          })}
          {filtered.length === 0 && <p className="empty">{tr('noDebtsYet')}</p>}
        </div>
      </Panel>

      {cancelDialogDebtId !== null && (() => {
        const cancelDebt = debts.find(d => d.id === cancelDialogDebtId);
        if (!cancelDebt) return null;
        return (
          <CancelDebtDialog
            debt={cancelDebt}
            language={language}
            onCancelled={(updated) => {
              setDebts(prev => prev.map(d => d.id === updated.id ? updated : d));
              setMessage(tr('cancelled_successfully'));
            }}
            onClose={() => setCancelDialogDebtId(null)}
          />
        );
      })()}
    </section>
  );
}
