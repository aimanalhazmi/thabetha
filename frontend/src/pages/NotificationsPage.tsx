import { Bell, Check } from "lucide-react";
import { useEffect, useState } from "react";
import { Panel } from "../components/Layout";
import { useToast } from "../contexts/ToastContext";
import { apiRequest } from "../lib/api";
import { t } from "../lib/i18n";
import type { Language, NotificationItem } from "../lib/types";

interface Props { language: Language }

export function NotificationsPage({ language }: Props) {
  const tr = (key: Parameters<typeof t>[1]) => t(language, key);
  const { showToast } = useToast();
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [loading, setLoading] = useState<Record<string, boolean>>({});

  async function load() {
    try { setNotifications(await apiRequest<NotificationItem[]>("/notifications")); } catch { /* ignored */ }
  }

  useEffect(() => { void load(); }, []);

  async function markRead(id: string) {
    setLoading(prev => ({ ...prev, [id]: true }));
    try {
      await apiRequest(`/notifications/${id}/read`, { method: "POST" });
      showToast(language === "ar" ? "تم تحديد الإشعار كمقروء" : "Notification marked as read", "success");
      await load();
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Failed", "error");
    } finally {
      setLoading(prev => ({ ...prev, [id]: false }));
    }
  }

  const unread = notifications.filter(n => !n.read_at);
  const read = notifications.filter(n => !!n.read_at);

  return (
    <Panel title={`${tr("notifications")} ${unread.length > 0 ? `(${unread.length} ${tr("unread")})` : ""}`}>
      {notifications.length === 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '12px', padding: '40px 0' }}>
          <Bell size={40} style={{ color: 'var(--text-muted)' }} />
          <p className="empty" style={{ padding: 0 }}>{tr("noUnread")}</p>
        </div>
      )}

      {unread.length > 0 && (
        <>
          <p style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            {tr("unread")}
          </p>
          <div className="debt-stack" style={{ marginBottom: '16px' }}>
            {unread.map((item) => (
              <article key={item.id} className="notif-item notif-unread">
                <div className="notif-dot" />
                <div className="notif-body">
                  <strong>{item.title}</strong>
                  <span>{item.body}</span>
                  <small>{new Date(item.created_at).toLocaleString()}</small>
                </div>
                <button
                  className="icon-button"
                  disabled={loading[item.id]}
                  onClick={() => void markRead(item.id)}
                  title={tr("markRead")}
                >
                  <Check size={16} />
                </button>
              </article>
            ))}
          </div>
        </>
      )}

      {read.length > 0 && (
        <>
          <p style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            {language === 'ar' ? 'المقروءة' : 'Read'}
          </p>
          <div className="debt-stack">
            {read.map((item) => (
              <article key={item.id} className="notif-item notif-read">
                <div className="notif-body">
                  <strong>{item.title}</strong>
                  <span>{item.body}</span>
                  <small>{new Date(item.created_at).toLocaleString()}</small>
                </div>
              </article>
            ))}
          </div>
        </>
      )}
    </Panel>
  );
}
