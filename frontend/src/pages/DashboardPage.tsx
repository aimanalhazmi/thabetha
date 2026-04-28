import { useEffect, useState } from 'react';
import { Panel, Stat } from '../components/Layout';
import { useAuth } from '../contexts/AuthContext';
import { apiRequest } from '../lib/api';
import { humanizeError } from '../lib/errors';
import { t } from '../lib/i18n';
import type { Debt, Language, NotificationItem, Profile } from '../lib/types';

interface Props {
  language: Language;
  message: string;
}

export function DashboardPage({ language, message }: Props) {
  const tr = (key: Parameters<typeof t>[1]) => t(language, key);
  const { user } = useAuth();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [debts, setDebts] = useState<Debt[]>([]);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    const loadAll = (initial: boolean) => {
      if (initial) { setLoading(true); setLoadError(null); }
      const promise = Promise.all([
        apiRequest<Profile>('/profiles/me').then(setProfile).catch(() => {}),
        apiRequest<Debt[]>('/debts').then(setDebts).catch((err) => {
          if (initial) setLoadError(humanizeError(err, language, 'loadDashboard'));
        }),
        apiRequest<NotificationItem[]>('/notifications').then(setNotifications).catch(() => {}),
      ]);
      if (initial) {
        void promise.finally(() => setLoading(false));
      } else {
        void promise;
      }
    };
    loadAll(true);
    const interval = setInterval(() => loadAll(false), 30_000);
    return () => clearInterval(interval);
  }, [language]);

  const isCreditor = user?.account_type === 'creditor' || user?.account_type === 'both' || user?.account_type === 'business';
  const isDebtor = user?.account_type === 'debtor' || user?.account_type === 'both';

  // Calculate stats
  const activeDebts = debts.filter(d => d.status === 'active');
  const waitingDebts = debts.filter(d => d.status === 'pending_confirmation');
  const overdueDebts = debts.filter(d => d.status === 'overdue');
  const paidDebts = debts.filter(d => d.status === 'paid');

  const paymentPendingDebts = debts.filter(d => d.status === 'payment_pending_confirmation');

  const totalAmount = debts
    .filter(d => d.status === 'active' || d.status === 'overdue' || d.status === 'payment_pending_confirmation')
    .reduce((sum, d) => sum + parseFloat(d.amount || '0'), 0);

  if (loading) return <p className="empty">{tr('loading')}</p>;
  if (loadError) return <p className="empty">{loadError}</p>;

  return (
    <section className="content-grid">
      {message && <div className="message" style={{ gridColumn: '1 / -1' }}>{message}</div>}

      {isCreditor && (
        <section className="wide-panel ai-upgrade-card">
          <div>
            <h2>{profile?.ai_enabled ? `✨ ${tr('aiActive')}` : `🤖 ${tr('upgradeToAi')}`}</h2>
            <p style={{ color: '#64748b', margin: '0.25rem 0 0' }}>{tr('upgradeToAiDesc')}</p>
          </div>
          {!profile?.ai_enabled && (
            <a href="/ai" className="primary-button" style={{ textDecoration: 'none' }}>
              {tr('upgradeNow')}
            </a>
          )}
        </section>
      )}

      <Stat label={isCreditor ? tr('receivable') : tr('totalDebt')} value={`${totalAmount.toFixed(2)} SAR`} />
      <Stat label={tr('active')} value={String(activeDebts.length)} />
      <Stat label={tr('pendingConfirmation')} value={String(waitingDebts.length)} />
      <Stat label={tr('paymentPendingConfirmation')} value={String(paymentPendingDebts.length)} />
      <Stat label={tr('commitmentIndicator')} value={`${profile?.commitment_score ?? 50} / 100`} />

      {/* Delay Alerts */}
      {overdueDebts.length > 0 && (
        <section className="wide-panel">
          <h2>⚠️ {tr('overdueAlerts')}</h2>
          <div className="debt-stack">
            {overdueDebts.map(d => (
              <div key={d.id} className="debt-item">
                <div>
                  <strong>{d.debtor_name}</strong>
                  <span>{d.description}</span>
                </div>
                <b>{d.amount} {d.currency}</b>
                <span className="status-badge overdue">{tr('overdue')}</span>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Recent debts */}
      <section className={overdueDebts.length > 0 ? 'panel' : 'wide-panel'}>
        <h2>{tr('recentDebts')} ({debts.length})</h2>
        <div className="compact-list">
          {debts.slice(0, 6).map((d) => (
            <div key={d.id}>
              <strong>{d.debtor_name}</strong>
              <span>{d.amount} {d.currency}</span>
              <span className={`status-badge ${d.status}`}>
                {d.status === 'pending_confirmation' ? tr('pendingConfirmation')
                  : d.status === 'active' ? tr('active')
                  : d.status === 'paid' ? tr('paid')
                  : d.status === 'edit_requested' ? tr('editRequested')
                  : d.status === 'payment_pending_confirmation' ? tr('paymentPendingConfirmation')
                  : d.status === 'cancelled' ? tr('cancelled')
                  : tr('overdue')}
              </span>
            </div>
          ))}
          {debts.length === 0 && <p className="empty">{tr('noDebtsYet')}</p>}
        </div>
      </section>

      {/* Stats panel */}
      <Panel title={overdueDebts.length > 0 ? tr('notifications') : tr('notifications')}>
        {isCreditor && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginBottom: '8px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem' }}>
              <span>{tr('paid')}</span>
              <strong style={{ color: 'var(--success)' }}>{paidDebts.length}</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem' }}>
              <span>{tr('debtors')}</span>
              <strong>{new Set(debts.map(d => d.debtor_id).filter(Boolean)).size}</strong>
            </div>
          </div>
        )}
        <ul className="simple-list">
          {notifications.slice(0, 5).map((n) => (
            <li key={n.id}><strong>{n.title}</strong>: {n.body}</li>
          ))}
          {notifications.length === 0 && <p className="empty">{tr('noData')}</p>}
        </ul>
        <p className="trust-disclaimer">{tr('commitmentDisclaimer')}</p>
      </Panel>
    </section>
  );
}
