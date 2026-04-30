import { Languages, LogOut, Users } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Panel } from '../components/Layout';
import { useAuth } from '../contexts/AuthContext';
import { apiRequest } from '../lib/api';
import { t } from '../lib/i18n';
import type { Language } from '../lib/types';

interface Props {
  language: Language;
  onToggleLanguage: () => void;
}

export function SettingsPage({ language, onToggleLanguage }: Props) {
  const tr = (key: Parameters<typeof t>[1]) => t(language, key);
  const { user, signOut } = useAuth();
  const [groupsEnabled, setGroupsEnabled] = useState<boolean>(true);

  // ── Data fetching — untouched ─────────────────────────────────
  useEffect(() => {
    apiRequest<{ groups_enabled: boolean }>('/profiles/me')
      .then((p) => setGroupsEnabled(p.groups_enabled))
      .catch(() => {});
  }, []);

  // ── Handler — untouched ───────────────────────────────────────
  async function toggleGroups() {
    const next = !groupsEnabled;
    setGroupsEnabled(next);
    try {
      await apiRequest('/profiles/me', { method: 'PATCH', body: JSON.stringify({ groups_enabled: next }) });
    } catch {
      setGroupsEnabled(!next);
    }
  }

  return (
    <section className="split">
      {/* General settings */}
      <Panel title={tr('settings')}>
        <div className="settings-section">
          <div className="settings-row">
            <span>{tr('languageLabel')}</span>
            <button className="ghost-button" onClick={onToggleLanguage}>
              <Languages size={16} />
              <span>{tr('switchLanguage')}</span>
            </button>
          </div>
          <div className="settings-row">
            <span>{tr('email')}</span>
            <strong style={{ fontSize: '0.88rem', color: 'var(--text-secondary)' }}>{user?.email}</strong>
          </div>
          <div className="settings-row" style={{ borderBottom: 'none' }}>
            <span>{tr('accountType')}</span>
            <span className="dash-count-badge" style={{ textTransform: 'capitalize' }}>{user?.account_type}</span>
          </div>
        </div>

        <button className="settings-signout" onClick={() => void signOut()}>
          <LogOut size={16} />
          <span>{tr('signOut')}</span>
        </button>
      </Panel>

      {/* Commitment indicator info */}
      <Panel title={tr('commitmentIndicator')}>
        <p style={{ fontSize: '0.88rem', color: 'var(--text-secondary)', lineHeight: 1.6, margin: 0 }}>
          {tr('commitmentDisclaimer')}
        </p>
      </Panel>

      {/* Groups feature toggle */}
      <Panel title={tr('settingsGroupsFeature')}>
        <p style={{ fontSize: '0.84rem', color: 'var(--text-secondary)', margin: '0 0 12px', lineHeight: 1.6 }}>
          {tr('settingsGroupsFeatureHint')}
        </p>
        <div className="settings-section">
          <label className="toggle-row" style={{ borderBottom: 'none' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Users size={16} color="var(--text-secondary)" />
              <span className="toggle-row__label">{tr('settingsGroupsFeature')}</span>
            </div>
            <div className="toggle-switch">
              <input
                type="checkbox"
                checked={groupsEnabled}
                onChange={() => void toggleGroups()}
              />
              <span className="toggle-switch__track" />
            </div>
          </label>
        </div>
      </Panel>
    </section>
  );
}
