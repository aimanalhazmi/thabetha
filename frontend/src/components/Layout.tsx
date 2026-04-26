import { Bell, Bot, CreditCard, Languages, LayoutDashboard, LogOut, QrCode, RefreshCw, Store, UserRound, Users } from 'lucide-react';
import type { ReactNode } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { t, type TranslationKey } from '../lib/i18n';
import type { Language } from '../lib/types';

const navItems: Array<{ path: string; icon: typeof LayoutDashboard; label: TranslationKey }> = [
  { path: '/dashboard', icon: LayoutDashboard, label: 'dashboard' },
  { path: '/debts', icon: CreditCard, label: 'debts' },
  { path: '/profile', icon: UserRound, label: 'profile' },
  { path: '/qr', icon: QrCode, label: 'qr' },
  { path: '/groups', icon: Users, label: 'groups' },
  { path: '/ai', icon: Bot, label: 'ai' },
  { path: '/notifications', icon: Bell, label: 'notifications' },
];

interface Props {
  language: Language;
  onToggleLanguage: () => void;
  onRefresh: () => void;
  currentPageLabel: TranslationKey;
  children: ReactNode;
}

export function Layout({ language, onToggleLanguage, onRefresh, currentPageLabel, children }: Props) {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();
  const tr = (key: TranslationKey) => t(language, key);

  async function handleSignOut() {
    await signOut();
    navigate('/');
  }

  const initials = user?.name
    ? user.name.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase()
    : '?';

  const roleLabel = user?.account_type === 'creditor'
    ? tr('creditor')
    : user?.account_type === 'both'
      ? tr('both')
      : tr('debtor');

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-header">
          <div className="brand">
            <div className="brand-icon">
              <Store size={22} />
            </div>
            <div className="brand-text">
              <strong>{tr('appName')}</strong>
              <span>Debt Tracker</span>
            </div>
          </div>
        </div>

        {user && (
          <div className="user-card">
            <div className="user-card-inner">
              <div className="user-avatar">{initials}</div>
              <div className="user-card-info">
                <span className="user-name">{user.name}</span>
                <span className="user-email">{user.email}</span>
              </div>
            </div>
            <span className="user-badge">{roleLabel}</span>
          </div>
        )}

        <nav className="nav-section">
          <div className="nav-label">{language === 'ar' ? 'القائمة' : 'Menu'}</div>
          <div className="nav-list">
            {navItems.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.path}
                  to={item.path}
                  className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}
                >
                  <Icon size={18} />
                  <span>{tr(item.label)}</span>
                </NavLink>
              );
            })}
          </div>
        </nav>

        <div className="sidebar-footer">
          <button className="nav-item" onClick={onToggleLanguage}>
            <Languages size={18} />
            <span>{language === 'ar' ? 'English' : 'العربية'}</span>
          </button>
          <button className="nav-item signout-btn" onClick={() => void handleSignOut()}>
            <LogOut size={18} />
            <span>{tr('signOut')}</span>
          </button>
        </div>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <span className="eyebrow">{user?.email ?? ''}</span>
            <h1>{tr(currentPageLabel)}</h1>
          </div>
          <button className="icon-button" title={tr('refresh')} onClick={onRefresh}>
            <RefreshCw size={18} />
          </button>
        </header>
        {children}
      </section>
    </main>
  );
}

// Shared sub-components used across pages
export function Stat({ label, value }: { label: string; value: string }) {
  return (
    <section className="stat">
      <span>{label}</span>
      <strong>{value}</strong>
    </section>
  );
}

export function Panel({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="panel">
      <h2>{title}</h2>
      {children}
    </section>
  );
}

export function Input({
  label,
  value,
  onChange,
  type = 'text',
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: string;
  placeholder?: string;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      <input type={type} value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} />
    </label>
  );
}
