import { Link } from 'react-router-dom';
import { Languages, ScanLine, Wallet } from 'lucide-react';
import { t } from '../lib/i18n';
import type { Language } from '../lib/types';

interface Props {
  language: Language;
  onToggleLanguage: () => void;
}

export function LandingPage({ language, onToggleLanguage }: Props) {
  const tr = (key: Parameters<typeof t>[1]) => t(language, key);

  return (
    <div className="landing-page">
      <header className="landing-header">
        <div className="landing-brand">
          <strong>{tr('appName')}</strong>
          <span>{tr('tagline')}</span>
        </div>
        <button className="ghost-button" onClick={onToggleLanguage}>
          <Languages size={16} />
          <span>{language === 'ar' ? 'English' : 'العربية'}</span>
        </button>
      </header>

      <main className="landing-hero">
        <h1>{tr('landingHeadline')}</h1>
        <p>{tr('landingPitch')}</p>
        <div className="landing-cta">
          <Link to="/auth?role=creditor" className="primary-button">
            <Wallet size={18} />
            <span>{tr('forCreditors')}</span>
          </Link>
          <Link to="/auth?role=debtor" className="secondary-button">
            <ScanLine size={18} />
            <span>{tr('forDebtors')}</span>
          </Link>
        </div>
      </main>

      <section className="landing-roles">
        <article>
          <h2>{tr('forCreditors')}</h2>
          <p>{tr('creditorPitch')}</p>
        </article>
        <article>
          <h2>{tr('forDebtors')}</h2>
          <p>{tr('debtorPitch')}</p>
        </article>
      </section>

      <footer className="landing-footer">
        <p>{tr('commitmentDisclaimer')}</p>
      </footer>
    </div>
  );
}
