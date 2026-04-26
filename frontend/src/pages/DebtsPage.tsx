import { AlertTriangle, Check, CreditCard, WalletCards, X } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { Input, Panel } from '../components/Layout';
import { useAuth } from '../contexts/AuthContext';
import { useToast } from '../contexts/ToastContext';
import { apiRequest } from '../lib/api';
import { t } from '../lib/i18n';
import type { Debt, DebtStatus, Language, VoiceDraft } from '../lib/types';

interface Props { language: Language }

const statusKeys: (DebtStatus | 'all')[] = [
  'all',
  'waiting_for_confirmation',
  'change_requested',
  'active',
  'payment_pending_confirmation',
  'paid',
  'delay',
  'rejected',
];

interface ChangeRequestForm {
  message: string;
  requested_amount: string;
  requested_due_date: string;
}

function isDueSoon(dueDate: string): boolean {
  const due = new Date(dueDate);
  const now = new Date();
  const diffDays = (due.getTime() - now.getTime()) / (1000 * 60 * 60 * 24);
  return diffDays >= 0 && diffDays <= 3;
}

export function DebtsPage({ language }: Props) {
  const tr = (key: Parameters<typeof t>[1]) => t(language, key);
  const { user } = useAuth();
  const { showToast } = useToast();
  const location = useLocation();

  const isCreditor = user?.account_type === 'creditor' || user?.account_type === 'both';

  // Pre-fill from AI voice draft navigation
  const draftFromAI = (location.state as { draftDebt?: VoiceDraft } | undefined)?.draftDebt;

  const [debts, setDebts] = useState<Debt[]>([]);
  const [filter, setFilter] = useState<DebtStatus | 'all'>('all');
  const [loadingActions, setLoadingActions] = useState<Record<string, boolean>>({});
  const [expandedChangeRequest, setExpandedChangeRequest] = useState<string | null>(null);
  const [rejectTarget, setRejectTarget] = useState<string | null>(null);
  const [changeForm, setChangeForm] = useState<ChangeRequestForm>({
    message: '',
    requested_amount: '',
    requested_due_date: '',
  });

  const [debtForm, setDebtForm] = useState({
    debtor_name: draftFromAI?.debtor_name ?? '',
    debtor_id: '',
    amount: draftFromAI?.amount ?? '25.00',
    currency: draftFromAI?.currency ?? 'SAR',
    description: draftFromAI?.description ?? '',
    due_date: draftFromAI?.due_date ?? new Date(Date.now() + 7 * 86400000).toISOString().slice(0, 10),
    notes: '',
  });

  async function load() {
    try {
      setDebts(await apiRequest<Debt[]>('/debts'));
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'Failed to load', 'error');
    }
  }

  useEffect(() => { void load(); }, []);

  function setActionLoading(key: string, val: boolean) {
    setLoadingActions(prev => ({ ...prev, [key]: val }));
  }

  async function runAction(key: string, action: () => Promise<unknown>, successMsg: string) {
    setActionLoading(key, true);
    try {
      await action();
      showToast(successMsg, 'success');
      await load();
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'Action failed', 'error');
    } finally {
      setActionLoading(key, false);
    }
  }

  async function submitChangeRequest(debtId: string) {
    const body: Record<string, string> = { message: changeForm.message };
    if (changeForm.requested_amount) body.requested_amount = changeForm.requested_amount;
    if (changeForm.requested_due_date) body.requested_due_date = changeForm.requested_due_date;
    await runAction(
      `${debtId}-change`,
      () => apiRequest(`/debts/${debtId}/change-request`, { method: 'POST', body: JSON.stringify(body) }),
      language === 'ar' ? 'تم إرسال طلب التعديل' : 'Change request sent',
    );
    setExpandedChangeRequest(null);
    setChangeForm({ message: '', requested_amount: '', requested_due_date: '' });
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
      case 'waiting_for_confirmation': return tr('waitingForConfirmation');
      case 'active': return tr('active');
      case 'paid': return tr('paid');
      case 'delay': return tr('delay');
      case 'rejected': return tr('rejected');
      case 'change_requested': return tr('changeRequested');
      case 'payment_pending_confirmation': return tr('paymentPendingConfirmation');
      default: return s;
    }
  }

  const isDebtorOf = (debt: Debt) => debt.debtor_id === user?.id;
  const isCreditorOf = (debt: Debt) => debt.creditor_id === user?.id;

  // The other party's name
  function partyDisplay(debt: Debt) {
    if (isCreditorOf(debt)) {
      return { label: tr('debtorName'), name: debt.debtor_name };
    }
    return { label: tr('creditorLabel'), name: debt.creditor_name || debt.creditor_id.slice(0, 8) };
  }

  return (
    <section className="split">
      {/* Create debt panel — creditors only */}
      {isCreditor && (
        <Panel title={tr('createDebt')}>
          {draftFromAI && (
            <div className="message" style={{ marginBottom: '8px', fontSize: '0.82rem' }}>
              {language === 'ar' ? '✨ تم تعبئة البيانات من مسودة الذكاء الاصطناعي' : '✨ Pre-filled from AI draft'}
            </div>
          )}
          <Input label={tr('debtorName')} value={debtForm.debtor_name} onChange={(v) => setDebtForm({ ...debtForm, debtor_name: v })} />
          <Input
            label={tr('debtorId')}
            value={debtForm.debtor_id}
            onChange={(v) => setDebtForm({ ...debtForm, debtor_id: v })}
            placeholder={language === 'ar' ? 'معرف المدين — انسخه من صفحة QR' : 'Debtor user ID — copy from QR page'}
          />
          <Input label={tr('amount')} value={debtForm.amount} onChange={(v) => setDebtForm({ ...debtForm, amount: v })} />
          <Input label={tr('currency')} value={debtForm.currency} onChange={(v) => setDebtForm({ ...debtForm, currency: v })} />
          <Input label={tr('description')} value={debtForm.description} onChange={(v) => setDebtForm({ ...debtForm, description: v })} />
          <Input label={tr('dueDate')} type="date" value={debtForm.due_date} onChange={(v) => setDebtForm({ ...debtForm, due_date: v })} />
          <button
            className="primary-button"
            disabled={loadingActions['create'] || !debtForm.debtor_name || !debtForm.description}
            onClick={() => void runAction(
              'create',
              () => apiRequest<Debt>('/debts', { method: 'POST', body: JSON.stringify(debtForm) }),
              language === 'ar' ? 'تم إنشاء الدين وإرساله للمدين' : 'Debt created and sent to debtor',
            )}
          >
            <CreditCard size={18} />
            <span>{loadingActions['create'] ? '...' : tr('create')}</span>
          </button>
        </Panel>
      )}

      <Panel title={`${tr('debts')} (${debts.length})`}>
        {/* Filter tabs — only statuses with debts */}
        <div className="filter-tabs">
          {statusKeys
            .filter(s => s === 'all' || (statusCounts[s] ?? 0) > 0)
            .map(s => (
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
            const { label: partyLabel, name: partyName } = partyDisplay(debt);
            const dueSoon = (debt.status === 'active' || debt.status === 'waiting_for_confirmation') && isDueSoon(debt.due_date);

            return (
              <article key={debt.id} className={`debt-item${dueSoon ? ' due-soon' : ''}`}>
                <div>
                  <strong>{partyName}</strong>
                  <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontWeight: 500 }}>
                    {partyLabel}
                  </span>
                  <span>{debt.description}</span>
                  <span className="due-date-line">
                    {language === 'ar' ? 'الاستحقاق:' : 'Due:'} {debt.due_date}
                    {dueSoon && (
                      <span className="due-soon-badge">
                        <AlertTriangle size={11} /> {tr('dueSoonWarning')}
                      </span>
                    )}
                  </span>
                </div>
                <b>{debt.amount} {debt.currency}</b>
                <span className={`status-badge ${debt.status}`}>
                  {statusLabel(debt.status)}
                </span>

                <div className="actions">
                  {/* Debtor: waiting_for_confirmation */}
                  {isDebtorOf(debt) && debt.status === 'waiting_for_confirmation' && (
                    <>
                      <button
                        disabled={!!loadingActions[`${debt.id}-accept`]}
                        onClick={() => void runAction(
                          `${debt.id}-accept`,
                          () => apiRequest(`/debts/${debt.id}/accept`, { method: 'POST' }),
                          language === 'ar' ? 'تم قبول الدين' : 'Debt accepted',
                        )}
                      >
                        <Check size={16} /><span>{loadingActions[`${debt.id}-accept`] ? '...' : tr('accept')}</span>
                      </button>
                      <button
                        disabled={!!loadingActions[`${debt.id}-reject`]}
                        onClick={() => setRejectTarget(debt.id)}
                      >
                        <X size={16} /><span>{tr('reject')}</span>
                      </button>
                      <button
                        className="ghost-button"
                        onClick={() => setExpandedChangeRequest(expandedChangeRequest === debt.id ? null : debt.id)}
                      >
                        <span>{tr('requestChange')}</span>
                      </button>
                    </>
                  )}

                  {/* Debtor: change_requested — can still accept or reject */}
                  {isDebtorOf(debt) && debt.status === 'change_requested' && (
                    <>
                      <button
                        disabled={!!loadingActions[`${debt.id}-accept`]}
                        onClick={() => void runAction(
                          `${debt.id}-accept`,
                          () => apiRequest(`/debts/${debt.id}/accept`, { method: 'POST' }),
                          language === 'ar' ? 'تم قبول الدين' : 'Debt accepted',
                        )}
                      >
                        <Check size={16} /><span>{loadingActions[`${debt.id}-accept`] ? '...' : tr('accept')}</span>
                      </button>
                      <button onClick={() => setRejectTarget(debt.id)}>
                        <X size={16} /><span>{tr('reject')}</span>
                      </button>
                    </>
                  )}

                  {/* Debtor: mark paid on active or delayed */}
                  {isDebtorOf(debt) && (debt.status === 'active' || debt.status === 'delay') && (
                    <button
                      disabled={!!loadingActions[`${debt.id}-markpaid`]}
                      onClick={() => void runAction(
                        `${debt.id}-markpaid`,
                        () => apiRequest(`/debts/${debt.id}/mark-paid`, { method: 'POST', body: JSON.stringify({ note: 'Paid' }) }),
                        language === 'ar' ? 'تم إرسال طلب تأكيد الدفع للدائن' : 'Payment confirmation sent to creditor',
                      )}
                    >
                      <WalletCards size={16} />
                      <span>{loadingActions[`${debt.id}-markpaid`] ? '...' : tr('markPaid')}</span>
                    </button>
                  )}

                  {/* Creditor: confirm payment */}
                  {isCreditorOf(debt) && debt.status === 'payment_pending_confirmation' && (
                    <button
                      disabled={!!loadingActions[`${debt.id}-confirmpay`]}
                      onClick={() => void runAction(
                        `${debt.id}-confirmpay`,
                        () => apiRequest(`/debts/${debt.id}/confirm-payment`, { method: 'POST' }),
                        language === 'ar' ? 'تم تأكيد استلام الدفع' : 'Payment confirmed',
                      )}
                    >
                      <Check size={16} />
                      <span>{loadingActions[`${debt.id}-confirmpay`] ? '...' : tr('confirmPayment')}</span>
                    </button>
                  )}
                </div>

                {/* Inline reject confirmation */}
                {rejectTarget === debt.id && (
                  <div className="confirm-inline">
                    <span>{language === 'ar' ? 'هل أنت متأكد من رفض هذا الدين؟' : 'Are you sure you want to reject this debt?'}</span>
                    <div style={{ display: 'flex', gap: '8px', marginTop: '8px' }}>
                      <button
                        className="danger-button"
                        disabled={!!loadingActions[`${debt.id}-reject`]}
                        onClick={() => void runAction(
                          `${debt.id}-reject`,
                          () => apiRequest(`/debts/${debt.id}/reject`, { method: 'POST', body: JSON.stringify({ message: 'Rejected' }) }),
                          language === 'ar' ? 'تم رفض الدين' : 'Debt rejected',
                        ).then(() => setRejectTarget(null))}
                      >
                        {tr('confirmReject')}
                      </button>
                      <button className="ghost-button" onClick={() => setRejectTarget(null)}>
                        {tr('cancel')}
                      </button>
                    </div>
                  </div>
                )}

                {/* Inline change-request form */}
                {expandedChangeRequest === debt.id && (
                  <div className="change-request-form">
                    <Input
                      label={tr('changeMessage')}
                      value={changeForm.message}
                      onChange={(v) => setChangeForm({ ...changeForm, message: v })}
                    />
                    <Input
                      label={tr('newAmount')}
                      value={changeForm.requested_amount}
                      onChange={(v) => setChangeForm({ ...changeForm, requested_amount: v })}
                    />
                    <Input
                      label={tr('newDueDate')}
                      type="date"
                      value={changeForm.requested_due_date}
                      onChange={(v) => setChangeForm({ ...changeForm, requested_due_date: v })}
                    />
                    <div style={{ display: 'flex', gap: '8px' }}>
                      <button
                        className="primary-button"
                        disabled={!changeForm.message || !!loadingActions[`${debt.id}-change`]}
                        onClick={() => void submitChangeRequest(debt.id)}
                      >
                        {loadingActions[`${debt.id}-change`] ? '...' : tr('submitChangeRequest')}
                      </button>
                      <button className="ghost-button" onClick={() => setExpandedChangeRequest(null)}>
                        <X size={16} />
                      </button>
                    </div>
                  </div>
                )}
              </article>
            );
          })}
          {filtered.length === 0 && (
            <p className="empty">{filter === 'all' ? tr('noDebtsYet') : tr('noDebtsCta')}</p>
          )}
        </div>
      </Panel>
    </section>
  );
}
