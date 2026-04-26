import { Check, Store } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Input, Panel } from '../components/Layout';
import { useAuth } from '../contexts/AuthContext';
import { useToast } from '../contexts/ToastContext';
import { apiRequest } from '../lib/api';
import { t } from '../lib/i18n';
import type { Language, Profile } from '../lib/types';

interface Props { language: Language }

export function ProfilePage({ language }: Props) {
  const tr = (key: Parameters<typeof t>[1]) => t(language, key);
  const { user } = useAuth();
  const { showToast } = useToast();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [saving, setSaving] = useState(false);

  const isCreditor = user?.account_type === 'creditor' || user?.account_type === 'both';

  useEffect(() => {
    void apiRequest<Profile>('/profiles/me').then(setProfile).catch(() => {});
  }, []);

  async function saveProfile() {
    if (!profile) return;
    setSaving(true);
    try {
      const updated = await apiRequest<Profile>('/profiles/me', { method: 'PATCH', body: JSON.stringify(profile) });
      setProfile(updated);
      showToast(language === 'ar' ? 'تم حفظ الملف الشخصي' : 'Profile saved', 'success');
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'Failed', 'error');
    } finally {
      setSaving(false);
    }
  }

  if (!profile) return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', padding: '60px' }}>
      <div className="spinner" />
    </div>
  );

  const trustColor = profile.trust_score >= 70 ? 'var(--success)' : profile.trust_score >= 40 ? 'var(--warning)' : 'var(--danger)';

  return (
    <section className="split">
      <Panel title={tr('profile')}>
        <Input label={tr('name')} value={profile.name} onChange={(v) => setProfile({ ...profile, name: v })} />
        <Input label={tr('phone')} value={profile.phone} onChange={(v) => setProfile({ ...profile, phone: v })} />

        {/* Trust score with visual bar */}
        <div className="trust-score">
          <div>
            <span>{tr('trustScore')}</span>
            <p className="trust-disclaimer">{tr('trustScoreDisclaimer')}</p>
          </div>
          <strong style={{ fontSize: '1.6rem', color: trustColor }}>{profile.trust_score}<small style={{ fontSize: '0.7em', color: 'var(--text-muted)' }}>/100</small></strong>
        </div>
        <div className="trust-bar">
          <div className="trust-bar-fill" style={{ width: `${profile.trust_score}%`, background: trustColor }} />
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginTop: '8px' }}>
          <label className="check-row">
            <input type="checkbox" checked={profile.ai_enabled} onChange={(e) => setProfile({ ...profile, ai_enabled: e.target.checked })} />
            <span>{tr('aiEnabled')}</span>
          </label>
          <label className="check-row">
            <input type="checkbox" checked={profile.whatsapp_enabled} onChange={(e) => setProfile({ ...profile, whatsapp_enabled: e.target.checked })} />
            <span>{tr('whatsapp')}</span>
          </label>
        </div>

        <button className="primary-button" disabled={saving} onClick={() => void saveProfile()}>
          <Check size={18} /><span>{saving ? '...' : tr('save')}</span>
        </button>
      </Panel>

      {isCreditor && (
        <Panel title={tr('businessProfile')}>
          <Input label={tr('shopName')} value={profile.shop_name ?? ''} onChange={(v) => setProfile({ ...profile, shop_name: v })} />
          <Input label={tr('activityType')} value={profile.activity_type ?? ''} onChange={(v) => setProfile({ ...profile, activity_type: v })} />
          <Input label={tr('location')} value={profile.shop_location ?? ''} onChange={(v) => setProfile({ ...profile, shop_location: v })} />
          <Input label={tr('shopDescription')} value={profile.shop_description ?? ''} onChange={(v) => setProfile({ ...profile, shop_description: v })} />
          <Input label={tr('taxId')} value={profile.tax_id ?? ''} onChange={(v) => setProfile({ ...profile, tax_id: v })} />
          <button className="primary-button" disabled={saving} onClick={() => void saveProfile()}>
            <Store size={18} /><span>{saving ? '...' : tr('save')}</span>
          </button>
        </Panel>
      )}
    </section>
  );
}
