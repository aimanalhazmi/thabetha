import { Languages, LogOut } from 'lucide-react';
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

  useEffect(() => {
    apiRequest<{ groups_enabled: boolean }>('/profiles/me')
      .then((p) => setGroupsEnabled(p.groups_enabled))
      .catch(() => {});
  }, []);

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
      <Panel title={tr('settings')}>
        <div className="settings-row">
          <span>{tr('languageLabel')}</span>
          <button className="ghost-button" onClick={onToggleLanguage}>
            <Languages size={16} />
            <span>{tr('switchLanguage')}</span>
          </button>
        </div>
        <div className="settings-row">
          <span>{tr('email')}</span>
          <strong>{user?.email}</strong>
        </div>
        <div className="settings-row">
          <span>{tr('accountType')}</span>
          <strong>{user?.account_type}</strong>
        </div>
        <button className="primary-button" onClick={() => void signOut()}>
          <LogOut size={16} />
          <span>{tr('signOut')}</span>
        </button>
      </Panel>

      <Panel title={tr('commitmentIndicator')}>
        <p>{tr('commitmentDisclaimer')}</p>
      </Panel>

      <Panel title={tr('settingsGroupsFeature')}>
        <p className="muted">{tr('settingsGroupsFeatureHint')}</p>
        <div className="settings-row">
          <span>{tr('settingsGroupsFeature')}</span>
          <button className="ghost-button" onClick={() => void toggleGroups()}>
            {groupsEnabled ? tr('groupsDecline') : tr('groupsAccept')}
          </button>
        </div>
      </Panel>
    </section>
  );
}
