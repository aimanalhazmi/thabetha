import { useEffect, useState } from 'react';
import { Panel, Stat } from '../components/Layout';
import { useAuth } from '../contexts/AuthContext';
import { apiRequest } from '../lib/api';
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

  useEffect(() => {
    setLoading(true);
    void Promise.all([
      apiRequest<Profile>('/profiles/me').then(setProfile).catch(() => {}),
      apiRequest<Debt[]>('/debts').then(setDebts).catch(() => {}),
      apiRequest<NotificationItem[]>('/notifications').then(setNotifications).catch(() => {}),
    ]).finally(() => setLoading(false));
  }, []);

  const isCreditor = user?.account_type === 'creditor' || user?.account_type === 'both';
  const isDebtor = user?.account_type === 'debtor' || user?.account_type === 'both';

  // Calculate stats
  const activeDebts = debts.filter(d => d.status === 'active');
  const waitingDebts = debts.filter(d => d.status === 'waiting_for_confirmation');
  const delayDebts = debts.filter(d => d.status === 'delay');
  const paidDebts = debts.filter(d => d.status === 'paid');

  const totalAmount = debts
    .filter(d => d.status === 'active' || d.status === 'delay')
    .reduce((sum, d) => sum + parseFloat(d.amount || '0'), 0);

  if (loading) return <p className="empty">{tr('loading')}</p>;

  return (
    <section className="content-grid">
      {message && <div className="message" style={{ gridColumn: '1 / -1' }}>{message}</div>}

      <Stat label={isCreditor ? tr('receivable') : tr('totalDebt')} value={`${totalAmount.toFixed(2)} SAR`} />
      <Stat label={tr('active')} value={String(activeDebts.length)} />
      <Stat label={tr('waitingForConfirmation')} value={String(waitingDebts.length)} />
      <Stat label={tr('trustScore')} value={`${profile?.trust_score ?? 50} / 100`} />

      {/* Delay Alerts */}
      {delayDebts.length > 0 && (
        <section className="wide-panel">
          <h2>⚠️ {tr('delayAlerts')}</h2>
          <div className="debt-stack">
            {delayDebts.map(d => (
              <div key={d.id} className="debt-item">
                <div>
                  <strong>{d.debtor_name}</strong>
                  <span>{d.description}</span>
                </div>
                <b>{d.amount} {d.currency}</b>
                <span className="status-badge delay">{tr('delay')}</span>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Recent debts */}
      <section className={delayDebts.length > 0 ? 'panel' : 'wide-panel'}>
        <h2>{tr('recentDebts')} ({debts.length})</h2>
        <div className="compact-list">
          {debts.slice(0, 6).map((d) => (
            <div key={d.id}>
              <strong>{d.debtor_name}</strong>
              <span>{d.amount} {d.currency}</span>
              <span className={`status-badge ${d.status}`}>
                {d.status === 'waiting_for_confirmation' ? tr('waitingForConfirmation')
                  : d.status === 'active' ? tr('active')
                  : d.status === 'paid' ? tr('paid')
                  : tr('delay')}
              </span>
            </div>
          ))}
          {debts.length === 0 && <p className="empty">{tr('noDebtsYet')}</p>}
        </div>
      </section>

      {/* Stats panel */}
      <Panel title={delayDebts.length > 0 ? tr('notifications') : tr('notifications')}>
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
        <p className="trust-disclaimer">{tr('trustScoreDisclaimer')}</p>
      </Panel>
    </section>
  );
}
