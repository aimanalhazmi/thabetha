import { t } from '../lib/i18n';
import type { Language, ProfilePreview } from '../lib/types';

interface Props {
  profile: ProfilePreview;
  language: Language;
  onBack: () => void;
  onConfirm: () => void;
}

export function DebtorConfirmCard({ profile, language, onBack, onConfirm }: Props) {
  const tr = (k: Parameters<typeof t>[1]) => t(language, k);
  const score = Math.max(0, Math.min(100, profile.commitment_score));
  return (
    <div className="debtor-confirm-card" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ padding: '1rem', border: '1px solid var(--border, #e3e6ee)', borderRadius: 8, background: 'var(--surface, #fff)' }}>
        <p style={{ margin: 0, fontSize: '1.1rem', fontWeight: 600 }}>{profile.name}</p>
        <p style={{ margin: '4px 0 0', color: '#64748b' }}>{profile.phone}</p>
        <div style={{ marginTop: 12 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem' }}>
            <span>{tr('debtor_confirm_score_label')}</span>
            <strong>{score}/100</strong>
          </div>
          <div style={{ height: 8, background: '#e2e8f0', borderRadius: 4, overflow: 'hidden', marginTop: 4 }}>
            <div
              style={{
                width: `${score}%`,
                height: '100%',
                background: score >= 70 ? '#16a34a' : score >= 40 ? '#eab308' : '#dc2626',
              }}
            />
          </div>
        </div>
      </div>
      <div style={{ display: 'flex', gap: 8 }}>
        <button type="button" onClick={onBack} style={{ flex: 1 }}>
          {tr('cancel')}
        </button>
        <button type="button" className="primary-button" onClick={onConfirm} style={{ flex: 1 }}>
          {tr('debtor_confirm_proceed')}
        </button>
      </div>
    </div>
  );
}
