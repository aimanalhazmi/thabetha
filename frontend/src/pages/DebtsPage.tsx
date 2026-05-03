import { Check, ChevronLeft, ChevronRight, CreditCard, ExternalLink, FileText, Image as ImageIcon, Mic, Pencil, RotateCcw, Square, WalletCards, X } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { AttachmentUploader } from '../components/AttachmentUploader';
import { CancelDebtDialog } from '../components/CancelDebtDialog';
import { GroupSelector } from '../components/GroupSelector';
import { Input, Panel } from '../components/Layout';
import { useAuth } from '../contexts/AuthContext';
import { aiVoiceDrafts, apiRequest, payOnline } from '../lib/api';
import { humanizeError } from '../lib/errors';
import { t } from '../lib/i18n';
import type { Attachment, Debt, DebtEvent, DebtStatus, Language, PayOnlineResult, Profile, ReceiptUploadItem, VoiceDraft } from '../lib/types';

function getInitials(name: string) {
  return name.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase();
}

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

type VoiceDraftField = keyof VoiceDraft['field_confirmations'];

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

const VOICE_DRAFT_FIELDS: VoiceDraftField[] = ['debtor_name', 'amount', 'currency', 'description', 'due_date'];

function addDays(iso: string, days: number): string {
  const d = new Date(iso);
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

export function DebtsPage({ language }: Props) {
  const tr = (key: Parameters<typeof t>[1]) => t(language, key);
  const { user } = useAuth();
  const navigate = useNavigate();
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const recordedChunksRef = useRef<Blob[]>([]);
  const recordingStartRef = useRef<number>(0);
  const [searchParams, setSearchParams] = useSearchParams();
  const isCreditor = user?.account_type === 'creditor' || user?.account_type === 'both' || user?.account_type === 'business';
  const [debts, setDebts] = useState<Debt[]>([]);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [message, setMessage] = useState('');
  const filter = (searchParams.get('status') as DebtStatus | 'all') || 'all';
  function setFilter(newFilter: DebtStatus | 'all') {
    const next = new URLSearchParams(searchParams);
    if (newFilter === 'all') next.delete('status');
    else next.set('status', newFilter);
    setSearchParams(next, { replace: true });
  }

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
  const [selectedGroupId, setSelectedGroupId] = useState<string | null>(null);
  const [voiceDraft, setVoiceDraft] = useState<VoiceDraft | null>(null);
  const [voiceDraftLoading, setVoiceDraftLoading] = useState(false);
  const [voiceConfirmedFields, setVoiceConfirmedFields] = useState<Set<VoiceDraftField>>(new Set());
  const [isRecording, setIsRecording] = useState(false);
  const [recordingError, setRecordingError] = useState<string | null>(null);

  // Debtor: id of the debt whose edit-request form is open, plus its draft fields.
  const [editingDebtId, setEditingDebtId] = useState<string | null>(null);
  const [cancelDialogDebtId, setCancelDialogDebtId] = useState<string | null>(null);
  const [actionInFlight, setActionInFlight] = useState(false);
  const [payOnlineResult, setPayOnlineResult] = useState<PayOnlineResult | null>(null);
  const [payOnlineDebtId, setPayOnlineDebtId] = useState<string | null>(null);
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

  function setDebtFormField(field: keyof typeof debtForm, value: string) {
    setDebtForm((current) => ({ ...current, [field]: value }));
    if (voiceDraft && field in voiceDraft.field_confirmations) {
      setVoiceConfirmedFields((current) => new Set(current).add(field as VoiceDraftField));
    }
  }

  function fieldLabel(field: VoiceDraftField): string {
    const labels: Record<VoiceDraftField, Parameters<typeof t>[1]> = {
      debtor_name: 'debtorName',
      amount: 'amount',
      currency: 'currency',
      description: 'description',
      due_date: 'dueDate',
    };
    return tr(labels[field]);
  }

  function voiceDraftFieldsToConfirm(draft: VoiceDraft | null = voiceDraft): VoiceDraftField[] {
    if (!draft) return [];
    return VOICE_DRAFT_FIELDS.filter((field) => draft.field_confirmations[field] === 'extracted_unconfirmed');
  }

  const voiceDraftReady = voiceDraftFieldsToConfirm().every((field) => voiceConfirmedFields.has(field));

  function applyVoiceDraft(draft: VoiceDraft) {
    setVoiceDraft(draft);
    setVoiceConfirmedFields(new Set());
    setDebtForm((current) => ({
      ...current,
      debtor_name: draft.debtor_name ?? current.debtor_name,
      debtor_id: current.debtor_id,
      amount: draft.amount ?? current.amount,
      currency: draft.currency || current.currency,
      description: draft.description ?? current.description,
      due_date: draft.due_date ?? current.due_date,
    }));
  }

  async function requestVoiceDraftFromAudio(file: File, durationSeconds?: number) {
    setVoiceDraftLoading(true);
    try {
      applyVoiceDraft(await aiVoiceDrafts.fromAudio(file, durationSeconds));
      setMessage(tr('voiceDraftReview'));
    } catch (err) {
      setMessage(humanizeError(err, language, 'aiVoiceDraft'));
    } finally {
      setVoiceDraftLoading(false);
    }
  }

  async function startRecording() {
    if (isRecording) return;
    setRecordingError(null);
    if (typeof navigator === 'undefined' || !navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
      setRecordingError(tr('voiceDraftRecorderUnavailable'));
      return;
    }
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      setRecordingError(tr('voiceDraftMicDenied'));
      return;
    }
    const mimeType = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4'].find((type) =>
      typeof MediaRecorder.isTypeSupported === 'function' ? MediaRecorder.isTypeSupported(type) : false,
    ) ?? '';
    const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
    recordedChunksRef.current = [];
    recorder.addEventListener('dataavailable', (event) => {
      if (event.data && event.data.size > 0) recordedChunksRef.current.push(event.data);
    });
    recorder.addEventListener('stop', () => {
      stream.getTracks().forEach((track) => track.stop());
      const recordedType = recorder.mimeType || 'audio/webm';
      const blob = new Blob(recordedChunksRef.current, { type: recordedType });
      recordedChunksRef.current = [];
      const extension = recordedType.includes('mp4') ? 'm4a' : 'webm';
      const file = new File([blob], `voice-note-${Date.now()}.${extension}`, { type: recordedType });
      const durationSeconds = (Date.now() - recordingStartRef.current) / 1000;
      setIsRecording(false);
      void requestVoiceDraftFromAudio(file, durationSeconds);
    });
    mediaRecorderRef.current = recorder;
    recordingStartRef.current = Date.now();
    recorder.start();
    setIsRecording(true);
  }

  function stopRecording() {
    const recorder = mediaRecorderRef.current;
    if (recorder && recorder.state !== 'inactive') recorder.stop();
    mediaRecorderRef.current = null;
  }

  function confirmVoiceField(field: VoiceDraftField) {
    setVoiceConfirmedFields((current) => new Set(current).add(field));
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
  }, []);

  async function load() {
    try {
      const data = await apiRequest<Debt[]>('/debts');
      setDebts(data);
      if (isCreditor) {
        const currentProfile = await apiRequest<Profile>('/profiles/me');
        setProfile(currentProfile);
      }
      void loadAttachmentsForDebts(data);
    } catch (err) {
      setMessage(humanizeError(err, language, 'loadDebts'));
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
      tr('toastEditRequestSent'),
    );
    setEditingDebtId(null);
    clearDebtorThread(debtId);
  }

  async function debtorAcceptDebt(debtId: string) {
    await runAction(
      () => apiRequest(`/debts/${debtId}/accept`, { method: 'POST' }),
      tr('toastDebtAccepted'),
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
      tr('toastEditApproved'),
    );
    clearDecisionState(debtId);
  }

  async function rejectEditRequest(debtId: string) {
    const draft = creditorDrafts[debtId];
    const reply = draft?.message.trim();
    const body = JSON.stringify({ message: reply || tr('originalTermsStand') });
    await runAction(
      () => apiRequest(`/debts/${debtId}/edit-request/reject`, { method: 'POST', body }),
      tr('toastEditRejected'),
    );
    clearDecisionState(debtId);
  }

  function patchCreditorDraft(debtId: string, patch: Partial<CreditorDecisionDraft>) {
    setCreditorDrafts((prev) => ({ ...prev, [debtId]: { ...(prev[debtId] ?? { message: '', amount: '', due_date: '', description: '' }), ...patch } }));
  }

  async function runAction(action: () => Promise<unknown>, success: string) {
    setActionInFlight(true);
    try {
      await action();
      setMessage(success);
      await load();
    } catch (err) {
      setMessage(humanizeError(err, language, 'transition'));
    } finally {
      setActionInFlight(false);
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
    if (voiceDraft && !voiceDraftReady) {
      setMessage(tr('voiceDraftNeedsConfirmation'));
      return;
    }
    // Guard: submit should never be reachable from error/resolving/self states (defense-in-depth)
    if (debtorSource === 'qr-resolving' || debtorSource === 'qr-self' || debtorSource === 'qr-expired' || debtorSource === 'qr-error') return;

    try {
      const created = await apiRequest<Debt>('/debts', {
        method: 'POST',
        body: JSON.stringify({ ...debtForm, reminder_dates: reminderDates, ...(selectedGroupId ? { group_id: selectedGroupId } : {}) }),
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
        setSelectedGroupId(null);
        setMessage(tr('toastDebtCreated'));
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
      setMessage(humanizeError(err, language, 'transition'));
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
      setMessage(tr('toastReceiptUploaded'));
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

  const statusTotals = useMemo(() =>
    debts.reduce<Record<string, number>>((acc, d) => {
      const amt = parseFloat(d.amount) || 0;
      acc[d.status] = (acc[d.status] ?? 0) + amt;
      acc['all'] = (acc['all'] ?? 0) + amt;
      return acc;
    }, {}),
    [debts]
  );

  function statusLabel(s: string): string {
    switch (s) {
      case 'pending_confirmation': return tr('debts_filter_pending');
      case 'active': return tr('debts_filter_active');
      case 'edit_requested': return tr('editRequested');
      case 'overdue': return tr('debts_filter_overdue');
      case 'payment_pending_confirmation': return tr('paymentPendingConfirmation');
      case 'paid': return tr('debts_filter_paid');
      case 'cancelled': return tr('debts_filter_cancelled');
      default: return s;
    }
  }

  const groupedDebts = useMemo(() => {
    const groups: Record<string, { userId: string; userName: string; totalAmount: number; debtCount: number }> = {};
    filtered.forEach(d => {
      const uId = isCreditor ? d.debtor_id : d.creditor_id;
      const key = uId || 'unknown';
      if (!groups[key]) {
        groups[key] = {
          userId: key,
          userName: isCreditor ? d.debtor_name : tr('creditor'),
          totalAmount: 0,
          debtCount: 0,
        };
      }
      groups[key].totalAmount += parseFloat(d.amount) || 0;
      groups[key].debtCount += 1;
    });
    return Object.values(groups).sort((a, b) => b.totalAmount - a.totalAmount);
  }, [filtered, isCreditor, language]);

  return (
    <section className="debts-page">

      {!isCreditor && message && <div className="message">{message}</div>}

      {/* Page header */}
      <div className="debts-page__header">
        <h2 className="debts-page__title">
          {isCreditor ? tr('debts') : tr('myDebtStatus')}
          <span className="dash-count-badge">{debts.length}</span>
        </h2>
      </div>

      {/* Filter tabs */}
      <div className="filter-tabs">
        {statusKeys.map(s => {
          const count = statusCounts[s] ?? 0;
          const total = statusTotals[s] ?? 0;
          return (
            <button
              key={s}
              className={`filter-tab${filter === s ? ' active' : ''}`}
              onClick={() => setFilter(s)}
            >
              <span className="filter-tab__label">
                {s === 'all' ? tr('allStatuses') : statusLabel(s)}
                {s !== 'all' && count > 0 && (
                  <span className="filter-tab-count">{count}</span>
                )}
              </span>
              {total > 0 && (
                <span className="filter-tab__amount">
                  {total.toLocaleString(language === 'ar' ? 'ar-SA' : 'en-SA', { minimumFractionDigits: 0, maximumFractionDigits: 0 })} ر.س
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Grouped user list */}
      <div className="compact-list">
        {groupedDebts.map((group) => {
          const initials = group.userName.substring(0, 2).toUpperCase();
          return (
            <div
              key={group.userId}
              className="user-summary-row"
              onClick={() => navigate(`/debts/user/${group.userId}`)}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => { if (e.key === 'Enter') navigate(`/debts/user/${group.userId}`); }}
            >
              <div className="user-summary-avatar">{initials}</div>
              <div className="user-summary-info">
                <span className="user-summary-name">{group.userName}</span>
                <span className="user-summary-count">{group.debtCount} {tr('debts_group_total_debts')}</span>
              </div>
              <div className="user-summary-amount">
                {group.totalAmount.toFixed(2)} SAR
              </div>
              {language === 'ar' ? <ChevronLeft className="user-summary-chevron" /> : <ChevronRight className="user-summary-chevron" />}
            </div>
          );
        })}
        {groupedDebts.length === 0 && <p className="empty">{tr('noDebtsYet')}</p>}
      </div>


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
