import { Check } from "lucide-react";
import { useEffect, useState } from "react";
import { Panel } from "../components/Layout";
import { WhatsAppDeliveryBadge } from "../components/WhatsAppDeliveryBadge";
import { apiRequest } from "../lib/api";
import { humanizeError } from "../lib/errors";
import { t } from "../lib/i18n";
import type { Language, NotificationItem } from "../lib/types";

interface Props { language: Language }

export function NotificationsPage({ language }: Props) {
  const tr = (key: Parameters<typeof t>[1]) => t(language, key);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [message, setMessage] = useState("");
  const [markingRead, setMarkingRead] = useState(false);

  async function load() {
    try {
      setNotifications(await apiRequest<NotificationItem[]>("/notifications"));
    } catch (err) {
      setMessage(humanizeError(err, language, 'loadNotifications'));
    }
  }

  useEffect(() => { void load(); }, []);

  async function markRead(id: string) {
    setMarkingRead(true);
    try {
      await apiRequest(`/notifications/${id}/read`, { method: "POST" });
      await load();
    } catch (err) {
      setMessage(humanizeError(err, language, 'transition'));
    } finally {
      setMarkingRead(false);
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
              {item.whatsapp_status && item.whatsapp_status !== 'not_attempted' && (
                <WhatsAppDeliveryBadge
                  status={item.whatsapp_status}
                  failedReason={item.whatsapp_failed_reason}
                  language={language}
                />
              )}
            </div>
            <button disabled={markingRead} onClick={() => void markRead(item.id)}>
              <Check size={16} /><span>{markingRead ? '…' : tr("save")}</span>
            </button>
          </article>
        ))}
        {notifications.length === 0 && <p className="empty">{tr("noNotificationsYet")}</p>}
      </div>
    </Panel>
  );
}
