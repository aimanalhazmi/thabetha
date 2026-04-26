import { Check, CreditCard, WalletCards, X } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { Input, Panel } from '../components/Layout';
import { useAuth } from '../contexts/AuthContext';
import { apiRequest } from '../lib/api';
import { t } from '../lib/i18n';
import type { Debt, DebtStatus, Language } from '../lib/types';

interface Props { language: Language }

const statusKeys: (DebtStatus | 'all')[] = ['all', 'waiting_for_confirmation', 'active', 'paid', 'delay'];

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
      case 'waiting_for_confirmation': return tr('waitingForConfirmation');
      case 'active': return tr('active');
      case 'paid': return tr('paid');
      case 'delay': return tr('delay');
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
          <button
            className="primary-button"
            onClick={() => void runAction(() => apiRequest<Debt>('/debts', { method: 'POST', body: JSON.stringify(debtForm) }), language === 'ar' ? 'تم إنشاء الدين' : 'Debt created')}
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
                {debt.status === 'waiting_for_confirmation' && (
                  <>
                    <button onClick={() => void runAction(() => apiRequest(`/debts/${debt.id}/accept`, { method: 'POST' }), language === 'ar' ? 'تم قبول الدين' : 'Debt accepted')}>
                      <Check size={16} /><span>{tr('accept')}</span>
                    </button>
                    <button onClick={() => void runAction(() => apiRequest(`/debts/${debt.id}/reject`, { method: 'POST', body: JSON.stringify({ message: 'Rejected' }) }), language === 'ar' ? 'تم رفض الدين' : 'Debt rejected')}>
                      <X size={16} /><span>{tr('reject')}</span>
                    </button>
                  </>
                )}
                {(debt.status === 'active' || debt.status === 'delay') && (
                  <button onClick={() => void runAction(() => apiRequest(`/debts/${debt.id}/mark-paid`, { method: 'POST', body: JSON.stringify({ note: 'Paid' }) }), language === 'ar' ? 'تم طلب تأكيد الدفع' : 'Payment requested')}>
                    <WalletCards size={16} /><span>{tr('markPaid')}</span>
                  </button>
                )}
                {debt.status === 'active' && (
                  <button onClick={() => void runAction(() => apiRequest(`/debts/${debt.id}/confirm-payment`, { method: 'POST' }), language === 'ar' ? 'تم تأكيد الدفع' : 'Payment confirmed')}>
                    <Check size={16} /><span>{tr('confirmPayment')}</span>
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
