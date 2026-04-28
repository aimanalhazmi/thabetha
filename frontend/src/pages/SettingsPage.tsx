import { Languages, LogOut } from 'lucide-react';
import { Panel } from '../components/Layout';
import { useAuth } from '../contexts/AuthContext';
import { t } from '../lib/i18n';
import type { Language } from '../lib/types';

interface Props {
  language: Language;
  onToggleLanguage: () => void;
}

export function SettingsPage({ language, onToggleLanguage }: Props) {
  const tr = (key: Parameters<typeof t>[1]) => t(language, key);
  const { user, signOut } = useAuth();

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
    </section>
  );
}
