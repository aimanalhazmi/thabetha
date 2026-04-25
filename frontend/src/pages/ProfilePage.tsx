import { Check, Store } from "lucide-react";
import { useEffect, useState } from "react";
import { Input, Panel } from "../components/Layout";
import { apiRequest } from "../lib/api";
import { t } from "../lib/i18n";
import type { Language, Profile } from "../lib/types";

interface Props { language: Language }

export function ProfilePage({ language }: Props) {
  const tr = (key: Parameters<typeof t>[1]) => t(language, key);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [message, setMessage] = useState("");
  const [businessForm, setBusinessForm] = useState({ shop_name: "", activity_type: "", location: "", description: "" });

  useEffect(() => {
    void apiRequest<Profile>("/profiles/me").then(setProfile).catch(() => {});
  }, []);

  async function saveProfile() {
    if (!profile) return;
    try {
      const updated = await apiRequest<Profile>("/profiles/me", { method: "PATCH", body: JSON.stringify(profile) });
      setProfile(updated);
      setMessage("Profile saved");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Failed");
    }
  }

  async function saveBusiness() {
    try {
      await apiRequest("/profiles/business-profile", { method: "POST", body: JSON.stringify(businessForm) });
      setMessage("Business profile saved");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Failed");
    }
  }

  if (!profile) return <p className="empty">{tr("noData")}</p>;

  return (
    <section className="split">
      {message && <div className="message wide-panel">{message}</div>}
      <Panel title={tr("profile")}>
        <Input label={tr("name")} value={profile.name} onChange={(v) => setProfile({ ...profile, name: v })} />
        <Input label={tr("phone")} value={profile.phone} onChange={(v) => setProfile({ ...profile, phone: v })} />
        <label className="check-row">
          <input type="checkbox" checked={profile.ai_enabled} onChange={(e) => setProfile({ ...profile, ai_enabled: e.target.checked })} />
          <span>{tr("aiEnabled")}</span>
        </label>
        <label className="check-row">
          <input type="checkbox" checked={profile.whatsapp_enabled} onChange={(e) => setProfile({ ...profile, whatsapp_enabled: e.target.checked })} />
          <span>{tr("whatsapp")}</span>
        </label>
        <div className="trust-score">
          <span>{tr("trustScore")}</span>
          <strong>{profile.trust_score}</strong>
        </div>
        <button className="primary-button" onClick={() => void saveProfile()}>
          <Check size={18} /><span>{tr("save")}</span>
        </button>
      </Panel>
      <Panel title={tr("businessProfile")}>
        <Input label={tr("shopName")} value={businessForm.shop_name} onChange={(v) => setBusinessForm({ ...businessForm, shop_name: v })} />
        <Input label={tr("activityType")} value={businessForm.activity_type} onChange={(v) => setBusinessForm({ ...businessForm, activity_type: v })} />
        <Input label={tr("location")} value={businessForm.location} onChange={(v) => setBusinessForm({ ...businessForm, location: v })} />
        <Input label={tr("description")} value={businessForm.description} onChange={(v) => setBusinessForm({ ...businessForm, description: v })} />
        <button className="primary-button" onClick={() => void saveBusiness()}>
          <Store size={18} /><span>{tr("save")}</span>
        </button>
      </Panel>
    </section>
  );
}
