import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Panel, Stat } from '../components/Layout';
import { useAuth } from '../contexts/AuthContext';
import { apiRequest } from '../lib/api';
import { t } from '../lib/i18n';
import type { Debt, Language, NotificationItem, Profile } from '../lib/types';

interface Props { language: Language }

function allStatusLabel(s: string, tr: (k: Parameters<typeof t>[1]) => string): string {
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

export function DashboardPage({ language }: Props) {
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

  // Separate by role
  const myDebtsAsCreditor = debts.filter(d => d.creditor_id === user?.id);
  const myDebtsAsDebtor = debts.filter(d => d.debtor_id === user?.id);

  const totalReceivable = myDebtsAsCreditor
    .filter(d => d.status === 'active' || d.status === 'delay' || d.status === 'payment_pending_confirmation')
    .reduce((sum, d) => sum + parseFloat(d.amount || '0'), 0);

  const totalOwed = myDebtsAsDebtor
    .filter(d => d.status === 'active' || d.status === 'delay')
    .reduce((sum, d) => sum + parseFloat(d.amount || '0'), 0);

  const waitingForMe = debts.filter(d => d.debtor_id === user?.id && d.status === 'waiting_for_confirmation');
  const delayDebts = isCreditor
    ? myDebtsAsCreditor.filter(d => d.status === 'delay')
    : myDebtsAsDebtor.filter(d => d.status === 'delay');

  const paymentPending = myDebtsAsCreditor.filter(d => d.status === 'payment_pending_confirmation');

  if (loading) return <p className="empty">{tr('loading')}</p>;

  // The other party's name for a debt
  function partyName(d: Debt) {
    return d.creditor_id === user?.id ? d.debtor_name : (d.creditor_name || d.creditor_id.slice(0, 8));
  }

  return (
    <section className="content-grid">

      {/* Financial stats */}
      {isCreditor && (
        <Stat label={tr('receivable')} value={`${totalReceivable.toFixed(2)} SAR`} sub={`${myDebtsAsCreditor.length} ${tr('debts')}`} />
      )}
      {isDebtor && (
        <Stat label={tr('totalOwed')} value={`${totalOwed.toFixed(2)} SAR`} sub={`${myDebtsAsDebtor.length} ${tr('debts')}`} />
      )}
      <Stat label={tr('waitingForConfirmation')} value={String(waitingForMe.length)} />
      <Stat label={tr('trustScore')} value={`${profile?.trust_score ?? 50} / 100`} />

      {/* Payment pending alerts — creditor needs to confirm */}
      {paymentPending.length > 0 && (
        <section className="wide-panel alert-panel">
          <h2>💰 {tr('paymentPendingConfirmation')}</h2>
          <div className="debt-stack">
            {paymentPending.map(d => (
              <div key={d.id} className="debt-item">
                <div>
                  <strong>{d.debtor_name}</strong>
                  <span>{d.description}</span>
                </div>
                <b>{d.amount} {d.currency}</b>
                <span className="status-badge payment_pending_confirmation">{tr('paymentPendingConfirmation')}</span>
              </div>
            ))}
          </div>
          <Link to="/debts" className="cta-link">{tr('viewAll')} →</Link>
        </section>
      )}

      {/* Delay / overdue alerts */}
      {delayDebts.length > 0 && (
        <section className="wide-panel alert-panel alert-danger">
          <h2>⚠️ {tr('delayAlerts')}</h2>
          <div className="debt-stack">
            {delayDebts.map(d => (
              <div key={d.id} className="debt-item">
                <div>
                  <strong>{partyName(d)}</strong>
                  <span>{d.description}</span>
                </div>
                <b>{d.amount} {d.currency}</b>
                <span className="status-badge delay">{tr('delay')}</span>
              </div>
            ))}
          </div>
          <Link to="/debts" className="cta-link">{tr('viewAll')} →</Link>
        </section>
      )}

      {/* Recent debts */}
      <section className={delayDebts.length > 0 || paymentPending.length > 0 ? 'panel' : 'wide-panel'}>
        <h2>{tr('recentDebts')} ({debts.length})</h2>
        <div className="compact-list">
          {debts.slice(0, 6).map((d) => (
            <div key={d.id}>
              <strong>{partyName(d)}</strong>
              <span>{d.amount} {d.currency}</span>
              <span className={`status-badge ${d.status}`}>
                {allStatusLabel(d.status, tr)}
              </span>
            </div>
          ))}
          {debts.length === 0 && (
            <div style={{ flexDirection: 'column', border: 'none', padding: '24px 0', gap: '12px' }}>
              <p className="empty" style={{ padding: 0 }}>{tr('noDebtsYet')}</p>
              {isCreditor && (
                <Link to="/debts" className="cta-link">{tr('debtCreatedCta')} →</Link>
              )}
            </div>
          )}
        </div>
      </section>

      {/* Notifications + stats panel */}
      <Panel title={tr('notifications')}>
        {isCreditor && (
          <div className="stat-rows">
            <div className="stat-row">
              <span>{tr('paid')}</span>
              <strong style={{ color: 'var(--success)' }}>{myDebtsAsCreditor.filter(d => d.status === 'paid').length}</strong>
            </div>
            <div className="stat-row">
              <span>{tr('myDebtors')}</span>
              <strong>{new Set(myDebtsAsCreditor.map(d => d.debtor_id).filter(Boolean)).size}</strong>
            </div>
          </div>
        )}
        <ul className="simple-list">
          {notifications.slice(0, 5).map((n) => (
            <li key={n.id} className={n.read_at ? '' : 'unread-notif'}>
              <strong>{n.title}</strong>: {n.body}
            </li>
          ))}
          {notifications.length === 0 && <p className="empty">{tr('noUnread')}</p>}
        </ul>
        {notifications.length > 5 && (
          <Link to="/notifications" className="cta-link" style={{ marginTop: '8px', display: 'block' }}>
            {tr('viewAll')} →
          </Link>
        )}
        <p className="trust-disclaimer">{tr('trustScoreDisclaimer')}</p>
      </Panel>
    </section>
  );
}
