import { Camera, Check, CreditCard, Keyboard, Lock, Mic, Square } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { AttachmentUploader } from '../components/AttachmentUploader';
import { DebtorConfirmCard } from '../components/DebtorConfirmCard';
import { Input, Panel } from '../components/Layout';
import { QRScanner } from '../components/QRScanner';
import { useAuth } from '../contexts/AuthContext';
import { aiVoiceDrafts, apiRequest } from '../lib/api';
import { humanizeError } from '../lib/errors';
import { t } from '../lib/i18n';
import type { Attachment, Debt, Language, Profile, ProfilePreview, ReceiptUploadItem, VoiceDraft } from '../lib/types';

interface Props { language: Language }

type Step = 1 | 2 | 3;
type ManualMode = 'token' | 'userid';
type IdentifyMode = 'scan' | 'manual';

type ResolvedDebtor = ProfilePreview & { source: 'qr' | 'manual_token' | 'manual_userid'; token?: string };

type VoiceDraftField = keyof VoiceDraft['field_confirmations'];

type ReminderPreset = { key: 'reminderPresetOnDue' | 'reminderPresetPlus1' | 'reminderPresetPlus3' | 'reminderPresetPlus7' | 'reminderPresetPlus14'; offsetDays: number };

const REMINDER_PRESETS: ReminderPreset[] = [
  { key: 'reminderPresetOnDue', offsetDays: 0 },
  { key: 'reminderPresetPlus1', offsetDays: 1 },
  { key: 'reminderPresetPlus3', offsetDays: 3 },
  { key: 'reminderPresetPlus7', offsetDays: 7 },
  { key: 'reminderPresetPlus14', offsetDays: 14 },
];

const AI_LOW_CONFIDENCE = 0.6;
const AI_EDITABLE_FIELDS: VoiceDraftField[] = ['amount', 'description', 'due_date'];

function addDays(iso: string, days: number): string {
  const d = new Date(iso);
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

export function CreateDebtPage({ language }: Props) {
  const tr = (k: Parameters<typeof t>[1]) => t(language, k);
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { user } = useAuth();
  const [step, setStep] = useState<Step>(1);

  const [identifyMode, setIdentifyMode] = useState<IdentifyMode>('scan');
  const [manualMode, setManualMode] = useState<ManualMode>('token');
  const [manualValue, setManualValue] = useState('');
  const [resolving, setResolving] = useState(false);
  const [identifyError, setIdentifyError] = useState<string | null>(null);

  const [resolved, setResolved] = useState<ResolvedDebtor | null>(null);

  const [profile, setProfile] = useState<Profile | null>(null);
  const [debtForm, setDebtForm] = useState({
    amount: '25.00',
    currency: 'SAR',
    description: '',
    due_date: new Date(Date.now() + 7 * 86400000).toISOString().slice(0, 10),
    notes: '',
  });
  const [reminderPresets, setReminderPresets] = useState<Set<number>>(new Set([3]));
  const [reminderCustom, setReminderCustom] = useState('');
  const [receiptItems, setReceiptItems] = useState<ReceiptUploadItem[]>([]);
  const [voiceNoteFile, setVoiceNoteFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  // AI voice draft state (Step 3 only)
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const recordedChunksRef = useRef<Blob[]>([]);
  const recordingStartRef = useRef<number>(0);
  const [voiceDraft, setVoiceDraft] = useState<VoiceDraft | null>(null);
  const [voiceDraftLoading, setVoiceDraftLoading] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [aiError, setAiError] = useState<string | null>(null);

  // Auto-resolve a token passed via ?qr_token= (e.g. from /qr scanner page).
  useEffect(() => {
    const token = searchParams.get('qr_token');
    if (token && step === 1 && !resolved && !resolving) {
      void resolveByToken(token);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Load profile on first reach of Step 3 to know whether AI is enabled
  async function loadProfileIfNeeded() {
    if (profile) return;
    try {
      const me = await apiRequest<Profile>('/profiles/me');
      setProfile(me);
    } catch {
      // non-fatal — AI just won't render
    }
  }

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

  // ── Step 1 — resolve debtor ────────────────────────────────────────────────
  async function resolveByToken(token: string) {
    setResolving(true);
    setIdentifyError(null);
    try {
      const trimmed = token.trim();
      if (!trimmed) throw new Error('empty');
      const p = await apiRequest<Profile>(`/qr/resolve/${encodeURIComponent(trimmed)}`);
      if (p.id === user?.id) {
        setIdentifyError(tr('cannotBillSelf'));
        return;
      }
      setResolved({
        id: p.id,
        name: p.name,
        phone: p.phone,
        commitment_score: p.commitment_score,
        source: identifyMode === 'scan' ? 'qr' : 'manual_token',
        token: trimmed,
      });
      setStep(2);
    } catch (err) {
      const status = (err as { status?: number })?.status;
      if (status === 404) setIdentifyError(tr('scan_qr_error_expired'));
      else setIdentifyError(humanizeError(err, language, 'qrResolve'));
    } finally {
      setResolving(false);
    }
  }

  async function resolveByUserId(userId: string) {
    setResolving(true);
    setIdentifyError(null);
    try {
      const trimmed = userId.trim();
      if (!trimmed) throw new Error('empty');
      const p = await apiRequest<ProfilePreview>(`/profiles/preview/${encodeURIComponent(trimmed)}`);
      if (p.id === user?.id) {
        setIdentifyError(tr('cannotBillSelf'));
        return;
      }
      setResolved({ ...p, source: 'manual_userid' });
      setStep(2);
    } catch (err) {
      const status = (err as { status?: number })?.status;
      if (status === 404) setIdentifyError(tr('scan_qr_error_notfound'));
      else setIdentifyError(humanizeError(err, language, 'generic'));
    } finally {
      setResolving(false);
    }
  }

  function submitManual() {
    if (manualMode === 'token') void resolveByToken(manualValue);
    else void resolveByUserId(manualValue);
  }

  // ── Step 2 → Step 3 ────────────────────────────────────────────────────────
  function confirmDebtor() {
    setStep(3);
    void loadProfileIfNeeded();
  }

  // ── Step 3 — AI voice assist ───────────────────────────────────────────────
  function applyVoiceDraft(draft: VoiceDraft) {
    setVoiceDraft(draft);
    setDebtForm((current) => ({
      ...current,
      // Locked debtor fields are NEVER touched. Only amount/description/due_date.
      amount: draft.amount ?? current.amount,
      description: draft.description ?? current.description,
      due_date: draft.due_date ?? current.due_date,
    }));
  }

  async function startRecording() {
    if (isRecording) return;
    setAiError(null);
    if (typeof navigator === 'undefined' || !navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
      setAiError(tr('voiceDraftRecorderUnavailable'));
      return;
    }
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      setAiError(tr('voiceDraftMicDenied'));
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

  async function requestVoiceDraftFromAudio(file: File, durationSeconds?: number) {
    setVoiceDraftLoading(true);
    setAiError(null);
    try {
      applyVoiceDraft(await aiVoiceDrafts.fromAudio(file, durationSeconds));
    } catch (err) {
      setAiError(humanizeError(err, language, 'aiVoiceDraft'));
    } finally {
      setVoiceDraftLoading(false);
    }
  }

  function isFieldLowConfidence(field: VoiceDraftField): boolean {
    if (!voiceDraft) return false;
    if (!AI_EDITABLE_FIELDS.includes(field)) return false;
    return voiceDraft.field_confirmations[field] === 'extracted_unconfirmed' && voiceDraft.confidence < AI_LOW_CONFIDENCE;
  }

  // ── Step 3 — submit ────────────────────────────────────────────────────────
  async function submit() {
    if (!resolved) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      // If the debtor came from a QR token, re-resolve to confirm the same identity.
      if (resolved.source !== 'manual_userid' && resolved.token) {
        try {
          const recheck = await apiRequest<Profile>(`/qr/resolve/${encodeURIComponent(resolved.token)}`);
          if (recheck.id !== resolved.id) {
            setSubmitError(tr('scan_qr_error_expired'));
            setSubmitting(false);
            return;
          }
        } catch {
          setSubmitError(tr('scan_qr_error_expired'));
          setSubmitting(false);
          return;
        }
      }

      const created = await apiRequest<Debt>('/debts', {
        method: 'POST',
        body: JSON.stringify({
          debtor_id: resolved.id,
          debtor_name: resolved.name,
          amount: debtForm.amount,
          currency: debtForm.currency,
          description: debtForm.description,
          due_date: debtForm.due_date,
          notes: debtForm.notes,
          reminder_dates: reminderDates,
        }),
      });

      // Receipts (invoice)
      for (const item of receiptItems) {
        const fd = new FormData();
        fd.append('file', item.uploadFile, item.name);
        try {
          await apiRequest<Attachment>(`/debts/${created.id}/attachments?attachment_type=invoice`, {
            method: 'POST',
            body: fd,
          });
        } catch {
          /* surface failures via debt detail page */
        }
      }
      // Voice note
      if (voiceNoteFile) {
        const fd = new FormData();
        fd.append('file', voiceNoteFile, voiceNoteFile.name);
        try {
          await apiRequest<Attachment>(`/debts/${created.id}/attachments?attachment_type=voice_note`, {
            method: 'POST',
            body: fd,
          });
        } catch {
          /* non-fatal */
        }
      }

      navigate(`/debts/${created.id}`);
    } catch (err) {
      setSubmitError(humanizeError(err, language, 'transition'));
    } finally {
      setSubmitting(false);
    }
  }

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <section>
      <Panel title={tr('createDebt')}>

        {/* Visual step indicator */}
        <div className="create-debt-steps">
          <div className={`create-debt-steps__item${step === 1 ? ' create-debt-steps__item--active' : step > 1 ? ' create-debt-steps__item--done' : ''}`}>
            <div className="create-debt-steps__dot">{step > 1 ? <Check size={14} /> : '1'}</div>
            <span>{tr('debtorName')}</span>
          </div>
          <div className="create-debt-steps__line" />
          <div className={`create-debt-steps__item${step === 2 ? ' create-debt-steps__item--active' : step > 2 ? ' create-debt-steps__item--done' : ''}`}>
            <div className="create-debt-steps__dot">{step > 2 ? <Check size={14} /> : '2'}</div>
            <span>{tr('debtor_confirm_proceed')}</span>
          </div>
          <div className="create-debt-steps__line" />
          <div className={`create-debt-steps__item${step === 3 ? ' create-debt-steps__item--active' : ''}`}>
            <div className="create-debt-steps__dot">3</div>
            <span>{tr('createDebt')}</span>
          </div>
        </div>

        {/* Step 1 — Identify debtor */}
        {step === 1 && (
          <div className="create-debt-section">
            <div role="tablist" style={{ display: 'flex', gap: 8 }}>
              <button
                type="button"
                role="tab"
                aria-selected={identifyMode === 'scan'}
                className={`filter-tab${identifyMode === 'scan' ? ' active' : ''}`}
                onClick={() => { setIdentifyMode('scan'); setIdentifyError(null); }}
              >
                <Camera size={14} /> <span>{tr('scan_qr_camera_label')}</span>
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={identifyMode === 'manual'}
                className={`filter-tab${identifyMode === 'manual' ? ' active' : ''}`}
                onClick={() => { setIdentifyMode('manual'); setIdentifyError(null); }}
              >
                <Keyboard size={14} /> <span>{tr('scan_qr_manual_token_label')}</span>
              </button>
            </div>

            {identifyMode === 'scan' && (
              <QRScanner language={language} onResult={(token) => { if (!resolving) void resolveByToken(token); }} />
            )}

            {identifyMode === 'manual' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                <div style={{ display: 'flex', gap: 8 }}>
                  <button
                    type="button"
                    className={`filter-tab${manualMode === 'token' ? ' active' : ''}`}
                    onClick={() => setManualMode('token')}
                  >
                    {tr('scan_qr_manual_token_label')}
                  </button>
                  <button
                    type="button"
                    className={`filter-tab${manualMode === 'userid' ? ' active' : ''}`}
                    onClick={() => setManualMode('userid')}
                  >
                    {tr('scan_qr_manual_userid_label')}
                  </button>
                </div>
                <Input
                  label={manualMode === 'token' ? tr('scan_qr_manual_token_label') : tr('scan_qr_manual_userid_label')}
                  value={manualValue}
                  onChange={setManualValue}
                />
                <button className="primary-button" disabled={resolving || !manualValue.trim()} onClick={submitManual}>
                  {resolving ? '…' : tr('lookup')}
                </button>
              </div>
            )}

            {identifyError && (
              <div className="message error">
                <p style={{ margin: 0 }}>{identifyError}</p>
                <button
                  type="button"
                  className="link-button"
                  style={{ fontSize: '0.85rem', marginTop: 4 }}
                  onClick={() => setIdentifyError(null)}
                >
                  {tr('settlementCtaTryAgain')}
                </button>
              </div>
            )}
          </div>
        )}

        {/* Step 2 — Confirm debtor */}
        {step === 2 && resolved && (
          <DebtorConfirmCard
            profile={resolved}
            language={language}
            onBack={() => { setStep(1); setResolved(null); }}
            onConfirm={confirmDebtor}
          />
        )}

        {/* Step 3 — Debt form */}
        {step === 3 && resolved && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>

            {/* Locked debtor fields */}
            <div className="create-debt-section">
              <div className="create-debt-section__label">{tr('debtorName')}</div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                <LockedField label={tr('debtorName')} value={resolved.name} hint={tr('create_debt_locked_field_hint')} />
                <LockedField label={tr('debtorId')} value={resolved.id} hint={tr('create_debt_locked_field_hint')} />
              </div>
            </div>

            {/* Amount, currency, description, due date */}
            <div className="create-debt-section">
              <div className="create-debt-section__label">{tr('amount')} / {tr('dueDate')}</div>
              <Input label={tr('amount')} value={debtForm.amount} onChange={(v) => setDebtForm((f) => ({ ...f, amount: v }))} />
              {isFieldLowConfidence('amount') && <small style={{ color: '#b45309' }}>{tr('create_debt_ai_confidence_low_warning')}</small>}
              <Input label={tr('currency')} value={debtForm.currency} onChange={(v) => setDebtForm((f) => ({ ...f, currency: v }))} />
              <Input label={tr('description')} value={debtForm.description} onChange={(v) => setDebtForm((f) => ({ ...f, description: v }))} />
              {isFieldLowConfidence('description') && <small style={{ color: '#b45309' }}>{tr('create_debt_ai_confidence_low_warning')}</small>}
              <Input label={tr('dueDate')} type="date" value={debtForm.due_date} onChange={(v) => setDebtForm((f) => ({ ...f, due_date: v }))} />
              {isFieldLowConfidence('due_date') && <small style={{ color: '#b45309' }}>{tr('create_debt_ai_confidence_low_warning')}</small>}
            </div>

            {/* Reminder picker */}
            <div className="create-debt-section">
              <div className="create-debt-section__label">{tr('reminderDates')}</div>
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
                placeholder={tr('reminderDatePlaceholder')}
              />
              {reminderDates.length > 0 && (
                <div className="reminder-list">{reminderDates.join(', ')}</div>
              )}
            </div>

            {/* Attachments & voice note */}
            <div className="create-debt-section">
              <div className="create-debt-section__label">{tr('receiptList')}</div>
              <AttachmentUploader language={language} items={receiptItems} onItemsChange={setReceiptItems} />
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <label style={{ fontWeight: 600, fontSize: '0.84rem', color: 'var(--text-secondary)' }}>{tr('voiceDraftTitle')}</label>
                <input
                  type="file"
                  accept="audio/*"
                  onChange={(e) => setVoiceNoteFile(e.target.files?.[0] ?? null)}
                />
                {voiceNoteFile && <small style={{ color: 'var(--text-secondary)' }}>{voiceNoteFile.name}</small>}
              </div>
            </div>

            {/* AI voice draft (gated on ai_enabled) */}
            {profile?.ai_enabled && (
              <div className="voice-draft-panel">
                <h3>{tr('voiceDraftTitle')}</h3>
                <p className="muted">{tr('voiceDraftRecordHint')}</p>
                <div className="voice-draft-actions">
                  {!isRecording ? (
                    <button type="button" className="secondary-button" onClick={() => void startRecording()} disabled={voiceDraftLoading}>
                      <Mic size={16} /> <span>{tr('voiceDraftRecord')}</span>
                    </button>
                  ) : (
                    <button type="button" className="secondary-button" onClick={stopRecording}>
                      <Square size={16} /> <span>{tr('voiceDraftStop')}</span>
                    </button>
                  )}
                </div>
                {aiError && <p className="error-text">{aiError}</p>}
                {voiceDraftLoading && <p className="muted">{tr('voiceDraftProcessing')}</p>}
                {voiceDraft && (
                  <p className="muted">
                    <strong>{tr('voiceDraftTranscript')}:</strong> {voiceDraft.raw_transcript}
                  </p>
                )}
              </div>
            )}

            {submitError && <div className="message error">{submitError}</div>}

            {/* Submit / back */}
            <div className="create-debt-submit-row">
              <button type="button" className="ghost-button" onClick={() => setStep(2)}>
                {tr('cancel')}
              </button>
              <button
                type="button"
                className="primary-button"
                disabled={submitting || !debtForm.description.trim() || !debtForm.amount.trim()}
                onClick={() => void submit()}
              >
                <CreditCard size={18} /> <span>{submitting ? '…' : tr('create')}</span>
              </button>
            </div>
          </div>
        )}
      </Panel>
    </section>
  );
}

function LockedField({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <label className="field locked-field">
      <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
        <Lock size={12} /> {label}
      </span>
      <input type="text" value={value} readOnly disabled />
      <small>{hint}</small>
    </label>
  );
}
