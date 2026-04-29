import { useEffect, useState } from "react";
import { groups as groupsApi } from "../lib/api";
import { t } from "../lib/i18n";
import type { Group, Language } from "../lib/types";

interface Props {
  debtorId: string | null;
  value: string | null;
  onChange: (id: string | null) => void;
  language: Language;
}

export function GroupSelector({ debtorId, value, onChange, language }: Props) {
  const tr = (key: Parameters<typeof t>[1]) => t(language, key);
  const [sharedGroups, setSharedGroups] = useState<Group[]>([]);

  useEffect(() => {
    if (!debtorId) { setSharedGroups([]); onChange(null); return; }
    groupsApi.shared(debtorId)
      .then(setSharedGroups)
      .catch(() => setSharedGroups([]));
  }, [debtorId]);

  if (sharedGroups.length === 0) return null;

  return (
    <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      <span className="muted">{tr("groupsSelectorLabel")}</span>
      <select
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value || null)}
        style={{ padding: "6px 8px", borderRadius: 6, border: "1px solid var(--border)", background: "var(--surface)", color: "var(--text)" }}
      >
        <option value="">{tr("groupsNoGroupOption")}</option>
        {sharedGroups.map((g) => (
          <option key={g.id} value={g.id}>{g.name}</option>
        ))}
      </select>
    </label>
  );
}
