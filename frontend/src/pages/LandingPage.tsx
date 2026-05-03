import { Link } from 'react-router-dom';
import {
  Languages, ShieldCheck, QrCode, TrendingUp,
  Sparkles, Bell, Users, Store, UserRound, ArrowRight,
} from 'lucide-react';
import { t } from '../lib/i18n';
import type { Language } from '../lib/types';

interface Props {
  language: Language;
  onToggleLanguage: () => void;
}

type FKey = Parameters<typeof t>[1];

const FEATURES: { icon: typeof ShieldCheck; titleKey: FKey; descKey: FKey }[] = [
  { icon: ShieldCheck, titleKey: 'landingF1Title', descKey: 'landingF1Desc' },
  { icon: QrCode,      titleKey: 'landingF2Title', descKey: 'landingF2Desc' },
  { icon: TrendingUp,  titleKey: 'landingF3Title', descKey: 'landingF3Desc' },
  { icon: Sparkles,    titleKey: 'landingF4Title', descKey: 'landingF4Desc' },
  { icon: Bell,        titleKey: 'landingF5Title', descKey: 'landingF5Desc' },
  { icon: Users,       titleKey: 'landingF6Title', descKey: 'landingF6Desc' },
];

export function LandingPage({ language, onToggleLanguage }: Props) {
  const tr = (key: FKey) => t(language, key);
  const isAr = language === 'ar';

  return (
    <div className="lp" dir={isAr ? 'rtl' : 'ltr'}>

      {/* ── Header ────────────────────────────────────────────── */}
      <header className="lp-header">
        <div className="lp-container lp-header-inner">
          <div className="lp-brand">
            <div className="lp-brand-icon">
              <Store size={22} />
            </div>
            <div>
              <strong className="lp-brand-name">{tr('appName')}</strong>
              <span className="lp-brand-tag">{tr('debtTrackerSubtitle')}</span>
            </div>
          </div>
          <button className="lp-lang-btn" onClick={onToggleLanguage}>
            <Languages size={15} />
            {tr('switchLanguage')}
          </button>
        </div>
      </header>

      {/* ── Hero ──────────────────────────────────────────────── */}
      <section className="lp-hero">
        {/* background mesh blobs */}
        <div className="lp-blob lp-blob-1" aria-hidden="true" />
        <div className="lp-blob lp-blob-2" aria-hidden="true" />

        <div className="lp-container lp-hero-inner">

          {/* Left: copy */}
          <div className="lp-hero-copy lp-anim-up" style={{ '--lp-delay': '0ms' } as React.CSSProperties}>
            <span className="lp-pill">
              <Sparkles size={13} />
              {isAr ? 'إدارة ديون موثوقة' : 'Trusted debt management'}
            </span>
            <h1 className="lp-hero-h1">{tr('landingHeadline')}</h1>
            <p className="lp-hero-pitch">{tr('landingPitch')}</p>
            <div className="lp-hero-cta">
              <Link to="/auth?role=creditor" className="lp-btn-primary">
                <Store size={17} />
                {tr('forCreditors')}
                <ArrowRight size={15} className={isAr ? 'lp-flip' : ''} />
              </Link>
              <Link to="/auth?role=debtor" className="lp-btn-outline">
                <UserRound size={17} />
                {tr('forDebtors')}
              </Link>
            </div>
          </div>

          {/* Right: visual */}
          <div className="lp-hero-visual lp-anim-up" style={{ '--lp-delay': '160ms' } as React.CSSProperties}>
            {/* Glow */}
            <div className="lp-glow" aria-hidden="true" />

            {/* Main mock card */}
            <div className="lp-mock lp-float">
              <div className="lp-mock-header">
                <div className="lp-mock-avatar">أ</div>
                <div className="lp-mock-meta">
                  <span className="lp-mock-name">{isAr ? 'أحمد العلي' : 'Ahmed Al-Ali'}</span>
                  <span className="lp-mock-role">{isAr ? 'دائن' : 'Creditor'}</span>
                </div>
                <div className="lp-mock-score">
                  <TrendingUp size={13} />
                  <span>{87}</span>
                </div>
              </div>
              <div className="lp-mock-body">
                <div className="lp-mock-row">
                  <span>{isAr ? 'مبلغ الدين' : 'Debt amount'}</span>
                  <strong>{isAr ? '٢٬٥٠٠ ر.س' : 'SAR 2,500'}</strong>
                </div>
                <div className="lp-mock-row">
                  <span>{isAr ? 'تاريخ الاستحقاق' : 'Due date'}</span>
                  <strong>{isAr ? '١٥ مايو ٢٠٢٥' : '15 May 2025'}</strong>
                </div>
                <div className="lp-mock-badge">
                  <span className="lp-mock-check">✓</span>
                  {isAr ? 'مؤكد من الطرفين' : 'Confirmed by both parties'}
                </div>
              </div>
            </div>

            {/* Floating stat widget */}
            <div className="lp-stat-card lp-float-slow">
              <div className="lp-stat-icon-wrap">
                <TrendingUp size={18} />
              </div>
              <div>
                <p className="lp-stat-label">{tr('commitmentIndicator')}</p>
                <p className="lp-stat-value">{87} / 100</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Features ──────────────────────────────────────────── */}
      <section className="lp-section">
        <div className="lp-container">
          <div className="lp-section-head">
            <h2 className="lp-section-title">{tr('landingFeaturesTitle')}</h2>
          </div>
          <div className="lp-features-grid">
            {FEATURES.map(({ icon: Icon, titleKey, descKey }, i) => (
              <div
                key={titleKey}
                className="lp-feature-card lp-anim-up"
                style={{ '--lp-delay': `${i * 70}ms` } as React.CSSProperties}
              >
                <div className="lp-feature-icon">
                  <Icon size={20} />
                </div>
                <h3 className="lp-feature-title">{tr(titleKey)}</h3>
                <p className="lp-feature-desc">{tr(descKey)}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── How it works ──────────────────────────────────────── */}
      <section className="lp-section lp-hiw-section">
        <div className="lp-container">
          <div className="lp-section-head">
            <h2 className="lp-section-title">{tr('landingHowItWorks')}</h2>
          </div>
          <div className="lp-hiw-grid">
            {([1, 2, 3] as const).map((n) => (
              <div
                key={n}
                className="lp-step lp-anim-up"
                style={{ '--lp-delay': `${(n - 1) * 100}ms` } as React.CSSProperties}
              >
                <div className="lp-step-num">{n}</div>
                <div className="lp-step-body">
                  <h3>{tr(`landingStep${n}Title` as FKey)}</h3>
                  <p>{tr(`landingStep${n}Desc` as FKey)}</p>
                </div>
                {n < 3 && <div className="lp-step-arrow" aria-hidden="true" />}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Role cards ────────────────────────────────────────── */}
      <section className="lp-section">
        <div className="lp-container">
          <div className="lp-role-grid">
            <div className="lp-role-card lp-role-creditor lp-anim-up" style={{ '--lp-delay': '0ms' } as React.CSSProperties}>
              <div className="lp-role-icon"><Store size={22} /></div>
              <h3>{tr('forCreditors')}</h3>
              <p>{tr('creditorPitch')}</p>
              <Link to="/auth?role=creditor" className="lp-btn-primary lp-btn-sm">
                {tr('getStarted')}
                <ArrowRight size={14} className={isAr ? 'lp-flip' : ''} />
              </Link>
            </div>
            <div className="lp-role-card lp-role-debtor lp-anim-up" style={{ '--lp-delay': '100ms' } as React.CSSProperties}>
              <div className="lp-role-icon"><UserRound size={22} /></div>
              <h3>{tr('forDebtors')}</h3>
              <p>{tr('debtorPitch')}</p>
              <Link to="/auth?role=debtor" className="lp-btn-outline lp-btn-sm">
                {tr('getStarted')}
                <ArrowRight size={14} className={isAr ? 'lp-flip' : ''} />
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* ── CTA banner ────────────────────────────────────────── */}
      <section className="lp-section">
        <div className="lp-container">
          <div className="lp-cta-card">
            <div className="lp-cta-blob" aria-hidden="true" />
            <div className="lp-cta-inner">
              <h2 className="lp-cta-title">{tr('landingCtaTitle')}</h2>
              <p className="lp-cta-desc">{tr('landingCtaDesc')}</p>
              <div className="lp-cta-btns">
                <Link to="/auth?role=creditor" className="lp-btn-gold">
                  {tr('forCreditors')}
                </Link>
                <Link to="/auth?role=debtor" className="lp-btn-ghost-white">
                  {tr('forDebtors')}
                </Link>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Footer ────────────────────────────────────────────── */}
      <footer className="lp-footer">
        <div className="lp-container lp-footer-inner">
          <p>© {new Date().getFullYear()} {tr('appName')} — {isAr ? 'جميع الحقوق محفوظة' : 'All rights reserved'}</p>
          <p className="lp-footer-disclaimer">{tr('commitmentDisclaimer')}</p>
        </div>
      </footer>
    </div>
  );
}
