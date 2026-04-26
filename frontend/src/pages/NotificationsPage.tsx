import { Check } from "lucide-react";
import { useEffect, useState } from "react";
import { Panel } from "../components/Layout";
import { apiRequest } from "../lib/api";
import { t } from "../lib/i18n";
import type { Language, NotificationItem } from "../lib/types";

interface Props { language: Language }

export function NotificationsPage({ language }: Props) {
  const tr = (key: Parameters<typeof t>[1]) => t(language, key);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [message, setMessage] = useState("");

  async function load() {
    try { setNotifications(await apiRequest<NotificationItem[]>("/notifications")); } catch { /* ignored */ }
  }

  useEffect(() => { void load(); }, []);

  async function markRead(id: string) {
    try {
      await apiRequest(`/notifications/${id}/read`, { method: "POST" });
      setMessage("Notification read");
      await load();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Failed");
    }
  }

  return (
    <Panel title={tr("notifications")}>
      {message && <div className="message">{message}</div>}
      <div className="debt-stack">
        {notifications.map((item) => (
          <article key={item.id} className={item.read_at ? "debt-item read" : "debt-item"}>
            <div>
              <strong>{item.title}</strong>
              <span>{item.body}</span>
            </div>
            <button onClick={() => void markRead(item.id)}>
              <Check size={16} /><span>{tr("save")}</span>
            </button>
          </article>
        ))}
        {notifications.length === 0 && <p className="empty">{tr("noData")}</p>}
      </div>
    </Panel>
  );
}
