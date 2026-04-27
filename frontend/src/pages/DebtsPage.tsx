import { Check, CreditCard, Pencil, WalletCards, X } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { Input, Panel } from '../components/Layout';
import { useAuth } from '../contexts/AuthContext';
import { apiRequest } from '../lib/api';
import { t } from '../lib/i18n';
import type { Debt, DebtStatus, Language } from '../lib/types';

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
  const isCreditor = user?.account_type === 'creditor' || user?.account_type === 'both';
  const [debts, setDebts] = useState<Debt[]>([]);
  const [message, setMessage] = useState('');
  const [filter, setFilter] = useState<DebtStatus | 'all'>('all');
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

  async function load() {
    try {
      const data = await apiRequest<Debt[]>('/debts');
      setDebts(data);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'Failed to load');
    }
  }

  useEffect(() => { void load(); }, []);

  async function runAction(action: () => Promise<unknown>, success: string) {
    try {
      await action();
      setMessage(success);
      await load();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'Action failed');
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
          <Input label={tr('debtorName')} value={debtForm.debtor_name} onChange={(v) => setDebtForm({ ...debtForm, debtor_name: v })} />
          <Input label={tr('debtorId')} value={debtForm.debtor_id} onChange={(v) => setDebtForm({ ...debtForm, debtor_id: v })} placeholder={language === 'ar' ? 'معرف المدين (اختياري)' : 'Debtor user ID (optional)'} />
          <Input label={tr('amount')} value={debtForm.amount} onChange={(v) => setDebtForm({ ...debtForm, amount: v })} />
          <Input label={tr('currency')} value={debtForm.currency} onChange={(v) => setDebtForm({ ...debtForm, currency: v })} />
          <Input label={tr('description')} value={debtForm.description} onChange={(v) => setDebtForm({ ...debtForm, description: v })} />
          <Input label={tr('dueDate')} type="date" value={debtForm.due_date} onChange={(v) => setDebtForm({ ...debtForm, due_date: v })} />

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

          <button
            className="primary-button"
            onClick={() => void runAction(
              () => apiRequest<Debt>('/debts', {
                method: 'POST',
                body: JSON.stringify({ ...debtForm, reminder_dates: reminderDates }),
              }),
              language === 'ar' ? 'تم إنشاء الدين' : 'Debt created',
            )}
          >
            <CreditCard size={18} />
            <span>{tr('create')}</span>
          </button>
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
          {filtered.map((debt) => (
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
                  <button onClick={() => void runAction(() => apiRequest(`/debts/${debt.id}/accept`, { method: 'POST' }), language === 'ar' ? 'تم قبول الدين' : 'Debt accepted')}>
                    <Check size={16} /><span>{tr('accept')}</span>
                  </button>
                )}
                {!isCreditor && debt.status === 'pending_confirmation' && (
                  <button onClick={() => {
                    const message = window.prompt(language === 'ar' ? 'سبب طلب التعديل' : 'Reason for edit') ?? '';
                    if (!message) return;
                    void runAction(
                      () => apiRequest(`/debts/${debt.id}/edit-request`, { method: 'POST', body: JSON.stringify({ message }) }),
                      language === 'ar' ? 'تم إرسال طلب التعديل' : 'Edit requested',
                    );
                  }}>
                    <Pencil size={16} /><span>{tr('requestEdit')}</span>
                  </button>
                )}
                {!isCreditor && (debt.status === 'active' || debt.status === 'overdue') && (
                  <button onClick={() => void runAction(() => apiRequest(`/debts/${debt.id}/mark-paid`, { method: 'POST', body: JSON.stringify({ note: 'Paid' }) }), language === 'ar' ? 'تم طلب تأكيد الدفع' : 'Payment requested')}>
                    <WalletCards size={16} /><span>{tr('markPaid')}</span>
                  </button>
                )}
                {isCreditor && debt.status === 'edit_requested' && (
                  <>
                    <button onClick={() => void runAction(() => apiRequest(`/debts/${debt.id}/edit-request/approve`, { method: 'POST', body: JSON.stringify({ message: 'Approved' }) }), language === 'ar' ? 'تمت الموافقة على التعديل' : 'Edit approved')}>
                      <Check size={16} /><span>{tr('approveEdit')}</span>
                    </button>
                    <button onClick={() => void runAction(() => apiRequest(`/debts/${debt.id}/edit-request/reject`, { method: 'POST', body: JSON.stringify({ message: 'Original terms stand' }) }), language === 'ar' ? 'تم رفض التعديل' : 'Edit rejected')}>
                      <X size={16} /><span>{tr('rejectEdit')}</span>
                    </button>
                  </>
                )}
                {isCreditor && debt.status === 'payment_pending_confirmation' && (
                  <button onClick={() => void runAction(() => apiRequest(`/debts/${debt.id}/confirm-payment`, { method: 'POST' }), language === 'ar' ? 'تم تأكيد الدفع' : 'Payment confirmed')}>
                    <Check size={16} /><span>{tr('confirmPayment')}</span>
                  </button>
                )}
                {isCreditor && (debt.status === 'pending_confirmation' || debt.status === 'edit_requested') && (
                  <button onClick={() => void runAction(() => apiRequest(`/debts/${debt.id}/cancel`, { method: 'POST', body: JSON.stringify({ message: 'Cancelled' }) }), language === 'ar' ? 'تم إلغاء الدين' : 'Debt cancelled')}>
                    <X size={16} /><span>{tr('cancel')}</span>
                  </button>
                )}
              </div>
            </article>
          ))}
          {filtered.length === 0 && <p className="empty">{tr('noDebtsYet')}</p>}
        </div>
      </Panel>
    </section>
  );
}
