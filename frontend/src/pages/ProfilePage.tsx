import { Check, Store } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Input, Panel } from '../components/Layout';
import { useAuth } from '../contexts/AuthContext';
import { apiRequest } from '../lib/api';
import { t } from '../lib/i18n';
import type { Language, Profile } from '../lib/types';

const COMMON_CURRENCIES = ['SAR', 'USD', 'EUR', 'GBP', 'AED', 'KWD', 'QAR', 'BHD', 'OMR', 'JOD', 'EGP'];

interface Props { language: Language }

function getInitials(name: string) {
  return name.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase();
}

function ScoreBar({ score }: { score: number }) {
  const color = score >= 70 ? 'var(--success)' : score >= 40 ? 'var(--warning)' : 'var(--danger)';
  return (
    <div className="score-bar">
      <div className="score-bar-fill" style={{ width: `${score}%`, background: color }} />
    </div>
  );
}

export function ProfilePage({ language }: Props) {
  const tr = (key: Parameters<typeof t>[1]) => t(language, key);
  const { user } = useAuth();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [message, setMessage] = useState('');

  const isCreditor = user?.account_type === 'creditor' || user?.account_type === 'both' || user?.account_type === 'business';

  // ── Data fetching — untouched ─────────────────────────────────
  useEffect(() => {
    void apiRequest<Profile>('/profiles/me').then(setProfile).catch(() => {});
  }, []);

  // ── Handler — untouched ───────────────────────────────────────
  async function saveProfile() {
    if (!profile) return;
    try {
      const updated = await apiRequest<Profile>('/profiles/me', { method: 'PATCH', body: JSON.stringify(profile) });
      setProfile(updated);
      setMessage(tr('toastProfileSaved'));
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'Failed');
    }
  }

  if (!profile) {
    return (
      <div className="dash-loading">
        <div className="spinner" />
      </div>
    );
  }

  const roleLabel = user?.account_type === 'creditor' || user?.account_type === 'business'
    ? tr('creditor')
    : user?.account_type === 'both'
      ? tr('both')
      : tr('debtor');

  return (
    <section>
      {message && <div className="message" style={{ marginBottom: 16 }}>{message}</div>}

      {/* Profile hero card */}
      <div className="profile-hero">
        <div className="profile-hero__avatar">{getInitials(profile.name)}</div>
        <div className="profile-hero__info">
          <span className="profile-hero__name">{profile.name}</span>
          <span className="profile-hero__badge">{roleLabel}</span>
        </div>
        {!isCreditor && (
          <div className="profile-hero__score">
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
              <span style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', fontWeight: 500 }}>
                {tr('commitmentIndicator')}
              </span>
              <strong style={{ fontSize: '0.88rem', color: 'var(--primary-dark)' }}>
                {profile.commitment_score} / 100
              </strong>
            </div>
            <ScoreBar score={profile.commitment_score} />
            <p className="trust-disclaimer" style={{ marginTop: 6 }}>{tr('commitmentDisclaimer')}</p>
          </div>
        )}
      </div>

      <div className="split" style={{ marginTop: 20 }}>
        {/* Personal info panel */}
        <Panel title={tr('profile')}>
          <Input label={tr('name')} value={profile.name} onChange={(v) => setProfile({ ...profile, name: v })} />
          <Input label={tr('phone')} value={profile.phone} onChange={(v) => setProfile({ ...profile, phone: v })} />

          <div className="field">
            <span>{tr('defaultCurrency')}</span>
            <select
              value={profile.default_currency ?? 'SAR'}
              onChange={(e) => setProfile({ ...profile, default_currency: e.target.value })}
            >
              {COMMON_CURRENCIES.map(c => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </div>

          <div className="profile-toggles">
            <label className="toggle-row">
              <span className="toggle-row__label">{tr('aiEnabled')}</span>
              <div className="toggle-switch">
                <input
                  type="checkbox"
                  checked={profile.ai_enabled}
                  onChange={(e) => setProfile({ ...profile, ai_enabled: e.target.checked })}
                />
                <span className="toggle-switch__track" />
              </div>
            </label>
            <label className="toggle-row">
              <span className="toggle-row__label">{tr('whatsapp')}</span>
              <div className="toggle-switch">
                <input
                  type="checkbox"
                  checked={profile.whatsapp_enabled}
                  onChange={(e) => setProfile({ ...profile, whatsapp_enabled: e.target.checked })}
                />
                <span className="toggle-switch__track" />
              </div>
            </label>
          </div>

          <button className="primary-button" style={{ width: '100%', justifyContent: 'center' }} onClick={() => void saveProfile()}>
            <Check size={18} /><span>{tr('save')}</span>
          </button>
        </Panel>

        {/* Business profile panel (creditor only) */}
        {isCreditor && (
          <Panel title={tr('businessProfile')}>
            <Input label={tr('shopName')} value={profile.shop_name ?? ''} onChange={(v) => setProfile({ ...profile, shop_name: v })} />
            <Input label={tr('activityType')} value={profile.activity_type ?? ''} onChange={(v) => setProfile({ ...profile, activity_type: v })} />
            <Input label={tr('location')} value={profile.shop_location ?? ''} onChange={(v) => setProfile({ ...profile, shop_location: v })} />
            <Input label={tr('description')} value={profile.shop_description ?? ''} onChange={(v) => setProfile({ ...profile, shop_description: v })} />
            <Input label={tr('taxId')} value={profile.tax_id ?? ''} onChange={(v) => setProfile({ ...profile, tax_id: v })} />
            <button className="primary-button" style={{ width: '100%', justifyContent: 'center' }} onClick={() => void saveProfile()}>
              <Store size={18} /><span>{tr('save')}</span>
            </button>
          </Panel>
        )}
      </div>
    </section>
  );
}
