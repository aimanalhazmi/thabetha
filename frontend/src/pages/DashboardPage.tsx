import { Activity, AlertTriangle, ArrowRight, Award, Bell, CircleDollarSign, Clock, TrendingUp } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { apiRequest } from '../lib/api';
import { humanizeError } from '../lib/errors';
import { t } from '../lib/i18n';
import type { Debt, Language, NotificationItem, Profile } from '../lib/types';

interface Props {
  language: Language;
  message: string;
}

// Local enhanced stat card — does not affect the shared Layout.Stat export
function StatCard({
  label,
  value,
  icon: Icon,
  accent,
}: {
  label: string;
  value: string;
  icon: React.ElementType;
  accent: 'primary' | 'warning' | 'danger' | 'info' | 'success' | 'purple';
}) {
  return (
    <section className={`dash-stat-card dash-stat-card--${accent}`}>
      <div className="dash-stat-card__icon">
        <Icon size={20} />
      </div>
      <div className="dash-stat-card__body">
        <span className="dash-stat-card__label">{label}</span>
        <strong className="dash-stat-card__value">{value}</strong>
      </div>
    </section>
  );
}

function ScoreBar({ score }: { score: number }) {
  const color = score >= 70 ? 'var(--success)' : score >= 40 ? 'var(--warning)' : 'var(--danger)';
  return (
    <div className="score-bar">
      <div className="score-bar-fill" style={{ width: `${score}%`, background: color }} />
    </div>
  );
}

function getInitials(name: string) {
  return name.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase();
}

export function DashboardPage({ language, message }: Props) {
  const tr = (key: Parameters<typeof t>[1]) => t(language, key);
  const { user } = useAuth();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<'overview' | 'statistics'>('overview');
  const [profile, setProfile] = useState<Profile | null>(null);
  const [debts, setDebts] = useState<Debt[]>([]);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  // ── Data fetching — untouched ─────────────────────────────────
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

  // ── Derived state — untouched ─────────────────────────────────
  const isCreditor = user?.account_type === 'creditor' || user?.account_type === 'both' || user?.account_type === 'business';

  const activeDebts = debts.filter(d => d.status === 'active');
  const waitingDebts = debts.filter(d => d.status === 'pending_confirmation');
  const overdueDebts = debts.filter(d => d.status === 'overdue');
  const paidDebts = debts.filter(d => d.status === 'paid');
  const paymentPendingDebts = debts.filter(d => d.status === 'payment_pending_confirmation');
  const commitmentScore = profile?.commitment_score ?? 50;

  const totalAmount = debts
    .filter(d => d.status === 'active' || d.status === 'overdue' || d.status === 'payment_pending_confirmation')
    .reduce((sum, d) => sum + parseFloat(d.amount || '0'), 0);

  const unreadCount = notifications.filter(n => !n.read_at).length;

  // ── Loading / error states ────────────────────────────────────
  if (loading) {
    return (
      <div className="dash-loading">
        <div className="spinner" />
      </div>
    );
  }
  if (loadError) return <p className="empty">{loadError}</p>;

  return (
    <section className="content-grid">
      {message && <div className="message" style={{ gridColumn: '1 / -1' }}>{message}</div>}

      {/* Tab switcher — creditor only */}
      {isCreditor && (
        <div className="filter-tabs-container" style={{ gridColumn: '1 / -1', marginBottom: '8px' }}>
          <button
            className={`filter-tab ${activeTab === 'overview' ? 'active' : ''}`}
            onClick={() => setActiveTab('overview')}
          >
            {tr('dashboard')}
          </button>
          <button
            className={`filter-tab ${activeTab === 'statistics' ? 'active' : ''}`}
            onClick={() => setActiveTab('statistics')}
          >
            {tr('stats_tab_label')}
          </button>
        </div>
      )}

      {/* Statistics tab */}
      {activeTab === 'statistics' && (
        <section className="wide-panel" style={{ gridColumn: '1 / -1' }}>
          <h2>{tr('stats_tab_label')}</h2>
          <div className="content-grid">
            <div className="stat" onClick={() => navigate('/debts?status=active')} style={{ cursor: 'pointer' }} role="button" tabIndex={0}>
              <span>{tr('debts_filter_active')}</span>
              <strong>{activeDebts.length}</strong>
            </div>
            <div className="stat" onClick={() => navigate('/debts?status=pending_confirmation')} style={{ cursor: 'pointer' }} role="button" tabIndex={0}>
              <span>{tr('debts_filter_pending')}</span>
              <strong>{waitingDebts.length}</strong>
            </div>
            <div className="stat" onClick={() => navigate('/debts?status=overdue')} style={{ cursor: 'pointer' }} role="button" tabIndex={0}>
              <span>{tr('debts_filter_overdue')}</span>
              <strong>{overdueDebts.length}</strong>
            </div>
            <div className="stat" onClick={() => navigate('/debts?status=payment_pending_confirmation')} style={{ cursor: 'pointer' }} role="button" tabIndex={0}>
              <span>{tr('paymentPendingConfirmation')}</span>
              <strong>{paymentPendingDebts.length}</strong>
            </div>
            <div className="stat" onClick={() => navigate('/debts?status=paid')} style={{ cursor: 'pointer' }} role="button" tabIndex={0}>
              <span>{tr('debts_filter_paid')}</span>
              <strong>{paidDebts.length}</strong>
            </div>
            <div className="stat" onClick={() => navigate('/debts?status=cancelled')} style={{ cursor: 'pointer' }} role="button" tabIndex={0}>
              <span>{tr('debts_filter_cancelled')}</span>
              <strong>{debts.filter(d => d.status === 'cancelled').length}</strong>
            </div>
          </div>
        </section>
      )}

      {/* Overview tab content */}
      {(activeTab === 'overview' || !isCreditor) && <>

      {/* AI upgrade banner */}
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

      {/* ── Stat cards ─────────────────────────────────────────── */}
      <StatCard
        label={isCreditor ? tr('receivable') : tr('totalDebt')}
        value={`${totalAmount.toFixed(2)} SAR`}
        icon={CircleDollarSign}
        accent="primary"
      />
      <StatCard
        label={tr('active')}
        value={String(activeDebts.length)}
        icon={Activity}
        accent="info"
      />
      <StatCard
        label={tr('pendingConfirmation')}
        value={String(waitingDebts.length)}
        icon={Clock}
        accent="warning"
      />
      <StatCard
        label={tr('paymentPendingConfirmation')}
        value={String(paymentPendingDebts.length)}
        icon={TrendingUp}
        accent="purple"
      />

      {/* Commitment indicator — debtors only */}
      {!isCreditor && (
        <section
          className="dash-stat-card dash-stat-card--success"
          style={{ gridColumn: '1 / -1' }}
        >
          <div className="dash-stat-card__icon">
            <Award size={20} />
          </div>
          <div className="dash-stat-card__body" style={{ flex: 1 }}>
            <span className="dash-stat-card__label">{tr('commitmentIndicator')}</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginTop: '6px' }}>
              <strong className="dash-stat-card__value" style={{ minWidth: '70px' }}>
                {commitmentScore} / 100
              </strong>
              <ScoreBar score={commitmentScore} />
            </div>
          </div>
        </section>
      )}

      {/* ── Overdue alerts ──────────────────────────────────────── */}
      {overdueDebts.length > 0 && (
        <section className="wide-panel dash-overdue-panel">
          <div className="dash-section-header">
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <AlertTriangle size={18} color="var(--danger)" />
              <h2 style={{ color: 'var(--danger)', margin: 0 }}>{tr('overdueAlerts')}</h2>
            </div>
            <span className="dash-overdue-count">{overdueDebts.length}</span>
          </div>
          <div className="dash-compact-list">
            {overdueDebts.map(d => (
              <div key={d.id} className="dash-debt-row">
                <div className="dash-debt-row__avatar">{getInitials(d.debtor_name)}</div>
                <div className="dash-debt-row__info">
                  <strong>{d.debtor_name}</strong>
                  <span>{d.description}</span>
                </div>
                <div className="dash-debt-row__right">
                  <b>{d.amount} {d.currency}</b>
                  <span className="status-badge overdue">{tr('overdue')}</span>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* ── Recent debts ────────────────────────────────────────── */}
      <section className={overdueDebts.length > 0 ? 'panel' : 'wide-panel'}>
        <div className="dash-section-header">
          <h2>
            {tr('recentDebts')}
            <span className="dash-count-badge">{debts.length}</span>
          </h2>
          <a href="/debts" className="dash-view-all">
            {language === 'ar' ? 'عرض الكل' : 'View all'}
            <ArrowRight size={14} />
          </a>
        </div>
        <div className="dash-compact-list">
          {debts.slice(0, 6).map((d) => (
            <div key={d.id} className="dash-debt-row">
              <div className="dash-debt-row__avatar">{getInitials(d.debtor_name)}</div>
              <div className="dash-debt-row__info">
                <strong>{d.debtor_name}</strong>
                <span>{d.description}</span>
              </div>
              <div className="dash-debt-row__right">
                <b>{d.amount} {d.currency}</b>
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
            </div>
          ))}
          {debts.length === 0 && <p className="empty">{tr('noDebtsYet')}</p>}
        </div>
      </section>

      {/* ── Notifications panel ──────────────────────────────────── */}
      <section className="panel">
        <div className="dash-section-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Bell size={16} color="var(--text-secondary)" />
            <h2 style={{ margin: 0 }}>{tr('notifications')}</h2>
          </div>
          {unreadCount > 0 && (
            <span className="dash-unread-badge">{unreadCount}</span>
          )}
        </div>

        {isCreditor && (
          <div className="dash-stats-mini">
            <div className="dash-stats-mini__row">
              <span>{tr('paid')}</span>
              <strong style={{ color: 'var(--success)' }}>{paidDebts.length}</strong>
            </div>
            <div className="dash-stats-mini__row">
              <span>{tr('debtors')}</span>
              <strong>{new Set(debts.map(d => d.debtor_id).filter(Boolean)).size}</strong>
            </div>
          </div>
        )}

        <ul className="dash-notif-list">
          {notifications.slice(0, 5).map((n) => (
            <li key={n.id} className={`dash-notif-item${!n.read_at ? ' dash-notif-item--unread' : ''}`}>
              {!n.read_at && <span className="dash-notif-dot" />}
              <div>
                <strong>{n.title}</strong>
                <span>{n.body}</span>
              </div>
            </li>
          ))}
          {notifications.length === 0 && <p className="empty">{tr('noData')}</p>}
        </ul>
        <p className="trust-disclaimer">{tr('commitmentDisclaimer')}</p>
      </section>

      </>}
    </section>
  );
}
