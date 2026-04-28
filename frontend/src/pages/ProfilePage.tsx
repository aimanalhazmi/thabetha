import { Check, Store } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Input, Panel } from '../components/Layout';
import { useAuth } from '../contexts/AuthContext';
import { apiRequest } from '../lib/api';
import { t } from '../lib/i18n';
import type { Language, Profile } from '../lib/types';

interface Props { language: Language }

export function ProfilePage({ language }: Props) {
  const tr = (key: Parameters<typeof t>[1]) => t(language, key);
  const { user } = useAuth();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [message, setMessage] = useState('');

  const isCreditor = user?.account_type === 'creditor' || user?.account_type === 'both' || user?.account_type === 'business';

  useEffect(() => {
    void apiRequest<Profile>('/profiles/me').then(setProfile).catch(() => {});
  }, []);

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

  if (!profile) return <p className="empty">{tr('loading')}</p>;

  return (
    <section className="split">
      {message && <div className="message" style={{ gridColumn: '1 / -1' }}>{message}</div>}
      <Panel title={tr('profile')}>
        <Input label={tr('name')} value={profile.name} onChange={(v) => setProfile({ ...profile, name: v })} />
        <Input label={tr('phone')} value={profile.phone} onChange={(v) => setProfile({ ...profile, phone: v })} />

        <div className="trust-score">
          <span>{tr('commitmentIndicator')}</span>
          <strong>{profile.commitment_score} / 100</strong>
        </div>
        <p className="trust-disclaimer">{tr('commitmentDisclaimer')}</p>

        <label className="check-row">
          <input type="checkbox" checked={profile.ai_enabled} onChange={(e) => setProfile({ ...profile, ai_enabled: e.target.checked })} />
          <span>{tr('aiEnabled')}</span>
        </label>
        <label className="check-row">
          <input type="checkbox" checked={profile.whatsapp_enabled} onChange={(e) => setProfile({ ...profile, whatsapp_enabled: e.target.checked })} />
          <span>{tr('whatsapp')}</span>
        </label>

        <button className="primary-button" onClick={() => void saveProfile()}>
          <Check size={18} /><span>{tr('save')}</span>
        </button>
      </Panel>

      {isCreditor && (
        <Panel title={tr('businessProfile')}>
          <Input label={tr('shopName')} value={profile.shop_name ?? ''} onChange={(v) => setProfile({ ...profile, shop_name: v })} />
          <Input label={tr('activityType')} value={profile.activity_type ?? ''} onChange={(v) => setProfile({ ...profile, activity_type: v })} />
          <Input label={tr('location')} value={profile.shop_location ?? ''} onChange={(v) => setProfile({ ...profile, shop_location: v })} />
          <Input label={tr('description')} value={profile.shop_description ?? ''} onChange={(v) => setProfile({ ...profile, shop_description: v })} />
          <Input label={tr('taxId')} value={profile.tax_id ?? ''} onChange={(v) => setProfile({ ...profile, tax_id: v })} />
          <button className="primary-button" onClick={() => void saveProfile()}>
            <Store size={18} /><span>{tr('save')}</span>
          </button>
        </Panel>
      )}
    </section>
  );
}
